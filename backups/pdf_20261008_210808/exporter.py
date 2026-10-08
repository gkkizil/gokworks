"""SolidWorks teknik resimlerini PDF'e aktarma işlemleri."""

import os

try:
    import pythoncom
    import win32com.client
except ImportError:
    pythoncom = None
    win32com = None

from solidworks.connection import connect_to_solidworks

def read_com_value(document, member_name):
    """COM üyesi değer veya metot olarak sunulmuşsa ikisini de oku."""
    value = getattr(document, member_name)
    return value() if callable(value) else value


def find_drawings(source_folder, include_subfolders):
    """Kaynak klasördeki teknik resimleri bul."""
    drawings = []

    if include_subfolders:
        for current_folder, _subfolders, filenames in os.walk(source_folder):
            for filename in filenames:
                if filename.lower().endswith(".slddrw") and not filename.startswith("~$"):
                    drawings.append(os.path.join(current_folder, filename))
    else:
        for filename in os.listdir(source_folder):
            full_path = os.path.join(source_folder, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(".slddrw") and not filename.startswith("~$"):
                drawings.append(full_path)

    return sorted(drawings, key=str.lower)


def export_drawings(source_folder, output_folder, include_subfolders, overwrite_existing, events):
    """Bulunan çizimleri açık SolidWorks oturumu üzerinden PDF'e aktar."""
    initialized_com = False
    succeeded = 0
    skipped = 0
    failed = 0

    try:
        if pythoncom is None or win32com is None:
            raise RuntimeError(
                "pywin32 kurulu değil. PyCharm Terminal'inde şu komutu çalıştırın:\n"
                ".venv\\Scripts\\python.exe -m pip install pywin32"
            )

        pythoncom.CoInitialize()
        initialized_com = True

        solidworks = connect_to_solidworks()

        drawing_files = find_drawings(source_folder, include_subfolders)
        if not drawing_files:
            events.put(("log", "Kaynak klasörde .slddrw dosyası bulunamadı."))
            events.put(("done", (0, 0, 0)))
            return

        total = len(drawing_files)
        events.put(("total", total))
        events.put(("log", f"{total} teknik resim bulundu. PDF aktarımı başlıyor."))

        for index, drawing_path in enumerate(drawing_files, start=1):
            relative_folder = os.path.relpath(os.path.dirname(drawing_path), source_folder)
            if relative_folder == ".":
                relative_folder = ""

            pdf_folder = os.path.join(output_folder, relative_folder)
            pdf_path = os.path.join(pdf_folder, os.path.splitext(os.path.basename(drawing_path))[0] + ".pdf")
            opened_here = False
            model = None

            try:
                if os.path.exists(pdf_path) and not overwrite_existing:
                    skipped += 1
                    events.put(("log", f"ATLANDI (PDF zaten var): {pdf_path}"))
                    events.put(("progress", (index, total)))
                    continue

                os.makedirs(pdf_folder, exist_ok=True)

                # Daha önce açık olan çizimi kullan; kullanıcıya ait belgeyi kapatma.
                model = solidworks.GetOpenDocumentByName(drawing_path)
                if model is None:
                    load_errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    load_warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    model = solidworks.OpenDoc6(drawing_path, 3, 1, "", load_errors, load_warnings)
                    opened_here = model is not None

                    if model is None:
                        raise RuntimeError(f"SolidWorks dosyayı açamadı. Hata kodu: {load_errors.value}")
                    if load_errors.value:
                        raise RuntimeError(f"SolidWorks dosyayı açarken hata verdi. Hata kodu: {load_errors.value}")

                pdf_data = solidworks.GetExportFileData(1)
                if pdf_data is None:
                    raise RuntimeError("SolidWorks PDF dışa aktarma ayarlarını oluşturamadı.")

                pdf_data.ViewPdfAfterSaving = False
                save_errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                save_warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                save_result = model.Extension.SaveAs(pdf_path, 0, 1, pdf_data, save_errors, save_warnings)
                save_success = save_result[0] if isinstance(save_result, tuple) else save_result

                if not save_success or not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) == 0:
                    raise RuntimeError(
                        f"PDF kaydedilemedi. Hata kodu: {save_errors.value}; uyarı kodu: {save_warnings.value}"
                    )

                succeeded += 1
                events.put(("log", f"BAŞARILI: {pdf_path}"))

            except Exception as error:
                failed += 1
                events.put(("log", f"HATALI: {drawing_path} | {error}"))

            finally:
                if opened_here and model is not None:
                    try:
                        solidworks.CloseDoc(read_com_value(model, "GetTitle"))
                    except Exception as error:
                        events.put(("log", f"Not: Açılan çizim kapatılamadı: {error}"))

                events.put(("progress", (index, total)))

        events.put(("done", (succeeded, skipped, failed)))

    except Exception as error:
        events.put(("log", f"İşlem başlatılamadı: {error}"))
        events.put(("done", (succeeded, skipped, failed)))

    finally:
        if initialized_com:
            pythoncom.CoUninitialize()
