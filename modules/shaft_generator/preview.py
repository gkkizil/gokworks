"""Two linked, true-scale Qt technical views of the same project."""

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget, QSizePolicy
from gui_qt.theme import COLORS
from .geometry import treated_profile
from .models import Groove, Keyway
from .validation import validate


class ShaftPreview(QWidget):
    stageSelected = Signal(str)
    operationSelected = Signal(str)

    def __init__(self, *, section=False):
        super().__init__()
        self.section = section
        self.project = None
        self.selected_stage = self.selected_operation = ''
        self.appearance = 'dark'
        self.stage_regions = []
        self.operation_regions = []
        self.setMinimumSize(180, 170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName('Mil teknik kesiti' if section else 'Mil dış görünüşü')
        self.setToolTip('Kademeyi seçmek için çizime tıklayın. Kesitte operasyona tıklayabilirsiniz.')

    def set_project(self, project, stage_id='', operation_id=''):
        self.project = project
        self.selected_stage, self.selected_operation = stage_id, operation_id
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = COLORS[self.appearance]
        background = QColor(colors['canvas'])
        ink = QColor(colors['text'])
        muted = QColor(colors['muted'])
        accent = QColor(colors['accent'])
        painter.fillRect(self.rect(), background)
        painter.setPen(muted)
        painter.drawText(QRectF(12, 8, self.width()-24, 22), Qt.AlignLeft|Qt.AlignVCenter,
                         'BOYUNA KESİT · A–A' if self.section else 'DIŞ GÖRÜNÜŞ · mm')
        self.stage_regions, self.operation_regions = [], []
        if self.project is None or validate(self.project):
            painter.drawText(self.rect().adjusted(18,35,-18,-10), Qt.AlignCenter|Qt.TextWordWrap,
                             'Geçerli ölçüler girildiğinde önizleme güncellenir.')
            return
        project = self.project
        # One isotropic scale preserves both diameter and axial proportions.
        margin = 40 if self.width() >= 400 else 24
        scale = min((self.width()-2*margin)/project.total_length,
                    (self.height()-110)/project.maximum_diameter)
        scale = max(scale, .000001)
        left = (self.width()-project.total_length*scale)/2
        center = (self.height()+12)/2
        def point(x,y):
            return QPointF(left+x*scale, center-y*scale)
        half = treated_profile(project)
        boundary = half[:-1] + [(x,-y) for x,y in reversed(half[1:-1])]
        body = QPainterPath()
        body.addPolygon(QPolygonF([point(x,y) for x,y in boundary]))
        body.closeSubpath()
        for op in project.operations:
            stage = project.stage(op.stage_id)
            if isinstance(op, Groove):
                x = project.start(stage.id)+op.offset
                for sign in (1,-1):
                    a=point(x,sign*stage.diameter/2)
                    b=point(x+op.width,sign*(stage.diameter/2-op.depth))
                    cut = QPainterPath(); cut.addRect(QRectF(a,b).normalized())
                    body = body.subtracted(cut)
        painter.setPen(QPen(ink,1.5))
        painter.setBrush(QColor(colors['border']) if not self.section else Qt.BrushStyle.BDiagPattern)
        painter.drawPath(body)
        for i, stage in enumerate(project.stages):
            x,end=project.boundaries[i:i+2]
            rect = QRectF(point(x,stage.diameter/2),point(end,-stage.diameter/2)).normalized()
            self.stage_regions.append((stage.id,rect))
            if stage.id == self.selected_stage:
                highlight = QColor(accent); highlight.setAlpha(48)
                painter.save(); painter.setClipPath(body)
                painter.fillRect(rect,highlight); painter.restore()
                painter.setPen(QPen(accent,1)); painter.setBrush(Qt.NoBrush); painter.drawRect(rect)
            # Dimensions use model values, with compact labels when narrow.
            painter.setPen(QPen(muted,.8))
            y = center+project.maximum_diameter*scale/2+18
            x1,x2=point(x,0).x(),point(end,0).x()
            painter.drawLine(QPointF(x1,y-5),QPointF(x1,y+5))
            painter.drawLine(QPointF(x2,y-5),QPointF(x2,y+5))
            painter.drawLine(QPointF(x1,y),QPointF(x2,y))
            if x2-x1 > 30:
                painter.drawText(QRectF(x1,y+3,x2-x1,18),Qt.AlignCenter,f'{stage.length:g}')
            if rect.width() > 38:
                painter.drawText(QRectF(rect.x(),rect.top()-22,rect.width(),20),Qt.AlignCenter,f'Ø{stage.diameter:g}')
        painter.setPen(QPen(muted,.8,Qt.DashDotLine))
        painter.drawLine(point(-5,0),point(project.total_length+5,0))
        for op in project.operations:
            stage=project.stage(op.stage_id)
            if isinstance(op,(Groove,Keyway)):
                x=project.start(stage.id)+op.offset
                length=op.width if isinstance(op,Groove) else op.length
                # 0° rectangular keyway is on the +Y side in both projections.
                top=stage.diameter/2
                rect=QRectF(point(x,top),point(x+length,top-op.depth)).normalized()
                if isinstance(op,Keyway):
                    painter.setPen(QPen(accent if op.id==self.selected_operation else ink,1.3))
                    painter.setBrush(background)
                    painter.drawRect(rect)
                hit=rect.adjusted(-3,-4,3,4)
            else:
                x=project.end(stage.id) if op.edge=='right' else project.start(stage.id)
                p=point(x,stage.diameter/2)
                hit=QRectF(p.x()-8,p.y()-8,16,16)
            self.operation_regions.append((op.id,op.stage_id,hit))
            if op.id==self.selected_operation:
                painter.setBrush(Qt.NoBrush); painter.setPen(QPen(accent,2))
                painter.drawRect(hit)
        painter.setPen(muted)
        painter.drawText(QRectF(12,self.height()-23,self.width()-24,19),Qt.AlignRight|Qt.AlignVCenter,
                         f'Toplam {project.total_length:g} mm · {len(project.stages)} kademe')

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            if self.section:
                for op_id,stage_id,rect in reversed(self.operation_regions):
                    if rect.contains(event.position()):
                        self.stageSelected.emit(stage_id); self.operationSelected.emit(op_id)
                        return
            for stage_id,rect in self.stage_regions:
                if rect.contains(event.position()):
                    self.stageSelected.emit(stage_id)
                    return
        super().mousePressEvent(event)
