"""Exports only an immutable successful snapshot; partial ZIPs retain explicit errors."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import zipfile
from .models import ExportOptions,ExportResult,ExportedFile,Issue,to_data
from .service import input_hash
from .storage import atomic_write
from .validation import integer
from .shapes.common import check_cancel,UnfoldCancelled


def safe_name(text):
    name=re.sub(r'[^\w.-]+','_',str(text),flags=re.UNICODE).strip(' ._')[:90] or 'parca'
    if name.upper().split('.')[0] in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:name='_'+name
    return name


def _snapshot(result,options):
    if result.status!='success' or result.errors or not result.parts:raise ValueError('Dışa aktarmak için başarılı hesap anlık görüntüsü gerekli.')
    if input_hash(result.normalized_inputs)!=result.input_hash:raise ValueError('Sonuç giriş imzası uyuşmuyor.')
    if result.request_id!=result.normalized_inputs['request_id'] or result.revision!=result.normalized_inputs['revision']:
        raise ValueError('Sonuç istek/revizyon kimliği anlık görüntüyle uyuşmuyor.')
    if not isinstance(options,ExportOptions):raise ValueError('ExportOptions gerekli.')
    if options.expected_revision is not None and options.expected_revision!=result.revision:raise ValueError('Sonuç revizyonu güncel değil.')
    if options.expected_input_hash is not None and options.expected_input_hash!=result.input_hash:raise ValueError('Sonuç giriş imzası güncel değil.')
    if options.format not in ('dxf','pdf','step','zip','json'):raise ValueError('Çıktı biçimi desteklenmiyor.')
    if options.page_size not in ('A4','A3'):raise ValueError('PDF sayfası A4/A3 olmalı.')
    if type(options.overwrite) is not bool or type(options.include_pdf) is not bool or type(options.include_step) is not bool:raise ValueError('Çıktı seçenekleri mantıksal değer olmalı.')
    integer(options.quantity_multiplier,'Adet çarpanı',1,1000000)
    if len(set(options.part_ids))!=len(options.part_ids) or set(options.part_ids)-{p.id for p in result.parts}:raise ValueError('Parça seçimi geçersiz veya tekrarlı.')
    return tuple(p for p in result.parts if not options.part_ids or p.id in options.part_ids)


def _write(result,parts,options,path,kind,cancel_token=None):
    check_cancel(cancel_token)
    key='step_surface' if kind=='step' else kind
    if not result.capabilities.get(key,False):raise ValueError(f'{kind.upper()} bu sonuç/ortam için desteklenmiyor.')
    if kind=='dxf':
        if len(parts)!=1:raise ValueError('DXF için tek parça seçin; çoklu parçada ZIP kullanın.')
        from .dxf import write_dxf
        write_dxf(parts[0],path,result)
    elif kind=='pdf':
        from .pdf import write_pdf
        write_pdf(parts,path,result,options,cancel_token)
    elif kind=='step':
        from .cad_process import execute
        execute(parts,path,cancel_token=cancel_token)
    else:path.write_text(json.dumps(to_data(replace(result,parts=parts)),ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')


def export_result(result,options,*,cancel_token=None):
    files=[];errors=[]
    try:
        check_cancel(cancel_token)
        parts=_snapshot(result,options)
        if options.format=='zip':
            def archive(path):
                with TemporaryDirectory(prefix='gokworks-unfold-zip-') as folder:
                    folder=Path(folder);records=[]
                    for i,part in enumerate(parts,1):
                        check_cancel(cancel_token)
                        base=f'{i:03d}_{safe_name(part.code)}_{hashlib.sha256(part.id.encode()).hexdigest()[:8]}'
                        kinds=('dxf',)+(('pdf',) if options.include_pdf else ())+(('step',) if options.include_step else ())
                        for kind in kinds:
                            target=folder/(base+'.'+kind)
                            try:
                                _write(result,(part,),options,target,kind,cancel_token)
                                records.append(dict(file=target.name,format=kind,part_id=part.id,quantity=part.quantity*options.quantity_multiplier,
                                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),status='complete'))
                            except UnfoldCancelled:raise
                            except (ValueError,OSError,RuntimeError,ImportError,TypeError) as exc:
                                target.unlink(missing_ok=True)
                                error=Issue('EXPORT_FAILED',f'{kind.upper()}: {exc}',part_id=part.id);errors.append(error)
                                records.append(dict(format=kind,part_id=part.id,status='error',message=error.message))
                    manifest=dict(schema='gokworks.unfolding.export',version=1,request_id=result.request_id,revision=result.revision,
                        input_hash=result.input_hash,engine_version=result.engine_version,status='partial' if errors else 'complete',
                        calculation_method=result.calculation_method,normalized_inputs=to_data(result.normalized_inputs),
                        warnings=to_data(result.warnings),files=records,errors=to_data(errors))
                    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
                    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                        for f in sorted(folder.iterdir()):z.write(f,f.name)
                    with zipfile.ZipFile(path) as z:
                        if z.testzip() is not None:raise ValueError('ZIP bütünlük kontrolü başarısız.')
                    check_cancel(cancel_token)
            path=atomic_write(options.path,archive,options.overwrite)
        else:
            def single(path):
                _write(result,parts,options,path,options.format,cancel_token)
                check_cancel(cancel_token)
            path=atomic_write(options.path,single,options.overwrite)
        files.append(ExportedFile(str(path),options.format,hashlib.sha256(path.read_bytes()).hexdigest(),parts[0].id if len(parts)==1 else None))
    except UnfoldCancelled:raise
    except (ValueError,OSError,RuntimeError,ImportError,TypeError,AttributeError) as exc:errors.append(Issue('EXPORT_FAILED',str(exc)))
    return ExportResult('partial' if errors and files else 'error' if errors else 'complete',
        result.request_id,result.revision,result.input_hash,tuple(files),tuple(errors))
