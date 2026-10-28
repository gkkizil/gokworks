"""Turkish Qt workbench. Basic math is synchronous; CAD runs in a bounded process."""

from PySide6.QtCore import Qt,QTimer,QSignalBlocker
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QDoubleSpinBox,
    QSpinBox,QCheckBox,QTabWidget,QStackedWidget,QTableWidget,QTableWidgetItem,
    QHeaderView,QFileDialog,QAbstractItemView)
from gui_qt.components import BasePage,button,label,scroll
from .models import GearSpecification,GearPairSpecification,LoadSpecification
from .calculation import calculate_pair
from .validation import require_manufacturable
from .view import GearCanvas
from .workspace import GearWorkspace
from . import service


def number(value):
    if value and (abs(value)<.0001 or abs(value)>=1e9):
        return f'{value:.8g}'.replace('.',',')
    return f'{value:,.4f}'.replace(',',' ').replace('.',',').rstrip('0').rstrip(',')


class GearPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Dişli Hesaplama','Dişli türleri · Hesap, hareket ve CAD · türe göre doğrulama kapsamı')
        self.family_panel=None
        self.specification=None;self.result=None;self.selected=0;self.mesh_view=None;self.last_export=None
        self._geometry_key=None;self._mesh_key=None;self._pending=None
        self.update_button=self.action('Hesapla / Güncelle',self.calculate,primary=True)
        self.stop_button=self.action('Durdur',self.jobs.cancel,locked=False)
        self.input_panel=QWidget();form_box=QVBoxLayout(self.input_panel);form_box.setContentsMargins(6,6,6,6)
        form_box.addWidget(label('GEOMETRİ','section'));self.form=QFormLayout();self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.fields={}
        self.type_picker=QComboBox();self.type_picker.addItem('Dış düz · Evolvent','external_spur')
        from .families.models import CATALOG
        for key,cap in CATALOG.items():self.type_picker.addItem(cap.title+(' · hesap' if not cap.geometry else ''),key)
        self.type_picker.setAccessibleName('Dişli tipi');self.layout.addWidget(self.type_picker)
        for key,title,value,low,high,integer in (
            ('module_mm','Modül m · mm',2.,.1,20.,False),('z1','Pinyon diş sayısı z₁',20,6,300,True),
            ('z2','Çark diş sayısı z₂',40,6,300,True),('pressure_angle_deg','Basınç açısı α · °',20.,14.5,30.,False),
            ('face_width_mm','Diş genişliği b · mm',15.,.1,500.,False),
            ('bore1','Pinyon delik çapı · mm',8.,0,5999.,False),('bore2','Çark delik çapı · mm',12.,0,5999.,False)):
            self.add_number(self.form,key,title,value,low,high,integer)
        form_box.addLayout(self.form)
        form_box.addWidget(label('İŞLETME DEĞERLERİ','section'));load=QFormLayout();load.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.load_form=load
        self.load_mode=QComboBox();self.load_mode.addItem('Güç P → Tork hesaplanır','power');self.load_mode.addItem('Tork T₁ → Güç hesaplanır','torque')
        self.load_mode.setAccessibleName('Birincil yük girdisi');load.addRow('Birincil yük',self.load_mode)
        for key,title,value,low,high in (('input_rpm','Giriş devri n₁ · dev/dak',1500.,-100000.,100000.),
                                        ('power_kw','Giriş gücü P · kW',1.5,.0001,1e7),('torque_nm','Giriş torku T₁ · N·m',9.5493,.0001,1e7)):
            self.add_number(load,key,title,value,low,high)
        form_box.addLayout(load)
        self.derived_load=label('','muted');self.derived_load.setAccessibleName('Hesaplanan ikincil yük değeri')
        form_box.addWidget(self.derived_load)
        form_box.addWidget(label('Varsayımlar: x₁=x₂=0 · hₐ*=1 · h𝒻*=1,25 · β=0° · sıfır diş boşluğu · paralel miller.','muted'))
        form_box.addWidget(label('K_A ve tasarım ömrü veri modelinde ayrılmıştır; bu sürümde mukavemet hesabına uygulanmaz.','muted'))
        form_box.addStretch();self.input_scroll=scroll(self.input_panel);self.input_scroll.setMinimumWidth(250)
        self.viewer_panel=QWidget();viewer=QVBoxLayout(self.viewer_panel);viewer.setContentsMargins(0,0,0,0);viewer.setSpacing(4)
        row=QHBoxLayout();self.play_button=button('Başlat',self.toggle_animation)
        self.reset_button=button('Sıfırla',lambda:self.canvas.reset());self.fit_button=button('Sığdır',self.fit_view)
        self.speed=QComboBox();self.speed.setAccessibleName('Animasyon gerçek devir ölçeği')
        for text,value in (('%0,2',.002),('%1',.01),('%2',.02),('%10',.1),('%100',1.)):
            self.speed.addItem(text,value)
        self.speed.setCurrentIndex(2)
        for w in (self.play_button,self.reset_button,self.fit_button):row.addWidget(w)
        row.addWidget(label('Hız','muted',wrap=False));row.addWidget(self.speed);row.addStretch();viewer.addLayout(row)
        row2=QHBoxLayout();self.pitch=QCheckBox('Bölüm daireleri');self.pitch.setChecked(True)
        self.base=QCheckBox('Temel daireler');self.selection=QComboBox()
        self.selection.addItem('Pinyon · z₁',0);self.selection.addItem('Çark · z₂',1);self.selection.setAccessibleName('Seçili dişli')
        row2.addWidget(self.pitch);row2.addWidget(self.base);row2.addWidget(self.selection);row2.addStretch();viewer.addLayout(row2)
        self.views=QTabWidget();self.canvas=GearCanvas(context.appearance);self.views.addTab(self.canvas,'2D · Hareket')
        self.three_d=QWidget();self.three_d_layout=QVBoxLayout(self.three_d)
        self.preview_button=button('Gerçek katıdan 3D önizleme oluştur',self.build_preview)
        self.three_d_layout.addWidget(self.preview_button)
        self.preview_hint=label('3D önizleme STEP ile aynı B-Rep katıdan üretilir.','muted');self.three_d_layout.addWidget(self.preview_hint)
        self.three_d_layout.addStretch();self.views.addTab(self.three_d,'3D · Katı');viewer.addWidget(self.views,1)
        self.motion_caption=label('','muted');viewer.addWidget(self.motion_caption)
        self.results_panel=QWidget();results=QVBoxLayout(self.results_panel);results.setContentsMargins(6,6,6,6)
        self.summary=label('','result');results.addWidget(self.summary)
        self.result_table=QTableWidget(0,2);self.result_table.setHorizontalHeaderLabels(['Büyüklük','Değer'])
        self.result_table.verticalHeader().hide();self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True);self.result_table.setAccessibleName('Dişli mühendislik sonuçları')
        self.result_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.result_table.setMinimumHeight(220);results.addWidget(self.result_table,1)
        self.warning_label=label('','muted');results.addWidget(self.warning_label)
        results.addWidget(label('CAD AKTARIMI','section'));self.export_target=QComboBox()
        for title,key in (('Pinyon · kendi merkezi','pinion'),('Çark · kendi merkezi','wheel'),('Dişli takımı · 2 ayrı gövde','pair')):
            self.export_target.addItem(title,key)
        self.export_target.setCurrentIndex(2);self.export_target.setAccessibleName('CAD aktarım hedefi');results.addWidget(self.export_target)
        self.construction=QCheckBox('DXF yardımcı dairelerini ekle');self.construction.setChecked(True);results.addWidget(self.construction)
        exports=QHBoxLayout();self.dxf_button=button('DXF kaydet',lambda:self.export_dialog('dxf'))
        self.step_button=button('STEP kaydet',lambda:self.export_dialog('step'))
        exports.addWidget(self.dxf_button);exports.addWidget(self.step_button);results.addLayout(exports)
        results.addWidget(label('Dip: temel daire altında radyal düz geçiş; gerçek trokoid/azdırma dip radyüsü değildir. '
            'ISO 6336/AGMA mukavemet, verim ve yük altında deformasyon hesabı yapılmaz.','muted'))
        self.results_scroll=scroll(self.results_panel);self.results_scroll.setMinimumWidth(250)
        self.body=GearWorkspace(self.input_scroll,self.viewer_panel,self.results_scroll)
        self.splitter=self.body.splitter;self.compact_tabs=self.body.compact_tabs
        self.family_stack=QStackedWidget();self.family_stack.addWidget(self.body)
        self.layout.addWidget(self.family_stack,1);self.finish_layout()
        self.type_picker.currentIndexChanged.connect(self.family_changed)
        self.controls.extend([self.input_panel,self.dxf_button,self.step_button,self.preview_button,self.play_button,self.export_target])
        self.update_timer=QTimer(self);self.update_timer.setSingleShot(True);self.update_timer.setInterval(180)
        self.update_timer.timeout.connect(self.calculate)
        for control in self.fields.values():control.valueChanged.connect(self.changed)
        self.load_mode.currentIndexChanged.connect(self.changed)
        self.pitch.toggled.connect(self.helpers);self.base.toggled.connect(self.helpers)
        self.speed.currentIndexChanged.connect(self.speed_changed);self.selection.currentIndexChanged.connect(self.selected_changed)
        self.canvas.gearSelected.connect(self.select_gear)
        self.canvas.runningChanged.connect(lambda running:self.play_button.setText('Duraklat' if running else 'Başlat'))
        self.calculate()

    def family_changed(self):
        self.canvas.pause();self.update_timer.stop()
        kind=self.type_picker.currentData()
        if kind=='external_spur':
            if self.family_panel:self.family_panel.canvas.pause();self.family_panel.timer.stop()
            self.family_stack.setCurrentWidget(self.body);self.calculate();return
        if self.family_panel is None:
            from .families.ui import FamilyPanel
            self.family_panel=FamilyPanel(self);self.family_stack.addWidget(self.family_panel);self.controls.append(self.family_panel)
        self.family_stack.setCurrentWidget(self.family_panel);self.family_panel.set_kind(kind)

    def family_active(self):
        return self.family_panel is not None and self.type_picker.currentData()!='external_spur'

    def add_number(self,form,key,title,value,low,high,integer=False):
        w=QSpinBox() if integer else QDoubleSpinBox()
        if not integer:w.setDecimals(4)
        w.setRange(low,high);w.setValue(value);w.setKeyboardTracking(False);w.setAccessibleName(title)
        w.setMinimumWidth(90);self.fields[key]=w;form.addRow(title,w)

    def changed(self,*args):
        # Clear exports immediately: a debounce must never export the previous values.
        self.canvas.pause();self.result=None;self.enable_exports(False);self.update_timer.start()
        self.sync_load_fields();self.derived_load.setText('Hesap güncelleniyor…')

    def sync_load_fields(self):
        power=self.load_mode.currentData()=='power'
        self.fields['power_kw'].setEnabled(power);self.fields['torque_nm'].setEnabled(not power)
        self.load_form.setRowVisible(self.fields['power_kw'],power)
        self.load_form.setRowVisible(self.fields['torque_nm'],not power)

    def specification_from_fields(self):
        v={key:w.value() for key,w in self.fields.items()}
        common=dict(module_mm=v['module_mm'],pressure_angle_deg=v['pressure_angle_deg'],face_width_mm=v['face_width_mm'])
        load=LoadSpecification(mode=self.load_mode.currentData(),input_rpm=v['input_rpm'],
            power_kw=v['power_kw'] if self.load_mode.currentData()=='power' else None,
            torque_nm=v['torque_nm'] if self.load_mode.currentData()=='torque' else None)
        return GearPairSpecification(GearSpecification(teeth=v['z1'],bore_mm=v['bore1'],**common),
                                     GearSpecification(teeth=v['z2'],bore_mm=v['bore2'],**common),load)

    def calculate(self):
        if self.family_active():self.family_panel.calculate();return
        if self.busy:return
        self.update_timer.stop();self.canvas.pause()
        power=self.load_mode.currentData()=='power'
        self.sync_load_fields()
        try:
            spec=self.specification_from_fields();result=calculate_pair(spec)
            key=(spec.pinion,spec.wheel)
            if key!=self._geometry_key:
                self.canvas.set_specification(spec);self._geometry_key=key;self._mesh_key=None
                if self.mesh_view:self.mesh_view.set_mesh(None)
                self.preview_hint.setText('3D önizleme için güncel katıyı oluşturun.')
            else:self.canvas.specification=spec
            self.specification=spec;self.result=result
            # Derived values may lie outside the primary input's UI limits.
            # Display the true result without clamping it or overwriting the
            # user's saved alternative primary input.
            self.derived_load.setText(
                f'Hesaplanan T₁ = {number(result.input_torque_nm)} N·m' if power else
                f'Hesaplanan P = {number(result.power_kw)} kW')
            self.show_results()
            self.warning_label.setText('\n'.join(i.message for i in result.warnings) or 'Geometrik temel kontroller uygun. Mukavemet doğrulaması yapılmadı.')
            self.enable_exports(True);self.set_status('Hesap ve evolvent geometri güncellendi.')
        except (ValueError,TypeError) as error:
            self.result=None;self.specification=None;self._geometry_key=None;self._mesh_key=None
            self.canvas.set_specification(None);self.result_table.setRowCount(0);self.summary.setText('—')
            if self.mesh_view:self.mesh_view.set_mesh(None)
            self.preview_hint.setText('Geçerli parametrelerle yeniden hesaplayın.')
            self.derived_load.setText('—')
            self.warning_label.setText(str(error));self.enable_exports(False);self.set_status(str(error),True)
        self.speed_changed()

    def enable_exports(self,valid):
        if valid and self.result is not None:
            try:require_manufacturable(self.result)
            except ValueError:valid=False
        for w in (self.dxf_button,self.step_button,self.play_button,self.preview_button):w.setEnabled(valid and not self.busy)

    def show_results(self):
        if self.result is None:return
        r=self.result;g=r.pinion if self.selected==0 else r.wheel
        self.summary.setText(f'i = {number(r.ratio)} · a = {number(r.center_distance_mm)} mm')
        rows=[('Seçili dişli','Pinyon' if self.selected==0 else 'Çark'),
            ('Bölüm dairesi d · mm',g.pitch_diameter_mm),('Diş üstü dairesi dₐ · mm',g.outside_diameter_mm),
            ('Diş dibi dairesi d𝒻 · mm',g.root_diameter_mm),('Temel daire dᵦ · mm',g.base_diameter_mm),
            ('Bölüm yarıçapı r · mm',g.pitch_radius_mm),('Temel yarıçap rᵦ · mm',g.base_radius_mm),
            ('Diş üstü yarıçapı rₐ · mm',g.outside_radius_mm),('Diş dibi yarıçapı r𝒻 · mm',g.root_radius_mm),
            ('Baş yüksekliği hₐ · mm',g.addendum_mm),('Dip yüksekliği h𝒻 · mm',g.dedendum_mm),
            ('Toplam yükseklik h · mm',g.whole_depth_mm),('Dip boşluğu c · mm',g.clearance_mm),
            ('Dairesel adım p · mm',g.circular_pitch_mm),('Temel adım pᵦ · mm',g.base_pitch_mm),('Diş kalınlığı s · mm',g.tooth_thickness_mm),
            ('Çalışma eksen mesafesi aᵥ · mm',r.working_center_distance_mm),('Çıkış devri n₂ · dev/dak',r.output_rpm),
            ('Giriş gücü P · kW',r.power_kw),('Giriş torku T₁ · N·m',r.input_torque_nm),
            ('İdeal çıkış torku T₂ · N·m',r.output_torque_nm),('Çevresel kuvvet Fₜ · N',r.tangential_force_n),
            ('Radyal kuvvet Fᵣ · N',r.radial_force_n),('Yaklaşma yolu · mm',r.approach_length_mm),
            ('Uzaklaşma yolu · mm',r.recess_length_mm),('Temas yolu · mm',r.path_of_contact_mm),('Kavrama oranı εα',r.transverse_contact_ratio)]
        self.result_table.setRowCount(len(rows))
        for i,(title,value) in enumerate(rows):
            self.result_table.setItem(i,0,QTableWidgetItem(title))
            cell=QTableWidgetItem(value if isinstance(value,str) else number(value));cell.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.result_table.setItem(i,1,cell)

    def select_gear(self,index):
        self.selected=index
        with QSignalBlocker(self.selection):self.selection.setCurrentIndex(index)
        self.canvas.select(index);self.show_results()
        self.export_target.setCurrentIndex(index)

    def selected_changed(self):
        self.select_gear(self.selection.currentData())

    def helpers(self):self.canvas.set_helpers(self.pitch.isChecked(),self.base.isChecked())

    def speed_changed(self):
        self.canvas.speed_scale=self.speed.currentData()
        if self.result:
            n=self.specification.load.input_rpm
            self.motion_caption.setText(f'n₁ = {number(n)} / n₂ = {number(self.result.output_rpm)} dev/dak · ters yön · '
                f'görsel hız: {self.speed.currentText()}')
        else:self.motion_caption.setText('Geçerli parametrelerle hesaplayın.')

    def fit_view(self):
        if self.views.currentIndex()==0:self.canvas.fit()
        elif self.mesh_view:self.mesh_view.fit()

    def toggle_animation(self):
        if self.family_active():self.family_panel.toggle();return
        if self.canvas.timer.isActive():self.canvas.pause();return
        if self.result is None or not self.can_start():return
        self.views.setCurrentIndex(0)
        self.run_job('check','pair',None)

    def build_preview(self):
        if self.family_active():return self.family_panel.run('mesh')
        if self.result is None or not self.can_start():return
        if self._mesh_key==self.specification and self.mesh_view:
            self.views.setCurrentIndex(1);return
        self.run_job('mesh','pair',None)

    def export_dialog(self,mode):
        if self.family_active():self.family_panel.dialog(mode);return
        if self.result is None or not self.can_start():return
        target=self.export_target.currentData()
        path,_=QFileDialog.getSaveFileName(self,'Dişli CAD dosyasını kaydet',f'disli_{target}.{mode}',
            'DXF (*.dxf)' if mode=='dxf' else 'STEP (*.step *.stp)')
        if path:self.start_export(mode,path,target)

    def start_export(self,mode,path,target=None):
        if self.family_active():return self.family_panel.run(mode,path,target)
        # Public UI command also flushes a pending input debounce.
        self.calculate()
        if self.result is None or not self.can_start():return False
        return self.run_job(mode,target or self.export_target.currentData(),path)

    def run_job(self,mode,target,path):
        self.canvas.pause();spec=self.specification;construction=self.construction.isChecked()
        self._pending=(mode,spec)
        self.set_status('Kavraşma kontrolü / yerel CAD işlemi sürüyor…');self.progressChanged.emit(-1,0)
        def operation(sink,stop):
            try:
                value=service.execute(spec,mode,target=target,path=path,construction=construction,overwrite=True,stop=stop)
                sink.put(('gear_result',(mode,spec,value)))
            except service.OperationCancelled as error:sink.put(('gear_cancelled',str(error)))
        return self.jobs.start(self,operation)

    def handle_events(self,events):
        super().handle_events(events)
        if self.family_panel:self.family_panel.handle(events)
        for kind,value in events:
            if kind=='gear_cancelled':self.set_status(value)
            elif kind=='gear_result':
                mode,spec,result=value
                if spec!=self.specification:return
                if mode=='check':
                    self.canvas.play();self.set_status(f"Kavraşma {result['samples']} konumda kontrol edildi; rijit hareket başladı.")
                elif mode=='mesh':
                    if self.mesh_view is None:
                        from modules.dxf_dwg.preview.viewer import MeshView
                        self.mesh_view=MeshView();self.mesh_view.setAccessibleName('Dişli takımı · gerçek CAD katısı 3D görünüm')
                        self.three_d_layout.insertWidget(2,self.mesh_view,1)
                    self.mesh_view.set_mesh(result['mesh']);self._mesh_key=spec
                    self.preview_hint.setText(f"{result['solids']} ayrı katı · hacim {number(result['volume_mm3'])} mm³ · statik CAD önizleme")
                    self.views.setCurrentIndex(1);self.set_status('Gerçek B-Rep katıdan 3D önizleme hazır.')
                else:
                    self.last_export=result;self.set_status(f"{mode.upper()} kaydedildi ve tekrar okunarak doğrulandı: {result['path']}")

    def set_busy(self,busy):
        super().set_busy(busy)
        self.type_picker.setEnabled(not busy)
        if self.family_panel:self.family_panel.enable()
        if not busy:self.enable_exports(self.result is not None)

    @property
    def compact_mode(self):
        return hasattr(self,'body') and self.body.compact_mode

    def theme_changed(self):
        super().theme_changed()
        self.canvas.theme_changed(self.context.appearance)
        if self.family_panel:self.family_panel.canvas.set_spec(self.family_panel.spec if self.family_panel.result and self.family_panel.result.cad_available else None)

    def hideEvent(self,event):
        self.canvas.pause()
        if self.family_panel:
            self.family_panel.canvas.pause()
            if self.family_panel.mesh_view:self.family_panel.mesh_view.cancel_render()
        if self.mesh_view:self.mesh_view.cancel_render()
        super().hideEvent(event)
