"""The CPU preview keeps drawing while the user drags, not only after release."""

import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from gui_qt.app import create_application
from modules.dxf_dwg.preview.viewer import MeshView
from .test_preview_geometry import ring_mesh


def _mouse(widget, kind, x, buttons):
    button = Qt.LeftButton if kind != QEvent.MouseMove else Qt.NoButton
    QApplication.sendEvent(widget, QMouseEvent(kind, QPointF(x, 120), QPointF(x, 120),
                                               button, buttons, Qt.NoModifier))


def test_dragging_renders_frames_and_finishes_on_the_final_camera(qtbot):
    create_application([])
    view = MeshView(); qtbot.addWidget(view); view.resize(520, 300); view.show()
    frames = []; view.frameReady.connect(lambda: frames.append(view.camera.yaw))
    view.set_mesh(ring_mesh())
    qtbot.waitUntil(lambda: bool(frames), timeout=5000)
    frames.clear()
    _mouse(view, QEvent.MouseButtonPress, 100, Qt.LeftButton)
    started, x = time.perf_counter(), 100
    while time.perf_counter() - started < 1.0:   # continuous motion, never pausing
        x += 3; _mouse(view, QEvent.MouseMove, x, Qt.LeftButton); qtbot.wait(8)
    during = len(frames)
    _mouse(view, QEvent.MouseButtonRelease, x, Qt.NoButton)
    assert during >= 5, f'Sürükleme sırasında yalnız {during} kare çizildi.'
    qtbot.waitUntil(lambda: frames and frames[-1] == view.camera.yaw and not view.running, timeout=5000)
    assert not view.dragging
