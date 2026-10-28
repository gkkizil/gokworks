"""Chain-specific inputs/results within the existing FamilyPanel/GearWorkspace."""
from pathlib import Path
import json,os
from tempfile import TemporaryDirectory
from PySide6.QtCore import QSignalBlocker,Qt
from PySide6.QtWidgets import QComboBox,QHBoxLayout,QTableWidgetItem,QFileDialog,QMessageBox,QAbstractSpinBox
from gui_qt.components import button,label,Disclosure
from ..families.ui import FamilyPanel
from .. import service
from ..models import LoadSpecification
from ..serialization import to_dict,from_dict
from .models import ChainSpecification,SprocketSpecification,SprocketPairSpecification
from .catalog import CHAINS
from .calculation import calculate
from .view import SprocketCanvas


class SprocketPanel(FamilyPanel):
    def __init__(self,owner):
        definitions=[('pitch_mm','Zincir adımı p · mm',12.7,.001,100),
            ('roller_diameter_mm','Makara çapı dᵣ · mm',8.51,.001,100),('inner_width_mm','Zincir iç genişliği b₁ · mm',7.75,.001,100),
            ('teeth1','Tahrik diş sayısı z₁',20,9,120),('teeth2','Tahrik edilen z₂',40,9,120),
            ('width1_mm','Tahrik diş genişliği · mm',7,.5,25),('width2_mm','İkinci diş genişliği · mm',7,.5,25),
            ('bore1_mm','Tahrik deliği · mm',10,0,3000),('bore2_mm','İkinci delik · mm',15,0,3000),
            ('hub1_diameter_mm','Tahrik göbek çapı · mm',0,0,3000),('hub1_length_mm','Göbek toplam boyu · mm',0,0,500),
            ('hub2_diameter_mm','İkinci göbek çapı · mm',0,0,3000),('hub2_length_mm','İkinci göbek boyu · mm',0,0,500),
            ('center_distance_mm','Eksen mesafesi C · mm',300,.001,10000),('link_count','Zincir bakla sayısı',78,4,2000),
            ('input_rpm','Giriş devri n₁ · dev/dak',1500,-100000,100000),('power_kw','Güç P · kW',1.5,.0001,1e7),
            ('torque_nm','Tork T₁ · N·m',10,.0001,1e7)]
        super().__init__(owner,definitions,SprocketCanvas);self.kind='chain_sprocket'
        self.standard=QComboBox();self.standard.addItem('ISO 606 · B serisi','ISO 606:2015')
        self.series=QComboBox()
        for key in CHAINS:self.series.addItem(key,key)
        self.form.insertRow(0,'Zincir standardı',self.standard);self.form.insertRow(1,'Zincir numarası',self.series)
        self.mounting=QComboBox();self.mounting.addItem('Eksen mesafesi → bakla','center');self.mounting.addItem('Bakla → eksen mesafesi','links')
        self.form.insertRow(self.form.rowCount()-2,'Montaj girdisi',self.mounting)
        for key in ('pitch_mm','roller_diameter_mm','inner_width_mm'):
            self.fields[key].setReadOnly(True);self.fields[key].setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.base.setText('Makara yerleşimi');self.base.setToolTip('Yalnız sıfır konumunda statik yerleşim; gerçek zincir hareketi değildir.');self.base.setChecked(True)
        self.selection.addItem('Tahrik · z₁',0);self.selection.addItem('Tahrik edilen · z₂',1)
        self.target.setItemText(0,'Tahrik dişlisi · kendi merkezi');self.target.setItemText(1,'Tahrik edilen · kendi merkezi')
        self.target.setItemText(2,'İki dişli · zincir dahil değil')
        self.target.setCurrentIndex(2)
        self.construction.setText('DXF bölüm daireleri / makara merkezleri');self.construction.setToolTip('Yardımcı geometriler ayrı katmanlardadır.')
        self.dxf_button.setToolTip('Daire yaylı kapalı dişli konturu; göbek yan görünüşü içermez.')
        self.scope_note.setText('CAD: yalnız zincir dişlileri. Yan pah/rölyef ve üretim toleransları modellenmez; imalat/ömür/dayanım onayı verilmez.')
        self.details_label=label('','muted');self.details=Disclosure('Hesap kapsamı',self.details_label)
        self.results_panel.layout().insertWidget(3,self.details)
        self.explanation.setText('Göbek isteğe bağlı: çap/boy birlikte 0 veya birlikte girilmeli. Boy, diş genişliği dahil toplam uzunluktur. Katalog ölçüleri salt okunur.')
        self.standard.setAccessibleName('Zincir standardı');self.series.setAccessibleName('Zincir serisi');self.mounting.setAccessibleName('Zincir montaj girdisi')
        self.series.currentIndexChanged.connect(self.apply_catalog);self.mounting.currentIndexChanged.connect(self.changed)
        self.materials=(None,None);self.load_extras=(1.,10000.)
        row=QHBoxLayout();row.addWidget(button('JSON aç',self.open_json));row.addWidget(button('JSON kaydet',self.save_json))
        box=self.input_panel.layout();box.insertLayout(box.count()-1,row)

    def set_kind(self,kind):
        if kind!='chain_sprocket':raise ValueError('Zincir panelinde farklı tür açılamaz.')
        self.calculate()

    def apply_catalog(self):
        c=CHAINS[self.series.currentData()]
        for key in ('pitch_mm','roller_diameter_mm','inner_width_mm'):
            with QSignalBlocker(self.fields[key]):self.fields[key].setValue(getattr(c,key))
        self.changed()

    def specification(self):
        v={k:w.value() for k,w in self.fields.items()}
        chain=ChainSpecification(standard=self.standard.currentData(),series=self.series.currentData(),
            **{k:v[k] for k in ('pitch_mm','roller_diameter_mm','inner_width_mm')})
        wheels=[SprocketSpecification(chain=chain,teeth=v[f'teeth{i}'],width_mm=v[f'width{i}_mm'],bore_mm=v[f'bore{i}_mm'],
            hub_diameter_mm=v[f'hub{i}_diameter_mm'],hub_length_mm=v[f'hub{i}_length_mm'],material=self.materials[i-1]) for i in (1,2)]
        power=self.load_mode.currentData()=='power'
        load=LoadSpecification(mode=self.load_mode.currentData(),input_rpm=v['input_rpm'],power_kw=v['power_kw'] if power else None,
            torque_nm=None if power else v['torque_nm'],application_factor=self.load_extras[0],design_life_hours=self.load_extras[1])
        center=self.mounting.currentData()=='center'
        return SprocketPairSpecification(*wheels,mounting_mode=self.mounting.currentData(),
            center_distance_mm=v['center_distance_mm'] if center else None,link_count=None if center else v['link_count'],load=load)

    def calculate(self):
        if self.owner.busy:return
        from ..ui import number
        self.timer.stop();self.canvas.pause();power=self.load_mode.currentData()=='power';center=self.mounting.currentData()=='center'
        self.load_form.setRowVisible(self.fields['power_kw'],power);self.load_form.setRowVisible(self.fields['torque_nm'],not power)
        self.form.setRowVisible(self.fields['center_distance_mm'],center);self.form.setRowVisible(self.fields['link_count'],not center)
        try:
            s=self.specification();r=calculate(s)
            if self.spec!=s:
                self.canvas.set_spec(s)
                if self.mesh_view:self.mesh_view.set_mesh(None)
                self.preview_hint.setText('3D: STEP ile aynı gerçek katı; zincir dahil değildir.')
            self.spec=s;self.result=r
            self.summary.setText(f'i = {number(r.ratio)} · C ≈ {r.corrected_center_mm:.2f} mm'.replace('.',','))
            self.derived_load.setText(f'Hesaplanan T₁ = {number(r.input_torque_nm)} N·m' if power else f'Hesaplanan P = {number(r.power_kw)} kW')
            self.table.setRowCount(len(r.values)+1);self.table.setItem(0,0,QTableWidgetItem('Seçili parça'))
            self.table.setItem(0,1,QTableWidgetItem(self.selection.currentText().split(' · ')[0]))
            titles={'P':'Giriş gücü P','n₁':'Giriş devri n₁','T₁':'Giriş torku T₁','p':'Zincir adımı p','dᵣ':'Makara çapı dᵣ',
                'b₁':'Zincir iç genişliği b₁','i':'Çevrim oranı i','n₂':'Çıkış devri n₂','T₂ ideal':'İdeal çıkış torku T₂',
                'Dp₁':'Tahrik bölüm çapı Dp₁','Dp₂':'İkinci bölüm çapı Dp₂','rᵢ':'Makara oturma radyüsü rᵢ','v ortalama':'Ortalama zincir hızı',
                'Rp₁':'Tahrik bölüm yarıçapı Rp₁','Rp₂':'İkinci bölüm yarıçapı Rp₂','θ₁':'Tahrik açısal diş adımı θ₁','θ₂':'İkinci açısal diş adımı θ₂',
                'Ft etkin':'Nominal etkin zincir kuvveti'}
            for j,(key,value,unit) in enumerate(r.values,1):
                title=titles.get(key,key)+(' · '+unit if unit else '');item=QTableWidgetItem(title);item.setToolTip(title)
                self.table.setItem(j,0,item);cell=QTableWidgetItem(number(value));cell.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);self.table.setItem(j,1,cell)
            self.warnings.setText('\n'.join((r.warnings[0],*r.warnings[4:])))
            self.details_label.setText('\n'.join(r.warnings));self.plot_stack.setCurrentIndex(0)
            self.owner.set_status('Zincir dişlisi hesabı güncellendi; montaj mesafesi yaklaşık çözümdür.')
        except (ValueError,TypeError) as e:
            self.spec=None;self.result=None;self.canvas.set_spec(None);self.table.setRowCount(0);self.summary.setText('—');self.derived_load.setText('—')
            if self.mesh_view:self.mesh_view.set_mesh(None)
            self.empty.setText('Geçerli zincir ve montaj parametreleriyle yeniden hesaplayın.');self.plot_stack.setCurrentIndex(1)
            self.details_label.setText('')
            self.warnings.setText(str(e));self.owner.set_status(str(e),True)
        self.enable();self.speed_changed()

    def enable(self):
        super().enable();valid=self.result is not None and not self.owner.busy
        self.construction.setEnabled(valid);self.base.setEnabled(valid)

    def speed_changed(self):
        super().speed_changed()
        if self.result:self.motion_caption.setText(self.motion_caption.text()+' · aynı yön · ortalama kinematik')

    def save_path(self,caption,suggested,filter_text):
        path,_=QFileDialog.getSaveFileName(self,caption,suggested,filter_text,options=QFileDialog.DontConfirmOverwrite)
        if not path:return None
        exists=Path(path).exists()
        if exists and QMessageBox.question(self,'Dosyayı değiştir',f'Mevcut dosya değiştirilsin mi?\n{path}',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return None
        return path,exists

    def dialog(self,mode):
        self.calculate()
        if not self.result:return
        selected=self.save_path('Zincir dişlisi CAD kaydet','chain_sprocket.'+mode,'STEP (*.step)' if mode=='step' else 'DXF (*.dxf)')
        if selected:self.run(mode,selected[0],overwrite=selected[1])

    def run(self,mode,path=None,target=None,*,overwrite=False):
        self.calculate()
        if not self.result or not self.owner.can_start():return False
        if path is not None and Path(path).exists() and not overwrite:
            self.owner.set_status('Mevcut dosya korunuyor; değiştirmek için kaydetme diyaloğunda onay verin.',True);return False
        self.canvas.pause();s=self.spec;target=target or self.target.currentData();construction=self.construction.isChecked()
        self.owner.set_status('Zincir profili / yerel CAD işlemi sürüyor…');self.owner.progressChanged.emit(-1,0)
        def operation(sink,stop):
            try:sink.put(('family_result',(mode,s,service.execute(s,mode,target=target,path=path,construction=construction,overwrite=overwrite,stop=stop))))
            except service.OperationCancelled as e:sink.put(('family_cancelled',str(e)))
        return self.owner.jobs.start(self.owner,operation)

    def handle(self,events):
        remaining=[]
        for kind,payload in events:
            if kind=='family_result' and payload[0]=='check':
                if payload[1]!=self.spec:continue
                if self.isVisible():
                    if self.compact_mode:self.compact_tabs.setCurrentIndex(1)
                    self.views.setCurrentIndex(0);self.canvas.play()
                    self.owner.set_status('Profil/makara taraması geçti; ortalama dişli kinematiği başladı. Zincir hareketi simüle edilmez.')
            else:remaining.append((kind,payload))
        super().handle(remaining)
        if self.mesh_view:self.mesh_view.setAccessibleName('Zincir dişlileri · yerel B-Rep katısı 3D görünüm')

    def restore(self,s):
        if not isinstance(s,SprocketPairSpecification):raise ValueError('Bu ekranda zincir dişlisi JSON kaydı açın.')
        calculate(s);v={k:getattr(s.driver.chain,k) for k in ('pitch_mm','roller_diameter_mm','inner_width_mm')}
        for i,wheel in enumerate((s.driver,s.driven),1):
            v.update({f'teeth{i}':wheel.teeth,f'width{i}_mm':wheel.width_mm,f'bore{i}_mm':wheel.bore_mm,
                f'hub{i}_diameter_mm':wheel.hub_diameter_mm,f'hub{i}_length_mm':wheel.hub_length_mm})
        v.update(input_rpm=s.load.input_rpm,center_distance_mm=s.center_distance_mm or self.fields['center_distance_mm'].value(),
            link_count=s.link_count or self.fields['link_count'].value())
        if s.load.power_kw is not None:v['power_kw']=s.load.power_kw
        if s.load.torque_nm is not None:v['torque_nm']=s.load.torque_nm
        for combo,value in ((self.series,s.driver.chain.series),(self.mounting,s.mounting_mode),(self.load_mode,s.load.mode)):
            with QSignalBlocker(combo):combo.setCurrentIndex(combo.findData(value))
        for k,value in v.items():
            with QSignalBlocker(self.fields[k]):self.fields[k].setValue(value)
        self.materials=(s.driver.material,s.driven.material);self.load_extras=(s.load.application_factor,s.load.design_life_hours)
        self.calculate()

    def open_json(self):
        path,_=QFileDialog.getOpenFileName(self,'Zincir projesi aç','','JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>32000:raise ValueError('Zincir JSON dosyası 32 kB sınırını aşıyor.')
            self.restore(from_dict(json.loads(Path(path).read_text(encoding='utf-8'))))
        except (ValueError,TypeError,OSError) as e:self.owner.set_status(str(e),True)

    def save_json(self):
        self.calculate()
        if not self.result:return
        selected=self.save_path('Zincir projesi kaydet','chain_sprocket.json','JSON (*.json)')
        if not selected:return
        path=Path(selected[0])
        try:
            with TemporaryDirectory(prefix='.gokworks-sprocket-json-',dir=path.parent) as folder:
                p=Path(folder)/path.name;p.write_text(json.dumps(to_dict(self.spec),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                if selected[1]:os.replace(p,path)
                else:os.link(p,path)
            self.owner.set_status('Zincir projesi JSON olarak kaydedildi.')
        except (ValueError,OSError) as e:self.owner.set_status(str(e),True)
