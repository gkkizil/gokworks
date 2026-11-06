"""Public inventory contracts, independent references, and all-model acceptance cases."""
from dataclasses import replace
import json
import math
from pathlib import Path
import pytest
from core.unfolding import UnfoldService,UnfoldRequest
from core.unfolding.models import Material,ExportOptions
from core.unfolding.source_models import inventory,model
from core.unfolding.geometry import polygon

ROOT=Path(__file__).resolve().parents[2]
EXAMPLES=json.loads((ROOT/'docs/unfolding/examples/source_models.json').read_text(encoding='utf-8'))['models']
BY_ID={e['source_id']:e['request'] for e in EXAMPLES}


def request(sid,**changes):
    raw=dict(BY_ID[sid]);params=dict(raw['parameters']);params.update(changes.pop('parameters',{}));raw['parameters']=params;raw.update(changes)
    return UnfoldRequest(**raw)


def calculate(sid,**changes):
    result=UnfoldService(0).calculate(request(sid,**changes))
    assert result.status=='success',[(e.code,e.message) for e in result.errors]
    return result


def dxf_measure(path):
    """Independent DXF bulge integration, not the engine contour measurement."""
    import ezdxf
    doc=ezdxf.readfile(path);assert doc.units==4 and not doc.audit().errors
    areas=[];length=0.
    for entity in doc.modelspace().query('LWPOLYLINE CIRCLE'):
        if entity.dxf.layer not in ('CUT_OUTER','CUT_INNER'):continue
        if entity.dxftype()=='CIRCLE':area=math.pi*entity.dxf.radius**2;perimeter=math.tau*entity.dxf.radius
        else:
            assert entity.closed
            pts=list(entity.get_points('xyb'));area=0.;perimeter=0.
            for a,b in zip(pts,pts[1:]+pts[:1]):
                area+=(a[0]*b[1]-a[1]*b[0])/2;chord=math.hypot(b[0]-a[0],b[1]-a[1]);bulge=a[2]
                if abs(bulge)>1e-14:
                    theta=4*math.atan(bulge);radius=chord/(2*abs(math.sin(theta/2)));area+=radius**2*(theta-math.sin(theta))/2;perimeter+=radius*abs(theta)
                else:perimeter+=chord
        areas.append(abs(area)*(1 if entity.dxf.layer=='CUT_OUTER' else -1));length+=perimeter
    return sum(areas),length


def test_exact_complete_inventory_and_case_sensitive_fields():
    data=inventory();models=data['models'];assert len(models)==len(BY_ID)==191
    assert sum(len(m['fields']) for m in models)==1136
    assert len({m['family'] for m in models})==51 and len({m['category'] for m in models})==11
    assert len(data['cut_sets'])==53
    service=UnfoldService();assert len(service.list_source_models())==191
    assert {v for shape in service.list_shapes() for v in shape.source_ids}==set(BY_ID)
    for m in models:
        schema=service.get_schema(**m['internal_id']);assert schema.source_id==m['source_id']
        assert [f.id for f in schema.fields]==[f['id'] for f in m['fields']]
        assert [f.default for f in schema.fields]==[f['default'] for f in m['fields']]
        assert schema.model_options['source_url']==m['source_url']
        if m['source_features'].get('meanOnly'):assert schema.supported_dimension_references==('mid',)
    assert {'W','w'}<={f.id for f in service.get_schema(**model('rectangular-duct-reducer')['internal_id']).fields}


@pytest.mark.parametrize('sid',list(BY_ID))
def test_every_source_model_has_valid_geometry_units_and_readback_dxf(sid,tmp_path):
    r=calculate(sid)
    assert r.parts and r.metrics['part_count']==sum(p.quantity for p in r.parts)
    assert r.quality_metrics['contour_closure_error_mm']<=1e-6
    assert r.capabilities['production_process_verified'] is False
    for part in r.parts:
        poly=polygon(part.geometry_2d);assert poly.is_valid and poly.area>0
        out=UnfoldService().export(r,ExportOptions(str(tmp_path/(part.id+'.dxf')),part_ids=(part.id,)))
        assert out.status=='complete',out.errors
        area,length=dxf_measure(out.files[0].path)
        assert area==pytest.approx(part.metrics.cutting_area_mm2,rel=1e-8,abs=1e-5)
        assert length==pytest.approx(part.metrics.cutting_length_mm,rel=1e-9,abs=1e-5)
    # Every model also has an invalid case which cannot yield exportable geometry.
    bad=dict(BY_ID[sid]['parameters']);bad[model(sid)['fields'][0]['id']]=0
    invalid=UnfoldService().calculate(replace(request(sid),parameters=bad))
    assert invalid.status=='error' and not invalid.parts


@pytest.mark.parametrize('sid',list(BY_ID))
def test_all_model_units_transform_only_lengths(sid):
    req=request(sid);m=model(sid);params={f['id']:req.parameters[f['id']]/25.4 if f['kind']=='length' else req.parameters[f['id']] for f in m['fields']}
    inch=replace(req,input_units='inch',parameters=params)
    service=UnfoldService(0);a,b=service.validate(req),service.validate(inch)
    assert a.valid and b.valid
    aa,bb=a.normalized_inputs['parameters'],b.normalized_inputs['parameters']
    assert set(aa)==set(bb)
    for k in aa:assert aa[k]==pytest.approx(bb[k],rel=1e-11,abs=1e-9)
    assert service.validate(replace(req,model_options={'helper_divisions':13})).errors


def test_cylinder_reference_surface_and_units_independent():
    for reference,t,expected in [('mid',0.,200.),('inner',2.,202.),('outer',2.,198.)]:
        r=calculate('cylinder',thickness=t,dimension_reference=reference)
        part=r.parts[0];assert part.metrics.bounds_mm[2]==pytest.approx(math.pi*expected,abs=1e-9)
        assert part.metrics.bounds_mm[3]==300.
        assert part.metrics.net_area_mm2==pytest.approx(math.pi*expected*300.,rel=1e-12)
    assert UnfoldService().calculate(request('cylinder',thickness=200.,dimension_reference='outer')).status=='error'


def test_alternative_cylinder_and_cone_inputs_are_equivalent():
    pairs=[('cylinder-top-angle',{'D':200.,'H':250.,'A':45.}),('cylinder-top-angle-side',{'D':200.,'H':150.,'A':45.}),('cylinder-angled-top',{'D':200.,'H1':150.,'H2':350.})]
    results=[calculate(sid,parameters=p) for sid,p in pairs]
    assert max(r.metrics['net_area_mm2'] for r in results)-min(r.metrics['net_area_mm2'] for r in results)<1e-5
    areas=[]
    for sid,p in [('cone-frustum',{'H':200.}),('cone-frustum-apex-height',{'Ha':400.}),('cone-frustum-angle',{'A':math.degrees(2*math.atan(75/200))})]:
        areas.append(calculate(sid,parameters=p).metrics['net_area_mm2'])
    expected=math.pi*(150+75)*math.hypot(200,75)
    assert areas==pytest.approx([expected]*3,rel=1e-12)


def test_oval_is_a_stadium_not_an_ellipse_and_prism_is_polygon():
    oval=calculate('oval-cylinder');assert oval.metrics['net_area_mm2']==pytest.approx((2*(300-200)+math.pi*200)*400,rel=1e-12)
    prism=calculate('prism');assert prism.metrics['net_area_mm2']==pytest.approx(5*800*math.sin(math.pi/5)*900,rel=1e-12)
    side=800*math.sin(math.pi/5);assert prism.parts[0].metrics.bounds_mm[2]==pytest.approx(5*side)


def test_oblique_cylinder_alternative_and_skew_cone_surface_area_reference():
    p={'D':250.,'H':700.,'X':100.};a=calculate('oblique-cylinder',parameters=p)
    b=calculate('oblique-cylinder-angle',parameters={'D':250.,'Lc':math.hypot(700,100),'A':math.degrees(math.atan2(700,100))})
    assert a.metrics['net_area_mm2']==pytest.approx(b.metrics['net_area_mm2'],rel=1e-10)
    r=calculate('oblique-cone-offset');R,rr,H,X=450.,200.,1200.,450.;N=20000
    integral=sum(math.sqrt(H*H+(rr-R+X*math.cos(math.tau*(i+.5)/N))**2) for i in range(N))*math.tau/N
    assert r.metrics['net_area_mm2']==pytest.approx((R+rr)/2*integral,rel=2e-4)


def test_miter_and_segmented_bend_independent_material_area_and_piece_counts():
    r=calculate('mitred-elbow-90');assert len(r.parts)==2
    assert r.metrics['net_area_mm2']==pytest.approx(math.pi*250*(800+900),rel=2e-5)
    r=calculate('segmented-bend-90');length=2*4000*math.tan(math.pi/16)*4
    assert len(r.parts)==5 and r.metrics['net_area_mm2']==pytest.approx(math.pi*2000*length,rel=2e-5)


def test_branch_intersections_lie_on_both_surfaces_independent():
    r=calculate('pipe-to-pipe-angle-branch');a=math.pi/4;axis=(math.sin(a),0.,math.cos(a))
    for x,y,z in r.quality_metrics['intersection_points_3d']:
        assert math.hypot(x,y)==pytest.approx(200.,abs=1e-7)
        q=(x,y-50.,z);u=sum(v*w for v,w in zip(q,axis));radial=math.sqrt(max(0.,sum(v*v for v in q)-u*u))
        assert radial==pytest.approx(125.,abs=1e-7)
    trunk=calculate('pipe-to-pipe-angle-trunk');assert len(trunk.parts[0].geometry_2d.holes)==1
    assert trunk.metrics['net_area_mm2']<math.pi*400*1000


def test_allowances_follow_wall_edges_and_quantities_are_applied_once():
    req=request('rectangular-duct-straight',thickness=2.,material=Material('Çelik',7850.),model_options={'lap_top':10.,'lap_left':5.})
    r=UnfoldService().calculate(req);assert r.status=='success'
    assert len(r.parts)==4 and r.metrics['net_area_mm2']==1050000.
    assert r.metrics['cutting_area_mm2']==pytest.approx(1083000.)
    assert r.metrics['mass_kg']==pytest.approx(1083000*2e-9*7850)
    assert all(p.metrics.cutting_area_mm2==p.metrics.net_area_mm2 for p in r.parts[:2])
    r=calculate('vessel-end-cap-hemispherical',thickness=2.,material=Material('Çelik',7850.))
    assert len(r.parts)==1 and r.parts[0].quantity==8
    assert r.metrics['mass_kg']==pytest.approx(r.parts[0].metrics.mass_kg*8)


def test_head_and_helix_approximation_is_quantified_and_warned():
    a=calculate('vessel-end-cap-hemispherical');b=calculate('vessel-end-cap-hemispherical',parameters={'n':24})
    assert b.quality_metrics['circumferential_length_deficit_ratio']<a.quality_metrics['circumferential_length_deficit_ratio']
    r=calculate('helix-deformed');assert r.quality_metrics['required_inner_edge_engineering_strain']>0
    assert not r.capabilities['step_surface']
    for r in (a,b,r,calculate('helix-tapered')):assert any(w.code=='APPROXIMATION' for w in r.warnings)
    for sid in ('helical-ramp-triangulated','helix-angled-flight','helix-tapered','helix-deformed'):
        assert not UnfoldService().validate(replace(request(sid),dimension_reference='outer')).valid
        assert not UnfoldService().validate(replace(request(sid),model_options={'numbering':True})).valid


def test_source_capability_limits_fail_closed_not_silently_ignored():
    r=UnfoldService().calculate(request('pipe-to-pipe-angle-branch',model_options={'heel':True}))
    assert r.status=='error' and 'Topuk' in r.errors[0].message
    for sid in ('cylinder','rectangular-duct-straight'):
        assert not UnfoldService().validate(replace(request(sid),model_options={'made_up':1})).valid
    for sid in ('rectangle-to-rectangle-angled-top','rectangle-to-rectangle-angled-top-base'):
        assert not UnfoldService().validate(request(sid,parameters={'diagonal':3})).valid
        a=calculate(sid);b=calculate(sid,parameters={'diagonal':2})
        assert a.parts[0].mesh_3d.triangles!=b.parts[0].mesh_3d.triangles


@pytest.mark.parametrize('sid',[m['source_id'] for m in inventory()['models'] if len(m['cut_options'])>1])
def test_every_cut_option_changes_real_piece_layout_and_preserves_material(sid):
    m=model(sid);base=calculate(sid);baseline=base.metrics['net_area_mm2']
    for cut in m['cut_options']:
        r=calculate(sid,model_options={'cut_type':cut['value']})
        value=cut['value'];split=4 if value.startswith('4_') else 3 if value.startswith('3_') else 2 if value.startswith('2_') else 1
        if m['category']=='Segmentli dirsekler':expected=BY_ID[sid]['parameters']['segments']*split
        elif m['category']=='Dirsekler':expected=len(base.parts)*split
        elif m['source_id']=='rain-head-conical':expected=2 if value=='1_all' else 1
        else:expected=BY_ID[sid]['parameters'].get('levels',1)*split
        assert len(r.parts)==expected
        if sid!='rain-head-conical':
            perimeter=sum(p.metrics.cutting_length_mm*p.quantity for p in r.parts)
            assert r.metrics['net_area_mm2']==pytest.approx(baseline,abs=.08*perimeter)


@pytest.mark.parametrize('sid',list(BY_ID))
def test_every_model_field_affects_geometry_or_rejects_its_perturbation(sid):
    m=model(sid);base=calculate(sid)
    def signature(r):return repr([(p.quantity,p.geometry_2d,p.mesh_3d) for p in r.parts])
    original=signature(base)
    for field in m['fields']:
        key=field['id'];old=BY_ID[sid]['parameters'][key]
        if field['kind']=='option':value=next(v for v,label in field['options'] if v!=old)
        elif field['kind']=='count':value=old+1
        elif field['kind']=='angle':value=old+1.
        else:value=old*1.01 if old else 1.
        result=UnfoldService(0).calculate(request(sid,parameters={key:value}))
        if sid=='cone-to-pipe-90-branch' and key=='H':
            assert UnfoldService(0).calculate(request(sid,parameters={'H':1.})).status=='error'
            continue  # Main height constrains validity; it does not change this branch's cut geometry.
        assert result.status=='error' or signature(result)!=original,(sid,key,'silently ignored field')


def test_cylindrical_cone_limit_and_real_top_edge_allowance():
    r=calculate('cone-frustum',parameters={'D':200.,'d':200.,'H':300.},model_options={'lap_top':5.})
    assert r.metrics['net_area_mm2']==pytest.approx(math.pi*200*300)
    assert r.metrics['cutting_area_mm2']==pytest.approx(math.pi*200*305)


def test_new_unknown_catalogue_family_is_not_assumed_implemented():
    from core.unfolding.shapes.source_dispatch import supported
    assert not supported({'family':'unknown-unimplemented-family'})


def test_unavailable_common_seam_controls_fail_closed():
    from core.unfolding.models import SeamOptions
    for sid in ('oval-cylinder','prism','pyramid','rectangular-duct-y','helical-ramp-triangulated','vessel-end-cap-hemispherical','pipe-to-pipe-angle-branch'):
        req=request(sid);service=UnfoldService();schema=service.get_schema(req.shape_id,req.variant_id)
        assert not schema.seam_supported
        assert not service.validate(replace(req,seam_options=SeamOptions(30.))).valid
    for sid in ('cylinder','cone-frustum','oblique-cone-offset','segmented-bend-angle'):
        a=calculate(sid);b=calculate(sid,seam_options=SeamOptions(30.))
        assert a.parts[0].mesh_3d.vertices!=b.parts[0].mesh_3d.vertices


def test_helpers_are_separate_from_adaptive_geometry_and_numbering_is_optional():
    for sid in ('pipe-to-pipe-angle-branch','pipe-to-pipe-angle-trunk','mitred-elbow-cone-cone-angle','vessel-end-cap-elliptical','rectangular-duct-straight'):
        a=calculate(sid,model_options={'helper_divisions':12})
        b=calculate(sid,model_options={'helper_divisions':48})
        assert sum(len(p.true_lengths) for p in b.parts)>sum(len(p.true_lengths) for p in a.parts)
        assert a.metrics['net_area_mm2']==pytest.approx(b.metrics['net_area_mm2'])
        for part in b.parts:
            assert all(t.length_mm==pytest.approx(math.dist(t.start,t.end),abs=1e-8) for t in part.true_lengths)
        c=calculate(sid,model_options={'numbering':False})
        assert not any(p.true_lengths for p in c.parts)
        assert not any(line.id for p in c.parts for line in p.construction_lines+p.bending_lines)


SINGLE_BRANCHES=[m['source_id'] for m in inventory()['models'] if m['category']=='Branşmanlar ve T parçalar' and m['source_id'].endswith(('-branch','-trunk'))]


@pytest.mark.parametrize('sid',SINGLE_BRANCHES)
def test_every_single_branch_intersection_satisfies_both_analytic_surfaces(sid):
    r=calculate(sid);p=BY_ID[sid]['parameters'];cone='to-cone-' in sid or 'to-oblique-cone-' in sid;oblique='to-oblique-cone-' in sid;branch_cone=sid.startswith('cone-');rect=sid.startswith('rectangle-')
    vertical='-vertical-' in sid;horizontal='-horizontal-' in sid or '-90-' in sid
    inclination=0. if vertical else 90. if horizontal else 90-p.get('B',45.) if branch_cone else 90-p['A'] if cone else p['A']
    a=math.radians(inclination);b=math.radians(p.get('B',0.) if oblique and not branch_cone else 0.)
    axis=(math.sin(a)*math.cos(b),math.sin(a)*math.sin(b),math.cos(a))
    if abs(axis[1])<.9:rx=(axis[2],0.,-axis[0])
    else:rx=(0.,-axis[2],axis[1])
    length=math.sqrt(sum(v*v for v in rx));rx=tuple(v/length for v in rx)
    ry=(axis[1]*rx[2]-axis[2]*rx[1],axis[2]*rx[0]-axis[0]*rx[2],axis[0]*rx[1]-axis[1]*rx[0])
    x0=p.get('Xb',p.get('X',0.)) if vertical else 0.;y0=p.get('Z',0.)
    if '-tangent-' in sid:y0=p['Dt']/2-p['W']/2
    z0=0. if vertical else p.get('Hb',0.)
    for x,y,z in r.quality_metrics['intersection_points_3d']:
        if cone:
            cx=p.get('X',0.)*z/p['H'] if oblique else 0.;radius=p['D']/2+(p['d']-p['D'])*z/(2*p['H'])
        else:cx=0.;radius=p['Dt']/2
        assert math.hypot(x-cx,y)==pytest.approx(radius,abs=1e-6)
        q=(x-x0,y-y0,z-z0);u=sum(v*w for v,w in zip(q,axis));xx=sum(v*w for v,w in zip(q,rx));yy=sum(v*w for v,w in zip(q,ry))
        if rect:
            hx=p.get('Hr',p.get('B'))/2;hy=p['W']/2;rr=p['r'];dx=abs(xx)-(hx-rr);dy=abs(yy)-(hy-rr)
            signed_distance=math.hypot(max(dx,0.),max(dy,0.))+min(max(dx,dy),0.)-rr
            assert signed_distance==pytest.approx(0.,abs=1e-6)
        else:
            if branch_cone:
                if 'db' in p:rr=p['Db']/2+(p['db']-p['Db'])*u/(2*p['Ht'])
                else:
                    end=p.get('Ls',p.get('Ht'));rr=p.get('Db',p.get('d'))/2+math.tan(math.radians(p['A']/2))*(end-u)
            else:rr=p['Db']/2
            assert math.hypot(xx,yy)==pytest.approx(rr,abs=1e-6)


@pytest.mark.parametrize('sid',['pipe-to-pipe-two-branches','pipe-to-pipe-two-branches-angled','pipe-to-pipe-two-branches-along','pipe-to-pipe-four-branches','breeches-3-pipes','breeches-4-pipes','breeches-5-pipes'])
def test_multi_pipe_trims_touch_a_real_neighbour_surface(sid):
    r=calculate(sid);radius=BY_ID[sid]['parameters'].get('Db',BY_ID[sid]['parameters'].get('D'))/2
    # Infer each axis from a genuine constant-length end generator, independently of dispatch.
    axes=[]
    for part in r.parts:
        # The profile is sampled adaptively, so its unweighted mean need not be the centre.
        a,b=part.true_lengths[0].start,part.true_lengths[0].end;v=tuple(y-x for x,y in zip(a,b));L=math.sqrt(sum(x*x for x in v));axes.append(tuple(x/L for x in v))
    for i,part in enumerate(r.parts):
        for point in part.mappings[::2]:
            q=point.assembled;res=[]
            if sid.startswith('pipe-to'):res.append(abs(math.hypot(q[0],q[1])-BY_ID[sid]['parameters']['Dt']/2))
            for j,a in enumerate(axes):
                if i==j:continue
                u=sum(v*w for v,w in zip(q,a));distance=math.sqrt(max(0.,sum(v*v for v in q)-u*u));res.append(abs(distance-radius))
            assert min(res)<1e-5


@pytest.mark.parametrize('sid',['pipe-to-bend-concentric','pipe-to-bend-offset','pipe-to-bend-angled'])
def test_torus_contact_has_independent_implicit_residual(sid):
    r=calculate(sid);p=BY_ID[sid]['parameters'];rr=p['Db']/2
    for point in r.parts[0].mappings[::2]:
        x,y,z=point.assembled
        assert (math.hypot(x,z)-p['R'])**2+y*y==pytest.approx(rr*rr,abs=1e-5)
        assert -1e-8<=math.atan2(z,x)<=math.pi/2+1e-8


def _point_segment_distance(q,a,b):
    d=tuple(y-x for x,y in zip(a,b));den=sum(v*v for v in d)
    t=max(0.,min(1.,sum((v-x)*dd for v,x,dd in zip(q,a,d))/den)) if den>1e-20 else 0.
    return math.sqrt(sum((v-x-t*dd)**2 for v,x,dd in zip(q,a,d)))


def _assert_shared_curve(a,b,tolerance=.05):
    assert len(a)>3 and len(b)>3
    for points,other in ((a,b),(b,a)):
        segments=list(zip(other,other[1:]+other[:1]))
        for q in points[::max(1,len(points)//32)]:
            assert min(_point_segment_distance(q,x,y) for x,y in segments)<tolerance


@pytest.mark.parametrize('sid',['reducing-breech-3-symmetric','reducing-breech-3-equal','reducing-breech-3-unequal'])
def test_three_piece_breech_has_matching_real_3d_seam_curves(sid):
    r=calculate(sid);p=BY_ID[sid]['parameters'];H=p['H'];angles=[-p['A']/2,p['A']/2] if 'A' in p else [-p['A1'],p['A2']]
    axes=[(0.,0.,-1.)]+[(math.sin(math.radians(a)),0.,math.cos(math.radians(a))) for a in angles]
    lengths=[H,p.get('L1',p.get('L')),p.get('L2',p.get('L'))];curves=[]
    for part,axis,L in zip(r.parts,axes,lengths):
        curves.append([v.assembled for v in part.mappings if abs(sum((v.assembled[k]-(H if k==2 else 0))*axis[k] for k in range(3))-L)>1e-6])
    for i,points in enumerate(curves):
        segments=[(a,b) for j,other in enumerate(curves) if j!=i for a,b in zip(other,other[1:]+other[:1])]
        assert len(points)>3
        for q in points[::max(1,len(points)//40)]:assert min(_point_segment_distance(q,a,b) for a,b in segments)<.05


@pytest.mark.parametrize('sid',[m['source_id'] for m in inventory()['models'] if m['category'] in ('Segmentli dirsekler','Dirsekler')])
def test_all_bend_joint_curves_match_in_world_coordinates(sid):
    r=calculate(sid);planes=r.quality_metrics['joint_planes']
    assert len(r.parts)==len(planes)+1
    for i,(normal,c) in enumerate(planes):
        def interface(part):return [p.assembled for p in part.mappings if abs(sum(a*b for a,b in zip(normal,p.assembled))-c)<1e-6]
        _assert_shared_curve(interface(r.parts[i]),interface(r.parts[i+1]))


def test_sharp_rectangular_transition_preserves_corner_correspondence():
    p={'W':700.,'L':1400.,'Wt':300.,'Lt':500.,'H':800.,'R':0.,'Rt':0.}
    r=calculate('rectangle-to-rectangle',parameters=p)
    expected=(700+300)*math.hypot(800,(1400-500)/2)+(1400+500)*math.hypot(800,(700-300)/2)
    assert r.metrics['net_area_mm2']==pytest.approx(expected,rel=1e-11)
    assert r.quality_metrics['facet_edge_error_mm']<1e-6


def test_sharp_square_round_uses_real_side_triangles_and_corner_fans():
    W,L,D,H=400.,300.,250.,300.;R=D/2;a=L/2;b=W/2;N=20000
    integral=sum(math.sqrt(H*H+(R-a*math.cos((i+.5)*math.pi/(2*N))-b*math.sin((i+.5)*math.pi/(2*N)))**2) for i in range(N))*math.pi/(2*N)
    expected=W*math.hypot(H,a-R)+L*math.hypot(H,b-R)+2*R*integral
    r=calculate('rectangle-to-round',parameters={'W':W,'L':L,'D':D,'H':H,'cornerRadius':0.})
    assert r.metrics['net_area_mm2']==pytest.approx(expected,rel=2e-4)
    assert r.quality_metrics['facet_edge_error_mm']<1e-6


def test_zero_azimuth_is_valid_and_zero_top_diameter_is_a_real_apex_limit():
    r=calculate('plate-cut-by-pipe-angle',parameters={'P':0.})
    assert r.parts[0].geometry_2d.holes
    r=calculate('cone-frustum',parameters={'d':0.})
    assert r.metrics['net_area_mm2']==pytest.approx(math.pi*150*math.hypot(150,200),rel=1e-12)
    a=calculate('pyramid-frustum',parameters={'d':0.});b=calculate('pyramid')
    assert a.metrics['net_area_mm2']==pytest.approx(b.metrics['net_area_mm2'],rel=1e-12)
