"""K/R çalışma alanı: takım kataloğu, elle hesap ve montaj işçisi."""

import threading
import tkinter as tk

import customtkinter as ctk
from gui.rendering import configure_changed

from gui.theme import INPUT, PANEL, BORDER, TEXT, MUTED, RED, SECONDARY, HOVER, UI_FONT, ACCENT_BG, ACCENT
from k_factor.apply import update_assembly
from k_factor.rules import (MATERIALS, DIE_OPENINGS, PUNCH_RADII, TOOL_ANGLES, Recipe, ManualAssignment, calculate,
                            number, ba_from_outside_dimensions)

AUTO_DIE = "Otomatik (8 × t)"
AUTOMATIC_TAB, MANUAL_TAB = "Malzeme / Takım", "Manuel K / R"
RESULTS_TAB = "Montaj sonuçları"


class KFactorView:
    def _build_k_workspace(self):
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        self._build_header()
        self.pdf_header.grid_configure(pady=(14, 12))
        self._build_stats()
        self.stats_frame.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 8))
        view = tk.StringVar(self, self.k_state['assignment_mode'].get())
        self.k_widgets['work_view'] = view
        selector = ctk.CTkSegmentedButton(self.workspace, variable=view,
            values=[AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB], command=self._select_k_view,
            height=48, dynamic_resizing=False, fg_color=SECONDARY, selected_color=ACCENT_BG,
            selected_hover_color=HOVER, unselected_color=SECONDARY,
            unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 14, 'bold'))
        selector.grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 8))
        self.k_widgets['assignment_tabs'] = selector
        self.controls.append(selector)
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=3, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.k_widgets['body'] = body
        self.form_panel = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12,
                                      border_width=1, border_color=BORDER)
        self.form_panel.grid(row=0, column=0, sticky='nsew')
        self.form_panel.grid_propagate(False)
        self.form_panel.grid_columnconfigure(0, weight=1)
        self.form_panel.grid_rowconfigure(0, weight=1)
        self._build_k_settings()
        self._build_results(parent=body)
        self.result_tabs.master.grid(row=0, column=0, sticky='nsew', padx=0)
        self.result_tabs.master.grid_propagate(False)
        self._build_k_actions(self.workspace)
        self.status_label = self._label(self.workspace, 'Hazır · Ana montajı SolidWorks’te aktif yapın.',
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
        panel = ctk.CTkFrame(self.settings_body, fg_color=INPUT, corner_radius=12,
                             border_width=1, border_color=BORDER)
        panel.grid(row=1, column=0, sticky="ew")
        self.k_widgets["automatic_panel"] = panel
        for column in range(3):
            panel.grid_columnconfigure(column, weight=1, uniform="kr")
        self._label(panel, "01   Malzeme ve takım · Havada büküm", 14, bold=True).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        for column, (key, label, values) in enumerate((
            ("material", "Malzeme varsayımı", [m.label for m in MATERIALS]),
            ("punch", "Üst bıçak uç R (mm)", [f"{r:g}" for r in PUNCH_RADII]),
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
        self._label(panel, "02   Elle hesap ve numune kontrolü", 14, bold=True).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(6, 4))
        for column, (key, label) in enumerate((
            ("thickness", "Hesap / numune kalınlığı (mm)"),
            ("angle", "Düz sacdan büküm açısı (°)"),
            ("radius", "Ölçülmüş iç R (mm, isteğe bağlı)"),
        )):
            self._k_field(panel, key, label, 4, column)
        self._k_field(panel, "method", "K kaynağı", 5, 0,
                      values=["Tablo", "BA ölçümü"], readonly=True)
        self._k_field(panel, "ba", "Ölçülmüş BA (mm)", 5, 1)
        self._label(panel, "BA ölçümünde gerçek iç R zorunlu. Kalibrasyon yalnız aynı kalınlığa uygulanır.",
                    11, MUTED, wraplength=225, justify="left").grid(
            row=5, column=2, sticky="w", padx=16, pady=8)
        for column, (key, label) in enumerate((
            ("outside_a", "Alternatif: dış A (mm)"),
            ("outside_b", "Dış B (mm)"), ("flat", "Ölçülen düz boy (mm)"),
        )):
            self._k_field(panel, key, label, 6, column)
        self._label(panel, "Tek bükümlü numune: A/B dış sanal köşeye ölçülür. BA boşsa A, B ve düz boydan hesaplanır.",
                    11, MUTED, wraplength=700, justify="left").grid(
            row=7, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 8))
        self.k_calculation_label = self._label(panel, "", 12, TEXT, wraplength=730,
                                              justify="left", anchor="w")
        self.k_calculation_label.grid(row=8, column=0, columnspan=3, sticky="ew", padx=16, pady=6)
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
        panel = ctk.CTkFrame(self.settings_body, fg_color=INPUT, corner_radius=12,
                             border_width=1, border_color=BORDER)
        panel.grid(row=1, column=0, sticky="ew")
        self.k_widgets["manual_panel"] = panel
        for column in range(3):
            panel.grid_columnconfigure(column, weight=1, uniform="manual_kr")
        self._label(panel, "Kalınlığa göre manuel K / R atama", 14, bold=True).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 8))
        self._k_field(panel, "manual_thickness", "Hedef sac kalınlığı (mm)", 1, 0,
                      values=["0.5", "0.8", "1", "1.2", "1.5", "2", "2.5", "3", "4", "5", "6", "8", "10", "12", "15", "20"])
        self._k_field(panel, "manual_k", "K faktörü (0–1)", 1, 1)
        self._k_field(panel, "manual_r", "İç büküm yarıçapı R (mm)", 1, 2)
        self._label(panel, "Örnek: 2 mm sac → K: 0,274 · R: 2 mm. Virgül veya nokta kullanabilirsiniz.",
                    11, MUTED, wraplength=700, justify="left").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=16, pady=(4, 8))
        summary = self._label(panel, "", 12, TEXT, wraplength=700, justify="left", anchor="w")
        summary.grid(row=3, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 14))
        self.k_widgets["manual_summary"] = summary

    def _select_k_assignment(self, selection):
        if self.busy or selection not in (AUTOMATIC_TAB, MANUAL_TAB):
            return
        if self.k_state["assignment_mode"].get() != selection:
            self.k_state["assignment_mode"].set(selection)
            return  # The variable trace applies the view once.
        self.k_widgets['assignment_tabs'].set(selection)
        self.form_panel.grid()
        if hasattr(self, 'result_tabs') and self.result_tabs.master.master is self.k_widgets['body']:
            self.result_tabs.master.grid_remove()
        manual = selection == MANUAL_TAB
        self.k_widgets["automatic_panel"].grid_remove()
        self.k_widgets["manual_panel"].grid_remove()
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
        self.form_panel.grid_remove()
        self.result_tabs.master.grid()
        self._resize_pdf_area()

    def _resize_k_workspace(self):
        width = self.k_widgets['body'].winfo_width()/self.workspace._get_widget_scaling()
        for key in ('automatic_summary', 'manual_summary'):
            configure_changed(self.k_widgets[key], wraplength=max(240, width-80))
        self._fit_results_toolbar(width)

    def _build_k_actions(self, parent):
        # Keep montage scanning and save choice outside the scrollable form.
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=24, pady=(8, 0))
        self.scan_button = self._button(actions, "Montajı tara", self._scan_k_assembly,
                                         icon="search", width=166)
        self.scan_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.open_button = self._button(actions, "Hesapla / kontrol et", self._preview_k_calculation, width=172)
        self.open_button.grid(row=0, column=1, sticky="ew")
        save = self._checkbox(actions, "Parça dosyalarını kaydet", self.k_state["save"])
        save.grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.controls.extend((self.scan_button, self.open_button, save))

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
                fg_color=PANEL, border_color=BORDER, button_color=SECONDARY,
                button_hover_color=HOVER, dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
                text_color=TEXT, dropdown_text_color=TEXT, font=(UI_FONT, 14),
                dropdown_font=(UI_FONT, 13))
        else:
            field = ctk.CTkEntry(holder, textvariable=self.k_state[key], height=42,
                                fg_color=PANEL, border_color=BORDER, text_color=TEXT,
                                font=(UI_FONT, 14))
        field.grid(row=1, column=0, sticky="ew")
        self.k_widgets[key] = field
        self.controls.append(field)

    def _k_recipe(self):
        values = {key: variable.get() for key, variable in self.k_state.items()}
        if values["assignment_mode"] == MANUAL_TAB:
            t = number(values["manual_thickness"], "Hedef sac kalınlığı")
            recipe = ManualAssignment(t, number(values["manual_k"], "Manuel K faktörü", zero=True),
                                      number(values["manual_r"], "Manuel büküm yarıçapı"))
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
                        die_angle_deg=number(values["die_angle"], "Alt kalıp açısı"))
        recipe.validate()
        return t, recipe

    def _preview_k_calculation(self):
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
                text += "Tablo önerisi · Hesap tutarlılığı, üretim doğrulaması değildir."
            self.k_calculation_label.configure(text=text, text_color=TEXT)
            return result
        except ValueError as error:
            self.k_calculation_label.configure(text=str(error), text_color=RED)
            return None

    def _scan_k_assembly(self):
        self._run_k_worker(preview=True)

    def _start_k_apply(self):
        self._run_k_worker(preview=False)

    def _run_k_worker(self, *, preview):
        if self.busy:
            return
        if self._preview_k_calculation() is None:
            return
        _, recipe = self._k_recipe()
        save = self.k_state["save"].get() and not preview
        self._save_preferences()
        self._reset()
        self._select_k_view(RESULTS_TAB)
        self._set_busy(True)
        self.status_label.configure(text="Montaj K/R önizlemesi hazırlanıyor…" if preview else "K/R uygulanıyor…",
                                    text_color=MUTED)
        threading.Thread(target=update_assembly, args=(recipe, self.events, self.stop_event),
                         kwargs=dict(preview=preview, save=save), daemon=False).start()
