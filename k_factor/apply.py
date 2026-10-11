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


def _read(obj, member):
    """Read a zero-argument COM member without invoking returned dispatch objects."""
    try:
        return _value(obj, member)
    except Exception as error:
        raise RuntimeError(f"SolidWorks API · {member}: {error}") from error


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


def _out(kind):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | kind, 0 if kind == pythoncom.VT_I4 else False if kind == pythoncom.VT_BOOL else "")


def _features(model, *, include_suppressed=False):
    first = _value(model, "FirstFeature")
    stack = [(first, False)] if first is not None else []
    visited, yielded = set(), set()
    empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
    while stack:
        feature, sub = stack.pop()
        name, kind = _value(feature, "Name"), _value(feature, "GetTypeName2")
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
        if identity in yielded:
            continue
        suppressed = feature.IsSuppressed2(1, empty)
        if suppressed is None:
            raise RuntimeError(f"Unsurun konfigürasyon durumu okunamadı: {name}")
        if include_suppressed or not sw._success(suppressed):
            yielded.add(identity)
            yield feature, kind


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


def _state(feature):
    definition = _read(feature, "GetDefinition")
    if definition is None:
        raise RuntimeError("SheetMetal unsur tanımı okunamadı.")
    allowance = _read(definition, "GetCustomBendAllowance")
    if allowance is None:
        raise RuntimeError("Özel büküm payı API'si okunamadı.")
    allowance_type = int(_read(allowance, "Type"))
    # Inactive allowance modes are not needed for state/rollback and some
    # dispatch implementations do not expose their getters in the current mode.
    k = float(_read(allowance, "KFactor")) if allowance_type == 2 else 0.0
    ba = float(_read(allowance, "BendAllowance")) if allowance_type == 3 else 0.0
    bd = float(_read(allowance, "BendDeduction")) if allowance_type == 4 else 0.0
    table = str(_read(allowance, "BendTableFile") or "") if allowance_type in (1, 5) else ""
    return FeatureState(_read(feature, "Name"), float(_read(definition, "Thickness")),
                        float(_read(definition, "BendRadius")), allowance_type, k, ba, bd, table)


def _states(model):
    return [_state(feature) for feature, kind in _features(model, include_suppressed=True)
            if kind == "SheetMetal"]


def _same(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if (a.name, a.allowance_type) != (b.name, b.allowance_type):
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
                         5: ("BendTableFile", state.bend_table)}[state.allowance_type]
        _write(allowance, member, value)
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
            if _same(before, _states(model)):
                continue
            features = {_value(f, "Name"): f for f, kind in _features(model, include_suppressed=True)
                        if kind == "SheetMetal"}
            for state in before:
                _modify(model, features[state.name], state)
        for name, before in snapshots.items():
            _show_configuration(model, name)
            if not _same(before, _states(model)):
                raise RuntimeError(f"Geri alma doğrulanamadı: {name}. Parçayı kaydetmeyin.")
    finally:
        _show_configuration(model, original)


def _check_defaults(model, definition):
    if bool(_read(definition, "UseMaterialSheetMetalParameters")):
        raise RuntimeError("Sac parametreleri malzemeye bağlı; önce SolidWorks'te bu bağı kaldırın.")
    used, filename = _out(pythoncom.VT_BOOL), _out(pythoncom.VT_BSTR)
    error = _call(definition, "GetUseGaugeTable", used, filename)
    if error != 0:
        raise RuntimeError(f"Gauge tablosu durumu okunamadı; API hata kodu: {error}")
    if used.value:
        raise RuntimeError("Gauge tablosuna bağlı sac; önce SolidWorks'te tablo bağını kaldırın.")
    for feature, kind in _features(model):
        if kind == "SheetMetal":
            continue
        data = _value(feature, "GetDefinition")
        if data is None:
            continue
        # Swept flanges use UseDefaultRadius; other bend features expose
        # UseDefaultBendRadius. Both must inherit the sheet-metal radius.
        for attribute in ("UseDefaultBendRadius", "UseDefaultRadius", "UseDefaultBendAllowance"):
            if hasattr(data, attribute) and not bool(_value(data, attribute)):
                raise RuntimeError(f"{_value(feature, 'Name')} özel büküm parametresi kullanıyor; genel K/R tüm bükümlere geçmez. Önce varsayılan büküm parametrelerini etkinleştirin.")


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
        # Assembly dependencies can be loaded without a document window.
        # Prefer the same lookup used by xCAD before trying the name lookup.
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
        original_config = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
        if not _value(model, "Visible"):
            model.Visible = True
            visibility_changed = True
        errors = _out(pythoncom.VT_I4)
        activated = app.ActivateDoc3(_value(model, "GetPathName"), False, 1, errors)
        active = _value(app, "ActiveDoc")
        if (activated is None or errors.value or active is None
                or _key(_value(activated, "GetPathName"), "") != _key(path, "")
                or _key(_value(active, "GetPathName"), "") != _key(path, "")):
            raise RuntimeError("SolidWorks kaynak parçayı etkinleştiremedi.")
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
        features = [f for f, kind in _features(model) if kind == "SheetMetal"]
        if len(features) != 1:
            raise RuntimeError("Tek bir aktif SheetMetal unsuru gerekir.")
        feature = features[0]
        if isinstance(recipe, ManualAssignment):
            # Read thickness first: non-matching sheets must never go through
            # K/R override checks or any parameter write/save.
            calculation = calculate(float(_read(_read(feature, "GetDefinition"), "Thickness")) * 1000, recipe)
        stage = "Mevcut K/R ve büküm payı okuma"
        before = _state(feature)
        if _read(feature, "GetErrorCode"):
            raise RuntimeError("SheetMetal unsuru zaten hata içeriyor; önce parçayı düzeltin.")
        calculation = calculate(before.thickness * 1000, recipe)
        stage = "Malzeme, gauge ve özel büküm kontrolleri"
        _check_defaults(model, _read(feature, "GetDefinition"))
        if not preview:
            if save and _read(model, "GetSaveFlag"):
                raise RuntimeError("Parçada önceden kaydedilmemiş değişiklik var; önce SolidWorks'te kaydedin veya dosyaları kaydet seçeneğini kapatın.")
            stage = "Konfigürasyonların yedeğini alma"
            snapshots = _capture(model)
            target = replace(before, radius=calculation.radius_mm / 1000,
                             allowance_type=2, k_factor=calculation.k_factor)
            changed = True  # COM setters can mutate even if ModifyDefinition fails.
            stage = "K/R yazma ve yeniden oluşturma"
            _modify(model, feature, target)
            stage = "K/R geri okuma ve konfigürasyon doğrulaması"
            after = _state(feature)
            if not _same([target], [after]):
                raise RuntimeError("K/R yazma sonrası değerler geri okumada eşleşmedi.")
            for name, untouched in snapshots.items():
                if name != configuration:
                    _show_configuration(model, name)
                    if not _same(untouched, _states(model)):
                        raise RuntimeError(f"Değişiklik başka konfigürasyona yayıldı ({name}); işlem geri alınıyor. Parametreleri konfigürasyona özel tanımlayın.")
            _show_configuration(model, configuration)
            if save:
                stage = "Parça dosyasını kaydetme"
                errors, warnings = _out(pythoncom.VT_I4), _out(pythoncom.VT_I4)
                if not model.Save3(1, errors, warnings) or errors.value:
                    raise RuntimeError(f"Parça kaydedilemedi; hata kodu: {errors.value}. Dosyanın durumunu SolidWorks'te kontrol edin.")
                notes.append("Parça dosyası kaydedildi.")
                if warnings.value:
                    notes.append(f"Kaydetme uyarısı: {warnings.value}")
            else:
                notes.append("Bellekte uygulandı; dosyaya kaydedilmedi. SolidWorks'te kontrol edip kaydedin.")
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


def update_assembly(recipe, events, stop_event=None, *, preview=False, save=False):
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
                errors = _out(pythoncom.VT_I4)
                restored = app.ActivateDoc3(assembly_name, False, 1, errors)
                active = _value(app, "ActiveDoc")
                if (restored is None or errors.value or sw._document_name(restored) != assembly_name
                        or active is None or sw._document_name(active) != assembly_name):
                    raise RuntimeError("Önceki montaj etkinleştirilemedi.")
            except Exception as error:
                summary.update(state="error", error=str(error))
        if initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception as error:
                summary.update(state="error", error=f"COM kapanışı: {error}")
        events.put(("done", summary.copy()))
