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


def _independent_sketch(feature, protected):
    """Only tolerate a sketch with a readable dependency graph excluding the sheets.

    Error name/code equality alone proves neither geometry validity nor that an
    error is unrelated. Body/bend features and unknown parent metadata fail closed.
    """
    if _kind(feature) not in ('ProfileFeature', '3DProfileFeature'):
        return False
    pending, visited = [feature], set()
    while pending:
        item = pending.pop()
        identity = _identity(item)
        if identity in protected:
            return False
        if identity in visited:
            continue
        visited.add(identity)
        if len(visited) > 20000:
            return False
        try:
            parents = _call(item, 'GetParents')
        except RuntimeError:
            return False
        if parents is not None:
            if not isinstance(parents, (tuple, list)):
                return False
            pending.extend(p for p in parents if p is not None)
    return True


def feature_errors(model, *, unrelated_to=None):
    """{feature name: error code} of every feature (sub-features included) with a rebuild error.

    Used to tell an existing, unrelated rebuild problem in the part (a dangling
    sketch relation, a failed cosmetic feature...) from an error the K/R edit
    caused. ``EditRebuild3`` returns False for both.
    """
    errors, visited = {}, set()
    stack = [(_call(model, "FirstFeature"), False)]
    while stack:
        feature, sub = stack.pop()
        if feature is None:
            continue
        name = _get(feature, "Name")
        if (name, sub) in visited:
            continue
        visited.add((name, sub))
        if len(visited) > 20000:
            raise RuntimeError("Unsur hata taraması tamamlanamadı; unsur ağacı sınırı aşıldı.")
        stack.append((_call(feature, "GetNextSubFeature" if sub else "GetNextFeature"), sub))
        stack.append((_call(feature, "GetFirstSubFeature"), True))
        code = _optional(feature, "GetErrorCode")
        if code and (unrelated_to is None or _independent_sketch(feature, unrelated_to)):
            errors[name] = int(code)
    return errors


def rebuild(model, tolerated):
    """Rebuild; a False result is accepted only when no feature gained an error.

    Returns the names of pre-existing errors that remain (for the report).
    """
    rebuilt = _call(model, "EditRebuild3")
    errors = feature_errors(model)
    new = {name: code for name, code in errors.items() if tolerated.get(name) != code}
    if new or not rebuilt and not errors:
        detail = ", ".join(f"{name} (kod {code})" for name, code in sorted(new.items()))
        raise RuntimeError("parça yeniden oluşturulamadı" + (f"; hata veren unsurlar: {detail}" if detail else "")
                           + ". Yarıçap/K bu geometriye uymuyor olabilir (ör. kısa flanş, kapalı köşe, kıvrım).")
    return sorted(errors)


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


def write(model, expected, tolerated=None):
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
    try:
        return rebuild(model, tolerated or {})
    except RuntimeError as error:
        raise RuntimeError(f"{expected.name}: {error}") from None


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
        self.tolerated = {}
        self.error_snapshots = {}
        self.tolerated_by_configuration = {}
        self.updated_snapshots = {}
        self.notes = []

    def active_configuration(self):
        return _get(_get(_get(self.model, "ConfigurationManager"), "ActiveConfiguration"), "Name")

    def show(self, name):
        if self.active_configuration() != name and not _call(self.model, "ShowConfiguration2", name):
            raise RuntimeError(f"Konfigürasyon açılamadı: {name}.")
        if self.active_configuration() != name:
            raise RuntimeError(f"SolidWorks beklenen konfigürasyonu etkinleştirmedi: {name}.")

    def prepare(self, recipe):
        from modules.k_factor.rules import calculate
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

    def _capture_errors(self, name, parameters):
        protected = {(p.name, p.kind) for p in parameters}
        self.error_snapshots[name] = feature_errors(self.model)
        self.tolerated_by_configuration[name] = feature_errors(self.model, unrelated_to=protected)

    def _verify_errors(self, name, parameters):
        tolerated = self.tolerated_by_configuration.get(name, {})
        remaining = rebuild(self.model, tolerated)
        safe = feature_errors(self.model, unrelated_to={(p.name, p.kind) for p in parameters})
        if any(key not in safe for key in remaining):
            raise RuntimeError(f'{name}: hata veren unsurun Sac-Levha bağımsızlığı doğrulanamadı.')
        return remaining

    def verify_current_configuration(self):
        """Last configuration activation can rebuild too; verify before Save3."""
        name = self.active_configuration()
        expected = self.updated_snapshots.get(name)
        if expected is None:
            raise RuntimeError(f'Konfigürasyon doğrulama kaydı yok: {name}.')
        if expected:
            self._verify_errors(name, expected)
        if not same(expected, self._snapshot()):
            raise RuntimeError(f'Kaydetmeden önce Sac-Levha parametreleri değişti: {name}.')

    def apply(self):
        names = _call(self.model, "GetConfigurationNames")
        if not names or self.configuration not in names:
            raise RuntimeError("Parçanın konfigürasyonları okunamadı.")
        try:
            for name in names:
                self.show(name)
                self.snapshots[name] = self._snapshot()
                self._capture_errors(name, self.snapshots[name])
                if self.snapshots[name]:
                    self._verify_errors(name, self.snapshots[name])
                    # Rebuild can resolve an old error. Do not exempt it if
                    # the K/R write introduces that error again later.
                    self._capture_errors(name, self.snapshots[name])
        finally:
            self.show(self.configuration)
        before = self.snapshots[self.configuration]
        if not before or not same((self.before,), before[:1]):
            raise RuntimeError("Sac-Levha parametreleri okuma sonrasında değişti; yeniden tarayın.")
        # Configuration activation can resolve an earlier error. Capture the
        # actual state immediately before this write, not prepare()'s stale map.
        self._capture_errors(self.configuration, before)
        self.tolerated = self.tolerated_by_configuration[self.configuration]
        # A setter may mutate the document even when ModifyDefinition fails.
        self.changed = True
        remaining = write(self.model, self.expected, self.tolerated)
        if remaining:
            self.notes.append("Parçada K/R atamasından önce de var olan yeniden oluşturma hataları sürüyor: "
                              + ", ".join(remaining) + ". Aynı hata kodları sürüyor; SolidWorks'te kontrol edin.")
        after = snapshot(self.model)
        if not same((self.expected,), after[:1]):
            raise RuntimeError("Sac-Levha K/R geri okuması girilen değerlerle eşleşmedi. "
                               "SolidWorks parametreyi kabul etmedi veya başka bir ayar geri yazdı.")
        if ([(x.name, x.kind) for x in before] != [(x.name, x.kind) for x in after]
                or any(not math.isclose(a.thickness, b.thickness, rel_tol=0, abs_tol=1e-10)
                       for a, b in zip(before, after))):
            raise RuntimeError("Atama sırasında sac kalınlığı veya sac unsur listesi değişti.")
        shared = []
        self.updated_snapshots[self.configuration] = after
        for name, baseline in self.snapshots.items():
            if name == self.configuration:
                continue
            self.show(name)
            current = self._snapshot()
            if current:
                self._verify_errors(name, current)
                current = self._snapshot()
            self.updated_snapshots[name] = current
            if same(baseline, current):
                continue
            # Sheet-Metal feature data is not configuration specific in SolidWorks: a
            # configuration that had exactly the active definition (e.g. the derived
            # "<config>SM-FLAT-PATTERN" / "SM-DÜZ-ÇOĞALTMA") follows the edit. That is
            # expected; a configuration with its own, different values must not change.
            if same(baseline, before) and same(current, after):
                shared.append(name); continue
            raise RuntimeError(f"K/R değişikliği farklı değerli başka konfigürasyona yayıldı: {name}.")
        self.show(self.configuration)
        if shared:
            self.notes.append("Sac-Levha parametreleri şu konfigürasyonlarla ortak; onlar da aynı K/R'yi aldı: "
                              + ", ".join(shared) + ".")
        self._verify_errors(self.configuration, after)
        if not same(after, snapshot(self.model)):
            raise RuntimeError("Konfigürasyon dönüşünde Sac-Levha parametreleri değişti.")
        parent, _ = discover(self.model)
        if _call(parent, "GetErrorCode"):
            raise RuntimeError("Sac-Levha unsuru atama sonrası yeniden oluşturma hatası içeriyor.")
        self.after = after[0]

    def rollback(self):
        errors = []
        try:
            # Restore parent first. Its inherited children usually recover with
            # it, so do not edit a body whose parameters already match baseline.
            for name, baseline in self.snapshots.items():
                try:
                    self.show(name)
                    for state in baseline:
                        try:
                            actual = next((item for item in self._snapshot()
                                           if (item.name, item.kind) == (state.name, state.kind)), None)
                        except Exception:
                            # Unreadable post-write state still needs a restore.
                            actual = None
                        if actual is None or not same((state,), (actual,)):
                            write(self.model, state, self.error_snapshots.get(name, {}))
                except Exception as error:
                    # A failure in one configuration must not strand all later
                    # configurations with the failed operation's parameters.
                    errors.append(f'{name}: {error}')
            for name, baseline in self.snapshots.items():
                try:
                    self.show(name)
                    if baseline:
                        rebuild(self.model, self.error_snapshots.get(name, {}))
                    if not same(baseline, self._snapshot()):
                        raise RuntimeError('Önceki parametreler geri okunamadı.')
                except Exception as error:
                    errors.append(f'{name}: {error}')
            if errors:
                raise RuntimeError('Geri alma doğrulanamadı: ' + '; '.join(errors) + '. Parçayı kaydetmeyin.')
            self.changed = False
        finally:
            self.show(self.configuration)
