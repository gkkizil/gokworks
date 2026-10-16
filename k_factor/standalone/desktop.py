"""Small standalone desktop for comparing the two K/R engines on one part."""

import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback

import customtkinter as ctk

from gui.icons import make_logo, set_window_icon
from gui.theme import BG, PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT, PRIMARY_TEXT, SECONDARY, RED, UI_FONT
from gui.typography import check_turkish_fonts
from k_factor.standalone.desktop_controller import native_executable, report_directory, run_pair


class KrDesktop(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.title("GOKWORKS · K/R denemesi")
        self.geometry("880x710")
        self.minsize(740, 620)
        self.configure(fg_color=BG)
        set_window_icon(self)
        check_turkish_fonts(self)
        self.events = queue.Queue()
        self.busy = False
        self.selected = None
        self.folder = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)

        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.grid(row=0, column=0, padx=24, pady=(22, 16), sticky="ew")
        heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(heading, text="K / R denemesi", font=(UI_FONT, 26, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(heading, text="C# ve Python motorlarını aynı sac parçasında karşılaştırın.",
                     font=(UI_FONT, 13), text_color=MUTED).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.logo = make_logo(126)
        ctk.CTkLabel(heading, text="", image=self.logo).grid(row=0, column=1, rowspan=2, padx=(14, 0))

        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14, border_color=BORDER, border_width=1)
        card.grid(row=1, column=0, padx=24, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="SolidWorks'te bir sac parçayı ayrı pencerede açın.",
                     text_color=TEXT, font=(UI_FONT, 14, "bold")).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(card, text="İlk denemeyi bir kopyada yapın. Dosyalar otomatik kaydedilmez.",
                     text_color=MUTED, font=(UI_FONT, 12)).grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")
        self.read_button = ctk.CTkButton(card, text="1. Parçayı oku", height=38, width=155,
                                         fg_color=ACCENT, text_color=PRIMARY_TEXT, command=lambda: self.start("inspect"))
        self.read_button.grid(row=0, column=1, rowspan=2, padx=18, pady=18)
        self.part_label = ctk.CTkLabel(card, text="Henüz parça okunmadı", anchor="w", text_color=MUTED,
                                       font=(UI_FONT, 12), wraplength=700)
        self.part_label.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=2, column=0, padx=24, pady=16, sticky="ew")
        for column in range(3):
            form.grid_columnconfigure(column, weight=1)
        self.values, self.entries = {}, []
        for column, (key, label, default) in enumerate((
            ("thickness_mm", "Sac kalınlığı · mm", ""),
            ("k_factor", "Yazılacak K faktörü", "0,274"),
            ("radius_mm", "Yazılacak iç yarıçap · mm", "1,5"),
        )):
            ctk.CTkLabel(form, text=label, text_color=MUTED, font=(UI_FONT, 12)).grid(row=0, column=column, sticky="w", padx=(0, 12))
            value = ctk.StringVar(value=default)
            entry = ctk.CTkEntry(form, textvariable=value, height=40, fg_color=INPUT, border_color=BORDER,
                                 text_color=TEXT, font=(UI_FONT, 15), state="disabled" if key == "thickness_mm" else "normal")
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 12 if column < 2 else 0), pady=(5, 12))
            self.values[key] = value
            self.entries.append(entry)
        self.verify_button = ctk.CTkButton(form, text="2. K/R yazma denemesi", height=42, fg_color=ACCENT,
                                           text_color=PRIMARY_TEXT, state="disabled", command=lambda: self.start("verify"))
        self.verify_button.grid(row=2, column=0, sticky="ew", columnspan=2, padx=(0, 12))
        self.folder_button = ctk.CTkButton(form, text="Rapor klasörü", height=42, fg_color=SECONDARY, text_color=TEXT,
                                           state="disabled", command=self.open_reports)
        self.folder_button.grid(row=2, column=2, sticky="ew")
        ctk.CTkLabel(form, text="Deneme: yaz → geri oku → eski değerleri geri yükle ve kontrol et.",
                     text_color=MUTED, font=(UI_FONT, 12)).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.log = ctk.CTkTextbox(self, fg_color=PANEL, text_color=TEXT, corner_radius=14,
                                  border_color=BORDER, border_width=1, font=(UI_FONT, 13), wrap="word", state="disabled")
        self.log.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
        self.status = ctk.CTkLabel(self, text="Hazır · Önce açık parçayı okuyun", anchor="w", text_color=MUTED, font=(UI_FONT, 12))
        self.status.grid(row=4, column=0, padx=24, pady=(0, 18), sticky="ew")
        self.append("Bu araç yalnız açık parçanın ana Sac-Levha ayarını ve etkin konfigürasyonunu dener.\nAlt bükümlerin özel ayarları değiştirilmez.")
        self.poll_id = self.after(60, self.poll)

    def append(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self, mode):
        if self.busy:
            return
        request = {"schema_version": 1, "mode": mode, "assignments": []}
        try:
            if mode == "verify":
                if self.selected is None:
                    raise ValueError("Önce parçayı okuyun.")
                assignment = {key: float(value.get().strip().replace(",", ".")) for key, value in self.values.items()}
                if not all(math.isfinite(value) for value in assignment.values()):
                    raise ValueError("Geçerli bir sayı girin.")
                before = self.selected["before"]
                if (before["bend_allowance_type"] == 2 and abs(assignment["k_factor"] - before["k_factor"]) < 1e-8
                        and abs(assignment["radius_mm"] - before["radius_mm"]) < 1e-6):
                    raise ValueError("Yazmayı sınamak için mevcut değerden farklı bir K veya R girin.")
                request.update(assignments=[assignment], document_path=self.selected["document_path"],
                               feature_name=before["feature_name"])
            from k_factor.standalone.python.probe import validate_request
            validate_request(request)
            self.folder = report_directory()
        except (ValueError, OSError) as error:
            self.status.configure(text=str(error), text_color=RED)
            return
        self.busy = True
        self.read_button.configure(state="disabled")
        self.verify_button.configure(state="disabled")
        for entry in self.entries:
            entry.configure(state="disabled")
        self.folder_button.configure(state="normal")
        self.status.configure(text="İşlem sürüyor…", text_color=ACCENT)
        self.append("Parça okunuyor…" if mode == "inspect" else "K/R yazma ve geri alma denemesi başladı.")
        threading.Thread(target=self.worker, args=(request, self.folder), daemon=False).start()

    def worker(self, request, folder):
        try:
            result = run_pair(request, folder, notify=lambda message: self.events.put(("progress", message)))
            self.events.put(("done", result))
        except Exception as error:
            try:
                (folder / "desktop-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            except OSError:
                pass
            self.events.put(("error", str(error)))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    self.status.configure(text=data, text_color=ACCENT)
                else:
                    self.busy = False
                    self.read_button.configure(state="normal")
                    for entry in self.entries[1:]:
                        entry.configure(state="normal")
                    if kind == "error":
                        self.selected = None
                        self.status.configure(text="Deneme tamamlanamadı · Ayrıntı aşağıda", text_color=RED)
                        self.append(data + "\n\nRapor klasörü: " + str(self.folder))
                    else:
                        self.selected = data["csharp"]
                        self.verify_button.configure(state="normal")
                        state = self.selected["before"]
                        self.values["thickness_mm"].set(f'{state["thickness_mm"]:.6f}'.rstrip("0").rstrip(".").replace(".", ","))
                        self.part_label.configure(text=Path(self.selected["document_path"]).name + " · " + self.selected["configuration"])
                        if data["comparison"]["status"] == "inspection_match":
                            current_k = f'{state["k_factor"]:g}' if state["k_factor"] is not None else "K tabanlı değil"
                            message = f'İki motor aynı sac değerlerini okudu.\nKalınlık: {state["thickness_mm"]:g} mm · Mevcut K: {current_k} · Mevcut R: {state["radius_mm"]:g} mm'
                        else:
                            target = self.selected["after"]
                            message = f'İki motor da K={target["k_factor"]:g} ve R={target["radius_mm"]:g} mm değerlerini yazıp geri okudu.\nEski değerler iki motorda da geri yüklendi ve doğrulandı. Dosya kaydedilmedi.'
                        self.status.configure(text="Tamamlandı · C# ve Python sonuçları uyumlu", text_color=ACCENT)
                        self.append(message + "\n\nRapor klasörü: " + str(self.folder))
        except queue.Empty:
            pass
        self.poll_id = self.after(60, self.poll)

    def open_reports(self):
        if self.folder is not None:
            import os
            os.startfile(self.folder)

    def close(self):
        if self.busy:
            self.status.configure(text="Geri alma kontrolünün tamamlanması bekleniyor. Bu sırada SolidWorks'ü kapatmayın.", text_color=MUTED)
            return
        self.after_cancel(self.poll_id)
        self.destroy()


def self_check(destination):
    result = {"status": "failed", "frozen": bool(getattr(sys, "frozen", False)),
              "platform": sys.platform, "solidworks_connection_tested": False}
    app = None
    try:
        from k_factor.standalone.runtime import prepare_generated_cache
        cache = prepare_generated_cache()
        if not cache or not (cache / "__init__.py").is_file():
            raise RuntimeError("Frozen MakePy cache was not initialized")
        import win32com.client.makepy
        import win32com.client.genpy
        import pythoncom
        import pywintypes
        from win32com.client import gencache
        assert not gencache.is_readonly and not gencache.is_zip
        # Exercise real typelib generation inside the frozen EXE using the
        # standard in-memory Windows dictionary; this does not open SolidWorks.
        from k_factor.standalone.python.probe import EarlyBound, Trace, report_template
        import win32com.client as client
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        try:
            raw = client.Dispatch("Scripting.Dictionary")
            info = raw._oleobj_.GetTypeInfo()
            typelib = info.GetContainingTypeLib()[0]
            guid, lcid, _platform, major, minor, _flags = typelib.GetLibAttr()
            module = gencache.EnsureModule(guid, lcid, major, minor, bValidateFile=True, bForDemand=False)
            binding = EarlyBound(client, pythoncom, module, Trace(report_template()))
            dictionary = binding.cast(raw, info.GetDocumentation(-1)[0])
            dictionary.Add("GOKWORKS-KR", 1)
            assert dictionary.Exists("GOKWORKS-KR") and dictionary.Count == 1
            dictionary.RemoveAll()
            result["generated_com_interface_test"] = "Scripting.Dictionary passed"
        finally:
            pythoncom.CoUninitialize()
        native = native_executable()
        checked = subprocess.run([str(native), "--self-test"], check=True, capture_output=True, text=True,
                                 encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        native_result = json.loads(checked.stdout)
        assert native_result["status"] == "passed"
        app = KrDesktop()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(str(args))
        for width, height in ((880, 710), (740, 620), (1100, 780)):
            app.geometry(f"{width}x{height}")
            app.update()
        assert not errors, errors
        assert app.read_button.cget("state") == "normal" and app.verify_button.cget("state") == "disabled"
        result.update(status="passed", tk=app.tk.call("info", "patchlevel"), writable_makepy_cache=True,
                      native_self_test=native_result, standalone_gui_opened=True, required_python_installed=False,
                      required_dotnet_installed=False)
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app.close()
        Path(destination).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["status"] == "passed" else 2


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        return self_check(sys.argv[2])
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GOKWORKS.KRProbe")
    app = KrDesktop()
    app.mainloop()
    return 0
