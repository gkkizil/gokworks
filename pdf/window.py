"""GOKWORKS'in PDF ve sac metal açınım ekranları."""

import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from pdf.exporter import export_drawings, find_drawings
from dxf_dwg.exporter import export_parts, find_parts
from pdf.settings import load_settings, save_settings, SETTINGS_PATH
from gui.layout import WorkspaceLayout
from k_factor.window import KFactorView
from iso_fits.window import IsoFitsView
from gui.icons import make_icon
from gui.theme import (BG, PANEL, INPUT, TEXT, MUTED, ACCENT, ACCENT_BG,
                       GREEN, AMBER, RED, SECONDARY, HOVER, UI_FONT)
LABELS = {"pending": "Bekliyor", "running": "İşleniyor", "success": "Başarılı",
          "skipped": "Atlandı", "error": "Hata"}
FILTERS = {"Tüm durumlar": None, "Bekleyen": "pending", "İşleniyor": "running",
           "Başarılı": "success", "Atlanan": "skipped", "Hatalı": "error"}


def _search_text(value):
    # Turkish İ casefolds to i + combining dot; searches should still match i.
    return str(value).casefold().replace("\u0307", "")


class GokworksPdfApp(IsoFitsView, KFactorView, WorkspaceLayout, ctk.CTk):
    _ISO_PAGE_ATTRIBUTES = ('workspace', 'iso_state', 'iso_widgets', 'iso_result',
                            'iso_search', 'status_label')
    _PAGE_ATTRIBUTES = (
        "source_folder", "output_folder", "include_subfolders", "overwrite_existing",
        "output_format", "bend_lines", "controls", "results", "row_ids", "stat_values",
        "workspace", "pdf_header", "start_button", "stop_button", "settings_body",
        "_settings_height", "scan_button", "open_button", "stats_frame", "results_header",
        "report_button", "result_tabs", "table", "empty_state", "log_box", "status_label", "progress",
        "search_query", "status_filter", "search_entry", "filter_menu", "files_toolbar",
        "visible_count", "results_footer", "row_statuses", "empty_title", "empty_hint",
        "_visible_rows",
        "k_state", "k_widgets", "k_calculation_label",
    )

    def __init__(self, settings_path=SETTINGS_PATH):
        saved = load_settings(settings_path)
        appearance = saved.get("appearance", "light")
        ctk.set_appearance_mode(appearance if appearance in ("light", "dark") else "light")
        ctk.set_default_color_theme("dark-blue")
        if os.name != "nt":
            ctk.ThemeManager.theme["CTkFont"]["family"] = UI_FONT
        super().__init__()
        self.title("GOKWORKS • SolidWorks Otomasyonu")
        window_scale = self._get_window_scaling()
        width = min(1240, max(1000, int(self.winfo_screenwidth()/window_scale)-24))
        height = min(860, max(690, int(self.winfo_screenheight()/window_scale)-32))
        self.geometry(f"{width}x{height}")
        self.minsize(1000, 690)
        self.configure(fg_color=BG)
        self.settings_path = settings_path
        self.mode = "pdf"
        self._pages = {}
        self.theme_mode = tk.StringVar(self, value="Koyu" if ctk.get_appearance_mode() == "Dark" else "Açık")
        self.source_folder = tk.StringVar(self, value=str(saved.get("pdf_source", "")))
        self.output_folder = tk.StringVar(self, value=str(saved.get("pdf_output", "")))
        self.include_subfolders = tk.BooleanVar(self, value=saved.get("pdf_recursive", True) is True)
        self.overwrite_existing = tk.BooleanVar(self, value=saved.get("pdf_overwrite", False) is True)
        self.output_format = tk.StringVar(self, value=saved.get("dxf_dwg_format", "DXF"))
        if self.output_format.get() not in ("DXF", "DWG", "DXF + DWG"):
            self.output_format.set("DXF")
        self.bend_lines = tk.BooleanVar(self, value=saved.get("dxf_dwg_bend_lines", False) is True)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.close_pending = False
        self._closed = False
        self.controls = []
        self.results = []
        self.row_ids = {}
        self.stat_values = {}
        self._icons = {}
        self.k_state = self.k_widgets = self.k_calculation_label = None
        self._create_filter_state()
        self._build_window()
        self._remember_page()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_id = self.after(80, self._process_events)
        self.bind("<Control-f>", self._focus_search)

    @property
    def _is_pdf(self):
        return self.mode == "pdf"

    @property
    def _start_text(self):
        if self.mode == "k_factor":
            return "Montaja K/R uygula"
        return "PDF aktarımını başlat" if self._is_pdf else "Açınım aktarımını başlat"

    @property
    def _extension(self):
        return ".SLDDRW" if self._is_pdf else ".SLDPRT"

    @property
    def _file_label(self):
        return "teknik resim" if self._is_pdf else "parça"

    def _switch_mode(self, mode):
        if self.busy or mode == self.mode or mode not in ("pdf", "dxf_dwg", "k_factor", "iso_fits"):
            return
        self._save_preferences()
        layout_fit = getattr(self, "_layout_fit_id", None)
        if layout_fit is not None:
            self.after_cancel(layout_fit)
            self._layout_fit_id = None
        self.workspace.unbind("<Configure>")
        self._remember_page()
        self.workspace.grid_remove()
        self.mode = mode
        if mode in self._pages:
            for name, value in self._pages[mode].items():
                setattr(self, name, value)
            self.workspace.grid()
        else:
            self._create_page_state()
            self._build_window()
            self._remember_page()
        self.stop_event.clear()
        self.workspace.bind("<Configure>", self._resize_pdf_area)
        self._update_navigation()
        self._resize_pdf_area()
        if self.mode == 'iso_fits':
            self._draw_iso_diagram()

    def _remember_page(self):
        attributes = self._ISO_PAGE_ATTRIBUTES if self.mode == 'iso_fits' else self._PAGE_ATTRIBUTES
        self._pages[self.mode] = {name: getattr(self, name) for name in attributes}

    def _create_page_state(self):
        saved = load_settings(self.settings_path)
        self.source_folder = tk.StringVar(self, value=str(saved.get(f"{self.mode}_source", "")))
        self.output_folder = tk.StringVar(self, value=str(saved.get(f"{self.mode}_output", "")))
        self.include_subfolders = tk.BooleanVar(self, value=saved.get(f"{self.mode}_recursive", True) is True)
        self.overwrite_existing = tk.BooleanVar(self, value=saved.get(f"{self.mode}_overwrite", False) is True)
        output_format = saved.get("dxf_dwg_format", "DXF")
        self.output_format = tk.StringVar(self, value=output_format if output_format in ("DXF", "DWG", "DXF + DWG") else "DXF")
        self.bend_lines = tk.BooleanVar(self, value=saved.get("dxf_dwg_bend_lines", False) is True)
        self.controls, self.results = [], []
        self.row_ids, self.stat_values = {}, {}
        self._create_filter_state()
        self.k_state = self.k_widgets = self.k_calculation_label = None
        if self.mode == "k_factor":
            self._create_k_state(saved)
        elif self.mode == 'iso_fits':
            self._create_iso_state(saved)

    def _create_filter_state(self):
        self.search_query = tk.StringVar(self, value="")
        self.status_filter = tk.StringVar(self, value="Tüm durumlar")
        self.row_statuses = {}
        self._visible_rows = set()
        mode = self.mode
        for variable in (self.search_query, self.status_filter):
            variable.trace_add("write", lambda *_: self._apply_filters() if self.mode == mode else None)

    def _icon(self, name, color=MUTED, size=20):
        key = name, color, size
        if key not in self._icons:
            self._icons[key] = make_icon(*key)
        return self._icons[key]

    def _update_navigation(self):
        for key, button in self.nav_buttons.items():
            active = key == self.mode
            button.configure(
                fg_color=ACCENT_BG if active else "transparent",
                hover_color=("#D9EDE3", "#214A3F") if active else SECONDARY,
                text_color=ACCENT if active else MUTED,
                image=self._icon({"pdf": "file", "dxf_dwg": "layers", "k_factor": "tools", "iso_fits": "ruler"}[key],
                                 ACCENT if active else MUTED),
                border_width=1 if active else 0,
                font=ctk.CTkFont(family=UI_FONT, size=14, weight="bold" if active else "normal"),
            )

    def _cancel_widget_callbacks(self, widget):
        """Silinen panelin CustomTkinter zamanlayıcılarını da iptal et."""
        owners = {}

        def collect(current):
            for command in getattr(current, "_tclCommands", None) or ():
                owners[command] = current
            for child in current.winfo_children():
                collect(child)

        collect(widget)
        for timer in self.tk.splitlist(self.tk.call("after", "info")):
            script = self.tk.call("after", "info", timer)[0]
            command = self.tk.splitlist(script)[0]
            owner = owners.get(command)
            if owner is not None:
                owner.after_cancel(timer)

    def _label(self, parent, text, size=13, color=TEXT, bold=False, **kwargs):
        kwargs.setdefault("height", size + 6)
        return ctk.CTkLabel(parent, text=text, text_color=color,
                            font=ctk.CTkFont(family=UI_FONT, size=size,
                                            weight="bold" if bold else "normal"), **kwargs)

    def _button(self, parent, text, command, primary=False, icon=None, **kwargs):
        return ctk.CTkButton(
            parent, text=text, command=command, corner_radius=8, height=38,
            fg_color=ACCENT if primary else SECONDARY,
            hover_color=("#12634F", "#70E7C7") if primary else HOVER,
            text_color=("#FFFFFF", "#10231D") if primary else TEXT, text_color_disabled=MUTED,
            image=self._icon(icon, ("#FFFFFF", "#10231D") if primary else MUTED, 18) if icon else None,
            font=ctk.CTkFont(family=UI_FONT, size=12, weight="bold"), **kwargs)

    def _change_theme(self, selection):
        if selection not in ("Açık", "Koyu"):
            return
        self.theme_mode.set(selection)
        ctk.set_appearance_mode("dark" if selection == "Koyu" else "light")
        self._configure_table_style()
        if self.mode == 'iso_fits':
            self._draw_iso_diagram()
        self._save_preferences()

    def _focus_search(self, event=None):
        if self.mode == 'iso_fits':
            key = 'hole_upper' if self.iso_state['method'].get() == 'Manuel kontrol' else 'search'
            self.iso_widgets[key].focus_set()
            return 'break'
        self.result_tabs.set("Dosyalar")
        self.search_entry.focus_set()
        return "break"

    def _clear_filters(self):
        self.search_query.set("")
        self.status_filter.set("Tüm durumlar")

    def _apply_filters(self):
        query = _search_text(self.search_query.get().strip())
        status = FILTERS.get(self.status_filter.get())
        self._visible_rows.clear()
        visible = 0
        for path, row in self.row_ids.items():
            values = self.table.item(row, "values")
            row_status = self.row_statuses[path]
            if (status is None or row_status == status) and query in _search_text(" ".join(values)):
                self.table.move(row, "", visible)
                self.table.item(row, tags=(row_status, "stripe") if visible % 2 else (row_status,))
                visible += 1
                self._visible_rows.add(row)
            else:
                self.table.detach(row)
        self._refresh_list_state()

    def _refresh_list_state(self):
        self.visible_count.configure(text=f"{len(self._visible_rows)} / {len(self.row_ids)} dosya")
        if self._visible_rows:
            self.empty_state.place_forget()
        else:
            filtered = bool(self.row_ids)
            self.empty_title.configure(text="Eşleşen dosya yok" if filtered else
                                       "Montaj için hazır" if self.mode == "k_factor" else "Aktarım için hazır")
            self.empty_hint.configure(text="Aramayı veya durum filtresini değiştirin." if filtered else
                                      "Montajı tara ile aktif montajı inceleyin." if self.mode == "k_factor" else
                                      "Kaynak klasörü seçin ve Klasörü tara düğmesine basın.")
            self.empty_state.place(relx=.5, rely=.6, anchor="center")

    def _show_detail(self, event=None):
        if event is not None and getattr(event, "num", None) == 1:
            row = self.table.identify_row(event.y)
        else:
            selection = self.table.selection()
            row = selection[0] if selection else ""
        path = next((path for path, identifier in self.row_ids.items() if identifier == row), None)
        if path is None:
            return "break"
        result = next((item for item in reversed(self.results) if item["source"] == path), None)
        output = result["output"] if result else "Henüz üretilmedi."
        detail = self.table.item(row, "values")[2] or "Dosya aktarım için bekliyor."
        status = LABELS[self.row_statuses[path]]
        text = f"Kaynak\n{path}\n\nÇıktı\n{output}\n\nDurum\n{status}\n\nAçıklama\n{detail}"
        existing = getattr(self, "detail_window", None)
        if existing is not None and existing.winfo_exists():
            self._close_detail()
        window = ctk.CTkToplevel(self)
        self.detail_window = window
        window.title("GOKWORKS · Dosya ayrıntıları")
        window.geometry("660x470")
        window.minsize(520, 360)
        window.configure(fg_color=PANEL)
        window.transient(self)
        window.protocol("WM_DELETE_WINDOW", self._close_detail)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        self._label(window, Path(path).name, 20, bold=True, wraplength=600,
                    justify="left").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 12))
        content = ctk.CTkTextbox(window, fg_color=INPUT, text_color=TEXT, wrap="word", font=(UI_FONT, 13))
        content.grid(row=1, column=0, sticky="nsew", padx=24)
        content.insert("1.0", text)
        content.configure(state="disabled")
        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=24, pady=18)
        def copy_details():
            self.clipboard_clear()
            self.clipboard_append(text)
        self._button(actions, "Ayrıntıları kopyala", copy_details, icon="copy", width=170).pack(side="left")
        self._button(actions, "Kapat", self._close_detail, width=90).pack(side="right")
        window.bind("<Escape>", lambda _: self._close_detail())
        return "break"

    def _close_detail(self):
        window = getattr(self, "detail_window", None)
        if window is not None and window.winfo_exists():
            self._cancel_widget_callbacks(window)
            window.destroy()
        self.detail_window = None

    def _resize_pdf_area(self, event=None):
        if self.mode == 'iso_fits':
            previous = getattr(self, '_layout_fit_id', None)
            if previous is not None:
                self.after_cancel(previous)
            self._layout_fit_id = self.after(150, self._resize_iso_workspace)
            return
        self.status_label.configure(wraplength=max(240, self.workspace.winfo_width() - 56))
        previous = getattr(self, "_layout_fit_id", None)
        if previous is not None:
            self.after_cancel(previous)
        self._layout_fit_id = self.after(150, self._fit_pdf_settings)

    def _fit_pdf_settings(self):
        self._layout_fit_id = None
        if self._closed or self.workspace.winfo_height() < 100:
            return
        scale = self.settings_body._get_widget_scaling()
        if getattr(self, "_table_style_key", None) != (ctk.get_appearance_mode(), scale):
            self._configure_table_style()
        results_card = self.result_tabs.master
        active_tab = self.result_tabs.tab(self.result_tabs.get())
        # Measure the rendered frame/tab decorations instead of guessing their
        # height. The scrollable settings content is taller than its viewport.
        result_chrome = results_card.winfo_height() - active_tab.winfo_height()
        horizontal_scroll = self.table.master.grid_slaves(row=2)[0]
        result_minimum = (result_chrome + 128 * scale + horizontal_scroll.winfo_reqheight()
                          + self.files_toolbar.winfo_reqheight() + self.results_footer.winfo_reqheight()
                          + 12 * scale)
        shared_space = (self.settings_body._parent_canvas.winfo_height()
                        + results_card.winfo_height())
        available = (shared_space - result_minimum) / scale
        preferred = int(self.settings_body.winfo_reqheight() / scale) + 2
        minimum = 64 if self.mode == "k_factor" else 96
        height = max(minimum, min(preferred, int(available)))
        if height != self._settings_height:
            self._settings_height = height
            self.settings_body.configure(height=height)
            # Tab/content switches change child geometry after this callback.
            # Re-measure once Tk has applied the new height, until it settles.
            self._layout_fit_id = self.after(40, self._fit_pdf_settings)
        scrollbar = self.settings_body._scrollbar
        needs_scroll = preferred > height
        if needs_scroll and not scrollbar.winfo_manager():
            scrollbar.grid()
        elif not needs_scroll and scrollbar.winfo_manager():
            scrollbar.grid_remove()


    def _choose_folder(self, variable, title):
        initial = variable.get().strip()
        if not initial or not Path(initial).is_dir():
            initial = str(Path.home())
        if variable is self.source_folder:
            # Windows'un dosya penceresi içerikleri ve tür filtresini gösterir.
            # Seçilen dosya, topluca taranacak klasörü belirler.
            selected = filedialog.askopenfilename(
                parent=self,
                title=f"Kaynak klasördeki bir {self._file_label} seç",
                initialdir=initial,
                filetypes=[(f"SOLIDWORKS {self._file_label} (*{self._extension})", self._extension.lower().replace(".", "*.")),
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
            saved = load_settings(self.settings_path)
            if self.mode == 'iso_fits':
                saved.update({f'iso_{key}': value.get() for key, value in self.iso_state.items()})
                saved['appearance'] = 'dark' if self.theme_mode.get() == 'Koyu' else 'light'
                save_settings(saved, self.settings_path)
                return
            if self.mode == "k_factor":
                saved.update({f"kr_{key}": value.get() for key, value in self.k_state.items() if key != "save"})
                saved["appearance"] = "dark" if self.theme_mode.get() == "Koyu" else "light"
                save_settings(saved, self.settings_path)
                return
            saved.update({f"{self.mode}_source": self.source_folder.get(),
                          f"{self.mode}_output": self.output_folder.get(),
                          f"{self.mode}_recursive": self.include_subfolders.get(),
                          f"{self.mode}_overwrite": self.overwrite_existing.get(),
                          "appearance": "dark" if self.theme_mode.get() == "Koyu" else "light"})
            if not self._is_pdf:
                saved.update({"dxf_dwg_format": self.output_format.get(),
                              "dxf_dwg_bend_lines": self.bend_lines.get()})
            save_settings(saved, self.settings_path)
        except OSError as error:
            if self.mode == 'iso_fits':
                self.status_label.configure(text=f'Tercihler kaydedilemedi: {error}', text_color=RED)
            else:
                self._append_log(f"Klasör tercihleri kaydedilemedi: {error}")

    def _set_busy(self, value):
        self.busy = value
        for key, button in self.nav_buttons.items():
            button.configure(state="disabled" if value else "normal")
        for control in self.controls:
            control.configure(state="disabled" if value else "normal")
        self.start_button.configure(state="disabled" if value else "normal",
                                     text="Aktarım sürüyor…" if value else self._start_text)
        self.stop_button.configure(state="normal" if value else "disabled")

    def _reset(self):
        self.results.clear()
        self._clear_filters()
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
        if self.mode == "k_factor":
            return self._scan_k_assembly()
        if self.busy:
            return
        source = self._valid_source()
        if source is None:
            return
        self._reset()
        self._set_busy(True)
        self.start_button.configure(text="Klasör taranıyor…")
        self.status_label.configure(text="Dosyalar taranıyor…", text_color=MUTED)
        recursive = self.include_subfolders.get()
        scanner = find_drawings if self._is_pdf else find_parts
        def scan():
            try:
                files = scanner(source, recursive, self.stop_event)
                self.events.put(("preview", files))
            except Exception as error:
                self.events.put(("preview_error", str(error)))
        threading.Thread(target=scan, daemon=False).start()

    def _start_export(self):
        if self.mode == "k_factor":
            return self._start_k_apply()
        if self.busy:
            return
        source = self._valid_source()
        if source is None:
            return
        output = self.output_folder.get().strip()
        if not output or (Path(output).exists() and not Path(output).is_dir()):
            self.status_label.configure(text="Geçerli bir çıktı kayıt klasörü seç.", text_color=RED)
            return
        self._save_preferences()
        self._reset()
        self._set_busy(True)
        self.status_label.configure(text="Aktarım hazırlanıyor…", text_color=MUTED)
        exporter = export_drawings if self._is_pdf else export_parts
        export_options = {} if self._is_pdf else {
            "formats": ("dxf", "dwg") if self.output_format.get() == "DXF + DWG" else (self.output_format.get().lower(),),
            "bend_lines": self.bend_lines.get(),
        }
        threading.Thread(target=exporter,
                         args=(source, output, self.include_subfolders.get(), self.overwrite_existing.get(), self.events, self.stop_event),
                         kwargs=export_options,
                         daemon=False).start()

    def _request_stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Geçerli dosya tamamlandıktan sonra duracak…", text_color=AMBER)

    def _fill_files(self, files):
        # Detached, filtered rows are not returned by get_children(). Delete
        # them too, otherwise the next scan reuses an existing file_n id.
        if self.row_ids:
            self.table.delete(*self.row_ids.values())
        self.row_ids.clear()
        self.row_statuses.clear()
        self._visible_rows.clear()
        for index, path in enumerate(files):
            try:
                name = str(Path(path).relative_to(Path(self.source_folder.get()).resolve()))
            except ValueError:
                name = Path(path).name
            self.row_ids[path] = self.table.insert("", "end", iid=f"file_{index}",
                                                    values=(name, "Bekliyor", ""), tags=("pending",))
            self.row_statuses[path] = "pending"
        self.stat_values["total"].configure(text=str(len(files)))
        self._apply_filters()

    def _update_row(self, path, status, detail=""):
        row = self.row_ids.get(path)
        if row:
            name = self.table.item(row, "values")[0]
            striped = "stripe" in self.table.item(row, "tags")
            values = name, LABELS[status], detail
            self.table.item(row, values=values, tags=(status, "stripe") if striped else (status,))
            self.row_statuses[path] = status
            wanted = FILTERS.get(self.status_filter.get())
            query = _search_text(self.search_query.get().strip())
            matches = (wanted is None or status == wanted) and query in _search_text(" ".join(values))
            changed = False
            if matches and row not in self._visible_rows:
                # Restore the original scan order without redrawing unrelated
                # rows on each worker event (large batches must stay responsive).
                position = 0
                for identifier in self.row_ids.values():
                    if identifier == row:
                        break
                    position += identifier in self._visible_rows
                self.table.move(row, "", position)
                self._visible_rows.add(row)
                changed = True
            elif not matches and row in self._visible_rows:
                self.table.detach(row)
                self._visible_rows.remove(row)
                changed = True
            if changed:
                self._refresh_list_state()
            if matches:
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
            except (OSError, AttributeError) as error:
                self.status_label.configure(text=f"Klasör açılamadı: {error}", text_color=RED)
        else:
            self.status_label.configure(text="Çıktı kayıt klasörü henüz oluşturulmadı.", text_color=AMBER)

    def _save_report(self):
        if not self.results:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Aktarım raporunu kaydet",
                                           initialfile=f"GOKWORKS_{self.mode.upper()}_{datetime.now():%Y%m%d_%H%M}.csv",
                                           defaultextension=".csv", filetypes=[("CSV raporu", "*.csv")])
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream, delimiter=";")
                    writer.writerow(("Kaynak", "K/R parçası" if self.mode == "k_factor" else "PDF" if self._is_pdf else "DXF / DWG", "Durum", "Açıklama"))
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
            text, color = ("Aktif montajda parça bulunamadı." if self.mode == "k_factor" else
                           f"Bu klasörde {self._extension} dosyası bulunamadı."), AMBER
        else:
            unit = "PDF" if self._is_pdf else "parça"
            preview = self.mode == "k_factor" and self.results and all(item.get("preview") for item in self.results)
            text = f"{'Önizleme tamamlandı' if preview else 'Tamamlandı'} · {summary['succeeded']} {unit}, {summary['skipped']} atlanan, {summary['failed']} hatalı."
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
                    detail = value["detail"]
                    if self.mode == "dxf_dwg" and value.get("thickness_mm") is not None and value.get("quantity") is not None:
                        detail = f"{value['thickness_mm']:g} mm · {value['quantity']} adet · {detail}"
                    self._update_row(value["source"], value["status"], detail)
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
                        text = f"{len(value)} {self._file_label} bulundu. Aktarım için hazır."
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
        self._cancel_widget_callbacks(self)
        self.destroy()


def main():
    app = GokworksPdfApp()
    app.mainloop()
