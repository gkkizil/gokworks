"""Reuses the Qt family canvas controls; chain marks are static references only."""
from math import acos,cos,sin,pi,degrees
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QPainterPath,QColor,QPen
from PySide6.QtWidgets import QGraphicsPathItem,QGraphicsEllipseItem,QGraphicsItem
from gui_qt.theme import COLORS
from ..families.ui import MechanismCanvas
from .calculation import calculate
from .geometry import profile,poses,chain_route


def outline(s):
    path=QPainterPath();arcs=profile(s);path.moveTo(*arcs[0].point(0))
    for a in arcs:
        x,y=a.center;r=a.radius
        path.arcTo(QRectF(x-r,y-r,2*r,2*r),-degrees(a.start),-degrees(a.end-a.start))
    path.closeSubpath()
    if s.bore_mm:path.addEllipse(QRectF(-s.bore_mm/2,-s.bore_mm/2,s.bore_mm,s.bore_mm))
    path.setFillRule(Qt.OddEvenFill);return path


class SprocketCanvas(MechanismCanvas):
    def __init__(self,owner):
        super().__init__(owner);self.setAccessibleName('Zincir dişlileri · ortalama kinematik ve statik zincir güzergâhı')

    def set_spec(self,s):
        self.pause();self.spec=s;self.angle=0.;self.scene().clear();self.items=[];self.pin_items=[];self.helpers=[]
        c=COLORS[self.owner.context.appearance];self.setBackgroundBrush(QColor(c['canvas']))
        if s is None:return
        result=calculate(s);C=result.corrected_center_mm
        for idx,(wheel,g,x) in enumerate(((s.driver,result.driver,0.),(s.driven,result.driven,C))):
            item=QGraphicsPathItem(outline(wheel));item.setData(0,idx);item.setPos(x,0)
            self.scene().addItem(item);self.items.append(item);r=g.pitch_diameter_mm/2
            self.add_helper(QGraphicsEllipseItem(-r,-r,2*r,2*r,item),'pitch')
            nx=(result.driver.pitch_diameter_mm-result.driven.pitch_diameter_mm)/(2*C)
            for j in range(wheel.teeth):
                angle=2*pi*j/wheel.teeth
                if (cos(angle)<=nx+1e-10 if idx==0 else cos(angle)>=nx-1e-10):
                    radius=wheel.chain.roller_diameter_mm/2
                    marker=QGraphicsEllipseItem(r*cos(angle)-radius,r*sin(angle)-radius,2*radius,2*radius,item)
                    self.add_helper(marker,'base')
            pen=QPen(QColor(c['muted']));pen.setCosmetic(True)
            self.scene().addLine(x-2,0,x+2,0,pen);self.scene().addLine(x,-2,x,2,pen)
        top1,top2,bottom2,bottom1=chain_route(s);route=QPainterPath();route.moveTo(*top1);route.lineTo(*top2)
        theta=acos((result.driver.pitch_diameter_mm-result.driven.pitch_diameter_mm)/(2*C))
        r=result.driven.pitch_diameter_mm/2
        route.arcTo(QRectF(C-r,-r,2*r,2*r),-degrees(theta),degrees(2*theta))
        route.lineTo(*bottom1);r=result.driver.pitch_diameter_mm/2
        route.arcTo(QRectF(-r,-r,2*r,2*r),degrees(theta),degrees(2*pi-2*theta));route.closeSubpath()
        pen=QPen(QColor(c['muted']));pen.setCosmetic(True);pen.setStyle(Qt.DashLine)
        self.scene().addPath(route,pen).setZValue(-1)
        bounds=self.scene().itemsBoundingRect();margin=s.driver.chain.pitch_mm*1.5;y=bounds.top()-margin
        self.scene().addLine(0,y,C,y,pen)
        for x in (0,C):self.scene().addLine(x,y-margin/4,x,y+margin/4,pen)
        from ..ui import number
        text=self.scene().addSimpleText(f'C ≈ {number(C)} mm · {result.selected_links} bakla · statik güzergâh')
        text.setBrush(QColor(c['muted']));text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        text.setPos(0,y-margin/2)
        self.scene().setSceneRect(bounds.adjusted(-margin,-2*margin,margin,margin))
        self.select(self.selected);self.update_pose();self.fit()

    def update_pose(self):
        if self.spec:
            for item,(_,angle,x,y) in zip(self.items,poses(self.spec,self.angle)):
                item.setRotation(degrees(angle));item.setPos(x,y)
        self.set_helpers(self.owner.pitch.isChecked(),self.owner.base.isChecked())

    def set_helpers(self,pitch,base):
        for item,key in self.helpers:item.setVisible(pitch if key=='pitch' else base and abs(self.angle)<1e-12)
