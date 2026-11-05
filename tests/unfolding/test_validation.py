from dataclasses import replace
import pytest
from core.unfolding import UnfoldService,UnfoldRequest
from core.unfolding.models import DevelopmentOptions,JointOptions,Material,SplitOptions
from .helpers import request_for


@pytest.mark.parametrize('change',[
    {'schema_version':2},{'schema_version':True},{'revision':-1},{'revision':False},{'input_units':'cm'},
    {'thickness':-1.},{'thickness':float('nan')},{'dimension_reference':'inside'},
    {'parameters':{'diameter':0.,'height':200.}}, {'parameters':{'diameter':True,'height':200.}},
    {'parameters':{'diameter':300.,'height':-2.}}, {'parameters':{'diameter':300.,'height':200.,'foo':1.}},
    {'split_options':SplitOptions(0)},{'split_options':SplitOptions(True)},
    {'joint_options':JointOptions('butt',5.)},{'joint_options':JointOptions('lap',0.)},
    {'material':Material('X',-2.)},{'material':Material('X',7850.,-2.)},
    {'development_options':DevelopmentOptions(kerf_mm=.2)},
    {'development_options':DevelopmentOptions(chord_error_mm=0.)}])
def test_invalid_input_does_not_produce_exportable_contours(change):
    req=replace(request_for(),**change);s=UnfoldService();v=s.validate(req);r=s.calculate(req)
    assert not v.valid and r.status=='error' and not r.parts and r.errors
    assert not r.capabilities.get('dxf',False)


def test_unsupported_families_and_unsafe_variants_are_not_advertised():
    s=UnfoldService()
    assert {x.shape_id for x in s.list_shapes()}=={'cylinder','cone','rectangular_reducer','rect_to_round','segmented_elbow'}
    for shape in ('dome','helix','branch','eccentric_cone'):
        r=s.calculate(UnfoldRequest(shape_id=shape))
        assert r.status=='error' and not r.parts
    with pytest.raises(ValueError):s.get_schema('cylinder','loft')
    assert s.calculate(request_for('cone','full',thickness=2.,dimension_reference='outer')).status=='error'
    assert s.calculate(request_for('rect_to_round','centered_faceted',thickness=2.,dimension_reference='inner')).status=='error'


def test_physical_cut_elbow_and_sampling_limits_are_checked():
    s=UnfoldService()
    for req in (request_for(variant='bevel',parameters={'height':10.,'cut_angle_deg':60.}),
                request_for('segmented_elbow','constant_diameter',parameters={'center_radius':90.}),
                request_for(parameters={'diameter':10.},thickness=10.,dimension_reference='outer'),
                request_for(variant='bevel',development_options=DevelopmentOptions(max_samples=16,chord_error_mm=.00001))):
        assert s.calculate(req).status=='error'


def test_schema_is_complete_and_serializable_without_a_second_ui_parameter_list():
    from core.unfolding.models import to_data
    import json
    s=UnfoldService()
    for summary in s.list_shapes():
        for variant in summary.variants:
            schema=s.get_schema(summary.shape_id,variant)
            assert all(f.label and f.dimension_id and f.description and f.required for f in schema.fields)
            assert json.loads(json.dumps(to_data(schema)))['shape_id']==summary.shape_id


def test_extreme_mesh_request_is_rejected_before_allocating_millions_of_points():
    req=request_for(parameters={'diameter':1e7,'height':1e6},split_options=SplitOptions(64),
                    development_options=DevelopmentOptions(mesh_error_mm=.0001,max_samples=8192))
    r=UnfoldService().calculate(req)
    assert r.status=='error' and not r.parts and 'bütçesi' in r.errors[0].message
