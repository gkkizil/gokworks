from dataclasses import replace
import json
import subprocess
from threading import Event
import zipfile
import pytest
from core.unfolding import UnfoldService,UnfoldProject,ProjectItem,ExportOptions,UnfoldCancelled
from core.unfolding.exporting import safe_name
from .helpers import request_for,calculate


def test_project_zip_has_distinct_safe_names_exact_quantities_and_partial_item_failure(tmp_path):
    good=request_for();bad=request_for(parameters={'diameter':0.})
    project=UnfoldProject((ProjectItem('../CON',good,3),ProjectItem('../CON',replace(good,request_id='second'),4),
        ProjectItem('bad',bad,1)),quantity=2)
    path=tmp_path/'project.zip'
    result=UnfoldService().export_project(project,ExportOptions(str(path),'zip',include_pdf=False))
    assert result.status=='partial' and len(result.errors)==1
    with zipfile.ZipFile(path) as z:
        names=z.namelist();assert len(names)==3 and all('/' not in n and '\\' not in n for n in names)
        manifest=json.loads(z.read('manifest.json'));records=manifest['files']
        assert [r['quantity'] for r in records if r['status']=='complete']==[6,8]
        assert manifest['status']=='partial' and records[-1]['status']=='error'
        assert len({r['file'] for r in records if r['status']=='complete'})==2
    assert safe_name('CON').startswith('_') and safe_name('../../x')=='x'


def test_cancelled_project_never_replaces_existing_archive(tmp_path):
    target=tmp_path/'keep.zip';target.write_bytes(b'keep');stop=Event();stop.set()
    project=UnfoldProject((ProjectItem('test',request_for()),))
    with pytest.raises(UnfoldCancelled):UnfoldService().export_project(project,
        ExportOptions(str(target),'zip',overwrite=True,include_pdf=False),cancel_token=stop)
    assert target.read_bytes()==b'keep'


def test_cad_worker_is_terminated_on_cancel_and_timeout(monkeypatch,tmp_path):
    from core.unfolding import cad_process
    instances=[];stop=Event()
    class Process:
        def __init__(self,*a,**kw):self.killed=False;instances.append(self)
        def poll(self):return 1 if self.killed else None
        def wait(self,timeout):
            if self.killed:return 1
            raise subprocess.TimeoutExpired('controlled-worker',timeout)
        def kill(self):self.killed=True
    monkeypatch.setattr(cad_process.subprocess,'Popen',Process)
    r=calculate();target=tmp_path/'never.step'
    with pytest.raises(TimeoutError):cad_process.execute(r.parts,target,timeout=.005)
    assert instances[-1].killed and not target.exists()
    class CancelProcess(Process):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);stop.set()
    monkeypatch.setattr(cad_process.subprocess,'Popen',CancelProcess)
    with pytest.raises(UnfoldCancelled):cad_process.execute(r.parts,target,cancel_token=stop)
    assert instances[-1].killed and not target.exists()


def test_headless_worker_rejects_broken_protocol_without_loading_the_gui(tmp_path):
    from core.unfolding.cad_process import run_worker
    request=tmp_path/'request.json';request.write_text('{"parts":[]}')
    assert run_worker(request)==1
    response=json.loads((tmp_path/'result.json').read_text())
    assert not response['ok'] and not (tmp_path/'surface.step').exists()


def test_shallow_nonzero_cone_is_stable_and_true_lengths_match_helper_lines():
    r=calculate('cone','frustum',parameters={'bottom_diameter':300.,'top_diameter':299.999999,'height':200.})
    assert r.status=='success' and abs(r.metrics['net_area_mm2']-188495.55890122836)<.01
    for part in r.parts:
        for line in part.construction_lines:
            record=next(x for x in part.true_lengths if x.id.endswith('.'+line.id))
            import math
            assert math.dist(line.start,line.end)==pytest.approx(record.length_mm,abs=1e-5)


def test_zero_thickness_and_missing_density_are_not_reported_as_zero_mass():
    r=calculate();assert r.metrics['mass_kg'] is None
    assert any(w.code=='MASS_NOT_EVALUATED' and w.severity=='NOT_EVALUATED' for w in r.warnings)


def test_exporting_an_analytic_surface_does_not_export_the_preview_mesh(tmp_path):
    # The preview tessellation can be changed without changing the authoritative STEP surface.
    from core.unfolding.models import Mesh3D
    r=calculate();p=replace(r.parts[0],mesh_3d=Mesh3D((),()))
    target=tmp_path/'analytic.step'
    report=UnfoldService().export(replace(r,parts=(p,)),ExportOptions(str(target),'step'))
    assert report.status=='complete',report.errors
    assert target.stat().st_size>1000


def test_cad_worker_missing_readback_proof_is_not_success(monkeypatch,tmp_path):
    from core.unfolding import cad_process
    class UnverifiedProcess:
        returncode=0
        def __init__(self,command,**kwargs):
            from pathlib import Path
            folder=Path(command[-1]).parent
            (folder/'result.json').write_text('{"ok":true}')
            (folder/'surface.step').write_text('ISO-10303-21; unverified')
        def poll(self):return 0
    monkeypatch.setattr(cad_process.subprocess,'Popen',UnverifiedProcess)
    target=tmp_path/'existing.step';target.write_text('keep')
    report=UnfoldService().export(calculate(),ExportOptions(str(target),'step',overwrite=True))
    assert report.status=='error' and 'doğrulama' in report.errors[0].message
    assert target.read_text()=='keep'
