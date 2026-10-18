"""Render existing engineering geometry as native QGraphicsScene vector items.

The drawing protocol retains geometry and engineering labels independently of
the UI toolkit. There are no Tk widgets, Tcl calls, bitmap screenshots or web views.
"""

from math import atan2, cos, sin, pi
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QPolygonF, QPainterPath, QFont, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsTextItem


class VectorScene(QGraphicsScene):
    def __init__(self, width, height, parent=None):
        super().__init__(parent)
        self.width, self.height = width, height
        self.background = '#1C2431'
        self.tagged = {}
        self.setSceneRect(0, 0, width, height)

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def configure(self, **options):
        if 'background' in options:
            self.background = options['background']
            self.setBackgroundBrush(QBrush(QColor(self.background)))

    def cget(self, name):
        return self.background if name == 'background' else None

    def delete(self, tag):
        if not isinstance(tag, str):
            self.removeItem(tag)
            for values in self.tagged.values():
                if tag in values:
                    values.remove(tag)
            return
        if tag == 'all':
            self.clear()
            self.tagged.clear()
        else:
            for item in self.tagged.pop(tag, []):
                self.removeItem(item)

    def _pen(self, options, *, line=False):
        color = options.get('fill' if line else 'outline', '#8899AA')
        pen = QPen(QColor(color)) if color else QPen(Qt.NoPen)
        pen.setWidthF(float(options.get('width', 1)))
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        if options.get('dash'):
            pen.setDashPattern([float(x) for x in options['dash']])
        return pen

    def _brush(self, options):
        color = options.get('fill', '')
        return QBrush(QColor(color)) if color else QBrush(Qt.NoBrush)

    def _register(self, item, options):
        tags = options.get('tags', ())
        if isinstance(tags, str):
            tags = (tags,)
        for tag in tags:
            self.tagged.setdefault(tag, []).append(item)
        return item

    @staticmethod
    def _points(points):
        if len(points) == 1 and isinstance(points[0], (tuple, list)):
            points = points[0]
        return [float(x) for x in points]

    def create_line(self, *points, **options):
        values = self._points(points)
        path = QPainterPath(QPointF(values[0], values[1]))
        for i in range(2, len(values), 2):
            path.lineTo(values[i], values[i + 1])
        item = self.addPath(path, self._pen(options, line=True))
        arrow = options.get('arrow')
        if arrow in ('last', 'both'):
            self._arrow(values[-4:], options)
        if arrow in ('first', 'both'):
            self._arrow((values[2], values[3], values[0], values[1]), options)
        return self._register(item, options)

    def _arrow(self, coords, options):
        x0, y0, x, y = coords
        angle = atan2(y - y0, x - x0)
        length = float(options.get('arrowshape', (6, 8, 3))[1])
        half = float(options.get('arrowshape', (6, 8, 3))[2])
        points = QPolygonF([QPointF(x, y), QPointF(x - length*cos(angle) + half*sin(angle), y - length*sin(angle) - half*cos(angle)),
                           QPointF(x - length*cos(angle) - half*sin(angle), y - length*sin(angle) + half*cos(angle))])
        self.addPolygon(points, QPen(Qt.NoPen), QBrush(QColor(options.get('fill', '#8899AA'))))

    def create_rectangle(self, *box, **options):
        x0, y0, x1, y1 = self._points(box)
        return self._register(self.addRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized(),
                                          self._pen(options), self._brush(options)), options)

    def create_polygon(self, *points, **options):
        values = self._points(points)
        polygon = QPolygonF([QPointF(values[i], values[i + 1]) for i in range(0, len(values), 2)])
        return self._register(self.addPolygon(polygon, self._pen(options), self._brush(options)), options)

    def create_oval(self, *box, **options):
        x0, y0, x1, y1 = self._points(box)
        return self._register(self.addEllipse(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized(),
                                             self._pen(options), self._brush(options)), options)

    def create_arc(self, *box, **options):
        x0, y0, x1, y1 = self._points(box)
        rect = QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized()
        path = QPainterPath()
        path.arcMoveTo(rect, float(options.get('start', 0)))
        path.arcTo(rect, float(options.get('start', 0)), float(options.get('extent', 90)))
        return self._register(self.addPath(path, self._pen(options)), options)

    def create_text(self, x, y, **options):
        item = QGraphicsTextItem()
        font_value = options.get('font', ('Segoe UI', -12))
        font = QFont(font_value[0])
        font.setPixelSize(max(1, abs(int(font_value[1]))))
        font.setBold('bold' in font_value[2:])
        item.setFont(font)
        item.setDefaultTextColor(QColor(options.get('fill', '#E8EEF7')))
        item.setPlainText(str(options.get('text', '')))
        if options.get('width'):
            item.setTextWidth(float(options['width']))
        document_options = item.document().defaultTextOption()
        document_options.setAlignment({'left': Qt.AlignLeft, 'right': Qt.AlignRight}.get(options.get('justify'), Qt.AlignCenter))
        item.document().setDefaultTextOption(document_options)
        bounds = item.boundingRect()
        anchor = options.get('anchor', 'center')
        dx = 0 if 'w' in anchor else bounds.width() if 'e' in anchor else bounds.width()/2
        dy = 0 if 'n' in anchor else bounds.height() if 's' in anchor else bounds.height()/2
        item.setPos(float(x) - dx, float(y) - dy)
        self.addItem(item)
        return self._register(item, options)

    def bbox(self, item):
        if isinstance(item, str):
            items = self.tagged.get(item, [])
            rect = QRectF()
            for value in items:
                rect = rect.united(value.sceneBoundingRect())
        else:
            rect = item.sceneBoundingRect()
        return rect.left(), rect.top(), rect.right(), rect.bottom()


class EngineeringDiagram(QGraphicsView):
    def __init__(self, *, width=520, height=320, parent=None):
        super().__init__(parent)
        self.vector = VectorScene(width, height, self)
        self.setScene(self.vector)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setMinimumSize(160, 190)
        self.renderer = None

    def render_geometry(self, renderer):
        self.renderer = renderer
        renderer(self.vector)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
