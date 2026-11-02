"""Local Qt mesh viewer: depth-buffered OpenGL with an asynchronous CPU fallback.

Both paths render the same native tessellation. No browser, localhost service,
remote assets, CAD screenshots or reconstructed DXF solids are involved.
"""

import math
import threading

import numpy as np
from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable, QThreadPool, QTimer
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QWidget, QStackedLayout, QApplication


# SolidWorks: front XY (+Z), top XZ (+Y), right YZ (+X); Y is up.
VIEWS = {'İzometrik': (-45, math.degrees(math.asin(1/math.sqrt(3)))),
         'Ön': (0, 0), 'Arka': (180, 0), 'Sağ': (-90, 0),
         'Sol': (90, 0), 'Üst': (0, 90), 'Alt': (0, -90)}


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


def raster(mesh, width, height, state, stop, background=(248, 248, 248)):
    """True depth testing; holes remain holes, independent of triangle order.

    ``background`` is the RGB canvas colour (the theme's ``canvas`` token).
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
    pixels = np.empty((height, width, 3), dtype=np.uint8); pixels[:] = background
    depth = np.full((height, width), np.inf)
    light = np.array([.25, .45, 1.]); light /= np.linalg.norm(light)
    shade = .42 + .58 * np.abs((normals[::3] @ view[:3, :3].T) @ light)
    for i, triangle in enumerate(p.reshape((-1, 3, 3))):
        if i % 32 == 0 and stop.is_set():
            return None
        if np.max(triangle[:, 2]) < -1 or np.min(triangle[:, 2]) > 1:
            continue
        x0, y0 = np.floor(triangle[:, :2].min(axis=0)).astype(int)
        x1, y1 = np.ceil(triangle[:, :2].max(axis=0)).astype(int)
        x0, x1, y0, y1 = max(0, x0), min(width-1, x1), max(0, y0), min(height-1, y1)
        if x0 > x1 or y0 > y1:
            continue
        a, b, c = triangle
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
        pixels[y0:y1+1, x0:x1+1][mask] = np.array([155, 172, 188]) * shade[i]
    if state[-1] and len(edges):
        lines = project(edges).reshape((-1, 2, 3))
        for i, (a, b) in enumerate(lines):
            if i % 64 == 0 and stop.is_set():
                return None
            a = a.copy(); b = b.copy()
            for point in (a, b):
                point[0] = (point[0]+1)*.5*(width-1)
                point[1] = (1-point[1])*.5*(height-1)
            samples = min(2*max(width, height), max(2, int(np.max(np.abs(b[:2]-a[:2])))+1))
            points = a + np.linspace(0, 1, samples)[:, None]*(b-a)
            xy = np.rint(points[:, :2]).astype(int)
            good = (xy[:, 0] >= 0) & (xy[:, 0] < width) & (xy[:, 1] >= 0) & (xy[:, 1] < height)
            xy, z = xy[good], points[good, 2]
            visible = (z <= depth[xy[:, 1], xy[:, 0]]+1e-5) & (z >= -1) & (z <= 1)
            pixels[xy[visible, 1], xy[visible, 0]] = (63, 77, 91)
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
        self.signals.done.emit(self.generation, result)


class SoftwareCanvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.image = QImage()
        self.background = QColor(DEFAULT_CANVAS)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background)
        if not self.image.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(self.rect(), self.image)


def gl_canvas(parent):
    # Load native graphics only on supported GUI platforms. The QObject subclass
    # is module-level, rather than closing over an individual preview widget.
    from .opengl import OpenGLCanvas
    return OpenGLCanvas(parent)

class MeshView(QWidget):
    frameReady = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(80, 80)
        self.setAccessibleName('Gerçek SolidWorks parçası · 3D görünüm')
        self.setToolTip('Sol sürükle: döndür · Sağ/orta sürükle: kaydır · Tekerlek: yakınlaştır')
        self.camera, self.mesh = Camera(), None
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
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(35)
        self.timer.timeout.connect(self.render)
        self.destroyed.connect(self.cancel_render)

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
            self.setToolTip('Sol sürükle: döndür · Sağ/orta sürükle: kaydır · Tekerlek: yakınlaştır\n' + message)
        self.stack.setCurrentWidget(self.software)
        self.render()

    def set_mesh(self, mesh):
        if mesh is not None and mesh is self.mesh:
            return
        self.mesh = mesh
        self.generation += 1; self.scene_generation += 1
        self.software.image = QImage(); self.software.update()
        if self.hardware: self.hardware.dirty = True; self.hardware.update()
        self.cancel_render()
        self.auto_fit = True
        self.fit_camera()
        self.timer.start()

    def changed(self):
        self.generation += 1
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
        factor = min(1., 640/max(1, self.width()), 480/max(1, self.height()))
        size = max(1, int(self.width()*factor)), max(1, int(self.height()*factor))
        task = RenderJob(self.generation, self.mesh, size, self.camera.state(), threading.Event(),
                         (self.background.red(), self.background.green(), self.background.blue()))
        task.signals.done.connect(self.rendered, Qt.QueuedConnection)
        task.scene_generation = self.scene_generation
        self.running = task
        self.pool.start(task)

    @Slot(int, object)
    def rendered(self, generation, image):
        task, self.running = self.running, None
        same_scene = task is not None and getattr(task, 'scene_generation', None) == self.scene_generation
        if image is not None and (generation == self.generation or (self.dragging and same_scene)):
            self.software.image = image; self.software.update(); self.frameReady.emit()
        if self.pending or generation != self.generation:
            self.pending = False; self.timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
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
        self.last = event.position(); self.dragging = True
        event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.changed()  # one exact frame for the final camera
        event.accept()

    def mouseMoveEvent(self, event):
        if not hasattr(self, 'last') or not event.buttons():
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
