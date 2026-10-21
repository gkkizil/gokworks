"""Aktif montajın referans konfigürasyonlarına K/R önizleme ve uygulama.

COM nesneleri yalnızca çalışan iş parçacığında alınır. Manuel montaj ataması
doğrudan ana Sac-Levha K/R parametrelerini değiştirir. Eski hesap/inheritance
yardımcıları geriye uyumluluk için ayrı yolda korunur.
"""

from dataclasses import dataclass, replace
import math

from modules.dxf_dwg import exporter as sw
from modules.k_factor.rules import AssignmentTable, ManualAssignment, ThicknessMismatch, calculate, material_by_key, number
from modules.k_factor.sheetmetal_parameters import ParameterEdit, NoSheetMetal
from solidworks.connection import connect_to_solidworks

pythoncom, win32com = sw.pythoncom, sw.win32com
_value, _key = sw._value, sw._part_key
ALREADY_OPEN = 128  # swFileLoadWarning_e.swFileLoadWarning_AlreadyOpen
NEEDS_REBUILD = 2  # swActivateDocError_e.swDocNeedsRebuildWarning
NOT_ENABLED_ON_TEMPLATE = 2  # swSheetMetalModifierError_NotEnabledOnTemplate
TEMPLATE_SHEET = "TemplateSheetMetal"
CONVERT_SOLID = "SolidToSheetMetal"  # IFeature.GetTypeName2; not the display name.
CONVERT_FLAGS = ("OverrideDefaultSheetMetalParameters", "OverrideDefaultBendAllowanceParameters")
MISSING_MEMBER = {-2147352573, -2147352570}  # DISP_E_MEMBERNOTFOUND / UNKNOWNNAME
BEND_DEFAULTS = {
    kind: ("UseDefaultBendRadius", "UseDefaultBendAllowance")
    for kind in ("EdgeFlange", "SketchBend", "SM3dBend", "OneBend", "ToroidalBend", "SMMiteredFlange", "Jog",
                 "Bends", "ProcessBends", "FlattenBends")
}
BEND_DEFAULTS.update(Hem=("UseDefaultBendAllowance",),
                     SweepFlange=("UseDefaultRadius", "UseDefaultBendAllowance"),
                     SweptFlange=("UseDefaultRadius", "UseDefaultBendAllowance"))


COM_METHODS = {"GetTemplateSheetMetal", "GetSheetMetalFolder", "GetSheetMetals",
               "GetFeature", "GetDefinition", "GetCustomBendAllowance", "GetFeatures"}


def _method_dispatch(obj, member):
    if member in COM_METHODS and hasattr(obj, "_oleobj_"):
        obj = win32com.client.dynamic.DumbDispatch(obj)
        obj._FlagAsMethod(member)
    return obj


def _read(obj, member):
    """Read a zero-argument COM member without invoking returned dispatch objects."""
    try:
        return _value(_method_dispatch(obj, member), member)
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


def _optional_read(obj, member):
    """Missing discovery APIs allow an alternate path; execution errors do not."""
    try:
        return _value(_method_dispatch(obj, member), member)
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
        obj._FlagAsMethod(member)
    return _call(obj, member, *args)


def _edit_call(obj, member, *args):
    """Edit a part feature with an explicit null IComponent2 dispatch.

    pywin32 converts bare None to VT_NULL. SolidWorks requires VT_DISPATCH
    for the absent Component in part context, including rollback writes.
    Late binding avoids a child wrapper converting our explicit VARIANT again.
    """
    if hasattr(obj, "_oleobj_") and args[-1] is None:
        args = (*args[:-1], win32com.client.VARIANT(pythoncom.VT_DISPATCH, None))
    return _call_byref(obj, member, *args)


def _out(kind):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | kind, 0 if kind == pythoncom.VT_I4 else False if kind == pythoncom.VT_BOOL else "")


def _solid_bodies(model):
    """K/R needs IPartDoc.GetBodies2; DXF export APIs are not a prerequisite."""
    try:
        return _call(model, "GetBodies2", 0, False) or ()
    except RuntimeError as error:
        cause = error.__cause__
        if getattr(cause, "hresult", None) in (-2147352561, -2147352562, -2147352571):
            return _call_byref(model, "GetBodies2", 0, False) or ()
        if not isinstance(cause, AttributeError) and getattr(cause, "hresult", None) not in MISSING_MEMBER:
            raise
    try:
        part = win32com.client.CastTo(model, "IPartDoc")
        return _call_byref(part, "GetBodies2", 0, False) or ()
    except Exception as error:
        raise RuntimeError(f"SolidWorks parça gövdeleri okunamadı (IPartDoc.GetBodies2): {error}") from error


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


def _converted_overrides(definition):
    if definition is None:
        raise RuntimeError("Katıyı Saca Dönüştür unsur tanımı okunamadı.")
    values = tuple(_read(definition, member) for member in CONVERT_FLAGS)
    if any(value is None for value in values):
        raise RuntimeError("Katıyı Saca Dönüştür varsayılan parametre durumu okunamadı: " + ", ".join(CONVERT_FLAGS))
    return tuple(bool(value) for value in values)


def _modify_converted(model, feature, flags):
    definition = _read(feature, "GetDefinition")
    if not _edit_call(definition, "AccessSelections", model, None):
        raise RuntimeError("Katıyı Saca Dönüştür seçim erişimi alınamadı.")
    accessed = True
    try:
        for member, value in zip(CONVERT_FLAGS, flags):
            _write(definition, member, value)
        if not _edit_call(feature, "ModifyDefinition", definition, model, None):
            raise RuntimeError("Katıyı Saca Dönüştür varsayılan parametreleri kabul edilmedi.")
        accessed = False
        if not _read(model, "EditRebuild3"):
            raise RuntimeError("Katıyı Saca Dönüştür yeniden oluşturulamadı.")
        if _converted_overrides(_read(feature, "GetDefinition")) != flags:
            raise RuntimeError("Katıyı Saca Dönüştür varsayılan parametreleri geri okumada eşleşmedi.")
    finally:
        if accessed:
            _read(definition, "ReleaseSelectionAccess")


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


def _body_feature(model, parent, kind, *, multiple=False):
    if kind == "SheetMetal":
        return parent
    children = [f for f, kind in _features(model, kinds={"SheetMetal"})]
    if not children:
        converted = [f for f, _ in _features(model, kinds={CONVERT_SOLID})]
        if len(converted) == 1:
            return converted[0]
    if multiple and children:
        thicknesses = [float(_read(_read(child, "GetDefinition"), "Thickness")) for child in children]
        if not all(math.isclose(t, thicknesses[0], rel_tol=0, abs_tol=1e-10) for t in thicknesses):
            raise RuntimeError("Sac gövdeleri farklı kalınlıkta; ortak Sac-Levha ayarıyla K/R atanmadı. "
                               "Kalınlıklar: " + ", ".join(f"{t*1000:g} mm" for t in thicknesses))
        # Every body's ownership is checked separately. These definitions
        # share one thickness and therefore the same whole-part K/R target.
        return children[0]
    if len(children) != 1:
        raise RuntimeError("Tek sac gövdesi için bir aktif SheetMetal alt unsuru gerekir.")
    return children[0]


def _body_inventory(model):
    bodies = tuple(_solid_bodies(model))
    flags = tuple(_read(body, "IsSheetMetal") for body in bodies)
    if any(value is None for value in flags):
        raise RuntimeError("Gövdenin sac metal durumu okunamadı; K/R atanmadı.")
    return bodies, tuple(bool(value) for value in flags)


def _check_body_coverage(model, bodies, flags, *, expected=None):
    signature = len(bodies), sum(flags)
    if expected is not None and signature != expected:
        raise RuntimeError("K/R sonrasında katı/sac gövde sayısı değişti; işlem geri alınıyor.")
    controllers = {_identity(feature) for feature, _ in
                   _features(model, kinds={"SheetMetal", CONVERT_SOLID})}
    for index, (body, sheet) in enumerate(zip(bodies, flags), 1):
        if not sheet:
            continue
        features = _read(body, "GetFeatures")
        if not features or not any(_identity(feature) in controllers for feature in features if feature is not None):
            raise RuntimeError(f"{index}. sac gövdesinin SheetMetal/dönüştürme unsuruyla bağı doğrulanamadı; K/R atanmadı.")
    return signature


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


@dataclass(frozen=True)
class BendState:
    name: str
    kind: str
    defaults: tuple
    radius: float | None
    allowance: tuple | None
    gauge: bool
    error_code: int
    suppressed: bool


def _bend_state(feature, kind):
    """Only read custom values when their API mode is valid; retain for undo."""
    data = _read(feature, "GetDefinition")
    if data is None:
        raise RuntimeError(f"{_read(feature, 'Name')}: büküm tanımı okunamadı.")
    defaults = []
    for member in BEND_DEFAULTS[kind]:
        value = _read(data, member)
        if value is None:
            raise RuntimeError(f"{_read(feature, 'Name')}: {member} okunamadı.")
        defaults.append((member, bool(value)))
    flags = dict(defaults)
    custom_radius = any(not value for member, value in defaults if member != "UseDefaultBendAllowance")
    radius = float(_read(data, "BendRadius")) if custom_radius else None
    allowance = None
    if flags.get("UseDefaultBendAllowance") is False:
        bend = _read(data, "GetCustomBendAllowance")
        if bend is None:
            raise RuntimeError(f"{_read(feature, 'Name')}: özel büküm payı okunamadı.")
        mode = int(_read(bend, "Type"))
        member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance",
                  4: "BendDeduction", 5: "BendCalculationTableFile"}.get(mode)
        if member is None:
            raise RuntimeError(f"Desteklenmeyen büküm payı türü: {mode}")
        value = _read(bend, member)
        allowance = (mode, str(value or "") if mode in (1, 5) else float(value))
    return BendState(_read(feature, "Name"), kind, tuple(defaults), radius, allowance,
                     bool(_optional_read(data, "UseGaugeTable")),
                     int(_read(feature, "GetErrorCode")), _suppressed(feature))


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
                        _converted_overrides(definition) if kind == CONVERT_SOLID else
                        _sheet_overrides(definition) if inherited else ())


def _states(model):
    features = _tracked_features(model)
    modern = features[0][1] == TEMPLATE_SHEET
    result = [_state(feature, kind, inherited=modern and kind == "SheetMetal")
              for feature, kind in features]
    result.extend(_bend_state(feature, kind) for feature, kind in
                  _features(model, include_suppressed=True, kinds=BEND_DEFAULTS))
    return result


def _same(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if type(a) is not type(b):
            return False
        if isinstance(a, BendState):
            if (a.name, a.kind, a.defaults, a.gauge, a.error_code, a.suppressed) != (
                    b.name, b.kind, b.defaults, b.gauge, b.error_code, b.suppressed):
                return False
            if a.radius is None or b.radius is None:
                if a.radius != b.radius:
                    return False
            elif not math.isclose(a.radius, b.radius, rel_tol=1e-9, abs_tol=1e-10):
                return False
            if a.allowance is None or b.allowance is None:
                if a.allowance != b.allowance:
                    return False
            elif a.allowance[0] != b.allowance[0]:
                return False
            elif a.allowance[0] in (1, 5):
                if a.allowance[1] != b.allowance[1]:
                    return False
            elif not math.isclose(a.allowance[1], b.allowance[1], rel_tol=1e-9, abs_tol=1e-10):
                return False
            continue
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


def _fresh_feature(model, name, kind):
    parent, _ = _parent(model)
    if _identity(parent) == (name, kind):
        return parent
    for feature, _ in _features(model, include_suppressed=True, kinds={kind}):
        if _identity(feature) == (name, kind):
            return feature
    raise RuntimeError(f"Unsur yeniden bulunamadı: {name} ({kind}).")


def _radius_dimension(feature):
    """PowerSM's radius route, restricted to this feature's own radial measure.

    Display traversal includes subfeatures; their dimensions and diameters must
    not be mistaken for the parent's radius. Hidden/absent dimensions use the
    documented BendRadius definition setter instead.
    """
    display = _optional_read(feature, "GetFirstDisplayDimension")
    dimensions = {}
    for _ in range(256):
        if display is None:
            break
        dimension_type = _optional_read(display, "Type2")
        if dimension_type is None:
            dimension_type = _read(display, "GetType")
        if dimension_type == 5:  # swDimensionType_e.swRadialDimension
            dimension = _call(display, "GetDimension2", 0)
            if dimension is None:
                raise RuntimeError("Yarıçap ölçüsü okunamadı.")
            owner = _read(dimension, "GetFeatureOwner")
            if owner is not None and _identity(owner) == _identity(feature):
                dimensions[str(_read(dimension, "FullName"))] = dimension
        display = _call(feature, "GetNextDisplayDimension", display)
    else:
        raise RuntimeError("Yarıçap ölçü listesi tamamlanamadı.")
    if len(dimensions) > 1:
        raise RuntimeError("Ana sac unsurunda birden fazla yarıçap ölçüsü var; R hedefi belirlenemedi.")
    return next(iter(dimensions.values()), None)


def _set_allowance(definition, mode, value):
    allowance = _read(definition, "GetCustomBendAllowance")
    if allowance is None:
        raise RuntimeError("Özel büküm payı API'si okunamadı.")
    _write(allowance, "Type", mode)
    member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance",
              4: "BendDeduction", 5: "BendCalculationTableFile"}[mode]
    _write(allowance, member, value)
    # Active value/file setters can reset Type themselves. Finalize last.
    _write(allowance, "Type", mode)
    _call(definition, "SetCustomBendAllowance", allowance)


def _modify(model, feature, state, *, inherit_only=False):
    dimension = _radius_dimension(feature) if not state.overrides else None
    definition = _read(feature, "GetDefinition")
    if not _edit_call(definition, "AccessSelections", model, None):
        raise RuntimeError("SheetMetal seçim erişimi alınamadı.")
    accessed = True
    try:
        if not inherit_only and not math.isclose(float(_read(definition, "Thickness")),
                                                 state.thickness, rel_tol=0, abs_tol=1e-10):
            # A converted body can override an inactive template thickness.
            # Align that default before inheritance, keeping the real sheet's
            # thickness unchanged. This also restores the default on rollback.
            _write(definition, "Thickness", state.thickness)
        current_overrides = _sheet_overrides(definition) if state.overrides else ()
        for parameter, overridden in enumerate(state.overrides):
            if current_overrides[parameter] == overridden:
                continue
            error = _call(definition, "SetOverrideDefaultParameter2", parameter, overridden)
            if error != 0:
                raise RuntimeError(f"Sac özel ayarı yazılamadı; API hata kodu: {error}")
        if not inherit_only:
            value = {1: state.bend_table, 2: state.k_factor, 3: state.bend_allowance,
                     4: state.bend_deduction, 5: state.bend_table}[state.allowance_type]
            _set_allowance(definition, state.allowance_type, value)
        if dimension is None and not inherit_only:
            _write(definition, "BendRadius", state.radius)
        if not _edit_call(feature, "ModifyDefinition", definition, model, None):
            raise RuntimeError("SolidWorks K/R değişikliğini kabul etmedi.")
        accessed = False  # ModifyDefinition ends selection access itself.
        if not _read(model, "EditRebuild3"):
            raise RuntimeError("K/R sonrasında parça yeniden oluşturulamadı.")
        if dimension is not None:
            # Reacquire after ModifyDefinition/rebuild. Use this configuration,
            # instead of inheriting PowerSM's SetSystemValue2(..., 0) setting.
            feature = _fresh_feature(model, state.name, state.kind)
            dimension = _radius_dimension(feature)
            if dimension is None:
                raise RuntimeError("K ataması sonrasında yarıçap ölçüsü kayboldu.")
            empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
            error = _call(dimension, "SetSystemValue3", state.radius, 1, empty)
            if error != 0:
                raise RuntimeError(f"Yarıçap ölçüsü yazılamadı; API hata kodu: {error}")
            if not _read(model, "EditRebuild3"):
                raise RuntimeError("R ataması sonrasında parça yeniden oluşturulamadı.")
        if _read(feature, "GetErrorCode"):
            raise RuntimeError("SheetMetal unsuru değişiklik sonrası hata içeriyor.")
        return "Yarıçap ölçüsü · yalnız hedef konfigürasyon" if dimension is not None else "Sac unsur tanımı"
    finally:
        if accessed:
            _read(definition, "ReleaseSelectionAccess")


def _modify_bend(model, feature, state):
    definition = _read(feature, "GetDefinition")
    if not _edit_call(definition, "AccessSelections", model, None):
        raise RuntimeError(f"{state.name}: büküm seçim erişimi alınamadı.")
    accessed = True
    try:
        for member, value in state.defaults:
            _write(definition, member, value)
        if state.radius is not None:
            _write(definition, "BendRadius", state.radius)
        if state.allowance is not None:
            _set_allowance(definition, *state.allowance)
        if not _edit_call(feature, "ModifyDefinition", definition, model, None):
            raise RuntimeError(f"{state.name}: büküm ayarları kabul edilmedi.")
        accessed = False
        if not _read(model, "EditRebuild3"):
            raise RuntimeError(f"{state.name}: büküm yeniden oluşturulamadı.")
        actual = _bend_state(_fresh_feature(model, state.name, state.kind), state.kind)
        if not _same([state], [actual]):
            raise RuntimeError(f"{state.name}: büküm ayarları geri okumada eşleşmedi.")
    finally:
        if accessed:
            _read(definition, "ReleaseSelectionAccess")


def _normalize_bends(model):
    """PowerSM's inherit mode, changing K/R flags only, with verified undo."""
    updated = []
    for state in _states(model):
        if state.suppressed:
            continue
        if isinstance(state, FeatureState) and state.kind == "SheetMetal" and state.overrides:
            if any(state.overrides):
                feature = _fresh_feature(model, state.name, state.kind)
                _modify(model, feature, replace(state, overrides=(False, False)), inherit_only=True)
                updated.append(state.name)
        elif isinstance(state, FeatureState) and state.kind == CONVERT_SOLID and any(state.overrides):
            _modify_converted(model, _fresh_feature(model, state.name, state.kind), (False, False))
            updated.append(state.name)
        elif isinstance(state, BendState) and not all(value for _, value in state.defaults):
            feature = _fresh_feature(model, state.name, state.kind)
            target = replace(state, defaults=tuple((member, True) for member, _ in state.defaults),
                             radius=None, allowance=None)
            _modify_bend(model, feature, target)
            updated.append(state.name)
    return tuple(updated)


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
                if isinstance(state, BendState):
                    feature = _fresh_feature(model, state.name, state.kind)
                    if not _same([state], [_bend_state(feature, state.kind)]):
                        _modify_bend(model, feature, state)
                    continue
                if state.kind == CONVERT_SOLID:
                    feature = _fresh_feature(model, state.name, state.kind)
                    if _converted_overrides(_read(feature, "GetDefinition")) != state.overrides:
                        _modify_converted(model, feature, state.overrides)
                    continue
                # Restore parent K/R before verifying downstream definitions.
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


def _check_sheet_defaults(definition, *, allow_unavailable=False, source=""):
    used, filename = _out(pythoncom.VT_BOOL), _out(pythoncom.VT_BSTR)
    error = _call_byref(definition, "GetUseGaugeTable", used, filename)
    if allow_unavailable and error == NOT_ENABLED_ON_TEMPLATE:
        # Never consume out arguments on an unsuccessful call. The caller
        # must establish a verified controlling source; code 2 alone does not
        # prove that gauge/material links are disabled.
        return False
    if error != 0:
        raise RuntimeError(f"{source + ': ' if source else ''}Sac kalınlık tablosu durumu okunamadı; "
                           f"GetUseGaugeTable API hata kodu: {error}")
    if used.value:
        raise RuntimeError("Sac kalınlık tablosuna bağlı parça; önce SolidWorks'te tablo bağını kaldırın.")
    # This property is documented as valid only when GetUseGaugeTable is false.
    if bool(_read(definition, "UseMaterialSheetMetalParameters")):
        raise RuntimeError("Sac parametreleri malzemeye bağlı; önce SolidWorks'te bu bağı kaldırın.")
    return True


def _check_defaults(model, parent, *, normalize=False, notes=None):
    parent_kind = _feature_kind(parent)
    parent_label = f"{_read(parent, 'Name')} ({parent_kind})"
    parent_checked = _check_sheet_defaults(_read(parent, "GetDefinition"),
                                          allow_unavailable=parent_kind == TEMPLATE_SHEET,
                                          source=f"Ana sac unsuru {parent_label}")
    body_checked = False
    for feature, kind in _features(model):
        if kind == TEMPLATE_SHEET or kind.endswith("Folder"):
            continue
        if kind == "SheetMetal":
            if _identity(feature) != _identity(parent):
                definition = _read(feature, "GetDefinition")
                overrides = _sheet_overrides(definition)
                # A body whose K/R comes from a verified template need not
                # expose this template-level gauge API itself. Still consume
                # and enforce any successful body gauge/material result.
                inherited = parent_kind == TEMPLATE_SHEET and parent_checked and not any(overrides)
                checked = _check_sheet_defaults(definition, allow_unavailable=inherited,
                            source=f"Gövde sac unsuru {_read(feature, 'Name')} ({kind})")
                body_checked = body_checked or checked
                if not checked and notes is not None:
                    notes.append(f"{_read(feature, 'Name')}: tablo API'si kod 2; özel K/R ayarı yok, "
                                 f"tablo/malzeme durumu ana sac unsurundan doğrulandı ({parent_label}).")
                if any(overrides) and not normalize:
                    raise RuntimeError(f"{_read(feature, 'Name')}: özel kalınlık/yarıçap veya büküm payı/K parametresi kullanıyor; K/R uygulanmadı.")
            continue
        if kind == CONVERT_SOLID:
            flags = _converted_overrides(_read(feature, "GetDefinition"))
            if any(flags) and not normalize:
                raise RuntimeError(f"{_read(feature, 'Name')}: Katıyı Saca Dönüştür özel parametre kullanıyor ({', '.join(CONVERT_FLAGS)}); tüm bükümlere uygula seçeneğini açın.")
            continue
        if kind not in BEND_DEFAULTS:
            continue
        state = _bend_state(feature, kind)
        if state.error_code:
            raise RuntimeError(f"{state.name}: büküm zaten hata içeriyor; önce parçayı düzeltin.")
        if normalize:
            if state.gauge and not all(value for _, value in state.defaults):
                raise RuntimeError(f"{state.name}: özel büküm ayarı sac kalınlık tablosuna bağlı; K/R uygulanmadı.")
        elif not all(value for _, value in state.defaults):
            raise RuntimeError(f"{state.name} özel büküm parametresi kullanıyor; genel K/R tüm bükümlere geçmez. Tüm bükümlere uygula seçeneğini açın veya SolidWorks'te varsayılan büküm parametrelerini etkinleştirin.")
    if not parent_checked:
        if not body_checked:
            raise RuntimeError("Ana sac şablonunda tablo kontrolü desteklenmiyor ve gövde sacının "
                               "tablo/malzeme durumu doğrulanamadı; K/R uygulanmadı.")
        if notes is not None:
            notes.append("Sac kalınlık tablosu ve malzeme bağları gövde sac unsurundan kontrol edildi.")


def _check_inherited_sheet(model, expected, *, expected_names=None, prepare=False):
    names = []
    for feature, kind in _features(model, kinds={"SheetMetal"}):
        if kind != "SheetMetal" or _identity(feature) == (expected.name, expected.kind):
            continue
        actual = _state(feature, kind, inherited=True)
        target = replace(expected, name=actual.name, kind=kind, error_code=0, overrides=(False, False))
        if prepare:
            # K/R differences can be normalized, thickness differences cannot.
            target = replace(actual, thickness=expected.thickness, error_code=0, suppressed=False)
        if not _same([actual], [target]):
            raise RuntimeError(f"{actual.name}: SheetMetal alt unsuru ana SAC LEVHA K/R ve kalınlığıyla eşleşmedi.")
        names.append(actual.name)
    if expected_names is not None and tuple(names) != expected_names:
        raise RuntimeError("SheetMetal alt unsur listesi değişti; SAC LEVHA doğrulanamadı.")
    return tuple(names)


def _check_converted_values(model, expected, *, expected_names=None, prepare=False):
    names = []
    for feature, kind in _features(model, kinds={CONVERT_SOLID}):
        if kind != CONVERT_SOLID:
            continue
        actual = _state(feature, kind)
        target = replace(expected, name=actual.name, kind=kind, error_code=0, overrides=(False, False))
        if prepare:
            target = replace(actual, thickness=expected.thickness, error_code=0, suppressed=False)
        if not _same([actual], [target]):
            raise RuntimeError(f"{actual.name}: Katıyı Saca Dönüştür K/R, kalınlık veya unsur durumu "
                               "ana sac parametreleriyle eşleşmedi; dönüşüm doğrulanamadı.")
        names.append(actual.name)
    if expected_names is not None and tuple(names) != expected_names:
        raise RuntimeError("Katıyı Saca Dönüştür unsur listesi değişti; dönüşüm doğrulanamadı.")
    return tuple(names)


def _check_bends(model, before, normalize):
    expected = [replace(state, defaults=tuple((member, True) for member, _ in state.defaults),
                        radius=None, allowance=None)
                if normalize and not state.suppressed else state for state in before]
    actual = [_bend_state(feature, kind) for feature, kind in
              _features(model, include_suppressed=True, kinds=BEND_DEFAULTS)]
    if not _same(expected, actual):
        raise RuntimeError("Alt bükümlerin K/R ayarları veya unsur listesi geri okumada eşleşmedi.")


class NotSheetMetal(Exception):
    pass


def process_part(app, path, configuration, recipe, *, preview=False, save=False, parameter_only=False):
    """Tek dosya/konfigürasyon; parameter_only ana Sac-Levha'yı doğrudan düzenler.

    Montaj işçisi manuel isteklerde parameter_only=True kullanır. False,
    eski hesap/alt büküm mirası API'sini kullanan çağrılar için korunur.
    """
    model = None
    original_config = None
    opened = changed = False
    visibility_changed = False
    snapshots = None
    parameter_editor = None
    body_signature = None
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
        if parameter_only:
            if not isinstance(recipe, (ManualAssignment, AssignmentTable)):
                raise ValueError("Doğrudan Sac-Levha ataması için manuel K/R değerleri gerekli.")
            recipe.validate()
            stage = "Sac-Levha parametrelerini doğrudan okuma"
            parameter_editor = ParameterEdit(model)
            calculation = parameter_editor.prepare(recipe)
            before = parameter_editor.before
            notes.append(f"Hedef: {before.name} ({before.kind}) · ISheetMetalFeatureData · "
                         f"Gerçek sac kalınlığı: {calculation.thickness_mm:.12g} mm.")
            if preview:
                notes.insert(0, f"Önizleme; K/R uygulanmadı. Hedef K={calculation.k_factor:.12g}, "
                             f"R={calculation.radius_mm:.12g} mm.")
            else:
                if preexisting_changes:
                    raise RuntimeError("Parçada önceden kaydedilmemiş değişiklik var; önce SolidWorks'te "
                                       "kaydedin veya dosyaları kaydet seçeneğini kapatın.")
                stage = "Sac-Levha K/R yazma, yeniden oluşturma ve geri okuma"
                parameter_editor.apply()
                changed = parameter_editor.changed
                after = parameter_editor.after
                if save:
                    stage = "Kaydetmeden önce konfigürasyonu geri açma"
                    _show_configuration(model, original_config)
                    stage = "Parça dosyasını kaydetme"
                    errors, warnings = _out(pythoncom.VT_I4), _out(pythoncom.VT_I4)
                    if not _call_byref(model, "Save3", 1, errors, warnings) or errors.value:
                        raise RuntimeError(f"Parça kaydedilemedi; hata kodu: {errors.value}.")
                    notes.append("Parça dosyası kaydedildi.")
                    if warnings.value:
                        notes.append(f"Kaydetme uyarısı: {warnings.value}")
                else:
                    notes.append("Bellekte uygulandı; dosyaya kaydedilmedi. SolidWorks'te kontrol edip kaydedin.")
                notes.insert(0, f"Sac-Levha parametreleri geri okumayla doğrulandı: "
                             f"K={after.allowance_value:.12g}, R={after.radius*1000:.12g} mm.")
            notes.append("Büküm tablosundan değer alınmadı. Kalınlık, malzeme ve özel alt büküm ayarları korundu.")
            status = "success"
        else:
            bodies, body_flags = _body_inventory(model)
            if not bodies or (not any(body_flags)
                              and not any(_features(model, kinds={CONVERT_SOLID}))):
                raise NotSheetMetal("Sac metal değil.")
            stage = "Sac unsuru ve kalınlığı"
            feature, parent_kind = _parent(model, notes=notes)
            multiple_sheets = sum(body_flags) > 1
            if len(bodies) > 1:
                if not any(body_flags):
                    raise RuntimeError("Çok gövdeli dönüşümde sac gövdeleri doğrulanamadı; K/R atanmadı.")
                if multiple_sheets and (parent_kind != TEMPLATE_SHEET or not recipe.all_bends):
                    raise RuntimeError(f"{sum(body_flags)} sac gövdesi bulundu; ortak ana Sac-Levha ve "
                                       "Tüm bükümlere uygula seçeneği gerekiyor.")
                if multiple_sheets:
                    if not all(body_flags):
                        raise RuntimeError("Birden fazla sac ve normal katı gövde birlikte bulundu; "
                                           "ortak K/R kapsamı doğrulanamadı.")
                    templates = {_identity(feature)} | {
                        _identity(item) for item, _ in _features(model, kinds={TEMPLATE_SHEET})}
                    if len(templates) != 1:
                        raise RuntimeError("Çok gövdeli parçada birden fazla ana Sac-Levha bulundu; K/R atanmadı.")
                body_signature = _check_body_coverage(model, bodies, body_flags)
                notes.append(f"Gövde kapsamı: {sum(body_flags)} sac gövdesi; "
                             f"{len(bodies)-sum(body_flags)} normal katı gövde K/R kapsamı dışında.")
            body_feature = _body_feature(model, feature, parent_kind, multiple=multiple_sheets)
            body_kind = _feature_kind(body_feature)
            notes.append(f"Gövde sac unsuru: {_read(body_feature, 'Name')} ({body_kind}).")
            # Use a body-level SheetMetal definition, not the template's potentially
            # different default thickness. Multiple sheet bodies must agree first.
            # Nonmatching manual sheets stop before allowance/override API calls.
            calculation = calculate(float(_read(_read(body_feature, "GetDefinition"),
                                           "SheetThickness" if body_kind == CONVERT_SOLID else "Thickness")) * 1000, recipe)
            stage = "Mevcut K/R ve büküm payı okuma"
            before = _state(feature, parent_kind)
            if before.error_code or before.suppressed:
                raise RuntimeError("SAC LEVHA unsuru bastırılmış veya zaten hata içeriyor; önce parçayı düzeltin.")
            stage = "Malzeme, sac kalınlık tablosu ve özel büküm kontrolleri"
            _check_defaults(model, feature, normalize=recipe.all_bends, notes=notes)
            actual_thickness = calculation.thickness_mm / 1000
            effective = replace(before, thickness=actual_thickness)
            align_template = not math.isclose(before.thickness, actual_thickness,
                                              rel_tol=0, abs_tol=1e-10)
            if align_template and (parent_kind != TEMPLATE_SHEET or not recipe.all_bends):
                raise RuntimeError("Ana sacın varsayılan kalınlığı gerçek sac kalınlığından farklı. "
                                   "Kalınlığı koruyarak K/R uygulamak için Tüm bükümlere uygula seçeneğini açın.")
            if align_template and not any(_features(model, kinds={CONVERT_SOLID})):
                raise RuntimeError(f"{_read(body_feature, 'Name')}: SheetMetal alt unsuru ana SAC LEVHA "
                                   "kalınlığıyla eşleşmedi; katıdan dönüştürme bulunmadan ana kalınlık değiştirilmedi.")
            inherited_names = _check_inherited_sheet(model, effective, prepare=recipe.all_bends)
            stage = "Katıyı Saca Dönüştür parametre kontrolü"
            converted_names = _check_converted_values(model, effective, prepare=recipe.all_bends)
            bends_before = [_bend_state(feature, kind) for feature, kind in
                            _features(model, include_suppressed=True, kinds=BEND_DEFAULTS)]
            if not preview:
                if preexisting_changes:
                    raise RuntimeError("Parçada önceden kaydedilmemiş değişiklik var; önce SolidWorks'te kaydedin veya dosyaları kaydet seçeneğini kapatın.")
                stage = "Konfigürasyonların yedeğini alma"
                snapshots = _capture(model)
                target = replace(effective, radius=calculation.radius_mm / 1000,
                                 allowance_type=2, k_factor=calculation.k_factor)
                changed = True  # COM setters can mutate even if ModifyDefinition fails.
                if recipe.all_bends:
                    if align_template:
                        stage = "Gerçek sac kalınlığını koruyarak ana varsayılanı eşitleme"
                        parent, _ = _parent(model)
                        _modify(model, parent, effective)
                        notes.append(f"Ana varsayılan kalınlığı {before.thickness*1000:g} mm → "
                                     f"{actual_thickness*1000:g} mm; gerçek gövde kalınlığı korundu.")
                    stage = "Alt bükümleri ana K/R ayarlarına bağlama"
                    updated = _normalize_bends(model)
                    if updated:
                        notes.append(f"Ana K/R ayarlarına bağlanan unsurlar: {', '.join(updated)}.")
                stage = "K/R yazma ve yeniden oluşturma"
                # Configuration capture invalidates previous COM definitions and
                # can invalidate feature wrappers. Resolve again before mutation.
                feature, kind = _parent(model)
                if _identity(feature) != (before.name, before.kind):
                    raise RuntimeError("SAC LEVHA hedefi konfigürasyon yedeğinden sonra değişti.")
                radius_route = _modify(model, feature, target)
                if radius_route:
                    notes.append(f"R atama yolu: {radius_route}.")
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
                _check_bends(model, bends_before, recipe.all_bends)
                _check_inherited_sheet(model, target, expected_names=inherited_names)
                _check_converted_values(model, target, expected_names=converted_names)
                if body_signature is not None:
                    current_bodies, current_flags = _body_inventory(model)
                    _check_body_coverage(model, current_bodies, current_flags, expected=body_signature)
                if converted_names:
                    notes.append(f"Katıyı Saca Dönüştür: {len(converted_names)} unsurda K/R ve kalınlık geri okumayla doğrulandı.")
                if save:
                    # Switching after Save3 can dirty a borrowed document again.
                    # Save with the user's original configuration already restored,
                    # so the next configuration in this batch starts clean.
                    stage = "Kaydetmeden önce konfigürasyonu geri açma"
                    _show_configuration(model, original_config)
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
            if recipe.all_bends:
                notes.append("Kapsam: tüm bükümler; özel K/R ayarları ana sacı kullanır, sac kalınlığı korunur.")
            if isinstance(recipe, (ManualAssignment, AssignmentTable)):
                notes.append(f"{'Manuel atama hedefi' if preview else 'Manuel atama'} · K={calculation.k_factor:.12g} · R={calculation.radius_mm:.12g} mm · t={calculation.thickness_mm:.12g} mm")
            else:
                notes.append(f"K={calculation.k_factor:.4f} · R={calculation.radius_mm:.3f} mm · t={calculation.thickness_mm:g} mm · V={calculation.die_opening_mm:g} mm · BA({calculation.angle_deg:g}°)={calculation.ba_mm:.5f} mm")
            notes.extend(calculation.notes)
            status = "success"
    except (NotSheetMetal, NoSheetMetal, ThicknessMismatch) as error:
        status = "skipped"
        notes.append(str(error))
    except Exception as error:
        # The table truncates long discovery notes. Show the actionable error
        # first so the user can see it without opening the complete log.
        notes.insert(0, f"{stage}: {error}")
        if parameter_editor is not None and parameter_editor.changed:
            changed = True
            try:
                parameter_editor.rollback()
                changed = False
                notes.append("Önceki Sac-Levha parametreleri geri yüklendi ve kontrol edildi.")
            except Exception as rollback_error:
                notes.insert(0, f"GERİ ALMA HATASI: {rollback_error}. Parçayı kaydetmeyin.")
        if changed and snapshots is not None:
            try:
                _rollback(model, snapshots)
                if body_signature is not None:
                    current_config = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
                    try:
                        _show_configuration(model, configuration)
                        current_bodies, current_flags = _body_inventory(model)
                        _check_body_coverage(model, current_bodies, current_flags, expected=body_signature)
                    finally:
                        _show_configuration(model, current_config)
                notes.append("Önceki K/R değerleri geri yüklendi ve kontrol edildi.")
                changed = False
            except Exception as rollback_error:
                notes.insert(0, f"GERİ ALMA HATASI: {rollback_error}")
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
        if isinstance(recipe, (ManualAssignment, AssignmentTable)):
            if isinstance(recipe, AssignmentTable):
                scope = f"Manuel K/R · {len(recipe.rows)} kalınlık satırı"
            else:
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
                                                        preview=preview, save=save,
                                                        parameter_only=isinstance(recipe, (ManualAssignment, AssignmentTable)))
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
