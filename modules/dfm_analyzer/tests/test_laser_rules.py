"""DFM-LAS against hand-computed values (generic example profile: limit = max(1 mm, 1 × t))."""

import copy
import json

import ezdxf
import pytest

from modules.dfm_analyzer.controller import analyze
from modules.dfm_analyzer.models import PASSED, FAILED, NOT_EVALUATED, AnalysisResult
from modules.dfm_analyzer.profiles import bundled, parse
from modules.dfm_analyzer import reporting

from .test_geometry_rules import dxf, rect, findings, outcome


@pytest.fixture
def laser():
    return copy.deepcopy(bundled()['laser_generic'])


def plate(tmp_path, name, extra):
    return dxf(tmp_path / name, lambda doc, msp: (rect(msp, 0, 0, 100, 50), extra(msp)))


@pytest.mark.parametrize('diameter, failed', [(1.5, True), (2.0, False), (3.0, False)])
def test_hole_diameter_below_at_and_above_the_limit(tmp_path, laser, diameter, failed):
    result = analyze(plate(tmp_path, 'h.dxf', lambda msp: msp.add_circle((50, 25), diameter / 2)), laser, thickness=2)
    found = findings(result, 'DFM-LAS-001')
    assert bool(found) is failed
    assert outcome(result, 'DFM-LAS-001').limit == pytest.approx(2.0)          # max(1 mm, 1 × 2 mm)
    if failed:
        assert found[0].measured == pytest.approx(1.5) and found[0].difference == pytest.approx(.5)


def test_hole_too_close_to_the_edge_marks_hole_and_distance(tmp_path, laser):
    result = analyze(plate(tmp_path, 'e.dxf', lambda msp: msp.add_circle((3, 25), 2)), laser, thickness=2)
    found = findings(result, 'DFM-LAS-003')
    assert len(found) == 1 and found[0].measured == pytest.approx(1.0, abs=.011)  # 3 − 2 (chord ≤ 0.01)
    line = next(m for m in found[0].marks if m.kind == 'line')
    assert line.points[1][0] == pytest.approx(0, abs=1e-9)                       # ends on the outer edge x = 0


def test_material_bridge_between_two_holes(tmp_path, laser):
    result = analyze(plate(tmp_path, 'w.dxf', lambda msp: (msp.add_circle((40, 25), 2), msp.add_circle((45, 25), 2))),
                     laser, thickness=2)
    found = findings(result, 'DFM-LAS-004')
    assert len(found) == 1 and found[0].measured == pytest.approx(1.0, abs=.011)   # 5 − 2 − 2


def test_narrow_slot_width_is_its_inscribed_circle_diameter(tmp_path, laser):
    def slot(msp):                                    # obround 1.5 mm wide, 10 mm between centres
        msp.add_lwpolyline([(40, 24.25, 0), (50, 24.25, 1), (50, 25.75, 0), (40, 25.75, 1)], format='xyb', close=True)
    result = analyze(plate(tmp_path, 's.dxf', slot), laser, thickness=2)
    found = findings(result, 'DFM-LAS-002')
    assert len(found) == 1 and found[0].measured == pytest.approx(1.5, abs=.02)
    assert not findings(result, 'DFM-LAS-001')        # a slot is not a round hole


def test_thin_tongue_and_narrow_notch(tmp_path, laser):
    def build(doc, msp):
        # 100 x 50 plate with a 1.5 mm wide, 20 mm long tongue on top and a 1 mm notch, 10 mm deep, at the bottom.
        msp.add_lwpolyline([(0, 0), (60, 0), (60, 10), (61, 10), (61, 0), (100, 0), (100, 50),
                            (50.75, 50), (50.75, 70), (49.25, 70), (49.25, 50), (0, 50)], close=True)
    result = analyze(dxf(tmp_path / 't.dxf', build), laser, thickness=2)
    tongue, notch = findings(result, 'DFM-LAS-005'), findings(result, 'DFM-LAS-006')
    assert len(tongue) == 1 and tongue[0].measured == pytest.approx(1.5, abs=.02)
    assert len(notch) == 1 and notch[0].measured == pytest.approx(1.0, abs=.02)


def test_plain_rectangle_corners_are_not_reported(tmp_path, laser):
    result = analyze(dxf(tmp_path / 'r.dxf', lambda doc, msp: rect(msp, 0, 0, 100, 50)), laser, thickness=10)
    assert not result.findings
    assert all(o.status == PASSED for o in result.outcomes if o.rule_id != 'DFM-LAS-008')


def test_without_thickness_the_thickness_rules_are_not_evaluated(tmp_path, laser):
    result = analyze(plate(tmp_path, 'n.dxf', lambda msp: msp.add_circle((50, 25), .5)), laser)
    for rid in ('DFM-LAS-001', 'DFM-LAS-002', 'DFM-LAS-003', 'DFM-LAS-004', 'DFM-LAS-005', 'DFM-LAS-006', 'DFM-LAS-007'):
        assert outcome(result, rid).status == NOT_EVALUATED and 'kalınl' in outcome(result, rid).reason
    assert result.summary()['not_evaluated'] == 7


def test_thickness_outside_the_profile_and_part_larger_than_the_table(tmp_path, laser):
    result = analyze(dxf(tmp_path / 'big.dxf', lambda doc, msp: rect(msp, 0, 0, 4000, 100)), laser, thickness=30)
    assert outcome(result, 'DFM-LAS-007').status == FAILED and outcome(result, 'DFM-LAS-008').status == FAILED


def test_user_profile_with_absolute_limit_and_error_severity(tmp_path):
    data = json.loads((bundled()['laser_generic'].path and open(bundled()['laser_generic'].path, encoding='utf-8').read()))
    data.update(id='my_laser', name='Atölye fiber 3 kW', verified=True)
    data['rules']['DFM-LAS-001'] = {'severity': 'ERROR', 'min_mm': 2.5}
    profile = parse(data)
    result = analyze(plate(tmp_path, 'u.dxf', lambda msp: msp.add_circle((50, 25), 1.2)), profile, thickness=1)
    found = findings(result, 'DFM-LAS-001')
    assert found[0].severity == 'ERROR' and found[0].limit == pytest.approx(2.5)
    with pytest.raises(ValueError, match='Bilinmeyen kural'):
        parse({**data, 'rules': {'DFM-XXX-1': {}}})
    with pytest.raises(ValueError, match='pozitif'):
        parse({**data, 'rules': {'DFM-LAS-001': {'min_mm': -1}}})


def test_json_round_trip_and_csv_report(tmp_path, laser):
    result = analyze(plate(tmp_path, 'j.dxf', lambda msp: msp.add_circle((3, 25), 2)), laser, thickness=2)
    reporting.write_json(result, tmp_path / 'r.json')
    again = reporting.read_json(tmp_path / 'r.json')
    assert isinstance(again, AnalysisResult) and again.summary() == result.summary()
    assert [tuple(p) for p in again.findings[0].marks[0].points] == [tuple(p) for p in result.findings[0].marks[0].points]
    reporting.write_csv(result, tmp_path / 'r.csv')
    text = (tmp_path / 'r.csv').read_text(encoding='utf-8-sig')
    assert text.startswith('Kural;Kural adı') and 'DFM-LAS-003' in text and '1' in text
