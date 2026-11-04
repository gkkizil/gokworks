"""DFM-GEO: each hygiene rule against hand-built DXFs with known answers."""

import hashlib
import math
import os
import threading

import ezdxf
import pytest

from modules.dfm_analyzer.controller import analyze
from modules.dfm_analyzer.importers.dxf import MissingUnits
from modules.dfm_analyzer.models import PASSED, FAILED, NOT_EVALUATED
from modules.dfm_analyzer.profiles import bundled


@pytest.fixture(scope='module')
def geo():
    return bundled()['geometry_basic']


def dxf(path, build, units=4):
    doc = ezdxf.new('R2018'); doc.units = units
    build(doc, doc.modelspace())
    doc.saveas(path)
    return path


def rect(msp, x0, y0, x1, y1, **attribs):
    return msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs=attribs)


def outcome(result, rule_id):
    return next(o for o in result.outcomes if o.rule_id == rule_id)


def findings(result, rule_id):
    return [f for f in result.findings if f.rule_id == rule_id]


def test_valid_closed_plate_passes_every_geometry_rule(tmp_path, geo):
    path = dxf(tmp_path / 'ok.dxf', lambda doc, msp: (rect(msp, 0, 0, 100, 50), msp.add_circle((20, 25), 5)))
    result = analyze(path, geo)
    assert [o.status for o in result.outcomes] == [PASSED] * len(result.outcomes)
    assert len(result.parts) == 1 and len(result.parts[0]['holes']) == 1
    assert result.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_open_contour_reports_both_ends_and_their_gap(tmp_path, geo):
    def build(doc, msp):
        msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50)); msp.add_line((100, 50), (0, 50))
    result = analyze(dxf(tmp_path / 'open.dxf', build), geo)
    ends = findings(result, 'DFM-GEO-001')
    assert outcome(result, 'DFM-GEO-001').status == FAILED
    assert len([f for f in ends if f.measured is not None]) == 2
    assert all(f.measured == pytest.approx(50) for f in ends if f.measured is not None)   # (0,0)–(0,50)
    assert outcome(result, 'DFM-GEO-013').status == FAILED                                # no closed part


def test_micro_gap_is_bridged_with_its_size_and_the_part_closes(tmp_path, geo):
    def build(doc, msp):
        msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50))
        msp.add_line((100, 50), (0, 50)); msp.add_line((0, 50), (0, .02))
    result = analyze(dxf(tmp_path / 'gap.dxf', build), geo)
    bridged = findings(result, 'DFM-GEO-002')
    assert len(bridged) == 1 and bridged[0].measured == pytest.approx(.02, abs=1e-9)
    assert outcome(result, 'DFM-GEO-001').status == PASSED and len(result.parts) == 1


def test_self_intersecting_and_crossing_contours(tmp_path, geo):
    def build(doc, msp):
        msp.add_lwpolyline([(0, 0), (10, 10), (10, 0), (0, 10)], close=True)        # bow tie
        rect(msp, 100, 0, 150, 50); rect(msp, 140, 10, 170, 40)                         # two outlines crossing
    result = analyze(dxf(tmp_path / 'x.dxf', build), geo)
    assert findings(result, 'DFM-GEO-007') and findings(result, 'DFM-GEO-008')
    crossing = findings(result, 'DFM-GEO-008')[0]
    points = sorted(tuple(round(c, 6) for c in m.points[0]) for m in crossing.marks)
    assert points == [(150, 10), (150, 40)]


def test_duplicate_and_overlapping_lines(tmp_path, geo):
    def build(doc, msp):
        rect(msp, 0, 0, 100, 50); rect(msp, 0, 0, 100, 50)                            # exact copy
        msp.add_line((200, 0), (260, 0)); msp.add_line((240, 0), (300, 0))             # 20 mm shared
    result = analyze(dxf(tmp_path / 'dup.dxf', build), geo)
    assert len(findings(result, 'DFM-GEO-005')) == 1
    overlap = findings(result, 'DFM-GEO-006')
    assert len(overlap) == 1 and overlap[0].measured == pytest.approx(20)
    assert len(result.parts) == 1                                                       # the copy is not a 2nd part


def test_island_inside_a_cutout_would_fall_out(tmp_path, geo):
    def build(doc, msp):
        rect(msp, 0, 0, 100, 100); rect(msp, 20, 20, 80, 80); rect(msp, 40, 40, 60, 60)
    result = analyze(dxf(tmp_path / 'island.dxf', build), geo)
    islands = findings(result, 'DFM-GEO-009')
    assert len(islands) == 1 and len(result.parts) == 2


def test_zero_length_and_short_segments(tmp_path, geo):
    def build(doc, msp):
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (50.01, 50), (50, 50), (0, 50)], close=True)
        msp.add_line((10, 10), (10, 10))
    result = analyze(dxf(tmp_path / 'short.dxf', build), geo)
    assert len(findings(result, 'DFM-GEO-004')) == 1
    short = findings(result, 'DFM-GEO-010')
    assert len(short) == 1 and short[0].measured == pytest.approx(.01) and short[0].severity == 'INFO'


def test_bulge_corners_close_and_keep_the_true_area(tmp_path, geo):
    r = 5.
    b = math.tan(math.radians(90) / 4)                                                 # 90° arc bulge
    points = [(r, 0, 0), (100 - r, 0, b), (100, r, 0), (100, 50 - r, b), (100 - r, 50, 0),
              (r, 50, b), (0, 50 - r, 0), (0, r, b)]
    result = analyze(dxf(tmp_path / 'bulge.dxf', lambda doc, msp: msp.add_lwpolyline(points, format='xyb', close=True)), geo)
    from shapely.geometry import Polygon
    area = Polygon(result.parts[0]['outline']).area
    assert area == pytest.approx(100 * 50 - (4 - math.pi) * r * r, abs=.5)       # chord error ≤ 0.01 mm
    assert all(o.status == PASSED for o in result.outcomes)


def test_huge_coordinates_and_micron_holes_are_measured_exactly(tmp_path):
    laser = bundled()['laser_generic']
    def build(doc, msp):
        rect(msp, 1e6, 1e6, 1e6 + 100, 1e6 + 50); msp.add_circle((1e6 + 50, 1e6 + 25), .1)
    result = analyze(dxf(tmp_path / 'far.dxf', build), laser, thickness=1)
    hole = findings(result, 'DFM-LAS-001')
    assert len(hole) == 1 and hole[0].measured == pytest.approx(.2, abs=1e-9)


def test_missing_units_must_be_chosen_and_inch_is_scaled(tmp_path, geo):
    path = dxf(tmp_path / 'nounits.dxf', lambda doc, msp: rect(msp, 0, 0, 4, 2), units=0)
    with pytest.raises(MissingUnits):
        analyze(path, geo)
    result = analyze(path, geo, unit='inch')
    xs = [p[0] for p in result.parts[0]['outline']]
    assert max(xs) - min(xs) == pytest.approx(4 * 25.4)


def test_broken_and_empty_files_are_refused_in_turkish(tmp_path, geo):
    (tmp_path / 'bad.dxf').write_bytes(os.urandom(2048))
    (tmp_path / 'empty.dxf').write_bytes(b'')
    with pytest.raises(ValueError, match='geçerli bir DXF'):
        analyze(tmp_path / 'bad.dxf', geo)
    with pytest.raises(ValueError, match='boş'):
        analyze(tmp_path / 'empty.dxf', geo)
    with pytest.raises(ValueError, match='yalnız DXF'):
        analyze(tmp_path / 'part.dwg', geo)


def test_unsupported_entities_are_not_evaluated_not_passed(tmp_path, geo):
    def build(doc, msp):
        rect(msp, 0, 0, 100, 50)
        msp.add_3dface([(0, 0, 0), (1, 0, 0), (1, 1, 0)])
        msp.add_text('ETİKET')
        doc.layers.add('BEND'); msp.add_line((50, 0), (50, 50), dxfattribs={'layer': 'BEND'})
    result = analyze(dxf(tmp_path / 'mixed.dxf', build), geo)
    unsupported = outcome(result, 'DFM-GEO-011')
    assert unsupported.status == NOT_EVALUATED and '3DFACE' in unsupported.reason
    assert outcome(result, 'DFM-GEO-003').status == PASSED                     # bend line did not branch
    assert any('büküm katmanı' in n for n in result.notes) and any('TEXT' not in n for n in result.notes)


def test_source_file_is_unchanged_and_cancel_stops(tmp_path, geo):
    path = dxf(tmp_path / 'ok.dxf', lambda doc, msp: rect(msp, 0, 0, 10, 10))
    before = path.read_bytes()
    analyze(path, geo)
    assert path.read_bytes() == before
    stop = threading.Event(); stop.set()
    with pytest.raises(InterruptedError):
        analyze(path, geo, stop=stop)
