"""Declared dimensional lists are not manufacturer power-rating catalogues."""

from dataclasses import FrozenInstanceError, replace
import math
from threading import Event

import pytest

from modules.belt_drive.catalog.models import CatalogSource, LengthCatalog
from modules.belt_drive.engineering.belt_selection import nearest_catalog_candidates
from modules.belt_drive.models import BeltDriveSpecification
from modules.belt_drive.validation import CalculationCancelled
from .test_calculation import timing


def timing_catalog(**changes):
    values = dict(identifier='example-only', profile='HTD_5M', reference_line='pitch',
                  source=CatalogSource('Synthetic test dimensions', kind='example'), tooth_counts=(108, 110, 112))
    return LengthCatalog(**(values | changes))


def test_nearest_declared_timing_sizes_and_inverse_geometry():
    catalog = timing_catalog()
    candidates = nearest_catalog_candidates(timing(), catalog)
    assert [item.belt_teeth for item in candidates] == [110, 112, 108]
    for candidate in candidates:
        assert candidate.length_mm == candidate.belt_teeth * 5
        assert candidate.status == 'GEOMETRICALLY_SUITABLE'
        assert candidate.dimension_listed and not candidate.power_capacity_verified and not candidate.production_approved
        assert candidate.source.kind == 'example'
        # Independent absolute-angle form, not the engine length function.
        small, large = 50 / math.pi, 100 / math.pi
        c = candidate.center_mm
        theta = math.acos((large - small) / c)
        length = 2 * math.sqrt(c*c - (large-small)**2) + 2*small*theta + 2*large*(math.pi-theta)
        assert length == pytest.approx(candidate.length_mm, abs=1e-9)
        assert candidate.center_deviation_mm == pytest.approx(c - 200.)
        assert candidate.small_wrap_deg == pytest.approx(math.degrees(2*theta))
        assert candidate.engaged_small_teeth_estimate == pytest.approx(20*theta/math.pi)
    assert nearest_catalog_candidates(timing(), catalog, limit=1) == candidates[:1]


def test_v_catalog_uses_explicit_datum_lengths_and_preserves_source():
    source = CatalogSource('User list', 'Declared manufacturer', 'Series X', 'rev 1', 'manual/page 4')
    catalog = LengthCatalog('local', 'A', 'datum', source, lengths_mm=(1250., 1275., 1300.))
    candidates = nearest_catalog_candidates(BeltDriveSpecification(), catalog)
    assert [item.length_mm for item in candidates] == [1275., 1300., 1250.]
    assert candidates[0].source == source
    assert all(item.belt_teeth is item.engaged_small_teeth_estimate is None for item in candidates)
    assert all(not item.production_approved for item in candidates)


def test_same_pitch_does_not_make_tooth_profiles_interchangeable():
    with pytest.raises(ValueError, match='aynı adım'):
        nearest_catalog_candidates(timing(), timing_catalog(profile='T5'))


def test_impossible_catalog_dimension_is_retained_as_unsuitable():
    item, = nearest_catalog_candidates(timing(), timing_catalog(tooth_counts=(10,)))
    assert item.dimension_listed and item.status == 'UNSUITABLE'
    assert item.center_mm is item.small_wrap_deg is None
    assert item.reason and not item.production_approved


@pytest.mark.parametrize('changes', [
    {'tooth_counts': ()}, {'tooth_counts': (110, 110)}, {'tooth_counts': (110.,)},
    {'tooth_counts': (True,)}, {'tooth_counts': (-1,)}, {'tooth_counts': (10**308,)},
    {'lengths_mm': (550.,)}, {'reference_line': 'datum'}, {'source': {}},
    {'identifier': ''}, {'profile': 'GT2'}, {'tooth_counts': range(100, 200)},
])
def test_invalid_catalogs_are_rejected(changes):
    with pytest.raises(ValueError):
        timing_catalog(**changes)


@pytest.mark.parametrize('bad', [0, -1, True, 1.5, 10001])
def test_invalid_candidate_limits(bad):
    with pytest.raises(ValueError):
        nearest_catalog_candidates(timing(), timing_catalog(), limit=bad)


def test_catalog_copies_input_sequences_and_is_immutable():
    values = [110, 112]
    catalog = timing_catalog(tooth_counts=values)
    values.append(114)
    assert catalog.tooth_counts == (110, 112)
    with pytest.raises(FrozenInstanceError):
        catalog.source.name = 'changed'
    with pytest.raises(ValueError):
        replace(catalog.source, kind='verified_manufacturer')


def test_selection_cancellation_is_not_an_unsuitable_candidate():
    stop = Event(); stop.set()
    with pytest.raises(CalculationCancelled):
        nearest_catalog_candidates(timing(), timing_catalog(), stop=stop)
