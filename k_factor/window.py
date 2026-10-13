"""K/R çalışma alanı: takım kataloğu, elle hesap ve montaj işçisi."""

import threading
import tkinter as tk

import customtkinter as ctk
from gui.rendering import configure_changed, hide_grid

from gui.theme import PANEL, INPUT, BORDER, TEXT, MUTED, RED, AMBER, SECONDARY, HOVER, UI_FONT, ACCENT_BG, ACCENT
from k_factor.apply import update_assembly
from k_factor.rules import (MATERIALS, DIE_OPENINGS, PUNCH_RADII, TOOL_ANGLES, Recipe, ManualAssignment, calculate,
                            number, ba_from_outside_dimensions)

AUTO_DIE = "Otomatik (8 × t)"
AUTOMATIC_TAB, MANUAL_TAB = "Malzeme / takım", "Manuel K / R"
RESULTS_TAB = "Montaj sonuçları"


class KFactorView:
    def _build_k_workspace(self):
        self.workspace = self._workspace_shell()
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        self._build_header()
        self.pdf_header.grid_configure(pady=(12, 8))
        self._build_stats()
        self.stats_frame.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 8))
        view = tk.StringVar(self, self.k_state['assignment_mode'].get())
        self.k_widgets['work_view'] = view
        selector = ctk.CTkSegmentedButton(self.workspace, variable=view,
            values=[AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB], command=self._select_k_view,
            height=42, dynamic_resizing=False, fg_color=SECONDARY, selected_color=PANEL,
            selected_hover_color=HOVER, unselected_color=SECONDARY,
            unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 13, 'bold'))
        selector.grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 8))
        self.k_widgets['assignment_tabs'] = selector
        self.controls.append(selector)
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=3, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.k_widgets['body'] = body
        self.form_panel = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.form_panel.grid(row=0, column=0, sticky='nsew')
        self.form_panel.grid_propagate(False)
        self.form_panel.grid_columnconfigure(0, weight=1)
        self.form_panel.grid_rowconfigure(0, weight=1)
        self._build_k_settings()
        self._build_results(parent=body)
        self.result_tabs.master.grid(row=0, column=0, sticky='nsew', padx=0)
        self.result_tabs.master.grid_propagate(False)
        copy = self._button(self.results_header, 'Günlüğü kopyala', self._copy_k_log,
                            icon='copy', width=140, state='disabled')
        copy.grid(row=0, column=2, padx=(8, 0))
        self.k_widgets['copy_log'] = copy
        self._build_k_actions(self.workspace)
        self.status_label = self._label(self.workspace, 'Hazır · SolidWorks’te ana montajı etkinleştirin.',
                                        12, MUTED, anchor='w')
        self.status_label.grid(row=5, column=0, sticky='ew', padx=24, pady=(4, 4))
        self.progress = ctk.CTkProgressBar(self.workspace, height=4, corner_radius=2,
                                         fg_color=BORDER, progress_color=ACCENT)
        self.progress.grid(row=6, column=0, sticky='ew', padx=24, pady=(0, 8))
        self.progress.set(0)
        self._refresh_list_state()
        self._select_k_view(view.get())
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._resize_pdf_area()

    def _create_k_state(self, saved):
        defaults = dict(material=MATERIALS[0].label, punch="1", die=AUTO_DIE,
                        thickness="2", angle="90", radius="", method="Tablo",
                        ba="", outside_a="", outside_b="", flat="")
        defaults.update(punch_angle="85", die_angle="85")
        defaults.update(assignment_mode=AUTOMATIC_TAB, manual_thickness="2", manual_k="", manual_r="")
        self.k_state = {key: tk.StringVar(self, value=str(saved.get(f"kr_{key}", value)))
                        for key, value in defaults.items()}
        if self.k_state["material"].get() not in [m.label for m in MATERIALS]:
            self.k_state["material"].set(MATERIALS[0].label)
        if self.k_state["method"].get() not in ("Tablo", "BA ölçümü"):
            self.k_state["method"].set("Tablo")
        if self.k_state["assignment_mode"].get() not in (AUTOMATIC_TAB, MANUAL_TAB):
            self.k_state["assignment_mode"].set(AUTOMATIC_TAB)
        self.k_state["save"] = tk.BooleanVar(self, value=False)  # explicit each session
        self.k_state["all_bends"] = tk.BooleanVar(self, value=saved.get("kr_all_bends", True) is True)
        self.k_widgets = {}

    def _build_k_settings(self):
        self.settings_body = ctk.CTkScrollableFrame(
            self.form_panel, height=340, corner_radius=0, fg_color="transparent",
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        self.settings_body.grid(row=0, column=0, sticky="nsew", padx=6, pady=(8, 0))
        self.settings_body.grid_columnconfigure(0, weight=1)
        # The CTk scrollbar defaults to 200 px and otherwise prevents the
        # settings viewport shrinking enough to leave room for the results.
        self.settings_body._scrollbar.configure(height=24, width=10)
        self._settings_height = 340
        panel = ctk.CTkFrame(self.settings_body, fg_color="transparent", corner_radius=0)
        panel.grid(row=1, column=0, sticky="ew")
        self.k_widgets["automatic_panel"] = panel
        for column in range(3):
            panel.grid_columnconfigure(column, weight=1, uniform="kr")
        self._label(panel, "Malzeme ve takım · havada büküm", 14, bold=True).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        for column, (key, label, values) in enumerate((
            ("material", "Hesapta kullanılacak malzeme", [m.label for m in MATERIALS]),
            ("punch", "Üst bıçak yarıçapı R (mm)", [f"{r:g}" for r in PUNCH_RADII]),
            ("die", "Alt kalıp V açıklığı (mm)", [AUTO_DIE] + [str(v) for v in DIE_OPENINGS]),
        )):
            self._k_field(panel, key, label, 1, column, values=values,
                          readonly=key == "material")
        for column, (key, label) in enumerate((("punch_angle", "Üst bıçak açısı (°)"),
                                                ("die_angle", "Alt kalıp açısı (°)"))):
            self._k_field(panel, key, label, 2, column, values=[str(a) for a in TOOL_ANGLES])
        self._label(panel, "Malzeme tüm saclar için kullanılır. Özel takım ölçüsü yazabilirsiniz; otomatik V parçanın kalınlığına göre seçilir.",
                    11, MUTED, wraplength=225, justify="left").grid(
            row=2, column=2, sticky="w", padx=16, pady=(0, 6))
        self._label(panel, "Numune hesabı ve kontrolü", 14, bold=True).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(6, 4))
        for column, (key, label) in enumerate((
            ("thickness", "Hesap / numune kalınlığı (mm)"),
            ("angle", "Düz sactan büküm açısı (°)"),
            ("radius", "Ölçülen iç yarıçap R (mm, isteğe bağlı)"),
        )):
            self._k_field(panel, key, label, 4, column)
        self._k_field(panel, "method", "K hesaplama yöntemi", 5, 0,
                      values=["Tablo", "BA ölçümü"], readonly=True)
        self._label(panel, "Tablo ile başlangıç değeri alın; üretim numunesiyle kontrol etmek için BA ölçümünü seçin.",
                    11, MUTED, wraplength=490, justify="left").grid(
            row=5, column=1, columnspan=2, sticky="w", padx=16, pady=8)
        calibration = ctk.CTkFrame(panel, fg_color=INPUT, corner_radius=14)
        calibration.grid(row=6, column=0, columnspan=3, sticky='ew', padx=16, pady=(8, 4))
        for column in range(3):
            calibration.grid_columnconfigure(column, weight=1, uniform='kr_calibration')
        self.k_widgets['calibration_panel'] = calibration
        self._label(calibration, 'Üretim numunesi · BA kalibrasyonu', 14, bold=True).grid(
            row=0, column=0, columnspan=3, sticky='w', padx=16, pady=(14, 6))
        self._k_field(calibration, "ba", "Ölçülen büküm payı BA (mm)", 1, 0)
        for column, (key, label) in enumerate((
            ("outside_a", "Dış ölçü A (mm, alternatif)"),
            ("outside_b", "Dış ölçü B (mm)"),
        )):
            self._k_field(calibration, key, label, 1, column+1)
        self._k_field(calibration, "flat", "Ölçülen açınım boyu (mm)", 2, 0)
        self._label(calibration, "İç yarıçapı girin. BA boşsa dış A, dış B ve açınım boyuyla hesaplanır. A ve B, dış yüzeylerin sanal kesişimine kadar ölçülür.",
                    11, MUTED, wraplength=470, justify="left").grid(
            row=2, column=1, columnspan=2, sticky="w", padx=16, pady=(0, 12))
        summary = ctk.CTkFrame(panel, fg_color=ACCENT_BG, corner_radius=14)
        summary.grid(row=7, column=0, columnspan=3, sticky='ew', padx=16, pady=(14, 16))
        summary.grid_columnconfigure(0, weight=1)
        self._label(summary, 'Hesap özeti', 11, ACCENT, True).grid(row=0, column=0, sticky='w', padx=16, pady=(12, 4))
        self.k_calculation_label = self._label(summary, "", 12, TEXT, wraplength=730,
                                              justify="left", anchor="w")
        self.k_calculation_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.k_widgets["automatic_summary"] = self.k_calculation_label
        self._build_manual_k_settings()
        self._select_k_assignment(self.k_state["assignment_mode"].get())
        for key, variable in self.k_state.items():
            if key == "assignment_mode":
                variable.trace_add("write", lambda *_: self._select_k_assignment(
                    self.k_state["assignment_mode"].get()) if self.mode == "k_factor" and not self.busy else None)
            elif key != "save":
                variable.trace_add("write", lambda *_: self._preview_k_calculation()
                                   if self.mode == "k_factor" and not self.busy else None)

    def _build_manual_k_settings(self):
        panel = ctk.CTkFrame(self.settings_body, fg_color="transparent", corner_radius=0)
        panel.grid(row=1, column=0, sticky="ew")
        self.k_widgets["manual_panel"] = panel
        for column in range(3):
            panel.grid_columnconfigure(column, weight=1, uniform="manual_kr")
        self._label(panel, "Belirli kalınlıktaki saclara K ve yarıçap atama", 14, bold=True).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 8))
        self._k_field(panel, "manual_thickness", "Hedef sac kalınlığı (mm)", 1, 0,
                      values=["0.5", "0.8", "1", "1.2", "1.5", "2", "2.5", "3", "4", "5", "6", "8", "10", "12", "15", "20"])
        self._k_field(panel, "manual_k", "K faktörü (0–1)", 1, 1)
        self._k_field(panel, "manual_r", "İç yarıçap R (mm)", 1, 2)
        self._label(panel, "Örnek: 2 mm sac → K: 0,274 · R: 2 mm. Virgül veya nokta kullanabilirsiniz.",
                    11, MUTED, wraplength=700, justify="left").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=16, pady=(4, 8))
        summary_band = ctk.CTkFrame(panel, fg_color=ACCENT_BG, corner_radius=10)
        summary_band.grid(row=3, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 16))
        summary_band.grid_columnconfigure(0, weight=1)
        summary = self._label(summary_band, "", 13, TEXT, wraplength=670, justify="left", anchor="w")
        summary.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        self.k_widgets["manual_summary"] = summary
        steps = ctk.CTkFrame(panel, fg_color='transparent')
        steps.grid(row=4, column=0, columnspan=3, sticky='ew', padx=16, pady=(0, 16))
        for column, (icon, title, hint) in enumerate((
            ('search', '01  Montajı kontrol et', 'Montajı tara ile eşleşen sacları görün.'),
            ('arrow', '02  Değerleri uygula', 'Montaja K/R uygula ile atamayı başlatın.'))):
            steps.grid_columnconfigure(column, weight=1, uniform='kr_steps')
            card = ctk.CTkFrame(steps, fg_color=INPUT, corner_radius=12)
            card.grid(row=0, column=column, sticky='nsew', padx=(0, 6) if column == 0 else (6, 0))
            card.grid_columnconfigure(0, weight=1)
            self._label(card, title, 12, TEXT, True, image=self._icon(icon, MUTED, 18), compound='left').grid(
                row=0, column=0, sticky='w', padx=14, pady=(12, 4))
            self._label(card, hint, 11, MUTED, wraplength=240, justify='left').grid(
                row=1, column=0, sticky='w', padx=14, pady=(0, 12))

    def _sync_k_calibration(self):
        panel = self.k_widgets.get('calibration_panel')
        if panel is None:
            return
        show = self.k_state['method'].get() == 'BA ölçümü'
        if show and not panel.winfo_manager():
            panel.grid()
        elif not show and panel.winfo_manager():
            hide_grid(panel)

    def _select_k_assignment(self, selection):
        if self.busy or selection not in (AUTOMATIC_TAB, MANUAL_TAB):
            return
        if self.k_state["assignment_mode"].get() != selection:
            self.k_state["assignment_mode"].set(selection)
            return  # The variable trace applies the view once.
        self.k_widgets['assignment_tabs'].set(selection)
        self.form_panel.grid()
        if hasattr(self, 'result_tabs') and self.result_tabs.master.master is self.k_widgets['body']:
            hide_grid(self.result_tabs.master)
        manual = selection == MANUAL_TAB
        hide_grid(self.k_widgets["automatic_panel"])
        hide_grid(self.k_widgets["manual_panel"])
        self.k_widgets["manual_panel" if manual else "automatic_panel"].grid()
        self.k_calculation_label = self.k_widgets["manual_summary" if manual else "automatic_summary"]
        self.settings_body._parent_canvas.yview_moveto(0)
        self._preview_k_calculation()
        if hasattr(self, "status_label"):
            self._resize_pdf_area()

    def _select_k_view(self, selection):
        if selection != RESULTS_TAB:
            return self._select_k_assignment(selection)
        self.k_widgets['assignment_tabs'].set(RESULTS_TAB)
        hide_grid(self.form_panel)
        self.result_tabs.master.grid()
        self._resize_pdf_area()

    def _resize_k_workspace(self):
        width = self.k_widgets['body'].winfo_width()/self.workspace._get_widget_scaling()
        for key in ('automatic_summary', 'manual_summary'):
            configure_changed(self.k_widgets[key], wraplength=max(240, width-(112 if key == 'manual_summary' else 80)))
        configure_changed(self.status_label, wraplength=max(240, width), justify='left')
        self._fit_results_toolbar(width)

    def _copy_k_log(self):
        text = self.log_box.get('1.0', 'end').strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append('GOKWORKS · K/R işlem günlüğü\n'+text)
            self.k_widgets['copy_log'].configure(text='Kopyalandı')

    def _finish_k_feedback(self, summary):
        self.k_widgets['copy_log'].configure(state='normal', text='Günlüğü kopyala')
        if summary['state'] == 'error' or summary.get('failed'):
            # Per-part failures finish the batch normally. Still expose their
            # full reasons instead of leaving them clipped in the table.
            self.result_tabs.set('Günlük')
        self._resize_pdf_area()

    def _show_k_calculation(self):
        self._select_k_view(self.k_state['assignment_mode'].get())
        self.settings_body._parent_canvas.yview_moveto(1)

    def _build_k_actions(self, parent):
        # Keep montage scanning and save choice outside the scrollable form.
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=24, pady=(8, 0))
        self.scan_button = self._button(actions, "Montajı tara", self._scan_k_assembly,
                                         icon="search", width=166)
        self.scan_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.open_button = self._button(actions, "Hesapla ve kontrol et", self._show_k_calculation, width=172)
        self.open_button.grid(row=0, column=1, sticky="ew")
        save = self._checkbox(actions, "Parça dosyalarını kaydet", self.k_state["save"])
        save.grid(row=0, column=2, sticky="w", padx=(20, 0))
        scope = self._checkbox(actions, "Tüm bükümlere uygula", self.k_state["all_bends"])
        scope.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._label(actions, "Özel K/R değerleri ana sac ayarlarını kullanır. Kalınlık korunur.",
                    11, MUTED, anchor="w", wraplength=280).grid(
                        row=1, column=2, sticky="w", padx=(20, 0), pady=(10, 0))
        self.k_widgets["all_bends"] = scope
        self.controls.extend((self.scan_button, self.open_button, save, scope))

    def _k_field(self, panel, key, label, row, column, *, values=None, readonly=False):
        holder = ctk.CTkFrame(panel, fg_color="transparent")
        holder.grid(row=row, column=column, sticky="ew", padx=16, pady=(3, 7))
        holder.grid_columnconfigure(0, weight=1)
        self._label(holder, label, 12, MUTED, wraplength=240, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))
        if values and readonly:
            field = ctk.CTkOptionMenu(
                holder, variable=self.k_state[key], values=values, height=42,
                fg_color=SECONDARY, button_color=SECONDARY, button_hover_color=HOVER,
                dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
                text_color=TEXT, dropdown_text_color=TEXT,
                font=(UI_FONT, 13), dropdown_font=(UI_FONT, 13))
        elif values:
            field = ctk.CTkComboBox(
                holder, variable=self.k_state[key], values=values, height=42,
                fg_color=INPUT, border_color=BORDER, button_color=SECONDARY,
                button_hover_color=HOVER, dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
                text_color=TEXT, dropdown_text_color=TEXT, font=(UI_FONT, 14),
                dropdown_font=(UI_FONT, 13))
        else:
            field = ctk.CTkEntry(holder, textvariable=self.k_state[key], height=42,
                                fg_color=INPUT, border_color=BORDER, text_color=TEXT,
                                font=(UI_FONT, 14))
        field.grid(row=1, column=0, sticky="ew")
        self.k_widgets[key] = field
        self.controls.append(field)

    def _k_recipe(self):
        values = {key: variable.get() for key, variable in self.k_state.items()}
        if values["assignment_mode"] == MANUAL_TAB:
            t = number(values["manual_thickness"], "Hedef sac kalınlığı")
            recipe = ManualAssignment(t, number(values["manual_k"], "Manuel K faktörü", zero=True),
                                      number(values["manual_r"], "Manuel büküm yarıçapı"),
                                      all_bends=values["all_bends"])
            recipe.validate()
            return t, recipe
        material = next((m.key for m in MATERIALS if m.label == values["material"]), None)
        t = number(values["thickness"], "Hesap / numune kalınlığı")
        radius = number(values["radius"], "Ölçülmüş iç R") if values["radius"].strip() else None
        angle = number(values["angle"], "Büküm açısı")
        measured_ba = None
        if values["method"] == "BA ölçümü":
            if radius is None:
                raise ValueError("BA kalibrasyonu için ölçülmüş iç R girin.")
            if values["ba"].strip():
                measured_ba = number(values["ba"], "Ölçülmüş BA")
            else:
                measured_ba = ba_from_outside_dimensions(t, radius, values["outside_a"],
                                                        values["outside_b"], values["flat"], angle)
        recipe = Recipe(material=material, punch_radius_mm=number(values["punch"], "Üst bıçak uç R"),
                        die_opening_mm=None if values["die"] == AUTO_DIE else number(values["die"], "Alt kalıp V"),
                        measured_radius_mm=radius, angle_deg=angle,
                        calibration_thickness_mm=t if measured_ba is not None else None,
                        measured_ba_mm=measured_ba,
                        punch_angle_deg=number(values["punch_angle"], "Üst bıçak açısı"),
                        die_angle_deg=number(values["die_angle"], "Alt kalıp açısı"),
                        all_bends=values["all_bends"])
        recipe.validate()
        return t, recipe

    def _preview_k_calculation(self):
        self._sync_k_calibration()
        try:
            thickness, recipe = self._k_recipe()
            result = calculate(thickness, recipe)
            if isinstance(recipe, ManualAssignment):
                self.k_calculation_label.configure(
                    text=f"{thickness:.12g} mm sac → K = {result.k_factor:.12g} · R = {result.radius_mm:.12g} mm\n"
                         "Aktif montaj ve alt montajlarda yalnız bu kalınlıktaki saclar güncellenir.\n"
                         "Önce Montajı tara ile kontrol edin; ardından Montaja K/R uygula düğmesini kullanın.",
                    text_color=TEXT)
                return result
            text = (f"K = {result.k_factor:.5f}   ·   İç R = {result.radius_mm:.3f} mm   ·   V = {result.die_opening_mm:g} mm\n"
                    f"BA = ({result.angle_deg:g} × π / 180) × ({result.radius_mm:g} + {result.k_factor:g} × {thickness:g})"
                    f" = {result.ba_mm:.5f} mm   ·   BD = {result.bd_mm:.5f} mm\n")
            if result.calibrated:
                text += f"Ölçümden K; tablo K = {result.table_k:.5f}, fark = {result.k_factor-result.table_k:+.5f}."
            else:
                text += "Tabloya göre öneri · Üretim ölçümüyle kontrol edin."
            self.k_calculation_label.configure(text=text, text_color=TEXT)
            return result
        except ValueError as error:
            self.k_calculation_label.configure(text=str(error), text_color=RED)
            return None

    def _scan_k_assembly(self):
        self._run_k_worker(preview=True)

    def _start_k_apply(self):
        if self.busy:
            if self.k_widgets.get('operation_preview') and not self.stop_event.is_set():
                _, recipe = self._k_recipe()
                self.k_widgets['pending_apply'] = (recipe, self.k_state['save'].get())
                self.start_button.configure(state='disabled', text='Uygulama sıraya alındı…')
                text = 'K/R uygulama isteği alındı. Montaj kontrolü bitince atama başlayacak.'
                self.status_label.configure(text=text, text_color=MUTED)
                self._append_log(text)
            return
        self._run_k_worker(preview=False)

    def _continue_k_apply(self, summary):
        request = self.k_widgets.pop('pending_apply', None)
        if request is None:
            return
        if (summary['state'] == 'completed' and summary.get('preview') is True
                and summary.get('scope') is not None and summary['succeeded']
                and not summary['failed'] and not self.stop_event.is_set()):
            self._run_k_worker(preview=False, request=(*request, summary['scope']))
        else:
            text = 'Bekleyen K/R ataması başlatılmadı: kontrolde hata oluştu, işlem durduruldu veya uygun parça bulunamadı. K/R uygulanmadı.'
            self.status_label.configure(text=text, text_color=AMBER)
            self._append_log(text)

    def _run_k_worker(self, *, preview, request=None):
        if self.busy:
            return
        expected_scope = None
        if request is None:
            if self._preview_k_calculation() is None:
                message = self.k_calculation_label.cget('text')
                self._select_k_view(self.k_state['assignment_mode'].get())
                self.status_label.configure(text=f'K/R başlatılmadı · {message}', text_color=RED)
                return
            _, recipe = self._k_recipe()
            save = self.k_state['save'].get() and not preview
        else:
            recipe, save, expected_scope = request
        self._save_preferences()
        self.k_widgets['operation_preview'] = preview
        self._reset()
        self.k_widgets['copy_log'].configure(state='disabled', text='Günlüğü kopyala')
        self.k_widgets['success_caption'].configure(text='Hazır' if preview else 'Uygulanan')
        self.filter_menu.configure(values=['Tüm durumlar', 'Bekleyen', 'İşleniyor',
                                          'Uygulamaya hazır' if preview else 'Uygulandı',
                                          'Atlanan', 'Hatalı'])
        self._select_k_view(RESULTS_TAB)
        self._set_busy(True)
        operation = ('Montaj kontrolü başladı. Bu işlem K/R değerlerini değiştirmez.'
                     if preview else 'K/R ataması başladı. Değerler parçalara yazılacak ve geri okunarak kontrol edilecek.')
        self.status_label.configure(text=operation, text_color=MUTED)
        self._append_log(operation)
        if isinstance(recipe, ManualAssignment):
            description = (f'Manuel · t={number(recipe.thickness_mm, "Kalınlık"):g} mm · '
                           f'K={number(recipe.k_factor, "K", zero=True):g} · R={number(recipe.radius_mm, "R"):g} mm')
        else:
            description = f'Malzeme / takım · {self.k_state["material"].get()}'
        description += ' · Tüm bükümler' if recipe.all_bends else ' · Mevcut özel büküm ayarları korunacak'
        self._append_log(description + (' · Dosyalar kaydedilecek.' if save else ' · Dosyalar kaydedilmeyecek.'))
        threading.Thread(target=update_assembly, args=(recipe, self.events, self.stop_event),
                         kwargs=dict(preview=preview, save=save, expected_scope=expected_scope),
                         daemon=False).start()
