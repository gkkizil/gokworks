"""Mechanism workbench using the existing window's cancellable job owner."""
from math import cos,sin,pi,degrees
from PySide6.QtCore import Qt,QTimer,QElapsedTimer,QRectF
from PySide6.QtGui import QPainterPath,QPen,QColor,QBrush,QPainter
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QDoubleSpinBox,QSpinBox,
    QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTabWidget,
    QGraphicsView,QGraphicsScene,QGraphicsPathItem)
from gui_qt.components import label,button,scroll
from gui_qt.theme import COLORS
from ..models import LoadSpecification
from .. import service
from .models import MechanismSpecification,CATALOG
from .calculation import calculate
from .geometry import sections,poses


def path_for(sec):
    result=QPainterPath()
    for segments in (sec.outer,sec.inner):
        if not segments:continue
        result.moveTo(*segments[0].point(0))
        for seg in segments:
            if seg.kind=='arc':
                r=seg.radius;result.arcTo(QRectF(-r,-r,2*r,2*r),-degrees(seg.start_angle),-degrees(seg.end_angle-seg.start_angle))
            elif seg.kind=='line':result.lineTo(*seg.controls[-1])
            else:result.cubicTo(*(v for p in seg.controls[1:] for v in p))
        result.closeSubpath()
    if sec.bore:result.addEllipse(QRectF(-sec.bore/2,-sec.bore/2,sec.bore,sec.bore))
    result.setFillRule(Qt.OddEvenFill);return result


class MechanismCanvas(QGraphicsView):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing);self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse);self.setMinimumSize(200,220)
        self.spec=None;self.items=[];self.angle=0.;self.timer=QTimer(self);self.timer.setInterval(16)
        self.clock=QElapsedTimer();self.timer.timeout.connect(self.tick)
        self.setAccessibleName('Dişli mekanizması · 2D kinematik')

    def set_spec(self,spec):
        self.pause();self.spec=spec;self.angle=0;self.scene().clear();self.items=[]
        c=COLORS[self.owner.context.appearance];self.setBackgroundBrush(QColor(c['canvas']))
        if spec is None:return
        profiles=sections(spec)
        for k,(idx,angle,x,y) in enumerate(poses(spec)):
            item=QGraphicsPathItem(path_for(profiles[idx]));pen=QPen(QColor(c['accent'] if idx!=2 else c['warning']));pen.setCosmetic(True)
            item.setPen(pen);fill=QColor(c['accent'] if idx!=2 else c['warning']);fill.setAlpha(40);item.setBrush(QBrush(fill))
            self.scene().addItem(item);self.items.append(item)
        if spec.kind=='cycloidal':
            R=spec.module_mm*spec.teeth2/2
            for j in range(spec.teeth2):
                x=R*cos(2*pi*j/spec.teeth2);y=R*sin(2*pi*j/spec.teeth2);r=spec.roller_radius_mm
                pen=QPen(QColor(c['warning']));pen.setCosmetic(True)
                self.scene().addEllipse(x-r,y-r,2*r,2*r,pen)
        self.update_pose();self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-5,-5,5,5));self.fit()

    def update_pose(self):
        if self.spec:
            angle=self.angle
            if self.spec.kind=='rack':angle=angle%(2*pi/self.spec.teeth1)
            for item,(_,a,x,y) in zip(self.items,poses(self.spec,angle)):
                item.setRotation(degrees(a));item.setPos(x,y)

    def play(self):self.clock.start();self.timer.start()
    def pause(self):self.timer.stop()
    def reset(self):self.pause();self.angle=0.;self.update_pose()
    def tick(self):
        self.angle+=self.spec.load.input_rpm*2*pi/60*self.clock.restart()/1000*self.owner.speed.currentData()
        self.update_pose()
    def fit(self):
        if self.items:self.resetTransform();self.fitInView(self.sceneRect(),Qt.KeepAspectRatio);self.scale(1,-1)
    def resizeEvent(self,event):super().resizeEvent(event);self.fit()
    def wheelEvent(self,event):
        factor=1.15**max(-4,min(4,event.angleDelta().y()/120));current=abs(self.transform().m11())
        if .01<=current*factor<=2000:self.scale(factor,factor)
        event.accept()
    def hideEvent(self,event):self.pause();super().hideEvent(event)


class FamilyPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.context=owner.context;self.spec=None;self.result=None;self.mesh_view=None;self.last_export=None
        self.kind='rack';self.saved={};self.fields={};layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        tabs=QTabWidget();layout.addWidget(tabs);input_box=QWidget();iv=QVBoxLayout(input_box)
        self.form=QFormLayout();iv.addLayout(self.form)
        definitions=[('module_mm','Modül m / mₙ / mₓ · mm',2,.1,20),('teeth1','Pinyon / güneş diş sayısı',20,6,300),
            ('teeth2','Çark / planet dişi / pim adedi',40,6,300),('pressure_angle_deg','Basınç açısı α / αₙ · °',20,14.5,30),
            ('width_mm','Genişlik b · mm',15,.1,500),('bore1_mm','İlk parça delik çapı · mm',8,0,5999),
            ('bore2_mm','İkinci parça delik çapı · mm',12,0,5999),('helix_deg','Helis açısı β · °',20,0,40),
            ('rack_teeth','Kremayer diş adedi',16,4,80),('rack_base_mm','Kremayer bölüm hattından tabana · mm',10,.1,1000),
            ('rim_mm','Halka dış radyal et · mm',5,.2,1000),('planets','Planet adedi',3,2,6),
            ('shaft_angle_deg','Miller arası açı Σ · °',90,20,160),('offset_mm','Hipoid ofset E · mm',10,.001,1000),
            ('worm_starts','Vida ağız sayısı',2,1,8),('diameter_quotient','Vida çap katsayısı q',10,4,30),
            ('eccentricity_mm','Eksantriklik e · mm',.5,.001,20),('roller_radius_mm','Pim yarıçapı · mm',1.5,.01,100),
            ('input_rpm','Giriş devri n₁ · dev/dak',1500,-100000,100000),('power_kw','Güç P · kW',1.5,.0001,1e7),
            ('torque_nm','Tork T₁ · N·m',10,.0001,1e7)]
        integer={'teeth1','teeth2','rack_teeth','planets','worm_starts'}
        for key,title,value,low,high in definitions:
            w=QSpinBox() if key in integer else QDoubleSpinBox()
            if key not in integer:w.setDecimals(4)
            w.setRange(low,high);w.setValue(value);w.setKeyboardTracking(False);w.setAccessibleName(title)
            self.fields[key]=w;self.form.addRow(title,w);w.valueChanged.connect(self.changed)
        self.load_mode=QComboBox();self.load_mode.addItem('Güç → Tork','power');self.load_mode.addItem('Tork → Güç','torque')
        self.form.addRow('Birincil yük',self.load_mode);self.load_mode.currentIndexChanged.connect(self.changed)
        self.explanation=label('','muted');iv.addWidget(self.explanation);iv.addStretch();tabs.addTab(scroll(input_box),'Parametreler')
        view=QWidget();v=QVBoxLayout(view);row=QHBoxLayout()
        self.play_button=button('Başlat / duraklat',self.toggle);self.speed=QComboBox()
        for title,value in (('%0,2',.002),('%1',.01),('%2',.02),('%10',.1)):self.speed.addItem(title,value)
        self.speed.setCurrentIndex(1);self.speed.setAccessibleName('Mekanizma görsel hız ölçeği')
        self.canvas=MechanismCanvas(self)
        for w in (self.play_button,button('Sıfırla',self.canvas.reset),button('Sığdır',self.canvas.fit),self.speed):row.addWidget(w)
        v.addLayout(row);v.addWidget(self.canvas,1);self.empty=label('');v.addWidget(self.empty);tabs.addTab(view,'2D · Hareket')
        self.preview=QWidget();self.preview_layout=QVBoxLayout(self.preview)
        self.preview_button=button('Gerçek katıdan 3D oluştur',lambda:self.run('mesh'))
        self.preview_layout.addWidget(self.preview_button);tabs.addTab(self.preview,'3D · Katı')
        results=QWidget();rv=QVBoxLayout(results);self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['Büyüklük','Değer / birim'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rv.addWidget(self.table,1);self.warnings=label('','muted');rv.addWidget(self.warnings)
        self.target=QComboBox();self.target.setAccessibleName('Mekanizma CAD hedefi')
        for title,key in (('İlk parça · kendi merkezi','pinion'),('İkinci parça / halka / pimler','wheel'),('Tam takım · ayrı katılar','pair')):self.target.addItem(title,key)
        self.target.setCurrentIndex(2);rv.addWidget(self.target)
        row=QHBoxLayout();self.step_button=button('STEP kaydet',lambda:self.dialog('step'));self.dxf_button=button('DXF alın kesiti kaydet',lambda:self.dialog('dxf'))
        row.addWidget(self.step_button);row.addWidget(self.dxf_button);rv.addLayout(row);tabs.addTab(results,'Sonuçlar / CAD')
        self.tabs=tabs;self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(200);self.timer.timeout.connect(self.calculate)

    def set_kind(self,kind):
        if self.spec is not None:self.calculate()  # Flush pending edits before saving this type.
        if self.spec:self.saved[self.kind]=self.spec
        self.canvas.pause();self.timer.stop();self.kind=kind
        s=self.saved.get(kind,MechanismSpecification(kind=kind,width_mm=10 if kind in ('bevel','spiral_bevel') else 15,
            teeth1=24 if kind=='internal' else 20,teeth2=72 if kind=='internal' else 12 if kind=='cycloidal' else 40))
        for key,w in self.fields.items():
            w.blockSignals(True)
            value=getattr(s.load,key,None) if key in ('input_rpm','power_kw','torque_nm') else getattr(s,key)
            if value is not None:w.setValue(value)
            w.blockSignals(False)
        self.load_mode.blockSignals(True);self.load_mode.setCurrentIndex(0 if s.load.mode=='power' else 1);self.load_mode.blockSignals(False)
        self.explanation.setText(CATALOG[kind].note)
        common={'module_mm','teeth1','teeth2','pressure_angle_deg','width_mm','bore1_mm','bore2_mm','input_rpm','power_kw','torque_nm'}
        extra={'rack':{'rack_teeth','rack_base_mm'},'helical':{'helix_deg'},'herringbone':{'helix_deg'},
            'internal':{'rim_mm'},'planetary':{'planets','rim_mm'},'bevel':{'shaft_angle_deg'},'spiral_bevel':{'shaft_angle_deg'},
            'hypoid':{'offset_mm'},'worm':{'worm_starts','diameter_quotient'},'cycloidal':{'eccentricity_mm','roller_radius_mm'}}
        hidden={'internal':{'bore2_mm'},'planetary':set(),'rack':{'teeth2','bore2_mm'},'cycloidal':{'teeth1','bore2_mm','pressure_angle_deg'},
                'hypoid':{'module_mm','pressure_angle_deg','width_mm','bore1_mm','bore2_mm'},
                'worm':{'teeth1','bore1_mm','bore2_mm','pressure_angle_deg','width_mm'},'bevel':{'bore1_mm','bore2_mm','pressure_angle_deg'},'spiral_bevel':{'bore1_mm','bore2_mm','pressure_angle_deg'}}
        for key,w in self.fields.items():self.form.setRowVisible(w,key in (common|extra.get(kind,set()))-hidden.get(kind,set()))
        self.calculate()

    def specification(self):
        from dataclasses import fields
        values={key:w.value() for key,w in self.fields.items()}
        keys={f.name for f in fields(MechanismSpecification)}-{'kind','load'}
        load=LoadSpecification(mode=self.load_mode.currentData(),input_rpm=values['input_rpm'],
            power_kw=values['power_kw'] if self.load_mode.currentData()=='power' else None,
            torque_nm=values['torque_nm'] if self.load_mode.currentData()=='torque' else None)
        return MechanismSpecification(kind=self.kind,load=load,**{k:values[k] for k in keys})

    def changed(self):
        self.canvas.pause();self.result=None;self.enable();self.timer.start()

    def calculate(self):
        if self.owner.busy:return
        from ..ui import number
        self.timer.stop();self.canvas.pause()
        power=self.load_mode.currentData()=='power'
        self.form.setRowVisible(self.fields['power_kw'],power);self.form.setRowVisible(self.fields['torque_nm'],not power)
        try:
            s=self.specification();r=calculate(s);changed=s!=self.spec
            self.spec=s;self.result=r
            if changed:
                self.canvas.set_spec(s if r.cad_available else None)
                if self.mesh_view:self.mesh_view.set_mesh(None)
            self.table.setRowCount(len(r.values))
            for j,(key,value,unit) in enumerate(r.values):
                self.table.setItem(j,0,QTableWidgetItem(key));self.table.setItem(j,1,QTableWidgetItem(number(value)+' '+unit))
            self.warnings.setText('\n'.join(r.warnings));self.empty.setText('' if r.cad_available else CATALOG[self.kind].note)
            self.owner.set_status('Mekanizma hesabı güncellendi.')
        except (ValueError,TypeError) as e:
            self.result=None;self.spec=None;self.canvas.set_spec(None);self.table.setRowCount(0)
            if self.mesh_view:self.mesh_view.set_mesh(None)
            self.warnings.setText(str(e));self.owner.set_status(str(e),True)
        self.enable()

    def enable(self):
        valid=self.result is not None and self.result.cad_available and not self.owner.busy
        for w in (self.step_button,self.dxf_button,self.play_button,self.preview_button):w.setEnabled(valid)

    def toggle(self):
        if self.canvas.timer.isActive():self.canvas.pause()
        else:self.run('check')

    def dialog(self,mode):
        from PySide6.QtWidgets import QFileDialog
        self.calculate()
        if not self.result or not self.result.cad_available:return
        path,_=QFileDialog.getSaveFileName(self,'Mekanizma CAD kaydet',self.kind+'.'+mode,'STEP (*.step)' if mode=='step' else 'DXF (*.dxf)')
        if path:self.run(mode,path)

    def run(self,mode,path=None,target=None):
        self.calculate()
        if not self.result or not self.result.cad_available or not self.owner.can_start():return False
        self.canvas.pause();spec=self.spec;target=target or self.target.currentData()
        self.owner.set_status('Kavraşma / CAD işlemi sürüyor…');self.owner.progressChanged.emit(-1,0)
        def operation(sink,stop):
            try:sink.put(('family_result',(mode,spec,service.execute(spec,mode,target=target,path=path,overwrite=True,stop=stop))))
            except service.OperationCancelled as e:sink.put(('family_cancelled',str(e)))
        return self.owner.jobs.start(self.owner,operation)

    def handle(self,events):
        from ..ui import number
        for kind,payload in events:
            if kind=='family_cancelled':self.owner.set_status(payload)
            if kind!='family_result':continue
            mode,spec,result=payload
            if self.spec!=spec:return
            if mode=='check':
                if not self.isVisible():
                    self.owner.set_status('Kavraşma kontrolü tamamlandı; hareketi sayfadan başlatabilirsiniz.');continue
                self.tabs.setCurrentIndex(1);self.canvas.play();self.owner.set_status('Kavraşma taraması geçti; rijit kinematik başladı.')
            elif mode=='mesh':
                if self.mesh_view is None:
                    from .mesh_view import MechanismMeshView
                    self.mesh_view=MechanismMeshView();self.preview_layout.addWidget(self.mesh_view,1)
                self.mesh_view.set_mesh(result['mesh']);self.tabs.setCurrentIndex(2)
                self.owner.set_status(f"{result['solids']} katı · {number(result['volume_mm3'])} mm³")
            else:self.last_export=result;self.owner.set_status(f"{mode.upper()} doğrulandı ve kaydedildi: {result['path']}")
