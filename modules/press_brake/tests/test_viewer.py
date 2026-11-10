"""Keep bend annotations independent from inherited viewer interaction layers."""
from types import SimpleNamespace
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget
from gui_qt.app import create_application
from modules.dxf_dwg.preview.geometry import make_mesh
from modules.gear_calculator.families.mesh_view import MechanismMeshView
from modules.press_brake.viewer import SceneView


def test_scene_does_not_replace_a_parent_viewer_overlay(qtbot, monkeypatch):
    create_application([])
    original = MechanismMeshView.__init__
    def inherited(self, *args, **kwargs):
        original(self, *args, **kwargs)
        # The current shared viewer on main reserves this name for its cube.
        if not hasattr(self, 'overlay'):
            self.overlay = QWidget(self)
        self.parent_controls = self.overlay
    monkeypatch.setattr(MechanismMeshView, '__init__', inherited)
    view = SceneView(); qtbot.addWidget(view)
    assert view.overlay is view.parent_controls
    assert view.bend_annotations is not view.overlay
    assert view.annotations is view.bend_annotations


def test_mouse_leave_camera_change_fallback_and_hide_keep_annotations_alive(qtbot):
    create_application([]); view = SceneView(); qtbot.addWidget(view)
    view.resize(400, 300); view.show()
    data = make_mesh((0, 0, 0, .01, 0, 0, 0, .01, 0))
    view.set_frame(SimpleNamespace(mesh=data, axis=((0, 0, 0), (10, 0, 0)), tool_bounds=(), hits=()))
    controls = getattr(view, 'overlay', None)
    QApplication.sendEvent(view, QEvent(QEvent.Leave))
    qtbot.mouseMove(view, QPoint(30, 35)); qtbot.mouseClick(view, Qt.LeftButton, pos=QPoint(80, 90))
    view.set_hud('Adım 1/1 · Büküm · 30°', 'collision')
    view.view('Ön'); view.fallback(); view.resize(420, 320)
    qtbot.wait(50)
    if controls is not None:
        assert view.overlay is controls and hasattr(controls, 'face_at') and hasattr(controls, 'set_hover')
    assert view.bend_annotations.geometry() == view.rect()
    assert view.bend_annotations.isVisible()
    assert view.annotations.hud == 'Adım 1/1 · Büküm · 30°' and view.annotations.state == 'collision'
    view.hide(); assert not view.timer.isActive()
