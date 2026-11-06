"""Real contours, old project compatibility, exact export selection and mesh metrics."""
from dataclasses import replace
import json
import math
import threading

import pytest

from core.unfolding import UnfoldRequest,UnfoldService,ExportOptions
from core.unfolding.models import Material,ProjectItem,UnfoldProject,to_data
from core.unfolding.forming.deformation import analyze_mesh,relax_mesh
from core.unfolding.forming.storage import save_profile,load_profile
from core.unfolding.shapes.common import UnfoldCancelled
from .test_source_models import request as source_request


def profile(**kwargs):
    p=dict(width=100.,flange_1=20.,flange_2=50.,flange_3=20.,bend_1_deg=90.,bend_2_deg=-90.,
           radius_1=2.,radius_2=2.,length_reference=1)
    return UnfoldRequest(shape_id='bent_profile',variant_id='double',parameters=p,thickness=2.,
                         material=Material('Synthetic test material',7850.,1.,'kg','TL'),
                         forming_options=dict(k_factor=.4),**kwargs)


@pytest.mark.parametrize('cut',['1_part_on_flat','1_part_on_radius','2_parts_90_degrees','2_parts_180_degrees'])
def test_oval_true_straight_and_arc_lengths_not_global_scaling(cut):
    s=UnfoldService();r=s.calculate(source_request('oval-cylinder',parameters={'L':300.,'W':200.,'H':400.},
                                                 thickness=2.,model_options={'cut_type':cut},
                                                 forming_options={'process':'roll_bending','k_factor':.4}))
    assert r.status=='success',r.errors
    assert r.forming_report['all_compensated']
    widths=[part.metrics.bounds_mm[2]-part.metrics.bounds_mm[0] for part in r.parts]
    assert sum(widths)==pytest.approx(200+math.pi*199.6,abs=1e-9)
    for p in r.parts:
        assert p.nominal_part and p.metrics.bounds_mm[3]==400.
        # Mappings on the genuinely flat section retain their arc-length distance.
        pairs=list(zip(p.nominal_part.mappings,p.mappings))
        segments=[(a,b) for a,b in zip(pairs,pairs[1:]) if a[0].assembled[2]==b[0].assembled[2] and
                  abs(a[0].assembled[1]-100.)<1e-7 and abs(b[0].assembled[1]-100.)<1e-7]
        for (old_a,new_a),(old_b,new_b) in segments:
            assert math.dist(new_a.developed,new_b.developed)==pytest.approx(math.dist(old_a.developed,old_b.developed),abs=1e-8)


@pytest.mark.parametrize('source_id',['segmented-bend-angle','segmented-bend-oval-angle','segmented-bend-oval-opposite-angle'])
def test_segmented_elbows_keep_piece_count_and_final_3d_geometry(source_id):
    s=UnfoldService();q=source_request(source_id,thickness=2.)
    nominal=s.calculate(q)
    r=s.calculate(replace(q,forming_options={'process':'roll_bending','k_factor':.4}))
    assert nominal.status==r.status=='success',(nominal.errors,r.errors)
    assert len(r.parts)==len(nominal.parts)==q.parameters['segments']
    assert r.forming_report['all_compensated']
    for p,b in zip(r.parts,nominal.parts):
        assert p.mesh_3d==b.mesh_3d
        assert p.nominal_part.geometry_2d==b.geometry_2d
        assert p.metrics.cutting_area_mm2<b.metrics.cutting_area_mm2


def test_cylinder_reference_units_and_unchanged_nominal_without_forming():
    s=UnfoldService();q=UnfoldRequest(parameters={'diameter':200.,'height':300.},thickness=2.,dimension_reference='inner')
    nominal=s.calculate(q)
    assert nominal.parts[0].metrics.bounds_mm[2]==pytest.approx(math.pi*202)
    o={'process':'roll_bending','k_factor':.4}
    r=s.calculate(replace(q,forming_options=o))
    assert r.parts[0].metrics.bounds_mm[2]==pytest.approx(math.pi*201.6)
    inch=replace(q,input_units='inch',parameters={'diameter':200/25.4,'height':300/25.4},thickness=2/25.4,forming_options=o)
    assert s.calculate(inch).parts[0].metrics.bounds_mm==pytest.approx(r.parts[0].metrics.bounds_mm)
    assert s.calculate(replace(q,dimension_reference='outer')).parts[0].metrics.bounds_mm[2]==pytest.approx(math.pi*198)


def test_multibend_profile_length_bend_locations_and_mass_are_from_actual_blank():
    r=UnfoldService().calculate(profile())
    assert r.status=='success',r.errors
    p=r.parts[0]
    assert p.metrics.bounds_mm[2]==pytest.approx(82.79645943005141)
    assert [b.start[0] for b in p.bending_lines]==pytest.approx([18.199114857512853,64.59734457253856])
    assert p.metrics.mass_kg==pytest.approx(82.79645943005141*100*2*7850/1e9)
    assert 'GEOMETRIC_MIDSURFACE' not in [w.code for w in r.warnings]
    assert r.capabilities['production_process_verified'] is False


@pytest.mark.parametrize('source_id',['oval-to-round-offset','ellipse-to-round-angled-top','cone-frustum'])
def test_unverified_fitting_compensation_is_not_faked(source_id,tmp_path):
    s=UnfoldService();q=source_request(source_id,thickness=2.,forming_options={'process':'roll_bending','k_factor':.4})
    r=s.calculate(q)
    assert r.status=='success',r.errors
    assert not r.forming_report['all_compensated']
    assert all(p.nominal_part is None for p in r.parts)
    e=s.export(r,ExportOptions(str(tmp_path/'false.dxf'),'dxf',part_ids=(r.parts[0].id,),development='compensated'))
    assert e.status=='error' and not (tmp_path/'false.dxf').exists()


def test_bounded_mesh_relaxation_reduces_distortion_without_claiming_plasticity():
    verts=((-1.,-1.,0.),(1.,-1.,0.),(1.,1.,0.),(-1.,1.,0.),(0.,0.,1.))
    tri=((0,1,4),(1,2,4),(2,3,4),(3,0,4));flat=tuple(v[:2] for v in verts)
    before=analyze_mesh(verts,tri,flat)
    optimized,report=relax_mesh(verts,tri,flat,iterations=300)
    after=analyze_mesh(verts,tri,optimized)
    assert report['final_energy']<report['initial_energy']
    assert after['rms_edge_strain']<before['rms_edge_strain']
    assert after['rms_edge_strain']>1e-4  # a curved fan cannot become an isometric plane
    assert all(a>=b for a,b in zip(report['energy_history'],report['energy_history'][1:]))
    assert optimized[:2]==flat[:2]
    assert after['plastic_strain'] is None and after['thickness_change_mm'] is None


def test_mesh_analysis_detects_area_and_edge_change_independently():
    result=analyze_mesh(((0.,0.,0.),(3.,0.,0.),(0.,4.,0.)),((0,1,2),),((0.,0.),(6.,0.),(0.,8.)))
    assert result['max_abs_edge_strain']==pytest.approx(1.)
    assert result['total_area_change_ratio']==pytest.approx(3.)


def test_formed_head_relaxation_keeps_restrictions_and_reports_actual_energy():
    q=source_request('vessel-end-cap-elliptical',thickness=2.,forming_options={'relax_mesh':True})
    r=UnfoldService().calculate(q)
    assert r.status=='success',r.errors
    record=next(iter(r.forming_report['parts'].values()))
    assert record['status']=='MESH_OPTIMIZED',record
    assert record['relaxation']['final_energy']<=record['relaxation']['initial_energy']
    assert not r.forming_report['all_compensated']
    assert r.quality_metrics['smooth_isometry'] is False


def test_project_and_profile_roundtrips_preserve_sources_and_old_projects_load(tmp_path):
    s=UnfoldService();q=profile();p=UnfoldProject((ProjectItem('P1',q,3),),quantity=2)
    path=tmp_path/'project.json';s.save_project(p,path)
    assert s.load_project(path)==p
    data=json.loads(path.read_text());data['project']['items'][0]['request'].pop('forming_options')
    data['project']['engine_version']='1.1.1';path.write_text(json.dumps(data))
    old=s.load_project(path)
    assert old.needs_recalculation and not old.items[0].request.forming_options
    config=tmp_path/'forming.json';save_profile(q.forming_options,config)
    assert load_profile(config)['k_factor']==.4


def test_nominal_compensated_comparison_dxf_units_contours_and_bend_direction(tmp_path):
    import ezdxf
    s=UnfoldService();r=s.calculate(profile())
    for mode,expected in [('nominal',83.42477796076938),('compensated',82.79645943005141),('comparison',82.79645943005141)]:
        path=tmp_path/(mode+'.dxf');e=s.export(r,ExportOptions(str(path),'dxf',development=mode))
        assert e.status=='complete',e.errors
        doc=ezdxf.readfile(path);assert doc.units==4 and not doc.audit().errors
        outer=[v for v in doc.modelspace().query('LWPOLYLINE') if v.dxf.layer in ('CUT_OUTER','COMPENSATED_OUTER')]
        assert len(outer)==1 and outer[0].closed
        xs=[p[0] for p in outer[0].get_points()]
        assert max(xs)-min(xs)==pytest.approx(expected)
        assert len(doc.modelspace().query('LINE[layer=="BEND_UP"]'))==1
        assert len(doc.modelspace().query('LINE[layer=="BEND_DOWN"]'))==1
        if mode=='comparison':assert len(doc.modelspace().query('LWPOLYLINE[layer=="NOMINAL_OUTER"]'))==1
    refused=s.export(r,ExportOptions(str(tmp_path/'bad.step'),'step',development='compensated'))
    assert refused.status=='error' and not (tmp_path/'bad.step').exists()


def test_pdf_roundtrip_contains_turkish_compensation_and_sources(tmp_path):
    from gui_qt.app import create_application
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtCore import QSize
    create_application([])
    s=UnfoldService();r=s.calculate(profile())
    path=tmp_path/'report.pdf';outcome=s.export(r,ExportOptions(str(path),'pdf',development='comparison'))
    assert outcome.status=='complete',outcome.errors
    doc=QPdfDocument();assert doc.load(str(path))==QPdfDocument.Error.None_
    try:
        text='\n'.join(doc.getAllText(i).text() for i in range(doc.pageCount()))
        assert 'Şekillendirme hesabı' in text and '82.796459430' in text and 'Nominal açınım' in text
        assert 'Kullanıcının açık K-Faktör girdisi' in text
        assert 'NOT_EVALUATED' in text
        assert not doc.render(doc.pageCount()-1,QSize(800,1100)).isNull()
    finally:doc.close()


def test_catalogue_comparison_is_for_explicit_dimensions_not_source_name():
    q=profile();data=to_data(q.forming_options)
    data['reference']=dict(source='Synthetic reference drawing',part_id='bent-profile',
                           measurements_mm={'width':82.79645943005141},absolute_tolerance_mm=1e-6,relative_tolerance_percent=1e-6)
    r=UnfoldService().calculate(replace(q,forming_options=data))
    comparison=r.forming_report['parts']['bent-profile']['catalogue_comparison']
    assert comparison['all_supplied_measurements_match']
    assert comparison['geometry_equivalence_verified'] is False


def test_cancelled_geometry_and_relaxation_do_not_publish_results():
    token=threading.Event();token.set()
    with pytest.raises(UnfoldCancelled):UnfoldService().calculate(profile(),token)
    with pytest.raises(UnfoldCancelled):relax_mesh(((0.,0.,0.),(2.,0.,0.),(0.,2.,0.)),((0,1,2),),((0.,0.),(1.,0.),(0.,1.)),cancel_token=token)


def test_cached_nominal_snapshot_keeps_the_current_request_identity(tmp_path):
    s=UnfoldService();q=profile();first=s.calculate(q)
    current=s.calculate(replace(q,request_id='new-current-request',revision=7))
    assert first.input_hash==current.input_hash
    assert current.parts[0].nominal_part.assembly_id=='new-current-request'
    path=tmp_path/'nominal.json'
    e=s.export(current,ExportOptions(str(path),'json',development='nominal'))
    assert e.status=='complete',e.errors
    data=json.loads(path.read_text())
    assert data['request_id']==data['parts'][0]['assembly_id']=='new-current-request'


def test_cylindrical_mesh_metric_error_converges_with_independent_chord_reference():
    errors=[];radius=100.;height=50.
    for count in (8,16,32):
        vertices=tuple((radius*math.cos(math.tau*i/count),radius*math.sin(math.tau*i/count),z)
                       for i in range(count+1) for z in (0.,height))
        flat=tuple((math.tau*radius*i/count,z) for i in range(count+1) for z in (0.,height))
        triangles=tuple(tri for i in range(1,count+1) for tri in ((2*i-2,2*i,2*i-1),(2*i,2*i+1,2*i-1)))
        metrics=analyze_mesh(vertices,triangles,flat)
        reference=(math.pi/count)/math.sin(math.pi/count)-1
        assert metrics['max_abs_edge_strain']==pytest.approx(reference,abs=1e-13)
        assert metrics['total_area_change_ratio']==pytest.approx(reference,abs=1e-13)
        errors.append(metrics['max_abs_edge_strain'])
    assert errors[0]>errors[1]>errors[2]>0.
    assert 3.9<errors[1]/errors[2]<4.1


def test_missing_reference_point_is_reported_and_cannot_pass_all_measurements():
    reference=dict(source='Synthetic dimensioned reference',part_id='cylinder-01',
                   measurements_mm={'width':math.pi*200},points_mm={'cylinder-01.0.1':(0.,300.05),'MISSING':(1.,2.)},
                   absolute_tolerance_mm=.1,relative_tolerance_percent=.1)
    q=UnfoldRequest(parameters={'diameter':200.,'height':300.},thickness=2.,forming_options={'reference':reference})
    r=UnfoldService().calculate(q)
    comparison=r.forming_report['parts']['cylinder-01']['catalogue_comparison']
    points={p['point']:p for p in comparison['point_measurements']}
    assert points['cylinder-01.0.1']['absolute_error_mm']==pytest.approx(.05)
    assert points['MISSING']['status']=='NOT_EVALUATED'
    assert not comparison['all_supplied_measurements_match']
