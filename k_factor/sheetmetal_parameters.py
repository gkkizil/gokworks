"""Direct edits of the Sheet-Metal PropertyManager's K factor and radius.

No gauge/bend table is evaluated. Only the selected SheetMetal definition is
edited; thickness, material links and individual bend overrides are retained.
The table filename of an *existing* allowance is retained only for rollback.
All real COM calls use IDispatch directly, without MakePy/type-info generation.
"""

from dataclasses import dataclass, replace
import math


SHEET_TYPES = {"SheetMetal", "TemplateSheetMetal"}
MISSING_MEMBER = {-2147352573, -2147352570}


def _raw(obj):
    raw = getattr(obj, "_oleobj_", obj)
    return raw if hasattr(raw, "Invoke") and hasattr(raw, "GetIDsOfNames") else None


def _invoke(obj, member, flags, *args):
    """Use published member names and explicit method/property invocation.

    Do not ask COM for GetTypeInfo or invoke a returned object's default member.
    This also avoids MakePy's implicit handling of optional/out parameters.
    """
    raw = _raw(obj)
    try:
        if raw is not None:
            dispid = raw.GetIDsOfNames(0, member)
            values = tuple(_raw(arg) if _raw(arg) is not None else arg for arg in args)
            return raw.Invoke(dispid, 0, flags, flags != 4, *values)
        if flags == 4:
            setattr(obj, member, args[0])
            return None
        value = getattr(obj, member)
        # Python doubles may expose a zero-argument method as a property.
        # A dispatch object, even if callable, is always a returned object.
        return value(*args) if flags == 1 and callable(value) and not hasattr(value, "_oleobj_") else value
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


def _get(obj, member):
    return _invoke(obj, member, 2)


def _call(obj, member, *args):
    return _invoke(obj, member, 1, *args)


def _put(obj, member, value):
    _invoke(obj, member, 4, value)


def _optional(obj, member):
    try:
        return _call(obj, member)
    except RuntimeError as error:
        cause = error.__cause__
        if isinstance(cause, AttributeError) or getattr(cause, "hresult", None) in MISSING_MEMBER:
            return None
        raise


def _kind(feature):
    kind = _call(feature, "GetTypeName2")
    return _call(feature, "GetTypeName") if kind == "ICE" else kind


def _identity(feature):
    return _get(feature, "Name"), _kind(feature)


def _suppressed(feature):
    if _raw(feature) is not None:
        import pythoncom
        from win32com.client import VARIANT
        configurations = VARIANT(pythoncom.VT_EMPTY, None)
    else:
        # The same swThisConfiguration contract for platform-neutral doubles.
        from types import SimpleNamespace
        configurations = SimpleNamespace(kind=0, value=None)
    values = _call(feature, "IsSuppressed2", 1, configurations)
    if isinstance(values, (tuple, list)):
        if len(values) != 1:
            raise RuntimeError("Sac unsurunun bastırma durumu tek konfigürasyon için okunamadı.")
        values = values[0]
    if values is None:
        raise RuntimeError("Sac unsurunun bastırma durumu okunamadı.")
    return bool(values)


def _sheet_features(model):
    stack = [(_call(model, "FirstFeature"), False)]
    visited = set()
    while stack:
        feature, sub = stack.pop()
        if feature is None:
            continue
        identity = _identity(feature)
        key = (*identity, sub)
        if key in visited:
            continue
        visited.add(key)
        if len(visited) > 20000:
            raise RuntimeError("Sac unsuru taraması tamamlanamadı; unsur ağacı sınırı aşıldı.")
        stack.append((_call(feature, "GetNextSubFeature" if sub else "GetNextFeature"), sub))
        if identity[1] in SHEET_TYPES and _suppressed(feature):
            continue
        stack.append((_call(feature, "GetFirstSubFeature"), True))
        # Folders and unrelated modeling features need no suppression API.
        if identity[1] in SHEET_TYPES:
            yield feature


class NoSheetMetal(ValueError):
    """A regular solid part is skipped, not reported as a failed assignment."""


@dataclass(frozen=True)
class Parameters:
    name: str
    kind: str
    thickness: float  # SolidWorks API length unit: metres.
    radius: float
    allowance_type: int
    allowance_value: float | str


def read(feature):
    name, kind = _identity(feature)
    definition = _call(feature, "GetDefinition")
    if definition is None:
        raise RuntimeError(f"{name}: ISheetMetalFeatureData okunamadı.")
    allowance = _call(definition, "GetCustomBendAllowance")
    if allowance is None:
        raise RuntimeError(f"{name}: ICustomBendAllowance okunamadı.")
    mode = int(_get(allowance, "Type"))
    member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance",
              4: "BendDeduction", 5: "BendCalculationTableFile"}.get(mode)
    if member is None:
        raise RuntimeError(f"{name}: desteklenmeyen büküm izni türü: {mode}.")
    value = _get(allowance, member)
    value = str(value or "") if mode in (1, 5) else float(value)
    state = Parameters(name, kind, float(_get(definition, "Thickness")),
                       float(_get(definition, "BendRadius")), mode, value)
    if (not math.isfinite(state.thickness) or state.thickness <= 0
            or not math.isfinite(state.radius) or state.radius < 0
            or mode not in (1, 5) and not math.isfinite(value)):
        raise RuntimeError(f"{name}: SolidWorks geçersiz sac parametreleri döndürdü.")
    return state


def discover(model):
    """Official 2013+ template API, then typed feature-tree fallback."""
    template = _optional(_get(model, "Extension"), "GetTemplateSheetMetal")
    features = {_identity(feature): feature for feature in _sheet_features(model)}
    folder = _optional(_get(model, "FeatureManager"), "GetSheetMetalFolder")
    if folder is not None:
        # Converted/multibody sheets can be absent from normal tree traversal.
        for feature in _optional(folder, "GetSheetMetals") or ():
            if feature is not None and _kind(feature) == "SheetMetal" and not _suppressed(feature):
                features[_identity(feature)] = feature
        if template is None:
            template = _optional(folder, "GetFeature")
    if template is not None:
        identity = _identity(template)
        if identity[1] not in SHEET_TYPES:
            raise RuntimeError(f"GetTemplateSheetMetal beklenmeyen unsur döndürdü: {identity}.")
        if _suppressed(template):
            raise NoSheetMetal("Aktif konfigürasyonda Sac-Levha unsuru bastırılmış.")
        features[identity] = template
    templates = [feature for (_, kind), feature in features.items() if kind == "TemplateSheetMetal"]
    sheets = [feature for (_, kind), feature in features.items() if kind == "SheetMetal"]
    if len(templates) > 1:
        raise RuntimeError("Birden fazla ana Sac-Levha unsuru var; ortak hedef belirlenemedi.")
    if templates:
        return templates[0], sheets
    if len(sheets) == 1:
        return sheets[0], sheets
    if not sheets:
        raise NoSheetMetal("Sac metal değil; SheetMetal / TemplateSheetMetal unsuru bulunamadı.")
    raise RuntimeError("Ortak Sac-Levha şablonu olmayan birden fazla SheetMetal unsuru var; hedef belirsiz.")


def snapshot(model):
    parent, sheets = discover(model)
    return tuple(read(feature) for feature in
                 {_identity(item): item for item in (parent, *sheets)}.values())


def same(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if (a.name, a.kind, a.allowance_type) != (b.name, b.kind, b.allowance_type):
            return False
        for x, y in ((a.thickness, b.thickness), (a.radius, b.radius),
                     (a.allowance_value, b.allowance_value)):
            if isinstance(x, str) or isinstance(y, str):
                if x != y:
                    return False
            elif not math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-10):
                return False
    return True


def write(model, expected):
    parent, sheets = discover(model)
    candidates = {_identity(item): item for item in (parent, *sheets)}
    feature = candidates.get((expected.name, expected.kind))
    if feature is None:
        raise RuntimeError(f"Sac-Levha hedefi yeniden bulunamadı: {expected.name}.")
    definition = _call(feature, "GetDefinition")
    if _raw(definition) is not None:
        import pythoncom
        from win32com.client import VARIANT
        component = VARIANT(pythoncom.VT_DISPATCH, None)
    else:
        component = None
    if not _call(definition, "AccessSelections", model, component):
        raise RuntimeError(f"{expected.name}: AccessSelections seçim erişimi alınamadı.")
    committed = False
    try:
        # Thickness and all gauge/material/override flags are deliberately absent.
        allowance = _call(definition, "GetCustomBendAllowance")
        member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance",
                  4: "BendDeduction", 5: "BendCalculationTableFile"}[expected.allowance_type]
        _put(allowance, member, expected.allowance_value)
        _put(allowance, "Type", expected.allowance_type)  # SolidWorks requires Type LAST.
        _call(definition, "SetCustomBendAllowance", allowance)
        _put(definition, "BendRadius", expected.radius)
        if not _call(feature, "ModifyDefinition", definition, model, component):
            raise RuntimeError(f"{expected.name}: ModifyDefinition değişikliği kabul etmedi.")
        committed = True  # ModifyDefinition releases selection access.
    finally:
        if not committed:
            _call(definition, "ReleaseSelectionAccess")
    if not _call(model, "EditRebuild3"):
        raise RuntimeError(f"{expected.name}: parça yeniden oluşturulamadı.")


def target(before, calculation):
    return replace(before, radius=calculation.radius_mm / 1000,
                   allowance_type=2, allowance_value=calculation.k_factor)


class ParameterEdit:
    """One part/configuration transaction, restricted to its parent definition."""

    def __init__(self, model):
        self.model = model
        self.configuration = self.active_configuration()
        self.snapshots = {}
        self.changed = False

    def active_configuration(self):
        return _get(_get(_get(self.model, "ConfigurationManager"), "ActiveConfiguration"), "Name")

    def show(self, name):
        if self.active_configuration() != name and not _call(self.model, "ShowConfiguration2", name):
            raise RuntimeError(f"Konfigürasyon açılamadı: {name}.")
        if self.active_configuration() != name:
            raise RuntimeError(f"SolidWorks beklenen konfigürasyonu etkinleştirmedi: {name}.")

    def prepare(self, recipe):
        from k_factor.rules import calculate
        parent, sheets = discover(self.model)
        # Match actual body thickness before reading allowance/rollback data.
        # A modern template's default thickness may differ from a converted body.
        thicknesses = [float(_get(_call(item, "GetDefinition"), "Thickness")) * 1000
                       for item in sheets or (parent,)]
        calculations = [calculate(thickness, recipe) for thickness in thicknesses]
        calculation = calculations[0]
        if any(not math.isclose(item.k_factor, calculation.k_factor, rel_tol=0, abs_tol=1e-12)
               or not math.isclose(item.radius_mm, calculation.radius_mm, rel_tol=0, abs_tol=1e-9)
               for item in calculations[1:]):
            raise RuntimeError("Bu parçadaki sac gövdeleri farklı K/R değerleri istiyor. "
                               "Ortak ana Sac-Levha parametresine tek K/R yazılabilir; parça değiştirilmedi.")
        if _call(parent, "GetErrorCode"):
            raise RuntimeError("Ana Sac-Levha unsuru mevcut bir yeniden oluşturma hatası içeriyor.")
        self.before = read(parent)
        self.expected = target(self.before, calculation)
        self.calculation = calculation
        return calculation

    def _snapshot(self):
        try:
            return snapshot(self.model)
        except NoSheetMetal:
            return ()  # Other configurations may suppress all sheet features.

    def apply(self):
        names = _call(self.model, "GetConfigurationNames")
        if not names or self.configuration not in names:
            raise RuntimeError("Parçanın konfigürasyonları okunamadı.")
        try:
            for name in names:
                self.show(name)
                self.snapshots[name] = self._snapshot()
        finally:
            self.show(self.configuration)
        before = self.snapshots[self.configuration]
        if not before or not same((self.before,), before[:1]):
            raise RuntimeError("Sac-Levha parametreleri okuma sonrasında değişti; yeniden tarayın.")
        # A setter may mutate the document even when ModifyDefinition fails.
        self.changed = True
        write(self.model, self.expected)
        after = snapshot(self.model)
        if not same((self.expected,), after[:1]):
            raise RuntimeError("Sac-Levha K/R geri okuması girilen değerlerle eşleşmedi. "
                               "SolidWorks parametreyi kabul etmedi veya başka bir ayar geri yazdı.")
        if ([(x.name, x.kind) for x in before] != [(x.name, x.kind) for x in after]
                or any(not math.isclose(a.thickness, b.thickness, rel_tol=0, abs_tol=1e-10)
                       for a, b in zip(before, after))):
            raise RuntimeError("Atama sırasında sac kalınlığı veya sac unsur listesi değişti.")
        for name, baseline in self.snapshots.items():
            if name == self.configuration:
                continue
            self.show(name)
            if not same(baseline, self._snapshot()):
                raise RuntimeError(f"K/R değişikliği başka konfigürasyona yayıldı: {name}.")
        self.show(self.configuration)
        if not same(after, snapshot(self.model)):
            raise RuntimeError("Konfigürasyon dönüşünde Sac-Levha parametreleri değişti.")
        parent, _ = discover(self.model)
        if _call(parent, "GetErrorCode"):
            raise RuntimeError("Sac-Levha unsuru atama sonrası yeniden oluşturma hatası içeriyor.")
        self.after = after[0]

    def rollback(self):
        try:
            # Restore parent first. Its inherited children usually recover with
            # it, so do not edit a body whose parameters already match baseline.
            for name, baseline in self.snapshots.items():
                self.show(name)
                for state in baseline:
                    try:
                        actual = next((item for item in self._snapshot()
                                       if (item.name, item.kind) == (state.name, state.kind)), None)
                    except Exception:
                        # A failed rebuild may prevent readback. Still attempt
                        # restoring the known parent definition before giving up.
                        actual = None
                    if actual is None or not same((state,), (actual,)):
                        write(self.model, state)
            for name, baseline in self.snapshots.items():
                self.show(name)
                if not same(baseline, self._snapshot()):
                    raise RuntimeError(f"Geri alma doğrulanamadı: {name}. Parçayı kaydetmeyin.")
            self.changed = False
        finally:
            self.show(self.configuration)
