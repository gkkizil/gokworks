"""Continuous packing keeps physical contours and saved angle restrictions intact."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import time

import pytest
from shapely import affinity
from shapely.geometry import Polygon, box

from modules.nesting import engine, sparrow
from modules.nesting.geometry import placed
from modules.nesting.layout_score import layout_score
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Placement, Result, Sheet
from modules.nesting.rotations import angle_allowed, search_angles
from modules.nesting.search_budget import SearchBudget
from modules.nesting.storage import load_project, save_project
from modules.nesting.validation import validate_result


def project():
    p = new_project()
    p.parts = [Part.create('Profile', affinity.rotate(box(-120, 30, -20, 42), 37, origin=(0, 0)), quantity=3)]
    p.sheets = [Sheet('s', 'Stock', 160, 300, stock=1)]
    p.options.angles = None
    p.options.seconds = 3
    return p


def test_continuous_proposals_follow_contours_without_expanding_saved_restrictions():
    p = project(); part = p.parts[0]
    assert angle_allowed(part, p.options, 12.345)
    assert not angle_allowed(part, p.options, float('nan'))
    assert any(abs((a - 53 + 180) % 360 - 180) < 1e-6 for a in search_angles(part, p.options))
    p.options.angles = [0, 90]
    assert search_angles(part, p.options) == [0, 90]
    assert not angle_allowed(part, p.options, 37)
    p.options.angles = None; part.grain_locked = True
    assert search_angles(part, p.options) == [0, 180]
    assert not angle_allowed(part, p.options, 90)
    p.options.rotation = False
    assert search_angles(part, p.options) == [0]


def test_continuous_round_trip_is_valid_and_does_not_change_source(tmp_path):
    p = project(); before = deepcopy(asdict(p))
    result = sparrow.nest(p)
    assert validate_result(p, result) and len(result.placements) == 3
    assert asdict(p) == before
    assert any(abs(row.angle % 90) > .01 for row in result.placements)
    path = tmp_path / 'continuous.goknest.json'
    save_project(p, path, result)
    loaded, saved = load_project(path)
    assert loaded.options.angles is None and validate_result(loaded, saved)
    loaded.options.angles = [0, 90, 180, 270]
    saved.digest = loaded.fingerprint()
    with pytest.raises(ValueError, match='açı'):
        validate_result(loaded, saved)


@pytest.mark.parametrize('axis', [0, 90])
def test_native_strip_axes_preserve_negative_origin_contour_and_handedness(axis):
    p = project(); part = p.parts[0]; part.quantity = 1
    part.geometry = Part.create('Asymmetric', Polygon([(-120,30),(-85,30),(-85,38),(-110,38),(-110,60),(-120,60)])).geometry
    origin = part.polygon.bounds[:2]; angle = 23.
    native_angle = angle - axis
    local = affinity.translate(part.polygon, -origin[0], -origin[1])
    rotated = affinity.rotate(local, native_angle, origin=(0, 0))
    x0, y0, _, _ = rotated.bounds
    scale, pad, clearance = .01, 10., 1.5
    tx, ty = 8 - x0, 8 - y0
    rows = [dict(id=part.id, x=tx*scale, y=ty*scale, angle=native_angle, reflected=False)]
    specs = {part.id: dict(part=part, demand=1, angles=None, origin=origin)}
    poses = sparrow._poses(rows, specs, scale, pad, clearance, p.sheets[0], 1, Counter(), axis)
    assert len(poses) == 1 and poses[0].angle == angle
    expected = affinity.translate(rotated, tx+pad-clearance, ty+pad-clearance)
    if axis == 90:
        expected = affinity.translate(affinity.rotate(expected, 90, origin=(0, 0)), p.sheets[0].width, 0)
    assert placed(part, poses[0]).equals_exact(expected, 1e-7)
    rows[0]['reflected'] = True
    with pytest.raises(ValueError, match='Aynalanmış'):
        sparrow._poses(rows, specs, scale, pad, clearance, p.sheets[0], 1, Counter(), axis)


def test_timed_out_native_axes_leave_a_valid_partial_result(monkeypatch):
    p = project()
    monkeypatch.setattr(sparrow, '_run', lambda *args: None)
    result = sparrow.nest(p)
    assert not result.placements and len(result.unplaced) == 3
    assert validate_result(p, result, complete=False)


def test_native_budget_is_shared_across_remaining_physical_sheets(monkeypatch):
    p = project(); p.sheets[0].width = p.sheets[0].height = 55; p.sheets[0].stock = 3
    p.parts = [Part.create('One per sheet', box(0, 0, 30, 20), quantity=3)]
    p.options.rotation = False; p.options.seconds = 12
    clock = [0.]; deadlines = []
    monkeypatch.setattr(sparrow.time, 'monotonic', lambda: clock[0])
    def run(request, deadline, stop):
        deadlines.append(deadline)
        clock[0] = deadline
        item = request['items'][0]
        x = -min(p[0] for p in item['shape']); y = -min(p[1] for p in item['shape'])
        # The complete strip has one part inside the physical sheet; the
        # remaining parts must be retried on subsequent finite sheets.
        return [dict(id=item['id'], x=x+i*10, y=y, angle=0) for i in range(item['demand'])]
    monkeypatch.setattr(sparrow, '_run', run)
    result = sparrow.nest(p)
    assert validate_result(p, result) and len(result.placements) == 3
    assert len(deadlines) == 3 and deadlines[0] <= 6
    assert {row.sheet_number for row in result.placements} == {1, 2, 3}


def test_refinement_compacts_a_sparse_single_plate_without_changing_plate_count():
    p = project(); p.options.angles = [0]; p.options.rotation = False
    p.parts = [Part.create('Rectangle', box(0, 0, 30, 20), quantity=3)]
    rows = [Placement(p.parts[0].id, i+1, 's', 1, 15+i*45, 40+i*70, 0) for i in range(3)]
    seed = Result(p.fingerprint(), rows, [], 'fixture', '1', 0., 0, '')
    assert validate_result(p, seed)
    start = time.monotonic(); budget = SearchBudget(start, start+2, start+2, 5)
    result = engine.nest(p, initial=seed, budget=budget)
    assert validate_result(p, result)
    assert layout_score(p, result)[:3] == layout_score(p, seed)[:3]
    assert layout_score(p, result)[3] < layout_score(p, seed)[3] * .6
