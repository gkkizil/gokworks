from dataclasses import replace,FrozenInstanceError
import math
from threading import Event
import subprocess
import sys
import pytest
from core.unfolding import UnfoldService,UnfoldCancelled
from core.unfolding.models import Material,SplitOptions,JointOptions,SeamOptions
from core.unfolding.geometry import curve_length,bend_allowance
from .helpers import request_for,calculate


def test_reference_cylinder_and_inner_reference_mass():
    r=calculate();m=r.parts[0].metrics
    assert m.bounds_mm==pytest.approx((0.,0.,942.4777960769379,200.))
    assert m.net_area_mm2==pytest.approx(188495.5592153876)
    assert m.mass_kg is None and r.metrics['mass_kg'] is None
    inner=calculate(thickness=2.,dimension_reference='inner',material=Material('S235',7850.))
    assert inner.normalized_inputs['parameters']['diameter']==302.
    assert inner.normalized_inputs['dimension_reference']=='mid'
    assert inner.normalized_inputs['source_dimension_reference']=='inner'
    assert inner.normalized_inputs['reference_parameters_mm']['diameter']==300.
    assert inner.parts[0].metrics.bounds_mm[2]==pytest.approx(948.7609813841175)
    assert inner.metrics['mass_kg']==pytest.approx(2.979109481546129)


def test_reference_frustum_and_exact_arc_lengths():
    r=calculate('cone','frustum');q=r.quality_metrics
    assert q['slant_height_mm']==pytest.approx(213.60009363293827)
    assert q['outer_sector_radius_mm']==pytest.approx(427.20018726587654)
    assert q['inner_sector_radius_mm']==pytest.approx(213.60009363293827)
    assert q['sector_angle_deg']==pytest.approx(126.40443897182102)
    arcs=[c for c in r.parts[0].geometry_2d.outer if c.kind=='arc']
    assert [curve_length(c) for c in arcs]==pytest.approx((942.4777960769379,471.23889803846896))
    assert r.metrics['cutting_area_mm2']==pytest.approx(math.pi*225*math.sqrt(45625))


@pytest.mark.parametrize('reference',['inner','mid','outer'])
def test_inch_mm_equivalence(reference):
    a=calculate(parameters={'diameter':254.,'height':127.},thickness=2.032,dimension_reference=reference)
    b=calculate(parameters={'diameter':10.,'height':5.},thickness=.08,input_units='inch',dimension_reference=reference)
    assert a.parts[0].metrics==b.parts[0].metrics
    assert a.input_hash==b.input_hash


def test_frustum_thickness_is_normal_offset_at_fixed_end_planes():
    r=calculate('cone','frustum',thickness=2.,dimension_reference='inner')
    p=r.normalized_inputs['parameters']
    # Normal distance from reference line r + .375 z - 150 = 0.
    actual=((p['bottom_diameter']-300)/2)/math.sqrt(1+.375**2)
    assert actual==pytest.approx(1.)
    assert p['top_diameter']-150==pytest.approx(p['bottom_diameter']-300)


@pytest.mark.parametrize('scale',[1e-5,1.,1000.])
def test_equal_cone_and_cylinder_limit_remain_stable(scale):
    a=calculate('cone','frustum',parameters={'bottom_diameter':300*scale,'top_diameter':300*scale,'height':200*scale})
    b=calculate(parameters={'diameter':300*scale,'height':200*scale})
    assert a.quality_metrics['cylinder_limit'] and a.metrics['net_area_mm2']==pytest.approx(b.metrics['net_area_mm2'])


def test_full_cone_tip_has_valid_non_degenerate_mesh():
    r=calculate('cone','full')
    assert r.quality_metrics['minimum_triangle_area_mm2']>0
    assert len(r.parts[0].mesh_3d.triangles)>8
    assert r.parts[0].metrics.net_area_mm2==pytest.approx(math.pi*150*250)


def test_bevel_points_lie_on_the_actual_cutting_plane():
    r=calculate(variant='bevel',parameters={'cut_angle_deg':25.,'plane_azimuth_deg':37.},seam_options=SeamOptions(17.))
    mesh=r.parts[0].mesh_3d;normal=(math.tan(math.radians(25))*math.cos(math.radians(37)),
                                math.tan(math.radians(25))*math.sin(math.radians(37)),1.)
    assert max(abs(sum(a*b for a,b in zip(p,normal))-200) for p in mesh.vertices[1::2])<1e-10
    assert r.quality_metrics['chord_error_bound_mm']<=.02
    for mapping in r.parts[0].mappings:
        assert mapping.developed[1]==pytest.approx(mapping.assembled[2])


@pytest.mark.parametrize('family,variant',[('cylinder','straight'),('cylinder','bevel'),('cone','frustum'),('cone','full')])
def test_split_and_lap_count_allowance_only_at_selected_seams(family,variant):
    whole=calculate(family,variant)
    split=calculate(family,variant,split_options=SplitOptions(4),joint_options=JointOptions('lap',5.))
    assert len(split.parts)==4
    assert split.metrics['net_area_mm2']==pytest.approx(whole.metrics['net_area_mm2'])
    if family=='cone':expected=4*whole.quality_metrics['slant_height_mm']*5
    else:expected=4*200*5
    assert split.metrics['cutting_area_mm2']-split.metrics['net_area_mm2']==pytest.approx(expected,abs=.1)
    assert split.quality_metrics['seam_closure_error_mm']<1e-9


def test_rectangular_reducer_matches_independent_trapezoid_surface_area():
    r=calculate('rectangular_reducer','centered')
    # Two 400/200 trapezoids at sqrt(300²+75²); two 300/150 at sqrt(300²+100²).
    expected=600*math.sqrt(95625)+450*math.sqrt(100000)
    assert len(r.parts)==4 and r.metrics['net_area_mm2']==pytest.approx(expected)
    assert r.quality_metrics['edge_length_error_mm']<1e-10


def test_square_round_is_an_edge_preserving_explicit_faceted_surface():
    r=calculate('rect_to_round','centered_faceted')
    assert r.calculation_method=='faceted_developable' and len(r.parts)==8
    assert r.quality_metrics['edge_length_error_mm']<1e-8
    assert r.metrics['net_area_mm2']==pytest.approx(r.quality_metrics['surface_area_3d_mm2'],abs=1e-6)
    assert r.quality_metrics['chord_error_bound_mm']<=.02
    assert all(not p.bending_lines for p in r.parts)


@pytest.mark.parametrize('segments,angle',[(2,45.),(4,90.),(7,135.)])
def test_elbow_end_pose_and_miter_interfaces(segments,angle):
    r=calculate('segmented_elbow','constant_diameter',parameters={'segments':segments,'total_angle_deg':angle,
        'inlet_extension':25.,'outlet_extension':30.})
    end=r.quality_metrics['outlet_center'];a=math.radians(angle)
    assert end==pytest.approx((300*(1-math.cos(a))+30*math.sin(a),0.,300*math.sin(a)+30*math.cos(a)),abs=1e-10)
    assert r.quality_metrics['inlet_center']==(0.,0.,-25.)
    assert len(r.parts)==segments and r.quality_metrics['end_segments_are_half']
    for first,second in zip(r.parts,r.parts[1:]):
        upper=first.mesh_3d.vertices[1::2];lower=second.mesh_3d.vertices[::2]
        assert len(upper)==len(lower)
        assert max(math.dist(a,b) for a,b in zip(upper,lower))<1e-10


def test_result_and_request_are_snapshots_and_cancel_does_not_replace_cache():
    s=UnfoldService();params={'diameter':300.,'height':200.};req=request_for(parameters=params);params['diameter']=12.
    result=s.calculate(req);stop=Event();stop.set()
    with pytest.raises(UnfoldCancelled):s.calculate(req,stop)
    again=s.calculate(replace(req,request_id='new-id',revision=4))
    assert again.input_hash==result.input_hash and again.revision==4
    assert again.parts[0].assembly_id=='new-id' and result.parts[0].assembly_id==req.request_id
    with pytest.raises(FrozenInstanceError):result.status='error'
    with pytest.raises(TypeError):result.normalized_inputs['thickness']=2.


def test_price_units_and_bend_allowance_are_separate_from_geometric_development():
    a=calculate(material=Material('Test',None,2.,'m2','TRY'))
    assert a.metrics['material_cost']==pytest.approx(.3769911184307752)
    b=calculate(material=Material('Test',None,2.,'m','TRY'))
    assert b.metrics['material_cost']==pytest.approx(4.569911184307752)
    assert bend_allowance(90.,2.,1.,.4)==pytest.approx(3.7699111843077517)
    with pytest.raises(ValueError):bend_allowance(90.,2.,1.,1.2)


def test_import_and_calculation_do_not_load_gui_com_or_cad():
    code='''
import sys
from core.unfolding import UnfoldService,UnfoldRequest
r=UnfoldService().calculate(UnfoldRequest(parameters={'diameter':300.,'height':200.}))
assert r.status=='success'
assert not any(k in sys.modules for k in ('PySide6','pythoncom','OCP','tkinter'))
'''
    subprocess.run([sys.executable,'-c',code],check=True,timeout=20)
