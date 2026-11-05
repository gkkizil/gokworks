from dataclasses import replace
import json
import math
from threading import Event
import zipfile
import pytest
import ezdxf

from core.unfolding import UnfoldService,ExportOptions,UnfoldProject,ProjectItem,UnfoldCancelled
from core.unfolding.models import Material,to_data,Geometry2D,Line2D,Circle2D
from core.unfolding.geometry import measure,polygon
from core.unfolding.nesting import to_nesting_parts
from core.unfolding.storage import request_from_dict
from .helpers import request_for,calculate


@pytest.mark.parametrize('shape,variant',[('cylinder','straight'),('cylinder','bevel'),('cone','frustum'),('cone','full'),
    ('rectangular_reducer','centered'),('rect_to_round','centered_faceted'),('segmented_elbow','constant_diameter')])
def test_real_dxf_roundtrip_units_closed_cutting_loops_and_layers(tmp_path,shape,variant):
    r=calculate(shape,variant);p=r.parts[0];target=tmp_path/(shape+'.dxf')
    report=UnfoldService().export(r,ExportOptions(str(target),part_ids=(p.id,)))
    assert report.status=='complete',report.errors
    d=ezdxf.readfile(target)
    assert d.units==4 and not d.audit().errors
    cuts=[e for e in d.modelspace() if e.dxf.layer=='CUT_OUTER']
    assert len(cuts)==1 and cuts[0].closed
    assert cuts[0].dxf.elevation==0
    assert {'CUT_OUTER','CUT_INNER','BEND_UP','BEND_DOWN','CONSTRUCTION','SEAM','DIMENSIONS','LABELS'}<=set(layer.dxf.name for layer in d.layers)
    if shape=='cone':assert any(abs(b)>0 for x,y,b in cuts[0].get_points('xyb'))
    # Independent ezdxf's own path conversion sees the same closed planar region.
    from ezdxf.path import make_path
    from shapely.geometry import Polygon
    path=make_path(cuts[0]);pts=[(p.x,p.y) for p in path.flattening(.005)]
    assert Polygon(pts).area==pytest.approx(p.metrics.cutting_area_mm2,abs=max(1.,p.metrics.cutting_length_mm*.01))
    assert p.quantity==1 and report.input_hash==r.input_hash


def test_dxf_preserves_large_sweeps_and_negative_coordinates(tmp_path):
    r=calculate('cone','full');p=r.parts[0];assert p.metrics.bounds_mm[0]<0
    target=tmp_path/'cone.dxf';UnfoldService().export(r,ExportOptions(str(target)))
    d=ezdxf.readfile(target);entity=next(e for e in d.modelspace() if e.dxf.layer=='CUT_OUTER')
    vertices=list(entity.get_points('xyb'))
    assert sum(4*math.atan(b) for x,y,b in vertices)==pytest.approx(math.radians(216.))
    assert len([b for x,y,b in vertices if b])==2


def test_stale_revision_hash_invalid_result_and_no_clobber(tmp_path):
    s=UnfoldService();r=calculate();target=tmp_path/'keep.dxf';target.write_text('untouched')
    for options in (ExportOptions(str(target)),ExportOptions(str(target),expected_revision=99,overwrite=True),
                    ExportOptions(str(target),expected_input_hash='wrong',overwrite=True)):
        assert s.export(r,options).status=='error' and target.read_text()=='untouched'
    assert s.export(replace(r,status='error'),ExportOptions(str(target),overwrite=True)).status=='error'
    assert target.read_text()=='untouched'
    stop=Event();stop.set()
    with pytest.raises(UnfoldCancelled):s.export(r,ExportOptions(str(target),overwrite=True),cancel_token=stop)
    assert target.read_text()=='untouched'


def test_project_roundtrip_units_options_quantity_and_engine_change(tmp_path):
    s=UnfoldService();request=request_for(input_units='inch',parameters={'diameter':10.,'height':5.})
    project=UnfoldProject((ProjectItem('PARÇA-1',request,3),),name='Türkçe proje',code='İŞ-001',revision='B',quantity=2)
    target=tmp_path/'project.gokunfold';s.save_project(project,target);again=s.load_project(target)
    assert again==project and not again.needs_recalculation
    assert s.calculate(again.items[0].request)==s.calculate(request)
    data=json.loads(target.read_text());data['project']['engine_version']='0.9.0';target.write_text(json.dumps(data))
    assert s.load_project(target).needs_recalculation
    assert again.quantity*again.items[0].quantity==6


@pytest.mark.parametrize('content',['{}','{"schema":1,"schema":2}', '{"a":NaN}', '{"schema":"gokworks.unfolding.project","version":true,"project":{}}'])
def test_malformed_project_files_are_refused(tmp_path,content):
    p=tmp_path/'bad.json';p.write_text(content)
    with pytest.raises(ValueError):UnfoldService().load_project(p)


def test_request_json_is_strict_and_unknown_options_are_rejected():
    source=to_data(request_for())
    source['seam_options']['unknown']=123
    with pytest.raises(ValueError):request_from_dict(source)


def test_zip_manifest_distinguishes_partial_step_and_keeps_all_valid_dxfs(tmp_path):
    r=calculate('segmented_elbow','constant_diameter');target=tmp_path/'parts.zip'
    export=UnfoldService().export(r,ExportOptions(str(target),'zip',include_pdf=False,include_step=True,quantity_multiplier=6))
    assert export.status=='partial' and len(export.errors)==4
    with zipfile.ZipFile(target) as z:
        assert len(z.namelist())==len(set(z.namelist()))==5
        assert all('/' not in name and '\\' not in name for name in z.namelist())
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['status']=='partial' and manifest['input_hash']==r.input_hash
        assert sum(x.get('quantity',0) for x in manifest['files'] if x['status']=='complete')==24
        assert len([x for x in manifest['files'] if x['status']=='error'])==4


def test_geometry_holes_cut_length_and_nesting_quantity_transfer_are_correct():
    outer=(Line2D((0.,0.),(100.,0.)),Line2D((100.,0.),(100.,100.)),Line2D((100.,100.),(0.,100.)),Line2D((0.,100.),(0.,0.)))
    g=Geometry2D(outer,((Circle2D((50.,50.),10.),),))
    m=measure(g,10000-math.pi*100,2.,Material('Test',7850.))
    assert m.cutting_area_mm2==pytest.approx(10000-math.pi*100)
    assert m.cutting_length_mm==pytest.approx(400+20*math.pi)
    r=calculate(thickness=2.,material=Material('S235',7850.));parts=to_nesting_parts(r,quantity_multiplier=6)
    assert parts[0].quantity==6 and parts[0].thickness==2. and parts[0].material=='S235'
    assert parts[0].polygon.area==pytest.approx(r.metrics['cutting_area_mm2'])
    assert parts[0].source_sha256==r.input_hash
    assert parts[0].original_dxf and 'CONSTRUCTION' not in parts[0].original_dxf


def test_nesting_keeps_analytic_arcs_through_rotation_and_translation(tmp_path):
    from modules.nesting.models import Project,Material as NestMaterial,Sheet,Placement,Result
    from modules.nesting.dxf_export import export_dxf
    r=calculate('cone','frustum',thickness=2.,material=Material('steel',7850.))
    parts=to_nesting_parts(r)
    project=Project(materials=[NestMaterial('steel','Çelik',7850.)],parts=list(parts),
                    sheets=[Sheet('sheet','Test',5000,5000,2.,'steel')])
    project.options.angles=[0,17,90,180,270]
    placement=Placement(parts[0].id,1,'sheet',1,1500.,1000.,17.)
    result=Result(project.fingerprint(),[placement],[],'controlled','1',0.,1,'2026-11-05T00:00:00Z')
    paths=export_dxf(project,result,tmp_path/'nested')
    doc=ezdxf.readfile(paths[0]);cuts=[e for e in doc.modelspace() if e.dxf.layer=='PART_OUTER']
    assert len(cuts)==4 and doc.units==4
    arcs=[c for c in cuts if c.dxftype()=='ARC']
    assert len(arcs)==2 and len([c for c in cuts if c.dxftype()=='LINE'])==2
    assert sorted(c.dxf.radius for c in arcs)==pytest.approx(sorted(c.radius for c in r.parts[0].geometry_2d.outer if c.kind=='arc'))
    assert [(c.dxf.end_angle-c.dxf.start_angle)%360 for c in arcs]==pytest.approx([126.40443897182102]*2)
    from modules.nesting.dxf_import import read_dxf
    imported=read_dxf(paths[0],excluded_layers=['SHEET_BOUNDARY','PART_LABELS','PART_REFERENCE'])
    assert len(imported)==1 and imported[0].polygon.is_valid
    assert imported[0].polygon.area==pytest.approx(parts[0].polygon.area,rel=1e-4)


@pytest.mark.parametrize('points',[((0,0),(10,10),(0,10),(10,0)),((0,0),(10,0),(10,0),(0,10))])
def test_self_crossing_and_duplicate_edges_do_not_become_production_contours(points):
    from core.unfolding.geometry import outline
    if points[1]==points[2]:
        # Duplicate zero-length edges are independently rejected by the quality gate.
        from core.unfolding.quality import inspect_parts
        r=calculate();g=outline(points)
        with pytest.raises(ValueError):inspect_parts((replace(r.parts[0],geometry_2d=g),),1e-6)
    else:
        with pytest.raises(ValueError):polygon(outline(points))
