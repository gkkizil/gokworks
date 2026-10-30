"""Real DXF per-source options, retries, count approval and project compatibility."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from threading import Event

import ezdxf
import pytest
from shapely.geometry import box

from modules.nesting.batch_import import import_batch
from modules.nesting.import_plan import ImportDraft, normalize_options
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Sheet, uid
from modules.nesting.storage import load_project, save_project


class Sink:
    def __init__(self): self.events=[]
    def put(self, event): self.events.append(event)
    def flush(self): pass
    @property
    def finished(self): return [v for k,v in self.events if k=='nest_file' and v['status']!='running']


def drawing(tmp_path,name='GÖVDE_T2_8AD.dxf', *, separate=1, hole=False, unit=4):
    path=tmp_path/name; doc=ezdxf.new(); doc.units=unit
    for n in range(separate):
        x=n*40
        doc.modelspace().add_lwpolyline([(x,0),(x+30,0),(x+30,20),(x,20)],close=True)
    if hole: doc.modelspace().add_circle((15,10),3)
    doc.saveas(path); return path


def entry(path, **options):
    draft=ImportDraft.create(path); opts=draft.options(normalize_options({}))
    opts.update(options)
    return dict(id=uid(),source=str(path),status='pending',detail='',options=opts,part_code=draft.detected.code)


def run(entries, **kwargs):
    sink=Sink(); import_batch(entries,{},sink,Event(),**kwargs); return sink


def test_three_user_examples_use_independent_options_and_preserve_source_bytes(tmp_path):
    files=[drawing(tmp_path,n) for n in ('GOVDE 1,2 mm 12 adet.dxf','KAPAK T 2mm 5 adet.dxf','FLANS_T0,8_QTY20.dxf')]
    before=[p.read_bytes() for p in files]
    rows=run([entry(p) for p in files]).finished
    assert [r['status'] for r in rows]==['success']*3
    parts=[r['parts'][0] for r in rows]
    assert [(p.code,p.thickness,p.quantity) for p in parts]==[('GOVDE',1.2,12),('KAPAK',2.,5),('FLANS',.8,20)]
    assert [p.read_bytes() for p in files]==before


def test_legacy_common_options_and_per_source_override_are_both_supported(tmp_path):
    paths=[drawing(tmp_path,n) for n in ('A.dxf','B.dxf')]
    entries=[dict(id='a',source=str(paths[0])),dict(id='b',source=str(paths[1]),options=dict(quantity=7,thickness=.6))]
    sink=Sink(); import_batch(entries,dict(quantity=2,thickness=3),sink,Event())
    assert [(r['parts'][0].thickness,r['parts'][0].quantity) for r in sink.finished]==[(3.,2),(.6,7)]


def test_bad_file_retry_retains_all_explicit_per_file_settings(tmp_path):
    path=tmp_path/'KAPAK_T2_5AD.dxf'; path.write_text('broken DXF')
    e=entry(path,material='CUSTOM',thickness=1.5,quantity=9,unit='cm',tolerance=.01,
            join_tolerance=.002,excluded_layers=['AUX'],grouped=True)
    options=deepcopy(e['options'])
    assert run([e]).finished[0]['status']=='error'
    drawing(tmp_path,path.name,unit=0)
    part=run([e]).finished[0]['parts'][0]
    assert (part.material,part.thickness,part.quantity,part.area)==('CUSTOM',1.5,9,60000)
    assert part.join_tolerance==.002 and 'AUX' in part.notes[-1] and e['options']==options


def test_drafts_manual_bulk_fields_win_over_redetection_and_default_changes():
    a=ImportDraft.create('ŞASE_T2_12AD.dxf'); b=ImportDraft.create('KAPAK_T3_5AD.dxf')
    a.edit('quantity',7); defaults=normalize_options(dict(quantity=4,thickness=8))
    assert a.options(defaults)==dict(defaults,thickness=2.,quantity=7)
    assert a.options(defaults,False)==dict(defaults,quantity=7)
    assert b.options(defaults)['quantity']==5
    bad=ImportDraft.create('KAPAK_T2_3MM_10AD_QTY20.dxf')
    assert bad.issues()
    bad.edit('thickness','1,2'); assert bad.issues()
    bad.edit('quantity',8); assert not bad.issues() and bad.options(defaults)['thickness']==1.2


def test_multicontour_requires_explicit_approval_but_holes_do_not(tmp_path):
    path=drawing(tmp_path,separate=3,hole=True); e=entry(path)
    first=run([e]).finished[0]
    assert first['status']=='review' and not first['parts'] and first['contour_review']['count']==3
    assert '24 kesim parçası' in first['detail']
    e['contour_approval']=first['contour_review']
    approved=run([e]).finished[0]
    assert approved['status']=='success' and sum(p.quantity for p in approved['parts'])==24
    e['options']['quantity']=9
    assert run([e]).finished[0]['status']=='review'  # Approval bound to count, source and quantity.
    e['options']['quantity']=8
    drawing(tmp_path,path.name,separate=2,hole=True)
    assert run([e]).finished[0]['status']=='review'
    hole=drawing(tmp_path,'DELİKLİ_T2_8AD.dxf',hole=True)
    row=run([entry(hole)]).finished[0]
    assert row['status']=='success' and len(row['parts'])==1 and len(row['parts'][0].polygon.interiors)==1


def test_grouped_contours_remain_one_set_with_file_quantity(tmp_path):
    path=drawing(tmp_path,separate=3,hole=True)
    row=run([entry(path,grouped=True)]).finished[0]
    assert row['status']=='success' and len(row['parts'])==1 and row['parts'][0].quantity==8
    assert row['parts'][0].polygon.geom_type=='MultiPolygon'


def test_quantity_limits_account_for_existing_project_and_all_sources(tmp_path):
    paths=[drawing(tmp_path,n) for n in ('A.dxf','B.dxf','C.dxf')]
    rows=run([entry(paths[0],quantity=2),entry(paths[1],quantity=3),entry(paths[2],quantity=1)],existing_quantity=9997).finished
    assert [r['status'] for r in rows]==['success','error','success']
    assert '10000' in rows[1]['detail']
    row=run([entry(paths[0],quantity=10000)]).finished[0]
    assert row['status']=='success' and row['parts'][0].quantity==10000
    assert run([entry(paths[0],quantity=10001)]).finished[0]['status']=='error'


def test_review_approval_and_options_roundtrip_without_changing_project_format(tmp_path):
    path=drawing(tmp_path,separate=2); e=entry(path)
    review=run([e]).finished[0]
    e.update(status='review',detail=review['detail'],contour_review=review['contour_review'])
    project=new_project(); target=tmp_path/'review.goknest.json'
    save_project(project,target,imports=[e]); data=json.loads(target.read_text())
    assert data['version']==1
    loaded,result,imports=load_project(target,with_imports=True)
    assert not loaded.parts and result is None and imports==[e]
    imports[0]['contour_approval']=imports[0]['contour_review']
    parts=run(imports).finished[0]['parts']; project.parts=parts
    e.update(status='success',part_ids=[p.id for p in parts])
    save_project(project,target,imports=[e],overwrite=True)
    loaded,_,imports=load_project(target,with_imports=True)
    assert json.dumps([asdict(p) for p in loaded.parts],sort_keys=True)==json.dumps([asdict(p) for p in parts],sort_keys=True)
    assert imports[0]['options']['quantity']==8
    # Version 1 without the optional import history still opens.
    data=json.loads(target.read_text()); data.pop('import_sources'); target.write_text(json.dumps(data))
    assert len(load_project(target)[0].parts)==2


def test_real_repository_dxf_options_reach_nesting_mass_cost_and_all_reports(tmp_path,qapp):
    from modules.nesting.engine import nest
    from modules.nesting.accounting import calculate, mass
    from modules.nesting.validation import validate_result
    from modules.nesting.report import export_excel, export_pdf
    from modules.nesting.pdf_report import report_html
    from modules.nesting.dxf_export import export_dxf
    from openpyxl import load_workbook
    root=Path(__file__).resolve().parents[3]
    original=root/'docs/nesting-example/input/GW-002.dxf'
    paths=[]
    for name in ('GÖVDE_T1,2_2AD.dxf','KAPAK_T2_3AD.dxf'):
        dest=tmp_path/name; dest.write_bytes(original.read_bytes()); paths.append(dest)
    rows=run([entry(p) for p in paths]).finished
    project=new_project(); project.parts=[r['parts'][0] for r in rows]
    project.sheets=[Sheet(uid(),f'{t} mm',thickness=t,price_kg=35) for t in (1.2,2.)]
    project.options.quality='Hızlı'; project.operations.cut_price_m=30
    result=nest(project); assert validate_result(project,result)
    totals=calculate(project,result)
    assert totals['part_count']==5
    assert sorted((r['thickness'],r['quantity']) for r in totals['part_summary'])==[(1.2,2),(2.,3)]
    expected=sum(mass(p.area,p.thickness,project.material(p.material).density)*p.quantity for p in project.parts)
    assert totals['net_weight']==pytest.approx(expected)
    assert totals['cut_cost']==pytest.approx(round(sum(p.polygon.length*p.quantity for p in project.parts)/1000*30,2))
    assert all(project.part(p.part_id).thickness==project.sheet(p.sheet_id).thickness for p in result.placements)
    target=tmp_path/'report.xlsx'; export_excel(project,result,target)
    book=load_workbook(target); assert 'GÖVDE' in str(list(book.worksheets[1].values))
    book.close()
    assert 'GÖVDE' in report_html(project,result,totals)
    pdf=tmp_path/'report.pdf'; export_pdf(project,result,pdf)
    assert pdf.read_bytes().startswith(b'%PDF-')
    folder=tmp_path/'output'; export_dxf(project,result,folder)
    assert list(folder.rglob('*.dxf')) and original.read_bytes()==paths[0].read_bytes()


def test_hundred_real_sources_keep_independent_values(tmp_path):
    entries=[entry(drawing(tmp_path,f'P{i}_T{1+i%3}_{1+i%7}AD.dxf')) for i in range(100)]
    sink=run(entries)
    assert len(sink.finished)==100 and all(r['status']=='success' for r in sink.finished)
    assert [(r['parts'][0].thickness,r['parts'][0].quantity) for r in sink.finished]==[(1.+i%3,1+i%7) for i in range(100)]
