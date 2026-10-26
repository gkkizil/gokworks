"""Native OpenGL canvas; module-level class keeps Qt subclass lifetime stable."""

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QMatrix4x4, QVector3D, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram

from .viewer import normalized, matrices


class OpenGLCanvas(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        fmt = QSurfaceFormat(); fmt.setDepthBufferSize(24); fmt.setVersion(2, 1)
        self.setFormat(fmt)
        self.ready = False; self.dirty = True
        self.program = self.buffer = self.lines = None

    def initializeGL(self):
        try:
            self.f = self.context().functions()
            self.f.initializeOpenGLFunctions()
            self.context().aboutToBeDestroyed.connect(self.cleanup)
            self.program = QOpenGLShaderProgram(self)
            vertex = '''attribute vec3 position; attribute vec3 normal;
                uniform mat4 mvp; uniform mat4 modelView; varying vec3 n;
                void main(){gl_Position=mvp*vec4(position,1.0); n=mat3(modelView)*normal;}'''
            fragment = '''#ifdef GL_ES\nprecision mediump float;\n#endif
                varying vec3 n; uniform bool lines;
                void main(){float l=.42+.58*abs(dot(normalize(n),normalize(vec3(.25,.45,1.))));
                gl_FragColor=lines?vec4(.25,.30,.36,1.):vec4(vec3(.61,.675,.737)*l,1.);}'''
            if not self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex) or not self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment) or not self.program.link():
                raise RuntimeError(self.program.log())
            self.buffer, self.lines = QOpenGLBuffer(), QOpenGLBuffer()
            if not self.buffer.create() or not self.lines.create():
                raise RuntimeError('OpenGL buffer oluşturulamadı.')
            self.ready = True
        except Exception:
            self.failed.emit('OpenGL kullanılamıyor; yerel yazılımsal görüntüleyici etkin.')

    def cleanup(self):
        self.makeCurrent()
        if self.buffer: self.buffer.destroy()
        if self.lines: self.lines.destroy()
        if self.program:
            self.program.release()
            self.program.removeAllShaders()
            self.program.deleteLater()
        self.program = self.buffer = self.lines = None
        self.ready = False
        self.doneCurrent()

    def paintGL(self):
        parent = self.parentWidget()
        if not self.ready:
            return
        try:
            f = self.f
            f.glClearColor(.973, .973, .973, 1.)
            f.glClear(0x4000 | 0x0100)  # GL_COLOR_BUFFER_BIT / DEPTH_BUFFER_BIT
            if parent.mesh is None:
                return
            if self.dirty:
                vertices, normals, edges = normalized(parent.mesh)
                self.count, self.edge_count = len(vertices), len(edges)
                data = np.c_[vertices, normals].astype('f4').tobytes()
                self.buffer.bind(); self.buffer.allocate(data, len(data)); self.buffer.release()
                data = edges.astype('f4').tobytes()
                self.lines.bind(); self.lines.allocate(data, len(data)); self.lines.release()
                self.dirty = False
            view, mvp = matrices(parent.camera.state(), max(1, self.width())/max(1, self.height()))
            f.glEnable(0x0B71)  # GL_DEPTH_TEST
            p = self.program; p.bind()
            p.setUniformValue('mvp', QMatrix4x4(*mvp.ravel().tolist()))
            p.setUniformValue('modelView', QMatrix4x4(*view.ravel().tolist()))
            p.setUniformValue('lines', False)
            self.buffer.bind()
            p.enableAttributeArray('position'); p.enableAttributeArray('normal')
            p.setAttributeBuffer('position', 0x1406, 0, 3, 24)
            p.setAttributeBuffer('normal', 0x1406, 12, 3, 24)
            f.glEnable(0x8037); f.glPolygonOffset(1., 1.)
            f.glDrawArrays(0x0004, 0, self.count)
            f.glDisable(0x8037); self.buffer.release()
            if parent.camera.edges and self.edge_count:
                p.setUniformValue('lines', True)
                self.lines.bind(); p.disableAttributeArray('normal')
                p.setAttributeValue('normal', QVector3D(0, 0, 1))
                p.setAttributeBuffer('position', 0x1406, 0, 3, 12)
                f.glDrawArrays(0x0001, 0, self.edge_count); self.lines.release()
            p.disableAttributeArray('position'); p.disableAttributeArray('normal'); p.release()
            parent.frameReady.emit()
        except Exception:
            self.ready = False
            self.failed.emit('OpenGL çizimi kullanılamıyor; yazılımsal görüntüleyici etkin.')
