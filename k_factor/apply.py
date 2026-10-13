"""Aktif montajın referans konfigürasyonlarına K/R önizleme ve uygulama.

COM nesneleri yalnızca çalışan iş parçacığında alınır. K/R dışında malzeme,
kalınlık veya unsur bazındaki özel büküm tanımları değiştirilmez.
"""

from dataclasses import dataclass, replace
import math

from dxf_dwg import exporter as sw
from k_factor.rules import ManualAssignment, ThicknessMismatch, calculate, material_by_key, number
from solidworks.connection import connect_to_solidworks

pythoncom, win32com = sw.pythoncom, sw.win32com
_value, _key = sw._value, sw._part_key
ALREADY_OPEN = 128  # swFileLoadWarning_e.swFileLoadWarning_AlreadyOpen
NEEDS_REBUILD = 2  # swActivateDocError_e.swDocNeedsRebuildWarning
TEMPLATE_SHEET = "TemplateSheetMetal"
CONVERT_SOLID = "SolidToSheetMetal"  # IFeature.GetTypeName2; not the display name.
MISSING_MEMBER = {-2147352573, -2147352570}  # DISP_E_MEMBERNOTFOUND / UNKNOWNNAME


def _read(obj, member):
    """Read a zero-argument COM member without invoking returned dispatch objects."""
    try:
        return _value(obj, member)
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


def _optional_read(obj, member):
    """Missing discovery APIs allow an alternate path; execution errors do not."""
    try:
        return _value(obj, member)
    except AttributeError:
        return None
    except Exception as error:
        if getattr(error, "hresult", None) in MISSING_MEMBER:
            return None
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


def _feature_kind(feature):
    kind = _read(feature, "GetTypeName2")
    # The documented exception for an Instant3D feature wrapper.
    return _read(feature, "GetTypeName") if kind == "ICE" else kind


def _suppressed(feature):
    empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
    value = _call(feature, "IsSuppressed2", 1, empty)
    if value is None:
        raise RuntimeError(f"Unsurun konfigürasyon durumu okunamadı: {_read(feature, 'Name')}")
    return sw._success(value)


def _write(obj, member, value):
    try:
        setattr(obj, member, value)
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member} yazımı: {error}") from error


def _call(obj, member, *args):
    try:
        return getattr(obj, member)(*args)
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


def _call_byref(obj, member, *args):
    # DumbDispatch on SldWorks does not propagate to returned definitions or
    # documents. Type-aware child wrappers infer their own output arguments
    # and return tuples instead of updating our explicit VARIANTs.
    if hasattr(obj, "_oleobj_"):
        obj = win32com.client.dynamic.DumbDispatch(obj)
    return _call(obj, member, *args)


def _out(kind):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | kind, 0 if kind == pythoncom.VT_I4 else False if kind == pythoncom.VT_BOOL else "")


def _activate_document(app, name):
    """Use the document pointer returned by activation, not a loaded proxy."""
    errors = _out(pythoncom.VT_I4)
    activated = _call_byref(app, "ActivateDoc3", name, False, 1, errors)
    active = _read(app, "ActiveDoc")
    if (activated is None or active is None or errors.value not in (0, NEEDS_REBUILD)
            or _key(sw._document_name(activated), "") != _key(name, "")
            or _key(sw._document_name(active), "") != _key(name, "")):
        raise RuntimeError(f"SolidWorks belgeyi etkinleştiremedi: {name}; hata kodu: {errors.value}")
    if errors.value == NEEDS_REBUILD and not _read(activated, "EditRebuild3"):
        raise RuntimeError(f"Etkinleştirilen belge yeniden oluşturulamadı: {name}")
    return activated


def _features(model, *, include_suppressed=False, kinds=None):
    first = _value(model, "FirstFeature")
    stack = [(first, False)] if first is not None else []
    # SheetMetal children can be exposed by the folder API even when normal
    # FirstFeature/subfeature traversal does not contain them (PowerSM).
    folder = _optional_read(_read(model, "FeatureManager"), "GetSheetMetalFolder")
    if folder is not None:
        sheets = _optional_read(folder, "GetSheetMetals")
        if sheets is not None:
            stack.extend((feature, False) for feature in sheets if feature is not None)
    visited, yielded = set(), set()
    while stack:
        feature, sub = stack.pop()
        name, kind = _read(feature, "Name"), _feature_kind(feature)
        context = name, kind, sub
        if context in visited:
            continue
        visited.add(context)
        next_feature = _value(feature, "GetNextSubFeature" if sub else "GetNextFeature")
        child = _value(feature, "GetFirstSubFeature")
        if next_feature is not None:
            stack.append((next_feature, sub))
        if child is not None:
            stack.append((child, True))
        identity = name, kind
        if identity in yielded or kinds is not None and kind not in kinds:
            continue
        # UI/history/body folders do not control K/R and need not support
        # configuration suppression. Their children are still traversed.
        if include_suppressed or kind.endswith("Folder") or not _suppressed(feature):
            yielded.add(identity)
            yield feature, kind


def _identity(feature):
    return _read(feature, "Name"), _feature_kind(feature)


def _parent(model, *, notes=None):
    """Resolve the unique SAC LEVHA parent by API/type, never a display name.

    A missing/null discovery API can use the folder or typed tree. A COM
    execution failure or conflicting result must not select an arbitrary child.
    """
    source = "GetTemplateSheetMetal"
    feature = _optional_read(_read(model, "Extension"), "GetTemplateSheetMetal")
    if feature is None:
        source = "GetSheetMetalFolder.GetFeature"
        folder = _optional_read(_read(model, "FeatureManager"), "GetSheetMetalFolder")
        if folder is not None:
            feature = _read(folder, "GetFeature")
            if feature is None:
                raise RuntimeError("SAC LEVHA klasörünün GetFeature sonucu boş.")
    if feature is not None:
        name, kind = _identity(feature)
        if kind != TEMPLATE_SHEET:
            raise RuntimeError(f"SAC LEVHA API'si beklenmeyen unsur döndürdü: {name} ({kind}).")
        if notes is not None:
            notes.append(f"Ana sac unsuru: {name} ({kind}) · Kaynak: {source}.")
        return feature, kind
    templates = list(_features(model, include_suppressed=True, kinds={TEMPLATE_SHEET}))
    if len(templates) > 1:
        raise RuntimeError("Birden fazla ana SAC LEVHA unsuru bulundu; hedef belirlenemedi.")
    if templates:
        feature, kind = templates[0]
        if notes is not None:
            notes.append(f"Ana sac unsuru: {_read(feature, 'Name')} ({kind}) · Kaynak: unsur ağacı.")
        return feature, kind
    active = [f for f, kind in _features(model, kinds={"SheetMetal"})]
    if len(active) != 1:
        raise RuntimeError("Eski sac yapısında tek bir aktif SheetMetal unsuru gerekir.")
    if notes is not None:
        notes.append(f"Sac unsuru: {_read(active[0], 'Name')} (SheetMetal) · Kaynak: eski sac yapısı.")
    return active[0], "SheetMetal"


def _tracked_features(model):
    # The API-selected template may not occur in FirstFeature traversal.
    parent, kind = _parent(model)
    result = [(parent, kind)]
    seen = {_identity(parent)}
    for feature, kind in _features(model, include_suppressed=True,
                                    kinds={TEMPLATE_SHEET, "SheetMetal", CONVERT_SOLID}):
        if kind in (TEMPLATE_SHEET, "SheetMetal", CONVERT_SOLID) and _identity(feature) not in seen:
            result.append((feature, kind))
            seen.add(_identity(feature))
    return result


def _body_feature(model, parent, kind):
    if kind == "SheetMetal":
        return parent
    children = [f for f, kind in _features(model, kinds={"SheetMetal"})]
    if len(children) != 1:
        raise RuntimeError("Tek sac gövdesi için bir aktif SheetMetal alt unsuru gerekir.")
    return children[0]


@dataclass(frozen=True)
class FeatureState:
    name: str
    thickness: float
    radius: float
    allowance_type: int
    k_factor: float
    bend_allowance: float
    bend_deduction: float
    bend_table: str
    kind: str = "SheetMetal"
    error_code: int = 0
    suppressed: bool = False
    overrides: tuple = ()


def _sheet_overrides(definition):
    values = []
    for parameter, label in ((0, "kalınlık/yarıçap"), (1, "büküm payı/K")):
        overridden = _out(pythoncom.VT_BOOL)
        error = _call_byref(definition, "GetOverrideDefaultParameter2", parameter, overridden)
        if error != 0:
            raise RuntimeError(f"{label} özel ayar durumu okunamadı; API hata kodu: {error}")
        values.append(bool(overridden.value))
    return tuple(values)


def _state(feature, kind="SheetMetal", *, inherited=False):
    definition = _read(feature, "GetDefinition")
    if definition is None:
        raise RuntimeError(f"{_read(feature, 'Name')} ({kind}) unsur tanımı okunamadı.")
    allowance = _read(definition, "GetCustomBendAllowance")
    if allowance is None:
        raise RuntimeError("Özel büküm payı API'si okunamadı.")
    allowance_type = int(_read(allowance, "Type"))
    # Inactive allowance modes are not needed for state/rollback and some
    # dispatch implementations do not expose their getters in the current mode.
    k = float(_read(allowance, "KFactor")) if allowance_type == 2 else 0.0
    ba = float(_read(allowance, "BendAllowance")) if allowance_type == 3 else 0.0
    bd = float(_read(allowance, "BendDeduction")) if allowance_type == 4 else 0.0
    if allowance_type not in (1, 2, 3, 4, 5):
        raise RuntimeError(f"Desteklenmeyen büküm payı türü: {allowance_type}")
    table_member = "BendCalculationTableFile" if allowance_type == 5 else "BendTableFile"
    table = str(_read(allowance, table_member) or "") if allowance_type in (1, 5) else ""
    thickness_member = "SheetThickness" if kind == CONVERT_SOLID else "Thickness"
    empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
    suppressed = _call(feature, "IsSuppressed2", 1, empty)
    if suppressed is None:
        raise RuntimeError(f"Unsurun konfigürasyon durumu okunamadı: {_read(feature, 'Name')}")
    return FeatureState(_read(feature, "Name"), float(_read(definition, thickness_member)),
                        float(_read(definition, "BendRadius")), allowance_type, k, ba, bd, table,
                        kind, int(_read(feature, "GetErrorCode")), sw._success(suppressed),
                        _sheet_overrides(definition) if inherited else ())


def _states(model):
    features = _tracked_features(model)
    modern = features[0][1] == TEMPLATE_SHEET
    return [_state(feature, kind, inherited=modern and kind == "SheetMetal")
            for feature, kind in features]


def _same(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if (a.name, a.kind, a.allowance_type, a.error_code, a.suppressed, a.overrides) != (b.name, b.kind, b.allowance_type, b.error_code, b.suppressed, b.overrides):
            return False
        if a.allowance_type in (1, 5) and a.bend_table != b.bend_table:
            return False
        active_field = {2: "k_factor", 3: "bend_allowance", 4: "bend_deduction"}.get(a.allowance_type)
        for field in ("thickness", "radius") + ((active_field,) if active_field else ()):
            if not math.isclose(getattr(a, field), getattr(b, field), rel_tol=1e-9, abs_tol=1e-10):
                return False
    return True


def _show_configuration(model, name):
    names = _value(model, "GetConfigurationNames") or ()
    name = next((item for item in names if str(item).lower() == str(name).lower()), name)
    if _value(model.ConfigurationManager.ActiveConfiguration, "Name") != name:
        if not model.ShowConfiguration2(name):
            raise RuntimeError(f"Konfigürasyon açılamadı: {name}")
    if _value(model.ConfigurationManager.ActiveConfiguration, "Name") != name:
        raise RuntimeError(f"SolidWorks farklı konfigürasyon döndürdü: {name}")


def _capture(model):
    original = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
    snapshots = {}
    try:
        names = _value(model, "GetConfigurationNames")
        if not names or original not in names:
            raise RuntimeError("Parçanın konfigürasyonları okunamadı.")
        for name in names:
            _show_configuration(model, name)
            snapshots[name] = _states(model)
    finally:
        _show_configuration(model, original)
    return snapshots


def _modify(model, feature, state):
    definition = _read(feature, "GetDefinition")
    if not _call(definition, "AccessSelections", model, None):
        raise RuntimeError("SheetMetal seçim erişimi alınamadı.")
    accessed = True
    try:
        allowance = _read(definition, "GetCustomBendAllowance")
        _write(allowance, "Type", state.allowance_type)
        member, value = {1: ("BendTableFile", state.bend_table), 2: ("KFactor", state.k_factor),
                         3: ("BendAllowance", state.bend_allowance), 4: ("BendDeduction", state.bend_deduction),
                         5: ("BendCalculationTableFile", state.bend_table)}[state.allowance_type]
        _write(allowance, member, value)
        # Active value/file setters can reset Type themselves. Finalize last.
        _write(allowance, "Type", state.allowance_type)
        _call(definition, "SetCustomBendAllowance", allowance)
        _write(definition, "BendRadius", state.radius)
        if not _call(feature, "ModifyDefinition", definition, model, None):
            raise RuntimeError("SolidWorks K/R değişikliğini kabul etmedi.")
        accessed = False  # ModifyDefinition ends selection access itself.
        if not _read(model, "EditRebuild3"):
            raise RuntimeError("K/R sonrasında parça yeniden oluşturulamadı.")
        if _read(feature, "GetErrorCode"):
            raise RuntimeError("SheetMetal unsuru değişiklik sonrası hata içeriyor.")
    finally:
        if accessed:
            _read(definition, "ReleaseSelectionAccess")


def _rollback(model, snapshots):
    original = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
    try:
        # Restore only changed states. All configurations are then checked,
        # including propagated changes caused by unconfigured dimensions.
        for name, before in snapshots.items():
            _show_configuration(model, name)
            try:
                unchanged = _same(before, _states(model))
            except Exception:
                # A failed rebuild can make a downstream definition unreadable.
                # Still attempt restoring the known parent values, then verify.
                unchanged = False
            if unchanged:
                continue
            for state in before:
                # ConvertSolid inherits these values. Do not initialize it or
                # alter its thickness/relief/override settings during rollback.
                if state.kind in (TEMPLATE_SHEET, "SheetMetal"):
                    # Reacquire after each parent modification/rebuild.
                    features = {_identity(f): f for f, kind in _tracked_features(model)}
                    feature = features[(state.name, state.kind)]
                    # Restoring the parent often restores its inherited child.
                    # Do not write that child unless it still differs.
                    try:
                        restored = _same([state], [_state(feature, state.kind, inherited=bool(state.overrides))])
                    except Exception:
                        restored = False
                    if not restored:
                        _modify(model, feature, state)
        for name, before in snapshots.items():
            _show_configuration(model, name)
            if not _same(before, _states(model)):
                raise RuntimeError(f"Geri alma doğrulanamadı: {name}. Parçayı kaydetmeyin.")
    finally:
        _show_configuration(model, original)


def _check_sheet_defaults(definition):
    used, filename = _out(pythoncom.VT_BOOL), _out(pythoncom.VT_BSTR)
    error = _call_byref(definition, "GetUseGaugeTable", used, filename)
    if error != 0:
        raise RuntimeError(f"Sac kalınlık tablosu durumu okunamadı; API hata kodu: {error}")
    if used.value:
        raise RuntimeError("Sac kalınlık tablosuna bağlı parça; önce SolidWorks'te tablo bağını kaldırın.")
    # This property is documented as valid only when GetUseGaugeTable is false.
    if bool(_read(definition, "UseMaterialSheetMetalParameters")):
        raise RuntimeError("Sac parametreleri malzemeye bağlı; önce SolidWorks'te bu bağı kaldırın.")


def _check_defaults(model, parent):
    _check_sheet_defaults(_read(parent, "GetDefinition"))
    for feature, kind in _features(model):
        if kind == TEMPLATE_SHEET or kind.endswith("Folder"):
            continue
        if kind == "SheetMetal":
            if _identity(feature) != _identity(parent):
                definition = _read(feature, "GetDefinition")
                _check_sheet_defaults(definition)
                if any(_sheet_overrides(definition)):
                    raise RuntimeError(f"{_read(feature, 'Name')}: özel kalınlık/yarıçap veya büküm payı/K parametresi kullanıyor; K/R uygulanmadı.")
            continue
        data = _value(feature, "GetDefinition")
        if kind == CONVERT_SOLID:
            name = _read(feature, "Name")
            if data is None:
                raise RuntimeError(f"{name}: Katıyı Saca Dönüştür unsur tanımı okunamadı.")
            # OverrideBendRadius concerns gauge settings during creation only.
            # Existing conversions override their parent through these flags.
            for attribute, label in (("OverrideDefaultSheetMetalParameters", "kalınlık/yarıçap"),
                                     ("OverrideDefaultBendAllowanceParameters", "büküm payı/K")):
                override = _read(data, attribute)
                if override is None:
                    raise RuntimeError(f"{name}: {attribute} durumu okunamadı; K/R uygulanmadı.")
                if bool(override):
                    raise RuntimeError(f"{name}: Katıyı Saca Dönüştür özel {label} parametresi kullanıyor "
                                       f"({attribute}). K/R uygulanmadı; SolidWorks'te dönüşüm unsurunu "
                                       "düzenleyip ilgili varsayılan parametreleri kullanın.")
        if data is None:
            continue
        # Swept flanges use UseDefaultRadius; other bend features expose
        # UseDefaultBendRadius. Both must inherit the sheet-metal radius.
        for attribute in ("UseDefaultBendRadius", "UseDefaultRadius", "UseDefaultBendAllowance"):
            if hasattr(data, attribute) and not bool(_value(data, attribute)):
                raise RuntimeError(f"{_value(feature, 'Name')} özel büküm parametresi kullanıyor; genel K/R tüm bükümlere geçmez. Önce varsayılan büküm parametrelerini etkinleştirin.")


def _check_inherited_sheet(model, expected, *, expected_names=None):
    names = []
    for feature, kind in _features(model, kinds={"SheetMetal"}):
        if kind != "SheetMetal" or _identity(feature) == (expected.name, expected.kind):
            continue
        actual = _state(feature, kind, inherited=True)
        target = replace(expected, name=actual.name, kind=kind, error_code=0, overrides=(False, False))
        if not _same([actual], [target]):
            raise RuntimeError(f"{actual.name}: SheetMetal alt unsuru ana SAC LEVHA K/R ve kalınlığıyla eşleşmedi.")
        names.append(actual.name)
    if expected_names is not None and tuple(names) != expected_names:
        raise RuntimeError("SheetMetal alt unsur listesi değişti; SAC LEVHA doğrulanamadı.")
    return tuple(names)


def _check_converted_values(model, expected, *, expected_names=None):
    names = []
    for feature, kind in _features(model, kinds={CONVERT_SOLID}):
        if kind != CONVERT_SOLID:
            continue
        actual = _state(feature, kind)
        target = replace(expected, name=actual.name, kind=kind, error_code=0)
        if not _same([actual], [target]):
            raise RuntimeError(f"{actual.name}: Katıyı Saca Dönüştür K/R, kalınlık veya unsur durumu "
                               "ana sac parametreleriyle eşleşmedi; dönüşüm doğrulanamadı.")
        names.append(actual.name)
    if expected_names is not None and tuple(names) != expected_names:
        raise RuntimeError("Katıyı Saca Dönüştür unsur listesi değişti; dönüşüm doğrulanamadı.")
    return tuple(names)


class NotSheetMetal(Exception):
    pass


def process_part(app, path, configuration, recipe, *, preview=False, save=False):
    """Tek dosya/konfigürasyon. Hatalı değişiklikleri bellekte geri al."""
    model = None
    original_config = None
    opened = changed = False
    visibility_changed = False
    snapshots = None
    notes, status, calculation = [], "error", None
    stage = "Parça açma"
    try:
        # These lookups may return an assembly-loaded document without its
        # own window. Use it for ownership/previous-state bookkeeping only;
        # parameter access uses the fresh pointer returned by ActivateDoc3.
        get_open = getattr(app, "GetOpenDocument", None)
        model = get_open(path) if get_open is not None else None
        if model is None:
            model = app.GetOpenDocumentByName(path)
        if model is None:
            errors, warnings = _out(pythoncom.VT_I4), _out(pythoncom.VT_I4)
            model = app.OpenDoc6(path, 1, 1, configuration, errors, warnings)
            # AlreadyOpen means this is a borrowed document. Closing it here
            # could close a part loaded by the user's assembly/session.
            opened = model is not None and not (warnings.value & ALREADY_OPEN)
            if model is None or errors.value:
                raise RuntimeError(f"Parça açılamadı; hata kodu: {errors.value}")
            if warnings.value & ALREADY_OPEN:
                notes.append("Açma bilgisi: belge zaten açık/yüklü (128); mevcut belge kullanıldı.")
            other_warnings = warnings.value & ~ALREADY_OPEN
            if other_warnings:
                notes.append(f"Açma uyarısı: {other_warnings} (toplam kod: {warnings.value})")
        stage = "Parça belgesi ve etkinleştirme"
        if _value(model, "GetType") != 1 or _key(_value(model, "GetPathName"), "") != _key(path, ""):
            raise RuntimeError("SolidWorks istenen parça yerine farklı belge döndürdü.")
        # Activation/configuration changes can themselves set the save flag.
        # Protect edits that existed before this operation, not our own switch.
        preexisting_changes = bool(_read(model, "GetSaveFlag")) if save and not preview else False
        original_config = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
        if not _value(model, "Visible"):
            model.Visible = True
            visibility_changed = True
        model = _activate_document(app, path)
        if _read(model, "GetType") != 1:
            raise RuntimeError("Etkinleştirilen belge bir parça değil; K/R uygulanmadı.")
        stage = "Konfigürasyon ve sac gövdeleri"
        _show_configuration(model, configuration)
        configuration = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
        part = sw._part_api(model)
        bodies = part.GetBodies2(0, False) or ()
        if not bodies or not any(_value(body, "IsSheetMetal") for body in bodies):
            raise NotSheetMetal("Sac metal değil.")
        if len(bodies) != 1:
            raise RuntimeError("Çok gövdeli parça desteklenmiyor; ayrı sac parçalar kullanın.")
        stage = "Sac unsuru ve kalınlığı"
        feature, parent_kind = _parent(model, notes=notes)
        body_feature = _body_feature(model, feature, parent_kind)
        notes.append(f"Gövde sac unsuru: {_read(body_feature, 'Name')} (SheetMetal).")
        # Single-body support makes this the unique body-level SheetMetal
        # definition, not the template's potentially different default thickness.
        # Nonmatching manual sheets stop before allowance/override API calls.
        calculation = calculate(float(_read(_read(body_feature, "GetDefinition"), "Thickness")) * 1000, recipe)
        stage = "Mevcut K/R ve büküm payı okuma"
        before = _state(feature, parent_kind)
        if before.error_code or before.suppressed:
            raise RuntimeError("SAC LEVHA unsuru bastırılmış veya zaten hata içeriyor; önce parçayı düzeltin.")
        stage = "Malzeme, sac kalınlık tablosu ve özel büküm kontrolleri"
        _check_defaults(model, feature)
        inherited_names = _check_inherited_sheet(model, before)
        stage = "Katıyı Saca Dönüştür parametre kontrolü"
        converted_names = _check_converted_values(model, before)
        if not preview:
            if preexisting_changes:
                raise RuntimeError("Parçada önceden kaydedilmemiş değişiklik var; önce SolidWorks'te kaydedin veya dosyaları kaydet seçeneğini kapatın.")
            stage = "Konfigürasyonların yedeğini alma"
            snapshots = _capture(model)
            target = replace(before, radius=calculation.radius_mm / 1000,
                             allowance_type=2, k_factor=calculation.k_factor)
            changed = True  # COM setters can mutate even if ModifyDefinition fails.
            stage = "K/R yazma ve yeniden oluşturma"
            # Configuration capture invalidates previous COM definitions and
            # can invalidate feature wrappers. Resolve again before mutation.
            feature, kind = _parent(model)
            if _identity(feature) != (before.name, before.kind):
                raise RuntimeError("SAC LEVHA hedefi konfigürasyon yedeğinden sonra değişti.")
            _modify(model, feature, target)
            stage = "K/R geri okuma ve konfigürasyon doğrulaması"
            feature, kind = _parent(model)
            after = _state(feature, kind)
            if not _same([target], [after]):
                raise RuntimeError("K/R yazma sonrası değerler geri okumada eşleşmedi.")
            for name, untouched in snapshots.items():
                if name != configuration:
                    _show_configuration(model, name)
                    if not _same(untouched, _states(model)):
                        raise RuntimeError(f"Değişiklik başka konfigürasyona yayıldı ({name}); işlem geri alınıyor. Parametreleri konfigürasyona özel tanımlayın.")
            _show_configuration(model, configuration)
            # Fresh reads after the configuration round-trip, including parent.
            feature, kind = _parent(model)
            after = _state(feature, kind)
            if not _same([target], [after]):
                raise RuntimeError("SAC LEVHA K/R konfigürasyon dönüşünde eşleşmedi.")
            _check_defaults(model, feature)
            _check_inherited_sheet(model, target, expected_names=inherited_names)
            _check_converted_values(model, target, expected_names=converted_names)
            if converted_names:
                notes.append(f"Katıyı Saca Dönüştür: {len(converted_names)} unsurda K/R ve kalınlık geri okumayla doğrulandı.")
            if save:
                stage = "Parça dosyasını kaydetme"
                errors, warnings = _out(pythoncom.VT_I4), _out(pythoncom.VT_I4)
                if not _call_byref(model, "Save3", 1, errors, warnings) or errors.value:
                    raise RuntimeError(f"Parça kaydedilemedi; hata kodu: {errors.value}. Dosyanın durumunu SolidWorks'te kontrol edin.")
                notes.append("Parça dosyası kaydedildi.")
                if warnings.value:
                    notes.append(f"Kaydetme uyarısı: {warnings.value}")
            else:
                notes.append("Bellekte uygulandı; dosyaya kaydedilmedi. SolidWorks'te kontrol edip kaydedin.")
            previous = f"K={before.k_factor:.12g}" if before.allowance_type == 2 else f"büküm payı tipi={before.allowance_type}"
            notes.append(f"SAC LEVHA: {after.name} ({after.kind}) · Konfigürasyon: {configuration} · "
                         f"Önceki {previous}, R={before.radius*1000:.12g} mm → "
                         f"Doğrulanan K={after.k_factor:.12g}, R={after.radius*1000:.12g} mm · "
                         f"{len(inherited_names)} SheetMetal alt unsuru doğrulandı.")
            notes.insert(0, f"K/R uygulandı ve geri okumayla doğrulandı: K={after.k_factor:.12g}, "
                         f"R={after.radius*1000:.12g} mm, t={after.thickness*1000:.12g} mm.")
        else:
            current = f"K={before.k_factor:.4f}" if before.allowance_type == 2 else f"büküm payı tipi={before.allowance_type}"
            notes.insert(0, f"Önizleme; K/R uygulanmadı. Mevcut {current}, R={before.radius*1000:.3f} mm.")
        if isinstance(recipe, ManualAssignment):
            notes.append(f"{'Manuel atama hedefi' if preview else 'Manuel atama'} · K={calculation.k_factor:.12g} · R={calculation.radius_mm:.12g} mm · t={calculation.thickness_mm:.12g} mm")
        else:
            notes.append(f"K={calculation.k_factor:.4f} · R={calculation.radius_mm:.3f} mm · t={calculation.thickness_mm:g} mm · V={calculation.die_opening_mm:g} mm · BA({calculation.angle_deg:g}°)={calculation.ba_mm:.5f} mm")
        notes.extend(calculation.notes)
        status = "success"
    except (NotSheetMetal, ThicknessMismatch) as error:
        status = "skipped"
        notes.append(str(error))
    except Exception as error:
        notes.append(f"{stage}: {error}")
        if changed and snapshots is not None:
            try:
                _rollback(model, snapshots)
                notes.append("Önceki K/R değerleri geri yüklendi ve kontrol edildi.")
                changed = False
            except Exception as rollback_error:
                notes.append(f"GERİ ALMA HATASI: {rollback_error}")
    finally:
        if model is not None and original_config is not None:
            try:
                _show_configuration(model, original_config)
            except Exception as error:
                status = "error"
                notes.append(f"Önceki konfigürasyon geri açılamadı: {error}")
        if opened and model is not None and (not changed or save and status == "success"):
            try:
                app.CloseDoc(_value(model, "GetTitle"))
            except Exception as error:
                status = "error"
                notes.append(f"Açılan parça kapatılamadı: {error}")
        elif visibility_changed and model is not None and (not changed or not opened):
            try:
                model.Visible = False
            except Exception as error:
                status = "error"
                notes.append(f"Belge görünürlüğü geri yüklenemedi: {error}")
    return status, "; ".join(notes), calculation


def update_assembly(recipe, events, stop_event=None, *, preview=False, save=False,
                    expected_scope=None):
    """Alt montajlar dahil, her dosya+konfigürasyona bir kez uygula."""
    summary = dict(state="completed", total=0, processed=0, succeeded=0,
                   skipped=0, failed=0, error="", preview=bool(preview))
    initialized, app, assembly_name = False, None, None
    try:
        recipe.validate()
        if stop_event is not None and stop_event.is_set():
            summary["state"] = "cancelled"
            return
        if pythoncom is None or win32com is None:
            raise RuntimeError("Montaja K/R aktarımı Windows, pywin32 ve açık SolidWorks gerektirir.")
        pythoncom.CoInitialize()
        initialized = True
        app = connect_to_solidworks()
        if hasattr(app, "_oleobj_"):
            app = win32com.client.dynamic.DumbDispatch(app)
        events.put(("phase", "Aktif montaj ve alt montajlar okunuyor…"))
        references = {}
        counts, assembly_name, assembly_configuration = sw.assembly_quantities(
            app, stop_event, references=references)
        # A queued apply must still target the assembly/configuration and
        # physical part references that were checked by its preview worker.
        # Keep only immutable values; COM objects cannot cross worker threads.
        scope = (_key(assembly_name, assembly_configuration), tuple(sorted(counts.items())))
        if expected_scope is not None and scope != expected_scope:
            raise RuntimeError(
                "Kontrolden sonra montaj, konfigürasyon veya parça listesi değişti. "
                "K/R uygulanmadı. Doğru montajı etkinleştirip yeniden tarayın.")
        summary['scope'] = scope
        # Comparison keys may change Unicode characters (İ -> i + dot).
        # They are suitable for counting, never for opening a physical file.
        records = [(references[key], quantity) for key, quantity in sorted(counts.items())]
        sources = [f"{path} [{configuration}]" for (path, configuration), _ in records]
        summary["total"] = len(records)
        events.put(("files", sources))
        events.put(("total", len(records)))
        if isinstance(recipe, ManualAssignment):
            scope = (f"Manuel K/R · Hedef kalınlık: {number(recipe.thickness_mm, 'Kalınlık'):.12g} mm"
                     f" · K={number(recipe.k_factor, 'K', zero=True):.12g}"
                     f" · R={number(recipe.radius_mm, 'R'):.12g} mm")
        else:
            scope = f"Malzeme varsayımı: {material_by_key(recipe.material).label} · Havada büküm"
        events.put(("log", f"Montaj: {assembly_name} [{assembly_configuration}] · {scope} · {'Önizleme' if preview else 'K/R uygulama'}"))
        if not records:
            summary["state"] = "empty"
        for index, (((path, configuration), quantity), source) in enumerate(zip(records, sources), 1):
            if stop_event is not None and stop_event.is_set():
                summary["state"] = "cancelled"
                break
            events.put(("current", source))
            status, detail, calculation = process_part(app, path, configuration, recipe,
                                                        preview=preview, save=save)
            summary["processed"] += 1
            summary[{"success": "succeeded", "skipped": "skipped", "error": "failed"}[status]] += 1
            result = dict(source=source, output=path, status=status,
                          detail=f"{quantity} adet · {detail}", configuration=configuration,
                          quantity=quantity, preview=preview)
            if calculation:
                result.update(k_factor=calculation.k_factor, radius_mm=calculation.radius_mm,
                              ba_mm=calculation.ba_mm, thickness_mm=calculation.thickness_mm)
            events.put(("result", result))
            events.put(("counts", summary.copy()))
            events.put(("progress", (index, len(records))))
    except sw.CountCancelled:
        summary["state"] = "cancelled"
    except Exception as error:
        summary.update(state="error", error=str(error))
        events.put(("log", str(error)))
    finally:
        if app is not None and assembly_name:
            try:
                _activate_document(app, assembly_name)
            except Exception as error:
                summary.update(state="error", error=str(error))
        if initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception as error:
                summary.update(state="error", error=f"COM kapanışı: {error}")
        events.put(("done", summary.copy()))
