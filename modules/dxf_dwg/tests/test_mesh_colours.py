"""Optional per-triangle mesh colours: absent = unchanged single-colour preview everywhere."""
import threading
import numpy as np
import pytest
from PySide6.QtGui import QImage
from modules.dxf_dwg.preview import viewer
from modules.dxf_dwg.preview.geometry import make_mesh
from modules.dxf_dwg.preview.opengl import SURFACE, vertex_colours

STATE = (-30, 25, 1, 0, 0, False, False)
# Two squares side by side (metres, as make_mesh expects), two triangles each.
SQUARES = np.array([[(0, 0, 0), (.01, 0, 0), (.01, .01, 0)], [(0, 0, 0), (.01, .01, 0), (0, .01, 0)],
                    [(.02, 0, 0), (.03, 0, 0), (.03, .01, 0)], [(.02, 0, 0), (.03, .01, 0), (.02, .01, 0)]])


def pixels(mesh):
    image = viewer.raster(mesh, 160, 120, STATE, threading.Event(), (0, 0, 0)).convertToFormat(QImage.Format_RGB888)
    data = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return data[:, :image.width()*3].reshape(image.height(), image.width(), 3).astype(int)


def test_meshes_without_colours_render_exactly_as_before():
    plain = make_mesh(SQUARES)
    assert plain.colours == b'' and np.array_equal(vertex_colours(plain)[0], SURFACE)
    image = pixels(plain); drawn = image[image.sum(axis=2) > 0]
    assert len(drawn) and np.allclose(drawn/np.maximum(drawn[:, :1], 1), viewer.BASE_COLOUR/viewer.BASE_COLOUR[0], atol=.05)


def test_coloured_triangles_keep_their_colour_in_software_and_opengl_paths():
    red, blue = (220, 40, 40), (40, 60, 220)
    mesh = make_mesh(SQUARES, colours=[red, red, blue, blue])
    assert len(mesh.colours) == 4*3
    image = pixels(mesh); drawn = image[image.sum(axis=2) > 0]
    assert (drawn[:, 0] > drawn[:, 2]*2).any() and (drawn[:, 2] > drawn[:, 0]*2).any()
    gl = vertex_colours(mesh)
    assert gl.shape == (12, 3) and gl[0, 0] > gl[0, 2] and gl[-1, 2] > gl[-1, 0]


def test_colours_follow_dropped_degenerate_triangles_and_must_match_the_count():
    degenerate = np.array([[(0, 0, 0), (0, 0, 0), (0, 0, 0)]])
    mesh = make_mesh(np.r_[degenerate, SQUARES], colours=[(1, 2, 3)] + [(9, 9, 9)]*4)
    assert mesh.triangles == 4 and set(mesh.colours) == {9}
    with pytest.raises(ValueError):
        make_mesh(SQUARES, colours=[(1, 2, 3)])
