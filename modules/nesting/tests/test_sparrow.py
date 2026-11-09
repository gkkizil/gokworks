"""Actual native Sparrow, finite stock, independent geometry and worker lifecycle."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys
from threading import Event, Timer
import time

import pytest
from shapely.geometry import box, Point, MultiPolygon, Polygon

from modules.nesting import sparrow
from modules.nesting.accounting import calculate
from modules.nesting.dxf_export import export_dxf
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Sheet, uid
from modules.nesting.sparrow import nest
from modules.nesting.storage import save_project, load_project
from modules.nesting.validation import validate_result


def project(shape=None, quantity=4, width=150, height=100):
    p=new_project(); p.parts=[Part.create('A',box(0,0,30,20) if shape is None else shape,quantity=quantity)]
    p.sheets=[Sheet(uid(),'Test sac',width,height,stock=20)]
    p.options.engine='Sparrow'; p.options.quality='Hızlı'; p.options.seconds=12
    return p


@pytest.mark.parametrize('geometry',[
    box(0,0,30,20),box(-1000,200, -970,220),
    Polygon(list(box(0,0,30,20).exterior.coords)[::-1]),
    box(0,0,30,20).difference(Point(15,10).buffer(4)),
    Polygon([(0,0),(30,0),(30,8),(10,8),(10,20),(0,20)])])
def test_native_contours_quantities_clearance_and_source_survive(geometry):
    p=project(geometry); before=deepcopy(asdict(p)); reports=[]
    r=nest(p,progress=lambda *args:reports.append(args))
    assert validate_result(p,r) and len(r.placements)==4
    assert r.engine=='Sparrow' and 'spyrrow 0.9.0' in r.engine_version
    assert asdict(p)==before and reports
    assert calculate(p,r)['part_count']==4


def test_multiple_finite_plates_and_exhausted_stock_are_explicit():
    p=project(quantity=5,width=65,height=55); p.sheets[0].stock=2
    p.options.rotation=False
    r=nest(p)
    assert validate_result(p,r,complete=False)
    assert len(r.placements)==2 and len(r.unplaced)==3
    assert {x.sheet_number for x in r.placements}=={1,2}
    with pytest.raises(ValueError,match='yerleşmedi'): validate_result(p,r)


@pytest.mark.parametrize('quantity',[1,3])
def test_sparse_small_parts_on_a_large_stock_do_not_collapse_the_native_strip(quantity):
    p=project(Polygon([(0,0),(0,30),(50,30),(50,0)]),quantity=quantity,width=1250,height=2500)
    result=nest(p)
    assert len(result.placements)==quantity and validate_result(p,result)


def test_material_thickness_and_allowed_angles_are_retained():
    p=project(box(0,0,80,10),quantity=2,width=45,height=110)
    p.options.angles=[90,270]
    other=deepcopy(p.sheets[0]); other.id=uid(); other.material='AISI 304'; p.sheets.insert(0,other)
    r=nest(p)
    assert validate_result(p,r)
    assert all(x.sheet_id==p.sheets[1].id and x.angle in (90,270) for x in r.placements)
    p.parts[0].grain_locked=True
    r=nest(p)
    assert not r.placements and len(r.unplaced)==2 and validate_result(p,r,complete=False)


def test_oversized_or_disconnected_parts_do_not_get_resized_or_hulled():
    p=project(box(0,0,200,300))
    r=nest(p); assert not r.placements and len(r.unplaced)==4
    p.parts[0].geometry=Part.create('group',MultiPolygon([box(0,0,10,10),box(20,0,30,10)])).geometry
    with pytest.raises(ValueError,match='tek bağlı'): nest(p)


def test_old_nfp_hashes_and_sparrow_project_results_round_trip(tmp_path):
    p=project(); p.options.engine='GOKWORKS NFP'
    legacy=asdict(p); legacy['options'].pop('engine')
    expected=hashlib.sha256(json.dumps(legacy,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
    assert p.fingerprint()==expected
    path=tmp_path/'old.goknest.json'
    save_project(p,path)
    data=json.loads(path.read_text()); data['project']['options'].pop('engine')
    path.write_text(json.dumps(data)); old,_=load_project(path)
    assert old.fingerprint()==expected and old.options.engine=='GOKWORKS NFP'
    old.options.engine='Sparrow'; assert old.fingerprint()!=expected
    r=nest(old); path=tmp_path/'new.goknest.json'; save_project(old,path,r)
    loaded,saved=load_project(path)
    assert saved==r and loaded.options.engine=='Sparrow' and validate_result(loaded,saved)
    files=export_dxf(loaded,saved,tmp_path/'dxf-output')
    assert files and all(f.stat().st_size>1000 for f in files)


def test_pre_cancel_returns_a_valid_unplaced_result():
    p=project(); stop=Event(); stop.set(); r=nest(p,stop=stop)
    assert r.stopped and not r.placements and len(r.unplaced)==4
    assert validate_result(p,r,complete=False)


@pytest.mark.parametrize('cancel',[False,True])
def test_worker_is_killed_and_reaped_on_deadline_or_cancel(monkeypatch,cancel):
    original=subprocess.Popen; children=[]
    def blocking(*args,**kwargs):
        child=original([sys.executable,'-c','import time; time.sleep(30)'],**kwargs)
        children.append(child); return child
    monkeypatch.setattr(sparrow.subprocess,'Popen',blocking)
    stop=Event(); timer=Timer(.15,stop.set) if cancel else None
    if timer: timer.start()
    started=time.monotonic()
    try: assert sparrow._run({},started+(3 if cancel else .15),stop) is None
    finally:
        if timer: timer.cancel(); timer.join()
    assert time.monotonic()-started<2 and len(children)==1 and children[0].poll() is not None


@pytest.mark.parametrize('bad',[
    [dict(id='unknown',x=1,y=1,angle=0)],
    [dict(id='a',x=float('nan'),y=1,angle=0)],
    [dict(id='a',x=1,y=1,angle=45)],
    [dict(id='a',x=1,y=1,angle=0)]*2])
def test_native_identity_angles_and_nonfinite_poses_are_rejected(bad):
    p=project(quantity=1); part=p.parts[0]; part.id='a'
    specs={'a':dict(part=part,demand=1,angles=[0],origin=(0,0))}
    with pytest.raises(ValueError): sparrow._poses(bad,specs,1,0,0,p.sheets[0],1,Counter())


def test_native_failure_does_not_silently_switch_engine(monkeypatch):
    p=project()
    def fail(*args): raise ValueError('native failure')
    monkeypatch.setattr(sparrow,'_run',fail)
    with pytest.raises(ValueError,match='native failure'): nest(p)
