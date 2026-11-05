"""Synthetic arithmetic is explicitly NOT Gates/Optibelt manufacturer validation."""

from dataclasses import replace

import pytest

from modules.belt_drive.catalog.importers import (catalog_to_dict, catalog_from_dict, catalog_loads,
    catalog_dumps, catalog_to_csv, catalog_from_csv, fingerprint)
from modules.belt_drive.catalog.rating_models import CorrectionTable
from modules.belt_drive.engineering.ratings import interpolate_power, interpolate_1d, TableRangeError
from modules.belt_drive.design_search import search_drives
from .design_fixtures import timing_catalog, v_catalog, request, with_rating


def test_product_catalog_json_and_csv_roundtrip_and_stable_digest():
    cat = timing_catalog()
    restored = catalog_loads(catalog_dumps(cat))
    assert restored == cat and fingerprint(restored) == fingerprint(cat)
    csv = catalog_to_csv(cat)
    assert catalog_from_csv(csv, identifier=cat.identifier, revision=cat.revision) == cat
    assert catalog_loads(catalog_dumps(timing_catalog(rated=True))) == timing_catalog(rated=True)
    with pytest.raises(ValueError, match='JSON'):
        catalog_to_csv(timing_catalog(rated=True))


@pytest.mark.parametrize('key,value', [('units','inch'), ('version',True), ('version',2), ('schema','other')])
def test_wrong_catalog_contract(key,value):
    data = catalog_to_dict(timing_catalog())
    data[key] = value
    with pytest.raises(ValueError):
        catalog_from_dict(data)


def test_bad_source_duplicate_sku_and_manufacturer_series_conflict():
    cat = timing_catalog()
    for kwargs in (dict(belts=cat.belts*2), dict(sources=cat.sources*2),
                   dict(belts=(replace(cat.belts[0], source_id='absent'),))):
        with pytest.raises(ValueError):
            replace(cat, **kwargs)
    source = replace(cat.sources[0], identifier='other', manufacturer='Another')
    with pytest.raises(ValueError, match='seri'):
        replace(cat, sources=(*cat.sources, source), belts=(replace(cat.belts[0], source_id='other'),))


def test_li_la_are_not_treated_as_ld_and_pitch_is_not_datum():
    belt = v_catalog().belts[0]
    with pytest.raises(ValueError):
        replace(belt, datum_length_mm=None, inside_length_mm=1200.)
    with pytest.raises(ValueError):
        replace(timing_catalog().belts[0], pitch_mm=3.)
    with pytest.raises(ValueError):
        replace(timing_catalog().belts[0], pitch_length_mm=801.)
    assert replace(belt, inside_length_mm=1200., outside_length_mm=1300.).length_mm == belt.datum_length_mm


def test_unknown_json_fields_and_csv_units_duplicates_are_rejected():
    data = catalog_to_dict(timing_catalog())
    data['belts'][0]['production_approved'] = True
    with pytest.raises(ValueError):
        catalog_from_dict(data)
    text = catalog_to_csv(timing_catalog())
    with pytest.raises(ValueError):
        catalog_from_csv(text.replace(',mm,', ',inch,'), identifier='x', revision='x')
    with pytest.raises(ValueError):
        catalog_from_csv('kind,kind,units\nbelt,belt,mm\n', identifier='x', revision='x')
    with pytest.raises(ValueError):
        catalog_loads('{"schema":1,"schema":2}')
    with pytest.raises(ValueError):
        catalog_loads(catalog_dumps(timing_catalog()).replace('10.0','NaN'))


def test_bilinear_interpolation_independent_linear_plane_and_edges():
    table = timing_catalog(rated=True).ratings[0]
    # Fixture values are the plane q(z,n)=z/10+n/1000-1.
    for z, n in ((20,1000), (80,4000), (43,2226.5), (20,2000), (50,4000)):
        assert interpolate_power(table,z,n) == pytest.approx(z/10+n/1000-1)
    for z,n in ((19,1000), (81,2000), (28,999), (28,4001)):
        with pytest.raises(TableRangeError):
            interpolate_power(table,z,n)
    with pytest.raises(TableRangeError):
        interpolate_power(replace(table,interpolation='none'),28,1450)
    assert interpolate_power(replace(table,interpolation='none'),20,1000) == 2.


def test_correction_interpolation_no_extrapolation_and_no_silent_factor():
    correction = CorrectionTable('wrap_deg',(90.,180.),(.8,1.),'linear_declared')
    assert interpolate_1d(correction,135.) == pytest.approx(.9)
    for angle in (89.,181.):
        with pytest.raises(TableRangeError):
            interpolate_1d(correction,angle)
    with pytest.raises(TableRangeError):
        interpolate_1d(replace(correction,interpolation='none'),135.)
    for kwargs in (dict(axis=(180.,90.)), dict(factors=(1.,)), dict(factors=(1.,float('inf')))):
        with pytest.raises(ValueError):
            replace(correction,**kwargs)


@pytest.mark.parametrize('power,meets,required', [(2.,True,1), (2.5,True,1), (2.6,False,2)])
def test_v_capacity_above_equal_below_demand(power,meets,required):
    # Base 2 + additive .5, explicitly declared unity factors, one belt.
    cat=v_catalog(rated=True)
    req=request(family='v',target_rpm=725.,power_kw=power,service_factor=1.)
    if meets:
        candidate,=search_drives(req,cat).unverified
        capacity=candidate.capacity
    else:
        from modules.belt_drive.calculation import calculate
        from modules.belt_drive.design_search import candidate_specification
        from modules.belt_drive.engineering.ratings import TabulatedRatingProvider
        result=calculate(candidate_specification(req,cat.pulleys[0],cat.pulleys[1],cat.belts[0],1))
        capacity=TabulatedRatingProvider().evaluate(cat,cat.belts[0],result,1)
        assert not search_drives(req,cat).unverified
    assert capacity.per_belt_power_kw == 2.5 and capacity.meets_declared_demand is meets
    assert capacity.required_belts == required and capacity.capacity_margin == pytest.approx(2.5/power)
    assert capacity.status=='PROVISIONAL' and not capacity.manufacturer_verified


def test_wrap_factor_additive_power_order_and_width_variants():
    cat=v_catalog(rated=True)
    table=cat.ratings[0]
    changed=replace(table,corrections=(CorrectionTable('wrap_deg',(90.,180.),(.8,1.),'linear_declared'),table.corrections[1]))
    candidate,=search_drives(request(family='v',target_rpm=725.),replace(cat,ratings=(changed,))).unverified
    # Fixed independent wrap angle from Stage 1 Decimal reference.
    expected=(2.+.5)*(.8+(165.638488437083437-90.)/90.*.2)
    assert candidate.capacity.per_belt_power_kw==pytest.approx(expected)
    candidates=search_drives(request(priority='capacity'),timing_catalog(rated=True,widths=(10.,20.))).unverified
    assert [x.belt.width_mm for x in candidates]==[20.,10.]
    assert candidates[0].capacity.per_belt_power_kw==pytest.approx(6.5)
    assert candidates[1].capacity.per_belt_power_kw==pytest.approx(3.25)


@pytest.mark.parametrize('changes', [dict(additional_power_kw=None),dict(corrections=()),dict(method_reference=''),
    dict(reference_width_mm=None),dict(small_pulley_axis=(60.,80.))])
def test_missing_or_out_of_range_rating_data_never_becomes_approval(changes):
    cat=timing_catalog(rated=True)
    candidate,=search_drives(request(),with_rating(cat,**changes)).unverified
    assert candidate.capacity.status=='NOT_EVALUATED' and candidate.capacity.total_power_kw is None


@pytest.mark.parametrize('status',['OUTDATED','INCOMPLETE'])
def test_old_or_incomplete_source_cannot_produce_capacity(status):
    cat=timing_catalog(rated=True)
    cat=replace(cat,sources=(replace(cat.sources[0],verification_status=status),))
    candidate,=search_drives(request(),cat).unverified
    assert candidate.capacity.status=='NOT_EVALUATED'


def test_no_service_factor_default_or_load_class_to_factor_guess():
    req=request(service_factor=None,daily_hours=16.,load_characteristic='shock',starting_conditions='frequent')
    candidate,=search_drives(req,timing_catalog(rated=True)).unverified
    assert candidate.capacity.design_power_kw is None and candidate.capacity.status=='NOT_EVALUATED'
    high,=search_drives(replace(req,service_factor=3.),timing_catalog(rated=True,widths=(20.,))).unverified
    assert high.capacity.design_power_kw==4.5 and high.capacity.total_power_kw==pytest.approx(6.5)


def test_missing_declared_limits_do_not_grant_engineering_clearance():
    candidate,=search_drives(request(),timing_catalog()).unverified
    missing={x.code for x in candidate.checks if x.severity=='NOT_EVALUATED'}
    assert {'SPEED_LIMIT','MINIMUM_PULLEY','ADJUSTMENT_TRAVEL','TENSION','CATALOG_COMPATIBILITY'}<=missing
    assert not candidate.engineering_approved
