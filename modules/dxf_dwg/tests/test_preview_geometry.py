"""Local mesh/depth/flat tests use synthetic geometry, never claim CAD acceptance."""

import threading

import ezdxf
import numpy as np
import pytest

from modules.cad_converter.models import Cancelled
from modules.dxf_dwg.preview.geometry import make_mesh
from modules.dxf_dwg.preview.models import MeshCache
from modules.dxf_dwg.preview.flat import read_flat
from modules.dxf_dwg.preview.viewer import Camera, VIEWS, raster, matrices


def ring_mesh():
    triangles = []
    outer = [(-.01, -.01, 0), (.01, -.01, 0), (.01, .01, 0), (-.01, .01, 0)]
    inner = [(-.004, -.004, 0), (.004, -.004, 0), (.004, .004, 0), (-.004, .004, 0)]
    for i in range(4):
        j = (i+1) % 4
        triangles.extend([outer[i], outer[j], inner[j], outer[i], inner[j], inner[i]])
    return make_mesh(np.asarray(triangles).ravel())


@pytest.mark.parametrize('data', [[], [0, 1], [0.]*9, [float('nan')]*9, [float('inf')]*9])
def test_bad_native_tessellation_is_rejected(data):
    with pytest.raises(ValueError): make_mesh(data)


def test_native_metres_are_mm_and_far_origin_does_not_collapse_geometry():
    source = np.array([[10000., 0, 0], [10000.01, 0, 0], [10000., .02, 0]])
    mesh = make_mesh(source.ravel())
    assert mesh.triangles == 1 and mesh.bounds[3]-mesh.bounds[0] == pytest.approx(10.)
    assert mesh.bounds[4]-mesh.bounds[1] == pytest.approx(20.)
    assert len(np.unique(np.frombuffer(mesh.positions, dtype='<f4').reshape(-1, 3), axis=0)) == 3
    assert mesh.origin[0] == pytest.approx(10000005.)


def test_triangle_diagonal_is_not_shown_as_a_cad_edge():
    mesh = make_mesh([0, 0, 0, .01, 0, 0, .01, .01, 0, 0, 0, 0, .01, .01, 0, 0, .01, 0])
    assert mesh.triangles == 2 and len(mesh.edges) == 4*2*3*4


def test_depth_render_keeps_actual_hole_open_and_is_not_a_bounding_box(qapp):
    mesh = ring_mesh(); camera = Camera(); camera.yaw, camera.pitch = VIEWS['Üst']; camera.edges = False
    image = raster(mesh, 200, 200, camera.state(), threading.Event())
    assert image.pixelColor(100, 100).red() == 248  # through hole, not filled
    assert image.pixelColor(60, 100).red() < 200  # actual ring material
    assert image.pixelColor(10, 10).red() == 248


@pytest.mark.parametrize('name', list(VIEWS))
@pytest.mark.parametrize('perspective', [False, True])
def test_all_camera_views_and_both_projections_are_finite(name, perspective):
    camera = Camera(); camera.yaw, camera.pitch = VIEWS[name]; camera.perspective = perspective
    view, mvp = matrices(camera.state(), 1.5)
    assert np.isfinite(view).all() and np.isfinite(mvp).all() and np.linalg.det(mvp) != 0


def test_render_and_mesh_cancellation(qapp):
    stop = threading.Event(); stop.set()
    with pytest.raises(Cancelled): make_mesh([0.]*9, stop)
    assert raster(ring_mesh(), 200, 200, Camera().state(), stop) is None


def test_cache_is_lru_bounded_and_not_path_only():
    mesh = ring_mesh(); cache = MeshCache(maximum=mesh.size*2, entries=2)
    cache.put(('source', 'configA', 1), mesh); cache.put(('source', 'configB', 1), mesh)
    assert cache.get(('source', 'configA', 2)) is None
    assert cache.get(('source', 'configA', 1)) is mesh
    cache.put(('other', 'configA', 1), mesh)
    assert cache.get(('source', 'configB', 1)) is None and cache.size <= cache.maximum
    cache.clear(); assert cache.size == 0 and not cache.items


def flat_file(path, unit=4):
    doc = ezdxf.new(); doc.units = unit
    doc.layers.new('BEND-UP', dxfattribs={'color': 1})
    doc.layers.new('CUT', dxfattribs={'color': 3})
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (100, 0), (100, 80), (0, 80)], close=True, dxfattribs={'layer': 'CUT'})
    m.add_circle((50, 40), 10, dxfattribs={'layer': 'CUT'})
    m.add_line((20, 0), (20, 80), dxfattribs={'layer': 'BEND-UP'})
    doc.saveas(path)
    return path


def test_real_dxf_reader_preserves_holes_bends_layers_units_and_length(tmp_path):
    flat = read_flat(flat_file(tmp_path/'part.dxf'))
    assert len(flat.strokes) == 3 and flat.bounds == (0, 0, 100, 80)
    assert sum(s.bend for s in flat.strokes) == 1
    assert flat.strokes[0].color != flat.strokes[2].color
    assert flat.cut_length == pytest.approx(360+20*np.pi, abs=.1)


def test_dxf_unknown_units_do_not_claim_mm_or_cut_length(tmp_path):
    flat = read_flat(flat_file(tmp_path/'unitless.dxf', 0))
    assert flat.cut_length is None and any('birimi tanımlı değil' in w for w in flat.warnings)


def test_block_geometry_is_transformed_and_unsupported_geometry_is_reported(tmp_path):
    path = tmp_path/'blocks.dxf'; doc = ezdxf.new(); doc.units = 4
    block = doc.blocks.new('CUT'); block.add_line((0, 0), (1, 0))
    doc.modelspace().add_blockref('CUT', (10, 20), dxfattribs={'xscale': 2, 'yscale': 2})
    doc.modelspace().add_solid([(0, 0), (0, 1), (1, 1)])
    doc.saveas(path); flat = read_flat(path)
    assert flat.bounds == (10, 20, 12, 20)
    assert any('SOLID' in w for w in flat.warnings) and flat.cut_length is None
