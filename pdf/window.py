"""GOKWORKS'in PDF ekranı."""

import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from pdf.exporter import export_drawings, find_drawings
from pdf.settings import load_settings, save_settings, SETTINGS_PATH

BG = "#101316"
PANEL = "#191E23"
INPUT = "#11161B"
BORDER = "#2D353D"
TEXT = "#EDF2F5"
MUTED = "#95A3AE"
ACCENT = "#4AD7B3"
GREEN = "#66DBAB"
AMBER = "#E9BE70"
RED = "#F1848F"
LABELS = {"pending": "Bekliyor", "running": "İşleniyor", "success": "Başarılı",
          "skipped": "Atlandı", "error": "Hata"}


class GokworksPdfApp(ctk.CTk):
    def __init__(self, settings_path=SETTINGS_PATH):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()
        self.title("GOKWORKS • SolidWorks Otomasyonu")
        self.geometry("1140x780")
        self.minsize(1000, 690)
        self.configure(fg_color=BG)
        self.settings_path = settings_path
        saved = load_settings(settings_path)
        self.source_folder = tk.StringVar(self, value=str(saved.get("pdf_source", "")))
        self.output_folder = tk.StringVar(self, value=str(saved.get("pdf_output", "")))
        self.include_subfolders = tk.BooleanVar(self, value=saved.get("pdf_recursive", True) is True)
        self.overwrite_existing = tk.BooleanVar(self, value=saved.get("pdf_overwrite", False) is True)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.close_pending = False
        self._closed = False
        self.controls = []
        self.results = []
        self.row_ids = {}
        self.stat_values = {}
        self._build_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_id = self.after(80, self._process_events)

    def _label(self, parent, text, size=13, color=TEXT, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color,
                            font=ctk.CTkFont(family="Segoe UI", size=size,
                                            weight="bold" if bold else "normal"), **kwargs)

    def _button(self, parent, text, command, primary=False, **kwargs):
        return ctk.CTkButton(
            parent, text=text, command=command, corner_radius=8, height=38,
            fg_color=ACCENT if primary else "#253039",
            hover_color="#70E7C7" if primary else "#34434F",
            text_color="#10231D" if primary else TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), **kwargs)

    def _build_window(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#151B20")
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(30, 32))
        badge = ctk.CTkFrame(brand, width=38, height=38, fg_color="#203D35", corner_radius=9)
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        badge.grid_propagate(False)
        self._label(badge, "G", 23, ACCENT, True).place(relx=.5, rely=.5, anchor="center")
        self._label(brand, "GOKWORKS", 16, bold=True).grid(row=0, column=1, sticky="w")
        self._label(brand, "SolidWorks otomasyonu", 10, MUTED).grid(row=1, column=1, sticky="w")
        self._label(self.sidebar, "ARAÇLAR", 10, MUTED, True).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 10))
        navigation = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        navigation.grid(row=2, column=0, sticky="ew", padx=14)
        navigation.grid_columnconfigure(0, weight=1)
        self.nav_buttons = {}
        for row, (key, title) in enumerate((("pdf", "PDF"), ("dxf_dwg", "DXF / DWG"), ("k_factor", "K Faktörü"))):
            active = key == "pdf"
            nav = ctk.CTkButton(navigation, text=title, height=46, corner_radius=8, anchor="w",
                               fg_color="#24483E" if active else "transparent",
                               hover_color="#2E5D4F" if active else "#222B32",
                               text_color=ACCENT if active else MUTED, text_color_disabled=MUTED,
                               border_width=1 if active else 0, border_color="#346857",
                               font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold" if active else "normal"),
                               command=lambda: self.workspace.focus_set(), state="normal" if active else "disabled")
            nav.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            self.nav_buttons[key] = nav
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=5, column=0, sticky="ew", padx=24, pady=24)
        self._label(footer, "SOLID AUTOMATION", 10, MUTED, True).pack(anchor="w")
        self._label(footer, "Windows masaüstü", 10, "#6F7E89").pack(anchor="w", pady=(3, 0))

        self.workspace = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.workspace.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.pdf_header = header
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        self._label(header, "PDF Aktarımı", 25, bold=True).grid(row=0, column=0, sticky="w")
        self._label(header, "Teknik resimlerin tüm sayfalarını PDF'e aktar.", 12, MUTED,
                    wraplength=310, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 0))
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        self.start_button = self._button(actions, "PDF AKTARIMINI BAŞLAT", self._start_export, primary=True, width=220)
        self.start_button.configure(height=44)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = self._button(actions, "Durdur", self._request_stop, width=80, state="disabled")
        self.stop_button.configure(height=44)
        self.stop_button.pack(side="left")

        self.settings_body = ctk.CTkScrollableFrame(self.workspace, height=220, fg_color="transparent",
                                                   corner_radius=0)
        self.settings_body.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.settings_body.grid_columnconfigure(0, weight=1)
        # Scrollbar'ın varsayılan 200 birimlik isteği kısa paneli büyütmesin.
        self.settings_body._scrollbar.configure(height=24)
        self._settings_height = 220
        folders = ctk.CTkFrame(self.settings_body, fg_color="transparent")
        folders.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(2):
            folders.grid_columnconfigure(column, weight=1, uniform="folders")
        for column, (title, hint, variable) in enumerate((
            ("Kaynak klasör", "Bir çizim seç; bulunduğu klasör taranır.", self.source_folder),
            ("PDF kayıt klasörü", "PDF dosyalarının kaydedileceği klasör.", self.output_folder),
        )):
            card = ctk.CTkFrame(folders, fg_color=PANEL, corner_radius=10, border_width=1, border_color=BORDER)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 6 if column == 0 else 0))
            card.grid_columnconfigure(0, weight=1)
            self._folder_input(card, 0, title, hint, variable)

        options = ctk.CTkFrame(self.settings_body, fg_color=PANEL, corner_radius=10)
        options.grid(row=1, column=0, sticky="ew")
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(1, weight=1)
        for column, (text, variable) in enumerate((("Alt klasörleri de tara", self.include_subfolders),
                                                   ("Mevcut PDF'lerin üzerine yaz", self.overwrite_existing))):
            control = ctk.CTkCheckBox(options, text=text, variable=variable, height=28,
                                     checkbox_width=18, checkbox_height=18, corner_radius=4,
                                     fg_color=ACCENT, hover_color="#70E7C7", checkmark_color=BG,
                                     border_color="#55636F", text_color=TEXT, font=ctk.CTkFont(size=12))
            control.grid(row=0, column=column, sticky="w", padx=16, pady=(12, 8))
            self.controls.append(control)
        tools = ctk.CTkFrame(options, fg_color="transparent")
        tools.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))
        tools.grid_columnconfigure(2, weight=1)
        self.scan_button = self._button(tools, "Klasörü tara", self._scan, width=110)
        self.scan_button.grid(row=0, column=0, padx=(0, 8))
        self.controls.append(self.scan_button)
        self.open_button = self._button(tools, "PDF klasörünü aç", self._open_output, width=138)
        self.open_button.grid(row=0, column=1)
        self._label(tools, "SolidWorks açık olmalı.", 11, MUTED).grid(row=0, column=2, sticky="e", padx=(12, 0))

        stats = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.stats_frame = stats
        stats.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        for index, (key, caption, color) in enumerate((("total", "Bulunan", TEXT), ("succeeded", "Başarılı", GREEN),
                                                      ("skipped", "Atlanan", AMBER), ("failed", "Hatalı", RED))):
            stats.grid_columnconfigure(index, weight=1, uniform="stats")
            card = ctk.CTkFrame(stats, fg_color=PANEL, corner_radius=10)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0 if index == 3 else 4))
            self._label(card, caption, 11, MUTED).pack(anchor="w", padx=14, pady=(10, 0))
            value = self._label(card, "0", 22, color, True)
            value.pack(anchor="w", padx=14, pady=(0, 8))
            self.stat_values[key] = value

        results_card = ctk.CTkFrame(self.workspace, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        results_card.grid(row=3, column=0, sticky="nsew")
        results_card.grid_columnconfigure(0, weight=1)
        results_card.grid_rowconfigure(1, weight=1)
        result_header = ctk.CTkFrame(results_card, fg_color="transparent")
        self.results_header = result_header
        result_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 2))
        result_header.grid_columnconfigure(0, weight=1)
        self._label(result_header, "Aktarım listesi", 15, bold=True).grid(row=0, column=0, sticky="w")
        self.report_button = self._button(result_header, "Rapor kaydet", self._save_report, width=106, state="disabled")
        self.report_button.grid(row=0, column=1)
        self.result_tabs = ctk.CTkTabview(results_card, fg_color=PANEL, corner_radius=6, anchor="w",
                                        segmented_button_fg_color=PANEL, segmented_button_selected_color="#293942",
                                        segmented_button_selected_hover_color="#344A56", segmented_button_unselected_color=PANEL,
                                        segmented_button_unselected_hover_color="#253039")
        self.result_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        files_tab = self.result_tabs.add("Dosyalar")
        log_tab = self.result_tabs.add("Günlük")
        files_tab.grid_rowconfigure(0, weight=1)
        files_tab.grid_columnconfigure(0, weight=1)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Gok.Treeview", background=INPUT, fieldbackground=INPUT, foreground=TEXT,
                        borderwidth=0, rowheight=32, font=("Segoe UI", 10))
        style.configure("Gok.Treeview.Heading", background="#253039", foreground=MUTED,
                        relief="flat", padding=(8, 9), font=("Segoe UI", 10, "bold"))
        style.map("Gok.Treeview.Heading", background=[("active", "#30434D")])
        style.map("Gok.Treeview", background=[("selected", "#284B40")], foreground=[("selected", "white")])
        self.table = ttk.Treeview(files_tab, columns=("file", "status", "detail"), show="headings", style="Gok.Treeview")
        for name, caption, width in (("file", "TEKNİK RESİM", 300), ("status", "DURUM", 105), ("detail", "AÇIKLAMA", 290)):
            self.table.heading(name, text=caption)
            self.table.column(name, width=width, minwidth=80, stretch=name != "status")
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ctk.CTkScrollbar(files_tab, command=self.table.yview, fg_color=INPUT)
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal = ctk.CTkScrollbar(files_tab, orientation="horizontal", command=self.table.xview, fg_color=INPUT)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        for status, color in (("pending", MUTED), ("running", ACCENT), ("success", GREEN), ("skipped", AMBER), ("error", RED)):
            self.table.tag_configure(status, foreground=color)
        log_tab.grid_rowconfigure(0, weight=1)
        log_tab.grid_columnconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(log_tab, fg_color=INPUT, text_color=TEXT, wrap="word", font=("Consolas", 11))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")
        self.status_label = self._label(self.workspace, "Hazır · Kaynak ve PDF kayıt klasörünü seç.", 12, MUTED, anchor="w")
        self.status_label.grid(row=4, column=0, sticky="ew", pady=(10, 5))
        self.workspace.bind("<Configure>", self._resize_pdf_area)
        self.progress = ctk.CTkProgressBar(self.workspace, height=6, corner_radius=3, fg_color=BORDER, progress_color=ACCENT)
        self.progress.grid(row=5, column=0, sticky="ew")
        self.progress.set(0)

    def _resize_pdf_area(self, event=None):
        self.status_label.configure(wraplength=max(240, self.workspace.winfo_width() - 12))
        previous = getattr(self, "_layout_fit_id", None)
        if previous is not None:
            self.after_cancel(previous)
        self._layout_fit_id = self.after(150, self._fit_pdf_settings)

    def _fit_pdf_settings(self):
        self._layout_fit_id = None
        if self._closed or self.workspace.winfo_height() < 100:
            return
        scale = self.settings_body._get_widget_scaling()
        fixed = (self.pdf_header.winfo_reqheight() + self.stats_frame.winfo_reqheight()
                 + self.status_label.winfo_reqheight() + self.progress.winfo_reqheight() + 57 * scale)
        result_minimum = self.results_header.winfo_reqheight() + 150 * scale
        available = (self.workspace.winfo_height() - fixed - result_minimum) / scale
        height = max(120, min(220, int(available)))
        if height != self._settings_height:
            self._settings_height = height
            self.settings_body.configure(height=height)


    def _folder_input(self, parent, row, label, hint, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(14, 14))
        frame.grid_columnconfigure(0, weight=1)
        self._label(frame, label, 13, bold=True).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        entry = ctk.CTkEntry(frame, textvariable=variable, height=38, corner_radius=7,
                            border_width=1, border_color=BORDER, fg_color=INPUT, font=("Segoe UI", 11))
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        browse = self._button(frame, "Gözat", lambda: self._choose_folder(variable, label), width=68)
        browse.grid(row=1, column=1)
        self._label(frame, hint, 10, MUTED, wraplength=260, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.controls.extend((entry, browse))

    def _choose_folder(self, variable, title):
        initial = variable.get().strip()
        if not initial or not Path(initial).is_dir():
            initial = str(Path.home())
        if variable is self.source_folder:
            # Windows'un dosya penceresi içerikleri ve tür filtresini gösterir.
            # Seçilen dosya, topluca taranacak klasörü belirler.
            selected = filedialog.askopenfilename(
                parent=self,
                title="Kaynak klasördeki bir teknik resmi seç",
                initialdir=initial,
                filetypes=[("SOLIDWORKS teknik resim (*.SLDDRW)", "*.slddrw"),
                           ("Tüm dosyalar (*.*)", "*.*")],
            )
            folder = str(Path(selected).parent) if selected else ""
        else:
            folder = filedialog.askdirectory(parent=self, title=title,
                                             initialdir=initial, mustexist=True)
        if folder:
            variable.set(folder)

    def _save_preferences(self):
        try:
            save_settings({"pdf_source": self.source_folder.get(), "pdf_output": self.output_folder.get(),
                           "pdf_recursive": self.include_subfolders.get(), "pdf_overwrite": self.overwrite_existing.get()},
                          self.settings_path)
        except OSError as error:
            self._append_log(f"Klasör tercihleri kaydedilemedi: {error}")

    def _set_busy(self, value):
        self.busy = value
        for control in self.controls:
            control.configure(state="disabled" if value else "normal")
        self.start_button.configure(state="disabled" if value else "normal",
                                     text="AKTARIM SÜRÜYOR…" if value else "PDF AKTARIMINI BAŞLAT")
        self.stop_button.configure(state="normal" if value else "disabled")

    def _reset(self):
        self.results.clear()
        self._fill_files([])
        self.result_tabs.set("Dosyalar")
        self.progress.set(0)
        self.report_button.configure(state="disabled")
        for value in self.stat_values.values():
            value.configure(text="0")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.stop_event.clear()

    def _valid_source(self):
        source = self.source_folder.get().strip()
        if not source or not Path(source).is_dir():
            self.status_label.configure(text="Kaynak klasör bulunamadı. Bir klasör seç.", text_color=RED)
            return None
        return source

    def _scan(self):
        if self.busy:
            return
        source = self._valid_source()
        if source is None:
            return
        self._reset()
        self._set_busy(True)
        self.start_button.configure(text="Klasör taranıyor…")
        self.status_label.configure(text="Teknik resimler taranıyor…", text_color=MUTED)
        recursive = self.include_subfolders.get()
        def scan():
            try:
                files = find_drawings(source, recursive, self.stop_event)
                self.events.put(("preview", files))
            except Exception as error:
                self.events.put(("preview_error", str(error)))
        threading.Thread(target=scan, daemon=False).start()

    def _start_export(self):
        if self.busy:
            return
        source = self._valid_source()
        if source is None:
            return
        output = self.output_folder.get().strip()
        if not output or (Path(output).exists() and not Path(output).is_dir()):
            self.status_label.configure(text="Geçerli bir PDF kayıt klasörü seç.", text_color=RED)
            return
        self._save_preferences()
        self._reset()
        self._set_busy(True)
        self.status_label.configure(text="Aktarım hazırlanıyor…", text_color=MUTED)
        threading.Thread(target=export_drawings,
                         args=(source, output, self.include_subfolders.get(), self.overwrite_existing.get(), self.events, self.stop_event),
                         daemon=False).start()

    def _request_stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Geçerli dosya tamamlandıktan sonra duracak…", text_color=AMBER)

    def _fill_files(self, files):
        self.table.delete(*self.table.get_children())
        self.row_ids.clear()
        for index, path in enumerate(files):
            try:
                name = str(Path(path).relative_to(Path(self.source_folder.get()).resolve()))
            except ValueError:
                name = Path(path).name
            self.row_ids[path] = self.table.insert("", "end", iid=f"file_{index}",
                                                    values=(name, "Bekliyor", ""), tags=("pending",))
        self.stat_values["total"].configure(text=str(len(files)))

    def _update_row(self, path, status, detail=""):
        row = self.row_ids.get(path)
        if row:
            name = self.table.item(row, "values")[0]
            self.table.item(row, values=(name, LABELS[status], detail), tags=(status,))
            self.table.see(row)

    def _append_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _open_output(self):
        folder = self.output_folder.get().strip()
        if folder and Path(folder).is_dir():
            try:
                os.startfile(folder)
            except OSError as error:
                self.status_label.configure(text=f"Klasör açılamadı: {error}", text_color=RED)
        else:
            self.status_label.configure(text="PDF kayıt klasörü henüz oluşturulmadı.", text_color=AMBER)

    def _save_report(self):
        if not self.results:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Aktarım raporunu kaydet",
                                           initialfile=f"GOKWORKS_PDF_{datetime.now():%Y%m%d_%H%M}.csv",
                                           defaultextension=".csv", filetypes=[("CSV raporu", "*.csv")])
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream, delimiter=";")
                    writer.writerow(("Kaynak", "PDF", "Durum", "Açıklama"))
                    for result in self.results:
                        writer.writerow((result["source"], result["output"], LABELS[result["status"]], result["detail"]))
                self._append_log(f"Rapor kaydedildi: {path}")
            except OSError as error:
                self.status_label.configure(text=f"Rapor kaydedilemedi: {error}", text_color=RED)

    def _finish(self, summary):
        self._set_busy(False)
        for key in ("total", "succeeded", "skipped", "failed"):
            self.stat_values[key].configure(text=str(summary[key]))
        state = summary["state"]
        if state == "error":
            text, color = summary["error"], RED
            self.result_tabs.set("Günlük")
        elif state == "cancelled":
            text, color = f"Durduruldu · {summary['processed']} / {summary['total']} dosya işlendi.", AMBER
        elif state == "empty":
            text, color = "Bu klasörde .SLDDRW dosyası bulunamadı.", AMBER
        else:
            text = f"Tamamlandı · {summary['succeeded']} PDF, {summary['skipped']} atlanan, {summary['failed']} hatalı."
            color = AMBER if summary["failed"] else GREEN
        self.status_label.configure(text=text, text_color=color)
        self._append_log(text)
        self.report_button.configure(state="normal" if self.results else "disabled")
        if self.close_pending:
            self._destroy_app()

    def _process_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "files":
                    self._fill_files(value)
                elif event == "phase":
                    self.status_label.configure(text=value, text_color=MUTED)
                elif event == "total":
                    self.stat_values["total"].configure(text=str(value))
                elif event == "current":
                    self._update_row(value, "running")
                    self.status_label.configure(text=f"Aktarılıyor · {Path(value).name}")
                elif event == "result":
                    self.results.append(value)
                    self._update_row(value["source"], value["status"], value["detail"])
                    self._append_log(f"{LABELS[value['status']]} · {Path(value['source']).name} · {value['detail']}")
                elif event == "counts":
                    for key in ("succeeded", "skipped", "failed"):
                        self.stat_values[key].configure(text=str(value[key]))
                elif event == "progress":
                    current, total = value
                    self.progress.set(current / total if total else 0)
                elif event == "log":
                    self._append_log(value)
                elif event in ("preview", "preview_error"):
                    self._set_busy(False)
                    if event == "preview":
                        self._fill_files(value)
                        text = f"{len(value)} teknik resim bulundu. Aktarım için hazır."
                        if self.stop_event.is_set():
                            text = "Klasör taraması durduruldu."
                        self.status_label.configure(text=text, text_color=MUTED)
                    else:
                        self.status_label.configure(text=value, text_color=RED)
                    if self.close_pending:
                        self._destroy_app()
                elif event == "done":
                    self._finish(value)
                if self._closed:
                    return
        except queue.Empty:
            pass
        self._poll_id = self.after(80, self._process_events)

    def _on_close(self):
        if self.busy:
            if messagebox.askyesno("İşlem sürüyor", "İşlemi durdurup uygulamayı kapatmak istiyor musun?", parent=self):
                self.close_pending = True
                self._request_stop()
            return
        self._destroy_app()

    def _destroy_app(self):
        self._save_preferences()
        self._closed = True
        layout_fit = getattr(self, "_layout_fit_id", None)
        if layout_fit is not None:
            self.after_cancel(layout_fit)
        self.after_cancel(self._poll_id)
        self.destroy()


def main():
    app = GokworksPdfApp()
    app.mainloop()
