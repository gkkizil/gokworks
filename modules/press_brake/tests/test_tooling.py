from dataclasses import replace
from io import StringIO
from math import pi
import ezdxf
import pytest
from modules.gear_calculator.cad import shape_stats
from modules.press_brake.demo import load_demo
from modules.press_brake.geometry import Geometry
from modules.press_brake.models import Segment
from modules.press_brake.tooling import sections, save_catalog, load_catalog
from modules.press_brake.dialogs import segments


def drawing(*, unit=4, open=False, multiple=False):
    doc = ezdxf.new(); doc.header['$INSUNITS'] = unit; m = doc.modelspace()
    # Semicircle + diameter. The volume oracle detects polygonised arcs.
    m.add_arc((0, 0), 10, 0, 180)
    if not open:
        m.add_line((-10, 0), (10, 0))
    m.add_text('Do not cut me', dxfattribs={'insert': (50, 20)})
    dim = m.add_linear_dim(base=(0, 30), p1=(-10, 0), p2=(10, 0), angle=0)
    dim.render()
    doc.layers.new('HELPER'); m.add_line((100, 0), (120, 0), dxfattribs={'layer': 'HELPER'})
    if multiple:
        m.add_circle((50, 0), 3)
    stream = StringIO(); doc.write(stream); return stream.getvalue()


def test_native_line_arc_sections_extrude_at_exact_mm_scale():
    text = drawing(); contours = sections(text)
    p = load_demo('L120'); tool = replace(p.tools[0], id='native', section=contours[0][0], section_dxf=text)
    shape = Geometry(p).tool_shape(tool, Segment(0, 100))
    assert shape_stats(shape)['volume_mm3'] == pytest.approx(pi*10**2/2*100, rel=1e-9)


def test_multi_contour_requires_explicit_index_and_circles_stay_analytic():
    text = drawing(multiple=True); contours = sections(text)
    assert len(contours) == 2
    p = load_demo('L120'); t = replace(p.tools[0], id='circle', section=contours[1][0], section_dxf=text, contour_index=1)
    assert shape_stats(Geometry(p).tool_shape(t, Segment(0, 10)))['volume_mm3'] == pytest.approx(pi*3**2*10, rel=1e-8)


def test_nested_dxf_hole_is_a_real_exact_circular_void():
    doc = ezdxf.new(); doc.header['$INSUNITS'] = 4; m = doc.modelspace()
    m.add_lwpolyline([(-10, -10), (10, -10), (10, 10), (-10, 10)], close=True)
    m.add_circle((0, 0), 3)
    s = StringIO(); doc.write(s); text = s.getvalue(); contours = sections(text)
    assert len(contours) == 1 and len(contours[0][0].holes) == 1
    p = load_demo('L120'); t = replace(p.tools[0], id='holed', section=contours[0][0], section_dxf=text)
    actual = shape_stats(Geometry(p).tool_shape(t, Segment(0, 10)))['volume_mm3']
    assert actual == pytest.approx((400-pi*9)*10, rel=1e-8)


def test_open_invalid_units_and_unitless_confirmation():
    with pytest.raises(ValueError, match='Açık'):
        sections(drawing(open=True))
    for unit in (0, 1):
        with pytest.raises(ValueError, match='mm'):
            sections(drawing(unit=unit))
    assert sections(drawing(unit=0), accept_unitless=True)
    with pytest.raises(ValueError):
        sections(drawing(unit=1), accept_unitless=True)


def test_user_catalog_roundtrip_does_not_embed_demo_or_manufacturer_assets(tmp_path):
    p = load_demo('L120'); t = replace(p.tools[0], id='user', demo=False, section_dxf=drawing(), contour_index=0)
    path = tmp_path/'tools.json'; save_catalog(p.tools+(t,), path)
    got = load_catalog(path)
    assert len(got) == 1 and got[0].id == 'user'
    assert got[0].section_dxf == t.section_dxf and got[0].line_load is None
    save_catalog((t,), path)  # normal second save replaces atomically
    assert len(load_catalog(path)) == 1


def test_segments_explicit_positions_count_and_overlap():
    assert segments('-60:20; -30:10; 0:30') == (Segment(-60, 20), Segment(-30, 10), Segment(0, 30))
    for bad in ('0:0', '0:-2', '0:20;10:20', 'nan:30', '0:inf', 'nope'):
        with pytest.raises(ValueError):
            segments(bad)
