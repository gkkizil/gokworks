"""Teknik olmayan kullanıcı için ölçü, hareket ve sonuç odaklı Qt görünümü."""
from dataclasses import replace
import math
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,
                               QTabWidget,QComboBox,QAbstractItemView,QTableWidget,QTableWidgetItem)
from gui_qt.components import label,button,scroll
from gui_qt.theme import COLORS
from .beginner import simple_supported,phase_seconds,FORCE_FACTORS
from .core.validation import InputError
from .presentation import result_rows
from .core.cylinder import areas,buckling

MOVEMENTS = {'extend':'İleri itme','retract':'Geri çekme','regenerate':'Hızlı ileri hareket (yağ geri kazanımlı)',
             'hold':'Yerinde basınçla bekleme','idle':'Makine boşta bekliyor'}


def text_number(value):
    return f'{value:.6f}'.rstrip('0').rstrip('.').replace('.',',')


class CylinderGuide(QWidget):
    """Gerçek model olmayan, hangi ölçünün nereden alınacağını anlatan çizim."""
    def __init__(self,context):
        super().__init__(); self.context=context; self.setMinimumHeight(180)
        self.setAccessibleName('Silindir ölçü rehberi: piston iç çapı, mil çapı ve hareket mesafesi')

    def paintEvent(self,event):
        c=COLORS[self.context.appearance]; p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        try:
            p.setPen(QPen(QColor(c['text']),2)); w=self.width()
            x=25.; y=45.; body=min(240.,w*.48); end=min(w-25,x+body+140)
            p.drawRect(QRectF(x,y,body,65));p.drawRect(QRectF(x+body-35,y+6,20,53))
            p.drawRect(QRectF(x+body-15,y+25,end-x-body+15,15))
            p.setPen(QColor(c['accent']));p.drawText(QRectF(x+5,y+20,body-45,30),Qt.AlignCenter,'Piston çapı (iç çap)')
            p.drawText(QRectF(x+body,y-24,end-x-body+20,22),Qt.AlignCenter,'Mil çapı')
            p.setPen(QColor(c['muted']));p.drawLine(int(x+body),135,int(end),135)
            p.drawText(QRectF(x,145,w-50,25),Qt.AlignCenter,'Hareket mesafesi = milin gidebildiği yol (strok)')
            p.drawText(QRectF(x,8,w-50,25),Qt.AlignLeft,'Ölçü rehberi · çizim ölçekli değildir')
        finally:p.end()


class ExplanationTable(QTableWidget):
    """Altı öneriyi kendi içinde kaydırma gerektirmeden okunur yükseklikte tutar."""
    def __init__(self):
        super().__init__(0,3)
        self.sizer=QTimer(self);self.sizer.setSingleShot(True);self.sizer.timeout.connect(self.fit_rows)

    def resizeEvent(self,event):
        super().resizeEvent(event);self.sizer.start(0)

    def fit_rows(self):
        self.resizeRowsToContents()
        height=self.horizontalHeader().height()+sum(self.rowHeight(r) for r in range(self.rowCount()))+4
        if self.height()!=height:self.setFixedHeight(height)


class BeginnerView(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.loading=False;self.inputs={};self.phase_inputs=[]
        self.previous_cycle=None;self.supported=True
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0)
        box.addWidget(label('Neye ihtiyacınız olduğunu üç adımda öğrenin','section'))
        box.addWidget(label('Ölçüleri ve yapılacak işleri girin; motor, pompa ve soğutma ihtiyacını öğrenin. İlk açılış değerleri örnektir; bir proje açarsanız onun değerleri gösterilir.','muted'))
        self.unsupported=label('Bu projede çok sayıda hareket veya birden fazla silindir var. Verileriniz korunuyor; düzenlemek için “Ayrıntılı ayarlar”ı açın.','warning')
        box.addWidget(self.unsupported)
        self.error_notice=label('','error');self.error_notice.setTextFormat(Qt.PlainText);self.error_notice.hide();box.addWidget(self.error_notice)
        self.fix_button=button('İlgili ayrıntılı ayarı aç →',owner.focus_first_problem);self.fix_button.hide();box.addWidget(self.fix_button)
        self.steps=QTabWidget();self.steps.setDocumentMode(True);box.addWidget(self.steps,1)
        measure=QWidget();m=QVBoxLayout(measure)
        m.addWidget(label('1. Silindirin ölçülerini girin','section'))
        m.addWidget(label('Piston çapı gövdenin dış çapı değildir. Bu bilgiyi silindir etiketinden, teknik resimden veya üreticiden alın.','muted'))
        m.addWidget(CylinderGuide(owner.context))
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for key,title in [('bore','Piston çapı · mm'),('rod','Dışarı çıkan milin çapı · mm'),('stroke','Toplam hareket mesafesi · mm')]:
            widget=self.input('cylinder.'+key,title)
            form.addRow(title,widget)
        m.addLayout(form)
        m.addWidget(label('Toplam mesafe silindirin sınırıdır. Her hareketin ne kadar yol alacağını ikinci adımda belirleyin.','muted'))
        m.addWidget(button('Devam: yapılacak hareketler →',lambda:self.steps.setCurrentIndex(1)));m.addStretch()
        self.steps.addTab(scroll(measure),'1 · Ölçüler')
        motion=QWidget();v=QVBoxLayout(motion)
        v.addWidget(label('2. Makine sırayla ne yapsın?','section'))
        v.addWidget(label('Her bölüm bir harekettir. Mesafeyi, kaç saniyede tamamlanacağını ve karşı koyan yükü girin. Geri çekme mesafesi, milin geriye alacağı yoldur.','muted'))
        row=QHBoxLayout();row.addWidget(label('Yük / kuvvet birimi',wrap=False))
        self.force_unit=QComboBox();self.force_unit.addItem('Kilonewton (kN)','kN');self.force_unit.addItem('Ton-kuvvet (tonf)','tonf')
        self.force_unit.setToolTip('Ton-kuvvet bir kuvvet birimidir; doğrudan yükün kütlesi değildir. 1 tonf = 9,80665 kN.')
        self.force_unit.currentIndexChanged.connect(self.change_force_unit);row.addWidget(self.force_unit);row.addStretch();v.addLayout(row)
        v.addWidget(label('Ton-kuvvet: kuvveti ton karşılığıyla ifade eder. Sürtünme, mekanizma oranı ve dinamik etkiler ayrıca değerlendirilmelidir.','muted'))
        self.motion_fields=QWidget();self.motion_box=QVBoxLayout(self.motion_fields);self.motion_box.setContentsMargins(0,0,0,0);v.addWidget(self.motion_fields)
        actions=QHBoxLayout()
        actions.addWidget(button('Basit ileri–bekle–geri örneği',owner.use_basic_cycle))
        self.undo_button=button('Önceki hareketlere dön',owner.undo_basic_cycle);actions.addWidget(self.undo_button)
        v.addLayout(actions);v.addWidget(button('Daha fazla silindir / farklı hareketler…',lambda:owner.open_detailed(1)))
        v.addWidget(button('Devam: sonuçları göster →',lambda:self.steps.setCurrentIndex(2)));v.addStretch()
        self.steps.addTab(scroll(motion),'2 · Hareketler')
        report=QWidget();r=QVBoxLayout(report)
        r.addWidget(label('3. Ne seçmeliyim?','section'))
        self.verdict=label('','section');self.verdict.setTextFormat(Qt.PlainText);r.addWidget(self.verdict)
        self.explanation=label('','muted');self.explanation.setTextFormat(Qt.PlainText);r.addWidget(self.explanation)
        self.warnings=label('','warning');self.warnings.setTextFormat(Qt.PlainText);r.addWidget(self.warnings)
        self.results=ExplanationTable();self.results.setHorizontalHeaderLabels(('İhtiyaç','Değer','Ne anlama geliyor?'))
        self.results.setEditTriggers(QAbstractItemView.NoEditTriggers);self.results.verticalHeader().hide()
        self.results.setWordWrap(True)
        from gui_qt.components import fit_columns
        fit_columns(self.results,elastic=2,minimum=150,defaults={0:165,1:100},autofit=())
        r.addWidget(self.results)
        self.assumptions=label('','muted');r.addWidget(self.assumptions)
        self.pump_button=button('Önerilen pompa hacmini uygula',owner.use_pump_recommendation);r.addWidget(self.pump_button)
        r.addWidget(button('Uyarıları ve bütün ayarları aç →',lambda:owner.open_detailed(6)))
        buttons=QHBoxLayout()
        self.pdf_button=button('PDF raporu al…',owner.export_pdf)
        self.excel_button=button('Excel tablosu al…',lambda:owner.export('excel'))
        self.cancel_pdf_button=button('Raporu durdur',owner.cancel_pdf)
        for b in (self.pdf_button,self.excel_button,self.cancel_pdf_button):buttons.addWidget(b)
        r.addLayout(buttons)
        self.status=label('','muted');self.status.setTextFormat(Qt.PlainText);r.addWidget(self.status);r.addStretch()
        self.steps.addTab(scroll(report),'3 · Sonuç ve rapor')

    def input(self,key,title):
        w=QLineEdit();w.setAccessibleName(title);w.setAlignment(Qt.AlignRight);w.setMinimumWidth(110);w.setMaximumWidth(240)
        w.textEdited.connect(self.owner.changed);self.inputs[key]=w
        return w

    def set_value(self,widget,value):
        widget.setText(text_number(value));widget._shown=(widget.text(),value)

    def value(self,widget,field):
        shown=getattr(widget,'_shown',None)
        if shown is not None and shown[0]==widget.text():return shown[1]
        try:
            value=float(widget.text().strip().replace(',','.'))
            if not math.isfinite(value):raise ValueError
            return value
        except ValueError:raise InputError(field,'Sayı girin; örneğin 63 veya 2,5.') from None

    def populate(self,project):
        self.loading=True
        try:
            self.supported=simple_supported(project);self.unsupported.setVisible(not self.supported)
            self.steps.setEnabled(self.supported);self.undo_button.setEnabled(self.previous_cycle is not None)
            if not self.supported:return
            for key in ('bore','rod','stroke'):self.set_value(self.inputs['cylinder.'+key],getattr(project.cylinders[0],key)*1000)
            while self.motion_box.count():
                item=self.motion_box.takeAt(0)
                if item.widget():item.widget().hide();item.widget().deleteLater()
            self.inputs={k:w for k,w in self.inputs.items() if k.startswith('cylinder.')}
            self.phase_inputs=[];factor=FORCE_FACTORS[self.force_unit.currentData()]
            for i,phase in enumerate(project.phases):
                group=QWidget();layout=QVBoxLayout(group);layout.setContentsMargins(0,8,0,8)
                layout.addWidget(label(f'{i+1}. {phase.name} — {MOVEMENTS[phase.kind]}','section'))
                form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows);controls={}
                specs=[('duration','Kaç saniye sürsün? · s',phase_seconds(phase))]
                if phase.kind not in ('hold','idle'):specs.insert(0,('stroke','Ne kadar yol alsın? · mm',phase.stroke*1000))
                if phase.kind!='idle':specs.append(('force','Gerekli itme / çekme kuvveti · '+self.force_unit.currentText(),phase.force/factor))
                for key,title,value in specs:
                    widget=self.input(f'phase.{i}.{key}',title);self.set_value(widget,value);controls[key]=widget
                    title_label=label(title,wrap=False);form.addRow(title_label,widget)
                    if key=='force':widget._force_label=title_label;widget._si_force=phase.force
                layout.addLayout(form);self.motion_box.addWidget(group);self.phase_inputs.append(controls)
        finally:self.loading=False

    def read_project(self,base):
        if not self.supported:return base
        c=base.cylinders[0]
        sizes={}
        for key in ('bore','rod','stroke'):
            widget=self.inputs['cylinder.'+key];value=self.value(widget,f'cylinders.0.{key}')
            if widget.text()!=getattr(widget,'_shown',('',None))[0]:sizes[key]=value/1000
        cylinder=replace(c,**sizes)
        try:areas(cylinder);buckling(cylinder,0)
        except InputError as error:raise InputError('cylinders.0.'+error.field,str(error)) from None
        except ArithmeticError as error:raise InputError('cylinders.0.bore','Ölçü çok büyük; milimetre cinsinden gerçek değeri girin.') from error
        phases=[];factor=FORCE_FACTORS[self.force_unit.currentData()]
        for i,(phase,controls) in enumerate(zip(base.phases,self.phase_inputs)):
            values={k:self.value(w,f'phases.{i}.{k}') for k,w in controls.items()}
            changed={k for k,w in controls.items() if getattr(w,'_shown',('',None))[0]!=w.text()}
            update={}
            if 'force' in controls:
                update['force']=values['force']*factor if 'force' in changed else controls['force']._si_force
            if 'stroke' in changed:update['stroke']=values['stroke']/1000
            if changed & {'duration','stroke'}:update.update(speed=None,duration=values['duration'])
            phases.append(replace(phase,**update))
        return replace(base,cylinders=(cylinder,),phases=tuple(phases),name=self.owner.name.text(),display_units=self.owner.units.currentData())

    def change_force_unit(self):
        if self.loading:return
        # Girdi önceki birimde okunur; birim değiştirme kuvveti değiştirmez.
        new=self.force_unit.currentData();old=getattr(self,'_force_unit','kN')
        candidates=[]
        for i,controls in enumerate(self.phase_inputs):
            if 'force' not in controls:continue
            w=controls['force']
            try:
                value=self.value(w,f'phases.{i}.force')
                force=w._si_force if getattr(w,'_shown',('',None))[0]==w.text() else value*FORCE_FACTORS[old]
            except InputError:
                self.force_unit.blockSignals(True);self.force_unit.setCurrentIndex(self.force_unit.findData(old));self.force_unit.blockSignals(False)
                self.status.setText('Birim değiştirmeden önce yük alanındaki sayıyı düzeltin.');return
            candidates.append((w,force))
        for w,force in candidates:
            self.set_value(w,force/FORCE_FACTORS[new]);w._si_force=force
            w._force_label.setText('Gerekli itme / çekme kuvveti · '+self.force_unit.currentText())
        self._force_unit=new

    def show_result(self,project,result):
        self.error_notice.hide();self.fix_button.hide()
        for widget in self.inputs.values():
            widget.setProperty('invalid',False);widget.style().unpolish(widget);widget.style().polish(widget)
        if not result.cycle['demand_met']:
            self.verdict.setText('Seçili pompa istediğiniz hareketleri karşılayamıyor.')
            self.explanation.setText('Hız veya kuvvet ihtiyacını azaltın ya da daha uygun pompa değerlendirin. Aşağıdaki değerler bir tasarım senaryosudur.')
        elif result.thermal['cooler_power']>0:
            self.verdict.setText('Pompa hareketleri karşılıyor; yağ için soğutma gerekiyor.')
            self.explanation.setText('Pompanın yeterli olması bütün ünitenin uygun olduğu anlamına gelmez. Soğutucu ihtiyacını ve diğer uyarıları birlikte inceleyin.')
        else:
            self.verdict.setText('Hesap tamamlandı. Seçim önerilerini inceleyin.')
            self.explanation.setText('Kullanım öncesinde uyarılar, gerçek ürün bilgileri ve uzman kontrolü gereklidir.')
        if result.thermal.get('status')=='scenario_only':
            self.explanation.setText(self.explanation.text()+' Isı ve soğutma değerleri bu durumda yalnız varsayımsal senaryodur; erişilmiş performans değildir.')
        rows={name:(value,unit) for name,value,unit,_ in result_rows(project,result)}
        choices=[('Seçilen motor','Motor gücü','Motorun pompayı çalıştırmak için gereken boyutu.'),
            ('Maksimum gerekli debi','Pompanın vermesi gereken yağ','Hareket için bir dakikada gereken yağ miktarı.'),
            ('Maksimum gerekli basınç','Gerekli basınç','Yükü hareket ettirmek için gereken basınç.'),
            ('Boru/hortum iç çapı','Hattın iç çapı','Akış için öneri; hortumun basınç dayanımını ayrıca doğrulayın.'),
            ('Gerekli kullanılabilir tank','Tankın yağ ihtiyacı','Tankın dış hacmi değil, kullanılabilir yağ hacmidir.'),
            ('Gerekli soğutucu','Soğutucu gücü','Hedef yağ sıcaklığını korumak için atılması gereken ısı.')]
        self.results.setRowCount(len(choices))
        for r,(key,title,help_) in enumerate(choices):
            value,unit=rows[key];display='Seri dışında / değerlendirilmedi' if value is None else f'{value:.2f} {unit}'
            for col,text in enumerate((title,display,help_)):self.results.setItem(r,col,QTableWidgetItem(text))
        self.results.resizeRowsToContents()
        self.results.sizer.start(0)
        translated={'HOT_OIL':'Yağ fazla ısınabilir. Soğutma ihtiyacını bir uzmanla doğrulayın.',
            'COOLER':'Yağı hedef sıcaklıkta tutmak için soğutucu gerekiyor.',
            'BUCKLING':'Silindir mili yük altında bükülebilir. Mil çapı ve bağlantıları kontrol edilmeli.',
            'VELOCITY':'Hattaki yağ akış hızı önerilen aralığın dışında; iç çapı kontrol edin.',
            'CAPACITY':'Seçili pompa bu hareket için yeterli değil.',
            'RELIEF_LIMIT':'Emniyet valfi ayarı pompanın sınırını aşıyor; ayarı düzeltin.',
            'MOTOR_SMALL':'Elle seçilen motorun gücü yetersiz.',
            'CYCLE_NOT_CLOSED':'Silindir başlangıç yerine dönmüyor; hareket sırası bu hâliyle tekrarlanamaz.'}
        self.warnings.setText('\n'.join(('Önemli: ' if issue.severity=='critical' else 'Kontrol edin: ')+translated.get(issue.code,issue.message)
            for issue in result.issues if issue.severity in ('critical','warning')))
        self.warnings.setProperty('role','error' if any(i.severity=='critical' for i in result.issues) else 'warning')
        self.warnings.style().unpolish(self.warnings);self.warnings.style().polish(self.warnings)
        self.assumptions.setText(f'Şu an seçili pompa: {project.pump.displacement*1e6:.2f} cm³/dev, {project.pump.angular_speed*60/(2*math.pi):.0f} dev/dak. '
            'Verim, yağ ve tank ayarları mevcut projeden alınır; bunları ayrıntılı görünümde kontrol edebilirsiniz. Öneriler imalat onayı değildir.')

    def show_error(self,error):
        self.error_notice.setText(str(error));self.error_notice.show();self.fix_button.show()
        self.verdict.setText('Önce girilen bilgileri düzeltin.');self.explanation.setText(str(error))
        self.results.setRowCount(0)
        self.warnings.setText('')
        parts=error.field.split('.');key=None
        if len(parts)>=3 and parts[0]=='cylinders':key='cylinder.'+parts[2]
        if len(parts)>=3 and parts[0]=='phases':key='phase.'+parts[1]+'.'+parts[2]
        for name,w in self.inputs.items():
            w.setProperty('invalid',name==key);w.style().unpolish(w);w.style().polish(w)
            w.setToolTip(str(error) if name==key else '')
        self.status.setText(str(error))

    def update_actions(self,result,busy,pdf_active):
        ready=result is not None and not busy and not pdf_active
        self.pdf_button.setEnabled(ready);self.excel_button.setEnabled(ready)
        self.pump_button.setEnabled(ready and result.cycle['displacement']['nominal'] is not None)
        self.cancel_pdf_button.setVisible(pdf_active)
