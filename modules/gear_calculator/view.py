"""Qt 2D view of the common analytic profile and external-pair rigid kinematics."""

from math import degrees, pi
from PySide6.QtCore import Qt, QRectF, Signal, QTimer, QElapsedTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGraphicsItem
from gui_qt.theme import COLORS
from .calculation import calculate_pair
from .geometry import gear_profile, pair_angles


def profile_path(spec):
    profile=gear_profile(spec)
    p=QPainterPath();p.moveTo(*profile.segments[0].point(0))
    for segment in profile.segments:
        if segment.kind=='line':
            p.lineTo(*segment.controls[-1])
        elif segment.kind=='bezier':
            p.cubicTo(*(v for point in segment.controls[1:] for v in point))
        else:
            r=segment.radius
            p.arcTo(QRectF(-r,-r,2*r,2*r),-degrees(segment.start_angle),-degrees(segment.end_angle-segment.start_angle))
    p.closeSubpath()
    if spec.bore_mm:
        r=spec.bore_mm/2;p.addEllipse(QRectF(-r,-r,2*r,2*r))
    p.setFillRule(Qt.OddEvenFill)
    return p


def cosmetic_pen(color,width=1.,style=Qt.SolidLine):
    p=QPen(QColor(color),width,style);p.setCosmetic(True)
    return p


class GearCanvas(QGraphicsView):
    gearSelected=Signal(int)
    runningChanged=Signal(bool)

    def __init__(self,appearance='dark',parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self));self.setMinimumSize(240,220)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setAccessibleName('Evolvent dişli çifti · 2D hareket ve seçim')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Dişliye tıkla: seç')
        self.appearance=appearance;self.specification=None;self.gears=[];self.helpers=[]
        self.selected=0;self.input_angle=0.;self.speed_scale=.02;self.auto_fit=True
        self.show_pitch=True;self.show_base=False
        self.timer=QTimer(self);self.timer.setInterval(16);self.timer.timeout.connect(self.tick)
        self.clock=QElapsedTimer()
        self.theme_changed(appearance)

    def set_specification(self,spec):
        self.pause();self.specification=spec;self.input_angle=0.
        self.scene().clear();self.gears=[];self.helpers=[]
        if spec is None:
            return
        result=calculate_pair(spec);colors=COLORS[self.appearance]
        for index,gear in enumerate((spec.pinion,spec.wheel)):
            item=QGraphicsPathItem(profile_path(gear));item.setData(0,index)
            self.scene().addItem(item);self.gears.append(item)
            item.setPos(0 if index==0 else result.center_distance_mm,0)
            for radius,key in ((gear.module_mm*gear.teeth/2,'pitch'),
                               ((result.pinion if index==0 else result.wheel).base_radius_mm,'base')):
                from PySide6.QtWidgets import QGraphicsEllipseItem
                circle=QGraphicsEllipseItem(-radius,-radius,2*radius,2*radius,item)
                circle.setPen(cosmetic_pen(colors['muted'] if key=='pitch' else colors['warning'],.8,Qt.DashLine))
                circle.setZValue(2);circle.setData(1,key);self.helpers.append(circle)
        bottom=-max(result.pinion.outside_radius_mm,result.wheel.outside_radius_mm)-6*spec.pinion.module_mm
        pen=cosmetic_pen(colors['muted'],.8,Qt.DashDotLine)
        self.scene().addLine(0,0,result.center_distance_mm,0,pen)
        for x in (0,result.center_distance_mm):
            self.scene().addLine(x,bottom,x,bottom+3*spec.pinion.module_mm,pen)
        self.scene().addLine(0,bottom,result.center_distance_mm,bottom,pen)
        text=self.scene().addSimpleText(f'a = {result.center_distance_mm:g} mm · z₁={spec.pinion.teeth} / z₂={spec.wheel.teeth}')
        text.setBrush(QBrush(QColor(colors['muted'])));text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        text.setPos(result.center_distance_mm*.2,bottom-spec.pinion.module_mm)
        margin=3*spec.pinion.module_mm
        self.scene().setSceneRect(QRectF(-result.pinion.outside_radius_mm-margin,bottom-margin,
            result.center_distance_mm+result.pinion.outside_radius_mm+result.wheel.outside_radius_mm+2*margin,
            max(result.pinion.outside_radius_mm,result.wheel.outside_radius_mm)-bottom+2*margin))
        self.select(self.selected);self.set_helpers(self.show_pitch,self.show_base);self.update_angles();self.fit()

    def select(self,index):
        self.selected=index;c=COLORS[self.appearance]
        for i,item in enumerate(self.gears):
            color=c['accent'] if i==0 else c['warning']
            fill=QColor(color);fill.setAlpha(58 if i==index else 28)
            item.setBrush(QBrush(fill));item.setPen(cosmetic_pen(color,1.7 if i==index else 1.))

    def theme_changed(self,appearance):
        self.appearance=appearance;self.setBackgroundBrush(QBrush(QColor(COLORS[appearance]['canvas'])))
        if self.specification is not None:
            spec=self.specification;angle=self.input_angle
            self.set_specification(spec);self.input_angle=angle;self.update_angles()

    def set_helpers(self,pitch,base):
        self.show_pitch,self.show_base=pitch,base
        for item in self.helpers:
            item.setVisible(pitch if item.data(1)=='pitch' else base)

    def update_angles(self):
        if self.specification is not None:
            for item,angle in zip(self.gears,pair_angles(self.specification,self.input_angle)):
                item.setRotation(degrees(angle))

    def play(self):
        if self.specification is None:return
        self.clock.start();self.timer.start();self.runningChanged.emit(True)

    def pause(self):
        active=self.timer.isActive();self.timer.stop()
        if active:self.runningChanged.emit(False)

    def reset(self):
        self.pause();self.input_angle=0.;self.update_angles()

    def tick(self):
        elapsed=self.clock.restart()/1000
        self.input_angle+=self.specification.load.input_rpm*2*pi/60*elapsed*self.speed_scale
        self.update_angles()

    def fit(self):
        self.auto_fit=True
        if self.gears:
            self.resetTransform();self.fitInView(self.sceneRect(),Qt.KeepAspectRatio);self.scale(1,-1)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit:self.fit()

    def wheelEvent(self,event):
        if not self.gears:return
        factor=1.15**max(-4,min(4,event.angleDelta().y()/120))
        current=abs(self.transform().m11())
        if .01<=current*factor<=2000:
            self.auto_fit=False;self.scale(factor,factor)
        event.accept()

    def mousePressEvent(self,event):
        self.press_position=event.position();super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        if hasattr(self,'press_position') and (event.position()-self.press_position).manhattanLength()<5:
            item=self.itemAt(event.position().toPoint())
            while item is not None and item not in self.gears:item=item.parentItem()
            if item in self.gears:
                self.select(self.gears.index(item));self.gearSelected.emit(self.selected)
        else:self.auto_fit=False
        super().mouseReleaseEvent(event)

    def hideEvent(self,event):
        self.pause();super().hideEvent(event)
