"""CAD görünümü: yumuşak gölgeleme, keskin kenarlar, degrade arka plan, görünüm küpü."""

import math

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from gui_qt.app import create_application
from gui_qt.theme import COLORS
from modules.dxf_dwg.preview.geometry import make_mesh
from modules.dxf_dwg.preview.viewer import VIEWS, MeshView, gradient, grid_lines


def cone(n=48):
    tri = []
    for i in range(n):
        a, b = 2*math.pi*i/n, 2*math.pi*(i+1)/n
        tri += [0, .2, 0, .15*math.cos(b), 0, .15*math.sin(b), .15*math.cos(a), 0, .15*math.sin(a)]
    return make_mesh(tri)


def box():
    v = np.array([(x, y, z) for x in (0, .01) for y in (0, .01) for z in (0, .01)])
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return make_mesh(np.array([[v[a], v[b], v[c], v[a], v[c], v[d]] for a, b, c, d in faces]).ravel())


def normals(mesh):
    return np.frombuffer(mesh.normals, '<f4').reshape(-1, 3)


def test_curved_surface_is_smooth_and_unit():
    n = normals(cone())
    assert np.allclose(np.linalg.norm(n, axis=1), 1, atol=1e-5)
    # triangle i is (apex, b_i, a_i); b_(i-1) and a_i are the same rim vertex
    assert np.allclose(n[1::3][-1], n[2::3][0], atol=1e-5)
    assert not np.allclose(n[1::3][0], n[2::3][0], atol=1e-3)   # but it still follows the curve


def test_box_edges_stay_sharp():
    n = normals(box())
    assert np.allclose(np.abs(n).max(axis=1), 1, atol=1e-6)     # every corner keeps its face normal


@pytest.mark.parametrize('appearance', ['dark', 'light'])
def test_gradient_keeps_the_canvas_colour_in_the_middle(appearance):
    canvas = QColor(COLORS[appearance]['canvas'])
    top, bottom = gradient(canvas)
    middle = (np.array(top) + np.array(bottom)) / 2
    assert top != bottom
    assert np.abs(middle - (canvas.red(), canvas.green(), canvas.blue())).max() <= 6


def test_grid_lies_under_the_part():
    vertices = np.array([(-1, -.4, 0), (1, .5, 0)])
    lines = grid_lines(vertices)
    assert len(lines) % 2 == 0 and np.all(lines[:, 1] < -.4)


def test_view_cube_click_selects_the_standard_view(qtbot):
    create_application([])
    view = MeshView(); qtbot.addWidget(view); view.resize(600, 400); view.show()
    view.set_mesh(box()); view.view('Ön'); qtbot.wait(10)
    centre = view.overlay.cube_rect().center()
    assert view.overlay.face_at(centre) == 'Ön'
    view.view('İzometrik')
    names = {name for name, _, _ in view.overlay.faces()}
    assert names == {'Ön', 'Sağ', 'Üst'}
    _, polygon, _ = next(f for f in view.overlay.faces() if f[0] == 'Üst')
    qtbot.mouseClick(view, __import__('PySide6.QtCore', fromlist=['Qt']).Qt.LeftButton,
                     pos=polygon.boundingRect().center().toPoint())
    assert (view.camera.yaw, view.camera.pitch) == VIEWS['Üst']
    assert view.overlay.geometry() == view.rect()
