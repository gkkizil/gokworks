"""Project ZIP with per-item provenance, quantities and explicit partial failures."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile
from .models import UnfoldProject,ExportOptions,ExportResult,ExportedFile,Issue,to_data
from .storage import atomic_write
from .exporting import safe_name,_write
from .validation import integer
from .shapes.common import check_cancel,UnfoldCancelled


def export_project(service,project,options,*,cancel_token=None):
    errors=[];files=[];digest=''
    try:
        if not isinstance(project,UnfoldProject) or not isinstance(options,ExportOptions) or options.format!='zip':
            raise ValueError('Toplu proje aktarımı UnfoldProject ve ZIP ExportOptions gerektirir.')
        integer(project.quantity,'Proje adedi',1,1000000)
        if not isinstance(project.items,tuple) or not 1<=len(project.items)<=256:raise ValueError('Proje 1–256 öğe içermeli.')
        if options.quantity_multiplier!=1 or options.part_ids:raise ValueError('Toplu aktarımda adet proje/öğeden alınır; ek adet veya parça filtresi kullanmayın.')
        digest=hashlib.sha256(json.dumps(to_data(project),sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        if options.expected_input_hash is not None and options.expected_input_hash!=digest:raise ValueError('Proje imzası güncel değil.')
        def write(path):
            with TemporaryDirectory(prefix='gokworks-unfold-project-') as folder:
                folder=Path(folder);records=[]
                for i,item in enumerate(project.items,1):
                    check_cancel(cancel_token)
                    try:
                        integer(item.quantity,'Öğe adedi',1,1000000)
                        quantity=integer(project.quantity*item.quantity,'Toplam adet',1,1000000)
                        result=service.calculate(item.request,cancel_token)
                        if result.status!='success':raise ValueError('; '.join(e.message for e in result.errors))
                        opts=replace(options,quantity_multiplier=quantity,project_name=project.name,
                                     project_code=item.code,project_revision=project.revision)
                        formats=('dxf',)+(('pdf',) if options.include_pdf else ())+(('step',) if options.include_step else ())
                        for part in result.parts:
                            base=f'{i:03d}_{safe_name(item.code)}_{safe_name(part.id)}'
                            for kind in formats:
                                check_cancel(cancel_token);target=folder/(base+'.'+kind)
                                common=dict(item_code=item.code,part_id=part.id,request_id=result.request_id,
                                    revision=result.revision,input_hash=result.input_hash,format=kind,quantity=quantity*part.quantity,
                                    calculation_method=result.calculation_method)
                                common.update(development=options.development,forming_report=to_data(result.forming_report))
                                try:
                                    _write(result,(part,),opts,target,kind,cancel_token)
                                    records.append(dict(common,file=target.name,status='complete',sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
                                except UnfoldCancelled:raise
                                except (OSError,ValueError,RuntimeError,ImportError,TypeError) as exc:
                                    target.unlink(missing_ok=True);error=Issue('EXPORT_FAILED',str(exc),part_id=part.id);errors.append(error)
                                    records.append(dict(common,status='error',message=error.message))
                    except UnfoldCancelled:raise
                    except (ValueError,TypeError,AttributeError) as exc:
                        error=Issue('PROJECT_ITEM_FAILED',f'{item.code}: {exc}');errors.append(error)
                        records.append(dict(item_code=item.code,status='error',message=error.message))
                manifest=dict(schema='gokworks.unfolding.project_export',version=1,input_hash=digest,project=to_data(project),
                              status='partial' if errors else 'complete',files=records,errors=to_data(errors))
                (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
                check_cancel(cancel_token)
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                    for p in sorted(folder.iterdir()):z.write(p,p.name)
                with zipfile.ZipFile(path) as z:
                    if z.testzip():raise ValueError('Proje ZIP bütünlüğü başarısız.')
                check_cancel(cancel_token)
        path=atomic_write(options.path,write,options.overwrite)
        files.append(ExportedFile(str(path),'zip',hashlib.sha256(path.read_bytes()).hexdigest()))
    except UnfoldCancelled:raise
    except (ValueError,OSError,TypeError,AttributeError) as exc:errors.append(Issue('PROJECT_EXPORT_FAILED',str(exc)))
    return ExportResult('partial' if errors and files else 'error' if errors else 'complete',
                        'project:'+digest[:16],0,digest,tuple(files),tuple(errors))
