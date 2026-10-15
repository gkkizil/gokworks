"""GOKWORKS'in PDF ve sac metal açınım ekranları."""

from bisect import bisect_left
import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from pdf.exporter import export_drawings, find_drawings
from dxf_dwg.exporter import export_parts, find_parts
from pdf.settings import load_settings, save_settings, SETTINGS_PATH
from gui.layout import WorkspaceLayout
from k_factor.window import KFactorView
from iso_fits.window import IsoFitsView
from geometric_tolerances.window import GeometricTolerancesView
from bom.window import BomView
from bolt.window import BoltView
from weight.window import WeightView
from naming.window import NamingView
from gui.icons import make_icon, set_window_icon
from gui.typography import check_turkish_fonts
from gui.rendering import configure_changed, hide_grid
from gui.theme import (BG, PANEL, INPUT, TEXT, MUTED, ACCENT, ACCENT_BG,
                       SUCCESS, AMBER, RED, SECONDARY, HOVER, UI_FONT, SIDEBAR, BORDER,
                       NAV_ACTIVE, NAV_ACCENT, NAV_MUTED, NAV_HOVER,
                       ACCENT_HOVER, PRIMARY_TEXT, configure_widget_theme)
LABELS = {"pending": "Bekliyor", "running": "İşleniyor", "success": "Başarılı",
          "partial": "Kısmen tamamlandı", "skipped": "Atlandı", "error": "Hata"}
FILTERS = {"Tüm durumlar": None, "Bekleyen": "pending", "İşleniyor": "running",
           "Başarılı": "success", "Uygulamaya hazır": "success", "Uygulandı": "success",
           "Kısmi": "partial", "Atlanan": "skipped", "Hatalı": "error"}


def _search_text(value):
    # Turkish İ casefolds to i + combining dot; searches should still match i.
    return str(value).casefold().replace("\u0307", "")


class GokworksPdfApp(NamingView, WeightView, BoltView, BomView, GeometricTolerancesView, IsoFitsView, KFactorView, WorkspaceLayout, ctk.CTk):
    _MODES = ('pdf', 'dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'bom', 'bolt', 'naming', 'weight')
    _NAMING_PAGE_ATTRIBUTES = ('workspace', 'naming_state', 'naming_snapshot', 'naming_plan',
                               'naming_overrides', 'naming_widgets', 'status_label', 'progress')
    _BOLT_PAGE_ATTRIBUTES = ('workspace', 'bolt_state', 'bolt_widgets', 'bolt_result', 'status_label')
    _WEIGHT_PAGE_ATTRIBUTES = ('workspace', 'weight_state', 'weight_widgets', 'weight_result', 'status_label')
    _BOM_PAGE_ATTRIBUTES = ('workspace', 'bom_state', 'bom_query', 'bom_result',
                            'bom_widgets', 'status_label', 'progress')
    _GDT_PAGE_ATTRIBUTES = ('workspace', 'gdt_state', 'gdt_widgets', 'gdt_result',
                            'gdt_search', 'status_label')
    _ISO_PAGE_ATTRIBUTES = ('workspace', 'iso_state', 'iso_widgets', 'iso_result',
                            'iso_search', 'status_label')
    _PAGE_ATTRIBUTES = (
        "source_folder", "output_folder", "include_subfolders", "overwrite_existing",
        "output_format", "bend_lines", "group_by_thickness", "controls", "results", "row_ids", "stat_values",
        "workspace", "pdf_header", "start_button", "stop_button", "settings_body", "form_panel",
        "_settings_height", "scan_button", "open_button", "stats_frame", "results_header",
        "report_button", "result_tabs", "table", "empty_state", "log_box", "status_label", "progress",
        "search_query", "status_filter", "search_entry", "filter_menu", "files_toolbar",
        "visible_count", "results_footer", "row_statuses", "empty_title", "empty_hint",
        "_visible_rows", "_visible_order", "_row_data",
        "k_state", "k_widgets", "k_calculation_label", "results_title", "results_hint", "clear_filter_button",
    )

    def __init__(self, settings_path=SETTINGS_PATH):
        saved = load_settings(settings_path)
        appearance = saved.get("appearance", "light")
        ctk.set_appearance_mode(appearance if appearance in ("light", "dark") else "light")
        ctk.set_default_color_theme("dark-blue")
        configure_widget_theme(ctk.ThemeManager.theme)
        if os.name != "nt":
            ctk.ThemeManager.theme["CTkFont"]["family"] = UI_FONT
        super().__init__()
        try:
            check_turkish_fonts(self)
        except RuntimeError:
            self.destroy()
            raise
        set_window_icon(self)
        self.title("GOKWORKS • SolidWorks otomasyonu")
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
        if self.output_format.get() not in ("DXF", "DWG"):
            self.output_format.set("DXF")
        self.bend_lines = tk.BooleanVar(self, value=saved.get("dxf_dwg_bend_lines", False) is True)
        self.group_by_thickness = tk.BooleanVar(self, value=saved.get("dxf_dwg_group_by_thickness", True) is True)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.close_pending = False
        self._closed = False
        self._pending_preferences = {}
        self._preferences_save_id = None
        self._pending_files = None
        self._pending_preview = False
        self._worker_updates = None
        self._last_ui_activity = time.monotonic()
        self._preload_id = None
        self._navigation_id = None
        self._requested_mode = None
        self.controls = []
        self.results = []
        self.row_ids = {}
        self.stat_values = {}
        self._icons = {}
        self.k_state = self.k_widgets = self.k_calculation_label = None
        self._create_filter_state()
        self._build_window()
        self._show_workspace()
        self._remember_page()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_id = self.after(80, self._process_events)
        self.bind("<Control-f>", self._focus_search)
        for sequence in ('<ButtonPress>', '<KeyPress>', '<MouseWheel>'):
            self.bind(sequence, self._note_ui_activity, add='+')
        self._preload_id = self.after(700, self._preload_page)

    def _note_ui_activity(self, event=None):
        self._last_ui_activity = time.monotonic()

    def _preload_page(self):
        """Prepare one hidden page between interactions, on the Tk thread."""
        self._preload_id = None
        if self._closed:
            return
        missing = next((mode for mode in self._MODES
                        if mode not in self._pages), None)
        if missing is None:
            return
        if self.busy or self._navigation_id is not None or time.monotonic()-self._last_ui_activity < .6:
            self._preload_id = self.after(700, self._preload_page)
            return
        self._remember_page()
        active_mode, active = self.mode, self._pages[self.mode]
        try:
            self.mode = missing
            self._create_page_state()
            self._build_window()
            self._remember_page()
            self.workspace.unbind('<Configure>')
            hide_grid(self.workspace)
        except Exception:
            if self.workspace is not active['workspace']:
                self._cancel_widget_callbacks(self.workspace)
                self.workspace.destroy()
            raise
        finally:
            if self._layout_fit_id is not None:
                self.after_cancel(self._layout_fit_id)
                self._layout_fit_id = None
            self.mode = active_mode
            for name, value in active.items():
                setattr(self, name, value)
            self._resize_pdf_area()
        self._preload_id = self.after(700, self._preload_page)

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

    def _request_mode(self, mode):
        """Coalesce queued clicks before spending time building a new page."""
        if self._closed or self.busy or mode not in self._MODES:
            return
        self._note_ui_activity()
        self._requested_mode = mode
        if self._navigation_id is None:
            self._navigation_id = self.after(0, self._apply_navigation)

    def _apply_navigation(self):
        self._navigation_id = None
        mode, self._requested_mode = self._requested_mode, None
        if mode is not None:
            self._switch_mode(mode)

    def _switch_mode(self, mode):
        # Direct programmatic navigation also supersedes any queued click.
        if self._navigation_id is not None:
            self.after_cancel(self._navigation_id)
            self._navigation_id = None
        self._requested_mode = None
        self._note_ui_activity()
        if self._closed or self.busy or mode == self.mode or mode not in self._MODES:
            return
        self._schedule_preferences()
        layout_fit = getattr(self, "_layout_fit_id", None)
        if layout_fit is not None:
            self.after_cancel(layout_fit)
            self._layout_fit_id = None
        self.workspace.unbind("<Configure>")
        self._remember_page()
        active_mode, active_workspace = self.mode, self.workspace
        self.mode = mode
        cached = mode in self._pages
        try:
            if cached:
                for name, value in self._pages[mode].items():
                    setattr(self, name, value)
            else:
                self._create_page_state()
                self._build_window()
                self._remember_page()
            # Map and paint the replacement below the previous native window.
            # Merely calling grid() before unmapping the old page leaves an
            # expose/geometry gap, especially on Windows.
            self.workspace.lower(active_workspace)
            self._show_workspace()
            self.update_idletasks()
            self._resize_pdf_area(immediate=True)
            self.update_idletasks()
            self.workspace.tkraise()
            hide_grid(active_workspace)
        except Exception:
            if self.workspace is not active_workspace:
                if cached:
                    hide_grid(self.workspace)
                else:
                    self._pages.pop(mode, None)
                    self._cancel_widget_callbacks(self.workspace)
                    self.workspace.destroy()
            if self._layout_fit_id is not None:
                self.after_cancel(self._layout_fit_id)
                self._layout_fit_id = None
            self.mode = active_mode
            for name, value in self._pages[active_mode].items():
                setattr(self, name, value)
            self.workspace.bind("<Configure>", self._resize_pdf_area)
            self._resize_pdf_area()
            raise
        self.stop_event.clear()
        self.workspace.bind("<Configure>", self._resize_pdf_area)
        self._update_navigation()
        self._resize_pdf_area()
        if self.mode == 'iso_fits':
            self._draw_iso_diagram()
        elif self.mode == 'geometric_tolerances':
            self._draw_gdt_diagram()
        elif self.mode == 'bolt':
            self._draw_bolt_diagram()
        elif self.mode == 'weight':
            self._draw_weight_diagram()

    def _remember_page(self):
        if self.mode == 'naming' and 'preview_id' in self.naming_widgets:
            # Cache the plan matching the latest fields before leaving the page.
            # A hidden debounce must not replace a plan already stored here.
            self._update_naming_preview()
        attributes = (self._NAMING_PAGE_ATTRIBUTES if self.mode == 'naming' else
                      self._WEIGHT_PAGE_ATTRIBUTES if self.mode == 'weight' else
                      self._BOLT_PAGE_ATTRIBUTES if self.mode == 'bolt' else
                      self._BOM_PAGE_ATTRIBUTES if self.mode == 'bom' else
                      self._GDT_PAGE_ATTRIBUTES if self.mode == 'geometric_tolerances' else
                      self._ISO_PAGE_ATTRIBUTES if self.mode == 'iso_fits' else self._PAGE_ATTRIBUTES)
        self._pages[self.mode] = {name: getattr(self, name) for name in attributes}

    def _create_page_state(self):
        saved = load_settings(self.settings_path)
        self.source_folder = tk.StringVar(self, value=str(saved.get(f"{self.mode}_source", "")))
        self.output_folder = tk.StringVar(self, value=str(saved.get(f"{self.mode}_output", "")))
        self.include_subfolders = tk.BooleanVar(self, value=saved.get(f"{self.mode}_recursive", True) is True)
        self.overwrite_existing = tk.BooleanVar(self, value=saved.get(f"{self.mode}_overwrite", False) is True)
        output_format = saved.get("dxf_dwg_format", "DXF")
        self.output_format = tk.StringVar(self, value=output_format if output_format in ("DXF", "DWG") else "DXF")
        self.bend_lines = tk.BooleanVar(self, value=saved.get("dxf_dwg_bend_lines", False) is True)
        self.group_by_thickness = tk.BooleanVar(self, value=saved.get("dxf_dwg_group_by_thickness", True) is True)
        if self.mode == "dxf_dwg":
            variable = self.group_by_thickness
            variable.trace_add("write", lambda *_: self._schedule_preferences()
                               if self.mode == "dxf_dwg" and self.group_by_thickness is variable else None)
        self.controls, self.results = [], []
        self.row_ids, self.stat_values = {}, {}
        self._create_filter_state()
        self.k_state = self.k_widgets = self.k_calculation_label = None
        if self.mode == "k_factor":
            self._create_k_state(saved)
        elif self.mode == 'iso_fits':
            self._create_iso_state(saved)
        elif self.mode == 'geometric_tolerances':
            self._create_gdt_state(saved)
        elif self.mode == 'bom':
            self._create_bom_state(saved)
        elif self.mode == 'bolt':
            self._create_bolt_state(saved)
        elif self.mode == 'naming':
            self._create_naming_state(saved)
        elif self.mode == 'weight':
            self._create_weight_state(saved)

    def _create_filter_state(self):
        self.search_query = tk.StringVar(self, value="")
        self.status_filter = tk.StringVar(self, value="Tüm durumlar")
        self.row_statuses = {}
        self._visible_rows = set()
        self._visible_order = []
        self._row_data = {}
        mode = self.mode
        for variable in (self.search_query, self.status_filter):
            variable.trace_add("write", lambda *_: self._apply_filters() if self.mode == mode else None)

    def _icon(self, name, color=MUTED, size=20):
        key = name, color, size
        if key not in self._icons:
            self._icons[key] = make_icon(*key)
        return self._icons[key]

    def _update_navigation(self):
        previous = self._nav_active
        self._nav_active = self.mode
        for key in dict.fromkeys((previous, self.mode)):
            active = key == self.mode
            configure_changed(
                self.nav_buttons[key],
                fg_color=NAV_ACTIVE if active else 'transparent',
                hover_color=NAV_HOVER,
                text_color=NAV_ACCENT if active else NAV_MUTED,
                image=self._icon({"pdf": "file", "dxf_dwg": "layers", "k_factor": "tools", "iso_fits": "ruler", "geometric_tolerances": "target", "bom": "tree", "bolt": "bolt", "naming": "copy", "weight": "weight"}[key],
                                 NAV_ACCENT if active else NAV_MUTED),
                border_width=0,
                font=self._nav_fonts[active],
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
            parent, text=text, command=command, corner_radius=12, height=38,
            border_width=0, border_color=BORDER,
            fg_color=ACCENT if primary else SECONDARY,
            hover_color=ACCENT_HOVER if primary else HOVER,
            text_color=PRIMARY_TEXT if primary else TEXT, text_color_disabled=MUTED,
            image=self._icon(icon, PRIMARY_TEXT if primary else MUTED, 18) if icon else None,
            font=ctk.CTkFont(family=UI_FONT, size=12, weight="bold"), **kwargs)

    def _change_theme(self, selection):
        if selection not in ("Açık", "Koyu"):
            return
        self.theme_mode.set(selection)
        ctk.set_appearance_mode("dark" if selection == "Koyu" else "light")
        self._configure_table_style()
        if self.mode == 'iso_fits':
            self._draw_iso_diagram()
        elif self.mode == 'geometric_tolerances':
            self._draw_gdt_diagram()
        elif self.mode == 'bolt':
            self._draw_bolt_diagram()
        elif self.mode == 'weight':
            self._draw_weight_diagram()
        self._save_preferences()

    def _focus_search(self, event=None):
        if self.mode == 'weight':
            self.weight_widgets['length_input'].focus_set()
            return 'break'
        if self.mode == 'naming':
            self.naming_widgets['prefix'].focus_set()
            return 'break'
        if self.mode == 'bolt':
            key = 'shear' if self.bolt_state['mode'].get() == 'Kesme' else 'tension'
            self.bolt_widgets[key+'_input'].focus_set()
            return 'break'
        if self.mode == 'bom':
            self.bom_widgets['tabs'].set('Parça listesi')
            self.bom_widgets['search'].focus_set()
            return 'break'
        if self.mode == 'geometric_tolerances':
            self.gdt_widgets['search'].focus_set()
            return 'break'
        if self.mode == 'iso_fits':
            key = 'hole_upper' if self.iso_state['method'].get() == 'Manuel kontrol' else 'search'
            self.iso_widgets[key].focus_set()
            return 'break'
        if self.mode == 'k_factor':
            from k_factor.window import RESULTS_TAB
            self._select_k_view(RESULTS_TAB)
        self.result_tabs.set("Dosyalar")
        self.search_entry.focus_set()
        return "break"

    def _clear_filters(self):
        self._suspend_filters = True
        try:
            self.search_query.set("")
            self.status_filter.set("Tüm durumlar")
        finally:
            self._suspend_filters = False
        self._apply_filters()

    def _apply_filters(self):
        if getattr(self, '_suspend_filters', False):
            return
        query = _search_text(self.search_query.get().strip())
        status = FILTERS.get(self.status_filter.get())
        rows, order = [], []
        for path, row in self.row_ids.items():
            data = self._row_data[path]
            row_status = self.row_statuses[path]
            if (status is None or row_status == status) and query in data['search']:
                tags = (row_status, "stripe") if len(rows) % 2 else (row_status,)
                if tags != data['tags']:
                    self.table.item(row, tags=tags)
                    data['tags'] = tags
                rows.append(row)
                order.append(data['order'])
        # One Tk call attaches matching items in scan order and detaches the
        # rest. Moving every row individually is quadratic for long lists.
        self.table.set_children('', *rows)
        self._visible_order = order
        self._visible_rows = set(rows)
        self._refresh_list_state()

    def _refresh_list_state(self):
        if self._worker_updates is not None:
            self._worker_updates['list_changed'] = True
            return
        configure_changed(self.visible_count, text=f"{len(self._visible_rows)} / {len(self.row_ids)} dosya")
        if self._visible_rows:
            self.empty_state.place_forget()
        else:
            filtered = bool(self.row_ids)
            self.empty_title.configure(text="Eşleşen dosya yok" if filtered else
                                       "Montaj için hazır" if self.mode == "k_factor" else "Aktarım için hazır")
            self.empty_hint.configure(text="Aramayı veya durum filtresini değiştirin." if filtered else
                                      "Montajı tara ile aktif montajı inceleyin." if self.mode == "k_factor" else
                                      "Kaynak klasörü seçin ve Klasörü tara düğmesine basın.")
            self.empty_state.place(relx=.5, rely=.52, anchor="center")

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
        status = self._result_status_label(self.row_statuses[path],
                                          preview=result.get('preview') if result else None)
        text = f"Kaynak\n{path}\n\nÇıktı\n{output}\n\nDurum\n{status}\n\nAçıklama\n{detail}"
        existing = getattr(self, "detail_window", None)
        if existing is not None and existing.winfo_exists():
            self._close_detail()
        window = ctk.CTkToplevel(self)
        set_window_icon(window)
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

    def _resize_pdf_area(self, event=None, *, immediate=False):
        if self._closed:
            return
        callbacks = {
            'weight': self._resize_weight_workspace,
            'naming': self._resize_naming_workspace,
            'bolt': self._resize_bolt_workspace,
            'bom': self._resize_bom_workspace,
            'iso_fits': self._resize_iso_workspace,
            'geometric_tolerances': self._resize_gdt_workspace,
        }
        callback = callbacks.get(self.mode, self._fit_pdf_settings)
        if self.mode not in callbacks:
            wrap = max(240, self.workspace.winfo_width() - 56)
            configure_changed(self.status_label, wraplength=wrap)
        previous = getattr(self, '_layout_fit_id', None)
        if previous is not None:
            self.after_cancel(previous)
        self._layout_fit_id = None
        if immediate:
            callback()
        else:
            self._layout_fit_id = self.after(35, callback)

    def _fit_pdf_settings(self):
        self._layout_fit_id = None
        if self._closed or self.workspace.winfo_height() < 100:
            return
        scale = self.settings_body._get_widget_scaling()
        if getattr(self, "_table_style_key", None) != (ctk.get_appearance_mode(), scale):
            self._configure_table_style()
        if self.mode == 'k_factor':
            return self._resize_k_workspace()
        width = self.workspace.winfo_width()/scale
        form_width = max(288, min(350, (width-60)*.35))
        width_changed = abs(self.form_panel.cget("width")-form_width) > .5
        if width_changed:
            self.form_panel.configure(width=form_width)
        result_width = max(260, width-form_width-60)
        self._fit_results_toolbar(result_width)
        self._settings_height = self.settings_body._parent_canvas.winfo_height()/scale
        preferred = self.settings_body.winfo_reqheight()/scale
        scrollbar = self.settings_body._scrollbar
        needs_scroll = preferred > self._settings_height
        if needs_scroll and not scrollbar.winfo_manager():
            scrollbar.grid()
        elif not needs_scroll and scrollbar.winfo_manager():
            hide_grid(scrollbar)
        if width_changed:
            self._layout_fit_id = self.after(40, self._fit_pdf_settings)

    def _fit_results_toolbar(self, result_width):
        key = (round(result_width), self.workspace._get_widget_scaling())
        if getattr(self.files_toolbar, '_layout_key', None) == key:
            return
        self.files_toolbar._layout_key = key
        self.results_title.configure(wraplength=max(90, result_width-190))
        self.results_hint.configure(wraplength=max(100, result_width-135))
        self.empty_hint.configure(wraplength=max(150, min(360, result_width-80)))
        # Search keeps the full width when the result panel is narrow; filters
        # move to the next row instead of forcing controls beyond the viewport.
        narrow = result_width < 560
        search = self.search_entry.master
        search.grid(row=0, column=0, columnspan=3 if narrow else 1, sticky="ew",
                              padx=(0, 0 if narrow else 8), pady=(0, 6 if narrow else 0))
        self.filter_menu.grid(row=1 if narrow else 0, column=0 if narrow else 1, sticky="w", padx=(0, 8))
        self.clear_filter_button.grid(row=1 if narrow else 0, column=2, sticky="e")


    def _choose_folder(self, variable, title):
        initial = variable.get().strip()
        if not initial or not Path(initial).is_dir():
            initial = str(Path.home())
        if variable is self.source_folder:
            # Windows'un dosya penceresi içerikleri ve tür filtresini gösterir.
            # Seçilen dosya, topluca taranacak klasörü belirler.
            selected = filedialog.askopenfilename(
                parent=self,
                title=f"Kaynak klasördeki bir {self._file_label} seçin",
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
        if self._preferences_save_id is not None:
            self.after_cancel(self._preferences_save_id)
            self._preferences_save_id = None
        self._pending_preferences.update(self._preference_values())
        try:
            saved = load_settings(self.settings_path)
            updated = {**saved, **self._pending_preferences}
            # Density is now fixed by the material catalogue, never a preference.
            updated.pop('weight_density', None)
            if updated != saved:
                save_settings(updated, self.settings_path)
            self._pending_preferences.clear()
        except OSError as error:
            if self.mode in ('iso_fits', 'geometric_tolerances', 'bolt', 'bom', 'naming', 'weight'):
                self.status_label.configure(text=f'Tercihler kaydedilemedi: {error}', text_color=RED)
            else:
                self._append_log(f"Klasör tercihleri kaydedilemedi: {error}")

    def _preference_values(self):
        saved = {'appearance': 'dark' if self.theme_mode.get() == 'Koyu' else 'light'}
        if self.mode == 'naming':
            saved.update({f'naming_{key}': value.get() for key, value in self.naming_state.items()})
        elif self.mode == 'weight':
            saved.update({f'weight_{key}': value.get() for key, value in self.weight_state.items()})
        elif self.mode == 'bolt':
            saved.update({f'bolt_{key}': value.get() for key, value in self.bolt_state.items()})
        elif self.mode == 'bom':
            saved['bom_include_excluded'] = self.bom_state['include_excluded'].get()
        elif self.mode == 'geometric_tolerances':
            saved.update({f'gdt_{key}': value.get() for key, value in self.gdt_state.items() if key != 'measured'})
        elif self.mode == 'iso_fits':
            saved.update({f'iso_{key}': value.get() for key, value in self.iso_state.items()})
        elif self.mode == 'k_factor':
            saved.update({f'kr_{key}': value.get() for key, value in self.k_state.items() if key != 'save'})
        else:
            saved.update({f'{self.mode}_source': self.source_folder.get(), f'{self.mode}_output': self.output_folder.get(),
                          f'{self.mode}_recursive': self.include_subfolders.get(), f'{self.mode}_overwrite': self.overwrite_existing.get()})
            if not self._is_pdf:
                saved.update(dxf_dwg_format=self.output_format.get(), dxf_dwg_bend_lines=self.bend_lines.get(),
                             dxf_dwg_group_by_thickness=self.group_by_thickness.get())
        return saved

    def _schedule_preferences(self):
        self._pending_preferences.update(self._preference_values())
        if self._preferences_save_id is not None:
            self.after_cancel(self._preferences_save_id)
        self._preferences_save_id = self.after(250, self._save_preferences)

    def _set_busy(self, value):
        self.busy = value
        for key, button in self.nav_buttons.items():
            button.configure(state="disabled" if value else "normal")
        for control in self.controls:
            control.configure(state="disabled" if value else "normal")
        self.start_button.configure(state="disabled" if value else "normal",
                                     text="Aktarım sürüyor…" if value else self._start_text)
        if value and self.mode == 'k_factor':
            preview = self.k_widgets.get('operation_preview', False)
            queued = bool(self.k_widgets.get('pending_apply'))
            self.start_button.configure(
                state='normal' if preview and not queued and not self.stop_event.is_set() else 'disabled',
                text=('Uygulama sıraya alındı…' if queued else 'Tarama bitince K/R uygula')
                     if preview else 'K/R uygulanıyor…')
        self.stop_button.configure(state="normal" if value else "disabled")

    def _reset(self):
        self.results.clear()
        self._prepare_file_list()
        self._clear_filters()
        self.stat_values['total'].configure(text='0')
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
            self.status_label.configure(text="Kaynak klasörü bulunamadı. Bir klasör seçin.", text_color=RED)
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
            self.status_label.configure(text="Geçerli bir çıktı klasörü seçin.", text_color=RED)
            return
        if not self._is_pdf and self.output_format.get() not in ('DXF', 'DWG'):
            self.status_label.configure(text='Çıktı türü olarak DXF veya DWG seçin.', text_color=RED)
            return
        self._save_preferences()
        self._reset()
        self._set_busy(True)
        self.status_label.configure(text="Aktarım hazırlanıyor…", text_color=MUTED)
        exporter = export_drawings if self._is_pdf else export_parts
        export_options = {} if self._is_pdf else {
            "formats": (self.output_format.get().lower(),),
            "bend_lines": self.bend_lines.get(),
            "group_by_thickness": self.group_by_thickness.get(),
        }
        threading.Thread(target=exporter,
                         args=(source, output, self.include_subfolders.get(), self.overwrite_existing.get(), self.events, self.stop_event),
                         kwargs=export_options,
                         daemon=False).start()

    def _request_stop(self):
        if self.mode == 'naming':
            return self._stop_naming()
        if self.mode == 'bom':
            return self._stop_bom()
        self.stop_event.set()
        if self.mode == 'k_factor':
            self.k_widgets.pop('pending_apply', None)
            self.start_button.configure(state='disabled')
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="İşlenen dosya tamamlanınca işlem duracak…", text_color=AMBER)

    def _fill_files(self, files):
        self._prepare_file_list()
        source = Path(self.source_folder.get()).resolve()
        for index, path in enumerate(files):
            self._insert_file_row(index, path, source)
        self.stat_values['total'].configure(text=str(len(files)))
        self._apply_filters()

    def _prepare_file_list(self):
        # Detached, filtered rows are not returned by get_children(). Delete
        # them too, otherwise the next scan reuses an existing file_n id.
        if self.row_ids:
            self.table.delete(*self.row_ids.values())
        self.row_ids.clear()
        self.row_statuses.clear()
        self._visible_rows.clear()
        self._visible_order.clear()
        self._row_data.clear()

    def _insert_file_row(self, index, path, source):
        try:
            name = str(Path(path).relative_to(source))
        except ValueError:
            name = Path(path).name
        values = name, 'Bekliyor', ''
        tags = ('pending', 'stripe') if index % 2 else ('pending',)
        self.row_ids[path] = self.table.insert('', 'end', iid=f'file_{index}',
                                              values=values, tags=tags)
        self.row_statuses[path] = 'pending'
        self._row_data[path] = dict(values=values, search=_search_text(' '.join(values)),
                                   order=index, tags=tags)

    def _queue_file_list(self, files):
        if len(files) <= 300:
            self._fill_files(files)
            return False
        self._prepare_file_list()
        self._pending_files = dict(iterator=iter(files), index=0, total=len(files),
                                   source=Path(self.source_folder.get()).resolve())
        return True

    def _fill_next_file_batch(self):
        pending = self._pending_files
        deadline = time.perf_counter()+.006
        while pending['index'] < pending['total']:
            self._insert_file_row(pending['index'], next(pending['iterator']), pending['source'])
            pending['index'] += 1
            if time.perf_counter() >= deadline:
                self.status_label.configure(text=f"Liste hazırlanıyor · {pending['index']} / {pending['total']}")
                return
        self._pending_files = None
        self.stat_values['total'].configure(text=str(pending['total']))
        self._apply_filters()
        if self._pending_preview:
            self._pending_preview = False
            self._finish_preview()

    def _finish_preview(self):
        self._set_busy(False)
        text = f'{len(self.row_ids)} {self._file_label} bulundu. Aktarım için hazır.'
        if self.stop_event.is_set():
            text = 'Klasör taraması durduruldu.'
        self.status_label.configure(text=text, text_color=MUTED)
        if self.close_pending:
            self._destroy_app()

    def _result_status_label(self, status, *, preview=None):
        if self.mode == 'k_factor' and status == 'success':
            if preview is None:
                preview = self.k_widgets.get('operation_preview', False)
            return 'Uygulamaya hazır' if preview else 'Uygulandı'
        return LABELS[status]

    def _update_row(self, path, status, detail="", *, preview=None):
        row = self.row_ids.get(path)
        if row:
            data = self._row_data[path]
            name = data['values'][0]
            striped = "stripe" in data['tags']
            values = name, self._result_status_label(status, preview=preview), detail
            tags = (status, "stripe") if striped else (status,)
            self.table.item(row, values=values, tags=tags)
            data.update(values=values, search=_search_text(' '.join(values)), tags=tags)
            self.row_statuses[path] = status
            wanted = FILTERS.get(self.status_filter.get())
            query = _search_text(self.search_query.get().strip())
            matches = (wanted is None or status == wanted) and query in data['search']
            changed = False
            position = bisect_left(self._visible_order, data['order'])
            if matches and row not in self._visible_rows:
                # Restore the original scan order without redrawing unrelated
                # rows on each worker event (large batches must stay responsive).
                self.table.move(row, "", position)
                self._visible_order.insert(position, data['order'])
                self._visible_rows.add(row)
                changed = True
            elif not matches and row in self._visible_rows:
                self.table.detach(row)
                self._visible_order.pop(position)
                self._visible_rows.remove(row)
                changed = True
            if changed:
                self._refresh_list_state()
            if matches:
                if self._worker_updates is not None:
                    self._worker_updates['row'] = row
                else:
                    self.table.see(row)

    def _append_log(self, message):
        text = f"{datetime.now():%H:%M:%S}  {message}\n"
        if self._worker_updates is not None:
            self._worker_updates['logs'].append(text)
        else:
            self._write_log(text)

    def _write_log(self, text):
        # Keep the reader's position when they scroll up during an export.
        follow = self.log_box.yview()[1] >= .999
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        if follow:
            self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _flush_worker_updates(self):
        updates, self._worker_updates = self._worker_updates, None
        if updates is None:
            return
        if updates['counts'] is not None:
            for key, widget in self.stat_values.items():
                configure_changed(widget, text=str(updates['counts'].get(key, 0)))
        if updates['total'] is not None:
            configure_changed(self.stat_values['total'], text=str(updates['total']))
        if updates['progress'] is not None:
            current, total = updates['progress']
            self.progress.set(current / total if total else 0)
        if updates['status']:
            configure_changed(self.status_label, **updates['status'])
        if updates['list_changed']:
            self._refresh_list_state()
        if updates['row'] in self._visible_rows:
            self.table.see(updates['row'])
        if updates['logs']:
            self._write_log(''.join(updates['logs']))

    def _open_output(self):
        folder = self.output_folder.get().strip()
        if folder and Path(folder).is_dir():
            try:
                os.startfile(folder)
            except (OSError, AttributeError) as error:
                self.status_label.configure(text=f"Klasör açılamadı: {error}", text_color=RED)
        else:
            self.status_label.configure(text="Çıktı klasörü bulunamadı. Geçerli bir klasör seçin.", text_color=AMBER)

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
                        writer.writerow((result["source"], result["output"],
                                         self._result_status_label(result["status"], preview=result.get('preview')),
                                         result["detail"]))
                self._append_log(f"Rapor kaydedildi: {path}")
            except OSError as error:
                self.status_label.configure(text=f"Rapor kaydedilemedi: {error}", text_color=RED)

    def _finish(self, summary):
        if self.mode == 'k_factor':
            expected_preview = self.k_widgets.get('operation_preview', False)
            actual_preview = summary.get('preview', expected_preview)
            self.k_widgets['operation_preview'] = actual_preview
            self.k_widgets['success_caption'].configure(text='Hazır' if actual_preview else 'Uygulanan')
            if not expected_preview and actual_preview:
                summary = dict(summary, state='error', error=(
                    'K/R uygulanmadı: uygulama isteğine yalnız kontrol sonucu geldi. '
                    'Montaja K/R uygula düğmesiyle yeniden deneyin.'))
        self._set_busy(False)
        for key, widget in self.stat_values.items():
            widget.configure(text=str(summary.get(key, 0)))
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
            preview = self.mode == 'k_factor' and summary.get('preview', self.k_widgets.get('operation_preview', False))
            if self.mode == 'k_factor':
                text = (f"{'Montaj kontrolü tamamlandı' if preview else 'K/R uygulaması tamamlandı'}"
                        f" · {summary['succeeded']} {'hazır' if preview else 'uygulanan'} parça, "
                        f"{summary['skipped']} atlanan, {summary['failed']} hatalı.")
                if preview:
                    text += ' K/R uygulanmadı. Montaja K/R uygula düğmesini kullanın.'
            else:
                text = f"Tamamlandı · {summary['succeeded']} {unit}, {summary['skipped']} atlanan, {summary['failed']} hatalı."
            if summary.get('partial'):
                text += f" {summary['partial']} parçada bazı biçimler hazır, bazıları tamamlanamadı."
            color = AMBER if summary["failed"] or summary.get('partial') else SUCCESS
        if summary.get('warnings'):
            text += ' · Uyarı: '+ '; '.join(summary['warnings'])
            color = AMBER
        self.status_label.configure(text=text, text_color=color)
        self._append_log(text)
        self.report_button.configure(state="normal" if self.results else "disabled")
        if self.mode == 'k_factor':
            self._finish_k_feedback(summary)
        if self.close_pending:
            self._destroy_app()
        elif self.mode == 'k_factor':
            self._continue_k_apply(summary)

    def _process_events(self):
        if self.mode == 'naming':
            return self._process_naming_events()
        if self.mode == 'bom':
            return self._process_bom_events()
        if self._pending_files is not None:
            self._fill_next_file_batch()
            if self._closed:
                return
            if self._pending_files is not None:
                self._poll_id = self.after(8, self._process_events)
                return
        # Retain every result/log, but paint counters and scrolling once per
        # bounded Tk turn. Leave time for the paint after consuming events.
        self._worker_updates = dict(counts=None, total=None, progress=None, status={},
                                    logs=[], row=None, list_changed=False)
        deadline = time.perf_counter()+.006
        handled = 0
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "files":
                    self._queue_file_list(value)
                elif event == "phase":
                    self._worker_updates['status'].update(text=value, text_color=MUTED)
                elif event == "total":
                    self._worker_updates['total'] = value
                elif event == "current":
                    self._update_row(value, "running")
                    action = ('Kontrol ediliyor' if self.k_widgets.get('operation_preview') else 'K/R uygulanıyor') if self.mode == 'k_factor' else 'Aktarılıyor'
                    self._worker_updates['status']['text'] = f"{action} · {Path(value).name}"
                elif event == "result":
                    self.results.append(value)
                    detail = value["detail"]
                    if self.mode == "dxf_dwg" and value.get("thickness_mm") is not None and value.get("quantity") is not None:
                        detail = f"{value['thickness_mm']:g} mm · {value['quantity']} adet · {detail}"
                    self._update_row(value["source"], value["status"], detail, preview=value.get('preview'))
                    label = self._result_status_label(value['status'], preview=value.get('preview'))
                    self._append_log(f"{label} · {Path(value['source']).name} · {value['detail']}")
                elif event == "counts":
                    self._worker_updates['counts'] = value
                    self._worker_updates['total'] = None
                elif event == "progress":
                    self._worker_updates['progress'] = value
                elif event == "log":
                    self._append_log(value)
                elif event in ("preview", "preview_error"):
                    if event == "preview":
                        self._pending_preview = self._queue_file_list(value)
                        if not self._pending_preview:
                            self._flush_worker_updates()
                            self._finish_preview()
                            break
                    else:
                        self._flush_worker_updates()
                        self._set_busy(False)
                        self.status_label.configure(text=value, text_color=RED)
                        if self.close_pending:
                            self._destroy_app()
                        break
                elif event == "done":
                    # Final summaries must not be overwritten by an earlier
                    # queued count/phase after the worker releases the GUI.
                    self._flush_worker_updates()
                    self._finish(value)
                    break
                if self._closed:
                    return
                handled += 1
                if self._pending_files is not None or handled >= 100 or time.perf_counter() >= deadline:
                    break
        except queue.Empty:
            pass
        finally:
            if not self._closed:
                self._flush_worker_updates()
            else:
                self._worker_updates = None
        if self._closed:
            return
        self._poll_id = self.after(8 if self._pending_files is not None or not self.events.empty() else 80, self._process_events)

    def _on_close(self):
        if self.busy:
            if messagebox.askyesno("İşlem sürüyor", "İşlemi durdurup uygulamayı kapatmak istiyor musunuz?", parent=self):
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
