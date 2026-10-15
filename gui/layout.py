"""GOKWORKS çalışma alanının açık/koyu tema uyumlu yerleşimi."""

from tkinter import ttk

import customtkinter as ctk

from gui.icons import make_logo
from gui.text import BOM_TITLE, KR_TITLE, KR_NAV_TITLE
from gui.theme import (BG, SIDEBAR, PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT,
                       ACCENT_BG, SUCCESS, AMBER, RED, SECONDARY, HOVER, UI_FONT, MONO_FONT,
                       NAV_TEXT, NAV_MUTED, NAV_ACTIVE, NAV_ACCENT, NAV_HOVER, PRIMARY_TEXT)


class ResultsTabview(ctk.CTkTabview):
    # CTk uses this value for both the selector and its reserved grid space.
    _button_height = 34

    def set(self, name):
        if name not in self._tab_dict:
            raise ValueError(f"CTkTabview has no tab named '{name}'")
        if name == self._current_name and self._tab_dict[name].winfo_manager():
            return
        self._current_name = name
        self._segmented_button.set(name)
        self._set_grid_current_tab()
        self._tab_dict[name].tkraise()
        # Paint the replacement while the previous tab remains underneath.
        # CTk's mouse path unmaps it first; set() instead schedules a captured
        # 100 ms cleanup that can unmap a newer selection during rapid changes.
        if self.winfo_viewable():
            self.update_idletasks()
        self._grid_forget_all_tabs(exclude_name=self._current_name)

    def _segmented_button_callback(self, selected_name):
        self.set(selected_name)
        if self._command is not None:
            self._command()


class WorkspaceLayout:
    def _workspace_shell(self):
        # CTk scrollbars flush idle geometry during construction. Keep the page
        # unmapped until complete so each child does not relayout the window.
        return ctk.CTkFrame(self, fg_color=BG, corner_radius=0, border_width=0)

    def _show_workspace(self):
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=16)

    def _build_window(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        if not hasattr(self, "sidebar"):
            self._build_sidebar()
        if self.mode == 'bolt':
            return self._build_bolt_workspace()
        if self.mode == 'weight':
            return self._build_weight_workspace()
        if self.mode == 'naming':
            return self._build_naming_workspace()
        if self.mode == 'bom':
            return self._build_bom_workspace()
        if self.mode == 'iso_fits':
            return self._build_iso_workspace()
        if self.mode == 'geometric_tolerances':
            return self._build_gdt_workspace()
        if self.mode == 'k_factor':
            return self._build_k_workspace()
        self.workspace = self._workspace_shell()
        self.workspace.grid_columnconfigure(0, weight=0)
        self.workspace.grid_columnconfigure(1, weight=1)
        self.workspace.grid_rowconfigure(2, weight=1)
        self._build_header()
        self.pdf_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 18))
        self.form_panel = ctk.CTkFrame(self.workspace, width=320, fg_color=PANEL,
                                     corner_radius=16, border_width=1, border_color=BORDER)
        self.form_panel.grid(row=2, column=0, sticky="nsew", padx=(24, 0))
        self.form_panel.grid_propagate(False)
        self.form_panel.grid_columnconfigure(0, weight=1)
        self.form_panel.grid_rowconfigure(0, weight=1)
        self._build_settings()
        self._build_stats()
        self.stats_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 14))
        self._build_results()
        self.result_tabs.master.grid(row=2, column=1, sticky="nsew", padx=(12, 24))
        self.result_tabs.master.grid_propagate(False)
        self.status_label = self._label(self.workspace, "Hazır · SolidWorks'te ana montajı etkinleştirin." if self.mode == "k_factor" else "Hazır · Kaynak ve çıktı klasörünü seçin.",
                                        12, MUTED, anchor="w")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", padx=24, pady=(10, 6))
        self.progress = ctk.CTkProgressBar(self.workspace, height=4, corner_radius=2,
                                          fg_color=BORDER, progress_color=ACCENT)
        self.progress.grid(row=4, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 18))
        self.progress.set(0)
        self._refresh_list_state()
        self.workspace.bind("<Configure>", self._resize_pdf_area)
        # Initial widget construction can emit Configure before the binding
        # exists. Schedule the first fit explicitly, without waiting for resize.
        self._resize_pdf_area()

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=208, corner_radius=18, fg_color=SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(12, 0), pady=12)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_brand = brand
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 18))
        self.brand_logo = make_logo(32)
        self.brand_badge = ctk.CTkLabel(brand, text="", image=self.brand_logo,
                                       width=42, height=42, fg_color="#FFFFFF", corner_radius=10)
        self.brand_badge.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self._label(brand, "GOKWORKS", 16, NAV_TEXT, bold=True).grid(row=0, column=1, sticky="w")
        self._label(brand, "Mühendislik araçları", 10, NAV_MUTED).grid(row=1, column=1, sticky="w")
        self.sidebar_category = self._label(self.sidebar, "AKTARIM VE MONTAJ", 10, NAV_MUTED, True)
        self.sidebar_category.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 10))
        navigation = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        navigation.grid(row=2, column=0, sticky="ew", padx=12)
        navigation.grid_columnconfigure(0, weight=1)
        self.nav_buttons = {}
        self._nav_active = self.mode
        self._nav_fonts = {active: ctk.CTkFont(family=UI_FONT, size=13, weight='bold' if active else 'normal')
                           for active in (False, True)}
        for row, (key, title, icon) in enumerate((
            ("pdf", "PDF aktarımı", "file"), ("dxf_dwg", "DXF / DWG", "layers"),
            ("bom", BOM_TITLE, "tree"),
            ("naming", "İsimlendirme aracı", "copy"),
            ("k_factor", KR_NAV_TITLE, "tools"),
            ("bolt", "Cıvata hesabı", "bolt"),
            ("weight", "Ağırlık hesabı", "weight"),
            ("iso_fits", "ISO geçmeleri", "ruler"),
            ("geometric_tolerances", "Geometrik toleranslar", "target"),
        )):
            if row == 4:
                self.navigation_section = self._label(navigation, "MÜHENDİSLİK HESAPLARI", 10, NAV_MUTED, True)
                self.navigation_section.grid(row=row, column=0, sticky="w", padx=10, pady=(22, 10))
            active = key == self.mode
            button = ctk.CTkButton(
                navigation, text=title, image=self._icon(icon, NAV_ACCENT if active else NAV_MUTED),
                height=44, corner_radius=12, anchor="w", border_color=NAV_ACTIVE,
                border_width=0,
                fg_color=NAV_ACTIVE if active else "transparent", hover_color=NAV_HOVER,
                text_color=NAV_ACCENT if active else NAV_MUTED, text_color_disabled=NAV_MUTED,
                font=self._nav_fonts[active],
                command=lambda selected=key: self._request_mode(selected),
                state="normal",
            )
            button.grid(row=row if row < 4 else row+1, column=0, sticky="ew", pady=(0, 4))
            self.nav_buttons[key] = button
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_footer = footer
        footer.grid(row=5, column=0, sticky="ew", padx=18, pady=16)
        footer.grid_columnconfigure(0, weight=1)
        self._label(footer, "GÖRÜNÜM", 10, NAV_MUTED, True).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.theme_selector = ctk.CTkSegmentedButton(
            footer, values=["Açık", "Koyu"], variable=self.theme_mode, command=self._change_theme,
            height=36, fg_color=SIDEBAR, selected_color=NAV_ACTIVE,
            selected_hover_color=NAV_HOVER, unselected_color=SIDEBAR,
            unselected_hover_color=NAV_HOVER, text_color=NAV_TEXT,
            font=ctk.CTkFont(family=UI_FONT, size=12),
        )
        self.theme_selector.grid(row=1, column=0, sticky="ew")
        self.sidebar_hint = ctk.CTkFrame(footer, fg_color='transparent')
        self.sidebar_hint.grid(row=2, column=0, sticky='ew')
        ctk.CTkFrame(self.sidebar_hint, height=1, fg_color=NAV_HOVER).grid(row=0, column=0, sticky="ew", pady=18)
        self._label(self.sidebar_hint, "SolidWorks masaüstü", 11, NAV_TEXT, True).grid(row=1, column=0, sticky="w")
        self._label(self.sidebar_hint, "CAD işlemleri için SolidWorks\noturumu açık olmalı.", 10, NAV_MUTED,
                    justify="left").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.sidebar.bind('<Configure>', self._resize_sidebar, add='+')
        self._resize_sidebar()

    def _resize_sidebar(self, event=None):
        if self._closed:
            return
        compact = self.sidebar.winfo_height()/self.sidebar._get_widget_scaling() < 780
        if getattr(self, '_sidebar_compact', None) == compact:
            return
        self._sidebar_compact = compact
        self.sidebar_brand.grid_configure(pady=(8, 10) if compact else (18, 18))
        self.sidebar_category.grid_configure(pady=(0, 6) if compact else (0, 10))
        self.navigation_section.grid_configure(pady=(12, 8) if compact else (22, 10))
        self.sidebar_footer.grid_configure(pady=8 if compact else 16)
        for button in self.nav_buttons.values():
            button.configure(height=36 if compact else 44)
            button.grid_configure(pady=(0, 2 if compact else 4))
        if compact:
            from gui.rendering import hide_grid
            hide_grid(self.sidebar_hint)
        else:
            self.sidebar_hint.grid(row=2, column=0, sticky='ew')

    def _page_header(self, title, subtitle, section, icon):
        """Shared page identity and a consistent action area."""
        header = ctk.CTkFrame(self.workspace, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 16))
        header.grid_columnconfigure(0, weight=1)
        identity = ctk.CTkFrame(header, fg_color="transparent")
        identity.grid(row=0, column=0, sticky="w")
        identity.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(identity, text="", image=self._icon(icon, ACCENT, 25),
                    width=48, height=48, fg_color=ACCENT_BG, corner_radius=14).grid(
            row=0, column=0, rowspan=3, padx=(0, 12), sticky="w")
        labels = {
            'eyebrow': self._label(identity, section, 10, MUTED, True),
            'title': self._label(identity, title, 26, bold=True),
            'subtitle': self._label(identity, subtitle, 12, MUTED, wraplength=300, justify="left"),
        }
        for row, label in enumerate(labels.values()):
            label.grid(row=row, column=1, sticky="w", pady=(0, 3 if row < 2 else 0))
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        return header, actions, labels

    def _build_header(self):
        subtitle = ("Girdiğiniz K ve R değerlerini parçaların Sac-Levha parametrelerine yazın." if self.mode == "k_factor" else
                    "Her teknik resmin tüm sayfalarını tek PDF dosyasına aktarın." if self._is_pdf else
                    "Sac açınımlarını kalınlık ve montaj adediyle adlandırıp kaydedin.")
        self.pdf_header, actions, _ = self._page_header(
            KR_TITLE if self.mode == "k_factor" else "PDF aktarımı" if self._is_pdf else "DXF / DWG açınımı",
            subtitle, "MÜHENDİSLİK / SAC METAL" if self.mode == "k_factor" else "AKTARIM / BELGELER",
            "tools" if self.mode == "k_factor" else "file" if self._is_pdf else "layers")
        self.start_button = self._button(actions, self._start_text, self._start_export,
                                         primary=True, icon="arrow", width=224)
        self.start_button.configure(height=42)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = self._button(actions, "Durdur", self._request_stop,
                                        icon="stop", width=92, state="disabled")
        self.stop_button.configure(height=42)
        self.stop_button.pack(side="left")

    def _build_settings(self):
        if self.mode == "k_factor":
            return self._build_k_settings()
        height = 340
        self.settings_body = ctk.CTkScrollableFrame(
            self.form_panel, height=height, corner_radius=0, fg_color="transparent",
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED,
        )
        self.settings_body.grid(row=0, column=0, sticky="nsew", padx=6, pady=8)
        self.settings_body.grid_columnconfigure(0, weight=1)
        self.settings_body._scrollbar.configure(height=24, width=10)
        self._settings_height = height
        panel = ctk.CTkFrame(self.settings_body, fg_color="transparent", corner_radius=0)
        panel.grid(row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        folders = ctk.CTkFrame(panel, fg_color="transparent")
        folders.grid(row=0, column=0, sticky="ew")
        folders.grid_columnconfigure(0, weight=1)
        for column, (title, hint, variable) in enumerate((
            ("Kaynak klasörü", f"Klasördeki {self._extension} dosyaları aktarılır.", self.source_folder),
            ("Çıktı klasörü", "Her teknik resim için tek PDF dosyası." if self._is_pdf else
             "PARÇA ADI - 2 mm - 12 adet.dxf", self.output_folder),
        )):
            card = ctk.CTkFrame(folders, fg_color="transparent")
            card.grid(row=column, column=0, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)
            self._folder_input(card, column, title, hint, variable)
        ctk.CTkFrame(panel, height=1, fg_color=BORDER).grid(row=1, column=0, sticky="ew", padx=16)
        options = ctk.CTkFrame(panel, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        self._label(options, 'SEÇENEKLER', 10, MUTED, True).pack(anchor='w', pady=(0, 8))
        tools = ctk.CTkFrame(options, fg_color="transparent")
        tools.pack(side="bottom", fill="x", pady=(12, 0))
        self.scan_button = self._button(tools, "Klasörü tara", self._scan, icon="search", width=116)
        self.scan_button.pack(fill="x", pady=(0, 6))
        self.open_button = self._button(tools, "Klasörü aç", self._open_output, icon="folder", width=126)
        self.open_button.pack(fill="x")
        self.controls.append(self.scan_button)
        for text, variable in (("Alt klasörleri tara", self.include_subfolders),
                               ("Mevcut dosyaların üzerine yaz", self.overwrite_existing)):
            control = self._checkbox(options, text, variable)
            control.pack(anchor="w", pady=4)
            self.controls.append(control)
        if not self._is_pdf:
            formats = ctk.CTkFrame(panel, fg_color="transparent")
            formats.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
            self._label(formats, "Biçim", 12, MUTED).pack(anchor="w", pady=(0, 6))
            format_menu = ctk.CTkSegmentedButton(
                formats, values=["DXF", "DWG"], variable=self.output_format,
                height=32, fg_color=SECONDARY, selected_color=ACCENT_BG,
                selected_hover_color=HOVER, unselected_color=SECONDARY,
                unselected_hover_color=HOVER, text_color=TEXT,
                font=ctk.CTkFont(family=UI_FONT, size=12),
            )
            format_menu.pack(fill="x", pady=(0, 8))
            bends = self._checkbox(formats, "Büküm çizgilerini ekle", self.bend_lines)
            bends.pack(anchor="w")
            thickness = self._checkbox(formats, "Sac kalınlığına göre klasörle", self.group_by_thickness)
            thickness.pack(anchor="w", pady=(4, 0))
            self._label(formats, "Çıktı / 1,5 mm / parça.dxf", 10, MUTED,
                        justify="left").pack(anchor="w", pady=(2, 0))
            self._label(formats, "Adet kaynağı: aktif montaj\nAlt montajlar dahil", 10, MUTED,
                        justify="left").pack(anchor="w", pady=(8, 0))
            self.controls.extend((format_menu, bends, thickness))

    def _checkbox(self, parent, text, variable):
        return ctk.CTkCheckBox(
            parent, text=text, variable=variable, height=28, checkbox_width=18,
            checkbox_height=18, corner_radius=4, border_width=2, fg_color=ACCENT,
            hover_color=HOVER, checkmark_color=PRIMARY_TEXT,
            border_color=MUTED, text_color=TEXT,
            font=ctk.CTkFont(family=UI_FONT, size=12),
        )

    def _folder_input(self, parent, column, label, hint, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 10))
        frame.grid_columnconfigure(0, weight=1)
        heading = ctk.CTkFrame(frame, fg_color='transparent')
        heading.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        self._label(heading, f'0{column+1}', 11, ACCENT, True, width=28, height=28,
                    fg_color=ACCENT_BG, corner_radius=8).pack(side='left', padx=(0, 9))
        self._label(heading, label, 13, bold=True).pack(side='left')
        entry = ctk.CTkEntry(frame, textvariable=variable, height=38, corner_radius=10,
                             border_width=1, border_color=BORDER, fg_color=INPUT,
                             text_color=TEXT, font=(UI_FONT, 12))
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        browse = self._button(frame, "Göz at", lambda: self._choose_folder(variable, label),
                               icon="folder", width=88)
        browse.grid(row=1, column=1)
        self._label(frame, hint, 11, MUTED, wraplength=260, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.controls.extend((entry, browse))

    def _build_stats(self):
        self.stats_frame = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.stats_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        metrics = [
            ("total", "Toplam parça" if self.mode == "k_factor" else "Toplam dosya", TEXT, "file"), ("succeeded", "Uygulanan" if self.mode == "k_factor" else "Başarılı", SUCCESS, "check"),
            ("skipped", "Atlanan", AMBER, "skip"), ("failed", "Hatalı", RED, "error"),
        ]
        for index, (key, caption, color, icon) in enumerate(metrics):
            self.stats_frame.grid_columnconfigure(index, weight=1, uniform="stats")
            card = ctk.CTkFrame(self.stats_frame, fg_color=PANEL, corner_radius=16,
                                 border_width=1, border_color=BORDER)
            card.grid(row=0, column=index, sticky="ew",
                       padx=(0 if index == 0 else 4, 0 if index == len(metrics)-1 else 4))
            card.grid_columnconfigure(0, weight=1)
            compact = self.mode == 'k_factor'
            caption_label = self._label(card, caption, 11, MUTED)
            caption_label.grid(row=0, column=0, sticky="w", padx=14,
                               pady=8 if compact else (8, 0))
            if compact and key == 'succeeded':
                self.k_widgets['success_caption'] = caption_label
            self.stat_values[key] = self._label(card, "0", 20 if compact else 26, color, True)
            self.stat_values[key].grid(row=0 if compact else 1, column=1 if compact else 0,
                                      sticky="w", padx=14, pady=8 if compact else (0, 8))
            if not compact:
                ctk.CTkLabel(card, text="", image=self._icon(icon, color, 20),
                            width=34, height=34, fg_color=INPUT, corner_radius=10).grid(
                    row=0, column=1, rowspan=2, padx=(8, 14))

    def _build_results(self, parent=None):
        card = ctk.CTkFrame(self.workspace if parent is None else parent, fg_color=PANEL, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.grid(row=3, column=0, sticky="nsew", padx=24)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        self.results_header = ctk.CTkFrame(card, fg_color="transparent")
        self.results_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 0))
        self.results_header.grid_columnconfigure(0, weight=1)
        self.results_title = self._label(self.results_header, "Montaj sonuçları" if self.mode == "k_factor" else "Dosyalar ve sonuçlar", 15, bold=True, wraplength=220, justify="left")
        self.results_title.grid(row=0, column=0, sticky="w")
        self.report_button = self._button(self.results_header, "Rapor kaydet", self._save_report,
                                          icon="download", width=136, state="disabled")
        self.report_button.configure(height=34)
        self.report_button.grid(row=0, column=1)
        self.result_tabs = ResultsTabview(
            card, fg_color=PANEL, corner_radius=6, anchor="w", text_color=TEXT,
            command=self._resize_pdf_area,
            segmented_button_fg_color=PANEL, segmented_button_selected_color=ACCENT_BG,
            segmented_button_selected_hover_color=HOVER, segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color=SECONDARY,
        )
        self.result_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.result_tabs._segmented_button.configure(font=ctk.CTkFont(family=UI_FONT, size=12, weight="bold"))
        files_tab = self.result_tabs.add("Dosyalar")
        log_tab = self.result_tabs.add("Günlük")
        files_tab.grid_columnconfigure(0, weight=1)
        files_tab.grid_rowconfigure(1, weight=1)
        self.files_toolbar = ctk.CTkFrame(files_tab, fg_color="transparent")
        self.files_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.files_toolbar.grid_columnconfigure(0, weight=1)
        search = ctk.CTkFrame(self.files_toolbar, height=32, corner_radius=6,
                              fg_color=INPUT, border_width=1, border_color=BORDER)
        search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        search.grid_columnconfigure(1, weight=1)
        self._label(search, "Ara", 11, MUTED, image=self._icon("search", MUTED, 16),
                    compound="left").grid(row=0, column=0, padx=(10, 6))
        self.search_entry = ctk.CTkEntry(
            search, textvariable=self.search_query, height=30, corner_radius=0,
            fg_color=INPUT, text_color=TEXT, border_width=0, font=(UI_FONT, 12),
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=1)
        self.filter_menu = ctk.CTkOptionMenu(
            self.files_toolbar, variable=self.status_filter,
            values=["Tüm durumlar", "Bekleyen", "İşleniyor", "Başarılı", "Atlanan", "Hatalı"],
            width=132, height=32, fg_color=SECONDARY, button_color=SECONDARY,
            button_hover_color=HOVER, dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
            dropdown_text_color=TEXT, text_color=TEXT,
            font=ctk.CTkFont(family=UI_FONT, size=12), dropdown_font=ctk.CTkFont(family=UI_FONT, size=12),
        )
        self.filter_menu.grid(row=0, column=1, padx=(0, 8))
        clear = self._button(self.files_toolbar, "Temizle", self._clear_filters, icon="close", width=88)
        self.clear_filter_button = clear
        clear.configure(height=32)
        clear.grid(row=0, column=2)
        self.table = ttk.Treeview(files_tab, columns=("file", "status", "detail"),
                                  show="headings", style="Gok.Treeview", selectmode="browse")
        for name, caption, width in (
            ("file", "Teknik resim" if self._is_pdf else "Parça", 270),
            ("status", "Durum", 108), ("detail", "K, R, takım ve BA" if self.mode == "k_factor" else "Açıklama" if self._is_pdf else "Kalınlık, adet ve açıklama", 340),
        ):
            self.table.heading(name, text=caption, anchor="w")
            self.table.column(name, width=width, minwidth=80, stretch=name != "status")
        self.table.grid(row=1, column=0, sticky="nsew")
        scroll = ctk.CTkScrollbar(files_tab, command=self.table.yview, width=10,
                                  fg_color=PANEL, button_color=BORDER, button_hover_color=MUTED)
        scroll.grid(row=1, column=1, sticky="ns")
        horizontal = ctk.CTkScrollbar(files_tab, orientation="horizontal", command=self.table.xview,
                                      height=10, fg_color=PANEL, button_color=BORDER, button_hover_color=MUTED)
        horizontal.grid(row=2, column=0, sticky="ew")
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.bind("<Double-1>", self._show_detail)
        self.table.bind("<Return>", self._show_detail)
        self.empty_state = ctk.CTkFrame(self.table, fg_color=PANEL, bg_color=PANEL, corner_radius=0)
        ctk.CTkLabel(self.empty_state, text="", width=52, height=52,
                     fg_color=ACCENT_BG, corner_radius=14,
                     image=self._icon("file" if self._is_pdf else "layers", ACCENT, 28)).pack(pady=(0, 14))
        self.empty_title = self._label(self.empty_state, "Aktarım için hazır", 16, bold=True)
        self.empty_title.pack(padx=12)
        self.empty_hint = self._label(self.empty_state, "Kaynak klasörü seçin ve Klasörü tara düğmesine basın.",
                                      11, MUTED, wraplength=400, justify="center")
        self.empty_hint.pack(padx=12, pady=(2, 0))
        self.empty_state.place(relx=.5, rely=.52, anchor="center")
        self.results_footer = ctk.CTkFrame(files_tab, fg_color="transparent")
        self.results_footer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.results_footer.grid_columnconfigure(0, weight=1)
        self.results_hint = self._label(self.results_footer, "Ayrıntı: çift tıklayın · Ctrl+F: ara", 10, MUTED, wraplength=220, justify="left")
        self.results_hint.grid(row=0, column=0, sticky="w")
        self.visible_count = self._label(self.results_footer, "0 / 0 dosya", 10, MUTED)
        self.visible_count.grid(row=0, column=1, sticky="e")
        log_tab.grid_rowconfigure(0, weight=1)
        log_tab.grid_columnconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(log_tab, fg_color=INPUT, text_color=TEXT,
                                     wrap="word", font=(MONO_FONT, 12))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")
        self._configure_table_style()

    def _configure_table_style(self):
        color = lambda value: value[1 if ctk.get_appearance_mode() == "Dark" else 0]
        scale = self.workspace._get_widget_scaling()
        style_key = ctk.get_appearance_mode(), scale
        style = ttk.Style(self)
        if style.theme_use() != 'clam':
            style.theme_use('clam')
        if getattr(self, '_table_style_key', None) != style_key:
            style.configure("Gok.Treeview", background=color(PANEL), fieldbackground=color(PANEL),
                            foreground=color(TEXT), borderwidth=0, bordercolor=color(PANEL),
                            lightcolor=color(PANEL), darkcolor=color(PANEL), rowheight=round(40 * scale),
                            font=(UI_FONT, -round(13 * scale)))
            style.configure("Gok.Treeview.Heading", background=color(INPUT), foreground=color(MUTED),
                            relief="flat", padding=(round(8 * scale), round(9 * scale)),
                            font=(UI_FONT, -round(11 * scale), "bold"))
            style.map("Gok.Treeview.Heading", background=[("active", color(SECONDARY))])
            style.map("Gok.Treeview", background=[("selected", color(ACCENT_BG))],
                      foreground=[("selected", color(TEXT))])
            self._table_style_key = style_key
        tables = {page['table'] for page in self._pages.values() if 'table' in page}
        if self.mode not in ('iso_fits', 'geometric_tolerances', 'bom', 'bolt', 'naming', 'weight'):
            tables.add(self.table)
        for table in tables:
            if getattr(table, '_gok_style_key', None) == style_key:
                continue
            table.column("status", width=round(152 * scale), minwidth=round(80 * scale))
            for column in ("file", "detail"):
                table.column(column, minwidth=round(80 * scale))
            for status, value in (("pending", MUTED), ("running", ACCENT), ("success", SUCCESS),
                                  ("partial", AMBER), ("skipped", AMBER), ("error", RED)):
                table.tag_configure(status, foreground=color(value))
            table.tag_configure("stripe", background=color(INPUT))
            table._gok_style_key = style_key
        bom_pages = [page['bom_widgets'] for page in self._pages.values() if 'bom_widgets' in page]
        if self.mode == 'bom' and self.bom_widgets not in bom_pages:
            bom_pages.append(self.bom_widgets)
        for widgets in bom_pages:
            self._style_bom_tables(widgets)
