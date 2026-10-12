"""Çizim dosyalarını, dosya bazında sonuç bildirerek PDF dosyalarına aktarır."""

import os
from pathlib import Path
from uuid import uuid4

try:
    import pythoncom
    import win32com.client
    import win32com.client.dynamic
except ImportError:
    pythoncom = None
    win32com = None

from solidworks.connection import connect_to_solidworks

DRAWING = 3
SILENT = 1
PDF_DATA = 1
SPECIFIED_SHEETS = 3
DONT_REBUILD = 1


def read_com_value(document, member_name):
    value = getattr(document, member_name)
    if hasattr(value, "_oleobj_"):
        return value
    return value() if callable(value) else value


def _late_bound(value):
    # Cached makepy wrappers infer BYREF types; explicit VARIANT outputs
    # require dynamic calls, including the nested ModelDocExtension.SaveAs.
    return win32com.client.dynamic.DumbDispatch(value) if hasattr(value, "_oleobj_") else value


def _document_name(model):
    return read_com_value(model, "GetPathName") or read_com_value(model, "GetTitle")


def _path_key(path):
    return os.path.abspath(str(path)).replace("\\", "/").lower() if path else ""


def _drawing_api(model):
    if hasattr(model, "GetSheetNames"):
        return model
    for interface in ("IDrawingDoc", "DrawingDoc"):
        try:
            drawing = win32com.client.CastTo(model, interface)
            if hasattr(drawing, "GetSheetNames"):
                return drawing
        except Exception:
            continue
    raise RuntimeError("SolidWorks teknik resim API'sine (IDrawingDoc) erişilemiyor.")


def find_drawings(source_folder, include_subfolders, stop_event=None):
    source = Path(source_folder)
    if not source.is_dir():
        raise ValueError("Kaynak klasörü bulunamadı.")
    drawings = []

    def scan_error(error):
        raise OSError(f"Klasör okunamadı: {error.filename}") from error

    for current, folders, filenames in os.walk(source, onerror=scan_error):
        if stop_event is not None and stop_event.is_set():
            break
        folders.sort(key=str.casefold)
        for filename in filenames:
            if filename.casefold().endswith(".slddrw") and not filename.startswith("~$"):
                drawings.append(str(Path(current) / filename))
        if not include_subfolders:
            break
    return sorted(drawings, key=str.casefold)


def pdf_destination(drawing, source, output):
    return Path(output) / Path(drawing).relative_to(source).with_suffix(".pdf")


def _com_success(value):
    return bool(value[0] if isinstance(value, tuple) else value)


def _out_integer():
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _validate_pdf(path):
    if not path.is_file():
        raise RuntimeError("SolidWorks PDF dosyasını oluşturmadı.")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise RuntimeError("Oluşturulan dosya geçerli bir PDF başlığı içermiyor.")
        size = path.stat().st_size
        stream.seek(max(0, size - 1024))
        if size < 16 or not stream.read().rstrip().endswith(b"%%EOF"):
            raise RuntimeError("PDF dosyası eksik veya dosya sonu bulunamadı.")


def export_one_drawing(app, drawing, destination, overwrite):
    """Tüm sayfaları geçici PDF dosyasına aktar; başarılı dosyayı hedefe taşı."""
    destination = Path(destination)
    if destination.exists():
        if not destination.is_file():
            return "error", "PDF çıktı yolu bir dosya değil."
        if not overwrite:
            return "skipped", "PDF zaten var."
    temporary = destination.with_name(f".gokworks-{uuid4().hex}.pdf")
    opened_here = False
    model = None
    previous_name = None
    activated_here = False
    notes = []
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        app = _late_bound(app)
        previous = read_com_value(app, "ActiveDoc")
        if previous is not None:
            previous_name = _document_name(previous)
        model = app.GetOpenDocumentByName(str(drawing))
        if model is None:
            errors, warnings = _out_integer(), _out_integer()
            model = app.OpenDoc6(str(drawing), DRAWING, SILENT, "", errors, warnings)
            opened_here = model is not None
            if model is None or errors.value:
                raise RuntimeError(f"Çizim açılamadı. SolidWorks hata kodu: {errors.value}")
            if warnings.value:
                notes.append(f"Açma uyarısı: {warnings.value}")
        if read_com_value(model, "GetType") != DRAWING:
            raise RuntimeError("Dosya bir teknik resim değil.")
        if _path_key(read_com_value(model, "GetPathName")) != _path_key(drawing):
            raise RuntimeError("SolidWorks istenen teknik resim yerine farklı belge döndürdü; aktarım yapılmadı.")

        data = app.GetExportFileData(PDF_DATA)
        if data is None:
            raise RuntimeError("PDF dışa aktarma ayarları alınamadı.")
        names = read_com_value(_drawing_api(model), "GetSheetNames")
        if isinstance(names, str):
            names = (names,)
        if not names:
            raise RuntimeError("Çizimde PDF dosyasına aktarılacak sayfa bulunamadı.")
        sheets = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, tuple(names))
        if not _com_success(data.SetSheets(SPECIFIED_SHEETS, sheets)):
            raise RuntimeError("Teknik resmin tüm sayfaları seçilemedi.")
        data.ViewPdfAfterSaving = False
        data.ExportAs3D = False
        active = read_com_value(app, "ActiveDoc")
        model_name = _document_name(model)
        if active is None or os.path.normcase(_document_name(active)) != os.path.normcase(model_name):
            errors = _out_integer()
            activated = app.ActivateDoc3(model_name, False, DONT_REBUILD, errors)
            activated_here = True
            if activated is None or errors.value:
                raise RuntimeError(f"Teknik resim etkinleştirilemedi. SolidWorks hata kodu: {errors.value}")
            if _path_key(read_com_value(activated, "GetPathName")) != _path_key(drawing):
                raise RuntimeError("SolidWorks farklı bir belgeyi etkinleştirdi; aktarım yapılmadı.")
        active = read_com_value(app, "ActiveDoc")
        if active is None or _path_key(read_com_value(active, "GetPathName")) != _path_key(drawing):
            raise RuntimeError("Aktif SolidWorks belgesi kaynak teknik resim değil; aktarım yapılmadı.")
        errors, warnings = _out_integer(), _out_integer()
        extension = _late_bound(read_com_value(model, "Extension"))
        saved = extension.SaveAs(str(temporary), 0, SILENT, data, errors, warnings)
        if not _com_success(saved) or errors.value:
            raise RuntimeError(f"PDF kaydedilemedi. SolidWorks hata kodu: {errors.value}")
        _validate_pdf(temporary)
        if warnings.value:
            notes.append(f"Kaydetme uyarısı: {warnings.value}")
        try:
            if overwrite:
                os.replace(temporary, destination)
            elif os.name == "nt":
                # Windows rename mevcut dosyanın üzerine yazmaz.
                os.rename(temporary, destination)
            else:
                os.link(temporary, destination)
                temporary.unlink()
            status, detail = "success", "Tüm sayfalar aktarıldı."
        except FileExistsError:
            status, detail = "skipped", "Aktarım sırasında aynı isimli PDF oluşturuldu."
    except Exception as error:
        status, detail = "error", str(error)
    finally:
        # Yalnızca bu çağrının ürettiği benzersiz geçici dosya temizlenir.
        try:
            temporary.unlink(missing_ok=True)
        except OSError as error:
            notes.append(f"Geçici PDF temizlenemedi: {error}")
        if opened_here and model is not None:
            try:
                app.CloseDoc(read_com_value(model, "GetTitle"))
            except Exception as error:
                notes.append(f"Çizim kapatılamadı: {error}")
        if previous_name and (opened_here or activated_here):
            try:
                errors = _out_integer()
                restored = app.ActivateDoc3(previous_name, False, DONT_REBUILD, errors)
                if restored is None or errors.value:
                    raise RuntimeError(f"SolidWorks hata kodu: {errors.value}")
            except Exception as error:
                notes.append(f"Önceki belge etkinleştirilemedi: {error}")
    if notes:
        detail = "; ".join([detail, *notes])
    return status, detail


def export_drawings(source_folder, output_folder, include_subfolders,
                    overwrite_existing, events, stop_event=None):
    """Arayüz kuyruğuna durum, sonuç ve bitiş olayları gönder."""
    summary = {"state": "completed", "total": 0, "processed": 0,
               "succeeded": 0, "skipped": 0, "failed": 0, "error": ""}
    initialized = False
    try:
        source = Path(source_folder).resolve()
        output = Path(output_folder).resolve()
        events.put(("phase", "Teknik resimler taranıyor…"))
        drawings = find_drawings(source, include_subfolders, stop_event)
        summary["total"] = len(drawings)
        events.put(("files", drawings))
        events.put(("total", len(drawings)))
        if stop_event is not None and stop_event.is_set():
            summary["state"] = "cancelled"
            return
        if not drawings:
            summary["state"] = "empty"
            events.put(("log", "Kaynak klasörde .SLDDRW dosyası bulunamadı."))
            return
        if pythoncom is None or win32com is None:
            raise RuntimeError("pywin32 kurulu değil. Projenin bağımlılıklarını yükleyin.")
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir():
            raise ValueError("PDF kayıt yolu bir klasör değil.")
        pythoncom.CoInitialize()
        initialized = True
        events.put(("phase", "SolidWorks'e bağlanılıyor…"))
        app = connect_to_solidworks()
        events.put(("log", f"{len(drawings)} teknik resim bulundu. Her teknik resmin tüm sayfaları tek PDF dosyasına aktarılacak."))

        for index, drawing in enumerate(drawings, 1):
            if stop_event is not None and stop_event.is_set():
                summary["state"] = "cancelled"
                break
            target = pdf_destination(drawing, source, output)
            events.put(("current", drawing))
            status, detail = export_one_drawing(app, drawing, target, overwrite_existing)
            counter = {"success": "succeeded", "skipped": "skipped", "error": "failed"}[status]
            summary[counter] += 1
            summary["processed"] = index
            events.put(("result", {"source": drawing, "output": str(target),
                                    "status": status, "detail": detail}))
            events.put(("counts", dict(summary)))
            events.put(("progress", (index, len(drawings))))
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
