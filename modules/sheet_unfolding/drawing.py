"""2D development view and dimensioned shape sketch, drawn from service vectors.

geometry_2d entities are drawn as real vector items (lines, polylines, exact
arcs). Coordinates are mm with +Y up. Measurement snaps to service vertices; it
never derives an engineering length from screen pixels.
"""

import math

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QBrush
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem, QGraphicsEllipseItem, QLineEdit, QWidget

from gui_qt.theme import COLORS

LAYERS = (  # key, title, pen token, style, width
    ('cut', 'Dış kesim', 'text', Qt.SolidLine, 1.8),
    ('hole', 'Delik', 'text', Qt.SolidLine, 1.4),
    ('bend', 'Büküm', 'accent', Qt.DashLine, 1.2),
    ('construction', 'Yardımcı', 'muted', Qt.DotLine, .8),
    ('seam', 'Dikiş', 'warning', Qt.DashDotLine, 1.4),
    ('dimension', 'Ölçü', 'muted', Qt.SolidLine, .8),
    ('nominal', 'Nominal karşılaştırma', 'warning', Qt.DashDotLine, 1.),
)
LAYER_KEYS = tuple(item[0] for item in LAYERS)


def _p(xy):
    return QPointF(xy[0], -xy[1])


def entity_path(entity):
    """Exact QPainterPath of one entity (drawing coordinates, Y flipped)."""
    path = QPainterPath()
    kind = entity['type']
    if kind in ('line', 'dimension'):
        path.moveTo(_p(entity['start'])); path.lineTo(_p(entity['end']))
    elif kind == 'polyline':
        points = entity['points']
        path.moveTo(_p(points[0]))
        for point in points[1:]:
            path.lineTo(_p(point))
        if entity.get('closed'):
            path.closeSubpath()
    elif kind == 'arc':
        cx, cy = entity['center']; r = entity['radius']
        start, end = entity['start_deg'], entity['end_deg']
        sweep = (end - start) % 360 or 360
        rect = QRectF(cx - r, -cy - r, 2 * r, 2 * r)
        path.arcMoveTo(rect, start); path.arcTo(rect, start, sweep)
    elif kind == 'circle':
        cx, cy = entity['center']; r = entity['radius']
        path.addEllipse(QPointF(cx, -cy), r, r)
    return path


def snap_points(entities):
    """Vertices, arc ends/centres from the service geometry (measurement snapping)."""
    points = []
    for e in entities:
        if e['layer'] == 'dimension':
            continue
        if e['type'] == 'line':
            points += [tuple(e['start']), tuple(e['end'])]
        elif e['type'] == 'polyline':
            points += [tuple(p) for p in e['points']]
        elif e['type'] in ('arc', 'circle'):
            cx, cy = e['center']; r = e['radius']; points.append((cx, cy))
            if e['type'] == 'arc':
                for a in (e['start_deg'], e['end_deg']):
                    points.append((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
    return points


class DevelopmentView(QGraphicsView):
    """Pan (drag), wheel zoom, fit, 1:1; layer toggles; part focus; snapped measuring."""
    measured = Signal(float)          # distance in mm from service coordinates
    partClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setAccessibleName('Açınım 2B görünüm')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Çift tık: sığdır')
        self.appearance = 'dark'
        self.parts = []; self.visible = set(LAYER_KEYS); self.selected = None; self.focus_selected = False
        self.measuring = False; self.measure_points = []; self.snaps = []
        self.message = 'Açınım yok.'
        self.setBackgroundBrush(QColor(COLORS[self.appearance]['canvas']))

    def set_appearance(self, appearance):
        self.appearance = appearance if appearance in COLORS else 'dark'
        self.setBackgroundBrush(QColor(COLORS[self.appearance]['canvas'])); self.redraw()

    def set_parts(self, parts, message=''):
        self.parts = list(parts or ()); self.message = message or 'Açınım yok.'
        if self.selected not in {p['part_id'] for p in self.parts}:
            self.selected = self.parts[0]['part_id'] if self.parts else None
        self.measure_points = []
        self.redraw(fit=True)

    def set_layer(self, key, on):
        (self.visible.add if on else self.visible.discard)(key); self.redraw()

    def select(self, part_id):
        self.selected = part_id; self.redraw(fit=self.focus_selected)

    def set_focus_selected(self, on):
        self.focus_selected = bool(on); self.redraw(fit=True)

    def _layout(self):
        """Parts side by side (display placement only; the geometry is unchanged)."""
        placed, x = [], 0.
        for part in self.parts:
            if self.focus_selected and part['part_id'] != self.selected:
                continue
            bounds = QRectF()
            for e in part['geometry_2d']['entities']:
                bounds = bounds.united(entity_path(e).boundingRect())
            placed.append((part, x - bounds.left()))
            x += bounds.width() + max(bounds.width() * .35, 40.)
        return placed

    def redraw(self, fit=False):
        scene = self.scene(); scene.clear(); self.snaps = []
        colors = COLORS[self.appearance]
        if not self.parts:
            text = scene.addSimpleText(self.message); text.setBrush(QColor(colors['muted']))
            self.resetTransform(); self.centerOn(text)
            return
        styles = {key: (token, style, width) for key, _, token, style, width in LAYERS}
        for part, dx in self._layout():
            selected = part['part_id'] == self.selected
            for e in part['geometry_2d']['entities']:
                layer = e['layer']
                if layer not in self.visible:
                    continue
                token, style, width = styles.get(layer, ('muted', Qt.SolidLine, 1.))
                colour = QColor(colors['accent'] if selected and layer == 'cut' and len(self.parts) > 1 else colors[token])
                pen = QPen(colour, width, style); pen.setCosmetic(True)
                item = scene.addPath(entity_path(e), pen); item.setPos(dx, 0); item.setData(0, part['part_id'])
                if e['type'] == 'dimension' and e.get('text'):
                    label = QGraphicsSimpleTextItem(e['text']); label.setBrush(QColor(colors['muted']))
                    label.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
                    mid = (_p(e['start']) + _p(e['end'])) / 2
                    label.setPos(mid.x() + dx, mid.y()); scene.addItem(label)
            self.snaps += [((x + dx, y), part['part_id']) for x, y in snap_points(part['geometry_2d']['entities'])]
        for point in self.measure_points:
            dot = QGraphicsEllipseItem(-4, -4, 8, 8); dot.setBrush(QBrush(QColor(colors['accent']))); dot.setPen(Qt.NoPen)
            dot.setFlag(QGraphicsEllipseItem.ItemIgnoresTransformations); dot.setPos(point[0], -point[1]); scene.addItem(dot)
        if len(self.measure_points) == 2:
            a, b = self.measure_points
            pen = QPen(QColor(colors['accent']), 1.2, Qt.DashLine); pen.setCosmetic(True)
            scene.addLine(a[0], -a[1], b[0], -b[1], pen)
        if fit:
            self.fit()

    def fit(self):
        rect = self.scene().itemsBoundingRect()
        if rect.isEmpty():
            return
        margin = max(rect.width(), rect.height()) * .05 + 1
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)

    def one_to_one(self):
        """1 mm on the model = 1 mm on this screen (from the screen's logical DPI)."""
        scale = self.logicalDpiX() / 25.4
        self.resetTransform(); self.scale(scale, scale)

    def wheelEvent(self, event):
        factor = 1.2 ** (event.angleDelta().y() / 120)
        if 1e-5 < self.transform().m11() * factor < 1e5:
            self.scale(factor, factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.fit(); event.accept()

    def set_measuring(self, on):
        self.measuring = bool(on); self.measure_points = []
        self.setDragMode(QGraphicsView.NoDrag if on else QGraphicsView.ScrollHandDrag); self.redraw()

    def nearest_snap(self, scene_point, radius_px=12):
        best, distance = None, None
        for (x, y), part in self.snaps:
            view_point = self.mapFromScene(QPointF(x, -y))
            d = (view_point - self.mapFromScene(scene_point)).manhattanLength()
            if d <= radius_px and (distance is None or d < distance):
                best, distance = ((x, y), part), d
        return best

    def add_measure_point(self, point):
        self.measure_points = (self.measure_points + [point])[-2:] if len(self.measure_points) < 2 else [point]
        self.redraw()
        if len(self.measure_points) == 2:
            (x1, y1), (x2, y2) = self.measure_points
            self.measured.emit(math.hypot(x2 - x1, y2 - y1))

    def mousePressEvent(self, event):
        scene_point = self.mapToScene(event.position().toPoint())
        if self.measuring and event.button() == Qt.LeftButton:
            snap = self.nearest_snap(scene_point)
            if snap is not None:
                self.add_measure_point(snap[0])
            event.accept(); return
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0):
            self.partClicked.emit(item.data(0))
        super().mousePressEvent(event)


class SchemaSketch(QWidget):
    """Dimensioned shape sketch; every dimension is an editable field placed on the drawing.

    The inline editors mirror the form fields (same parameter ids); the page owns
    parsing and validation, the sketch only places and forwards the text.
    """
    annotationClicked = Signal(str)
    inlineEdited = Signal(str, str)        # parameter id, text
    inlineCommitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.appearance = 'dark'; self.schema = None; self.active = None; self._hits = []; self.editors = {}
        self._editor_cache = {}
        self.setMinimumHeight(150); self.setAccessibleName('Ölçülü şekil şeması')
        self.setToolTip('Ölçüleri doğrudan çizim üzerinde yazabilirsiniz.')

    def set_schema(self, schema):
        self.schema = schema; self.active = None
        for editor in self.editors.values():
            editor.hide()                                  # kept for this schema; shown again on return
        key = ((schema or {}).get('shape_id'), (schema or {}).get('variant_id'))
        cache = self._editor_cache
        if key in cache:
            self.editors = cache[key]
            for editor in self.editors.values():
                editor.show()
            self.place_editors(); self.update(); return
        self.editors = cache[key] = {}
        for annotation in (schema or {}).get('dimension_annotations', []):
            key = annotation['parameter_id']
            editor = QLineEdit(self); editor.setAlignment(Qt.AlignCenter); editor.setFixedWidth(74)
            editor.setAccessibleName(f'Çizimde {annotation["text"]}'); editor.setToolTip(annotation['text'])
            editor.textEdited.connect(lambda text, k=key: self.inlineEdited.emit(k, text))
            editor.returnPressed.connect(lambda k=key: self.inlineCommitted.emit(k))
            editor.installEventFilter(self)
            self.editors[key] = editor; editor.show()
        self.place_editors(); self.update()

    def set_text(self, key, text):
        editor = self.editors.get(key)
        if editor is not None and editor.text() != text:
            editor.setText(text)

    def set_invalid(self, key, invalid):
        editor = self.editors.get(key)
        if editor is not None:
            colour = COLORS[self.appearance]['danger']
            editor.setStyleSheet(f'border: 1px solid {colour};' if invalid else '')

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.FocusIn:
            for key, editor in self.editors.items():
                if editor is watched:
                    self.highlight(key)
        return super().eventFilter(watched, event)

    def place_editors(self):
        if not self.schema or not self.editors or self.width() < 10:
            return
        to = self._transform()
        for annotation in self.schema.get('dimension_annotations', []):
            editor = self.editors.get(annotation['parameter_id'])
            if editor is None:
                continue
            a, b = to(annotation['start']), to(annotation['end'])
            mid = (a + b) / 2
            vertical = abs(a.x() - b.x()) < abs(a.y() - b.y())
            # Vertical dimensions get their field beside the dimension line, not on top of it.
            centre_x = mid.x() + editor.width() / 2 + 8 if vertical else mid.x()
            x = min(max(2, centre_x - editor.width() / 2), self.width() - editor.width() - 2)
            y = min(max(2, mid.y() - editor.height() / 2), self.height() - editor.height() - 2)
            editor.move(int(x), int(y))

    def resizeEvent(self, event):
        super().resizeEvent(event); self.place_editors()

    def highlight(self, parameter_id):
        self.active = parameter_id; self.update()

    def _transform(self):
        points = [pt for line in self.schema.get('sketch', []) for pt in line]
        points += [pt for a in self.schema.get('dimension_annotations', []) for pt in (a['start'], a['end'])]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        margin = 34
        scale = min((self.width() - 2 * margin) / max(x1 - x0, 1e-9), (self.height() - 2 * margin) / max(y1 - y0, 1e-9))
        ox = margin + (self.width() - 2 * margin - (x1 - x0) * scale) / 2 - x0 * scale
        oy = margin + (self.height() - 2 * margin - (y1 - y0) * scale) / 2 + y1 * scale
        return lambda p: QPointF(ox + p[0] * scale, oy - p[1] * scale)

    def paintEvent(self, event):
        colors = COLORS[self.appearance]
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(colors['canvas']))
        if not self.schema or not self.schema.get('sketch'):
            painter.setPen(QColor(colors['muted'])); painter.drawText(self.rect(), Qt.AlignCenter, 'Şema yok'); return
        to = self._transform()
        painter.setPen(QPen(QColor(colors['text']), 1.6))
        for line in self.schema['sketch']:
            for a, b in zip(line, line[1:]):
                painter.drawLine(to(a), to(b))
        font = QFont(self.font()); font.setBold(True); painter.setFont(font)
        self._hits = []
        for annotation in self.schema.get('dimension_annotations', []):
            active = annotation['parameter_id'] == self.active
            pen = QPen(QColor(colors['accent'] if active else colors['muted']), 2.4 if active else 1.)
            painter.setPen(pen)
            a, b = to(annotation['start']), to(annotation['end'])
            painter.drawLine(a, b)
            for end in (a, b):
                painter.drawEllipse(end, 2, 2)
            mid = (a + b) / 2
            box = QRectF(mid.x() - 14, mid.y() - 18, 28, 18)
            editor = self.editors.get(annotation['parameter_id'])
            if editor is not None:
                painter.drawText(QPointF(editor.x() - 14, editor.y() + editor.height() - 6), annotation['text'])
            else:
                painter.drawText(box, Qt.AlignCenter, annotation['text'])
            self._hits.append((box.adjusted(-6, -6, 6, 6), annotation['parameter_id']))

    def mousePressEvent(self, event):
        for box, parameter in self._hits:
            if box.contains(event.position()):
                self.annotationClicked.emit(parameter); return
        super().mousePressEvent(event)


class ReferenceSketch(QWidget):
    """Tiny wall section showing which surface (inner / mid / outer) dimensions refer to."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.appearance = 'dark'; self.reference = 'mid'; self.setFixedHeight(70)
        self.setAccessibleName('Ölçü yüzeyi şeması')

    def set_reference(self, reference):
        self.reference = reference; self.update()

    def paintEvent(self, event):
        colors = COLORS[self.appearance]
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        w = self.width(); top, bottom = 8, 48
        fill = QColor(colors['muted']); fill.setAlpha(60)
        painter.fillRect(QRectF(8, top, w - 16, bottom - top), fill)
        for key, y, title in (('outer', top, 'dış'), ('mid', (top + bottom) / 2, 'orta'), ('inner', bottom, 'iç')):
            active = key == self.reference
            painter.setPen(QPen(QColor(colors['accent'] if active else colors['muted']), 2.4 if active else .8,
                                Qt.SolidLine if active else Qt.DotLine))
            painter.drawLine(QPointF(8, y), QPointF(w - 60, y))
            painter.drawText(QPointF(w - 54, y + 4), title + (' ◀' if active else ''))
        painter.setPen(QColor(colors['muted'])); painter.drawText(QPointF(8, 66), 'sac kesiti · iç taraf altta')
