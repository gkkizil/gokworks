"""Reproduce all source output evidence; a changed implementation invalidates the run."""
import argparse
from dataclasses import replace
import hashlib
from importlib.metadata import version,PackageNotFoundError
import json
import math
from pathlib import Path
import platform
import time
from core.unfolding import UnfoldService,UnfoldRequest,UnfoldProject,ProjectItem
from core.unfolding.models import ExportOptions,Material,to_data,ENGINE_VERSION
from core.unfolding.source_models import inventory
from core.unfolding.nesting import to_nesting_parts
from .test_source_models import dxf_measure


def implementation_digest(root):
    digest=hashlib.sha256()
    for path in sorted((root/'core/unfolding').rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode());digest.update(b'\0');digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--skip-step',action='store_true');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[2];example_path=root/'docs/unfolding/examples/source_models.json'
    examples=json.loads(example_path.read_text(encoding='utf-8'))['models'];initial_digest=implementation_digest(root)
    packages={}
    for name in ('PySide6','ezdxf','shapely','cadquery-ocp-novtk'):
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    spec=[{k:m[k] for k in ('source_id','source_url','source_fields','cut_options','source_features')} for m in inventory()['models']]
    report=dict(schema='gokworks.unfolding.source_validation',version=1,engine_version=ENGINE_VERSION,source_count=191,
        implementation_sha256=initial_digest,source_spec_sha256=hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        examples_sha256=hashlib.sha256(example_path.read_bytes()).hexdigest(),platform=platform.system(),python=platform.python_version(),packages=packages,
        requested_outputs=['dxf','pdf','json_project','nesting_adapter']+([] if args.skip_step else ['step_surface_when_available']),
        live_windows=False,live_solidworks=False,live_oda=False,complete=False,models=[])
    target=args.output/'source_validation.json'
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtCore import QSize
    from PySide6.QtPdf import QPdfDocument
    app=QGuiApplication.instance() or QGuiApplication([]);service=UnfoldService(0)
    for index,e in enumerate(examples,1):
        sid=e['source_id'];folder=args.output/sid;folder.mkdir(exist_ok=True);started=time.monotonic();errors=[];files=[]
        req=replace(UnfoldRequest(**e['request']),thickness=2.,material=Material('Demir / Çelik',7850.,30.,currency='TL'))
        r=service.calculate(req)
        row=dict(source_id=sid,request=to_data(req),calculation_status=r.status,input_hash=r.input_hash,calculation_method=r.calculation_method,
                 validated_outputs=[],files=files,errors=errors,quality=to_data(r.quality_metrics),capabilities=to_data(r.capabilities),
                 metrics=to_data(r.metrics),part_quantities={p.id:p.quantity for p in r.parts})
        if r.status=='success':
            try:
                for part in r.parts:
                    path=folder/(part.id+'.dxf');output=service.export(r,ExportOptions(str(path),part_ids=(part.id,),overwrite=True))
                    if output.status!='complete':raise ValueError(str(output.errors))
                    area,length=dxf_measure(path)
                    if abs(area-part.metrics.cutting_area_mm2)>max(1e-5,part.metrics.cutting_area_mm2*1e-8):raise ValueError('DXF alan geri okuması uyuşmuyor.')
                    if abs(length-part.metrics.cutting_length_mm)>max(1e-5,length*1e-9):raise ValueError('DXF kesim boyu geri okuması uyuşmuyor.')
                    files.append(dict(format='dxf',part_id=part.id,path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),area_mm2=area,cut_length_mm=length))
                row['validated_outputs'].append('dxf')
            except (ValueError,RuntimeError,OSError) as exc:errors.append(dict(format='dxf',error=str(exc)))
            try:
                path=folder/(sid+'.pdf');output=service.export(r,ExportOptions(str(path),'pdf',overwrite=True))
                if output.status!='complete':raise ValueError(str(output.errors))
                document=QPdfDocument()
                try:
                    if document.load(str(path))!=QPdfDocument.Error.None_:raise ValueError('PDF yüklenemedi.')
                    pages=document.pageCount();text=''.join(document.getAllText(i).text() for i in range(pages));render=document.render(0,QSize(794,1123))
                    if render.isNull() or not all(p.code in text for p in r.parts) or 'Açınım' not in text:raise ValueError('PDF metin/render doğrulaması başarısız.')
                    render.save(str(folder/'pdf-first-page.png'))
                finally:document.close()
                files.append(dict(format='pdf',path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=pages,rendered_first_page=True));row['validated_outputs'].append('pdf')
            except (ValueError,RuntimeError,OSError) as exc:errors.append(dict(format='pdf',error=str(exc)))
            try:
                path=folder/(sid+'.gokunfold.json')
                project=UnfoldProject((ProjectItem(sid,req,3),),name='Türkçe / '+sid,quantity=2)
                service.save_project(project,path,overwrite=True)
                if service.load_project(path)!=project:raise ValueError('JSON proje girdileri/adetleri değişti.')
                row['json_project_roundtrip_verified']=True
                row['validated_outputs'].append('json_project')
                files.append(dict(format='json_project',path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            except (ValueError,RuntimeError,OSError) as exc:errors.append(dict(format='json_project',error=str(exc)))
            try:
                nested=to_nesting_parts(r,quantity_multiplier=3)
                if len(nested)!=len(r.parts) or any(a.quantity!=b.quantity*3 or not a.original_dxf for a,b in zip(nested,r.parts)):raise ValueError('Nesting veri/adet sözleşmesi uyuşmuyor.')
                row['nesting_adapter_verified']=True
            except (ValueError,RuntimeError,OSError) as exc:errors.append(dict(format='nesting',error=str(exc)))
            if r.capabilities.get('step_surface') and not args.skip_step:
                try:
                    path=folder/(sid+'.step');output=service.export(r,ExportOptions(str(path),'step',overwrite=True))
                    if output.status!='complete':raise ValueError(str(output.errors))
                    from core.unfolding.cad import read_step
                    _,stats=read_step(path)
                    nominal_area=sum(part.metrics.net_area_mm2 for part in r.parts)
                    if not math.isclose(stats['area_mm2'],nominal_area,rel_tol=1e-7,abs_tol=1e-5):
                        raise ValueError('STEP alanı bağımsız 2D nominal parça alanıyla uyuşmuyor.')
                    vertices=[v for part in r.parts for v in part.mesh_3d.vertices]
                    expected_bounds=tuple(min(v[i] for v in vertices) for i in range(3))+tuple(max(v[i] for v in vertices) for i in range(3))
                    bound_tolerance=max(req.development_options.mesh_error_mm,req.development_options.chord_error_mm)+1e-4
                    if max(abs(a-b) for a,b in zip(stats['bounds_mm'],expected_bounds))>bound_tolerance:
                        raise ValueError('STEP montaj sınırları bağımsız 3D model yerleşimiyle uyuşmuyor.')
                    if 'NOT VALIDATED' not in path.read_text(encoding='utf-8'):raise ValueError('STEP üretim sınırı açıklaması eksik.')
                    files.append(dict(format='step_surface',path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),stats=stats,
                        expected_nominal_area_mm2=nominal_area,expected_mesh_bounds_mm=expected_bounds,bounds_tolerance_mm=bound_tolerance));row['validated_outputs'].append('step_surface')
                except (ValueError,RuntimeError,OSError) as exc:errors.append(dict(format='step_surface',error=str(exc)))
        else:errors.extend(to_data(r.errors))
        row['elapsed_seconds']=time.monotonic()-started;report['models'].append(row)
        (folder/'evidence.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');save();app.processEvents()
        print(f'{index}/191 {sid}: {r.status}; '+','.join(row['validated_outputs'])+f'; errors={len(errors)}',flush=True)
    report['implementation_unchanged']=implementation_digest(root)==initial_digest
    report['complete']=len(report['models'])==191 and report['implementation_unchanged'] and not any(row['errors'] for row in report['models'])
    save();return 0 if report['complete'] else 1


if __name__=='__main__':raise SystemExit(main())
