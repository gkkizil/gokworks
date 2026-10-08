"""Çizim dosyalarını, dosya bazında sonuç bildirerek PDF'e aktarır."""

import os
from pathlib import Path
from uuid import uuid4

try:
    import pythoncom
    import win32com.client
except ImportError:
    pythoncom = None
    win32com = None

from solidworks.connection import connect_to_solidworks

DRAWING = 3
SILENT = 1
PDF_DATA = 1
SPECIFIED_SHEETS = 3


def read_com_value(document, member_name):
    value = getattr(document, member_name)
    return value() if callable(value) else value


def find_drawings(source_folder, include_subfolders, stop_event=None):
    source = Path(source_folder)
    if not source.is_dir():
        raise ValueError("Kaynak klasör bulunamadı.")
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


def export_one_drawing(app, drawing, destination, overwrite):
    """Tüm sayfaları geçici PDF'e aktar; başarılı dosyayı hedefe taşı."""
    destination = Path(destination)
    if destination.exists() and not overwrite:
        return "skipped", "PDF zaten var."
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.gokworks-{uuid4().hex}.pdf")
    opened_here = False
    model = None
    notes = []
    try:
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

        data = app.GetExportFileData(PDF_DATA)
        if data is None:
            raise RuntimeError("PDF dışa aktarma ayarları alınamadı.")
        names = read_com_value(model, "GetSheetNames")
        if isinstance(names, str):
            names = (names,)
        if not names:
            raise RuntimeError("Çizimde PDF'e aktarılacak sayfa bulunamadı.")
        sheets = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, tuple(names))
        if not _com_success(data.SetSheets(SPECIFIED_SHEETS, sheets)):
            raise RuntimeError("Teknik resmin tüm sayfaları seçilemedi.")
        data.ViewPdfAfterSaving = False
        errors, warnings = _out_integer(), _out_integer()
        saved = model.Extension.SaveAs(str(temporary), 0, SILENT, data, errors, warnings)
        if not _com_success(saved) or errors.value:
            raise RuntimeError(f"PDF kaydedilemedi. SolidWorks hata kodu: {errors.value}")
        _validate_pdf(temporary)
        if overwrite:
            os.replace(temporary, destination)
        elif os.name == "nt":
            # Windows rename mevcut dosyanın üzerine yazmaz.
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
        if warnings.value:
            notes.append(f"Kaydetme uyarısı: {warnings.value}")
        status, detail = "success", "; ".join(notes) or "Tüm sayfalar aktarıldı."
    except FileExistsError:
        status, detail = "skipped", "Aktarım sırasında aynı isimli PDF oluşturuldu."
    except Exception as error:
        status, detail = "error", str(error)
    finally:
        # Yalnızca bu çağrının ürettiği benzersiz geçici dosya temizlenir.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if opened_here and model is not None:
            try:
                app.CloseDoc(read_com_value(model, "GetTitle"))
            except Exception as error:
                notes.append(f"Çizim kapatılamadı: {error}")
    if notes and status == "success":
        detail = "; ".join(notes)
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
        events.put(("log", f"{len(drawings)} teknik resim bulundu. Tüm sayfalar PDF'e aktarılacak."))

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
        if initialized:
            pythoncom.CoUninitialize()
        events.put(("done", summary))
