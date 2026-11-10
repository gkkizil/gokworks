"""Native OpenGL canvas; module-level class keeps Qt subclass lifetime stable.

CAD-style frame: vertical background gradient from the theme canvas, a faint
floor grid, smooth two-light shading with a soft highlight, crisp edges and
4x multisampling. Overlays (view cube, axis triad) are painted by the viewer.
"""

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QMatrix4x4, QVector4D, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram

from .viewer import GRID_FADE, normalized, matrices, gradient, grid_lines, grid_colour, triangle_colours

HEADER = '#ifdef GL_ES\nprecision mediump float;\n#endif\n'
MESH_VERTEX = '''attribute vec3 position; attribute vec3 normal; attribute vec3 colour;
    uniform mat4 mvp; uniform mat4 modelView; varying vec3 n; varying vec3 c;
    void main(){gl_Position=mvp*vec4(position,1.0); n=(modelView*vec4(normal,0.0)).xyz; c=colour;}'''
MESH_FRAGMENT = HEADER + '''varying vec3 n; varying vec3 c;
    void main(){
        vec3 m=normalize(n); if(m.z<0.0) m=-m;            // two-sided: shade the side facing the viewer
        vec3 key=normalize(vec3(.35,.55,1.)), fill=normalize(vec3(-.65,-.25,.55));
        float light=.30+.58*max(dot(m,key),0.)+.20*max(dot(m,fill),0.)+.08*(m.y*.5+.5);
        float shine=pow(max(dot(m,normalize(key+vec3(0.,0.,1.))),0.),40.)*.28;
        gl_FragColor=vec4(c*light+shine,1.);
    }'''
LINE_VERTEX = '''attribute vec3 position; uniform mat4 mvp; varying vec3 p;
    void main(){gl_Position=mvp*vec4(position,1.0); p=position;}'''
LINE_FRAGMENT = HEADER + '''uniform vec4 colour; uniform float fade; varying vec3 p;
    void main(){float a=fade>0.0?clamp(1.0-length(p.xz)/fade,0.,1.):1.0; gl_FragColor=vec4(colour.rgb,colour.a*a);}'''
BACK_VERTEX = '''attribute vec2 position; attribute vec3 colour; varying vec3 c;
    void main(){gl_Position=vec4(position,0.999,1.0); c=colour;}'''
BACK_FRAGMENT = HEADER + 'varying vec3 c; void main(){gl_FragColor=vec4(c,1.);}'

EDGE = (.11, .13, .16, .9)
SURFACE = (.70, .745, .79)   # single-colour meshes (all modules but press brake scenes)


def vertex_colours(mesh):
    if not getattr(mesh, 'colours', b''):
        return np.broadcast_to(np.array(SURFACE), (len(mesh.positions)//12, 3))
    # Shader light peaks above 1; scale the same as SURFACE relates to BASE_COLOUR.
    return np.repeat(triangle_colours(mesh)/255*np.array(SURFACE)/(np.array([155, 172, 188])/255), 3, axis=0)


def program(parent, vertex, fragment):
    shader = QOpenGLShaderProgram(parent)
    if not (shader.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex)
            and shader.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment) and shader.link()):
        raise RuntimeError(shader.log())
    return shader


class OpenGLCanvas(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        fmt = QSurfaceFormat(); fmt.setDepthBufferSize(24); fmt.setVersion(2, 1); fmt.setSamples(4)
        self.setFormat(fmt)
        self.ready = False; self.dirty = True
        self.programs = {}; self.buffers = {}

    def initializeGL(self):
        try:
            self.f = self.context().functions()
            self.f.initializeOpenGLFunctions()
            self.context().aboutToBeDestroyed.connect(self.cleanup)
            self.programs = {'mesh': program(self, MESH_VERTEX, MESH_FRAGMENT),
                             'line': program(self, LINE_VERTEX, LINE_FRAGMENT),
                             'back': program(self, BACK_VERTEX, BACK_FRAGMENT)}
            for name in ('mesh', 'edges', 'grid', 'back'):
                buffer = QOpenGLBuffer()
                if not buffer.create():
                    raise RuntimeError('OpenGL buffer oluşturulamadı.')
                self.buffers[name] = buffer
            self.ready = True
        except Exception:
            self.failed.emit('OpenGL kullanılamıyor; yerel yazılımsal görüntüleyici etkin.')

    def cleanup(self):
        self.makeCurrent()
        for buffer in self.buffers.values():
            buffer.destroy()
        for shader in self.programs.values():
            shader.release(); shader.removeAllShaders(); shader.deleteLater()
        self.programs, self.buffers = {}, {}
        self.ready = False
        self.doneCurrent()

    def upload(self, name, array):
        data = np.ascontiguousarray(array, dtype='f4').tobytes()
        buffer = self.buffers[name]; buffer.bind(); buffer.allocate(data, len(data)); buffer.release()

    def draw_background(self, background):
        top, bottom = gradient(background)
        quad = np.array([(-1, -1, *bottom), (1, -1, *bottom), (-1, 1, *top), (1, 1, *top)], dtype=float)
        quad[:, 2:] /= 255
        self.upload('back', quad)
        p = self.programs['back']; p.bind(); self.buffers['back'].bind()
        p.enableAttributeArray('position'); p.enableAttributeArray('colour')
        p.setAttributeBuffer('position', 0x1406, 0, 2, 20); p.setAttributeBuffer('colour', 0x1406, 8, 3, 20)
        self.f.glDisable(0x0B71); self.f.glDrawArrays(0x0005, 0, 4)   # no depth test; GL_TRIANGLE_STRIP
        p.disableAttributeArray('position'); p.disableAttributeArray('colour'); self.buffers['back'].release(); p.release()

    def draw_lines(self, name, count, mvp, colour, fade=0.):
        p = self.programs['line']; p.bind(); self.buffers[name].bind()
        p.setUniformValue('mvp', mvp); p.setUniformValue('colour', QVector4D(*colour)); p.setUniformValue1f('fade', float(fade))
        p.enableAttributeArray('position'); p.setAttributeBuffer('position', 0x1406, 0, 3, 12)
        self.f.glDrawArrays(0x0001, 0, count)   # GL_LINES
        p.disableAttributeArray('position'); self.buffers[name].release(); p.release()

    def paintGL(self):
        parent = self.parentWidget()
        if not self.ready:
            return
        try:
            f = self.f
            background = parent.background  # theme ``canvas`` token
            f.glClearColor(background.redF(), background.greenF(), background.blueF(), 1.)
            f.glClear(0x4000 | 0x0100)  # GL_COLOR_BUFFER_BIT / DEPTH_BUFFER_BIT
            self.draw_background(background)
            if parent.mesh is None:
                return
            if self.dirty:
                vertices, normals, edges = normalized(parent.mesh)
                self.count, self.edge_count = len(vertices), len(edges)
                self.upload('mesh', np.c_[vertices, normals, vertex_colours(parent.mesh)]); self.upload('edges', edges)
                grid = grid_lines(vertices); self.grid_count = len(grid); self.upload('grid', grid)
                self.dirty = False
            view, mvp = matrices(parent.camera.state(), max(1, self.width())/max(1, self.height()))
            mvp, view = QMatrix4x4(*mvp.ravel().tolist()), QMatrix4x4(*view.ravel().tolist())
            f.glEnable(0x0B71)  # GL_DEPTH_TEST
            f.glEnable(0x0BE2); f.glBlendFunc(0x0302, 0x0303)  # GL_BLEND, SRC_ALPHA / ONE_MINUS_SRC_ALPHA
            if parent.grid and self.grid_count:
                f.glDepthMask(False)
                self.draw_lines('grid', self.grid_count, mvp, grid_colour(background), fade=GRID_FADE)
                f.glDepthMask(True)
            p = self.programs['mesh']; p.bind(); self.buffers['mesh'].bind()
            p.setUniformValue('mvp', mvp); p.setUniformValue('modelView', view)
            p.enableAttributeArray('position'); p.enableAttributeArray('normal'); p.enableAttributeArray('colour')
            p.setAttributeBuffer('position', 0x1406, 0, 3, 36)
            p.setAttributeBuffer('normal', 0x1406, 12, 3, 36)
            p.setAttributeBuffer('colour', 0x1406, 24, 3, 36)
            f.glEnable(0x8037); f.glPolygonOffset(1., 1.)   # GL_POLYGON_OFFSET_FILL: edges stay on top
            f.glDrawArrays(0x0004, 0, self.count)
            f.glDisable(0x8037)
            p.disableAttributeArray('position'); p.disableAttributeArray('normal'); p.disableAttributeArray('colour'); self.buffers['mesh'].release(); p.release()
            if parent.camera.edges and self.edge_count:
                self.draw_lines('edges', self.edge_count, mvp, EDGE)
            f.glDisable(0x0BE2)
            parent.frameReady.emit()
        except Exception:
            self.ready = False
            self.failed.emit('OpenGL çizimi kullanılamıyor; yazılımsal görüntüleyici etkin.')

