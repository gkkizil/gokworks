"""Read-only body/Cut List/FlatPattern evidence for native drawing pages.

Only existing derived flat configurations are eligible. No suppression,
configuration creation, Cut List update, rebuild or source save is performed.
"""

from collections import Counter, defaultdict
import math
from pathlib import Path
import re

from modules.cad_converter.api import ApiError, RestoreError, PART_IID
from .models import Cancelled, SheetBody, checkpoint, to_mm
from .solidworks import (as_interface, call, get, hresult, null_dispatch, optional,
                         values, variant)

MAX_BODIES = 256
MAX_FLAT_CONFIGURATIONS = 128


def propagate(error):
    if isinstance(error, (Cancelled, RestoreError)) or hresult(error) in (
            -2147417848, -2147023174, -2147418111, -2147417846):
        raise error


def feature_by_ref(session, model, name, reference, kind):
    feature = call(model, 'FeatureByName', name)
    if not reference or feature is None or call(feature, 'GetTypeName2') != kind or (
            session.persistent_ref(model, feature) != reference):
        raise ApiError('Unsurun kalıcı kimliği doğrulanamadı: '+name)
    return feature


def fixed_body_ref(session, model, feature):
    """Release definition rollback before resolving any body used by a drawing."""
    definition = fixed = body = None
    attempted = False
    try:
        definition = call(feature, 'GetDefinition')
        if definition is None:
            raise ApiError('FlatPattern tanımı okunamadı.')
        fixed = optional(definition, 'FixedFace2', property=True)
        if fixed is not None:
            body = call(fixed, 'GetBody')
            reference = session.persistent_ref(model, body) if body is not None else ''
            if reference:
                return reference
        # FixedFace2 can require AccessSelections on suppressed patterns. That
        # is a temporary rollback scope, never a ModifyDefinition operation.
        fixed = body = None
        attempted = True
        if call(definition, 'AccessSelections', model, null_dispatch()) is not True:
            raise ApiError('FlatPattern sabit yüz seçimine erişilemedi.')
        fixed = get(definition, 'FixedFace2')
        body = call(fixed, 'GetBody') if fixed is not None else None
        reference = session.persistent_ref(model, body) if body is not None else ''
        if not reference:
            raise ApiError('FlatPattern gövdesinin kalıcı kimliği okunamadı.')
        return reference
    finally:
        fixed = body = None
        try:
            if attempted:
                call(definition, 'ReleaseSelectionAccess')
        except Exception as error:
            raise RestoreError('FlatPattern tanım erişimi geri alınamadı; kuyruk durduruldu.') from error
        finally:
            definition = feature = model = None


def flat_configurations(session, model, info, stop=None):
    names = info.configurations or info.flat_configurations
    if len(names) > MAX_FLAT_CONFIGURATIONS:
        raise ApiError('Açınım konfigürasyonu sayısı güvenli tarama sınırını aştı.')
    matching = []
    for name in names:
        checkpoint(stop)
        if name == info.source.configuration:
            continue
        config = call(model, 'GetConfigurationByName', name)
        parent = call(config, 'GetParent') if config is not None else None
        if parent is not None and str(get(parent, 'Name')) == info.source.configuration:
            matching.append(name)
    return tuple(matching)


def unfolded_configurations(session, feature, configurations):
    if not configurations:
        return ()
    states = values(call(feature, 'IsSuppressed2', session.c('swSpecifyConfiguration'),
                         variant(0x2008, configurations)))
    if len(states) != len(configurations) or any(type(s) is not bool for s in states):
        raise ApiError('FlatPattern konfigürasyon durumları okunamadı.')
    return tuple(name for name, suppressed in zip(configurations, states) if not suppressed)


def thickness(session, body, properties, unit):
    measured = []
    for feature in values(optional(body, 'GetFeatures', default=())):
        if call(feature, 'GetTypeName2') != 'SheetMetal':
            continue
        state = values(call(feature, 'IsSuppressed2', session.c('swThisConfiguration'), variant(0, None)))
        if state == (False,):
            measured.append(to_mm(get(call(feature, 'GetDefinition'), 'Thickness')))
    if measured:
        if any(v <= 0 or not math.isclose(v, measured[0], rel_tol=1e-8, abs_tol=1e-6) for v in measured):
            raise ApiError('Gövdeye bağlı SheetMetal kalınlıkları tutarsız.')
        return measured[0]
    for key in ('SHEET METAL THICKNESS', 'SHEETMETAL THICKNESS', 'THICKNESS', 'SAC KALINLIĞI'):
        match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|inch|ft|\")?',
                             properties.get(key, '').strip(), re.I)
        if match:
            factor = {'mm': 1., 'cm': 10., 'm': 1000., 'in': 25.4, 'inch': 25.4,
                      '"': 25.4, 'ft': 304.8}.get((match[2] or unit).lower())
            if factor is not None:
                result = float(match[1].replace(',', '.'))*factor
                if math.isfinite(result) and result > 0:
                    return result
    return None


def material(body, configuration, properties):
    native = optional(body, 'GetMaterialPropertyName2', configuration, variant(0x4008, ''), default='')
    return next((properties[k].strip() for k in ('MATERIAL', 'SW-MATERIAL', 'MALZEME')
                 if properties.get(k, '').strip()), '') or (native.strip() if isinstance(native, str) else '')


def inspect_bodies(session, model, info, features, stop=None):
    """features are (label, kind, persistent ID); no COM handle enters the result."""
    patterns, folders = defaultdict(list), defaultdict(list)
    issues = []
    feature = folder = body = None
    bodies = ()
    try:
        if session.active_configuration(model) != info.source.configuration:
            raise ApiError('Sac analizi için kaynak konfigürasyonu değişmiş.')
        if info.sheet_body_count > MAX_BODIES:
            raise ApiError('Sac gövdesi sayısı güvenli tarama sınırını aştı.')
        # A user may rename SM-FLAT-PATTERN to a Turkish/company-specific name.
        # Parent identity AND the actual feature state determine eligibility.
        configs = flat_configurations(session, model, info, stop)
        # A definition access can invalidate all earlier body pointers. Process
        # definitions first, then reacquire the current source bodies below.
        for name, kind, reference in features:
            checkpoint(stop)
            try:
                feature = feature_by_ref(session, model, name, reference, kind)
                if kind == 'FlatPattern':
                    token = fixed_body_ref(session, model, feature)
                    feature = feature_by_ref(session, model, name, reference, kind)
                    patterns[token].append((name, reference, unfolded_configurations(session, feature, configs)))
                elif kind == 'CutListFolder':
                    folder = call(feature, 'GetSpecificFeature2')
                    members = tuple(session.persistent_ref(model, member)
                                    for member in values(call(folder, 'GetBodies')))
                    properties = session.property_values(get(feature, 'CustomPropertyManager'))
                    for token in set(members)-{''}:
                        folders[token].append((name, reference, members, properties))
            except Exception as error:
                propagate(error)
                issues.append(name+': '+str(error))
            finally:
                feature = folder = None
        if session.active_configuration(model) != info.source.configuration:
            raise ApiError('Sac özellikleri okunurken kaynak konfigürasyonu değişti; eski veri kullanılmadı.')
        part = as_interface(model, PART_IID)
        bodies = values(call(part, 'GetBodies2', session.c('swSolidBody'), False))
        sheets = [(session.persistent_ref(model, b), b) for b in bodies if call(b, 'IsSheetMetal')]
        if len(sheets) != info.sheet_body_count or len(sheets) > MAX_BODIES:
            raise ApiError('Sac gövdesi sayısı değişti veya güvenli tarama sınırı aşıldı.')
        counts = Counter(token for token, b in sheets)
        rows = []
        for index, (token, body) in enumerate(sorted(sheets, key=lambda pair: pair[0]), 1):
            checkpoint(stop)
            label = Path(info.source.path).stem+(f'-{index:02d}' if info.body_count > 1 else '')
            row = SheetBody(index, label, str(optional(body, 'Name', property=True, default='') or ''), token,
                            warnings=list(issues))
            rows.append(row)
            if not token or counts[token] != 1:
                row.body_ref = ''
                row.warnings.append('Gövdenin tekil kalıcı kimliği okunamadı; isimle tahmin edilmedi.')
                continue
            box = values(call(body, 'GetBodyBox'))
            if len(box) != 6:
                raise ApiError('Sac gövdesinin dış sınırları okunamadı.')
            row.size_mm = tuple(to_mm(box[i+3]-box[i]) for i in range(3))
            if any(v <= 0 for v in row.size_mm):
                raise ApiError('Sac gövdesinin dış ölçüleri geçersiz.')
            matches = folders.get(token, ())
            properties = {}
            if len(matches) == 1:
                row.cut_list, row.cut_list_ref, members, props = matches[0]
                row.cut_list_quantity = len(members)
                properties = {k.upper(): str(v) for k, v in props.items()}
            else:
                row.warnings.append('Gövdeye bağlı tek bir Cut List doğrulanamadı.')
            try:
                row.thickness_mm = thickness(session, body, properties, info.source_unit)
            except Exception as error:
                propagate(error)
                row.warnings.append(str(error))
            if row.thickness_mm is None:
                row.warnings.append('Gövde kalınlığı doğrulanamadı; modelin ortak kalınlığı kullanılmadı.')
            row.material = material(body, info.source.configuration, properties)
            if not row.material:
                row.warnings.append('Gövde malzemesi doğrulanamadı; ortak model malzemesi gövdeye atanmadı.')
            candidates = patterns.get(token, ())
            if len(candidates) == 1:
                row.flat_feature, row.flat_ref, row.configurations = candidates[0]
            else:
                row.warnings.append('Gövdeye bağlı tek bir FlatPattern doğrulanamadı.')
            if len(row.configurations) != 1:
                row.warnings.append('Bu gövdenin açıldığı tek bir mevcut konfigürasyon doğrulanamadı; açınım atlandı.')
        return rows
    finally:
        patterns.clear(); folders.clear()
        feature = folder = body = model = None
        bodies = sheets = part = ()


def verify_unfolded(session, model, row, configuration):
    """Recheck the feature identity and its EXISTING configuration before output."""
    feature = feature_by_ref(session, model, row.flat_feature, row.flat_ref, 'FlatPattern')
    if unfolded_configurations(session, feature, (configuration,)) != (configuration,):
        raise ApiError('Gövdenin FlatPattern unsuru açınım konfigürasyonunda bastırılmış.')


def verify_metadata(session, model, row, info):
    """A drawing header must not silently retain stale thickness/material data."""
    part = body = feature = folder = None
    candidates = members = ()
    try:
        with session.configuration(model, info.source.configuration):
            properties = {}
            if row.cut_list:
                feature = feature_by_ref(session, model, row.cut_list, row.cut_list_ref, 'CutListFolder')
                folder = call(feature, 'GetSpecificFeature2')
                members = values(call(folder, 'GetBodies'))
                references = tuple(session.persistent_ref(model, member) for member in members)
                if row.body_ref not in references or len(members) != row.cut_list_quantity:
                    raise ApiError(row.label+': Cut List gövde üyeliği / adedi değişmiş.')
                properties = {k.upper(): v for k, v in session.property_values(
                    get(feature, 'CustomPropertyManager')).items()}
                members = (); folder = feature = None
            if session.active_configuration(model) != info.source.configuration:
                raise ApiError('Gövde özellikleri okunurken kaynak konfigürasyonu değişti.')
            part = as_interface(model, PART_IID)
            candidates = values(call(part, 'GetBodies2', session.c('swSolidBody'), False))
            matches = [b for b in candidates if session.persistent_ref(model, b) == row.body_ref]
            if len(matches) != 1 or not call(matches[0], 'IsSheetMetal'):
                raise ApiError(row.label+': kaynak sac gövdesi artık doğrulanamıyor.')
            body = matches[0]
            actual = thickness(session, body, properties, info.source_unit)
            if row.thickness_mm is not None and (actual is None or not math.isclose(
                    actual, row.thickness_mm, rel_tol=1e-8, abs_tol=1e-6)):
                raise ApiError(row.label+': kaynağın sac kalınlığı değişmiş; eski kalınlıkla resim yayımlanmadı.')
            if row.material and material(body, info.source.configuration, properties) != row.material:
                raise ApiError(row.label+': kaynağın gövde malzemesi değişmiş; eski malzemeyle resim yayımlanmadı.')
    finally:
        part = body = feature = folder = model = None
        candidates = members = matches = ()
