"""Add analysis-only notes; no dimension, tolerance or model parameter setters.

Copy output uses SaveAs(Silent|Copy), verifies dependencies, saves only the
copy, closes it, then atomically publishes the complete native drawing.
Source saves are a separate explicitly approved operation with a verified backup.
"""

from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import os
import shutil
import textwrap

from . import com
from .calculator import check_cancel
from .models import fmt
from .report import assert_current,verdict
from .solidworks_reader import read_document,verify_live
from .storage import atomic_write,fingerprint,check_sources


def dependencies(model):
    values=com.call(model,'GetDependencies2',False,True,False) or ()
    if not isinstance(values,(tuple,list)) or len(values)%2:
        raise RuntimeError('Teknik resim model referansları doğrulanamadı.')
    paths=tuple(sorted(com.path_key(values[i]) for i in range(1,len(values),2)))
    if any(not path or not (':' in path or path.startswith('/')) for path in paths):
        raise RuntimeError('Model referansları mutlak yol olarak çözülemedi; farklı kaydet yapılmadı.')
    return paths


def analysis_lines(project,result):
    dimensions={d.id:d for d in project.dimensions}
    chain=' '.join(('+' if t.direction>0 else '−')+f'{fmt(t.factor,3)}×L{i}' for i,t in enumerate(project.terms,1))
    rows=[f'GOKWORKS · {project.id} · {result.project_digest[:12]}','TOLERANCE STACK-UP ANALYSIS',
        project.name,project.critical,chain,f'Başlangıç: {project.start} / Bitiş: {project.end}',
        f'Eksen / ortak datum: {project.axis} / {project.datum}',f'Nominal: {fmt(result.nominal)} mm',
        f'Worst-Case: {fmt(result.minimum)} … {fmt(result.maximum)} mm',
        f'RSS: {fmt(result.rss_minimum)} … {fmt(result.rss_maximum)} mm',
        f'Kabul: {"Yok" if project.acceptance_min is None else fmt(project.acceptance_min)} … '
        f'{"Yok" if project.acceptance_max is None else fmt(project.acceptance_max)} mm',
        f'Worst-Case: {verdict(result.worst_case_pass)} / RSS: {verdict(result.rss_pass)}',
        f'Yöntem: {project.method} / Sonuç bandı: ±{project.output_sigma}σ',
        f'Hesap zamanı (UTC): {result.timestamp}','KAYNAK ÖLÇÜLER · mm']
    for i,t in enumerate(project.terms,1):
        d=dimensions[t.dimension_id]
        rows += [f'L{i}: {d.name} = {fmt(d.nominal)} [{fmt(d.lower)} / {fmt(d.upper)}]',
                 f'  {Path(d.source).name or "Manuel"} · {d.sheet} · {d.view} · {d.configuration}',
                 f'  ID: {d.api_name or d.id} · Veri: {d.provenance}']
        if t.relation: rows.append('  İlişki: '+t.relation)
        if t.alignment_confirmed: rows.append('  Ortak doğrultu / referans: kullanıcı doğruladı; CAD geometrisinden çıkarılmadı.')
    if result.monte_carlo:
        mc=result.monte_carlo
        rows += [f'MC: n={mc["samples"]}, seed={mc["seed"]}, ortalama={fmt(mc["mean"])} mm, σ={fmt(mc["sigma"])} mm',
                 f'Tahmini PPM: {mc["ppm"]} (simülasyon); örnek uçları WC sınırı değildir.']
    rows += ['VARSAYIMLAR',*result.assumptions]
    return [line for row in rows for line in textwrap.wrap(str(row).replace('$','＄').replace('<','‹').replace('>','›').replace('\r',''),100) or ['']]


def insert_note(model,text,x,y,created):
    note=com.call(model,'InsertNote',text)
    if note is None: raise RuntimeError('SolidWorks analiz notunu oluşturmadı.')
    annotation=com.call(note,'GetAnnotation');created.append(annotation)
    if str(com.call(note,'GetText')).replace('\r\n','\n')!=text:
        raise RuntimeError('Analiz notu geri okunarak doğrulanamadı.')
    if not com.call(annotation,'SetPosition2',float(x),float(y),0.):
        raise RuntimeError('Analiz notu yerleştirilemedi.')
    # Set the new note's own text size only. No production annotation is edited.
    format=com.call(annotation,'GetTextFormat',0)
    com.put(format,'CharHeight',.0025)
    if not com.call(annotation,'SetTextFormat',0,False,format): raise RuntimeError('Analiz notu metin biçimi uygulanamadı.')
    return note


def remove_annotations(model,annotations,sheets):
    failures=[]
    for annotation in reversed(annotations):
        try:
            if not com.call(annotation,'Select3',False,com.null_dispatch()) or not com.call(com.get(model,'Extension'),'DeleteSelection2',0):
                failures.append('Analiz notu silinemedi.')
        except Exception: failures.append('Analiz notu silinemedi.')
    for sheet in reversed(sheets):
        try:
            if not com.call(com.get(model,'Extension'),'SelectByID2',sheet,'SHEET',0.,0.,0.,False,0,com.null_dispatch(),0):
                raise RuntimeError('Sayfa seçilemedi.')
            if not com.call(com.get(model,'Extension'),'DeleteSelection2',0): raise RuntimeError('Sayfa silinemedi.')
        except Exception: failures.append('Analiz sayfası silinemedi.')
    if failures: raise RuntimeError(' '.join(failures)+' Kaynak belgeyi kaydetmeden yeniden açın.')


def add_analysis(model,project,result,*,new_sheet=True,labels=False,position=(.02,.25),stop=None):
    source=str(com.call(model,'GetPathName'))
    before,_=read_document(model,stop=stop)
    signatures={d.id:d.original_signature for d in before}
    old_sheet=str(com.call(com.call(model,'GetCurrentSheet'),'GetName'))
    created=[];sheets=[]
    try:
        with com.preserve_selection(model):
            lines=analysis_lines(project,result)
            if not new_sheet and (len(lines)>42 or max(map(len,lines),default=0)>150):
                raise ValueError('Not seçilen sayfaya sığmayabilir. Ayrı analiz sayfasını veya PDF/Excel raporunu seçin.')
            chunks=[lines[i:i+38] for i in range(0,len(lines),38)] if new_sheet else [lines]
            for i,chunk in enumerate(chunks,1):
                check_cancel(stop)
                if new_sheet:
                    name=f'GOKWORKS-{uuid4().hex[:8]}-{i}'
                    # swDwgPapersUserDefined=12, swDwgTemplateNone=13.
                    if not com.call(model,'NewSheet3',name,12,13,1.,1.,True,'',.420,.297,''):
                        raise RuntimeError('Ayrı analiz sayfası oluşturulamadı.')
                    sheets.append(name)
                    if not com.call(model,'ActivateSheet',name): raise RuntimeError('Analiz sayfası etkinleştirilemedi.')
                text='\n'.join(([f'GOKWORKS · {project.id} · devam {i}'] if i>1 else [])+chunk)
                insert_note(model,text,.015 if new_sheet else position[0],.280 if new_sheet else position[1],created)
            if labels:
                by_id={d.id:d for d in project.dimensions}
                for i,term in enumerate(project.terms,1):
                    check_cancel(stop);d=by_id[term.dimension_id]
                    # Copy file uses the original source identifiers as provenance.
                    if d.sheet and len(d.position)>=2 and d.source:
                        if com.path_key(d.source) not in (com.path_key(source),com.path_key(getattr(project,'_label_source',source))): continue
                        if not com.call(model,'ActivateSheet',d.sheet): raise RuntimeError('Etiket kaynak sayfası bulunamadı.')
                        insert_note(model,f'GOKWORKS · {project.id[:8]} · L{i}',d.position[0]/1000+.004,d.position[1]/1000+.004,created)
            after,_=read_document(model,stop=stop)
            if signatures!={d.id:d.original_signature for d in after}:
                raise RuntimeError('Üretim ölçüleri değişti veya silindi; anotasyon işlemi geri alınacak.')
            check_cancel(stop)
    except Exception as error:
        try:
            with com.preserve_selection(model): remove_annotations(model,created,sheets)
        except Exception as rollback: raise RuntimeError(f'{error} GERİ ALMA: {rollback}') from error
        raise
    finally:
        if not com.call(model,'ActivateSheet',old_sheet): raise RuntimeError('Önceki teknik resim sayfası geri getirilemedi.')
    return created,sheets


def save_document(model):
    errors,warnings=com.out_int(),com.out_int()
    success=com.call(model,'Save3',1,errors,warnings)
    if not success or errors.value or com.call(model,'GetSaveFlag'):
        raise RuntimeError(f'Teknik resim kaydı doğrulanamadı; API kodu: {errors.value}, uyarı: {warnings.value}.')


def write_drawing(project,result,source,*,mode='memory',destination=None,new_sheet=True,labels=False,
                  position=(.02,.25),approved=False,stop=None):
    assert_current(project,result,stop=stop)
    if project.offline_snapshot: raise ValueError('Teknik resme aktarım için çevrimdışı anlık görüntü seçimini kapatıp kaynakları canlı doğrulayın.')
    verify_live(project,stop=stop)
    if mode not in ('memory','copy','source'): raise ValueError('Teknik resim çıktı yöntemi geçersiz.')
    if mode=='source' and not approved: raise PermissionError('Kaynak üzerine kayıt için açık kullanıcı onayı gerekir.')
    if not str(source).casefold().endswith('.slddrw'): raise ValueError('Hedef .SLDDRW olmalı.')
    with com.Session() as session:
        original=session.document(source,readonly=False)
        session.activate(original)
        original_stamp=fingerprint(source,stop=stop)
        references=dependencies(original)
        old_name=com.call(original,'GetPathName');old_dirty=bool(com.call(original,'GetSaveFlag'))
        backup=None
        if mode=='copy':
            if not destination or not str(destination).casefold().endswith('.slddrw'): raise ValueError('Yeni .SLDDRW çıktı yolu seçin.')
            forbidden={com.path_key(s.path) for s in project.sources}|{com.path_key(source)}|set(references)
            if com.path_key(Path(destination).resolve()) in forbidden: raise ValueError('Kopya kaynak çizim veya model dosyasının üzerine yazılamaz.')
            def write(temporary):
                errors,warnings=com.out_int(),com.out_int()
                if not com.call(com.get(original,'Extension'),'SaveAs',str(temporary),0,3,com.null_dispatch(),errors,warnings) or errors.value:
                    raise RuntimeError(f'Analiz kopyası oluşturulamadı; API kodu: {errors.value}.')
                if com.call(original,'GetPathName')!=old_name or bool(com.call(original,'GetSaveFlag'))!=old_dirty:
                    raise RuntimeError('SaveAs Copy kaynak belge kimliğini/durumunu değiştirdi; işlem durduruldu.')
                copy=session.document(str(temporary),readonly=False);session.activate(copy)
                if dependencies(copy)!=references: raise RuntimeError('Kopyada model referansları değişti; çıktı yayımlanmadı.')
                # Target filename is staging-only; dimension identities before/after
                # are read consistently from that copy, never compared across paths.
                from dataclasses import replace
                label_project=replace(project)
                label_project._label_source=str(source)
                add_analysis(copy,label_project,result,new_sheet=new_sheet,labels=labels,position=position,stop=stop)
                check_cancel(stop);save_document(copy)
                if dependencies(copy)!=references: raise RuntimeError('Kaydedilen kopyada model referansları değişti.')
                session.close_owned(copy)
                if temporary.stat().st_size<8: raise RuntimeError('Native çizim dosyası boş veya eksik.')
                if fingerprint(source,stop=stop).sha256!=original_stamp.sha256: raise RuntimeError('Kaynak çizim kayıt sırasında değişti.')
                check_sources(project,stop=stop)
            path=atomic_write(destination,write,stop=stop)
            return dict(mode=mode,path=str(path),backup=None,saved=True)
        if mode=='source':
            if old_dirty: raise ValueError('Kaynak çizimde kaydedilmemiş kullanıcı değişiklikleri var. Önce SolidWorks’te kendiniz kaydedin; sonra yeniden tarayın.')
            folder=Path(source).parent/'.gokworks-backups'
            backup=folder/(Path(source).stem+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]+'.SLDDRW')
            atomic_write(backup,lambda temporary:shutil.copyfile(source,temporary),stop=stop)
            if fingerprint(backup).sha256!=original_stamp.sha256: raise RuntimeError('Kaynak yedeği doğrulanamadı; değişiklik yapılmadı.')
        created=sheets=None
        try:
            created,sheets=add_analysis(original,project,result,new_sheet=new_sheet,labels=labels,position=position,stop=stop)
            check_cancel(stop)
            if mode=='source': save_document(original)
            elif fingerprint(source,stop=stop).sha256!=original_stamp.sha256: raise RuntimeError('Kaynak dosya beklenmeden değişti.')
        except Exception as original_error:
            rollback_error=None
            if created is not None:
                try:
                    with com.preserve_selection(original): remove_annotations(original,created,sheets)
                except Exception as error: rollback_error=error
            if mode=='source' and backup is not None and fingerprint(source).sha256!=original_stamp.sha256:
                atomic_write(source,lambda temporary:shutil.copyfile(backup,temporary),overwrite=True)
                if fingerprint(source).sha256!=original_stamp.sha256: raise RuntimeError('Kaynak yedekten geri yüklenemedi; yedek dosyasını koruyun.')
                raise RuntimeError('Kayıt doğrulanamadı; disk dosyası yedekten geri getirildi. Açık çizimi kaydetmeden yeniden açın.')
            if rollback_error is not None: raise RuntimeError(f'{original_error} Geri alma hatası: {rollback_error}') from original_error
            raise
        session.keep(original)  # Keep the explicitly annotated document visible to the user.
        return dict(mode=mode,path=str(source),backup=str(backup) if backup else None,saved=mode=='source')
