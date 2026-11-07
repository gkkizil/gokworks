"""Independent regressions from the post-expansion code audit."""
from dataclasses import replace
import math
import pytest
from core.unfolding import UnfoldService, ExportOptions
from core.unfolding.models import DevelopmentOptions, Material
from core.unfolding.source_models import model
from core.unfolding.geometry import polygon
from modules.sheet_unfolding.service import EngineService
from .test_source_models import request


@pytest.mark.parametrize('sid', ['rectangle-to-round-one-angle', 'rectangle-to-round-two-angle'])
def test_length_minima_are_in_mm_independent_of_input_units(sid):
    service = UnfoldService()
    for length, expected in ((.001, True), (.0005, False)):
        mm = request(sid, parameters={'drop': length})
        kinds = {f['id']: f['kind'] for f in model(sid)['fields']}
        inch = replace(mm, input_units='inch', parameters={
            key: value/25.4 if kinds[key] == 'length' else value for key, value in mm.parameters.items()})
        assert service.validate(mm).valid is expected
        assert service.validate(inch).valid is expected


def test_allowance_limit_is_in_mm_in_both_input_units():
    service = UnfoldService()
    mm = request('cylinder', model_options={'lap_top': 100000.001})
    inch = replace(mm, input_units='inch', parameters={k: v/25.4 for k, v in mm.parameters.items()},
                   model_options={'lap_top': 100000.001/25.4})
    assert not service.validate(mm).valid
    assert not service.validate(inch).valid


@pytest.mark.parametrize('offset', [-100., 100.])
def test_variable_duct_allowances_use_the_actual_planar_projection(offset):
    service = UnfoldService(0)
    nominal = service.calculate(request('rectangular-duct-reducer-offset', parameters={'Y': offset}))
    expanded = service.calculate(request('rectangular-duct-reducer-offset', parameters={'Y': offset},
                                          model_options={'lap_top': 5., 'lap_left': 5.}))
    assert nominal.status == expanded.status == 'success', expanded.errors
    assert len(expanded.parts) == 4
    for before, after in zip(nominal.parts, expanded.parts):
        if 'wall' in before.id:
            assert polygon(after.geometry_2d).buffer(1e-7).covers(polygon(before.geometry_2d))
            assert after.metrics.cutting_area_mm2 > before.metrics.cutting_area_mm2
        else:
            assert after.geometry_2d == before.geometry_2d


def test_cylinder_limit_levels_are_placed_at_their_real_step_heights(tmp_path):
    pytest.importorskip('OCP')
    from core.unfolding.cad import read_step
    service = UnfoldService()
    result = service.calculate(request('cone-frustum-levels',
        parameters={'D': 200., 'd': 200., 'H': 300., 'levels': 3}))
    assert result.status == 'success'
    path = tmp_path/'three-level-cylinder.step'
    outcome = service.export(result, ExportOptions(str(path), 'step',step_kind='surface'))
    assert outcome.status == 'complete', outcome.errors
    _, stats = read_step(path)
    assert stats['faces'] == 3
    assert stats['area_mm2'] == pytest.approx(math.pi*200*300, rel=1e-9)
    assert stats['bounds_mm'][2] == pytest.approx(0., abs=1e-6)
    assert stats['bounds_mm'][5] == pytest.approx(300., abs=1e-6)


@pytest.mark.parametrize('sid', ['cone', 'cone-frustum', 'cone-frustum-levels'])
@pytest.mark.parametrize('divisions', [12, 48])
def test_source_cone_helpers_follow_the_requested_count(sid, divisions):
    result = UnfoldService().calculate(request(sid, model_options={'helper_divisions': divisions}))
    assert result.status == 'success', result.errors
    for part in result.parts:
        assert len(part.construction_lines) == divisions-1
        assert len(part.true_lengths) == divisions+1
        lengths = {t.id: t for t in part.true_lengths}
        for line in part.construction_lines:
            assert line.id in lengths
            assert math.dist(line.start, line.end) == pytest.approx(lengths[line.id].length_mm, abs=1e-7)
            assert lengths[line.id].length_mm == pytest.approx(math.dist(lengths[line.id].start, lengths[line.id].end))


def test_adapter_project_roundtrip_keeps_material_and_development_contracts():
    original = request('cylinder', thickness=0.,
        material=Material('Özel sac', 8100., 0., price_unit='m2', currency='EUR'),
        development_options=DevelopmentOptions(chord_error_mm=.005, mesh_error_mm=.1, max_samples=8192))
    restored = EngineService.engine_request(EngineService.page_request(original))
    assert restored == original


def test_a_new_identifier_in_a_known_family_is_not_assumed_implemented():
    from core.unfolding.shapes.source_dispatch import supported
    assert not supported({'family':'Silindir','source_id':'new-unimplemented-cylinder-variant'})


def test_finite_bend_inputs_cannot_return_infinite_zone_results():
    from core.unfolding.bend_profiles import BendInput, develop_profile
    with pytest.raises(ValueError):
        develop_profile((10.,10.),(BendInput(.01,1e308,0.),),1e308,dimension_reference='tangent')


def test_bend_allowance_rejects_derived_overflow():
    from core.unfolding.geometry import bend_allowance
    with pytest.raises(ValueError):
        bend_allowance(90.,1e308,1e308,1.)


def test_slender_rectangular_ribbon_preserves_the_whole_material_area():
    from core.unfolding.shapes.development import ribbon
    n={'thickness':0.,'request_id':'slender-reference','model_options':{'helper_divisions':24}}
    part,error=ribbon('slender',((0.,0.,0.),(.001,0.,0.)),
        ((0.,0.,1e7),(.001,0.,1e7)),n,Material(),DevelopmentOptions())
    assert part.metrics.net_area_mm2==pytest.approx(10000.,abs=1e-5)
    assert error<=1e-6


def test_cone_cylinder_limit_adds_strip_lap_beyond_the_existing_joint_lap():
    from core.unfolding.models import JointOptions
    r=UnfoldService().calculate(request('cone-frustum',parameters={'D':200.,'d':200.,'H':300.},
        joint_options=JointOptions('lap',10.),model_options={'strip_lap':5.}))
    assert r.status=='success',r.errors
    assert r.metrics['cutting_area_mm2']==pytest.approx((math.pi*200+15)*300,abs=1e-6)
