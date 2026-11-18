"""Regression: the NFP mitre offset must not hit GEOS on zero-length round-off edges.

Before the fix ``obstacle.buffer(d, join_style=2)`` warned "invalid value encountered
in buffer" for the dense layout case 2: the convex-sum union kept edges of
1e-14..1e-30 mm left by rotating parts about the origin. The obstacle polygon below
is the one recorded from that run (Python 3.13, NumPy 2.5, Shapely 2.1, GEOS 3.13).
"""
import random
import warnings

from shapely import set_precision
from shapely.geometry import Polygon

from modules.nesting.engine import NFP_GRID, nest
from modules.nesting.models import Material, Options, Part, Project, Sheet
from .test_independent_geometry_oracle import _shape

RECORDED_OBSTACLE = [
    (-268.03136819924805, 289.3228367572179),
    (-21.291468557969885, 289.3228367572179),
    (-21.291468557969885, 299.9790416129939),
    (-21.29146855796986, 299.9790416129939),
    (-21.29146855796986, 568.010409812242),
    (21.29146855796986, 568.010409812242),
    (21.29146855796986, 321.27051017096375),
    (299.9790416129939, 321.27051017096375),
    (299.9790416129939, 21.29146855796986),
    (299.9790416129939, 0.0),
    (2.061700532036378e-30, -2.4868995751603503e-14),
    (0.0, -2.4868995751603507e-14),
    (-2.06170053203638e-30, -2.4868995751603503e-14),
    (-2.4868995751603507e-14, -2.4868995751603507e-14),
    (-4.9737991503207007e-14, -4.614884846116368e-30),
    (-268.03136819924805, -2.4868995751603507e-14),
    (-268.03136819924805, 0.0),
    (-268.03136819924805, 21.29146855796986),
]
DISTANCE = 3.0


def test_snapped_obstacle_offsets_without_warning_and_still_contains_the_euclidean_offset():
    obstacle = Polygon(RECORDED_OBSTACLE)
    assert obstacle.is_valid
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        grown = set_precision(obstacle, NFP_GRID).buffer(DISTANCE + 2e-6, join_style=2)
    assert grown.is_valid and not grown.is_empty
    assert grown.covers(obstacle.buffer(DISTANCE, quad_segs=64))     # exact clearance kept


def test_dense_layout_case_2_runs_without_numeric_warnings():
    rng = random.Random(7002)
    parts = [Part.create(f'P{i}', _shape(rng), material='m', thickness=2, quantity=rng.randint(3, 8))
             for i in range(rng.randint(2, 4))]
    sheet = Sheet('s', 'S', rng.choice([600, 800]), rng.choice([800, 1000]), 2, 'm', 100)
    options = Options(gap=rng.choice([0, 3, 5]), margin=rng.choice([0, 10]), kerf=rng.choice([0, .2, 2]),
                      rotation=True, seed=2)
    project = Project('qa', [Material('m', 'S235JR', 7850)], parts, [sheet], options)
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        result = nest(project)
    assert not result.unplaced
