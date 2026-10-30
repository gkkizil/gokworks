"""Safe native flat export, including explicit body/configuration selections."""

import os
import base64
from collections import Counter
import math
from pathlib import Path
import re
from uuid import uuid4
from contextlib import nullcontext

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
ALREADY_OPEN = 128  # swFileLoadWarning_e.swFileLoadWarning_AlreadyOpen
ASSEMBLY = 2
SAVE_SILENT_REFERENCED = 1 | 4  # swSaveAsOptions_Silent | swSaveAsOptions_SaveReferenced


class CountCancelled(Exception):
    pass


class SaveDocumentsError(RuntimeError):
    pass


class SourceRestoreError(RuntimeError):
    pass


def _late_bound(app):
    # Preview sessions intentionally return raw PyIDispatch. It has Invoke /
    # GetIDsOfNames, but no _oleobj_ and no Python attribute named ActiveDoc.
    # DumbDispatch accepts either the raw pointer or a generated wrapper and
    # preserves late-bound BYREF handling in the legacy export path.
    if hasattr(app, "_oleobj_") or (
        callable(getattr(app, "Invoke", None)) and callable(getattr(app, "GetIDsOfNames", None))
    ):
        return win32com.client.dynamic.DumbDispatch(app)
    return app


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


def save_modified_documents(app, *, extra=()):
    """User-authorized Save All, via silent native saves, never UI commands.

    Parts can dirty their parent assemblies when saved. Re-read the flags
    until all documents are clean; preflight all dirty files before writing.
    Preview code never calls this function.
    """
    saved, notes = [], []
    try:
        if hasattr(app, '_FlagAsMethod'):
            app._FlagAsMethod('GetDocuments')
        for attempt in range(128):
            documents = {}
            for model in (*(_value(app, 'GetDocuments') or ()), *extra):
                if model is None:
                    continue
                path = _value(model, 'GetPathName')
                key = _part_key(path, '')[0] if path else ('unsaved', _value(model, 'GetTitle'))
                documents.setdefault(key, model)
            dirty = []
            for model in documents.values():
                if not _value(model, 'GetSaveFlag'):
                    continue
                path = _value(model, 'GetPathName')
                title = path or _value(model, 'GetTitle')
                if not path or Path(path).suffix.lower() not in ('.sldprt', '.sldasm', '.slddrw'):
                    raise SaveDocumentsError(f'Otomatik kayıt yapılamadı: {title}. Belgeyi önce SolidWorks dosyası olarak kaydedin.')
                if _value(model, 'IsOpenedReadOnly'):
                    raise SaveDocumentsError(f'Otomatik kayıt yapılamadı; belge salt okunur: {title}')
                dirty.append(model)
            if not dirty:
                return saved, notes
            # SaveReferenced lets an assembly save its referenced parts too.
            dirty.sort(key=lambda model: 0 if _value(model, 'GetType') == ASSEMBLY else 1)
            for model in dirty:
                if not _value(model, 'GetSaveFlag'):
                    continue  # Already saved through an assembly's references.
                path = _value(model, 'GetPathName')
                errors, warnings = _out_integer(), _out_integer()
                model = _late_bound(model)
                if hasattr(model, '_FlagAsMethod'):
                    model._FlagAsMethod('Save3')
                result = model.Save3(SAVE_SILENT_REFERENCED, errors, warnings)
                if isinstance(result, tuple) and len(result) == 3:
                    ok, error_code, warning_code = result
                else:
                    ok, error_code, warning_code = _success(result), errors.value, warnings.value
                if not ok or error_code:
                    raise SaveDocumentsError(f'Otomatik kayıt başarısız: {path}. SolidWorks hata kodu: {error_code}')
                if _value(model, 'GetSaveFlag'):
                    raise SaveDocumentsError(f'Otomatik kayıt sonrasında belge hâlâ değiştirilmiş görünüyor: {path}')
                saved.append(path)
                if warning_code:
                    notes.append(f'Kaydetme uyarısı: {path} · kod {warning_code}')
        raise SaveDocumentsError('Belgeler kayıt sırasında tekrar değişiyor; otomatik kayıt tamamlanamadı.')
    except SaveDocumentsError:
        raise
    except Exception as error:
        raise SaveDocumentsError(f'SolidWorks otomatik kayıt API hatası: {error}') from error


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


def assembly_quantities(app, stop_event=None, *, references=None):
    """Aktif montajın fiziksel parça örneklerini dosya+konfigürasyonla say.

    BOM satırları/kullanıcı adet özellikleri kullanılmaz. Gizli ve BOM dışı
    bileşenler sayılır; bastırılmış bileşenler ve onların alt dalları sayılmaz.
    Aynı alt montajın her örneği ayrı dolaşılır, dosya bazında tekilleştirilmez.
    references verilirse karşılaştırma anahtarlarının özgün dosya yolu ve
    konfigürasyon adları bu sözlüğe yazılır; COM'a bu özgün adlar gönderilir.
    """
    assembly = _value(app, "ActiveDoc")
    if assembly is None or _value(assembly, "GetType") != ASSEMBLY:
        raise RuntimeError("Montajdaki toplam adet için SolidWorks'te ana montajı etkinleştirin.")
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
        raise RuntimeError("Aktif montaj SpeedPak konfigürasyonunda. Toplam adet için tam montaj konfigürasyonunu etkinleştirin.")
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
            if references is not None:
                references.setdefault(key, (str(path), str(config)))
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


def named_destinations(part, source, output, formats, thickness_mm, quantity,
                       group_by_thickness=False):
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
    folder = Path(output)
    if group_by_thickness:
        folder /= f"{thickness.replace('.', ',')} mm"
    return [folder / relative.parent / f"{stem}.{kind}"
            for kind in normalize_formats(formats)]


def find_parts(source_folder, include_subfolders, stop_event=None):
    source = Path(source_folder)
    if not source.is_dir():
        raise ValueError("Kaynak klasörü bulunamadı.")
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
        # Publishing is complete once the destination link exists. Temporary
        # cleanup belongs to the caller and must not turn a saved file into a
        # failed export if unlinking is refused.


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


def _restore_export_configuration(model, configuration):
    if model is None or configuration is None:
        return
    if _value(model.ConfigurationManager.ActiveConfiguration, 'Name') != configuration:
        if not _success(model.ShowConfiguration2(configuration)):
            raise SourceRestoreError('Önceki kaynak konfigürasyonu açılamadı.')
        if _value(model.ConfigurationManager.ActiveConfiguration, 'Name') != configuration:
            raise SourceRestoreError('Önceki kaynak konfigürasyonu doğrulanamadı.')


def preview_identity(model, body):
    """Optional read-only provenance for the preview; never gates an export."""
    identity = {}
    try:
        path = _value(model, 'GetPathName')
        stamp = Path(path).stat()
        identity['source_stamp'] = (stamp.st_size, stamp.st_mtime_ns)
    except Exception:
        pass
    try:
        stamp = _value(model, 'GetUpdateStamp')
        if type(stamp) is int: identity['update_stamp'] = stamp
    except Exception:
        pass
    try:
        data = model.Extension.GetPersistReference3(body)
        if data:
            identity['body_ref'] = 'persist:' + base64.b64encode(bytes(int(v) & 255 for v in data)).decode('ascii')
    except Exception:
        pass
    return identity


def export_one_part(app, part, targets, overwrite=False, bend_lines=False,
                    target_builder=None, output_paths=None, output_results=None, output_identity=None,
                    save_modified=False, stop_event=None, sheet=None, selection_session=None):
    """Açınımı aktar; yalnızca bu çağrının açtığı belgeyi kapat.

    Normal toplu aktarım save_modified=True ile sessiz Tümünü Kaydet uygular.
    Önizleme ve doğrudan çağrılar varsayılan olarak kaynakları kaydetmez.

    Çok gövdeli parça için taramadan gelen kesin sheet kimliği gerekir.
    Her biçimin sonucu ayrıdır. Hazır çıktı ile başarısız biçim birlikteyse
    parça kısmen tamamlandı olarak raporlanır; başarısız biçim saklanmaz.
    """
    targets = [Path(target) for target in targets]
    records = [] if output_results is None else output_results
    records.clear()
    def record(target, state, detail):
        records.append(dict(format=target.suffix[1:].upper(), path=str(target),
                            status=state, detail=detail))
    try:
        pending = _pending_targets(targets, overwrite) if target_builder is None else []
    except (OSError, ValueError) as error:
        return "error", str(error)
    if target_builder is None and not pending:
        for target in targets:
            record(target, "skipped", "Dosya zaten var; yeniden aktarılmadı.")
        return "skipped", "Seçilen çıktı dosyaları zaten var."
    opened_here = False
    model = None
    previous_name = None
    activated_here = False
    visibility_changed = False
    save_failed = False
    original_config = None
    restore_failed = ''
    source_validated = False
    notes, outcomes = [], []
    def checkpoint():
        if stop_event is not None and stop_event.is_set():
            raise CountCancelled()
    try:
        checkpoint()
        # GetActiveObject can return a cached makepy wrapper. Explicit BYREF
        # VARIANT outputs below require late-bound calls (pywin32 variant docs).
        app = _late_bound(app)
        previous = _value(app, "ActiveDoc")
        if previous is not None:
            previous_name = _document_name(previous)
        if save_modified:
            saved, warnings = save_modified_documents(app)
            notes.extend(warnings)
            if saved:
                notes.append(f'SolidWorks: {len(saved)} belge otomatik kaydedildi.')
        checkpoint()
        model = app.GetOpenDocumentByName(str(part))
        if model is None:
            errors, warnings = _out_integer(), _out_integer()
            model = app.OpenDoc6(str(part), PART, SILENT, "", errors, warnings)
            # OpenDoc6 can return a document already loaded by the user's session.
            opened_here = model is not None and not (warnings.value & ALREADY_OPEN)
            activated_here = model is not None  # Opening may also change ActiveDoc.
            if model is None or errors.value:
                raise RuntimeError(f"Parça açılamadı. SolidWorks hata kodu: {errors.value}")
            if warnings.value:
                notes.append(f"Açma uyarısı: {warnings.value}")
        if _value(model, "GetType") != PART:
            raise RuntimeError("Dosya bir parça değil.")
        part_api = _late_bound(selection_session.part(model)) if selection_session is not None else _part_api(model)
        original_config = _value(model.ConfigurationManager.ActiveConfiguration, 'Name')
        requested_config = sheet.get('configuration', '') if sheet else ''
        if requested_config and requested_config != original_config:
            errors = _out_integer()
            activated_here = True
            activated = app.ActivateDoc3(_document_name(model), False, DONT_REBUILD, errors)
            if activated is None or errors.value or not _success(model.ShowConfiguration2(requested_config)):
                raise RuntimeError('İstenen kaynak konfigürasyonu açılamadı: '+requested_config)
            if _value(model.ConfigurationManager.ActiveConfiguration, 'Name') != requested_config:
                raise RuntimeError('İstenen kaynak konfigürasyonu doğrulanamadı.')
        bodies = part_api.GetBodies2(SOLID_BODY, False) or ()
        if sheet:
            if not sheet.get('body_ref') or not sheet.get('flat_ref') or selection_session is None:
                raise RuntimeError('Gövde/Flat-Pattern kimliği eksik; yeniden tarayın.')
            matches = [body for body in bodies if selection_session.persistent_ref(model, body) == sheet['body_ref']]
            if len(matches) != 1:
                raise RuntimeError('Seçilen sac gövdesi artık bulunamıyor; yeniden tarayın.')
            selected_body = matches[0]
        elif len(bodies) != 1:
            raise RuntimeError("Bu aktarım tek gövdeli sac parçalar içindir. Çok gövdeli parçayı gövde bazında ayrı .SLDPRT dosyalarına ayırın.")
        else:
            selected_body = bodies[0]
        if not _value(selected_body, "IsSheetMetal"):
            raise RuntimeError("Aktif konfigürasyondaki gövde sac metal değil.")
        model_path = _value(model, "GetPathName")
        if not model_path:
            raise RuntimeError("Parça önce SolidWorks'te kaydedilmeli.")
        if _part_key(model_path, "") != _part_key(os.path.abspath(str(part)), ""):
            raise RuntimeError("SolidWorks istenen kaynak yerine farklı bir parça döndürdü; aktarım yapılmadı.")
        config = _value(model.ConfigurationManager.ActiveConfiguration, "Name")
        source_validated = True
        if output_identity is not None:
            output_identity.update(preview_identity(model, selected_body))
            output_identity['bend_lines'] = bool(bend_lines)
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
        if pending and save_modified:
            saved, warnings = save_modified_documents(app, extra=(model,))
            notes.extend(warnings)
            if saved:
                notes.append(f'SolidWorks: {len(saved)} belge otomatik kaydedildi.')
        # Default orientation; no selection, suppression or preference changes.
        alignment = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
        views = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
        for target in targets:
            checkpoint()
            kind = target.suffix[1:].upper()
            if target not in pending:
                outcomes.append("skipped")
                notes.append(f"{kind}: zaten var, atlandı")
                record(target, "skipped", "Dosya zaten var; yeniden aktarılmadı.")
                continue
            # Keep the temporary basename short: appending a UUID to a long
            # part name can exceed Windows/filesystem limits before publishing.
            temporary = target.with_name(f".gokworks-{uuid4().hex}{target.suffix}")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Resolve the exact body and FlatPattern again for EACH format.
                # ExportToDWG2 must see one selected FlatPattern, never all bodies.
                guard = (selection_session.selected_flat(model, sheet['body_ref'], sheet['flat_ref'], stop_event,
                                                         feature_name=sheet.get('flat_pattern',''))
                         if sheet else nullcontext())
                try:
                    with guard:
                        checkpoint()
                        exported = part_api.ExportToDWG2(str(temporary), model_path, SHEET_METAL,
                                                        True, alignment, False, False, options, views)
                except Exception as error:
                    from modules.cad_converter.api import RestoreError
                    if isinstance(error, RestoreError):
                        raise SourceRestoreError(str(error)) from error
                    raise
                _restore_export_configuration(model, config)
                checkpoint()
                if not _success(exported):
                    raise RuntimeError("SolidWorks açınımı aktaramadı. Sac metal/açınım unsurunu kontrol edin.")
                _validate_output(temporary)
                if sheet and target.suffix.lower()=='.dxf':
                    from .geometry_check import validate_flat_geometry
                    validate_flat_geometry(temporary,stop_event)
                checkpoint()
                try:
                    _publish(temporary, target, overwrite)
                    outcomes.append("success")
                    notes.append(f"{kind}: açınım aktarıldı")
                    record(target, "success", "Açınım doğrulandı ve kaydedildi.")
                except FileExistsError:
                    outcomes.append("skipped")
                    notes.append(f"{kind}: aktarım sırasında hedef oluştu, atlandı")
                    record(target, "skipped", "Aktarım sırasında hedef oluştu; üzerine yazılmadı.")
            except (CountCancelled, SourceRestoreError):
                raise
            except Exception as error:
                from modules.cad_converter.models import Cancelled
                if isinstance(error,Cancelled):raise CountCancelled() from error
                outcomes.append("error")
                notes.append(f"{kind}: {error}")
                record(target, "error", str(error))
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as error:
                    notes.append(f"Geçici dosya temizlenemedi: {error}")
        status = ("partial" if "error" in outcomes and any(item in outcomes for item in ("success", "skipped"))
                  else "error" if "error" in outcomes else "success" if "success" in outcomes else "skipped")
    except CountCancelled:
        status = 'partial' if 'success' in outcomes else 'skipped'
        notes.append('Durduruldu; devam eden geçici çıktı yayımlanmadı, sonraki biçimlere geçilmedi.')
    except Exception as error:
        status = "error"
        notes.append(str(error))
        save_failed = isinstance(error, (SaveDocumentsError, SourceRestoreError))
        if isinstance(error, SourceRestoreError):
            restore_failed = str(error)
    finally:
        if model is not None and original_config is not None:
            try:
                _restore_export_configuration(model, original_config)
            except Exception as error:
                restore_failed = f'Açınım sonrası kaynak konfigürasyon geri getirilemedi; belge kaydedilmedi veya kapatılmadı: {error}'
                save_failed = True
                notes.append(restore_failed)
        if save_modified and model is not None and source_validated and not save_failed:
            try:
                saved, warnings = save_modified_documents(app, extra=(model,))
                notes.extend(warnings)
                if saved:
                    notes.append(f'SolidWorks: {len(saved)} belge otomatik kaydedildi.')
                if output_identity is not None:
                    output_identity.update(preview_identity(model, bodies[0]) if 'bodies' in locals() and bodies else {})
            except SaveDocumentsError as error:
                save_failed = True
                status = 'partial' if any(item == 'success' for item in outcomes) else 'error'
                notes.append(str(error))
        if save_failed:
            if output_identity is not None:
                output_identity['native_save_error'] = '; '.join(notes)
            notes.append('Kayıt başarısız olduğu için açık belgeler kapatılmadı; aktarım durduruldu.')
        if visibility_changed and not opened_here and model is not None:
            try:
                model.Visible = False
            except Exception as error:
                notes.append(f"Önceki belge görünürlüğü geri yüklenemedi: {error}")
        if opened_here and model is not None and not save_failed:
            try:
                app.CloseDoc(_value(model, "GetTitle"))
            except Exception as error:
                notes.append(f"Parça kapatılamadı: {error}")
        if previous_name and (opened_here or activated_here) and not save_failed:
            try:
                errors = _out_integer()
                restored = app.ActivateDoc3(previous_name, False, DONT_REBUILD, errors)
                if restored is None or errors.value:
                    raise RuntimeError(f"SolidWorks hata kodu: {errors.value}")
            except Exception as error:
                notes.append(f"Önceki belge etkinleştirilemedi: {error}")
        # Release child dispatch wrappers before a fatal restoration exception
        # can retain this frame past the owning STA's CoUninitialize.
        model = part_api = previous = active = activated = restored = selected_body = app = None
        bodies = matches = ()
        if restore_failed:
            raise SourceRestoreError(restore_failed)
    return status, "; ".join(notes)


def export_parts(source_folder, output_folder, include_subfolders, overwrite_existing,
                 events, stop_event=None, formats=("dxf",), bend_lines=False,
                 group_by_thickness=False, *, items=None, naming=()):
    """Dosya bazında olaylar gönder; sayaçlar çıktı biçimlerini değil parçaları sayar."""
    if items is not None:
        return export_selection(items, source_folder, output_folder, formats, events, stop_event,
                                overwrite=overwrite_existing, bend_lines=bend_lines,
                                group_by_thickness=group_by_thickness, naming=naming)
    summary = {"state": "completed", "total": 0, "processed": 0,
               "succeeded": 0, "partial": 0, "skipped": 0, "failed": 0, "error": "", "warnings": [],
               "unexported_configurations": 0}
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
        app = _late_bound(app)
        active = _value(app, 'ActiveDoc')
        if active is None or _value(active, 'GetType') != ASSEMBLY:
            raise RuntimeError("Montajdaki toplam adet için SolidWorks'te ana montajı etkinleştirin.")
        events.put(('phase', 'Değiştirilmiş SolidWorks belgeleri otomatik kaydediliyor…'))
        saved, warnings = save_modified_documents(app)
        events.put(('log', f'SolidWorks otomatik kayıt: {len(saved)} belge.'))
        summary['warnings'].extend(warnings)
        events.put(("phase", "Aktif montajdaki toplam adetler hesaplanıyor…"))
        references = {}
        quantities, assembly_name, assembly_config = assembly_quantities(app, stop_event, references=references)
        assembly_paths = {path for path, config in quantities}
        configurations = {}
        for key in sorted(quantities):
            configurations.setdefault(key[0], []).append((key, references[key][1]))
        events.put(("log", f"Adet kaynağı: {assembly_name} · Konfigürasyon: {assembly_config} · Alt montajlar dahil."))
        events.put(("log", "Dosya adı: PARÇAADI - kalınlık mm - toplam adet. Aynı parça/konfigürasyon sayılır; bastırılmış bileşenler sayılmaz."))
        if group_by_thickness:
            events.put(("log", "Çıktılar sac kalınlığına göre klasörlenir (örn. 1,5 mm); kaynak alt klasörleri korunur."))
        for index, part in enumerate(parts, 1):
            if stop_event is not None and stop_event.is_set():
                summary["state"] = "cancelled"
                break
            targets, metadata, outputs = [], {}, []
            events.put(("current", part))
            def build_targets(model, configuration):
                quantity = quantities.get(_part_key(part, configuration), 0)
                if not quantity:
                    raise ValueError(f"Parçanın '{configuration}' konfigürasyonu aktif montajda bulunamadı. Montajdaki konfigürasyonu parçada etkinleştirin.")
                thickness = sheet_thickness_mm(model)
                others = [(name, quantities[key]) for key, name in configurations[_part_key(part, "")[0]]
                          if key != _part_key(part, configuration)]
                metadata.update(thickness_mm=thickness, quantity=quantity, configuration=configuration,
                                unexported_configurations=others)
                return named_destinations(part, source, output, formats, thickness, quantity,
                                          group_by_thickness)

            if _part_key(part, "")[0] not in assembly_paths:
                status, detail = "skipped", "Parça aktif montajda kullanılmıyor; aktarılmadı."
            else:
                status, detail = export_one_part(app, part, targets, overwrite_existing, bend_lines,
                                                target_builder=build_targets, output_paths=targets,
                                                output_results=outputs, output_identity=metadata,
                                                save_modified=True, stop_event=stop_event)
            others = metadata.get('unexported_configurations', ())
            if others:
                summary['unexported_configurations'] += len(others)
                detail += ('; Aktarılmayan montaj konfigürasyonları: '
                           + ', '.join(f'{name} ({quantity} adet)' for name, quantity in others)
                           + '. Bu işlem yalnız parçanın etkin konfigürasyonunu aktarır.')
            summary[{"success": "succeeded", "partial": "partial", "skipped": "skipped", "error": "failed"}[status]] += 1
            summary["processed"] = index
            available = [item['path'] for item in outputs if item['status'] in ('success', 'skipped')]
            events.put(("result", {"source": part, "output": " | ".join(available), "outputs": outputs,
                                    "status": status, "detail": detail, **metadata}))
            events.put(("counts", dict(summary)))
            events.put(("progress", (index, len(parts))))
            if metadata.get('native_save_error'):
                raise SaveDocumentsError(metadata['native_save_error'])
            if stop_event is not None and stop_event.is_set():
                summary['state'] = 'cancelled'
                break
        if summary['unexported_configurations']:
            summary['warnings'].append(
                f"Montajdaki {summary['unexported_configurations']} parça konfigürasyonu bu aktarımda "
                "dışarıda kaldı; ayrıntılar sonuç listesinde.")
    except CountCancelled:
        summary["state"] = "cancelled"
    except SourceRestoreError as error:
        summary['state'] = 'error'
        summary['error'] = str(error)
        summary['native_restore_failed'] = True
        events.put(('log', f'İşlem durdu: {error}'))
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
            summary["warnings"].append(message)
            events.put(("log", message))
        finally:
            events.put(("done", summary))


def export_selection(items, source, output, formats, events, stop=None, *, overwrite=False,
                     bend_lines=False, group_by_thickness=False, naming=(), session_factory=None):
    """One worker STA, body-specific exports, no source saves or implicit rescans.

    Preserve the old callable export_parts signature for script callers. The
    DXF workbench passes its checked sheet inventory through `items` instead.
    """
    from .sheetmetal import Session
    from .inventory import plan_destinations
    from modules.cad_converter.api import RestoreError
    from modules.cad_converter.models import checkpoint, Cancelled
    summary = dict(state='completed', total=len(items), processed=0, succeeded=0,
                   partial=0, skipped=0, failed=0, warnings=[], error='')
    active_item=None;outputs=[];metadata={}
    try:
        checkpoint(stop)
        if any(not item.get('exportable') or not item.get('body_ref') or not item.get('flat_ref') for item in items):
            raise ValueError('Seçimde doğrulanmamış bir sac gövdesi var; yeniden tarayın.')
        plans = plan_destinations(items, source, output, formats, group_by_thickness, naming)
        events.put(('total', len(items)))
        if not items:
            summary['state'] = 'empty'
            return
        with (session_factory or Session)() as session:
            for item in items:
                checkpoint(stop)
                active_item=item
                model = None
                outputs, metadata = [], {}
                events.put(('sheet_current', item['sheet_id']))
                try:
                    # Open missing documents read-only, in the owning STA. The
                    # legacy single-export primitive sees an already-open doc.
                    model = session.document(item['source'])
                    with session.configuration(model, item['configuration']):
                        # Material/property edits need not advance the geometry
                        # stamp. Refresh only this body, immediately before use.
                        fresh, _ = session.describe(model, item['source'], item['configuration'], stop,
                                                    body_ref=item['body_ref'])
                        match = [row for row in fresh if row['body_ref']==item['body_ref']]
                        if len(match)!=1 or not match[0]['exportable'] or match[0]['flat_ref']!=item['flat_ref']:
                            raise ValueError('Sac/Flat-Pattern eşleşmesi değişmiş; yeniden tarayın.')
                        if not math.isclose(match[0]['thickness_mm'],item['thickness_mm'],abs_tol=1e-6,rel_tol=1e-9):
                            raise ValueError('Sac kalınlığı taramadan sonra değişmiş; yeniden tarayın.')
                        if match[0].get('material','')!=item.get('material',''):
                            raise ValueError('Gövdenin malzemesi taramadan sonra değişmiş; yeniden tarayın.')
                        status, detail = export_one_part(session.app, item['source'], plans[item['sheet_id']],
                            overwrite, bend_lines, output_results=outputs, output_identity=metadata,
                            stop_event=stop, sheet=item, selection_session=session)
                except (Cancelled, RestoreError, SourceRestoreError):
                    raise
                except Exception as error:
                    status, detail = 'error', str(error)
                finally:
                    model = None
                summary['processed'] += 1
                summary[dict(success='succeeded',partial='partial',skipped='skipped',error='failed')[status]] += 1
                available = [r['path'] for r in outputs if r['status'] in ('success','skipped')]
                events.put(('sheet_result', dict(item, **metadata, status=status, detail=detail,
                           outputs=outputs, output=' | '.join(available))))
                active_item=None
                events.put(('progress',(summary['processed'],len(items))))
                checkpoint(stop)
    except Cancelled:
        summary['state'] = 'cancelled'
        if active_item is not None:
            available = [r['path'] for r in outputs if r['status'] in ('success','skipped')]
            state = 'partial' if any(r['status']=='success' for r in outputs) else 'skipped'
            summary['processed'] += 1
            summary['partial' if state=='partial' else 'skipped'] += 1
            events.put(('sheet_result',dict(active_item,**metadata,status=state,
                       detail='İşlem durduruldu; tamamlanmış çıktılar korundu.' if state=='partial' else 'İşlem durduruldu; yeni çıktı oluşturulmadı.',
                       outputs=outputs,output=' | '.join(available))))
            events.put(('progress',(summary['processed'],len(items))))
    except (RestoreError, SourceRestoreError) as error:
        summary.update(state='error', error=str(error), native_restore_failed=True)
        if active_item is not None:
            available=[r['path'] for r in outputs if r['status'] in ('success','skipped')]
            state='partial' if any(r['status']=='success' for r in outputs) else 'error'
            summary['processed']+=1;summary['partial' if state=='partial' else 'failed']+=1
            events.put(('sheet_result',dict(active_item,**metadata,status=state,detail=str(error),
                       outputs=outputs,output=' | '.join(available))))
    except Exception as error:
        summary.update(state='error', error=str(error))
    finally:
        events.put(('done',summary))
