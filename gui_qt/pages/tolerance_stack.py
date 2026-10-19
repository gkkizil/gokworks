"""Integrated, asynchronous Qt workflow for drawing-based 1D tolerance chains."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt,QSignalBlocker,QFileSystemWatcher
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QTabWidget,QLineEdit,QComboBox,
    QTableView,QCheckBox,QFileDialog,QMessageBox,QApplication)

from tolerance_stack.models import Project,Term,number,fmt,manual_dimension,snapshot as project_snapshot
from tolerance_stack.calculator import calculate,Cancelled,check_cancel
from tolerance_stack import storage,solidworks_reader,drawing_writer,report
from tolerance_stack.diagram import draw_chain,draw_contributions,draw_histogram
from ..components import BasePage,ValueForm,PathPicker,card,label,button,scroll,configure_view,show_details
from ..models import Column,TableModel,FilterProxy
from ..diagrams import EngineeringDiagram
from .stack_dialogs import MemorySettings,DimensionDialog,TermDialog,IsoPairDialog,KINDS,DIST


METHODS={'Worst-Case':'worst_case','Worst-Case + RSS':'rss','Worst-Case + RSS + Monte Carlo':'all'}
DISTRIBUTIONS={'Normal':'normal','Uniform':'uniform','Üçgensel':'triangular'}
HELP=('1. Aktif .SLDDRW teknik resmini veya birden fazla dosyayı okuyun; SolidWorks olmadan manuel ölçü ekleyebilirsiniz.\n'
      '2. Yalnız fonksiyonel zincire ait ölçüleri seçip +/− yönüyle ekleyin. Başlangıç/bitiş ve ortak datum/ekseni tanımlayın.\n'
      '3. Çap/radyüs için doğrusal ilişkiyi açıklayın. Açılar, BASIC/referans ölçüler ve GD&T doğrudan kullanılamaz.\n'
      '4. Tolerans bilinmiyorsa manuel tamamlayın. ISO 2768 veya genel tolerans kendiliğinden atanmaz.\n'
      '5. Ayarlarda kabul sınırlarını ve dağılım varsayımlarını belirleyin. Zinciri doğrulayıp hesaplayın.\n'
      '6. WC tüm sınırları kapsar; RSS istatistiksel bir aralıktır. Normal dağılım kesilmiyorsa tolerans dışı örnekler mümkündür.\n'
      '7. Cp/Cpk ve PPM varsayımsaldır; gerçek proses kabiliyeti değildir. Sıfır gözlenen hata, sıfır gerçek PPM garantilemez.\n'
      '8. Sonuçları PDF/Excel olarak veya teknik resme ayrı GOKWORKS anotasyonları olarak aktarın.\n'
      '9. Varsayılan işlem kaynak çizimi kaydetmez. Farklı kaydet kopyada çalışır. Kaynağa kayıt ayrıca açık onay ve doğrulanmış yedek gerektirir.\n'
      '10. Projeyi JSON olarak kaydedin. Açılan dosyanın eski sonucu güncel sayılmaz; kaynakları doğrulayıp tekrar hesaplayın.\n\n'
      'Bu sürüm 1D doğrusal analiz içindir. Korelasyon, konum/profil/MMC/LMC ve 3D GD&T hesapları desteklenmez.')


class StackTable(TableModel):
    def data(self,index,role=Qt.DisplayRole):
        if role==Qt.TextAlignmentRole and index.isValid() and self.columns[index.column()].key in (
            'nominal','lower','upper','minimum','maximum','variance','wc','factor'):
            return Qt.AlignRight|Qt.AlignVCenter
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
        super().__init__(context,'Tolerans yığılması','Teknik resim ölçülerinden doğrulanmış 1D fonksiyonel zincir oluşturun.')
        self.project=Project();self.result=None;self.selected_files=[];self.loading=False
        self.dirty=False;self.active_operation='';self.project_path='';self.metadata_error=''
        self.source_watcher=QFileSystemWatcher(self)
        self.source_watcher.fileChanged.connect(self.source_changed)
        self.action('Proje aç',self.open_project)
        self.action('Proje kaydet',self.save_project)
        self.action('Rehber',lambda:show_details(self,'Tolerans yığılması · Rehber',HELP))
        self.stop_button=self.action('Durdur',self.jobs.cancel,locked=False);self.stop_button.setEnabled(False)
        source,body=card()
        toolbar=QHBoxLayout()
        self.active_button=button('Aktif teknik resmi oku',lambda:self.scan(active=True))
        self.choose_button=button('Dosya seç',self.choose_sources)
        self.scan_button=button('Ölçüleri tara',self.scan)
        self.check_button=button('Kaynakları doğrula',self.check_sources)
        for widget in (self.active_button,self.choose_button,self.scan_button,self.check_button): toolbar.addWidget(widget)
        body.addLayout(toolbar)
        self.source_info=label('SolidWorks: henüz bağlanılmadı · Manuel analiz çevrimdışı çalışır.','muted')
        body.addWidget(self.source_info);self.layout.addWidget(source)
        self.splitter=QSplitter(Qt.Horizontal)
        library,left=card('Teknik resim ölçüleri')
        search=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Ölçü, sayfa, görünüm veya kaynak ara…')
        self.filter=QComboBox();self.filter.addItems(('Tümü','Doğrusal','Çap / radyüs','Eksik tolerans','Desteklenmeyen'))
        search.addWidget(self.search,1);search.addWidget(self.filter);left.addLayout(search)
        self.library=configure_view(QTableView());self.library.setMinimumWidth(250)
        self.library.setMinimumHeight(185)
        self.library_model=StackTable((Column('Ölçü','name'),Column('Nominal mm','nominal',fmt),Column('Alt sapma','lower',fmt),
            Column('Üst sapma','upper',fmt),Column('Minimum mm','minimum',fmt),Column('Maksimum mm','maximum',fmt),
            Column('Sayfa / görünüm','location'),Column('Tür / tolerans','type'),Column('Kaynak','source')))
        self.library_proxy=LibraryFilter(self);self.library_proxy.setSourceModel(self.library_model)
        self.library.setModel(self.library_proxy);self.library.setColumnWidth(0,190)
        for index,width in enumerate((140,95,85,85,95,95,160,160,240)):self.library.setColumnWidth(index,width)
        self.search.textChanged.connect(self.library_proxy.set_query);self.filter.currentTextChanged.connect(self.library_proxy.set_category)
        self.library.doubleClicked.connect(self.edit_dimension);left.addWidget(self.library,1)
        self.expand_library=button('Ölçü tablosunu genişlet')
        self.expand_library.setCheckable(True)
        self.expand_library.toggled.connect(lambda checked:self.tabs.setVisible(not checked))
        left.addWidget(self.expand_library)
        for choices in ((('+ Zincire ekle',lambda:self.add_selected(1)),('− Zincire ekle',lambda:self.add_selected(-1))),
                        (('Manuel ölçü',self.add_manual),('ISO geçme',self.add_iso)),
                        (('Ölçüyü düzenle',self.edit_dimension),('Kaynağı göster',self.locate)),
                        (('Yeni analiz',self.new_project),('Örneği yükle',self.load_example))):
            row=QHBoxLayout()
            for text,callback in choices: row.addWidget(button(text,callback))
            left.addLayout(row)
        left.addWidget(label('Çift tıklama: yalnız analiz verisini düzenler. Üretim ölçüleri değiştirilmez.','muted'))
        library_scroll=scroll(library);library_scroll.setMinimumWidth(330)
        self.splitter.addWidget(library_scroll)
        self.tabs=QTabWidget();self.splitter.addWidget(self.tabs);self.splitter.setSizes([490,700]);self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter,1)
        self.chain_host=QWidget();chain=QVBoxLayout(self.chain_host);chain.setContentsMargins(0,0,0,0)
        self.chain_diagram=EngineeringDiagram(width=700,height=220);self.chain_diagram.setMinimumHeight(200)
        chain.addWidget(self.chain_diagram)
        self.chain_table=configure_view(QTableView());self.chain_table.setSortingEnabled(False)
        self.chain_table.setMinimumHeight(170)
        self.chain_model=StackTable((Column('Terim','label'),Column('Ölçü','name'),Column('Yön','direction'),Column('Katsayı','factor',fmt),
            Column('Başlangıç','start'),Column('Bitiş','end'),Column('Eksen / datum','frame'),Column('İlişki / dağılım','relation')))
        self.chain_table.setModel(self.chain_model);self.chain_table.doubleClicked.connect(self.edit_term);chain.addWidget(self.chain_table,1)
        for index,width in enumerate((55,130,50,75,80,80,95,240)):self.chain_table.setColumnWidth(index,width)
        for choices in ((('Yukarı',lambda:self.move_term(-1)),('Aşağı',lambda:self.move_term(1)),('İlişkiyi düzenle',self.edit_term)),
                        (('Çıkar',self.remove_term),('Noktaları sıraya bağla',self.relink))):
            actions=QHBoxLayout()
            for title,callback in choices:actions.addWidget(button(title,callback))
            chain.addLayout(actions)
        self.confirm_box=QCheckBox('Fonksiyonel zinciri doğruladım.');self.confirm_box.toggled.connect(self.confirm_chain)
        chain.addWidget(self.confirm_box)
        chain.addWidget(label('Yönleri, başlangıç/bitiş noktalarını ve kaynak görünümlerinin ortak datum/eksen ilişkisini doğrulayın.','muted'))
        self.calculate_button=button('Analizi hesapla',self.start_calculation,primary=True);chain.addWidget(self.calculate_button)
        chain.addWidget(label('Tüm çizim ölçüleri kendiliğinden toplanmaz. Aynı fiziksel ölçünün tekrarı, eksik tolerans ve süreksiz zincir hesabı engeller.','muted'))
        self.tabs.addTab(scroll(self.chain_host),'Zincir')
        settings,settings_body=card('Analiz ve dağılım ayarları')
        self.form=ValueForm(MemorySettings(),'')
        for key,title in (('name','Analiz adı'),('critical','Kritik fonksiyonel ölçü'),('start','Zincir başlangıcı'),('end','Zincir bitişi'),('datum','Ortak fonksiyonel datum')):
            self.form.text(key,title,getattr(self.project,key))
        self.form.combo('axis','Doğrusal eksen',('X','Y','Z'),'X')
        self.form.text('acceptance_min','Minimum kabul · mm (boş = sınır yok)','0')
        self.form.text('acceptance_max','Maksimum kabul · mm (boş = sınır yok)','')
        self.form.combo('method','Hesap yöntemi',METHODS,'Worst-Case + RSS + Monte Carlo')
        self.form.combo('distribution','Varsayılan dağılım',DISTRIBUTIONS,'Normal')
        self.form.text('input_sigma','Normal giriş bandı: ±nσ','3');self.form.text('output_sigma','RSS sonuç bandı: ±nσ','3')
        self.form.check('truncate_normal','Normal dağılımı tolerans sınırlarında kes',True)
        self.form.text('samples','Monte Carlo örnek sayısı','50000');self.form.text('seed','Seed (boş = rastgele)','42')
        self.form.check('independent','RSS / MC girdileri bağımsız kabul ediliyor',True)
        self.form.check('offline_snapshot','CAD ölçülerini çevrimdışı anlık görüntü olarak kullan',False)
        settings_body.addWidget(self.form)
        settings_body.addWidget(label('Asimetrik toleransta nominal ve bant merkezi ayrıdır. Normal girdide varsayılan σ = yarı genişlik / 3; '
            'Uniform ve üçgensel dağılım kendi varyanslarını kullanır. RSS/MC korelasyon modeli içermez. '
            'Çevrimdışı CAD verisi açık SolidWorks oturumuna karşı doğrulanamaz; bu seçim teknik resme aktarımı engeller.','muted'))
        self.form.changed.connect(self.form_changed);self.tabs.addTab(scroll(settings),'Ayarlar')
        results,results_body=card()
        self.headline=label('Zinciri doğrulayıp hesaplayın','result');results_body.addWidget(self.headline)
        self.result_summary=label('Worst-Case, RSS ve Monte Carlo sonuçları burada gösterilir.');results_body.addWidget(self.result_summary)
        self.assumptions=label('Hesap sonucu henüz yok.','muted');results_body.addWidget(self.assumptions)
        plots=QTabWidget();self.contribution_diagram=EngineeringDiagram(width=700,height=320);self.histogram=EngineeringDiagram(width=700,height=300)
        plots.addTab(self.contribution_diagram,'Tolerans katkıları');plots.addTab(self.histogram,'Monte Carlo dağılımı');results_body.addWidget(plots)
        self.critical_label=label();results_body.addWidget(self.critical_label)
        self.metrics=configure_view(QTableView());self.metrics.setMinimumHeight(230)
        self.metric_model=StackTable((Column('Sonuç / açıklama','name'),Column('Değer','value')));self.metrics.setModel(self.metric_model)
        self.metrics.setSortingEnabled(False)
        results_body.addWidget(self.metrics)
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
        self.tabs.addTab(scroll(output),'Teknik resim')
        self.controls.extend((self.active_button,self.choose_button,self.scan_button,self.check_button,library,self.chain_host,self.form,output,results))
        self.finish_layout();self.refresh()

    @property
    def appearance(self): return 'Dark' if self.context.appearance=='dark' else 'Light'

    def invalidate(self):
        self.project.invalidate();self.result=None;self.dirty=True
        with QSignalBlocker(self.confirm_box): self.confirm_box.setChecked(False)
        self.headline.setText('Zinciri doğrulayıp yeniden hesaplayın');self.result_summary.clear()
        self.metric_model.replace([]);self.assumptions.setText('Girdiler değişti; önceki sonuç güncel sayılmaz.');self.critical_label.clear()
        self.draw()

    def capture_settings(self):
        f=self.form;p=replace(self.project)
        for key in ('name','critical','start','end','axis','datum'): setattr(p,key,f.value(key).strip())
        for key in ('acceptance_min','acceptance_max'):
            setattr(p,key,number(f.value(key),key) if f.value(key).strip() else None)
        for key in ('input_sigma','output_sigma'): setattr(p,key,number(f.value(key),key))
        samples=number(f.value('samples'),'Örnek sayısı')
        if samples!=samples.to_integral_value(): raise ValueError('Örnek sayısı tam sayı olmalı.')
        p.samples=int(samples)
        seed=number(f.value('seed'),'Seed') if f.value('seed').strip() else None
        if seed is not None and seed!=seed.to_integral_value(): raise ValueError('Seed tam sayı olmalı.')
        p.seed=int(seed) if seed is not None else None
        p.method=METHODS[f.value('method')];p.distribution=DISTRIBUTIONS[f.value('distribution')]
        for key in ('independent','truncate_normal','offline_snapshot'): setattr(p,key,f.value(key))
        self.project=p;self.metadata_error=''

    def load_form(self):
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
        except ValueError as error:self.metadata_error=str(error);self.set_status(str(error),True)
        self.draw()

    def refresh(self):
        rows=[]
        for d in self.project.dimensions:
            rows.append(dict(id=d.id,name=d.name,nominal=None if d.nominal is None else float(d.nominal),
                lower=None if d.lower is None else float(d.lower),upper=None if d.upper is None else float(d.upper),
                minimum=None if d.minimum is None else float(d.minimum),maximum=None if d.maximum is None else float(d.maximum),
                location=f'{d.sheet} / {d.view}',kind=d.kind,type=next((title for title,key in KINDS.items() if key==d.kind),d.kind)+' · '+d.tolerance_type,source=d.source or 'Manuel',
                missing=d.nominal is None or d.lower is None or d.upper is None,note=d.note,configuration=d.configuration))
        self.library_model.replace(rows)
        dimensions={d.id:d for d in self.project.dimensions}
        self.chain_model.replace([dict(label=f'L{i}',name=dimensions[t.dimension_id].name if t.dimension_id in dimensions else 'Kaynak ölçü silinmiş',
            direction='+' if t.direction>0 else '−',factor=float(t.factor),start=t.start,end=t.end,frame=t.axis+' / '+t.datum,
            relation=t.relation+' · '+next(title for title,key in DIST.items() if key==t.distribution),index=i-1) for i,t in enumerate(self.project.terms,1)])
        self.draw()

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
        if dialog.exec():
            self.project.dimensions.append(dialog.value);self.invalidate();self.refresh()

    def edit_dimension(self,*args):
        d=self.selected_dimension()
        if d is None:return
        if d.kind in ('angle','gdt','basic','reference','arc','chamfer'):
            show_details(self,'Ölçü sınıflandırması',d.kind+'\n'+d.note+'\nBu tür için doğrulanmış ayrı matematiksel model gerekli.');return
        dialog=DimensionDialog(self,d)
        if dialog.exec():
            self.project.dimensions=[dialog.value if item.id==d.id else item for item in self.project.dimensions]
            self.invalidate();self.refresh()

    def add_selected(self,direction):
        d=self.selected_dimension()
        if d is None:self.set_status('Önce bir ölçü seçin.',True);return
        self.append_dimension(d,direction)

    def append_dimension(self,d,direction,*,factor=1,relation=''):
        start=self.project.terms[-1].end if self.project.terms else self.project.start
        used={t.start for t in self.project.terms}|{t.end for t in self.project.terms}|{start}
        end=f'P{len(self.project.terms)+1}'
        while end in used:end+='a'
        self.project.terms.append(Term(d.id,direction,start,end,self.project.axis,self.project.datum,factor,relation))
        self.expand_library.setChecked(False)
        self.project.end=end;self.load_form();self.invalidate();self.refresh()
        self.chain_table.selectRow(len(self.project.terms)-1)
        if d.source and not relation:self.set_status('Kaynak görünümün ortak datum/eksen eşlemesini İlişkiyi düzenle düğmesiyle açıklayın.')
        if sum((item.physical_id or item.id)==(d.physical_id or d.id) for t in self.project.terms for item in self.project.dimensions if item.id==t.dimension_id)>1:
            self.set_status('Aynı fiziksel ölçü tekrar eklendi; bağımsız kabul edilemez. Hesaplamadan önce düzeltin.',True)

    def add_iso(self):
        dialog=IsoPairDialog(self)
        if dialog.exec():
            hole,shaft,factor,relation=dialog.value
            self.project.dimensions.extend((hole,shaft));self.append_dimension(hole,1,factor=factor,relation=relation)
            self.append_dimension(shaft,-1,factor=factor,relation=relation)

    def chain_index(self):
        index=self.chain_table.currentIndex();return index.row() if index.isValid() else -1

    def edit_term(self,*args):
        index=self.chain_index()
        if index<0:return
        term=self.project.terms[index];d=next((d for d in self.project.dimensions if d.id==term.dimension_id),None)
        if d is None:self.set_status('Kaynak ölçü bulunamadı; yeniden tarayın.',True);return
        dialog=TermDialog(self,term,d)
        if dialog.exec():self.project.terms[index]=dialog.value;self.invalidate();self.refresh()

    def move_term(self,direction):
        index=self.chain_index();target=index+direction
        if index<0 or not 0<=target<len(self.project.terms):return
        self.project.terms[index],self.project.terms[target]=self.project.terms[target],self.project.terms[index]
        self.invalidate();self.refresh();self.chain_table.selectRow(target)
        self.set_status('Sıra değişti. Fonksiyonel bağlantıları inceleyin veya Noktaları sıraya bağla düğmesini kullanın.')

    def remove_term(self):
        index=self.chain_index()
        if index<0:return
        self.project.terms.pop(index);self.invalidate();self.refresh()

    def relink(self):
        if not self.project.terms:return
        start=self.project.start
        for i,t in enumerate(self.project.terms):
            end=self.project.end if i==len(self.project.terms)-1 else f'{self.project.start}-N{i+1}'
            self.project.terms[i]=replace(t,start=start,end=end);start=end
        self.invalidate();self.refresh();self.set_status('Şematik zincir bağlandı. Gerçek datum/konum ilişkisini ayrıca doğrulayın.')

    def confirm_chain(self,checked):
        if not checked:self.invalidate();return
        try:
            self.capture_settings();self.project.confirm();self.set_status('Fonksiyonel zincir doğrulandı; hesaplanabilir.')
        except ValueError as error:
            with QSignalBlocker(self.confirm_box):self.confirm_box.setChecked(False)
            self.set_status(str(error),True)

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
            if self.project.confirmed_digest!=self.project.fingerprint():raise ValueError('Önce fonksiyonel zinciri doğrulayın.')
        except ValueError as error:self.set_status(str(error),True);return
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
        if paths:self.selected_files=paths;self.source_info.setText(f'{len(paths)} teknik resim seçildi. Ölçüleri tara düğmesine basın.')

    def scan(self,checked=False,*,active=False):
        paths=None if active else tuple(self.selected_files)
        if not active and not paths:self.set_status('Teknik resim dosyalarını seçin veya Aktif teknik resmi oku düğmesini kullanın.',True);return
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
        self.source_info.setText(f'SolidWorks: okundu · {len(self.project.sources)} teknik resim · {len(self.project.dimensions)} ölçü/anotasyon. '
            'Kaynak veya zincir değişti; yeniden doğrulayın.')
        self.set_status('Ölçüler okundu. Bilinmeyen toleransları tamamlayıp fonksiyonel ölçüleri seçin.')

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
        self.result_summary.setText(f'Nominal: {fmt(value.nominal)} mm\nWorst-Case: {fmt(value.minimum)} … {fmt(value.maximum)} mm\n'
            f'Dağılım merkezi: {fmt(value.mean)} mm · RSS: {fmt(value.rss_minimum)} … {fmt(value.rss_maximum)} mm')
        if self.project.sources:self.result_summary.setText(self.result_summary.text()+f'\nKaynak doğrulama: {value.timestamp} (UTC). '
            'Disk değişiklikleri izlenir; kaydedilmemiş SolidWorks değişiklikleri yeniden kontrolde/aktarımda okunur.')
        self.assumptions.setText('\n'.join(value.assumptions))
        self.metric_model.replace([dict(name=str(key),value=str(val)) for key,val in report.summary_rows(self.project,value)])
        self.metrics.setColumnWidth(0,260)
        critical=sorted(value.contributions,key=lambda x:x.variance_percent if x.variance_percent is not None else x.worst_case_percent,reverse=True)[:3]
        self.critical_label.setText('Kritik ölçüler: '+' · '.join(c.name+f' %{fmt(c.variance_percent if c.variance_percent is not None else c.worst_case_percent,1)}' for c in critical))
        self.draw();self.tabs.setCurrentIndex(2);self.set_status('Analiz tamamlandı; sonuçlar varsayımları ve kaynak bilgileriyle doğrulandı.')

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

    def load_example(self):
        if not self.confirm_discard():return
        self.project=Project(name='A − B − C · Fonksiyonel boşluk',acceptance_max=number('.40'),method='rss',truncate_normal=False)
        self.project.dimensions=[manual_dimension('A',50,'-.10','.10'),manual_dimension('B',20,'-.05','.05'),manual_dimension('C','29.80','-.03','.03')]
        self.project.terms=[Term(d.id,1 if i==0 else -1,f'P{i}',f'P{i+1}',datum='A') for i,d in enumerate(self.project.dimensions)]
        self.project.end='P3';self.project_path='';self.selected_files=[]
        self.target.setText('');self.source_info.setText('Manuel örnek · SolidWorks kaynağı yok.');self.watch_sources()
        self.load_form();self.invalidate();self.refresh();self.tabs.setCurrentIndex(0)
        self.set_status('Örnek yüklendi. Beklenen Worst-Case: 0,02 … 0,38 mm; nominal 0,20 mm. Zinciri doğrulayın.')

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
