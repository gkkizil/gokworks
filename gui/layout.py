"""GOKWORKS çalışma alanının açık/koyu tema uyumlu yerleşimi."""

from tkinter import ttk

import customtkinter as ctk

from gui.theme import (SIDEBAR, PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT,
                       ACCENT_BG, GREEN, AMBER, RED, SECONDARY, HOVER, UI_FONT, MONO_FONT)


class WorkspaceLayout:
    def _build_window(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        if not hasattr(self, "sidebar"):
            self._build_sidebar()
        if self.mode == 'iso_fits':
            return self._build_iso_workspace()
        if self.mode == 'geometric_tolerances':
            return self._build_gdt_workspace()
        if self.mode == 'k_factor':
            return self._build_k_workspace()
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=0)
        self.workspace.grid_columnconfigure(1, weight=1)
        self.workspace.grid_rowconfigure(2, weight=1)
        self._build_header()
        self.pdf_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 18))
        self.form_panel = ctk.CTkFrame(self.workspace, width=320, fg_color=INPUT,
                                     corner_radius=12, border_width=1, border_color=BORDER)
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
        self.status_label = self._label(self.workspace, "Hazır · Ana montajı SolidWorks'te aktif yapın." if self.mode == "k_factor" else "Hazır · Kaynak ve çıktı klasörünü seçin.",
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
        self.sidebar = ctk.CTkFrame(self, width=212, corner_radius=0, fg_color=SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(30, 32))
        badge = ctk.CTkFrame(brand, width=36, height=36, corner_radius=10, fg_color=ACCENT_BG)
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=self._icon("layers", ACCENT, 24)).place(
            relx=.5, rely=.5, anchor="center")
        self._label(brand, "GOKWORKS", 16, bold=True).grid(row=0, column=1, sticky="w")
        self._label(brand, "SolidWorks araçları", 11, MUTED).grid(row=1, column=1, sticky="w")
        self._label(self.sidebar, "ÇALIŞMA ALANLARI", 10, MUTED, True).grid(
            row=1, column=0, sticky="w", padx=22, pady=(0, 10))
        navigation = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        navigation.grid(row=2, column=0, sticky="ew", padx=12)
        navigation.grid_columnconfigure(0, weight=1)
        self.nav_buttons = {}
        self._nav_active = self.mode
        self._nav_fonts = {active: ctk.CTkFont(family=UI_FONT, size=13, weight='bold' if active else 'normal')
                           for active in (False, True)}
        for row, (key, title, icon) in enumerate((
            ("pdf", "PDF aktarımı", "file"), ("dxf_dwg", "DXF / DWG", "layers"),
            ("k_factor", "K FAKTÖR - RADIUS", "tools"),
            ("iso_fits", "ISO GEÇMELERİ", "ruler"),
            ("geometric_tolerances", "GEOMETRİK TOL.", "ruler"),
        )):
            active = key == self.mode
            button = ctk.CTkButton(
                navigation, text=title, image=self._icon(icon, ACCENT if active else MUTED),
                height=44, corner_radius=8, anchor="w", border_color=BORDER,
                border_width=1 if active else 0,
                fg_color=ACCENT_BG if active else "transparent", hover_color=SECONDARY,
                text_color=ACCENT if active else MUTED, text_color_disabled=MUTED,
                font=self._nav_fonts[active],
                command=lambda selected=key: self._switch_mode(selected),
                state="normal",
            )
            button.grid(row=row, column=0, sticky="ew", pady=(0, 6))
            self.nav_buttons[key] = button
        self._label(self.sidebar, "Belge ve sac metal araçları", 10, MUTED).grid(
            row=3, column=0, sticky="w", padx=24, pady=(4, 0))
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=5, column=0, sticky="ew", padx=20, pady=24)
        footer.grid_columnconfigure(0, weight=1)
        self._label(footer, "GÖRÜNÜM", 10, MUTED, True).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.theme_selector = ctk.CTkSegmentedButton(
            footer, values=["Açık", "Koyu"], variable=self.theme_mode, command=self._change_theme,
            height=34, fg_color=SECONDARY, selected_color=ACCENT_BG,
            selected_hover_color=HOVER, unselected_color=SECONDARY,
            unselected_hover_color=HOVER, text_color=TEXT,
            font=ctk.CTkFont(family=UI_FONT, size=12),
        )
        self.theme_selector.grid(row=1, column=0, sticky="ew")
        ctk.CTkFrame(footer, height=1, fg_color=BORDER).grid(row=2, column=0, sticky="ew", pady=18)
        self._label(footer, "MASAÜSTÜ OTOMASYONU", 10, MUTED, True).grid(row=3, column=0, sticky="w")
        self._label(footer, "Aktarım için SolidWorks\noturumu açık olmalı.", 11, MUTED,
                    justify="left").grid(row=4, column=0, sticky="w", pady=(4, 0))

    def _build_header(self):
        header = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.pdf_header = header
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 18))
        header.grid_columnconfigure(0, weight=1)
        self._label(header, "GOKWORKS  /  SAC PARAMETRELERİ" if self.mode == "k_factor" else "GOKWORKS  /  BELGE İŞLEMLERİ", 10, MUTED, True).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self._label(header, "K FAKTÖR - RADIUS" if self.mode == "k_factor" else "PDF Aktarımı" if self._is_pdf else "DXF / DWG Açınımı",
                    24, bold=True).grid(row=1, column=0, sticky="w")
        subtitle = ("Malzeme, takım ve BA hesabıyla montajdaki sac parçaları düzenleyin." if self.mode == "k_factor" else
                    "Teknik resimlerin tüm sayfalarını tek PDF'e aktarın." if self._is_pdf else
                    "Sac metal parçaları kalınlık ve toplam adetle kaydedin.")
        self._label(header, subtitle, 12, MUTED, wraplength=350, justify="left").grid(
            row=2, column=0, sticky="w", pady=(3, 0))
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=1, column=1, rowspan=2, sticky="e", padx=(12, 0))
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
        panel = ctk.CTkFrame(self.settings_body, fg_color=INPUT, corner_radius=12,
                             border_width=1, border_color=BORDER)
        panel.grid(row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        folders = ctk.CTkFrame(panel, fg_color="transparent")
        folders.grid(row=0, column=0, sticky="ew")
        folders.grid_columnconfigure(0, weight=1)
        for column, (title, hint, variable) in enumerate((
            ("Kaynak klasör", f"Klasördeki {self._extension} dosyaları aktarılır.", self.source_folder),
            ("Çıktı klasörü", "Her teknik resim için tek PDF dosyası." if self._is_pdf else
             "PARÇAADI - 2 mm - 12 adet.dxf", self.output_folder),
        )):
            card = ctk.CTkFrame(folders, fg_color="transparent")
            card.grid(row=column, column=0, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)
            self._folder_input(card, column, title, hint, variable)
        ctk.CTkFrame(panel, height=1, fg_color=BORDER).grid(row=1, column=0, sticky="ew", padx=16)
        options = ctk.CTkFrame(panel, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        tools = ctk.CTkFrame(options, fg_color="transparent")
        tools.pack(side="bottom", fill="x", pady=(12, 0))
        self.scan_button = self._button(tools, "Klasörü tara", self._scan, icon="search", width=116)
        self.scan_button.pack(fill="x", pady=(0, 6))
        self.open_button = self._button(tools, "Çıktı klasörü", self._open_output, icon="folder", width=126)
        self.open_button.pack(fill="x")
        self.controls.append(self.scan_button)
        for text, variable in (("Alt klasörleri tara", self.include_subfolders),
                               ("Üzerine yaz", self.overwrite_existing)):
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
            bends = self._checkbox(formats, "Büküm çizgileri", self.bend_lines)
            bends.pack(anchor="w")
            self._label(formats, "Adet kaynağı: aktif montaj\nAlt montajlar dahil", 10, MUTED,
                        justify="left").pack(anchor="w", pady=(8, 0))
            self.controls.extend((format_menu, bends))

    def _checkbox(self, parent, text, variable):
        return ctk.CTkCheckBox(
            parent, text=text, variable=variable, height=28, checkbox_width=18,
            checkbox_height=18, corner_radius=4, border_width=2, fg_color=ACCENT,
            hover_color=HOVER, checkmark_color=("#FFFFFF", "#10231D"),
            border_color=MUTED, text_color=TEXT,
            font=ctk.CTkFont(family=UI_FONT, size=12),
        )

    def _folder_input(self, parent, column, label, hint, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 10))
        frame.grid_columnconfigure(0, weight=1)
        self._label(frame, f"0{column + 1}   {label}", 13, bold=True).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        entry = ctk.CTkEntry(frame, textvariable=variable, height=38, corner_radius=7,
                             border_width=1, border_color=BORDER, fg_color=PANEL,
                             text_color=TEXT, font=(UI_FONT, 12))
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        browse = self._button(frame, "Gözat", lambda: self._choose_folder(variable, label),
                               icon="folder", width=88)
        browse.grid(row=1, column=1)
        self._label(frame, hint, 11, MUTED, wraplength=260, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.controls.extend((entry, browse))

    def _build_stats(self):
        self.stats_frame = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.stats_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        metrics = [
            ("total", "Toplam parça" if self.mode == "k_factor" else "Toplam dosya", TEXT, "file"), ("succeeded", "Başarılı", GREEN, "check"),
            ("skipped", "Atlanan", AMBER, "skip"), ("failed", "Hatalı", RED, "error"),
        ]
        for index, (key, caption, color, icon) in enumerate(metrics):
            self.stats_frame.grid_columnconfigure(index, weight=1, uniform="stats")
            card = ctk.CTkFrame(self.stats_frame, fg_color=INPUT, corner_radius=10,
                                 border_width=1, border_color=BORDER)
            card.grid(row=0, column=index, sticky="ew",
                       padx=(0 if index == 0 else 4, 0 if index == len(metrics)-1 else 4))
            card.grid_columnconfigure(0, weight=1)
            compact = self.mode == 'k_factor'
            self._label(card, caption, 11, MUTED).grid(row=0, column=0, sticky="w", padx=14,
                                                     pady=8 if compact else (8, 0))
            self.stat_values[key] = self._label(card, "0", 20, color, True)
            self.stat_values[key].grid(row=0 if compact else 1, column=1 if compact else 0,
                                      sticky="w", padx=14, pady=8 if compact else (0, 8))
            ctk.CTkLabel(card, text="", image=self._icon(icon, color, 20)).grid(
                row=0, column=2 if compact else 1, rowspan=1 if compact else 2, padx=(8, 14))

    def _build_results(self, parent=None):
        card = ctk.CTkFrame(self.workspace if parent is None else parent, fg_color=PANEL, corner_radius=12,
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
        self.result_tabs = ctk.CTkTabview(
            card, fg_color=PANEL, corner_radius=6, anchor="w", text_color=TEXT,
            command=self._resize_pdf_area,
            segmented_button_fg_color=PANEL, segmented_button_selected_color=ACCENT_BG,
            segmented_button_selected_hover_color=HOVER, segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color=SECONDARY,
        )
        self.result_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.result_tabs._segmented_button.configure(font=ctk.CTkFont(family=UI_FONT, size=12))
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
        self.empty_title = self._label(self.empty_state, "Aktarım için hazır", 14, bold=True)
        self.empty_title.pack(padx=12)
        self.empty_hint = self._label(self.empty_state, "Kaynak klasörü seçin ve Klasörü tara düğmesine basın.",
                                      11, MUTED, wraplength=400, justify="center")
        self.empty_hint.pack(padx=12, pady=(2, 0))
        self.empty_state.place(relx=.5, rely=.6, anchor="center")
        self.results_footer = ctk.CTkFrame(files_tab, fg_color="transparent")
        self.results_footer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.results_footer.grid_columnconfigure(0, weight=1)
        self.results_hint = self._label(self.results_footer, "Ayrıntılar: çift tık  ·  Ctrl+F: ara", 10, MUTED, wraplength=220, justify="left")
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
        self._table_style_key = ctk.get_appearance_mode(), scale
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Gok.Treeview", background=color(PANEL), fieldbackground=color(PANEL),
                        foreground=color(TEXT), borderwidth=0, bordercolor=color(PANEL),
                        lightcolor=color(PANEL), darkcolor=color(PANEL), rowheight=round(36 * scale),
                        font=(UI_FONT, -round(13 * scale)))
        style.configure("Gok.Treeview.Heading", background=color(INPUT), foreground=color(MUTED),
                        relief="flat", padding=(round(8 * scale), round(9 * scale)),
                        font=(UI_FONT, -round(11 * scale), "bold"))
        style.map("Gok.Treeview.Heading", background=[("active", color(SECONDARY))])
        style.map("Gok.Treeview", background=[("selected", color(ACCENT_BG))],
                  foreground=[("selected", color(TEXT))])
        tables = {page['table'] for page in self._pages.values() if 'table' in page}
        if self.mode not in ('iso_fits', 'geometric_tolerances'):
            tables.add(self.table)
        for table in tables:
            table.column("status", width=round(152 * scale), minwidth=round(80 * scale))
            for column in ("file", "detail"):
                table.column(column, minwidth=round(80 * scale))
            for status, value in (("pending", MUTED), ("running", ACCENT), ("success", GREEN),
                                  ("partial", AMBER), ("skipped", AMBER), ("error", RED)):
                table.tag_configure(status, foreground=color(value))
            table.tag_configure("stripe", background=color(INPUT))
