"""Small Qt-only editors and a vector, zoomable sheet preview."""

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QDialogButtonBox, QGraphicsView, QGraphicsScene, QSizePolicy)

from ..components import ValueForm, label, scroll
from ..models import TableModel
from ..theme import COLORS
from nesting.geometry import placed
from nesting.render import painter_path, PALETTE


class Values(dict):
    def set(self, key, value):
        self[key] = value


class NestingTableModel(TableModel):
    """Keep numeric columns legible and full source/error text discoverable."""
    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            row = self.rows[index.row()]
            if role == Qt.TextAlignmentRole and self.columns[index.column()].key in ('quantity','thickness','stock','weight','price'):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            if role == Qt.ToolTipRole:
                details=[str(row[k]) for k in ('code','source','detail') if row.get(k)]
                if row.get('weight') is not None:
                    details.append(f"Net ağırlık: {row['weight']:.3f} kg/adet".replace('.',','))
                return '\n'.join(details) or super().data(index,role)
        return super().data(index,role)


class Editor(QDialog):
    def __init__(self, parent, title, build, parse):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(520, 650); self.value = None; self.parse = parse
        layout = QVBoxLayout(self)
        self.form = ValueForm(Values(), '')
        build(self.form)
        layout.addWidget(scroll(self.form), 1)
        self.error = label('', 'error'); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Uygula'); buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        buttons.accepted.connect(self.submit); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def submit(self):
        try:
            self.value = self.parse(self.form)
        except (ValueError, TypeError) as error:
            self.error.setText(str(error)); return
        self.accept()


class NestingCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self)); self.setMinimumSize(0,0)
        # The sheet takes the remaining space. A minimum viewport height can
        # force Qt to overlap the result labels at native Windows font sizes.
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Ignored)
        self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # fitInView must not toggle scrollbars and start another resize/layout
        # cycle while a progress update is synchronously repainting the window.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.theme = 'dark'; self.project = self.result = self.key = None
        self.auto_fit = True
        self.show_labels = True; self.part_labels = []
        self.setAccessibleName('Sac üzerinde parça yerleşimi')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Sığdır: bütün plakayı göster')
        self.resize_timer = QTimer(self); self.resize_timer.setSingleShot(True); self.resize_timer.setInterval(40)
        self.resize_timer.timeout.connect(lambda:self.fit() if self.auto_fit else None)
        self.empty_label = label('DXF dosyalarını ekleyin, ardından Yerleştir düğmesine basın.', 'muted')
        self.empty_label.setParent(self.viewport()); self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.empty()

    def empty(self):
        self.scene().clear()
        self.part_labels = []
        self.scene().setSceneRect(QRectF(0,0,100,100))
        self.setBackgroundBrush(QColor(COLORS[self.theme]['bg']))
        self.empty_label.setStyleSheet('font-size: 13px; color: '+COLORS[self.theme]['muted']+';')
        self.empty_label.setGeometry(self.viewport().rect().adjusted(24,24,-24,-24))
        self.empty_label.show(); self.fit()

    def render(self, project, result, key):
        self.project, self.result, self.key = project, result, key
        self.scene().clear()
        self.part_labels = []
        if result is None or key is None:
            return self.empty()
        self.empty_label.hide()
        colors = COLORS[self.theme]; self.setBackgroundBrush(QColor(colors['bg']))
        sheet = project.sheet(key[0]); pen = QPen(QColor(colors['muted'])); pen.setCosmetic(True)
        self.scene().addRect(QRectF(0,-sheet.height,sheet.width,sheet.height), pen, QColor(colors['panel']))
        margin = project.options.margin
        edge = QPen(QColor(colors['muted']), 1, Qt.DashLine); edge.setCosmetic(True)
        self.scene().addRect(QRectF(margin, -sheet.height+margin, max(0,sheet.width-2*margin), max(0,sheet.height-2*margin)), edge)
        part_lookup = {part.id:(part,PALETTE[index%len(PALETTE)],part.area)
                       for index,part in enumerate(project.parts)}
        for p in result.placements:
            if (p.sheet_id, p.sheet_number) != key:
                continue
            part,color,area = part_lookup[p.part_id]; g = placed(part, p)
            item = self.scene().addPath(painter_path(g), pen, QColor(color))
            item.setToolTip(f'{part.code} #{p.instance}\n{area:,.2f} mm² · {part.thickness:g} mm\n'
                            f'X={p.x:.3f}; Y={p.y:.3f}; {p.angle:g}°')
            # Keep long file names out of neighbouring parts. The full code
            # and instance remain available on hover, including with names off.
            caption = part.code if len(part.code) <= 18 else part.code[:15]+'…'
            text = self.scene().addSimpleText(caption)
            text.setBrush(QColor('#12243a')); bounds = text.boundingRect(); center = g.representative_point()
            factor = min(1, (g.bounds[2]-g.bounds[0])/max(bounds.width(),1)*.7,
                         (g.bounds[3]-g.bounds[1])/max(bounds.height(),1)*.5)
            text.setScale(factor); text.setPos(center.x-bounds.width()*factor/2, -center.y-bounds.height()*factor/2)
            text.setToolTip(item.toolTip())
            text.setVisible(self.show_labels); self.part_labels.append(text)
        self.scene().setSceneRect(-10,-sheet.height-10,sheet.width+20,sheet.height+20); self.fit()

    def set_labels_visible(self, visible):
        self.show_labels = visible
        for item in self.part_labels: item.setVisible(visible)

    def fit(self):
        self.auto_fit = True
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'empty_label'): self.empty_label.setGeometry(self.viewport().rect().adjusted(24,24,-24,-24))
        if hasattr(self,'resize_timer'): self.resize_timer.start()

    def wheelEvent(self, event):
        self.auto_fit = False
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        if .0001 < self.transform().m11()*factor < 10000:
            self.scale(factor, factor)
        event.accept()
