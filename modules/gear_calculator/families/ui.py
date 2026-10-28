"""Mechanism workbench using the existing window's cancellable job owner."""
from math import cos,sin,pi,degrees
from PySide6.QtCore import Qt,QTimer,QElapsedTimer,QRectF,Signal,QSignalBlocker
from PySide6.QtGui import QPainterPath,QPen,QColor,QBrush,QPainter
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QDoubleSpinBox,QSpinBox,
    QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTabWidget,
    QGraphicsView,QGraphicsScene,QGraphicsPathItem,QGraphicsEllipseItem,QGraphicsItem,QCheckBox,QStackedWidget)
from gui_qt.components import label,button,scroll
from gui_qt.theme import COLORS
from ..models import LoadSpecification
from .. import service
from ..workspace import GearWorkspace
from .models import MechanismSpecification,CATALOG
from .calculation import calculate,cylindrical
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
    partSelected=Signal(int)
    runningChanged=Signal(bool)
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing);self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse);self.setMinimumSize(200,220)
        self.spec=None;self.items=[];self.pin_items=[];self.helpers=[];self.selected=0;self.angle=0.;self.auto_fit=True
        self.timer=QTimer(self);self.timer.setInterval(16)
        self.clock=QElapsedTimer();self.timer.timeout.connect(self.tick)
        self.setAccessibleName('Dişli mekanizması · 2D kinematik')

    def set_spec(self,spec):
        self.pause();self.spec=spec;self.angle=0;self.scene().clear();self.items=[];self.pin_items=[];self.helpers=[]
        c=COLORS[self.owner.context.appearance];self.setBackgroundBrush(QColor(c['canvas']))
        if spec is None:return
        profiles=sections(spec)
        for k,(idx,angle,x,y) in enumerate(poses(spec)):
            item=QGraphicsPathItem(path_for(profiles[idx]));item.setData(0,idx)
            self.scene().addItem(item);self.items.append(item)
            if spec.kind!='cycloidal':
                if spec.kind=='rack' and idx==1:
                    b=item.boundingRect();helper=self.scene().addLine(b.left(),0,b.right(),0)
                    helper.setParentItem(item);self.add_helper(helper,'pitch')
                else:
                    z=spec.teeth1 if idx==0 else spec.teeth1+2*spec.teeth2 if idx==2 else spec.teeth2
                    g=cylindrical(spec,z)
                    for radius,key in ((g['r'],'pitch'),(g['rb'],'base')):
                        self.add_helper(QGraphicsEllipseItem(-radius,-radius,2*radius,2*radius,item),key)
        if spec.kind=='cycloidal':
            R=spec.module_mm*spec.teeth2/2
            for j in range(spec.teeth2):
                x=R*cos(2*pi*j/spec.teeth2);y=R*sin(2*pi*j/spec.teeth2);r=spec.roller_radius_mm
                pen=QPen(QColor(c['warning']));pen.setCosmetic(True)
                item=self.scene().addEllipse(x-r,y-r,2*r,2*r,pen);item.setData(0,1);self.pin_items.append(item)
            helper=self.scene().addEllipse(-R,-R,2*R,2*R)
            self.add_helper(helper,'pitch')
        self.select(self.selected);self.set_helpers(self.owner.pitch.isChecked(),self.owner.base.isChecked())
        self.update_pose()
        bounds=self.scene().itemsBoundingRect();margin=3*spec.module_mm
        result=calculate(spec)
        from ..ui import number
        values={k:(v,unit) for k,v,unit in result.values}
        key=next((k for k in ('a','a planet','Montaj yüksekliği','R pim') if k in values),None)
        if key:
            pen=QPen(QColor(c['muted']));pen.setCosmetic(True);pen.setStyle(Qt.DashDotLine)
            if spec.kind in ('helical','herringbone','internal'):
                y=bounds.top()-margin
                self.scene().addLine(0,y,values[key][0],y,pen)
                for x in (0,values[key][0]):self.scene().addLine(x,y-margin/2,x,y+margin/2,pen)
            text=self.scene().addSimpleText(f'{key} = {number(values[key][0])} mm')
            text.setBrush(QColor(c['muted']));text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            text.setPos(bounds.left()+bounds.width()*.35,bounds.top()-2*margin)
        self.scene().setSceneRect(bounds.adjusted(-margin,-3*margin,margin,3*margin));self.fit()

    def add_helper(self,item,key):
        c=COLORS[self.owner.context.appearance];pen=QPen(QColor(c['muted'] if key=='pitch' else c['warning']))
        pen.setCosmetic(True);pen.setStyle(Qt.DashLine);item.setPen(pen);item.setZValue(2)
        self.helpers.append((item,key))

    def set_helpers(self,pitch,base):
        for item,key in self.helpers:item.setVisible(pitch if key=='pitch' else base)

    def select(self,index):
        self.selected=index;c=COLORS[self.owner.context.appearance]
        for item in self.items+self.pin_items:
            selected=item.data(0)==index;color=c['accent'] if item.data(0)==0 else c['warning']
            pen=QPen(QColor(color));pen.setCosmetic(True);pen.setWidthF(1.7 if selected else 1.)
            fill=QColor(color);fill.setAlpha(58 if selected else 28);item.setPen(pen);item.setBrush(QBrush(fill))

    def update_pose(self):
        if self.spec:
            angle=self.angle
            if self.spec.kind=='rack':angle=angle%(2*pi/self.spec.teeth1)
            for item,(_,a,x,y) in zip(self.items,poses(self.spec,angle)):
                item.setRotation(degrees(a));item.setPos(x,y)

    def play(self):self.clock.start();self.timer.start();self.runningChanged.emit(True)
    def pause(self):
        active=self.timer.isActive();self.timer.stop()
        if active:self.runningChanged.emit(False)
    def reset(self):self.pause();self.angle=0.;self.update_pose()
    def tick(self):
        self.angle+=self.spec.load.input_rpm*2*pi/60*self.clock.restart()/1000*self.owner.speed.currentData()
        self.update_pose()
    def fit(self):
        self.auto_fit=True
        if self.items:self.resetTransform();self.fitInView(self.sceneRect(),Qt.KeepAspectRatio);self.scale(1,-1)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit:self.fit()
    def wheelEvent(self,event):
        factor=1.15**max(-4,min(4,event.angleDelta().y()/120));current=abs(self.transform().m11())
        if .01<=current*factor<=2000:self.auto_fit=False;self.scale(factor,factor)
        event.accept()
    def mousePressEvent(self,event):self.press_position=event.position();super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if hasattr(self,'press_position') and (event.position()-self.press_position).manhattanLength()<5:
            item=self.itemAt(event.position().toPoint())
            while item is not None and item.data(0) is None:item=item.parentItem()
            if item is not None:self.partSelected.emit(item.data(0))
        else:self.auto_fit=False
        super().mouseReleaseEvent(event)
    def hideEvent(self,event):self.pause();super().hideEvent(event)


class FamilyPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.context=owner.context;self.spec=None;self.result=None;self.mesh_view=None;self.last_export=None
        self.kind='rack';self.saved={};self.fields={};layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.input_panel=QWidget();iv=QVBoxLayout(self.input_panel);iv.setContentsMargins(6,6,6,6)
        iv.addWidget(label('GEOMETRİ','section'));self.form=QFormLayout();self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.load_form=QFormLayout();self.load_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
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
            w.setMinimumWidth(90);self.fields[key]=w
            (self.load_form if key in ('input_rpm','power_kw','torque_nm') else self.form).addRow(title,w)
            w.valueChanged.connect(self.changed)
        iv.addLayout(self.form);iv.addWidget(label('İŞLETME DEĞERLERİ','section'))
        self.load_mode=QComboBox();self.load_mode.addItem('Güç → Tork','power');self.load_mode.addItem('Tork → Güç','torque')
        self.load_form.insertRow(0,'Birincil yük',self.load_mode);iv.addLayout(self.load_form)
        self.load_mode.currentIndexChanged.connect(self.changed)
        self.derived_load=label('','muted');iv.addWidget(self.derived_load)
        self.explanation=label('','muted');iv.addWidget(self.explanation);iv.addStretch()
        self.input_scroll=scroll(self.input_panel);self.input_scroll.setMinimumWidth(250)
        self.viewer_panel=QWidget();v=QVBoxLayout(self.viewer_panel);v.setContentsMargins(0,0,0,0);v.setSpacing(4)
        row=QHBoxLayout();self.play_button=button('Başlat',self.toggle);self.speed=QComboBox()
        for title,value in (('%0,2',.002),('%1',.01),('%2',.02),('%10',.1),('%100',1.)):self.speed.addItem(title,value)
        self.speed.setCurrentIndex(2);self.speed.setAccessibleName('Mekanizma görsel hız ölçeği')
        self.pitch=QCheckBox('Bölüm daireleri');self.pitch.setChecked(True);self.base=QCheckBox('Temel daireler')
        self.base.setToolTip('Evolvent parçaların temel dairelerini gösterir.')
        self.selection=QComboBox();self.selection.setAccessibleName('Seçili mekanizma parçası')
        self.canvas=MechanismCanvas(self)
        self.reset_button=button('Sıfırla',self.canvas.reset);self.fit_button=button('Sığdır',self.fit_view)
        for w in (self.play_button,self.reset_button,self.fit_button):row.addWidget(w)
        row.addWidget(label('Hız','muted',wrap=False));row.addWidget(self.speed);row.addStretch();v.addLayout(row)
        row=QHBoxLayout()
        for w in (self.pitch,self.base,self.selection):row.addWidget(w)
        row.addStretch();v.addLayout(row)
        self.views=QTabWidget();plot=QWidget();pv=QVBoxLayout(plot);pv.setContentsMargins(0,0,0,0)
        self.plot_stack=QStackedWidget();self.plot_stack.addWidget(self.canvas)
        empty_box=QWidget();empty_layout=QVBoxLayout(empty_box);empty_layout.addStretch()
        self.empty=label('','muted');self.empty.setAlignment(Qt.AlignCenter);empty_layout.addWidget(self.empty);empty_layout.addStretch()
        self.plot_stack.addWidget(empty_box);pv.addWidget(self.plot_stack);self.views.addTab(plot,'2D · Hareket')
        self.preview=QWidget();self.preview_layout=QVBoxLayout(self.preview)
        self.preview_button=button('Gerçek katıdan 3D oluştur',lambda:self.run('mesh'))
        self.preview_layout.addWidget(self.preview_button)
        self.preview_hint=label('3D önizleme STEP ile aynı B-Rep katıdan üretilir.','muted');self.preview_layout.addWidget(self.preview_hint)
        self.views.addTab(self.preview,'3D · Katı');v.addWidget(self.views,1)
        self.tabs=self.views;self.motion_caption=label('','muted');v.addWidget(self.motion_caption)
        self.results_panel=QWidget();rv=QVBoxLayout(self.results_panel);rv.setContentsMargins(6,6,6,6)
        self.summary=label('','result');rv.addWidget(self.summary)
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['Büyüklük','Değer'])
        self.table.verticalHeader().hide();self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName('Mekanizma hesap sonuçları')
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents);self.table.setMinimumHeight(220)
        rv.addWidget(self.table,1);self.warnings=label('','muted');rv.addWidget(self.warnings)
        rv.addWidget(label('CAD AKTARIMI','section'))
        self.target=QComboBox();self.target.setAccessibleName('Mekanizma CAD hedefi')
        for title,key in (('İlk parça · kendi merkezi','pinion'),('İkinci parça / halka / pimler','wheel'),('Tam takım · ayrı katılar','pair')):self.target.addItem(title,key)
        self.target.setCurrentIndex(2);rv.addWidget(self.target)
        self.construction=QCheckBox('DXF bölüm dairelerini ekle');self.construction.setChecked(True)
        self.construction.setToolTip('Helisel, çift helisel, iç dişli ve planet DXF aktarımında bölüm dairelerini ekler.')
        rv.addWidget(self.construction)
        row=QHBoxLayout();self.step_button=button('STEP kaydet',lambda:self.dialog('step'));self.dxf_button=button('DXF kaydet',lambda:self.dialog('dxf'))
        self.dxf_button.setToolTip('Helisel türlerde yalnız alın kesiti dışa aktarılır.')
        row.addWidget(self.dxf_button);row.addWidget(self.step_button);rv.addLayout(row)
        rv.addWidget(label('Nominal/ideal hesap. Kesici dibi, mukavemet ve üretim toleransları ayrıca doğrulanmalıdır.','muted'))
        self.results_scroll=scroll(self.results_panel);self.results_scroll.setMinimumWidth(250)
        self.body=GearWorkspace(self.input_scroll,self.viewer_panel,self.results_scroll)
        self.splitter=self.body.splitter;self.compact_tabs=self.body.compact_tabs;layout.addWidget(self.body,1)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(200);self.timer.timeout.connect(self.calculate)
        self.pitch.toggled.connect(self.helpers);self.base.toggled.connect(self.helpers)
        self.selection.currentIndexChanged.connect(self.selected_changed);self.canvas.partSelected.connect(self.select_part)
        self.canvas.runningChanged.connect(lambda active:self.play_button.setText('Duraklat' if active else 'Başlat'))
        self.speed.currentIndexChanged.connect(self.speed_changed)

    @property
    def compact_mode(self):return self.body.compact_mode

    def fit_view(self):
        if self.views.currentIndex()==0:self.canvas.fit()
        elif self.mesh_view:self.mesh_view.fit()

    def helpers(self):self.canvas.set_helpers(self.pitch.isChecked(),self.base.isChecked())

    def selected_changed(self):
        value=self.selection.currentData()
        if value is not None:self.select_part(value)

    def select_part(self,index):
        i=self.selection.findData(index)
        if i<0:return
        with QSignalBlocker(self.selection):self.selection.setCurrentIndex(i)
        self.canvas.select(index)
        if self.result is not None and self.table.rowCount():self.table.item(0,1).setText(self.selection.currentText().split(' · ')[0])
        target='pinion' if index==0 else 'pair' if self.kind=='planetary' and index==1 else 'wheel'
        self.target.setCurrentIndex(self.target.findData(target))

    def speed_changed(self):
        from ..ui import number
        if self.spec and self.result:
            if not self.result.cad_available:
                self.motion_caption.setText('Bu türde hareket ve CAD henüz desteklenmiyor.');return
            values={k:(v,u) for k,v,u in self.result.values}
            output=values.get('n₂')
            detail=f'n₂ = {number(output[0])} dev/dak' if output else f'v = {number(values["v kremayer"][0])} mm/s'
            self.motion_caption.setText(f'n₁ = {number(self.spec.load.input_rpm)} dev/dak · {detail} · görsel hız: {self.speed.currentText()}')
        else:self.motion_caption.setText('Geçerli parametrelerle hesaplayın.')

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
        self.configure_type_controls()
        common={'module_mm','teeth1','teeth2','pressure_angle_deg','width_mm','bore1_mm','bore2_mm','input_rpm','power_kw','torque_nm'}
        extra={'rack':{'rack_teeth','rack_base_mm'},'helical':{'helix_deg'},'herringbone':{'helix_deg'},
            'internal':{'rim_mm'},'planetary':{'planets','rim_mm'},'bevel':{'shaft_angle_deg'},'spiral_bevel':{'shaft_angle_deg'},
            'hypoid':{'offset_mm'},'worm':{'worm_starts','diameter_quotient'},'cycloidal':{'eccentricity_mm','roller_radius_mm'}}
        hidden={'internal':{'bore2_mm'},'planetary':set(),'rack':{'teeth2','bore2_mm'},'cycloidal':{'teeth1','bore2_mm','pressure_angle_deg'},
                'hypoid':{'module_mm','pressure_angle_deg','width_mm','bore1_mm','bore2_mm'},
                'worm':{'teeth1','bore1_mm','bore2_mm','pressure_angle_deg','width_mm'},'bevel':{'bore1_mm','bore2_mm','pressure_angle_deg'},'spiral_bevel':{'bore1_mm','bore2_mm','pressure_angle_deg'}}
        for key,w in self.fields.items():
            if key not in ('input_rpm','power_kw','torque_nm'):
                self.form.setRowVisible(w,key in (common|extra.get(kind,set()))-hidden.get(kind,set()))
        self.calculate()

    def configure_type_controls(self):
        kind=self.kind
        titles={'module_mm':'Modül m · mm','teeth1':'Pinyon diş sayısı z₁','teeth2':'Çark diş sayısı z₂',
            'pressure_angle_deg':'Basınç açısı α · °','width_mm':'Diş genişliği b · mm',
            'bore1_mm':'Pinyon delik çapı · mm','bore2_mm':'Çark delik çapı · mm','rack_base_mm':'Bölümden tabana · mm'}
        if kind in ('helical','herringbone'):
            titles.update(module_mm='Normal modül mₙ · mm',pressure_angle_deg='Normal basınç açısı αₙ · °')
        if kind=='herringbone':titles['width_mm']='Toplam genişlik b · mm'
        if kind=='internal':titles['teeth2']='Halka diş sayısı zᵣ'
        if kind=='planetary':titles.update(teeth1='Güneş diş sayısı zₛ',teeth2='Planet diş sayısı zₚ',bore1_mm='Güneş deliği · mm',bore2_mm='Planet deliği · mm')
        if kind=='cycloidal':titles.update(module_mm='Pim dairesi ölçeği m · mm',teeth2='Pim adedi N',bore1_mm='Disk deliği · mm')
        if kind=='worm':titles['module_mm']='Eksenel modül mₓ · mm'
        if kind in ('bevel','spiral_bevel'):titles['module_mm']='Dış alın modülü m · mm'
        for key,title in titles.items():
            self.form.labelForField(self.fields[key]).setText(title);self.fields[key].setAccessibleName(title)
        names={
            'rack':[('Pinyon · z₁',0),('Kremayer',1)],
            'internal':[('Pinyon · z₁',0),('İç halka · zᵣ',1)],
            'planetary':[('Güneş · zₛ',0),('Planetler · takımda',1),('Halka · zᵣ',2)],
            'cycloidal':[('Sikloid disk',0),('Çevresel pimler',1)]}.get(kind,[('Pinyon · z₁',0),('Çark · z₂',1)])
        with QSignalBlocker(self.selection):
            self.selection.clear()
            for title,index in names:self.selection.addItem(title,index)
            self.selection.setCurrentIndex(0)
        self.canvas.selected=0
        self.target.setItemText(0,names[0][0]+' · kendi merkezi')
        self.target.setItemText(1,('Halka · kendi merkezi' if kind=='planetary' else names[-1][0]))
        self.target.setCurrentIndex(2)
        self.pitch.setText('Pim dairesi' if kind=='cycloidal' else 'Bölüm daireleri')

    def specification(self):
        from dataclasses import fields
        values={key:w.value() for key,w in self.fields.items()}
        keys={f.name for f in fields(MechanismSpecification)}-{'kind','load'}
        load=LoadSpecification(mode=self.load_mode.currentData(),input_rpm=values['input_rpm'],
            power_kw=values['power_kw'] if self.load_mode.currentData()=='power' else None,
            torque_nm=values['torque_nm'] if self.load_mode.currentData()=='torque' else None)
        return MechanismSpecification(kind=self.kind,load=load,**{k:values[k] for k in keys})

    def changed(self):
        self.canvas.pause();self.result=None;self.enable();self.timer.start();self.derived_load.setText('Hesap güncelleniyor…')

    def calculate(self):
        if self.owner.busy:return
        from ..ui import number
        self.timer.stop();self.canvas.pause()
        power=self.load_mode.currentData()=='power'
        self.load_form.setRowVisible(self.fields['power_kw'],power);self.load_form.setRowVisible(self.fields['torque_nm'],not power)
        try:
            s=self.specification();r=calculate(s);changed=s!=self.spec
            self.spec=s;self.result=r
            if changed:
                self.canvas.set_spec(s if r.cad_available else None)
                if self.mesh_view:self.mesh_view.set_mesh(None)
                self.preview_hint.setText('3D önizleme için güncel katıyı oluşturun.')
            values={key:value for key,value,unit in r.values}
            summary=[]
            for key in ('i','a','a planet','p','e','R dış','E ofset'):
                if key in values:
                    symbol={'a planet':'aₚ','R dış':'R','E ofset':'E'}.get(key,key)
                    value=f'{values[key]:.4g}'.replace('.',',')
                    summary.append(f'{symbol} = {value}'+(' mm' if key!='i' else ''))
            self.summary.setText(' · '.join(summary))
            self.derived_load.setText(f'Hesaplanan T₁ = {number(values["T₁"])} N·m' if power else f'Hesaplanan P = {number(values["P"])} kW')
            titles={'P':'Giriş gücü P','n₁':'Giriş devri n₁','T₁':'Giriş torku T₁','d₁':'Pinyon bölüm dairesi d₁',
                'd₂':'Çark bölüm dairesi d₂','dₐ₁':'Pinyon diş üstü dₐ₁','d𝒻₁':'Pinyon diş dibi d𝒻₁','dᵦ₁':'Pinyon temel daire dᵦ₁',
                'mₜ':'Alın modülü mₜ','αₜ':'Alın basınç açısı αₜ','β':'Helis açısı β','a':'Eksen mesafesi a','i':'Çevrim oranı i',
                'n₂':'Çıkış devri n₂','T₂ ideal':'İdeal çıkış torku T₂','Fₜ':'Çevresel kuvvet Fₜ','Fᵣ':'Radyal kuvvet Fᵣ',
                'Fₐ':'Eksenel kuvvet Fₐ','εα':'Alın kavrama oranı εα','εβ':'Eksenel kavrama oranı εβ','εγ':'Toplam kavrama oranı εγ',
                'p':'Dairesel adım p','dₐ₂':'Çark diş üstü dₐ₂','d𝒻₂':'Çark diş dibi d𝒻₂'}
            if self.kind=='planetary':titles.update({'d₁':'Güneş bölüm dairesi d₁','d₂':'Planet bölüm dairesi d₂','n₂':'Taşıyıcı devri n꜀',
                'dₐ₁':'Güneş diş üstü dₐ₁','d𝒻₁':'Güneş diş dibi d𝒻₁','dᵦ₁':'Güneş temel daire dᵦ₁'})
            if self.kind=='internal':titles.update({'d₂':'Halka bölüm dairesi d₂','dₐ₂':'Halka diş üstü dₐ₂','d𝒻₂':'Halka diş dibi d𝒻₂'})
            if self.kind in ('hypoid','worm'):titles['n₂']='Çıkış devri büyüklüğü |n₂|'
            self.table.setRowCount(len(r.values)+1)
            self.table.setItem(0,0,QTableWidgetItem('Seçili parça'))
            self.table.setItem(0,1,QTableWidgetItem(self.selection.currentText().split(' · ')[0]))
            for j,(key,value,unit) in enumerate(r.values):
                self.table.setItem(j+1,0,QTableWidgetItem(titles.get(key,key)+(' · '+unit if unit else '')))
                cell=QTableWidgetItem(number(value));cell.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);self.table.setItem(j+1,1,cell)
            self.warnings.setText('\n'.join(r.warnings[2:]) or 'Geometrik temel kontroller uygun. Mukavemet doğrulaması yapılmadı.')
            self.empty.setText('' if r.cad_available else CATALOG[self.kind].note)
            self.plot_stack.setCurrentIndex(0 if r.cad_available else 1)
            self.owner.set_status('Mekanizma hesabı güncellendi.')
        except (ValueError,TypeError) as e:
            self.result=None;self.spec=None;self.canvas.set_spec(None);self.table.setRowCount(0)
            if self.mesh_view:self.mesh_view.set_mesh(None)
            self.summary.setText('—');self.derived_load.setText('—');self.empty.setText('Geçerli parametrelerle yeniden hesaplayın.')
            self.plot_stack.setCurrentIndex(1);self.warnings.setText(str(e));self.owner.set_status(str(e),True)
        self.enable();self.speed_changed()

    def enable(self):
        valid=self.result is not None and self.result.cad_available and not self.owner.busy
        for w in (self.step_button,self.dxf_button,self.play_button,self.preview_button,self.pitch,self.selection,self.speed,self.reset_button,self.fit_button,self.target):w.setEnabled(valid)
        self.construction.setEnabled(valid and self.kind in ('helical','herringbone','internal','planetary'))
        self.base.setEnabled(valid and self.kind!='cycloidal')
        self.views.setTabEnabled(1,valid)

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
        self.canvas.pause();spec=self.spec;target=target or self.target.currentData();construction=self.construction.isChecked()
        self.owner.set_status('Kavraşma / CAD işlemi sürüyor…');self.owner.progressChanged.emit(-1,0)
        def operation(sink,stop):
            try:sink.put(('family_result',(mode,spec,service.execute(spec,mode,target=target,path=path,construction=construction,overwrite=True,stop=stop))))
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
                if self.compact_mode:self.compact_tabs.setCurrentIndex(1)
                self.views.setCurrentIndex(0);self.canvas.play();self.owner.set_status('Kavraşma taraması geçti; rijit kinematik başladı.')
            elif mode=='mesh':
                if self.mesh_view is None:
                    from .mesh_view import MechanismMeshView
                    self.mesh_view=MechanismMeshView();self.preview_layout.addWidget(self.mesh_view,1)
                self.mesh_view.set_mesh(result['mesh'])
                if self.compact_mode:self.compact_tabs.setCurrentIndex(1)
                self.views.setCurrentIndex(1);self.preview_hint.setText(f"{result['solids']} ayrı katı · hacim {number(result['volume_mm3'])} mm³")
                self.owner.set_status(f"{result['solids']} katı · {number(result['volume_mm3'])} mm³")
            else:self.last_export=result;self.owner.set_status(f"{mode.upper()} doğrulandı ve kaydedildi: {result['path']}")
