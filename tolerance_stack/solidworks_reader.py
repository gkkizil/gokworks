"""Read all drawing sheets/views through the published drawing API.

Traversal adapted from CodeStack export-dimensions (MIT, Xarial Pty Limited).
See packaging/licenses/tolerance-stack and docs/tolerance-stack.md.
Numeric API values are metres/radians, never inferred from rounded display text.
"""

import base64
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import math
import re

from . import com
from .calculator import check_cancel
from .models import Dimension, digest, number
from .storage import fingerprint, check_sources


# Verified against SolidWorks.Interop.swconst 2023 metadata, not ordinal guesses.
TOLERANCE_TYPES={0:'Yok',1:'BASIC',2:'Asimetrik',3:'Limit',4:'Simetrik',5:'Minimum',6:'Maksimum',
                 7:'ISO geçme',8:'ISO geçme + tolerans',9:'Yalnız geçme toleransı',10:'Blok',11:'Genel'}
DIMENSION_TYPES={1:'ordinate',2:'linear',3:'angle',4:'arc',5:'radius',6:'diameter',7:'ordinate',8:'ordinate',
                 9:'linear',10:'chamfer',11:'horizontal',12:'vertical',13:'unknown',14:'radius',15:'diameter'}


def signature(dimension):
    return digest({key:getattr(dimension,key) for key in ('nominal','lower','upper','kind','tolerance_type','source',
        'sheet','view','configuration','model','api_name','display_text','position','physical_id')})


def drawing_unit(model,angular=False):
    try:
        unit=com.call(model,'GetUserUnit',1 if angular else 0)
        factor=float(com.call(unit,'GetConversionFactor'))
        choices=((1.,'rad'),(180/math.pi,'deg')) if angular else ((1000.,'mm'),(100.,'cm'),(1.,'m'),(1000/25.4,'in'),(1000000.,'µm'))
        return next((name for value,name in choices if math.isclose(value,factor,rel_tol=1e-7)),'unknown')
    except RuntimeError: return 'unknown'


def read_dimension(model,view,display,source,sheet,view_name,sequence,general_notes,units=None):
    notes=[];nominal=lower=upper=None;position=();persist='';api_name='';dimension=None
    try:kind=DIMENSION_TYPES.get(com.get(display,'Type2'),'unknown')
    except RuntimeError:kind='unknown';notes.append('Ölçü türü okunamadı; manuel sınıflandırma gerekli.')
    angular=kind=='angle'
    tolerance_type='Bilinmiyor'
    configuration=str(com.optional(view,'ReferencedConfiguration',property=True,default='') or '')
    reference_model=str(com.optional(view,'GetReferencedModelName',default='') or '')
    try:annotation=com.call(display,'GetAnnotation')
    except RuntimeError:annotation=None
    try:
        pos=com.call(annotation,'GetPosition')
        if pos: position=tuple(float(number(x)*1000) for x in pos)
        raw=com.call(com.get(model,'Extension'),'GetPersistReference3',annotation)
        if raw: persist=base64.b64encode(bytes(raw)).decode()
    except RuntimeError: notes.append('Anotasyon kalıcı referansı/konumu okunamadı; sayfa ve görünüm ile bulunabilir.')
    try:
        dimension=com.call(display,'GetDimension2',0)
        api_name=str(com.get(dimension,'FullName'))
        values=com.call(dimension,'GetSystemValue3',3 if configuration else 1,com.config_array(configuration))
        if not isinstance(values,(tuple,list)) or len(values)!=1:
            raise RuntimeError('Nominal değer tek konfigürasyona bağlanamadı.')
        nominal=number(values[0])*(1 if angular else 1000)
    except (RuntimeError,ValueError): notes.append('Nominal ölçü/konfigürasyon okunamadı; manuel tamamlayın.')
    try:
        reference=bool(com.call(display,'IsReferenceDim'))
        tolerance=com.get(dimension,'Tolerance')
        tol_kind=int(com.get(tolerance,'Type'))
        tolerance_type=TOLERANCE_TYPES.get(tol_kind,f'Desteklenmeyen API türü {tol_kind}')
        if tol_kind==1: kind='basic'
        elif reference: kind='reference'
        if tol_kind in (2,3,4,7,8,9,10,11):
            factor=1 if angular else 1000
            lower=number(com.tolerance_value(tolerance,'GetMinValue2'))*factor
            upper=number(com.tolerance_value(tolerance,'GetMaxValue2'))*factor
            if lower>upper: raise ValueError('Alt/üst tolerans tutarsız.')
            evidence=[text for text in general_notes if re.search(r'ISO\s*2768|genel\s+tolerans|general\s+toleranc|unless.+specified',text,re.I)]
            if tol_kind in (10,11) and (not evidence or lower==upper==0):
                lower=upper=None
                notes.append('Genel/blok toleransı çizim notlarından sayısal olarak doğrulanamadı. Otomatik tablo atanmadı.')
        elif tol_kind not in (0,1):
            notes.append('Tek taraflı sınırsız veya desteklenmeyen tolerans; sonlu alt/üst sınırları manuel tamamlayın.')
        if tol_kind in (7,8,9) and nominal is not None:
            hole=str(com.call(tolerance,'GetHoleFitValue') or '').strip()
            shaft=str(com.call(tolerance,'GetShaftFitValue') or '').strip()
            tolerance_type += ' · '+('/'.join(c for c in (hole,shaft) if c))
            if hole and shaft:
                lower=upper=None;notes.append('Delik/mil çift gösterimi: tek ölçüye indirgenmedi. ISO araçlarıyla iki ayrı fonksiyonel ölçü oluşturun.')
            elif hole or shaft:
                from iso_fits.rules import limits,mm
                band=limits(str(nominal),hole or shaft,'hole' if hole else 'shaft')
                if lower is None or upper is None or abs(lower-mm(band.lower_nm))>Decimal('.000000001') or abs(upper-mm(band.upper_nm))>Decimal('.000000001'):
                    lower=upper=None;notes.append('SolidWorks toleransı doğrulanan ISO 286 tablosuyla uyuşmuyor; manuel inceleyin.')
    except (RuntimeError,ValueError) as error:
        lower=upper=None;notes.append(str(error))
    text=str(com.optional(display,'GetText',0,default='') or '')
    if com.optional(display,'GetOverride',default=False):
        lower=upper=None;notes.append('Görünen ölçü override içeriyor; model değeriyle görüntü aynı kabul edilmedi. Manuel inceleyin.')
    identity=api_name or str((com.optional(annotation,'GetName',default='') if annotation is not None else '') or f'Okunamayan-{sequence}')
    if not api_name: notes.append('API ölçü adı okunamadı; yeniden taramada kimliği inceleyin.')
    record=Dimension(digest((source,sheet,view_name,identity)),identity,nominal,lower,upper,kind=kind,
        tolerance_type=tolerance_type,source=source,sheet=sheet,view=view_name,configuration=configuration,
        model=reference_model,api_name=api_name,persistent_ref=persist,
        physical_id=digest((com.path_key(reference_model or source),configuration,api_name)) if api_name else '',
        position=position,display_unit='rad' if angular else 'mm',display_text=text,provenance='solidworks',
        note='\n'.join(notes)+f'\nÇizim gösterim birimi: {(units or {}).get(angular) or drawing_unit(model,angular)}; hesap birimi: '+('rad' if angular else 'mm'))
    return replace(record,original_signature=signature(record))


def read_document(model,*,stop=None,progress=None):
    model=com.drawing(model)
    source=str(com.call(model,'GetPathName'))
    if not source: raise ValueError('Teknik resmin kimliği için önce .SLDDRW olarak kaydedin; araç kaynak dosyayı kaydetmez.')
    before=fingerprint(source,stop=stop,title=str(com.call(model,'GetTitle')),dirty=bool(com.call(model,'GetSaveFlag')))
    sheets=com.call(model,'GetViews')
    if not isinstance(sheets,(tuple,list)): raise RuntimeError('Teknik resim sayfaları okunamadı.')
    dimensions=[];notes=[];seen=set()
    units={False:drawing_unit(model),True:drawing_unit(model,True)}
    for group in sheets:
        if not isinstance(group,(tuple,list)): raise RuntimeError('GetViews sayfa/görünüm yapısı geçersiz.')
        sheet_notes=[]
        for view in group:
            for note in com.optional(view,'GetNotes',default=()) or ():
                text=str(com.call(note,'GetText') or '')
                if text and not text.startswith('GOKWORKS ·'):sheet_notes.append(text)
        notes.extend(sheet_notes)
        for view in group:
            check_cancel(stop)
            view_name=str(com.call(view,'GetName2'))
            sheet=com.get(view,'Sheet')
            sheet_name=str(com.call(sheet,'GetName')) if sheet is not None else view_name
            display=com.call(view,'GetFirstDisplayDimension5');count=0
            while display is not None:
                check_cancel(stop);count+=1
                if count>20000: raise RuntimeError('Görünüm ölçü taraması güvenli sınırı aştı.')
                record=read_dimension(model,view,display,source,sheet_name,view_name,count,sheet_notes,units)
                if record.id in seen: raise RuntimeError('Ölçü kimliği tekrarlanıyor; tarama güvenli biçimde durduruldu.')
                seen.add(record.id);dimensions.append(record)
                if progress: progress(len(dimensions))
                display=com.call(display,'GetNext5')
            for i,gtol in enumerate(com.optional(view,'GetGTols',default=()) or (),1):
                annotation=com.call(gtol,'GetAnnotation')
                name=str(com.call(annotation,'GetName'))
                dimensions.append(Dimension(digest((source,sheet_name,view_name,name,'gdt')),name,None,None,None,
                    kind='gdt',source=source,sheet=sheet_name,view=view_name,api_name=name,provenance='solidworks',
                    note='GD&T çerçevesi; doğrulanmış 2D/3D model olmadan 1D zincire alınamaz.'))
    after=fingerprint(source,stop=stop)
    if before.sha256!=after.sha256: raise RuntimeError('Tarama sırasında kaynak çizim değişti; yeniden okuyun.')
    return dimensions,replace(before,notes=tuple(dict.fromkeys(notes)))


def read_sources(paths=None,*,stop=None,progress=None):
    records=[];sources=[]
    with com.Session() as session:
        for path in paths or (None,):
            model=session.document(path)
            dimensions,source=read_document(model,stop=stop,progress=progress)
            records.extend(dimensions);sources.append(source)
    return records,sources


def verify_live(project,*,stop=None):
    check_sources(project,stop=stop)
    if not project.sources or project.offline_snapshot: return
    current,_=read_sources([s.path for s in project.sources],stop=stop)
    by_id={item.id:item for item in current}
    used={t.dimension_id for t in project.terms}
    for original in project.dimensions:
        if original.id not in used or not original.source: continue
        item=by_id.get(original.id)
        if item is None or item.original_signature!=original.original_signature:
            raise ValueError(f'{original.name}: açık teknik resimde ölçü değişmiş/silinmiş. Yeniden tarayın; eski sonuç kullanılamaz.')


def highlight(record):
    with com.Session() as session:
        model=session.document(record.source)
        session.activate(model)
        if not com.call(model,'ActivateSheet',record.sheet): raise RuntimeError('Kaynak sayfa bulunamadı.')
        if not record.persistent_ref: raise ValueError('Ölçünün kalıcı anotasyon referansı yok; sayfa/görünüm bilgisini kullanın.')
        error=com.out_int()
        reference=com.variant(0x2011,tuple(base64.b64decode(record.persistent_ref)))
        annotation=com.call(com.get(model,'Extension'),'GetObjectByPersistReference3',reference,error)
        if annotation is None or error.value: raise ValueError('Kaynak ölçü değişmiş veya silinmiş; yeniden tarayın.')
        if not com.call(annotation,'Select3',False,com.null_dispatch()): raise RuntimeError('Ölçü SolidWorks üzerinde vurgulanamadı.')
        session.keep(model)
        session.previous=''  # Explicit source navigation should leave that drawing visible.
