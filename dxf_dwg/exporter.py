"""Aktif konfigürasyondaki tek gövdeli sac parçaları DXF/DWG açınımına aktarır."""

import os
from collections import Counter
import math
from pathlib import Path
import re
from uuid import uuid4

try:
    import ezdxf
except ImportError:
    ezdxf = None

try:
    import pythoncom
    import win32com.client
    import win32com.client.dynamic
except ImportError:
    pythoncom = None
    win32com = None

from solidworks.connection import connect_to_solidworks

PART, SILENT, SOLID_BODY = 1, 1, 0
SHEET_METAL, FLAT_GEOMETRY, BEND_LINES = 1, 1, 4
DONT_REBUILD = 1  # swRebuildOnActivation_e.swDontRebuildActiveDoc
ASSEMBLY = 2


class CountCancelled(Exception):
    pass


def _value(obj, name):
    value = getattr(obj, name)
    # pywin32 CDispatch objects are callable too: calling ActiveDoc would
    # invoke its default COM member, not read the document property.
    if hasattr(value, "_oleobj_"):
        return value
    return value() if callable(value) else value


def _document_name(model):
    # Full paths distinguish documents with identical titles. Unsaved prior
    # documents have no path and can only be restored by title.
    return _value(model, "GetPathName") or _value(model, "GetTitle")


def _success(value):
    return bool(value[0] if isinstance(value, tuple) else value)


def _out_integer():
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _part_api(model):
    # OpenDoc6 may return an IModelDoc2 wrapper rather than the IPartDoc API.
    if hasattr(model, "GetBodies2") and hasattr(model, "ExportToDWG2"):
        return model
    for interface in ("IPartDoc", "PartDoc"):
        try:
            part = win32com.client.CastTo(model, interface)
            if hasattr(part, "GetBodies2") and hasattr(part, "ExportToDWG2"):
                return part
        except Exception:
            continue
    raise RuntimeError("SolidWorks parça API'sine (IPartDoc) erişilemiyor. SolidWorks/pywin32 COM kurulumunu kontrol edin.")


def _part_key(path, configuration):
    normalized = os.path.normpath(str(path).replace("\\", "/")).replace("\\", "/")
    # Windows-style case normalization must not expand letters: casefold()
    # merges distinct file/configuration names such as Straße and Strasse.
    return normalized.lower(), str(configuration).lower()


def assembly_quantities(app, stop_event=None):
    """Aktif montajın fiziksel parça örneklerini dosya+konfigürasyonla say.

    BOM satırları/kullanıcı adet özellikleri kullanılmaz. Gizli ve BOM dışı
    bileşenler sayılır; bastırılmış bileşenler ve onların alt dalları sayılmaz.
    Aynı alt montajın her örneği ayrı dolaşılır, dosya bazında tekilleştirilmez.
    """
    assembly = _value(app, "ActiveDoc")
    if assembly is None or _value(assembly, "GetType") != ASSEMBLY:
        raise RuntimeError("Montajdaki toplam adet için SolidWorks'te ana montajı aktif yapın.")
    assembly_api = assembly
    if not hasattr(assembly_api, "ResolveAllLightWeightComponents"):
        for interface in ("IAssemblyDoc", "AssemblyDoc"):
            try:
                assembly_api = win32com.client.CastTo(assembly, interface)
                if hasattr(assembly_api, "ResolveAllLightWeightComponents"):
                    break
            except Exception:
                continue
        else:
            raise RuntimeError("SolidWorks montaj API'sine erişilemiyor.")
    if stop_event is not None and stop_event.is_set():
        raise CountCancelled()
    resolved = assembly_api.ResolveAllLightWeightComponents(True)
    if resolved not in (0, 2):  # swResolveOk / swResolveNotPerformed
        raise RuntimeError(f"Montaj bileşenleri çözümlenemedi. SolidWorks hata kodu: {resolved}")
    configuration = assembly.ConfigurationManager.ActiveConfiguration
    if hasattr(configuration, "IsSpeedPak") and _value(configuration, "IsSpeedPak"):
        raise RuntimeError("Aktif montaj SpeedPak konfigürasyonunda. Toplam adet için tam montaj konfigürasyonunu aktif yapın.")
    root = configuration.GetRootComponent3(True)
    if root is None:
        raise RuntimeError("Montaj bileşen ağacı okunamadı.")
    counts = Counter()
    stack = [(child, frozenset()) for child in (_value(root, "GetChildren") or ())]
    while stack:
        if stop_event is not None and stop_event.is_set():
            raise CountCancelled()
        component, ancestors = stack.pop()
        state = _value(component, "GetSuppression")
        if state == 0:  # swComponentSuppressed
            continue
        if state not in (2, 3):  # fully resolved / resolved
            raise RuntimeError("Montajda çözümlenmemiş bir bileşen var. Adet hesabı eksik olabileceği için aktarım durduruldu.")
        path = _value(component, "GetPathName")
        config = _value(component, "ReferencedConfiguration")
        if not path or not config:
            raise RuntimeError("Montajdaki bir bileşenin dosya yolu veya konfigürasyonu okunamadı.")
        key = _part_key(path, config)
        extension = str(path).lower()
        if extension.endswith(".sldprt"):
            counts[key] += 1
        elif extension.endswith(".sldasm"):
            if key in ancestors:
                raise RuntimeError("Montaj ağacında döngü bulundu; adet hesabı tamamlanamadı.")
            if _value(component, "GetModelDoc2") is None:
                raise RuntimeError(f"Alt montaj yüklenmemiş; toplam adet hesaplanamadı: {path}")
            if hasattr(component, "IsSpeedPak") and _value(component, "IsSpeedPak"):
                raise RuntimeError(f"SpeedPak alt montajın tam bileşen ağacını açın: {path}")
            # GetChildren is instance-specific and uses ReferencedConfiguration.
            children = _value(component, "GetChildren") or ()
            stack.extend((child, ancestors | {key}) for child in children)
        else:
            raise RuntimeError(f"Montaj bileşeninin dosya türü tanınmadı: {path}")
    return counts, _document_name(assembly), _value(configuration, "Name")


def sheet_thickness_mm(model):
    """Aktif SheetMetal unsurunun metre cinsinden kalınlığını mm'ye çevir."""
    first = _value(model, "FirstFeature")
    stack = [(first, False)] if first is not None else []
    seen, thicknesses = set(), []
    empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
    while stack:
        feature, subfeature = stack.pop()
        kind = _value(feature, "GetTypeName2")
        # The same feature can appear in both lists. Its top-level successor
        # differs from its subfeature successor, so visit each context once.
        identity = (_value(feature, "Name"), kind, subfeature)
        if identity in seen:
            continue
        seen.add(identity)
        next_feature = _value(feature, "GetNextSubFeature" if subfeature else "GetNextFeature")
        if next_feature is not None:
            stack.append((next_feature, subfeature))
        child = _value(feature, "GetFirstSubFeature")
        if child is not None:
            stack.append((child, True))
        if kind != "SheetMetal":
            continue
        suppressed = feature.IsSuppressed2(1, empty)  # swThisConfiguration
        if suppressed is None:
            raise RuntimeError("Sac metal unsurunun aktif konfigürasyon durumu okunamadı.")
        if _success(suppressed):
            continue
        definition = _value(feature, "GetDefinition")
        if definition is None:
            raise RuntimeError("Sac metal unsurunun kalınlık verisi okunamadı.")
        thickness = float(_value(definition, "Thickness")) * 1000
        if not math.isfinite(thickness) or thickness <= 0:
            raise RuntimeError("Sac kalınlığı geçersiz.")
        thicknesses.append(thickness)
    if not thicknesses:
        raise RuntimeError("Aktif konfigürasyondaki sac kalınlığı okunamadı.")
    if any(not math.isclose(value, thicknesses[0], rel_tol=1e-9, abs_tol=1e-6)
           for value in thicknesses[1:]):
        raise RuntimeError("Birden fazla farklı sac kalınlığı bulundu; dosya adı oluşturulamadı.")
    return thicknesses[0]


def named_destinations(part, source, output, formats, thickness_mm, quantity):
    if not math.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("Sac kalınlığı geçersiz.")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise ValueError("Montaj adedi pozitif bir tam sayı olmalı.")
    thickness = f"{thickness_mm:.6f}".rstrip("0").rstrip(".")
    if thickness == "0":
        raise ValueError("Sac kalınlığı dosya adına yazılamayacak kadar küçük.")
    relative = Path(part).relative_to(source)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", relative.stem).rstrip(" .")
    if not name:
        raise ValueError("Parça adı geçersiz.")
    stem = f"{name} - {thickness} mm - {quantity} adet"
    return [Path(output) / relative.parent / f"{stem}.{kind}"
            for kind in normalize_formats(formats)]


def find_parts(source_folder, include_subfolders, stop_event=None):
    source = Path(source_folder)
    if not source.is_dir():
        raise ValueError("Kaynak klasör bulunamadı.")
    parts = []

    def scan_error(error):
        raise OSError(f"Klasör okunamadı: {error.filename}") from error

    for current, folders, filenames in os.walk(source, onerror=scan_error):
        if stop_event is not None and stop_event.is_set():
            break
        folders.sort(key=str.casefold)
        parts.extend(str(Path(current) / name) for name in filenames
                     if name.casefold().endswith(".sldprt") and not name.startswith("~$"))
        if not include_subfolders:
            break
    return sorted(parts, key=str.casefold)


def normalize_formats(formats):
    if isinstance(formats, str):
        formats = (formats,)
    normalized = tuple(dict.fromkeys(str(item).lower().lstrip(".") for item in formats))
    if not normalized or any(item not in ("dxf", "dwg") for item in normalized):
        raise ValueError("En az bir çıktı biçimi seçin: DXF veya DWG.")
    return normalized


def destinations(part, source, output, formats):
    relative = Path(part).relative_to(source)
    return [Path(output) / relative.with_suffix(f".{kind}")
            for kind in normalize_formats(formats)]


def _validate_output(path):
    if not path.is_file() or path.stat().st_size < 16:
        raise RuntimeError("SolidWorks geçerli bir çıktı dosyası oluşturmadı.")
    with path.open("rb") as stream:
        header = stream.read(24)
        if path.suffix.lower() == ".dwg":
            if not re.match(rb"AC10\d{2}", header):
                raise RuntimeError("DWG dosya başlığı geçersiz.")
            return
        stream.seek(max(0, path.stat().st_size - 1024))
        tail = stream.read()
        if header.startswith(b"AutoCAD Binary DXF\r\n\x1a\x00"):
            # R12 uses one-byte group codes; R13+ uses two-byte codes.
            if not tail.endswith(b"\x00EOF\x00"):
                raise RuntimeError("İkili DXF dosyası eksik veya dosya sonu bulunamadı.")
        else:
            lines = [line.strip() for line in tail.rstrip().splitlines()]
            if len(lines) < 2 or lines[-1] != b"EOF" or lines[-2] != b"0":
                raise RuntimeError("DXF dosyası eksik veya dosya sonu bulunamadı.")
    if ezdxf is None:
        raise RuntimeError("DXF doğrulaması için ezdxf gerekli. Projenin requirements.txt bağımlılıklarını yükleyin.")
    try:
        document = ezdxf.readfile(path)
        audit = document.audit()
    except Exception as error:
        raise RuntimeError(f"DXF dosyası okunamadı: {error}") from error
    if audit.errors or audit.fixes:
        raise RuntimeError("DXF dosyası yapı hatası içeriyor veya onarım gerektiriyor; çıktı yayımlanmadı.")
    if not document.modelspace():
        raise RuntimeError("DXF dosyasında açınım geometrisi bulunamadı.")


def _publish(temporary, destination, overwrite):
    if overwrite:
        os.replace(temporary, destination)
    elif os.name == "nt":
        os.rename(temporary, destination)
    else:
        os.link(temporary, destination)
        temporary.unlink()


def _pending_targets(targets, overwrite):
    if not targets or any(target.suffix.lower() not in (".dxf", ".dwg") for target in targets):
        raise ValueError("Geçersiz DXF/DWG hedefi.")
    pending = []
    for target in targets:
        if target.exists():
            if not target.is_file():
                raise ValueError(f"DXF/DWG çıktı yolu bir dosya değil: {target}")
            if not overwrite:
                continue
        pending.append(target)
    return pending


def export_one_part(app, part, targets, overwrite=False, bend_lines=False,
                    target_builder=None, output_paths=None):
    """Kaynağı kaydetmeden açınımı aktar; yalnızca bu çağrının açtığı belgeyi kapat.

    Çok gövdeli parçalar eksik/üst üste geometri üretmek yerine hata döndürür.
    İki biçim seçilirse birindeki hata parçanın tamamında hata olarak raporlanır.
    """
    targets = [Path(target) for target in targets]
    try:
        pending = _pending_targets(targets, overwrite) if target_builder is None else []
    except (OSError, ValueError) as error:
        return "error", str(error)
    if target_builder is None and not pending:
        return "skipped", "Seçilen çıktı dosyaları zaten var."
    opened_here = False
    model = None
    previous_name = None
    activated_here = False
    visibility_changed = False
    notes, outcomes = [], []
    try:
        # GetActiveObject can return a cached makepy wrapper. Explicit BYREF
        # VARIANT outputs below require late-bound calls (pywin32 variant docs).
        if hasattr(app, "_oleobj_"):
            app = win32com.client.dynamic.DumbDispatch(app)
        previous = _value(app, "ActiveDoc")
        if previous is not None:
            previous_name = _document_name(previous)
        model = app.GetOpenDocumentByName(str(part))
        if model is None:
            errors, warnings = _out_integer(), _out_integer()
            model = app.OpenDoc6(str(part), PART, SILENT, "", errors, warnings)
            opened_here = model is not None
            if model is None or errors.value:
                raise RuntimeError(f"Parça açılamadı. SolidWorks hata kodu: {errors.value}")
            if warnings.value:
                notes.append(f"Açma uyarısı: {warnings.value}")
        if _value(model, "GetType") != PART:
            raise RuntimeError("Dosya bir parça değil.")
        part_api = _part_api(model)
        bodies = part_api.GetBodies2(SOLID_BODY, False) or ()
        if len(bodies) != 1:
            raise RuntimeError("Bu aktarım tek gövdeli sac parçalar içindir. Çok gövdeli parçayı gövde bazında ayrı .SLDPRT dosyalarına ayırın.")
        if not _value(bodies[0], "IsSheetMetal"):
            raise RuntimeError("Aktif konfigürasyondaki gövde sac metal değil.")
        model_path = _value(model, "GetPathName")
        if not model_path:
            raise RuntimeError("Parça önce SolidWorks'te kaydedilmeli.")
        if _part_key(model_path, "") != _part_key(os.path.abspath(str(part)), ""):
            raise RuntimeError("SolidWorks istenen kaynak yerine farklı bir parça döndürdü; aktarım yapılmadı.")
        config = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
        notes.append(f"Konfigürasyon: {config}")
        if target_builder is not None:
            targets = [Path(target) for target in target_builder(model, config)]
            if output_paths is not None:
                output_paths[:] = targets
            pending = _pending_targets(targets, overwrite)
            if not pending:
                notes.append("Seçilen çıktı dosyaları zaten var.")
        if pending and not _value(model, "Visible"):
            model.Visible = True
            visibility_changed = True
        active = _value(app, "ActiveDoc")
        active_path = _value(active, "GetPathName") if active is not None else ""
        if pending and _part_key(active_path, "") != _part_key(model_path, ""):
            errors = _out_integer()
            activated = app.ActivateDoc3(model_path, False, DONT_REBUILD, errors)
            # Activation may change ActiveDoc even when an error is reported.
            activated_here = True
            if activated is None or errors.value:
                raise RuntimeError(f"Parça etkinleştirilemedi. SolidWorks hata kodu: {errors.value}")
            if _part_key(_value(activated, "GetPathName"), "") != _part_key(model_path, ""):
                raise RuntimeError("SolidWorks farklı bir belgeyi etkinleştirdi; aktarım yapılmadı.")
        if pending:
            active = _value(app, "ActiveDoc")
            if active is None or _part_key(_value(active, "GetPathName"), "") != _part_key(model_path, ""):
                raise RuntimeError("Aktif SolidWorks belgesi kaynak parça değil; aktarım yapılmadı.")
        options = FLAT_GEOMETRY | (BEND_LINES if bend_lines else 0)
        # Default orientation; no selection, suppression, preferences or save.
        alignment = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
        views = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
        for target in targets:
            kind = target.suffix[1:].upper()
            if target not in pending:
                outcomes.append("skipped")
                notes.append(f"{kind}: zaten var, atlandı")
                continue
            # Keep the temporary basename short: appending a UUID to a long
            # part name can exceed Windows/filesystem limits before publishing.
            temporary = target.with_name(f".gokworks-{uuid4().hex}{target.suffix}")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                exported = part_api.ExportToDWG2(str(temporary), model_path, SHEET_METAL,
                                                True, alignment, False, False, options, views)
                if not _success(exported):
                    raise RuntimeError("SolidWorks açınımı aktaramadı. Sac metal/açınım unsurunu kontrol edin.")
                _validate_output(temporary)
                try:
                    _publish(temporary, target, overwrite)
                    outcomes.append("success")
                    notes.append(f"{kind}: açınım aktarıldı")
                except FileExistsError:
                    outcomes.append("skipped")
                    notes.append(f"{kind}: aktarım sırasında hedef oluştu, atlandı")
            except Exception as error:
                outcomes.append("error")
                notes.append(f"{kind}: {error}")
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as error:
                    notes.append(f"Geçici dosya temizlenemedi: {error}")
        status = "error" if "error" in outcomes else "success" if "success" in outcomes else "skipped"
    except Exception as error:
        status = "error"
        notes.append(str(error))
    finally:
        if visibility_changed and not opened_here and model is not None:
            try:
                model.Visible = False
            except Exception as error:
                notes.append(f"Önceki belge görünürlüğü geri yüklenemedi: {error}")
        if opened_here and model is not None:
            try:
                app.CloseDoc(_value(model, "GetTitle"))
            except Exception as error:
                notes.append(f"Parça kapatılamadı: {error}")
        if previous_name and (opened_here or activated_here):
            try:
                errors = _out_integer()
                restored = app.ActivateDoc3(previous_name, False, DONT_REBUILD, errors)
                if restored is None or errors.value:
                    raise RuntimeError(f"SolidWorks hata kodu: {errors.value}")
            except Exception as error:
                notes.append(f"Önceki belge etkinleştirilemedi: {error}")
    return status, "; ".join(notes)


def export_parts(source_folder, output_folder, include_subfolders, overwrite_existing,
                 events, stop_event=None, formats=("dxf",), bend_lines=False):
    """Dosya bazında olaylar gönder; sayaçlar çıktı biçimlerini değil parçaları sayar."""
    summary = {"state": "completed", "total": 0, "processed": 0,
               "succeeded": 0, "skipped": 0, "failed": 0, "error": ""}
    initialized = False
    try:
        formats = normalize_formats(formats)
        source = Path(source_folder).resolve()
        output = Path(output_folder).resolve()
        events.put(("phase", "Sac metal parçalar taranıyor…"))
        parts = find_parts(source, include_subfolders, stop_event)
        summary["total"] = len(parts)
        events.put(("files", parts))
        events.put(("total", len(parts)))
        if stop_event is not None and stop_event.is_set():
            summary["state"] = "cancelled"
            return
        if not parts:
            summary["state"] = "empty"
            events.put(("log", "Kaynak klasörde .SLDPRT dosyası bulunamadı."))
            return
        if pythoncom is None or win32com is None:
            raise RuntimeError("DXF/DWG aktarımı Windows, pywin32 ve açık SolidWorks oturumu gerektirir.")
        if "dxf" in formats and ezdxf is None:
            raise RuntimeError("DXF doğrulaması için ezdxf gerekli. Projenin requirements.txt bağımlılıklarını yükleyin.")
        output.mkdir(parents=True, exist_ok=True)
        pythoncom.CoInitialize()
        initialized = True
        app = connect_to_solidworks()
        if hasattr(app, "_oleobj_"):
            app = win32com.client.dynamic.DumbDispatch(app)
        events.put(("phase", "Aktif montajdaki toplam adetler hesaplanıyor…"))
        quantities, assembly_name, assembly_config = assembly_quantities(app, stop_event)
        assembly_paths = {path for path, config in quantities}
        events.put(("log", f"Adet kaynağı: {assembly_name} · Konfigürasyon: {assembly_config} · Alt montajlar dahil."))
        events.put(("log", "Dosya adı: PARÇAADI - kalınlık mm - toplam adet. Aynı parça/konfigürasyon sayılır; bastırılmış bileşenler sayılmaz."))
        for index, part in enumerate(parts, 1):
            if stop_event is not None and stop_event.is_set():
                summary["state"] = "cancelled"
                break
            targets, metadata = [], {}
            events.put(("current", part))
            def build_targets(model, configuration):
                quantity = quantities.get(_part_key(part, configuration), 0)
                if not quantity:
                    raise ValueError(f"Parçanın '{configuration}' konfigürasyonu aktif montajda bulunamadı. Montajdaki konfigürasyonu parçada aktif yapın.")
                thickness = sheet_thickness_mm(model)
                metadata.update(thickness_mm=thickness, quantity=quantity)
                return named_destinations(part, source, output, formats, thickness, quantity)

            if _part_key(part, "")[0] not in assembly_paths:
                status, detail = "skipped", "Parça aktif montajda kullanılmıyor; aktarılmadı."
            else:
                status, detail = export_one_part(app, part, targets, overwrite_existing, bend_lines,
                                                target_builder=build_targets, output_paths=targets)
            summary[{"success": "succeeded", "skipped": "skipped", "error": "failed"}[status]] += 1
            summary["processed"] = index
            events.put(("result", {"source": part, "output": " | ".join(map(str, targets)),
                                    "status": status, "detail": detail, **metadata}))
            events.put(("counts", dict(summary)))
            events.put(("progress", (index, len(parts))))
    except CountCancelled:
        summary["state"] = "cancelled"
    except Exception as error:
        summary["state"] = "error"
        summary["error"] = str(error)
        events.put(("log", f"İşlem durdu: {error}"))
    finally:
        try:
            if initialized:
                pythoncom.CoUninitialize()
        except Exception as error:
            message = f"SolidWorks bağlantısı temizlenemedi: {error}"
            summary["state"] = "error"
            summary["error"] = "; ".join(filter(None, (summary["error"], message)))
            events.put(("log", message))
        finally:
            events.put(("done", summary))
