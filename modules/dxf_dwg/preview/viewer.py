"""Local Qt mesh viewer: depth-buffered OpenGL with an asynchronous CPU fallback.

Both paths render the same native tessellation. No browser, localhost service,
remote assets, CAD screenshots or reconstructed DXF solids are involved.
"""

import math
import threading

import numpy as np
import shiboken6
from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable, QThreadPool, QTimer
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QStackedLayout, QApplication


# SolidWorks: front XY (+Z), top XZ (+Y), right YZ (+X); Y is up.
VIEWS = {'İzometrik': (-45, math.degrees(math.asin(1/math.sqrt(3)))),
         'Ön': (0, 0), 'Arka': (180, 0), 'Sağ': (-90, 0),
         'Sol': (90, 0), 'Üst': (0, 90), 'Alt': (0, -90)}


TIP = 'Sol sürükle: döndür · Sağ/orta sürükle: kaydır · Tekerlek: yakınlaştır · Küp: standart görünüm'


# Drawing surfaces follow the theme's ``canvas`` token; this is only the value
# used before the page reports its appearance (dark is the application default).
DEFAULT_CANVAS = '#1A1B1E'


class Camera:
    def __init__(self):
        self.yaw, self.pitch = VIEWS['İzometrik']
        self.zoom, self.pan_x, self.pan_y = 1., 0., 0.
        self.perspective = False
        self.edges = True

    def fit(self):
        self.zoom, self.pan_x, self.pan_y = 1., 0., 0.

    def state(self):
        return self.yaw, self.pitch, self.zoom, self.pan_x, self.pan_y, self.perspective, self.edges


def matrices(state, aspect):
    yaw, pitch, zoom, x, y, perspective, _ = state
    a, b = math.radians(yaw), math.radians(pitch)
    ry = np.array([[math.cos(a), 0, math.sin(a), 0], [0, 1, 0, 0],
                   [-math.sin(a), 0, math.cos(a), 0], [0, 0, 0, 1]], dtype=float)
    rx = np.array([[1, 0, 0, 0], [0, math.cos(b), -math.sin(b), 0],
                   [0, math.sin(b), math.cos(b), 0], [0, 0, 0, 1]], dtype=float)
    view = rx @ ry
    view[0, 3], view[1, 3], view[2, 3] = x, y, -6
    if perspective:
        f = 1 / math.tan(math.radians(35) / 2) * zoom
        projection = np.array([[f/aspect, 0, 0, 0], [0, f, 0, 0],
                               [0, 0, -101/99, -200/99], [0, 0, -1, 0]])
    else:
        extent = 2.05 / zoom
        projection = np.diag([1/(extent*aspect), 1/extent, -2/99, 1.])
        projection[2, 3] = -101/99
    return view, projection @ view


def normalized(mesh):
    low, high = np.array(mesh.bounds[:3]), np.array(mesh.bounds[3:])
    center, scale = (low+high)/2, 2/float(np.max(high-low))
    vertices = (np.frombuffer(mesh.positions, dtype='<f4').reshape((-1, 3)).astype(float) - center) * scale
    edges = (np.frombuffer(mesh.edges, dtype='<f4').reshape((-1, 3)).astype(float) - center) * scale
    normals = np.frombuffer(mesh.normals, dtype='<f4').reshape((-1, 3))
    return vertices, normals, edges


def gradient(background):
    """CAD-style vertical gradient (top, bottom) around the theme canvas colour.

    The middle of the view stays within a few levels of the canvas token, so a
    through hole still shows the theme background.
    """
    c = QColor(background) if not isinstance(background, tuple) else QColor(*background)
    rgb = np.array([c.red(), c.green(), c.blue()])
    if c.lightness() > 128:
        top, bottom = rgb + (6, 6, 6), rgb - (10, 8, 4)
    else:
        top, bottom = rgb + (16, 18, 22), rgb - (12, 12, 12)
    return tuple(int(v) for v in np.clip(top, 0, 255)), tuple(int(v) for v in np.clip(bottom, 0, 255))


GRID_FADE = 2.6   # normalized units; the part fits in [-1, 1]


def grid_lines(vertices, step=.25, extent=GRID_FADE):
    """Floor grid just under the part (Y is up), as GL line segments."""
    floor = float(vertices[:, 1].min()) - .002 if len(vertices) else -1.
    ticks = np.arange(-extent, extent + 1e-9, step)
    lines = []
    for v in ticks:
        lines += [(v, floor, -extent), (v, floor, extent), (-extent, floor, v), (extent, floor, v)]
    return np.array(lines, dtype=float)


def grid_colour(background):
    return (0., 0., 0., .22) if QColor(background).lightness() > 128 else (1., 1., 1., .13)


BASE_COLOUR = np.array([155, 172, 188], dtype=float)
EDGE_COLOUR = (63, 77, 91)


def _fill(triangles, shade, ids, size, depth, pixels, stop):
    """Rasterize triangles whose screen bounding box fits in size = (columns, rows), all at once.

    Every candidate sample gets barycentric coordinates and a depth; the
    nearest sample per pixel (also against the existing depth buffer) wins.
    Same coverage rule and depth range as the per-triangle loop it replaces.
    """
    height, width = depth.shape
    columns, rows = size
    dx, dy = np.arange(columns, dtype=np.float32), np.arange(rows, dtype=np.float32)
    flat_depth, flat_pixels = depth.reshape(-1), pixels.reshape(-1, 3)
    batch = max(1, 300000 // (columns*rows))
    for begin in range(0, len(ids), batch):
        if stop.is_set():
            return False
        chunk = ids[begin:begin + batch]
        t = triangles[chunk].astype(np.float32)
        x0 = np.maximum(0, np.floor(t[:, :, 0].min(axis=1)))
        y0 = np.maximum(0, np.floor(t[:, :, 1].min(axis=1)))
        x1 = np.minimum(width-1, np.ceil(t[:, :, 0].max(axis=1)))
        y1 = np.minimum(height-1, np.ceil(t[:, :, 1].max(axis=1)))
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        den = (b[:, 1]-c[:, 1])*(a[:, 0]-c[:, 0]) + (c[:, 0]-b[:, 0])*(a[:, 1]-c[:, 1])
        good = np.abs(den) >= 1e-10
        den = np.where(good, den, np.float32(1))
        # Barycentrics are affine in x and y: u = u0 + ux*dx + uy*dy.
        ux, uy = (b[:, 1]-c[:, 1])/den, (c[:, 0]-b[:, 0])/den
        vx, vy = (c[:, 1]-a[:, 1])/den, (a[:, 0]-c[:, 0])/den
        u0 = ux*(x0-c[:, 0]) + uy*(y0-c[:, 1])
        v0 = vx*(x0-c[:, 0]) + vy*(y0-c[:, 1])
        u = u0[:, None, None] + uy[:, None, None]*dy[None, :, None] + ux[:, None, None]*dx[None, None, :]
        v = v0[:, None, None] + vy[:, None, None]*dy[None, :, None] + vx[:, None, None]*dx[None, None, :]
        w = 1-u-v
        mask = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8)
        mask &= (x0[:, None, None] + dx[None, None, :] <= x1[:, None, None])
        mask &= (y0[:, None, None] + dy[None, :, None] <= y1[:, None, None])
        mask &= good[:, None, None]
        triangle, row, column = np.nonzero(mask)
        if not len(triangle):
            continue
        uu, vv = u[triangle, row, column], v[triangle, row, column]
        z = (uu*a[triangle, 2] + vv*b[triangle, 2] + (1-uu-vv)*c[triangle, 2]).astype(float)
        inside = (z >= -1) & (z <= 1)
        triangle, z = triangle[inside], z[inside]
        index = ((y0[triangle] + row[inside])*width + x0[triangle] + column[inside]).astype(np.int64)
        before = flat_depth[index]
        np.minimum.at(flat_depth, index, z)
        won = (z == flat_depth[index]) & (z < before)
        flat_pixels[index[won]] = (BASE_COLOUR[None, :] * shade[chunk[triangle[won]]][:, None]).astype(np.uint8)
    return True


def raster(mesh, width, height, state, stop, background=(248, 248, 248)):
    """True depth testing; holes remain holes, independent of triangle order.

    ``background`` is the RGB canvas colour (the theme's ``canvas`` token), or a
    (top, bottom) pair of RGB colours for a vertical gradient.
    Triangles are rasterized in vectorized batches grouped by screen size, so
    a CPU frame of a few thousand triangles takes milliseconds, not a
    Python-level loop per triangle (the old cause of a stuttering rotation
    when OpenGL is unavailable).
    """
    width, height = max(1, width), max(1, height)
    vertices, normals, edges = normalized(mesh)
    view, mvp = matrices(state, width/height)
    def project(points):
        clip = np.c_[points, np.ones(len(points))] @ mvp.T
        return clip[:, :3] / clip[:, 3, None]
    p = project(vertices)
    p[:, 0] = (p[:, 0]+1) * .5 * (width-1)
    p[:, 1] = (1-p[:, 1]) * .5 * (height-1)
    pixels = np.empty((height, width, 3), dtype=np.uint8)
    if len(background) == 2:
        top, bottom = np.array(background, dtype=float)
        t = np.linspace(0, 1, height)[:, None]
        pixels[:] = np.rint(top + (bottom - top) * t)[:, None, :].astype(np.uint8)
    else:
        pixels[:] = background
    depth = np.full((height, width), np.inf)
    light = np.array([.25, .45, 1.]); light /= np.linalg.norm(light)
    shade = .42 + .58 * np.abs((normals[::3] @ view[:3, :3].T) @ light)
    triangles = p.reshape((-1, 3, 3))
    low, high = triangles[:, :, :2].min(axis=1), triangles[:, :, :2].max(axis=1)
    keep = ((triangles[:, :, 2].max(axis=1) >= -1) & (triangles[:, :, 2].min(axis=1) <= 1)
            & (high[:, 0] >= 0) & (high[:, 1] >= 0) & (low[:, 0] <= width-1) & (low[:, 1] <= height-1)
            & np.isfinite(triangles).all(axis=(1, 2)))
    span = np.ceil(np.minimum(high, [width-1, height-1])) - np.floor(np.maximum(low, 0)) + 1
    limits = (2, 4, 8, 16, 32, 64, 128, 256)
    bucket = np.searchsorted(limits, np.clip(span, 1, None))      # per axis; slivers stay cheap
    large = keep & (bucket.max(axis=1) >= len(limits))
    for bx, by in sorted(set(map(tuple, bucket[keep & ~large]))):
        ids = np.nonzero(keep & ~large & (bucket[:, 0] == bx) & (bucket[:, 1] == by))[0]
        if not _fill(triangles, shade, ids, (limits[bx], limits[by]), depth, pixels, stop):
            return None
    for i in np.nonzero(large)[0]:   # rare very large triangles
        if stop.is_set():
            return None
        x0, y0 = np.floor(low[i]).astype(int); x1, y1 = np.ceil(high[i]).astype(int)
        x0, x1, y0, y1 = max(0, x0), min(width-1, x1), max(0, y0), min(height-1, y1)
        a, b, c = triangles[i]
        denominator = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(denominator) < 1e-10:
            continue
        yy, xx = np.mgrid[y0:y1+1, x0:x1+1]
        u = ((b[1]-c[1])*(xx-c[0]) + (c[0]-b[0])*(yy-c[1])) / denominator
        v = ((c[1]-a[1])*(xx-c[0]) + (a[0]-c[0])*(yy-c[1])) / denominator
        w = 1-u-v
        z = u*a[2]+v*b[2]+w*c[2]
        old = depth[y0:y1+1, x0:x1+1]
        mask = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8) & (z < old) & (z >= -1) & (z <= 1)
        old[mask] = z[mask]
        pixels[y0:y1+1, x0:x1+1][mask] = BASE_COLOUR * shade[i]
    if state[-1] and len(edges):
        if stop.is_set():
            return None
        lines = project(edges).reshape((-1, 2, 3))
        lines[:, :, 0] = (lines[:, :, 0]+1)*.5*(width-1)
        lines[:, :, 1] = (1-lines[:, :, 1])*.5*(height-1)
        lines = lines[np.isfinite(lines).all(axis=(1, 2))]
        a, b = lines[:, 0], lines[:, 1]
        counts = np.minimum(2*max(width, height),
                            np.maximum(2, (np.max(np.abs(b[:, :2]-a[:, :2]), axis=1)+1).astype(int)))
        line = np.repeat(np.arange(len(lines)), counts)
        start = np.repeat(np.cumsum(counts)-counts, counts)
        step = (np.arange(counts.sum())-start) / np.repeat(np.maximum(counts-1, 1), counts)
        points = a[line] + step[:, None]*(b[line]-a[line])
        xy = np.rint(points[:, :2]).astype(int)
        good = (xy[:, 0] >= 0) & (xy[:, 0] < width) & (xy[:, 1] >= 0) & (xy[:, 1] < height)
        xy, z = xy[good], points[good, 2]
        visible = (z <= depth[xy[:, 1], xy[:, 0]]+1e-5) & (z >= -1) & (z <= 1)
        pixels[xy[visible, 1], xy[visible, 0]] = EDGE_COLOUR
    return QImage(pixels.data, width, height, pixels.strides[0], QImage.Format_RGB888).copy()


class RenderSignals(QObject):
    done = Signal(int, object)


class RenderJob(QRunnable):
    def __init__(self, generation, mesh, size, state, stop, background=(248, 248, 248)):
        super().__init__()
        self.generation, self.mesh, self.size, self.state, self.stop = generation, mesh, size, state, stop
        self.background = background
        self.signals = RenderSignals()

    def run(self):
        try:
            result = raster(self.mesh, *self.size, self.state, self.stop, self.background)
        except Exception:
            result = None
        try:
            self.signals.done.emit(self.generation, result)
        except RuntimeError:
            # Qt can destroy the emitter while a native render is finishing
            # at shutdown. A live view must still receive cancelled results
            # so it can release its running slot and draw the next frame.
            if shiboken6.isValid(self.signals):
                raise


class SoftwareCanvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.image = QImage()
        self.background = QColor(DEFAULT_CANVAS)

    def paintEvent(self, event):
        painter = QPainter(self)
        top, bottom = gradient(self.background)
        fill = QLinearGradient(0, 0, 0, max(1, self.height()))
        fill.setColorAt(0, QColor(*top)); fill.setColorAt(1, QColor(*bottom))
        painter.fillRect(self.rect(), fill)
        if not self.image.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(self.rect(), self.image)


def gl_canvas(parent):
    # Load native graphics only on supported GUI platforms. The QObject subclass
    # is module-level, rather than closing over an individual preview widget.
    from .opengl import OpenGLCanvas
    return OpenGLCanvas(parent)

CUBE_FACES = (('Ön', (0, 0, 1)), ('Arka', (0, 0, -1)), ('Sağ', (1, 0, 0)),
              ('Sol', (-1, 0, 0)), ('Üst', (0, 1, 0)), ('Alt', (0, -1, 0)))
AXES = (('X', (1, 0, 0), '#E5484D'), ('Y', (0, 1, 0), '#46A758'), ('Z', (0, 0, 1), '#3E7BFA'))


def face_corners(normal):
    n = np.array(normal, dtype=float); axis = int(np.argmax(np.abs(n)))
    u, v = [np.eye(3)[i] for i in range(3) if i != axis]
    if np.cross(u, v) @ n < 0:
        u, v = v, u
    return [n + a*u + b*v for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


class Overlay(QWidget):
    """View cube (click a face for that standard view) and axis triad, drawn over either canvas."""

    SIZE, MARGIN = 84, 10

    def __init__(self, view):
        super().__init__(view)
        self.view = view; self.hover = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def rotation(self):
        view, _ = matrices(self.view.camera.state(), 1.)
        return view[:3, :3]

    def cube_rect(self):
        s = self.SIZE
        return QRectF(self.width() - s - self.MARGIN, self.MARGIN, s, s)

    def faces(self):
        """Visible faces, back to front: (name, screen polygon, facing)."""
        rotation, rect = self.rotation(), self.cube_rect()
        centre, scale = rect.center(), rect.width() * .27
        shown = []
        for name, normal in CUBE_FACES:
            facing = float((rotation @ np.array(normal, dtype=float))[2])
            if facing <= 1e-3:
                continue
            points = [rotation @ corner for corner in face_corners(normal)]
            polygon = QPolygonF([QPointF(centre.x() + p[0]*scale, centre.y() - p[1]*scale) for p in points])
            shown.append((name, polygon, facing))
        return sorted(shown, key=lambda face: face[2])

    def face_at(self, point):
        for name, polygon, _ in reversed(self.faces()):
            if polygon.containsPoint(QPointF(point), Qt.OddEvenFill):
                return name
        return None

    def set_hover(self, name):
        if name != self.hover:
            self.hover = name; self.update()

    def paintEvent(self, event):
        if self.view.mesh is None:
            return
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        light = self.view.background.lightness() > 128
        ink = QColor('#2B2F36') if light else QColor('#DDE2E8')
        fill = QColor('#F4F6F8') if light else QColor('#3A3F47')
        accent = QColor('#3E7BFA')
        font = QFont(self.font()); font.setPixelSize(10); font.setBold(True); painter.setFont(font)
        for name, polygon, facing in self.faces():
            colour = QColor(accent) if name == self.hover else QColor(fill)
            colour.setAlphaF(.92 if name == self.hover else .78)
            shade = QColor(colour).darker(int(100 + (1 - facing) * 45))
            painter.setPen(QPen(ink if not light else QColor('#9AA3AE'), 1)); painter.setBrush(shade)
            painter.drawPolygon(polygon)
            if facing > .45:
                painter.setPen(QColor('white') if name == self.hover else ink)
                painter.drawText(polygon.boundingRect(), Qt.AlignCenter, name)
        rotation = self.rotation(); origin = QPointF(30, self.height() - 30)
        for label_, axis, colour in AXES:
            d = rotation @ np.array(axis, dtype=float)
            tip = QPointF(origin.x() + d[0]*22, origin.y() - d[1]*22)
            painter.setPen(QPen(QColor(colour), 2)); painter.drawLine(origin, tip)
            painter.setPen(QColor(colour))
            painter.drawText(QRectF(tip.x() + d[0]*7 - 6, tip.y() - d[1]*7 - 7, 12, 14), Qt.AlignCenter, label_)
        painter.end()


class MeshView(QWidget):
    frameReady = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(80, 80)
        self.setAccessibleName('Gerçek SolidWorks parçası · 3D görünüm')
        self.setToolTip(TIP)
        self.camera, self.mesh = Camera(), None
        self.grid = True
        self.background = QColor(DEFAULT_CANVAS)
        self.auto_fit = True
        self.pool = QThreadPool(self); self.pool.setMaxThreadCount(1)
        self.generation = 0; self.running = None; self.pending = False
        # Mesh/canvas identity: a frame of the same part and canvas may be
        # shown while dragging even if the camera has moved on since.
        self.scene_generation = 0; self.dragging = False; self.context_checks = 0
        self.software = SoftwareCanvas(self)
        self.software.background = self.background
        self.stack = QStackedLayout(self); self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.software)
        self.hardware = None
        if QApplication.platformName() not in ('offscreen', 'minimal'):
            self.hardware = gl_canvas(self)
            self.hardware.failed.connect(self.fallback, Qt.QueuedConnection)
            self.stack.addWidget(self.hardware); self.stack.setCurrentWidget(self.hardware)
        # Child canvases paint only; all interaction is handled by this wrapper.
        for canvas in (self.software, self.hardware):
            if canvas: canvas.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay = Overlay(self); self.overlay.raise_()
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(35)
        self.timer.timeout.connect(self.render)
        # A slot bound to this QWidget is disconnected during its teardown.
        # Capture only the stop token so cancellation happens before Qt waits
        # for the child thread pool to finish.
        render_state = self._render_state = [None]
        def cancel_on_destroy(*_):
            if render_state[0] is not None:
                render_state[0].set()
        self.destroyed.connect(cancel_on_destroy)

    def leaveEvent(self, event):
        self.overlay.set_hover(None)
        super().leaveEvent(event)

    def set_background(self, color):
        """Repaint both render paths on the theme's canvas colour."""
        color = QColor(color)
        if color == self.background:
            return
        self.background = color
        self.software.background = color
        self.software.image = QImage()  # the old frame carries the old canvas
        self.scene_generation += 1
        self.software.update()
        if self.hardware: self.hardware.update()
        self.changed()

    def cancel_render(self, *args):
        if self.running: self.running.stop.set()

    @Slot(str)
    def fallback(self, message=''):
        if message:
            self.setToolTip(TIP + '\n' + message)
        self.stack.setCurrentWidget(self.software)
        self.overlay.raise_()   # the stack raises its current canvas
        self.render()

    def set_mesh(self, mesh):
        if mesh is not None and mesh is self.mesh:
            return
        self.mesh = mesh
        self.generation += 1; self.scene_generation += 1
        self.software.image = QImage(); self.software.update()
        if self.hardware: self.hardware.dirty = True; self.hardware.update()
        self.overlay.update()
        self.cancel_render()
        self.auto_fit = True
        self.fit_camera()
        self.timer.start()

    def changed(self):
        self.generation += 1
        self.overlay.update()
        if self.hardware: self.hardware.update()
        if self.dragging:
            # CPU fallback while dragging: let the running frame finish and
            # render at most every timer interval, instead of restarting the
            # debounce on every mouse move (which showed nothing until the
            # pointer stopped).
            if not self.timer.isActive():
                self.timer.start()
            return
        self.cancel_render()
        self.timer.start()

    def view(self, name):
        self.camera.yaw, self.camera.pitch = VIEWS[name]
        self.fit()

    def fit(self):
        self.auto_fit = True
        self.fit_camera(); self.changed()

    def fit_camera(self):
        self.camera.fit()
        if self.mesh is None:
            return
        low, high = np.array(self.mesh.bounds[:3]), np.array(self.mesh.bounds[3:])
        corners = np.array([(x, y, z) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])])
        corners = (corners-(low+high)/2)*2/float(np.max(high-low))
        _, mvp = matrices(self.camera.state(), max(1, self.width())/max(1, self.height()))
        clip = np.c_[corners, np.ones(8)] @ mvp.T
        extent = np.max(np.abs(clip[:, :2]/clip[:, 3, None]))
        if extent > 0:
            self.camera.zoom = min(50., max(.05, .88/extent))

    def render(self):
        if self.mesh is None or self.stack.currentWidget() is self.hardware:
            return
        if self.running:
            self.pending = True
            return
        # Render off the GUI thread; a large part never blocks input or CAD jobs.
        # While dragging, a lighter frame keeps rotation fluid; the release
        # renders one exact frame at the normal resolution.
        limit = (400, 300) if self.dragging else (640, 480)
        factor = min(1., limit[0]/max(1, self.width()), limit[1]/max(1, self.height()))
        size = max(1, int(self.width()*factor)), max(1, int(self.height()*factor))
        task = RenderJob(self.generation, self.mesh, size, self.camera.state(), threading.Event(), gradient(self.background))
        task.signals.done.connect(self.rendered, Qt.QueuedConnection)
        task.scene_generation = self.scene_generation
        self.running = task
        self._render_state[0] = task.stop
        self.pool.start(task)

    @Slot(int, object)
    def rendered(self, generation, image):
        task, self.running = self.running, None
        self._render_state[0] = None
        same_scene = task is not None and getattr(task, 'scene_generation', None) == self.scene_generation
        if image is not None and (generation == self.generation or (self.dragging and same_scene)):
            self.software.image = image; self.software.update(); self.frameReady.emit()
        if self.pending or generation != self.generation:
            self.pending = False; self.timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect()); self.overlay.raise_()
        if self.auto_fit: self.fit_camera()
        self.changed()

    def showEvent(self, event):
        super().showEvent(event)
        if self.hardware:
            QTimer.singleShot(150, self.check_context)

    def check_context(self):
        if not self.hardware or self.stack.currentWidget() is not self.hardware or self.hardware.isValid():
            self.context_checks = 0
            return
        # A context is created on the first real paint. A view that is not yet
        # laid out (hidden, zero size, page still opening) is not a GL failure:
        # retry for a few seconds before switching permanently to the CPU path.
        if not (self.isVisible() and self.width() > 1 and self.height() > 1):
            return  # showEvent checks again once the view is really on screen
        if self.context_checks < 10:
            self.context_checks += 1
            self.hardware.update()
            QTimer.singleShot(150, self.check_context)
            return
        self.fallback('OpenGL bağlamı oluşturulamadı; yazılımsal görüntüleyici etkin.')

    def mousePressEvent(self, event):
        face = self.overlay.face_at(event.position()) if self.mesh is not None else None
        if face and event.button() == Qt.LeftButton:
            self.view(face); event.accept(); return
        self.last = event.position(); self.dragging = True
        event.accept()

    def mouseReleaseEvent(self, event):
        if not self.dragging:
            event.accept(); return
        self.dragging = False
        self.changed()  # one exact frame for the final camera
        event.accept()

    def mouseMoveEvent(self, event):
        if not event.buttons():
            self.overlay.set_hover(self.overlay.face_at(event.position()) if self.mesh is not None else None)
            return
        if not hasattr(self, 'last') or not self.dragging:
            return
        delta = event.position()-self.last; self.last = event.position()
        self.auto_fit = False
        if event.buttons() & Qt.LeftButton:
            self.camera.yaw = (self.camera.yaw+delta.x()*.7) % 360
            self.camera.pitch = (self.camera.pitch+delta.y()*.7) % 360
        else:
            self.camera.pan_x += delta.x()*4/max(1, self.height())/self.camera.zoom
            self.camera.pan_y -= delta.y()*4/max(1, self.height())/self.camera.zoom
        self.changed(); event.accept()

    def wheelEvent(self, event):
        self.auto_fit = False
        self.camera.zoom = min(50., max(.05, self.camera.zoom*1.15**(event.angleDelta().y()/120)))
        self.changed(); event.accept()
