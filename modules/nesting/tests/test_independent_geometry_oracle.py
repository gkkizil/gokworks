"""Seeded nesting runs re-checked with plain shapely, not validation.py.

Shapes include rings, frames with large holes, L/T forms and irregular
polygons, so parts may legitimately sit inside another part's hole.
"""

import math
import random

import pytest
from shapely.geometry import Point, Polygon, box

from modules.nesting.engine import nest
from modules.nesting.geometry import placed
from modules.nesting.models import Material, Options, Part, Project, Sheet


def _shape(rng):
    kind = rng.randint(0, 5)
    if kind == 0:
        return box(0, 0, rng.uniform(20, 300), rng.uniform(20, 300))
    if kind == 1:
        r = rng.uniform(20, 120)
        return Point(0, 0).buffer(r, 32).difference(Point(0, 0).buffer(r * rng.uniform(.3, .7), 32))
    if kind == 2:
        w, h, t = rng.uniform(80, 300), rng.uniform(80, 300), rng.uniform(10, 30)
        return box(0, 0, w, h).difference(box(t, t, w, h))
    if kind == 3:
        n = rng.randint(5, 9)
        points = [(math.cos(2*math.pi*i/n)*rng.uniform(40, 120), math.sin(2*math.pi*i/n)*rng.uniform(40, 120))
                  for i in range(n)]
        return Polygon(points).convex_hull
    if kind == 4:
        w, h = rng.uniform(150, 400), rng.uniform(150, 400)
        return box(0, 0, w, h).difference(box(w*.2, h*.2, w*.8, h*.8))
    w = rng.uniform(100, 300)
    return box(0, 0, w, 40).union(box(w/2 - 20, 0, w/2 + 20, 200))


@pytest.mark.parametrize('case', range(3))
def test_dense_multi_sheet_layout_has_no_overlap_gap_or_edge_violation(case):
    rng = random.Random(7000 + case)
    parts = [Part.create(f'P{i}', _shape(rng), material='m', thickness=2, quantity=rng.randint(3, 8))
             for i in range(rng.randint(2, 4))]
    sheet = Sheet('s', 'S', rng.choice([600, 800]), rng.choice([800, 1000]), 2, 'm', 100)
    options = Options(gap=rng.choice([0, 3, 5]), margin=rng.choice([0, 10]), kerf=rng.choice([0, .2, 2]),
                      rotation=True, seed=case)
    project = Project('qa', [Material('m', 'S235JR', 7850)], parts, [sheet], options)
    result = nest(project)

    required = max(options.gap, options.kerf)
    edge = options.margin + options.kerf / 2
    usable = box(edge - 1e-6, edge - 1e-6, sheet.width - edge + 1e-6, sheet.height - edge + 1e-6)
    by_sheet = {}
    for placement in result.placements:
        part = project.part(placement.part_id)
        shape = placed(part, placement)
        assert usable.covers(shape), part.code
        assert shape.area == pytest.approx(part.polygon.area, rel=1e-9)   # rigid transform only
        by_sheet.setdefault(placement.sheet_number, []).append(shape)
    for shapes in by_sheet.values():
        for i, first in enumerate(shapes):
            for second in shapes[i + 1:]:
                assert first.intersection(second).area <= 1e-6
                assert first.distance(second) + 1e-6 >= required
    assert len(result.placements) + len(result.unplaced) == sum(p.quantity for p in parts)
    assert not result.unplaced                                             # stock 100 is ample
