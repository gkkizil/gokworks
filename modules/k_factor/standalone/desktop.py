"""Write the user's K/R values to the active part through the native SW API."""

import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback

import customtkinter as ctk

from shared.icons import make_logo, set_window_icon
from shared.theme import BG, PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT, PRIMARY_TEXT, SECONDARY, RED, UI_FONT
from shared.typography import check_turkish_fonts
from modules.k_factor.standalone.desktop_controller import native_executable, report_directory, run_native
from modules.k_factor.standalone.python.probe import ProbeError, validate_request


class KrDesktop(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.title("GOKWORKS · K/R ataması")
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
        ctk.CTkLabel(heading, text="K faktörü / yarıçap", font=(UI_FONT, 26, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(heading, text="Girdiğiniz değerleri açık parçanın Sac-Levha parametrelerine uygulayın.",
                     font=(UI_FONT, 13), text_color=MUTED).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.logo = make_logo(126)
        ctk.CTkLabel(heading, text="", image=self.logo).grid(row=0, column=1, rowspan=2, padx=(14, 0))

        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14, border_color=BORDER, border_width=1)
        card.grid(row=1, column=0, padx=24, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="SolidWorks'te bir sac parçayı ayrı pencerede açın.",
                     text_color=TEXT, font=(UI_FONT, 14, "bold")).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(card, text="Başarılı atama açık parçada kalır. Dosya otomatik kaydedilmez.",
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
        self.apply_button = ctk.CTkButton(form, text="2. K/R uygula", height=42, fg_color=ACCENT,
                                          text_color=PRIMARY_TEXT, state="disabled", command=lambda: self.start("apply"))
        self.apply_button.grid(row=2, column=0, sticky="ew", columnspan=2, padx=(0, 12))
        self.folder_button = ctk.CTkButton(form, text="Rapor klasörü", height=42, fg_color=SECONDARY, text_color=TEXT,
                                           state="disabled", command=self.open_reports)
        self.folder_button.grid(row=2, column=2, sticky="ew")
        ctk.CTkLabel(form, text="Yaz → geri oku → doğrula. Başarılı atamada yeni K/R değerleri korunur.",
                     text_color=MUTED, font=(UI_FONT, 12)).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.log = ctk.CTkTextbox(self, fg_color=PANEL, text_color=TEXT, corner_radius=14,
                                  border_color=BORDER, border_width=1, font=(UI_FONT, 13), wrap="word", state="disabled")
        self.log.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
        self.status = ctk.CTkLabel(self, text="Hazır · Önce açık parçayı okuyun", anchor="w", text_color=MUTED, font=(UI_FONT, 12))
        self.status.grid(row=4, column=0, padx=24, pady=(0, 18), sticky="ew")
        self.append("Bu araç açık parçanın ana Sac-Levha K faktörünü ve iç yarıçapını değiştirir.\nBaşarılı atama geri alınmaz. Dosyayı SolidWorks'te kendiniz kaydedebilirsiniz.")
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
            if mode not in ("inspect", "apply"):
                raise ValueError("Parçayı okuyun veya K/R uygula düğmesini kullanın.")
            if mode == "apply":
                if self.selected is None:
                    raise ValueError("Önce parçayı okuyun.")
                assignment = {key: float(value.get().strip().replace(",", ".")) for key, value in self.values.items()}
                if not all(math.isfinite(value) for value in assignment.values()):
                    raise ValueError("Geçerli bir sayı girin.")
                if not 0 <= assignment["k_factor"] <= 1:
                    raise ValueError("K faktörü 0 ile 1 arasında olmalı.")
                if assignment["radius_mm"] < 0:
                    raise ValueError("İç yarıçap sıfır veya daha büyük olmalı.")
                before = self.selected["after"] if self.selected.get("status") == "applied" else self.selected["before"]
                request.update(assignments=[assignment], document_path=self.selected["document_path"],
                               configuration=self.selected["configuration"], feature_name=before["feature_name"],
                               expected_state=before)
            validate_request(request)
            self.folder = report_directory()
        except (ProbeError, ValueError, OSError) as error:
            self.status.configure(text=str(error), text_color=RED)
            return
        self.busy = True
        self.read_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")
        for entry in self.entries:
            entry.configure(state="disabled")
        self.folder_button.configure(state="normal")
        self.status.configure(text="İşlem sürüyor…", text_color=ACCENT)
        self.append("Parça okunuyor…" if mode == "inspect" else "Girdiğiniz K/R değerleri Sac-Levha'ya uygulanıyor…")
        threading.Thread(target=self.worker, args=(request, self.folder), daemon=False).start()

    def worker(self, request, folder):
        try:
            result = run_native(request, folder, notify=lambda message: self.events.put(("progress", message)))
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
                        self.status.configure(text="İşlem tamamlanamadı · Ayrıntı aşağıda", text_color=RED)
                        self.append(data + "\n\nRapor klasörü: " + str(self.folder))
                    else:
                        self.selected = data["csharp"]
                        self.apply_button.configure(state="normal")
                        applied = self.selected["status"] == "applied"
                        state = self.selected["after"] if applied else self.selected["before"]
                        self.values["thickness_mm"].set(f'{state["thickness_mm"]:.6f}'.rstrip("0").rstrip(".").replace(".", ","))
                        self.part_label.configure(text=Path(self.selected["document_path"]).name + " · " + self.selected["configuration"])
                        if not applied:
                            current_k = f'{state["k_factor"]:g}' if state["k_factor"] is not None else "K tabanlı değil"
                            message = f'Sac-Levha parametreleri okundu.\nKalınlık: {state["thickness_mm"]:g} mm · Mevcut K: {current_k} · Mevcut R: {state["radius_mm"]:g} mm'
                        else:
                            target = self.selected["after"]
                            message = f'K={target["k_factor"]:g} ve R={target["radius_mm"]:g} mm Sac-Levha\'ya uygulandı ve geri okunarak doğrulandı.\nYeni değerler açık parçada kaldı. Dosyayı SolidWorks\'te kaydedebilirsiniz.'
                        self.status.configure(text="Uygulandı · Yeni değerler açık parçada" if applied else "Parça okundu · K ve R girip uygulayın", text_color=ACCENT)
                        if self.selected.get("warnings"):
                            self.append(f'{len(self.selected["warnings"])} teknik not işlem raporuna eklendi.')
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
            self.status.configure(text="İşlemin tamamlanması bekleniyor. Bu sırada SolidWorks'ü kapatmayın.", text_color=MUTED)
            return
        self.after_cancel(self.poll_id)
        self.destroy()


def self_check(destination):
    result = {"status": "failed", "frozen": bool(getattr(sys, "frozen", False)),
              "platform": sys.platform, "solidworks_connection_tested": False,
              "desktop_engine": "csharp", "assignment_mode": "apply",
              "python_com_required_for_assignment": False}
    app = None
    try:
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
        assert app.read_button.cget("state") == "normal" and app.apply_button.cget("state") == "disabled"
        assert app.apply_button.cget("text") == "2. K/R uygula"
        result.update(status="passed", tk=app.tk.call("info", "patchlevel"),
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
