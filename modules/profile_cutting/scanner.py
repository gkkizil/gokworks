"""Instance-aware Weldments orchestration; returns only serializable values."""

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import traceback

from modules.cad_converter.api import call, get, RestoreError
from .solidworks import Session, optional, values
from .models import ScanResult, ScanRow, digest, quantity, number, checkpoint, Cancelled
from .properties import (DEFAULT_MAPPING, evaluated, validate_mapping, length_mm, angle_degrees,
                         section_thickness, identifiable_section, key)
from .geometry import verify


@dataclass(frozen=True)
class Options:
    update_cut_list: bool = False
    geometry_length: bool = False


def read_part(session, model, path, configuration, options, mapping, stop):
    rows = []
    unit = session.display_unit(model)
    extension = folder = body = feature = bodies = None
    seen_bodies = set()
    try:
        extension = get(model, 'Extension')
        needs_rebuild = optional(extension, 'NeedsRebuild2', prop=True)
        extension = None
        for feature, kind in session.cut_folders(model,stop):
            checkpoint(stop)
            folder = call(feature, 'GetSpecificFeature2')
            if folder is None: raise RuntimeError('Cut List BodyFolder okunamadı.')
            if kind == 'SolidBodyFolder':
                if options.update_cut_list and not call(folder, 'UpdateCutList'):
                    raise RuntimeError('Cut List güncellenemedi; modeli SolidWorks’te kontrol edin.')
                continue
            name = str(get(feature, 'Name'))
            row = ScanRow(digest([path.casefold(), configuration, name]), path, configuration, name)
            row.display_unit = unit
            try:
                if options.update_cut_list:
                    updated = bool(call(folder, 'UpdateCutList'))
                    if not updated: row.issues.append('Cut List güncellemesi başarısız.')
                    row.freshness = 'UpdateCutList başarılı' if updated else 'Güncellenemedi'
                else:
                    automatic = optional(folder, 'GetAutomaticUpdate')
                    row.freshness = 'Otomatik güncelleme açık; bekleyen rebuild yok' if automatic and needs_rebuild is False else 'Güncellik doğrulanamadı'
                    if not automatic or needs_rebuild is not False:
                        row.issues.append('Cut List güncelliği doğrulanamadı; güncellemeyi seçin veya SolidWorks’te güncelleyip yeniden tarayın.')
                if needs_rebuild is not False:
                    row.issues.append('Model yeniden oluşturma bekliyor veya durumu okunamadı; SolidWorks’te rebuild yapın.')
                row.properties = session.properties(feature)
                def read(field):
                    try:
                        value = evaluated(row.properties, mapping[field])
                    except ValueError:
                        row.property_errors.append(field); raise
                    matched = any(key(name) in {key(alias) for alias in mapping[field]} for name in row.properties)
                    if not value and (field in ('profile','material','length','count') or matched):
                        row.property_errors.append(field)
                    return value
                for field in ('profile', 'material', 'standard', 'stock_code'):
                    try: setattr(row, field, read(field))
                    except ValueError as error: row.issues.append(str(error))
                try:
                    text = read('length')
                    if text: row.length = str(length_mm(text, unit))
                except ValueError as error:
                    row.property_errors.append('length'); row.issues.append('LENGTH: ' + str(error))
                for field in ('angle1', 'angle2'):
                    try:
                        text = read(field)
                        if text: setattr(row, field, str(angle_degrees(text)))
                    except ValueError as error:
                        row.property_errors.append(field); row.issues.append(str(error))
                try:
                    text = read('thickness')
                    if text: row.thickness = str(length_mm(text, unit))
                except ValueError as error:
                    row.property_errors.append('thickness'); row.issues.append('Et kalınlığı: ' + str(error))
                if unit == 'mm':
                    inferred = section_thickness(row.profile)
                    if inferred is not None:
                        if row.thickness and number(row.thickness) != inferred:
                            row.property_errors.append('thickness')
                            row.issues.append('Profil tanımı ve et kalınlığı property değeri çelişiyor.')
                        elif not row.thickness: row.thickness = str(inferred)
                if row.profile and not identifiable_section(row.profile,row.thickness,row.stock_code):
                    row.property_errors.append('profile')
                    row.issues.append('Profil tanımı kesiti ayırt etmiyor; kesit/et veya doğrulanmış stok kodunu inceleme ekranında tamamlayın.')
                if unit != 'mm' and row.profile and not row.standard and not row.stock_code:
                    row.property_errors.append('profile')
                    row.issues.append('Kesit tanımının birimi doğrulanamadı; mm kesit/et veya standart/stok kodunu manuel doğrulayın.')
                bodies = values(call(folder, 'GetBodies'))
                row.count = len(bodies)
                if call(folder, 'GetBodyCount') != len(bodies):
                    row.issues.append('BodyFolder gövde sayısı, okunan gövdelerle eşleşmiyor.')
                try:
                    declared = read('count')
                    if declared and quantity(declared) != len(bodies):
                        row.property_errors.append('count')
                        row.issues.append(f'QUANTITY={declared}; gerçek gövde adedi={len(bodies)}. Miktarı doğrulayın.')
                except ValueError as error:
                    row.property_errors.append('count'); row.issues.append('Adet: ' + str(error))
                cut_type = call(folder, 'GetCutListType')
                if cut_type != session.c('swWeldmentCutlist'):
                    row.excluded = True
                    row.issues.append('Weldment profil grubu değil; sac/levha/diğer katı inceleme listesinde.')
                verified = []
                unique_bodies = True
                for body in bodies:
                    checkpoint(stop)
                    reference = session.persistent_ref(model, body)
                    if not reference:
                        body_name = str(optional(body, 'Name', prop=True, default='') or '')
                        reference = 'name:' + body_name if body_name else ''
                    if not reference or reference in seen_bodies:
                        unique_bodies = False
                        row.issues.append('Gövde kimliği eksik veya başka Cut List satırında tekrarlandı.')
                    if reference: seen_bodies.add(reference)
                    row.body_refs.append(reference)
                    if call(body, 'IsSheetMetal'):
                        row.excluded = True; row.issues.append('Sac metal gövde; profil kesiminden hariç.')
                    check = verify(session.faces(body,stop), number(row.length) if row.length else None)
                    verified.append(check)
                row.geometry_verified = bool(verified) and all(v.verified for v in verified)
                if not row.geometry_verified:
                    row.issues.append(next((v.reason for v in verified if not v.verified), 'Gövde veya doğrusal geometri bulunamadı.'))
                if not row.length and options.geometry_length and row.geometry_verified:
                    lengths = [v.length_mm for v in verified]
                    if max(lengths)-min(lengths) <= .001:
                        row.length = str(Decimal(str(lengths[0])).quantize(Decimal('.001'),rounding=ROUND_CEILING))
                        row.length_source = 'Doğrulanmış uç düzlemleri geometrisi (mm)'
                if any(value and number(value) not in (0, 90) for value in (row.angle1, row.angle2)):
                    row.issues.append('Gönye/özel uç açısı: testere konvansiyonunu ve gerekli ek ham boyu manuel doğrulayın.')
                try:
                    total = read('total_length')
                    if total and row.length and abs(length_mm(total, unit)-number(row.length)*row.count) > Decimal('.05'):
                        row.property_errors.append('total_length')
                        row.issues.append('TOTAL LENGTH, parça boyu × gövde adediyle eşleşmiyor.')
                except ValueError as error:
                    row.property_errors.append('total_length'); row.issues.append('Toplam boy: ' + str(error))
                row.id = digest([path.casefold(), configuration, sorted(row.body_refs) or [name],
                                 name if not unique_bodies else None])
            except Cancelled: raise
            except Exception as error:
                row.issues.append('Cut List okunamadı: ' + str(error))
            rows.append(row)
            bodies = body = folder = feature = None
        return rows
    finally: model = extension = folder = feature = bodies = body = None


def scan(path=None, options=Options(), mapping=None, events=None, stop=None, *, session_factory=Session):
    mapping = validate_mapping(deepcopy(mapping if mapping is not None else DEFAULT_MAPPING))
    result = None
    model = None
    cache = {}
    merged = {}
    welded = set()
    try:
        with session_factory() as session:
            try:
                model = session.document(path)
                root_path = str(call(model, 'GetPathName') or '')
                if not root_path: raise ValueError('Önce modeli SolidWorks’te kaydedin; kaynak kimliği olmadan tarama yapılamaz.')
                if Path(root_path).suffix.casefold() not in ('.sldprt','.sldasm'):
                    raise ValueError('Modeli önce SLDPRT veya SLDASM olarak kaydedin.')
                configuration = session.active_configuration(model)
                result = ScanResult(root_path, configuration)
                def visit(source, config, occurrence, ancestry=(), context_issues=()):
                    nonlocal model
                    checkpoint(stop)
                    identity = (source.replace('\\','/').casefold(), config)
                    if identity in ancestry or len(ancestry) > 64:
                        result.unscanned += 1
                        result.diagnostics.append(dict(source=source, detail='Döngüsel veya aşırı derin montaj referansı.')); return
                    if events: events.put(('phase', f'Taranıyor: {Path(source).name} [{config}]'))
                    try:
                        if identity not in cache:
                            model = session.document(source)
                            with session.configuration(model, config):
                                if session.is_assembly(model):
                                    cache[identity] = ('assembly', (session.children(model,stop), session.assembly_cautions(model,stop)))
                                else:
                                    rows = read_part(session, model, source, config, options, mapping, stop)
                                    cache[identity] = ('part', rows)
                            model = None
                        kind, data = cache[identity]
                        if kind == 'assembly':
                            components, caution = data
                            inherited = context_issues + tuple(f'{source}: {note}' for note in caution)
                            for component in components:
                                checkpoint(stop)
                                detail = occurrence + '/' + component.name
                                if component.state == 'suppressed':
                                    result.diagnostics.append(dict(source=detail, detail='Suppressed bileşen hariç tutuldu.')); continue
                                if component.state in ('virtual', 'mismatch') or not component.path or not component.configuration:
                                    result.unscanned += 1
                                    result.diagnostics.append(dict(source=detail, detail='Bileşen dosyası/konfigürasyonu okunamadı; sanal veya kimliği tutarsız olabilir.')); continue
                                if component.state == 'lightweight':
                                    result.diagnostics.append(dict(source=detail, detail='Lightweight referansı ayrı salt okunur belge olarak tarandı; montaj çözümleme ayarı değiştirilmedi.'))
                                visit(component.path, component.configuration, detail, ancestry+(identity,), inherited)
                        else:
                            result.scanned_parts += 1
                            if any(not row.excluded for row in data): welded.add(identity)
                            else: result.diagnostics.append(dict(source=source, detail='Cut List bulunamadı. Weldments kesim listesini SolidWorks’te oluşturun.'))
                            for template in data:
                                merge_id = digest([template.id, context_issues]) if context_issues else template.id
                                if merge_id not in merged:
                                    merged[merge_id] = deepcopy(template)
                                    merged[merge_id].id = merge_id
                                    merged[merge_id].issues += list(context_issues)
                                    merged[merge_id].occurrences = []
                                    merged[merge_id].count = 0
                                row = merged[merge_id]
                                row.count += template.count
                                row.occurrences.append(occurrence)
                    except (Cancelled, RestoreError): raise
                    except Exception as error:
                        result.unscanned += 1
                        result.diagnostics.append(dict(source=source, configuration=config, detail=str(error)))
                    finally: model = None
                visit(root_path, configuration, Path(root_path).name)
                result.rows = list(merged.values())
                result.weldments = len(welded)
            except Exception as error:
                # Failed COM calls can keep body/model pointers alive inside
                # completed Python frames. Release those before leaving the
                # STA, while retaining the error type and readable message.
                pending, seen = [error], set()
                while pending:
                    current = pending.pop()
                    if id(current) in seen: continue
                    seen.add(id(current))
                    pending.extend(e for e in (current.__cause__,current.__context__) if e is not None)
                    if current.__traceback__: traceback.clear_frames(current.__traceback__)
                    current.__traceback__ = current.__cause__ = current.__context__ = None
                raise error.with_traceback(None) from None
            finally:
                model = None
                cache.clear()
                merged.clear()
        checkpoint(stop)
        if events: events.put(('weldment_scan', result))
        return result
    except Cancelled:
        if events: events.put(('phase', 'Tarama durduruldu; önceki liste korundu.'))
        return None
