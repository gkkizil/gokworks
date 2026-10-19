"""Small native widgets shared by the tolerance workspace and its editors."""

from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton
from ..diagrams import EngineeringDiagram


class StackDiagram(EngineeringDiagram):
    """Reflow text at the viewport width instead of shrinking a desktop-sized image."""

    def __init__(self, *, width=700, height=300, parent=None):
        super().__init__(width=width,height=height,parent=parent)
        self.preferred_height=height
        self.resize_timer=QTimer(self);self.resize_timer.setSingleShot(True);self.resize_timer.setInterval(40)
        self.resize_timer.timeout.connect(self.redraw)

    def size_scene(self):
        width=max(360,self.viewport().width())
        height=max(130,min(self.preferred_height,self.viewport().height()))
        self.vector.width,self.vector.height=width,height
        self.vector.setSceneRect(0,0,width,height)

    def render_geometry(self,renderer):
        self.size_scene()
        super().render_geometry(renderer)

    def redraw(self):
        if self.renderer is not None:self.render_geometry(self.renderer)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'resize_timer'):self.resize_timer.start()


class Disclosure(QWidget):
    """Keep specialist controls available without crowding the main workflow."""

    def __init__(self, title, content, parent=None, *, expanded=False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.content = content
        layout.addWidget(self.toggle, alignment=Qt.AlignLeft)
        layout.addWidget(content)
        self.toggle.toggled.connect(self.set_expanded)
        self.toggle.setChecked(expanded)
        self.set_expanded(expanded)

    def set_expanded(self, expanded):
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setAccessibleDescription('Açık' if expanded else 'Kapalı')


def compact(value, digits=4):
    """Readable mm labels; reports continue to retain their full precision."""
    if value is None:
        return 'Eksik'
    text = f'{value:.{digits}f}'.rstrip('0').rstrip('.')
    if not text or text == '-0':
        text = '0'
    if text == '0' and value != 0:
        text = f'{value:.6g}'
    return text.replace('.', ',')


def short_name(dimension):
    return dimension.name.split('@', 1)[0]
