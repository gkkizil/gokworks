"""Integrated, asynchronous Qt workflow for drawing-based 1D tolerance chains."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt,QSignalBlocker,QFileSystemWatcher,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QTabWidget,QLineEdit,QComboBox,
    QTableView,QCheckBox,QFileDialog,QMessageBox,QApplication,QMenu,QDialog,QDialogButtonBox)

from tolerance_stack.models import Project,Term,number,fmt,manual_dimension,snapshot as project_snapshot
from tolerance_stack.calculator import calculate,Cancelled,check_cancel
from tolerance_stack.chain import validate,ChainIssue
from tolerance_stack import storage,solidworks_reader,drawing_writer,report
from tolerance_stack.diagram import draw_chain,draw_contributions,draw_histogram
from ..components import BasePage,ValueForm,PathPicker,card,label,button,scroll,configure_view,show_details
from ..models import Column,TableModel,FilterProxy
from .stack_dialogs import MemorySettings,DimensionDialog,TermDialog,IsoPairDialog,KINDS,KIND_TITLES,DIST
from .stack_widgets import Disclosure,StackDiagram,compact,short_name


METHODS={'Worst-Case':'worst_case','Worst-Case + RSS':'rss','Worst-Case + RSS + Monte Carlo':'all'}
DISTRIBUTIONS={'Normal':'normal','Uniform':'uniform','Üçgensel':'triangular'}
HELP=('1 · ÖLÇÜLERİ AL\n'
      'SolidWorks’te teknik resmi açıp Aktif resmi oku düğmesine basın. Dosya seç ve oku ile birden fazla '
      'resim de seçebilirsiniz. SolidWorks olmadan Manuel ölçü veya ISO geçme kullanın.\n\n'
      '2 · NEYİ HESAPLAYACAĞINIZI KURUN\n'
      'Soldan bir ölçü seçin. Sonuca eklenecekse + Topla, çıkarılacaksa − Çıkar düğmesine basın. '
      'Örneğin A=50, B=20 ve C=29,8 ise kalan mesafe A−B−C=0,2 mm olur. '
      'Yalnız bu mesafeyi oluşturan ölçüleri ekleyin; çizimdeki bütün ölçüler aynı hesabın parçası değildir.\n\n'
      '3 · KONTROL EDİP HESAPLAYIN\n'
      'Gerçek teknik resimde ölçülerin aynı doğrultuda ve ortak referansa göre alındığını kontrol edin. '
      'Şema yalnız seçiminizi gösterir; CAD geometrisini doğrulamaz. Kontrol kutusunu işaretleyip Hesapla düğmesine basın. '
      'Doğrusal ölçüler için ayrıca açıklama yazmanız gerekmez. Eksik değer varsa ekrandaki düzeltme düğmesini kullanın.\n\n'
      'KABUL ARALIĞI\n'
      'Sonucun hangi sınırlar içinde kalmasını istediğinizi Analiz ayarlarından girin. Örneğin 0–0,4 mm. '
      'Sınırlar boşsa yalnız değerler hesaplanır; uygunluk kararı verilmez.\n\n'
      'SONUÇLAR\n'
      'Worst-Case: bütün ölçüler tolerans uçlarına geldiğinde oluşabilecek en küçük/en büyük sonuç. '
      'RSS: bağımsız ölçülerin istatistiksel hesabı. Monte Carlo: seçilen dağılımlarla yapılan benzetim. '
      'RSS, PPM ve Cp/Cpk gerçek üretim verisiyle doğrulanmış proses kabiliyeti değildir.\n\n'
      'ÖZEL ÖLÇÜLER\n'
      'Referans ölçüyü ve toleransını önce kontrol edin. Çap/radyüs için hangi mesafeyi temsil ettiğini '
      'Ölçü ayarlarından seçin. Açı, BASIC ve GD&T bu doğrusal hesapta desteklenmez. '
      'Bilinmeyen toleranslar tahmin edilmez.\n\n'
      'KAYDETME VE AKTARMA\n'
      'Proje menüsü analizi kaydeder/açar. Sonuçlardan PDF/Excel alınabilir. Teknik resme aktar '
      'ayrı analiz notları ekler; üretim ölçülerini değiştirmez. Kaynağa kayıt açık onay ve yedek gerektirir. '
      'Kaynak ölçü değişirse eski sonuç kaldırılır ve yeniden hesaplama gerekir.')


class StackTable(TableModel):
    def data(self,index,role=Qt.DisplayRole):
        if role==Qt.TextAlignmentRole and index.isValid() and self.columns[index.column()].key in (
            'nominal','lower','upper','minimum','maximum','variance','wc','factor'):
            return Qt.AlignRight|Qt.AlignVCenter
        if role==Qt.ToolTipRole and index.isValid():
            row=self.rows[index.row()]
            return row.get('tooltip') or super().data(index,role)
        return super().data(index,role)


class LibraryFilter(FilterProxy):
    category='Tümü'
    def filterAcceptsRow(self,row,parent):
        if not super().filterAcceptsRow(row,parent): return False
        item=self.sourceModel().index(row,0,parent).data(Qt.UserRole)
        return (self.category=='Tümü' or self.category=='Eksik tolerans' and item['missing'] or
                self.category=='Doğrusal' and item['kind'] in ('linear','horizontal','vertical','ordinate') or
                self.category=='Çap / radyüs' and item['kind'] in ('diameter','radius') or
                self.category=='Desteklenmeyen' and item['kind'] not in ('linear','horizontal','vertical','ordinate','diameter','radius'))

    def set_category(self,value):
        self.beginFilterChange();self.category=value;self.endFilterChange()


class ToleranceStackPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Tolerans yığılması','Ölçüleri seçin, toplayın veya çıkarın; kalan mesafenin sınırlarını görün.')
        self.project=Project();self.result=None;self.selected_files=[];self.loading=False
        self.dirty=False;self.active_operation='';self.project_path='';self.metadata_error='';self.metadata_field=''
        self.current_issue=None
        self.source_watcher=QFileSystemWatcher(self)
        self.source_watcher.fileChanged.connect(self.source_changed)
        project_button=self.action('Proje',None)
        project_menu=QMenu(project_button)
        for title,callback in (('Yeni analiz',self.new_project),('Proje aç…',self.open_project),('Proje kaydet…',self.save_project),
                               ('Kaynakların güncelliğini kontrol et',self.check_sources)):
            project_menu.addAction(title,callback)
        project_button.setMenu(project_menu)
        project_menu.addSeparator();project_menu.addAction('Örnekle dene',self.load_example)
        self.action('Yardım',lambda:show_details(self,'Tolerans yığılması · Kullanım',HELP))
        self.library_button=self.action('Ölçü listesi',self.show_library,locked=False);self.library_button.hide()
        self.stop_button=self.action('Durdur',self.jobs.cancel,locked=False);self.stop_button.setEnabled(False)
        source,body=card()
        body.setContentsMargins(14,10,14,10);body.setSpacing(6)
        toolbar=QHBoxLayout()
        toolbar.addWidget(label('Ölçü kaynağı','section'),1)
        self.active_button=button('Aktif resmi oku',lambda:self.scan(active=True),primary=True)
        self.choose_button=button('Dosya seç ve oku',self.choose_sources)
        self.scan_button=button('Yeniden tara',self.scan)
        self.check_button=button('Güncelliği kontrol et',self.check_sources)
        self.check_button.setVisible(False)
        toolbar.addWidget(self.active_button);toolbar.addWidget(self.choose_button)
        source_menu=QMenu(self)
        source_menu.addAction('Seçili kaynakları yeniden tara',lambda:self.scan_button.click())
        source_menu.addAction('Kaynakların güncelliğini kontrol et',self.check_sources)
        source_more=button('Diğer');source_more.setMenu(source_menu);toolbar.addWidget(source_more)
        self.scan_button.setParent(source);self.scan_button.hide()
        body.addLayout(toolbar)
        self.source_info=label('Açık teknik resmi okuyun veya Manuel ölçü ile SolidWorks olmadan başlayın.','muted')
        body.addWidget(self.source_info);self.layout.addWidget(source)
        self.splitter=QSplitter(Qt.Horizontal)
        library,left=card()
        left.setContentsMargins(12,12,12,12);left.setSpacing(8)
        library_heading=QHBoxLayout();library_heading.addWidget(label('1 · Ölçüleri seç','section'),1)
        self.library_count=label('0 ölçü','muted');library_heading.addWidget(self.library_count);left.addLayout(library_heading)
        manual_row=QHBoxLayout()
        manual_row.addWidget(button('Manuel ölçü',self.add_manual));manual_row.addWidget(button('ISO geçme',self.add_iso));left.addLayout(manual_row)
        search=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Ölçü, sayfa, görünüm veya kaynak ara…')
        self.filter=QComboBox();self.filter.addItems(('Tümü','Doğrusal','Çap / radyüs','Eksik tolerans','Desteklenmeyen'))
        self.filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.filter.setMinimumContentsLength(6)
        self.filter.setMaximumWidth(145)
        search.addWidget(self.search,1);search.addWidget(self.filter);left.addLayout(search)
        self.library=configure_view(QTableView());self.library.setMinimumWidth(250)
        self.library.setMinimumHeight(150)
        self.library_model=StackTable((Column('Ölçü','name'),Column('mm','nominal',compact),
            Column('Tolerans','tolerance'),Column('Durum','readiness'),
            Column('Alt sapma','lower',fmt),Column('Üst sapma','upper',fmt),
            Column('Minimum mm','minimum',fmt),Column('Maksimum mm','maximum',fmt),
            Column('Sayfa / görünüm','location'),Column('Tür / tolerans','type'),Column('Kaynak','source')))
        self.library_proxy=LibraryFilter(self);self.library_proxy.setSourceModel(self.library_model)
        self.library.setModel(self.library_proxy);self.library.setColumnWidth(0,190)
        self.library.horizontalHeader().setMinimumSectionSize(48)
        for index,width in enumerate((65,60,95,105,95,95,100,100,180,170,240)):self.library.setColumnWidth(index,width)
        for index in range(4,self.library_model.columnCount()):self.library.setColumnHidden(index,True)
        self.search.textChanged.connect(self.library_proxy.set_query);self.filter.currentTextChanged.connect(self.library_proxy.set_category)
        self.library.selectionModel().currentRowChanged.connect(self.selection_changed)
        self.library.doubleClicked.connect(self.edit_dimension);left.addWidget(self.library,1)
        self.selection_info=label('Bir ölçü seçin. Sonuca eklemek için +, çıkarmak için − kullanın.','muted')
        self.selection_info.setMinimumHeight(0);left.addWidget(self.selection_info)
        add_row=QHBoxLayout()
        self.add_plus=button('+ Topla',lambda:self.add_selected(1),primary=True)
        self.add_minus=button('− Çıkar',lambda:self.add_selected(-1))
        add_row.addWidget(self.add_plus);add_row.addWidget(self.add_minus);left.insertLayout(3,add_row)
        self.add_plus.setToolTip('Örnek: dış ölçü (+) − içteki parçalar (−) = kalan boşluk')
        self.add_minus.setToolTip(self.add_plus.toolTip())
        edit_row=QHBoxLayout()
        self.edit_dimension_button=button('Ölçüyü düzenle',self.edit_dimension)
        self.locate_button=button('Kaynağı göster',self.locate)
        edit_row.addWidget(self.edit_dimension_button);edit_row.addWidget(self.locate_button);left.addLayout(edit_row)
        self.expand_library=button('Tüm sütunları göster')
        self.expand_library.setCheckable(True)
        self.expand_library.toggled.connect(self.toggle_library)
        left.addWidget(self.expand_library)
        left.addWidget(label('Değişiklikler yalnız analize uygulanır. CAD ölçüleri korunur.','muted'))
        self.library_scroll=scroll(library);self.library_scroll.setMinimumWidth(300)
        self.splitter.addWidget(self.library_scroll)
        self.library_dialog=QDialog(self);self.library_dialog.setWindowTitle('Tolerans yığılması · Ölçü listesi')
        self.library_dialog.setWindowModality(Qt.WindowModal)
        self.library_dialog_body=QVBoxLayout(self.library_dialog)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.button(QDialogButtonBox.Close).setText('Zincire dön')
        close.rejected.connect(self.library_dialog.reject);self.library_dialog_body.addWidget(close)
        self.compact_library=False
        self.right_host=QWidget();right=QVBoxLayout(self.right_host);right.setContentsMargins(0,0,0,0);right.setSpacing(8)
        self.tabs=QTabWidget();right.addWidget(self.tabs,1)
        self.splitter.addWidget(self.right_host);self.splitter.setSizes([400,780]);self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter,1)
        self.chain_host=QWidget();chain=QVBoxLayout(self.chain_host);chain.setContentsMargins(0,0,0,0)
        chain.setSpacing(8)
        self.chain_title=label('2 · Zinciri kur','section');chain.addWidget(self.chain_title)
        self.formula=label('Sonuç = seçtiğiniz ölçülerin toplamı / farkı','section');chain.addWidget(self.formula)
        self.chain_diagram=StackDiagram(width=700,height=150);self.chain_diagram.setMinimumHeight(130);self.chain_diagram.setMaximumHeight(150)
        chain.addWidget(self.chain_diagram)
        self.chain_table=configure_view(QTableView());self.chain_table.setSortingEnabled(False)
        self.chain_table.setMinimumHeight(170)
        self.chain_model=StackTable((Column('Sıra','label'),Column('Ölçü','name'),Column('İşlem','direction'),
            Column('mm','nominal',compact),Column('Kontrol','check'),Column('Katsayı','factor',fmt),
            Column('Başlangıç','start'),Column('Bitiş','end'),Column('Doğrultu / referans','frame'),Column('İlişki / dağılım','relation')))
        self.chain_table.setModel(self.chain_model);self.chain_table.doubleClicked.connect(self.edit_term);chain.addWidget(self.chain_table,1)
        self.chain_table.horizontalHeader().setMinimumSectionSize(40)
        for index,width in enumerate((45,110,100,90,150,75,80,80,140,240)):self.chain_table.setColumnWidth(index,width)
        for index in range(5,self.chain_model.columnCount()):self.chain_table.setColumnHidden(index,True)
        actions=QHBoxLayout()
        self.term_controls=[]
        for title,callback in (('↑',lambda:self.move_term(-1)),('↓',lambda:self.move_term(1)),
                               ('+ / −',self.flip_term),('Düzenle',self.edit_term),('Çıkar',self.remove_term)):
            control=button(title,callback);actions.addWidget(control);self.term_controls.append(control)
        self.term_controls[0].setToolTip('Seçili ölçüyü yukarı taşı');self.term_controls[1].setToolTip('Seçili ölçüyü aşağı taşı')
        self.term_controls[2].setToolTip('Seçili ölçünün toplama / çıkarma yönünü değiştir')
        self.term_controls[3].setToolTip('Seçili ölçünün yönünü, kullanımını ve gelişmiş ayarlarını düzenle')
        self.chain_table.selectionModel().currentRowChanged.connect(self.update_term_controls)
        chain.insertLayout(3,actions)
        self.chain_details=QCheckBox('Bağlantı ve dağılım ayrıntıları')
        self.chain_details.toggled.connect(self.toggle_chain_details);chain.addWidget(self.chain_details)
        self.chain_footer=QWidget();footer=QVBoxLayout(self.chain_footer);footer.setContentsMargins(0,0,0,0);footer.setSpacing(6)
        self.acceptance_button=button('',self.show_settings);footer.addWidget(self.acceptance_button)
        self.review,review_body=card();review_body.setContentsMargins(12,10,12,10);review_body.setSpacing(6)
        self.review_title=label('Sonraki adım','section');review_body.addWidget(self.review_title)
        self.review_text=label('Ölçülerinizi soldaki listeden ekleyin.','muted');review_body.addWidget(self.review_text)
        self.fix_button=button('Düzelt',self.fix_issue);review_body.addWidget(self.fix_button,alignment=Qt.AlignLeft)
        footer.insertWidget(0,self.review)
        self.confirm_box=QCheckBox('Ortak doğrultuyu ve + / − yönlerini kontrol ettim.')
        self.confirm_box.setToolTip('Gerçek çizimde ölçülerin aynı doğrultuda ve ortak referansa göre alındığını kontrol edin. '
            'Şema CAD geometrisini doğrulamaz. Doğrusal ölçüler için ayrıca açıklama yazmanız gerekmez.')
        self.confirm_box.toggled.connect(self.confirm_chain);footer.addWidget(self.confirm_box)
        self.calculate_button=button('Hesapla ve sonuçları göster',self.start_calculation,primary=True);footer.addWidget(self.calculate_button)
        right.addWidget(self.chain_footer)
        self.tabs.currentChanged.connect(lambda index:self.chain_footer.setVisible(index==0))
        self.tabs.addTab(scroll(self.chain_host),'Zincir')
        settings,settings_body=card('İstenen sonuç ve hesap yöntemi')
        self.form=ValueForm(MemorySettings(),'')
        for key,title in (('name','Analiz adı'),('critical','Hesaplanan mesafenin adı')):
            self.form.text(key,title,getattr(self.project,key))
        self.form.text('acceptance_min','İstenen en küçük sonuç · mm','0').setPlaceholderText('Boş bırakırsanız alt sınır aranmaz')
        self.form.text('acceptance_max','İstenen en büyük sonuç · mm','').setPlaceholderText('Boş bırakırsanız üst sınır aranmaz')
        self.form.combo('method','Hesap yöntemi',METHODS,'Worst-Case + RSS + Monte Carlo')
        settings_body.addWidget(self.form)
        settings_body.addWidget(label('Örnek: boşluğun 0–0,4 mm arasında kalması gerekiyorsa alt sınıra 0, üst sınıra 0,4 yazın. '
            'İki alan da boşsa uygunluk kararı verilmez.','muted'))
        settings_body.addWidget(label('Worst-Case: olası en küçük ve en büyük sonuç. RSS: istatistiksel aralık. '
            'Monte Carlo: dağılımlarla benzetim. RSS ve benzetim üretim garantisi değildir.','muted'))
        frame=QWidget();frame_body=QVBoxLayout(frame);frame_body.setContentsMargins(0,0,0,0)
        frame_form=ValueForm(MemorySettings(),'')
        for key,title in (('start','Zincir başlangıcı'),('end','Zincir bitişi'),('datum','Ortak referans (datum)')):
            frame_form.text(key,title,getattr(self.project,key))
        frame_form.combo('axis','Ölçüm doğrultusu',('X','Y','Z'),'X');frame_body.addWidget(frame_form)
        frame_body.addWidget(label('X / Y / Z bu analizin doğrultusunu, referans ise ölçülerin dayandığı ortak noktayı tanımlar. '
            'Çizimde yatay veya düşey görünmek, montajda aynı doğrultuda olmak anlamına gelmez.','muted'))
        frame_body.addWidget(button('Noktaları sıraya bağla',self.relink))
        self.frame_section=Disclosure('Gelişmiş · Doğrultu ve bağlantı noktaları',frame);settings_body.addWidget(self.frame_section)
        statistics=QWidget();statistics_body=QVBoxLayout(statistics);statistics_body.setContentsMargins(0,0,0,0)
        statistics_form=ValueForm(MemorySettings(),'')
        f=self.form;self.form=statistics_form
        self.form.combo('distribution','Varsayılan dağılım',DISTRIBUTIONS,'Normal')
        self.form.text('input_sigma','Normal giriş bandı: ±nσ','3');self.form.text('output_sigma','RSS sonuç bandı: ±nσ','3')
        self.form.check('truncate_normal','Normal dağılımı tolerans sınırlarında kes',True)
        self.form.text('samples','Benzetim sayısı (Monte Carlo)','50000');self.form.text('seed','Rastgelelik anahtarı (seed)','42')
        self.form.check('independent','RSS / MC girdileri bağımsız kabul ediliyor',True)
        self.form.check('offline_snapshot','CAD ölçülerini çevrimdışı anlık görüntü olarak kullan',False)
        statistics_body.addWidget(self.form)
        statistics_body.addWidget(label('Asimetrik toleransta nominal ve bant merkezi ayrıdır. Normal girdide varsayılan σ = yarı genişlik / 3; '
            'Uniform ve üçgensel dağılım kendi varyanslarını kullanır. RSS/MC korelasyon modeli içermez. '
            'Çevrimdışı CAD verisi açık SolidWorks oturumuna karşı doğrulanamaz; bu seçim teknik resme aktarımı engeller.','muted'))
        self.form=f
        self.statistics_section=Disclosure('Gelişmiş · Dağılım ve benzetim ayarları',statistics);settings_body.addWidget(self.statistics_section)
        # Keep the page's single form API while the actual controls live in small, named sections.
        for section_form in (frame_form,statistics_form):
            self.form.fields.update(section_form.fields);section_form.changed.connect(self.form_changed)
        settings_body.addStretch()
        self.form.changed.connect(self.form_changed);self.settings_scroll=scroll(settings)
        self.tabs.addTab(self.settings_scroll,'Analiz ayarları')
        results,results_body=card()
        self.headline=label('3 · Hesap sonucu','result');results_body.addWidget(self.headline)
        self.result_summary=label('Ölçüleri zincire ekleyip Hesapla düğmesine basın.');results_body.addWidget(self.result_summary)
        self.result_cards={};cards=QHBoxLayout()
        for key,title in (('nominal','Nominal sonuç'),('minimum','En küçük olası sonuç'),('maximum','En büyük olası sonuç')):
            tile,tile_body=card();tile_body.setContentsMargins(12,10,12,10);tile_body.addWidget(label(title,'muted'))
            value=label('—','section');tile_body.addWidget(value);self.result_cards[key]=value;cards.addWidget(tile)
        results_body.addLayout(cards)
        plots=QTabWidget();self.contribution_diagram=StackDiagram(width=700,height=320);self.histogram=StackDiagram(width=700,height=300)
        plots.addTab(self.contribution_diagram,'Tolerans katkıları');plots.addTab(self.histogram,'Monte Carlo dağılımı');results_body.addWidget(plots)
        self.critical_label=label();results_body.addWidget(self.critical_label)
        self.metrics=configure_view(QTableView());self.metrics.setMinimumHeight(230)
        self.metric_model=StackTable((Column('Sonuç / açıklama','name'),Column('Değer','value')));self.metrics.setModel(self.metric_model)
        self.metrics.setSortingEnabled(False)
        details=QWidget();details_body=QVBoxLayout(details);details_body.setContentsMargins(0,0,0,0)
        self.assumptions=label('Hesap sonucu henüz yok.','muted');details_body.addWidget(self.assumptions);details_body.addWidget(self.metrics)
        results_body.addWidget(Disclosure('Tüm sonuçlar ve hesap varsayımları',details))
        outputs=QHBoxLayout()
        for title,callback in (('Sonucu kopyala',self.copy_result),('PDF raporu',lambda:self.export_report('pdf')),('Excel raporu',lambda:self.export_report('xlsx'))):
            outputs.addWidget(button(title,callback))
        results_body.insertLayout(2,outputs);self.tabs.addTab(scroll(results),'Sonuçlar')
        output,output_body=card('Teknik resme analiz raporu')
        self.target=PathPicker(folder=False,title='Hedef .SLDDRW teknik resmi');output_body.addWidget(self.target)
        self.output_mode=QComboBox();self.output_mode.addItems(('Yalnız GOKWORKS içinde görüntüle','Anotasyon ekle · kaydetme','Analizli kopyayı farklı kaydet','Kaynağa kaydet · onay + yedek'))
        output_body.addWidget(self.output_mode)
        self.new_sheet=QCheckBox('Ayrı analiz sayfaları oluştur');self.new_sheet.setChecked(True);output_body.addWidget(self.new_sheet)
        self.labels=QCheckBox('Kaynak ölçülerin yanına ayrı L1, L2… analiz notları ekle');output_body.addWidget(self.labels)
        self.position=ValueForm(MemorySettings(),'');self.position.text('x','Mevcut sayfada X · mm','20');self.position.text('y','Mevcut sayfada Y · mm','250')
        output_body.addWidget(self.position)
        output_body.addWidget(button('Seçili çıktıyı oluştur',self.export_drawing,primary=True))
        output_body.addWidget(label('Üretim ölçüsü, toleransı veya model parametresi değiştirilmez. '
            'Anotasyon ekle seçeneği çizimi yalnız açık oturumda değiştirir; dosyayı kaydetmez. '
            'Farklı kaydet yeni bir .SLDDRW üretir ve model referanslarını kontrol eder. '
            'Kaynak üzerine kayıt ayrı açık onay, kayıt dışı değişiklik kontrolü ve doğrulanmış yedek gerektirir.','muted'))
        self.tabs.addTab(scroll(output),'Teknik resme aktar')
        self.controls.extend((source,library,self.chain_host,self.chain_footer,settings,output,results))
        self.finish_layout()
        self.status_details.clicked.disconnect()
        self.status_details.clicked.connect(lambda:show_details(self,'İşlem ayrıntısı',getattr(self,'technical_details',self.status_text)))
        self.column_timer=QTimer(self);self.column_timer.setSingleShot(True);self.column_timer.setInterval(20)
        self.column_timer.timeout.connect(self.fit_columns)
        self.splitter.splitterMoved.connect(lambda *args:self.column_timer.start())
        self.refresh();self.selection_changed()

    @property
    def appearance(self): return 'Dark' if self.context.appearance=='dark' else 'Light'

    def set_status(self,text,error=False):
        self.technical_details=str(text)
        message=str(text)
        if error and any(token in message for token in ('Traceback','HRESULT','DISP_','(-2147','pythoncom','pywintypes')):
            message='SolidWorks işlemi tamamlanamadı. Teknik resmin açık olduğundan emin olup yeniden deneyin. Teknik hata Ayrıntı düğmesinde.'
        super().set_status(message,error)

    def toggle_library(self,expanded):
        self.right_host.setVisible(self.compact_library or not expanded)
        for index in range(4,self.library_model.columnCount()):self.library.setColumnHidden(index,not expanded)
        self.expand_library.setText('Zincire geri dön' if expanded else 'Tüm sütunları göster')
        self.column_timer.start()

    def toggle_chain_details(self,expanded):
        for index in range(5,self.chain_model.columnCount()):self.chain_table.setColumnHidden(index,not expanded)
        self.fit_columns()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'library_dialog'):
            compact=event.size().width()<760
            if compact!=self.compact_library:
                self.compact_library=compact
                if compact:
                    self.library_dialog_body.insertWidget(0,self.library_scroll,1)
                    self.right_host.show()
                else:
                    self.library_dialog.reject();self.library_dialog_body.removeWidget(self.library_scroll)
                    self.splitter.insertWidget(0,self.library_scroll);self.library_scroll.show()
                    self.right_host.setVisible(not self.expand_library.isChecked())
                    self.splitter.setSizes([340,max(360,self.width()-380)])
                self.library_button.setVisible(compact)
        if hasattr(self,'column_timer'):self.column_timer.start()

    def show_library(self):
        if self.compact_library:
            bounds=self.screen().availableGeometry()
            self.library_dialog.resize(min(620,bounds.width()-40),min(720,bounds.height()-60))
            self.library_dialog.open()

    def fit_columns(self):
        # Status remains in the selected-measurement summary and inline guidance on narrow windows.
        self.library.setColumnHidden(3,not self.expand_library.isChecked() and self.library.viewport().width()<330)
        self.chain_table.setColumnHidden(4,not self.chain_details.isChecked() and self.chain_table.viewport().width()<520)

    @staticmethod
    def dimension_state(d):
        if d.kind not in (*KINDS.values(),'reference'):return 'Kullanılamaz'
        if d.nominal is None:return 'Değer eksik'
        if d.lower is None or d.upper is None:return 'Tolerans eksik'
        if d.kind=='reference':return 'Kontrol gerekli'
        if d.kind in ('diameter','radius'):return 'İlişki seçin'
        return 'Hazır'

    def selection_changed(self,*args):
        d=self.selected_dimension()
        for control in (self.add_plus,self.add_minus,self.edit_dimension_button,self.locate_button):control.setEnabled(d is not None)
        if d is None:
            self.selection_info.setText('Bir ölçü seçin. Sonuca eklemek için +, çıkarmak için − kullanın.')
        else:
            self.selection_info.setText(f'{short_name(d)} · {compact(d.nominal)} mm · {self.dimension_state(d)}\n'
                +(f'{d.sheet} / {d.view}' if d.source else 'Manuel analiz ölçüsü'))
            self.selection_info.setToolTip(d.name+'\n'+(d.source or 'Manuel')+'\n'+d.note)

    def update_term_controls(self,*args):
        index=self.chain_index()
        for control in self.term_controls:control.setEnabled(index>=0)
        self.term_controls[0].setEnabled(index>0)
        self.term_controls[1].setEnabled(0<=index<len(self.project.terms)-1)

    def review_candidate(self):
        """Preview a *potential* explicit confirmation; never persist this on review alone."""
        candidate=project_snapshot(self.project)
        dimensions={d.id:d for d in candidate.dimensions}
        candidate.terms=[replace(t,alignment_confirmed=True)
            if (d:=dimensions.get(t.dimension_id)) and d.source and
               d.kind in ('linear','horizontal','vertical','ordinate') and t.factor==1 and
               t.axis==candidate.axis and t.datum==candidate.datum else t for t in candidate.terms]
        return candidate

    def readiness_issue(self):
        if self.metadata_error:
            section=('statistics' if self.metadata_field in ('input_sigma','output_sigma','samples','seed') else
                'frame' if self.metadata_field in ('start','end','axis','datum') else 'settings')
            return ChainIssue(self.metadata_error,action='İlgili ayarı düzelt',target=section)
        try:validate(self.review_candidate(),confirmed=False)
        except ChainIssue as error:return error
        except ValueError as error:return ChainIssue(str(error),action='Analiz ayarlarını aç')
        return None

    def update_guidance(self):
        self.current_issue=self.readiness_issue()
        self.review.setVisible(self.current_issue is not None and bool(self.project.terms))
        if self.current_issue:
            self.review_title.setText('Önce bunu tamamlayın' if self.project.terms else 'Başlamak için')
            self.review_text.setText(str(self.current_issue))
            self.fix_button.setText(self.current_issue.action or 'Ölçü listesini aç')
            self.fix_button.setVisible(bool(self.current_issue.action))
        else:
            confirmed=bool(self.project.confirmed_digest) and self.project.confirmed_digest==self.project.fingerprint()
            self.review_title.setText('Hesaplamaya hazır' if confirmed else 'Son kontrol · Yönler doğru mu?')
            self.review_text.setText('Hesapla düğmesiyle sonuç aralığını ve katkı grafiklerini görebilirsiniz.' if confirmed else
                '+ sonuca ekler, − çıkarır. Gerçek çizimde ortak doğrultuyu ve referansı kontrol edip aşağıdaki kutuyu işaretleyin.')
            self.fix_button.setVisible(False)
        self.confirm_box.setEnabled(bool(self.project.terms) and self.current_issue is None)
        self.calculate_button.setEnabled(bool(self.project.terms) and self.current_issue is None)
        low,high=self.project.acceptance_min,self.project.acceptance_max
        criterion=(f'{compact(low)} … {compact(high)} mm' if low is not None and high is not None else
            f'En az {compact(low)} mm' if low is not None else f'En fazla {compact(high)} mm' if high is not None else 'Sınır girilmedi')
        self.acceptance_button.setText('İstenen sonuç: '+criterion+'  ·  Düzenle')
        by_id={d.id:d for d in self.project.dimensions};parts=[];nominal=number(0)
        for i,t in enumerate(self.project.terms):
            if i<10:parts.append(('− ' if t.direction<0 else '+ ' if i else '')+f'L{i+1}'+(f' × {compact(t.factor)}' if t.factor!=1 else ''))
            d=by_id.get(t.dimension_id)
            if d is None or d.nominal is None:nominal=None
            elif nominal is not None:nominal+=d.nominal*t.direction*t.factor
        formula='Sonuç = '+' '.join(parts) if parts else 'Örnek: dış ölçü − iç ölçü = kalan boşluk'
        if len(self.project.terms)>10:formula+=' …'
        if parts and nominal is not None:formula+=f'  =  {compact(nominal)} mm (nominal)'
        self.formula.setText(formula)
        self.update_term_controls()

    def show_settings(self,section=None):
        self.tabs.setCurrentIndex(1)
        if section=='frame':self.frame_section.toggle.setChecked(True)
        elif section=='statistics':self.statistics_section.toggle.setChecked(True)
        key=self.metadata_field or ('axis' if section=='frame' else 'samples' if section=='statistics' else 'acceptance_min')
        field=self.form.fields[key]
        self.settings_scroll.ensureWidgetVisible(field);field.setFocus()

    def select_library_id(self,dimension_id):
        self.search.clear();self.filter.setCurrentText('Tümü')
        for row in range(self.library_proxy.rowCount()):
            if self.library_proxy.index(row,0).data(Qt.UserRole)['id']==dimension_id:
                self.library.selectRow(row);self.library.scrollTo(self.library_proxy.index(row,0));return True
        return False

    def fix_issue(self):
        issue=self.current_issue
        if issue is None:return
        self.expand_library.setChecked(False)
        self.tabs.setCurrentIndex(0)
        if issue.term_index is not None:self.chain_table.selectRow(issue.term_index)
        if issue.target=='dimension':
            if self.select_library_id(issue.dimension_id):self.edit_dimension()
        elif issue.target=='term':self.edit_term()
        elif issue.target=='relink':self.relink()
        elif issue.target=='confirm':self.confirm_box.setFocus()
        elif issue.target=='scan':self.scan() if self.selected_files else self.scan(active=True)
        elif issue.target=='select_term':self.chain_table.setFocus()
        elif issue.target=='library':self.library.setFocus()
        else:self.show_settings(issue.target)

    def invalidate(self):
        self.project.invalidate();self.result=None;self.dirty=True
        with QSignalBlocker(self.confirm_box): self.confirm_box.setChecked(False)
        self.headline.setText('Zinciri doğrulayıp yeniden hesaplayın');self.result_summary.clear()
        self.metric_model.replace([]);self.assumptions.setText('Girdiler değişti; önceki sonuç güncel sayılmaz.');self.critical_label.clear()
        for value in self.result_cards.values():value.setText('—')
        self.update_guidance()
        self.draw()

    def capture_settings(self):
        f=self.form;p=replace(self.project)
        for key in ('name','critical','start','end','axis','datum'): setattr(p,key,f.value(key).strip())
        for key,title in (('acceptance_min','İstenen en küçük sonuç'),('acceptance_max','İstenen en büyük sonuç')):
            setattr(p,key,number(f.value(key),title) if f.value(key).strip() else None)
        for key in ('input_sigma','output_sigma'): setattr(p,key,number(f.value(key),'İstatistiksel bant katsayısı'))
        samples=number(f.value('samples'),'Örnek sayısı')
        if samples!=samples.to_integral_value(): raise ValueError('Örnek sayısı tam sayı olmalı.')
        p.samples=int(samples)
        seed=number(f.value('seed'),'Seed') if f.value('seed').strip() else None
        if seed is not None and seed!=seed.to_integral_value(): raise ValueError('Seed tam sayı olmalı.')
        p.seed=int(seed) if seed is not None else None
        p.method=METHODS[f.value('method')];p.distribution=DISTRIBUTIONS[f.value('distribution')]
        for key in ('independent','truncate_normal','offline_snapshot'): setattr(p,key,f.value(key))
        self.project=p;self.metadata_error='';self.metadata_field=''

    def load_form(self):
        self.metadata_error='';self.metadata_field=''
        self.loading=True
        try:
            for key in self.form.fields:
                value=getattr(self.project,key)
                if key=='method': value=next(k for k,v in METHODS.items() if v==value)
                elif key=='distribution': value=next(k for k,v in DISTRIBUTIONS.items() if v==value)
                self.form.set_value(key,'' if value is None else value)
        finally: self.loading=False

    def form_changed(self,key):
        if self.loading:return
        self.invalidate()
        try:self.capture_settings()
        except ValueError as error:self.metadata_error=str(error);self.metadata_field=key;self.set_status(str(error),True)
        self.draw();self.update_guidance()

    def refresh(self):
        selected=self.selected_dimension()
        selected_id=selected.id if selected else None
        chain_index=self.chain_index()
        rows=[]
        for d in self.project.dimensions:
            tolerance=('Eksik' if d.lower is None or d.upper is None else '±'+compact(d.upper) if d.lower==-d.upper else
                       f'{compact(d.lower)} / {"+" if d.upper>0 else ""}{compact(d.upper)}')
            rows.append(dict(id=d.id,name=short_name(d),full_name=d.name,nominal=None if d.nominal is None else float(d.nominal),
                lower=None if d.lower is None else float(d.lower),upper=None if d.upper is None else float(d.upper),
                minimum=None if d.minimum is None else float(d.minimum),maximum=None if d.maximum is None else float(d.maximum),
                location=f'{d.sheet} / {d.view}',kind=d.kind,type=KIND_TITLES.get(d.kind,d.kind)+' · '+d.tolerance_type,source=d.source or 'Manuel',
                missing=d.nominal is None or d.lower is None or d.upper is None,note=d.note,configuration=d.configuration,
                tolerance=tolerance,readiness=self.dimension_state(d),tooltip=f'{d.name}\n{self.dimension_state(d)}\n'
                f'{d.source or "Manuel ölçü"}\n{d.sheet} / {d.view}\n{d.note}'))
        self.library_model.replace(rows)
        self.library_count.setText(f'{len(rows)} ölçü')
        dimensions={d.id:d for d in self.project.dimensions}
        self.chain_model.replace([dict(label=f'L{i}',name=short_name(dimensions[t.dimension_id]) if t.dimension_id in dimensions else 'Ölçü bulunamadı',
            direction='Topla (+)' if t.direction>0 else 'Çıkar (−)',factor=float(t.factor),start=t.start,end=t.end,frame=t.axis+' / '+t.datum,
            nominal=dimensions[t.dimension_id].nominal if t.dimension_id in dimensions else None,
            check=self.term_state(t,dimensions.get(t.dimension_id)),
            relation=(t.relation or ('Doğrultu kullanıcı tarafından kontrol edildi' if t.alignment_confirmed else ''))+' · '+next(title for title,key in DIST.items() if key==t.distribution),
            tooltip=(dimensions[t.dimension_id].name if t.dimension_id in dimensions else 'Kaynak ölçü bulunamadı')+f'\n{t.start} → {t.end}\n{t.axis} / {t.datum}\n{t.relation}',
            index=i-1) for i,t in enumerate(self.project.terms,1)])
        for row in range(self.library_proxy.rowCount()):
            if selected_id is None or self.library_proxy.index(row,0).data(Qt.UserRole)['id']==selected_id:
                self.library.selectRow(row);break
        if 0<=chain_index<len(self.project.terms):self.chain_table.selectRow(chain_index)
        self.selection_changed();self.update_guidance();self.draw()

    def term_state(self,term,dimension):
        if dimension is None:return 'Kaynak eksik'
        state=self.dimension_state(dimension)
        if state not in ('Hazır','İlişki seçin'):return state
        if dimension.kind in ('diameter','radius') and not term.relation.strip():return 'İlişki seçin'
        if term.axis!=self.project.axis or term.datum!=self.project.datum:return 'Doğrultu farklı'
        if not dimension.source:return 'Manuel giriş'
        return 'Kontrol edildi' if term.alignment_confirmed or term.relation else 'Onay bekliyor'

    def draw(self):
        self.chain_diagram.render_geometry(lambda scene:draw_chain(scene,self.project,self.appearance))
        self.contribution_diagram.render_geometry(lambda scene:draw_contributions(scene,self.result,self.appearance))
        self.histogram.render_geometry(lambda scene:draw_histogram(scene,self.project,self.result,self.appearance))

    def theme_changed(self): self.draw()

    def selected_dimension(self):
        row=self.library.currentIndex().data(Qt.UserRole)
        return next((d for d in self.project.dimensions if row and d.id==row['id']),None)

    def add_manual(self):
        dialog=DimensionDialog(self)
        try:
            if dialog.exec():
                self.project.dimensions.append(dialog.value);self.invalidate();self.refresh();self.select_library_id(dialog.value.id)
                self.set_status('Ölçü eklendi. + Topla veya − Çıkar ile hesabınıza katın.')
        finally:dialog.deleteLater()

    def edit_dimension(self,*args):
        d=self.selected_dimension()
        if d is None:return
        if d.kind=='reference' and d.geometry_kind not in KINDS.values():
            show_details(self,'Bu ölçü henüz kullanılamıyor','Bu referans ölçünün doğrusal mı, açısal mı olduğu okunamadı. '
                'Önce teknik resmi yeniden tarayın. Açılar, yay ve pah ölçüleri bu doğrusal hesaba eklenemez.\n\nTeknik ayrıntı:\n'+d.note);return
        if d.kind in ('angle','gdt','basic','arc','chamfer'):
            show_details(self,'Bu ölçü doğrusal hesapta kullanılamıyor',KIND_TITLES.get(d.kind,d.kind)+
                '\nBu modül yalnız aynı doğrultudaki mesafeleri toplar veya çıkarır. '
                'Açı, BASIC ve geometrik tolerans kontrolleri ayrı hesap gerektirir.\n\nTeknik ayrıntı:\n'+d.note);return
        dialog=DimensionDialog(self,d)
        try:
            if dialog.exec():
                self.project.dimensions=[dialog.value if item.id==d.id else item for item in self.project.dimensions]
                self.invalidate();self.refresh();self.select_library_id(d.id)
                return dialog.value
        finally:dialog.deleteLater()

    def add_selected(self,direction):
        d=self.selected_dimension()
        if d is None:self.set_status('Önce bir ölçü seçin.',True);return
        if d.kind=='reference':
            d=self.edit_dimension()
            if d is None:return
        if d.kind not in KINDS.values():
            self.edit_dimension();return
        if any(t.dimension_id==d.id or (d.physical_id and next((item.physical_id for item in self.project.dimensions if item.id==t.dimension_id),'')==d.physical_id)
               for t in self.project.terms):
            self.set_status('Bu fiziksel ölçü zincirde zaten var; aynı ölçü iki kez kullanılamaz. İşlemini değiştirmek için zincirdeki satırı seçip + / − Değiştir düğmesini kullanın.',True)
            for row,t in enumerate(self.project.terms):
                item=next((item for item in self.project.dimensions if item.id==t.dimension_id),None)
                if item and (item.id==d.id or d.physical_id and item.physical_id==d.physical_id):self.chain_table.selectRow(row);break
            return
        self.append_dimension(d,direction)

    def append_dimension(self,d,direction,*,factor=1,relation=''):
        start=self.project.terms[-1].end if self.project.terms else self.project.start
        used={t.start for t in self.project.terms}|{t.end for t in self.project.terms}|{start}
        end=f'P{len(self.project.terms)+1}'
        while end in used:end+='a'
        self.project.terms.append(Term(d.id,direction,start,end,self.project.axis,self.project.datum,factor,relation))
        self.expand_library.setChecked(False)
        self.project.end=end;self.load_form();self.invalidate();self.refresh()
        self.select_library_id(d.id);self.tabs.setCurrentIndex(0)
        self.chain_table.selectRow(len(self.project.terms)-1)
        self.set_status(f'{short_name(d)} zincire {"toplanacak (+)" if direction>0 else "çıkarılacak (−)"} olarak eklendi. '
            'Yön yanlışsa + / − Değiştir düğmesini kullanın.')
        if sum((item.physical_id or item.id)==(d.physical_id or d.id) for t in self.project.terms for item in self.project.dimensions if item.id==t.dimension_id)>1:
            self.set_status('Aynı fiziksel ölçü tekrar eklendi; bağımsız kabul edilemez. Hesaplamadan önce düzeltin.',True)

    def add_iso(self):
        dialog=IsoPairDialog(self)
        try:
            if dialog.exec():
                hole,shaft,factor,relation=dialog.value
                self.project.dimensions.extend((hole,shaft));self.append_dimension(hole,1,factor=factor,relation=relation)
                self.append_dimension(shaft,-1,factor=factor,relation=relation)
        finally:dialog.deleteLater()

    def chain_index(self):
        index=self.chain_table.currentIndex();return index.row() if index.isValid() else -1

    def edit_term(self,*args):
        index=self.chain_index()
        if index<0:return
        term=self.project.terms[index];d=next((d for d in self.project.dimensions if d.id==term.dimension_id),None)
        if d is None:self.set_status('Kaynak ölçü bulunamadı; yeniden tarayın.',True);return
        dialog=TermDialog(self,term,d)
        try:
            if dialog.exec():
                self.project.terms[index]=dialog.value;self.invalidate();self.refresh();self.chain_table.selectRow(index)
        finally:dialog.deleteLater()

    def flip_term(self):
        index=self.chain_index()
        if index<0:return
        term=self.project.terms[index];self.project.terms[index]=replace(term,direction=-term.direction)
        self.invalidate();self.refresh();self.chain_table.selectRow(index)
        self.set_status(f'L{index+1}: işlem {"Topla (+)" if term.direction<0 else "Çıkar (−)"} olarak değiştirildi. Formülü kontrol edin.')

    def default_points(self):
        return (self.project.start=='P0' and self.project.end==f'P{len(self.project.terms)}' and
            all(t.start==f'P{i}' and t.end==f'P{i+1}' for i,t in enumerate(self.project.terms)))

    def link_default_points(self):
        self.project.terms=[replace(t,start=f'P{i}',end=f'P{i+1}') for i,t in enumerate(self.project.terms)]
        self.project.end=f'P{len(self.project.terms)}' if self.project.terms else ''
        self.load_form()

    def move_term(self,direction):
        index=self.chain_index();target=index+direction
        if index<0 or not 0<=target<len(self.project.terms):return
        automatic=self.default_points()
        self.project.terms[index],self.project.terms[target]=self.project.terms[target],self.project.terms[index]
        if automatic:self.link_default_points()
        self.invalidate();self.refresh();self.chain_table.selectRow(target)
        self.set_status('Ölçü sırası değişti. + / − yönleri korundu; formülü kontrol edin.' if automatic else
            'Sıra değişti. Özel başlangıç/bitiş bağlantılarını kontrol edin veya Bağlantıları düzelt düğmesini kullanın.')

    def remove_term(self):
        index=self.chain_index()
        if index<0:return
        automatic=self.default_points()
        self.project.terms.pop(index)
        if automatic:self.link_default_points()
        self.invalidate();self.refresh()
        if self.project.terms:self.chain_table.selectRow(min(index,len(self.project.terms)-1))

    def relink(self):
        if not self.project.terms:return
        start=self.project.start
        for i,t in enumerate(self.project.terms):
            end=self.project.end if i==len(self.project.terms)-1 else f'{self.project.start}-N{i+1}'
            self.project.terms[i]=replace(t,start=start,end=end);start=end
        self.invalidate();self.refresh();self.set_status('Bağlantılar sıraya göre yeniden kuruldu. Gerçek çizimdeki ölçü sırasını ve + / − yönlerini kontrol edin.')

    def confirm_chain(self,checked):
        if not checked:self.invalidate();return
        try:
            self.capture_settings();candidate=self.review_candidate();candidate.confirm();self.project=candidate
            self.refresh();self.set_status('Ölçü yönleri ve ortak doğrultu kontrolü kaydedildi. Hesapla düğmesine basabilirsiniz.')
        except ValueError as error:
            with QSignalBlocker(self.confirm_box):self.confirm_box.setChecked(False)
            self.update_guidance();self.set_status(str(error),True)

    def start_job(self,name,operation):
        if not self.can_start():return False
        self.active_operation=name
        def guarded(sink,stop):
            try:operation(sink,stop)
            except Cancelled as error:sink.put(('stack_cancelled',str(error)))
        return self.jobs.start(self,guarded)

    def start_calculation(self):
        try:
            self.capture_settings()
            issue=self.readiness_issue()
            if issue:raise issue
            if self.project.confirmed_digest!=self.project.fingerprint():
                self.current_issue=ChainIssue('Son bir kontrol gerekiyor: ölçüler aynı doğrultuda ve ortak referansa göre mi alındı? '
                    'Doğrulama kutusunu işaretleyip tekrar Hesapla düğmesine basın.',action='Doğrulama kutusuna git',target='confirm')
                self.review_title.setText('Son kontrol gerekli');self.review_text.setText(str(self.current_issue))
                self.fix_button.setText(self.current_issue.action);self.fix_button.show();self.review.show();self.confirm_box.setFocus()
                self.set_status(str(self.current_issue),True);return
        except ValueError as error:self.update_guidance();self.set_status(str(error),True);return
        snapshot=project_snapshot(self.project)
        self.result=None;self.headline.setText('Kaynaklar doğrulanıyor ve hesaplanıyor…')
        def operation(sink,stop):
            sink.put(('stack_phase','Kaynak ölçüler doğrulanıyor…'));solidworks_reader.verify_live(snapshot,stop=stop)
            value=calculate(snapshot,stop=stop,progress=lambda current,total:sink.put(('stack_progress',(current,total))))
            solidworks_reader.verify_live(snapshot,stop=stop)
            sink.put(('stack_result',value))
        self.start_job('calculate',operation)

    def choose_sources(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Teknik resimleri seç','','SolidWorks (*.SLDDRW *.slddrw)')
        if paths:
            self.selected_files=paths;self.source_info.setText(f'{len(paths)} teknik resim seçildi; ölçüler okunuyor…');self.scan()

    def scan(self,checked=False,*,active=False):
        paths=None if active else tuple(self.selected_files)
        if not active and not paths:self.set_status('Önce Dosya seç ve oku veya Aktif resmi oku düğmesine basın.',True);return
        def operation(sink,stop):
            result=solidworks_reader.read_sources(paths,stop=stop,progress=lambda count:sink.put(('stack_phase',f'{count} ölçü okunuyor…')) if count%25==0 else None)
            check_cancel(stop)
            sink.put(('stack_sources',result))
        self.start_job('scan',operation)

    def merge_sources(self,dimensions,sources):
        updated={solidworks_reader.com.path_key(s.path) for s in sources}
        previous={d.id:d for d in self.project.dimensions}
        merged=[d for d in self.project.dimensions if solidworks_reader.com.path_key(d.source) not in updated]
        for d in dimensions:
            old=previous.get(d.id)
            merged.append(old if old and old.provenance=='manual_override' and old.original_signature==d.original_signature else d)
        self.project.dimensions=merged
        self.project.sources=[s for s in self.project.sources if solidworks_reader.com.path_key(s.path) not in updated]+list(sources)
        self.selected_files=[s.path for s in self.project.sources]
        self.watch_sources()
        if sources and not self.target.text():self.target.setText(sources[0].path)
        self.invalidate();self.refresh()
        self.source_info.setText(f'SolidWorks · {len(self.project.sources)} teknik resim · {len(self.project.dimensions)} ölçü. '
            'Hesapta kullanacağınız ölçüleri soldan seçin.')
        self.expand_library.setChecked(False);self.tabs.setCurrentIndex(0)
        self.set_status('Ölçüler okundu. + Topla veya − Çıkar ile zincirinizi kurun; eksik değerler listede belirtilir.')

    def check_sources(self):
        snapshot=project_snapshot(self.project)
        def operation(sink,stop):
            solidworks_reader.verify_live(snapshot,stop=stop);sink.put(('stack_phase','Kaynak dosya ve kullanılan ölçü kimlikleri doğrulandı.' if snapshot.sources else 'Manuel analiz; CAD kaynağı yok.'))
        self.start_job('check',operation)

    def locate(self):
        d=self.selected_dimension()
        if d is None:return
        show_details(self,'Ölçünün kaynağı',f'{d.name}\n{d.source or "Manuel"}\nSayfa: {d.sheet}\nGörünüm: {d.view}\n'
            f'Model: {d.model}\nKonfigürasyon: {d.configuration}\nAPI kimliği: {d.api_name}\n'
            f'Konum (çizim mm): {d.position}\nTür: {d.kind}\nKaynak: {d.provenance}\nGörünen metin: {d.display_text}\n{d.note}')
        if d.source and d.persistent_ref:
            self.start_job('highlight',lambda sink,stop:(solidworks_reader.highlight(d),sink.put(('stack_phase','Ölçü SolidWorks’te seçildi.'))))

    def show_result(self,value):
        if value.project_digest!=self.project.fingerprint():self.set_status('Hesap sırasında girdiler değişti; sonuç kullanılmadı.',True);return
        self.result=value
        self.headline.setText(report.verdict(value.worst_case_pass)+' · '+value.kind)
        for key in self.result_cards:self.result_cards[key].setText(compact(getattr(value,key))+' mm')
        summary='En küçük/en büyük değerler, tüm ölçülerin tolerans uçlarından hesaplanır (Worst-Case).'
        if value.rss_minimum is not None:
            summary+=f'\nİstatistiksel aralık (RSS): {compact(value.rss_minimum)} … {compact(value.rss_maximum)} mm. Bu aralık garanti değildir.'
        if value.worst_case_pass is None:summary+='\nKabul sınırı girilmedi; uygunluk değerlendirilmedi.'
        self.result_summary.setText(summary)
        if self.project.sources:self.result_summary.setText(self.result_summary.text()+f'\nKaynak doğrulama: {value.timestamp} (UTC). '
            'Disk değişiklikleri izlenir; kaydedilmemiş SolidWorks değişiklikleri yeniden kontrolde/aktarımda okunur.')
        self.assumptions.setText('\n'.join(value.assumptions))
        self.metric_model.replace([dict(name=str(key),value=str(val)) for key,val in report.summary_rows(self.project,value)])
        self.metrics.setColumnWidth(0,260)
        critical=sorted(value.contributions,key=lambda x:x.variance_percent if x.variance_percent is not None else x.worst_case_percent,reverse=True)[:3]
        self.critical_label.setText('Kritik ölçüler: '+' · '.join(c.name+f' %{fmt(c.variance_percent if c.variance_percent is not None else c.worst_case_percent,1)}' for c in critical))
        self.draw();self.tabs.setCurrentIndex(2);self.set_status('Hesap tamamlandı. Sonuçlar, katkı grafikleri ve PDF/Excel çıktıları hazır.')

    def copy_result(self):
        if self.result is None:return
        if self.result.project_digest!=self.project.fingerprint():self.invalidate();return
        snapshot,value=project_snapshot(self.project),self.result
        text='\n'.join(f'{key}: {value}' for key,value in report.summary_rows(snapshot,value))
        if not snapshot.sources:
            QApplication.clipboard().setText(text);self.set_status('Analiz özeti ve varsayımlar kopyalandı.');return
        def operation(sink,stop):
            solidworks_reader.verify_live(snapshot,stop=stop);report.assert_current(snapshot,value,stop=stop)
            sink.put(('stack_clipboard',text))
        self.start_job('check',operation)

    def watch_sources(self):
        if self.source_watcher.files():self.source_watcher.removePaths(self.source_watcher.files())
        if self.project.sources:self.source_watcher.addPaths([s.path for s in self.project.sources])

    def source_changed(self,path):
        self.invalidate();self.set_status('Kaynak teknik resim değişti veya silindi. Ölçüleri yeniden tarayın; eski sonuç kaldırıldı.',True)

    def export_report(self,kind):
        if self.result is None:self.set_status('Önce güncel bir analiz hesaplayın.',True);return
        path,_=QFileDialog.getSaveFileName(self,'Analiz raporunu kaydet',f'GOKWORKS_Analiz.{kind}',f'{kind.upper()} (*.{kind})')
        if not path:return
        snapshot,value=project_snapshot(self.project),self.result
        def operation(sink,stop):
            solidworks_reader.verify_live(snapshot,stop=stop)
            (report.export_pdf if kind=='pdf' else report.export_excel)(snapshot,value,path,overwrite=True,stop=stop)
            sink.put(('stack_output',dict(path=path,saved=True,mode=kind)))
        self.start_job('report',operation)

    def export_drawing(self):
        index=self.output_mode.currentIndex()
        if index==0:self.tabs.setCurrentIndex(2);return
        if self.result is None:self.set_status('Önce güncel bir analiz hesaplayın.',True);return
        source=self.target.text()
        if not source:self.set_status('Hedef teknik resmi seçin.',True);return
        mode={1:'memory',2:'copy',3:'source'}[index];destination=None;approved=False
        if mode=='copy':
            destination,_=QFileDialog.getSaveFileName(self,'Analizli teknik resmi farklı kaydet',str(Path(source).with_name(Path(source).stem+'-Analiz.SLDDRW')),'SolidWorks (*.SLDDRW)')
            if not destination:return
        elif mode=='source':
            approved=QMessageBox.question(self,'Kaynak teknik resme kayıt onayı',
                f'{source}\n\nKaynak çizime yalnız GOKWORKS analiz anotasyonları eklenecek ve dosya kaydedilecek. '
                'Önce aynı klasörde .gokworks-backups altında doğrulanmış yedek oluşturulur. Üretim ölçüleri değiştirilmez. Devam edilsin mi?',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
            if not approved:return
        try:position=tuple(float(number(self.position.value(key))/1000) for key in ('x','y'))
        except ValueError as error:self.set_status(str(error),True);return
        snapshot,value=project_snapshot(self.project),self.result
        new_sheet,labels=self.new_sheet.isChecked(),self.labels.isChecked()
        def operation(sink,stop):
            output=drawing_writer.write_drawing(snapshot,value,source,mode=mode,destination=destination,new_sheet=new_sheet,
                labels=labels,position=position,approved=approved,stop=stop)
            sink.put(('stack_output',output))
        self.start_job('drawing',operation)

    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(self,'Kaydedilmemiş analiz','Mevcut analizde kaydedilmemiş değişiklikler var. Devam edilsin mi?',
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def new_project(self):
        if not self.confirm_discard():return
        self.project=Project();self.project_path='';self.selected_files=[];self.result=None
        self.target.setText('');self.source_info.setText('Yeni manuel analiz · SolidWorks kaynağı yok.');self.watch_sources()
        self.load_form();self.invalidate();self.refresh();self.dirty=False
        self.expand_library.setChecked(False);self.tabs.setCurrentIndex(0)

    def load_example(self):
        if not self.confirm_discard():return
        self.project=Project(name='A − B − C · Fonksiyonel boşluk',acceptance_max=number('.40'),method='rss',truncate_normal=False)
        self.project.dimensions=[manual_dimension('A',50,'-.10','.10'),manual_dimension('B',20,'-.05','.05'),manual_dimension('C','29.80','-.03','.03')]
        self.project.terms=[Term(d.id,1 if i==0 else -1,f'P{i}',f'P{i+1}',datum='A') for i,d in enumerate(self.project.dimensions)]
        self.project.end='P3';self.project_path='';self.selected_files=[]
        self.target.setText('');self.source_info.setText('Manuel örnek · SolidWorks kaynağı yok.');self.watch_sources()
        self.load_form();self.invalidate();self.refresh();self.expand_library.setChecked(False);self.tabs.setCurrentIndex(0)
        self.set_status('Örnek: 50 − 20 − 29,8 = 0,2 mm. Kontrol kutusunu işaretleyip Hesapla düğmesine basın.')

    def save_project(self):
        try:self.capture_settings()
        except ValueError as error:self.set_status(str(error),True);return
        path,_=QFileDialog.getSaveFileName(self,'Analiz projesini kaydet',self.project_path or 'GOKWORKS.gokstack.json','GOKWORKS analiz (*.gokstack.json *.json)')
        if not path:return
        snapshot,value=project_snapshot(self.project),self.result
        self.start_job('save',lambda sink,stop:(storage.save_project(snapshot,path,result=value,overwrite=True,stop=stop),sink.put(('stack_saved',path))))

    def open_project(self):
        if not self.confirm_discard():return
        path,_=QFileDialog.getOpenFileName(self,'Analiz projesini aç','','GOKWORKS analiz (*.gokstack.json *.json)')
        if not path:return
        def operation(sink,stop):
            project,archive=storage.load_project(path);issues=''
            try:storage.check_sources(project,stop=stop)
            except ValueError as error:issues=str(error)
            sink.put(('stack_loaded',(project,path,issues,bool(archive))))
        self.start_job('load',operation)

    def handle_events(self,events):
        super().handle_events(events)
        latest={kind:index for index,(kind,_) in enumerate(events) if kind in ('stack_phase','stack_progress')}
        for index,(kind,value) in enumerate(events):
            if kind in latest and latest[kind]!=index:continue
            if kind=='stack_sources':self.merge_sources(*value)
            elif kind=='stack_result':self.show_result(value)
            elif kind=='stack_progress':self.progressChanged.emit(*value)
            elif kind=='stack_phase':self.set_status(value)
            elif kind=='stack_saved':self.project_path=value;self.dirty=False;self.set_status('Analiz projesi atomik olarak kaydedildi.')
            elif kind=='stack_loaded':
                self.project,self.project_path,issues,archived=value;self.load_form();self.invalidate();self.refresh();self.dirty=False
                self.selected_files=[s.path for s in self.project.sources]
                self.watch_sources();self.source_info.setText(f'Proje verisi · {len(self.project.sources)} CAD kaynağı. Açık SolidWorks oturumu henüz doğrulanmadı.')
                if self.project.sources:self.target.setText(self.project.sources[0].path)
                else:self.target.setText('')
                self.set_status('Proje açıldı. Eski sonuç güncel sayılmaz; kaynakları ve zinciri doğrulayıp yeniden hesaplayın.'+('\n'+issues if issues else ''),bool(issues))
            elif kind=='stack_output':
                self.set_status(('Çıktı kaydedildi: ' if value['saved'] else 'Anotasyon eklendi; çizim kaydedilmedi: ')+value['path']+
                    ('\nYedek: '+value['backup'] if value.get('backup') else ''))
                if value['mode']=='source':self.invalidate();self.set_status('Kaynak analiz anotasyonlarıyla kaydedildi; üretim ölçüleri korunur. Yeni dosya revizyonu için yeniden tarayın. Yedek: '+value['backup'])
            elif kind=='stack_clipboard':
                QApplication.clipboard().setText(value);self.set_status('Kaynaklar doğrulandı; analiz özeti ve varsayımlar kopyalandı.')
            elif kind in ('job_error','stack_cancelled'):
                if self.active_operation in ('calculate','scan','check','drawing'):
                    self.invalidate()
                self.set_status(value['error'] if kind=='job_error' else value,kind=='job_error')
