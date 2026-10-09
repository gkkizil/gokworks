"""ISO geçmeleri için bağımsız, açık/koyu temalı hesap ve gösterim ekranı."""

import csv
import tkinter as tk
from tkinter import filedialog
import webbrowser

import customtkinter as ctk

from gui.theme import (PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       GREEN, AMBER, RED, SECONDARY, HOVER, UI_FONT)
from iso_fits.diagram import draw
from iso_fits.manual import calculate_manual, compare_classes, usage_hint
from iso_fits.rules import (classes, calculate, PRESETS, CLASSIFICATION,
                            format_mm, format_deviation)

SAMPLES = ('En az boşluk', 'Orta değer', 'En çok boşluk')
VIEWS = ('Montaj kesiti', 'Tolerans bölgeleri')
METHODS = ('ISO seçimi', 'Manuel kontrol')
COLORS = {'clearance': GREEN, 'transition': AMBER, 'interference': RED}
SOURCE_TEXT = '''ISO 286-1:2010 — Tolerans, sapma ve geçmelerin temel kuralları.
ISO 286-2:2010 — Delik ve mil tolerans sınıflarının sınır sapmaları.

Bu ekran 1–400 mm aralığında doğrulanan 11 delik ve 18 mil sınıfını sunar. Delikler büyük, miller küçük harfle gösterilir. Değerler tablodan alınır; yaklaşık IT formülü kullanılmaz. Çap aralıklarında alt sınır hariç, üst sınır dahildir.

Cmin = EI − es; Cmax = ES − ei.
Pozitif C boşluk, negatif C sıkılıktır. H7/h6 gibi Cmin=0 eşleşmeler boşluklu geçme sınıfındadır; minimum boşluk sıfırdır.

Tablolar: parkergreene/isofits, lachr/Passungsrechner, bell-jamie/iso-286. Kaynak commitleri, çap sınırları ve bağımsız karşılaştırma docs/iso-fits.md içinde kayıtlıdır. F8 ≤3 mm için bir kaynakta saptanan satır hatası, IT8 genişliği ve diğer tabloyla kontrol edilmiştir.

Bu uygulama ISO belgesinin tam metnini içermez. Resmî metin ve güncellik ISO kataloğundan kontrol edilmelidir. Resmî ISO/üretici sitelerine bu bulut oturumunun ağ politikası nedeniyle erişilemedi; kaynaklar ISO tarafından sertifikalandırılmış sayılmaz.

Montaj kesiti şematiktir; sapmalar görünürlük için büyütülür. Tolerans bölgeleri gerçek sayısal sapma ölçeğini gösterir. Orta değer bir olasılık/üretim dağılımı varsayımı değildir. Yalnızca limitlerin ortasıdır.

Montaj kuvveti, çalışma sıcaklığı, malzeme, yüzey ve şekil/konum toleransları bu çaptan hesaplanmaz. Pres kuvveti veya yağlı/elle montaj kararı için bu bilgiler ayrıca gerekir. Geometrik toleranslar ISO 1101 kapsamındadır; bu sekme çap geçmelerini hesaplar.'''


SOURCE_TEXT += '\n\nManuel kontrol: delik ve mil için ortak nominal çap ile ayrı alt/üst sapmalar girilir. Geçme girilen ölçü limitlerinden hesaplanır. Tam ISO eşleşmesi iki sapmanın da aynı olmasıdır; en yakın sınıf mevcut sınıflar içindeki alt/üst farkların mutlak toplamına göre seçilir. Yakın sınıf girilen toleransları değiştirmez. Kayar/yağlı kullanım adları öneridir; yağlama veya montaj kuvveti sonucu değildir.'


class IsoFitsView:
    def _create_iso_state(self, saved):
        defaults = {'diameter': '50', 'hole': 'H8', 'shaft': 'f7',
                    'unit': 'mm', 'sample': 'Orta değer', 'view': 'Montaj kesiti',
                    'method': 'ISO seçimi', 'hole_lower': '0', 'hole_upper': '+0,02',
                    'shaft_lower': '-0,02', 'shaft_upper': '0'}
        self.iso_state = {key: tk.StringVar(self, value=str(saved.get(f'iso_{key}', value)))
                          for key, value in defaults.items()}
        for key, choices in [('hole', classes('hole')), ('shaft', classes('shaft')),
                             ('unit', ('mm', 'µm')), ('sample', SAMPLES), ('view', VIEWS),
                             ('method', METHODS)]:
            if self.iso_state[key].get() not in choices:
                self.iso_state[key].set(defaults[key])
        self.iso_result = None
        self.iso_widgets = {}
        self._iso_loading = False

    def _iso_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=INPUT, corner_radius=12,
                            border_width=1, border_color=BORDER)

    def _iso_menu(self, parent, key, values, width=130):
        return ctk.CTkOptionMenu(parent, variable=self.iso_state[key], values=list(values),
                                width=width, height=34, fg_color=SECONDARY,
                                button_color=SECONDARY, button_hover_color=HOVER,
                                dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
                                dropdown_text_color=TEXT, text_color=TEXT,
                                font=(UI_FONT, 12), dropdown_font=(UI_FONT, 12))

    def _build_iso_workspace(self):
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self.workspace, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 16))
        header.grid_columnconfigure(0, weight=1)
        self._label(header, 'GOKWORKS  /  MÜHENDİSLİK HESAPLARI', 10, MUTED, True).grid(row=0, column=0, sticky='w')
        self._label(header, 'ISO Geçme Toleransları', 24, bold=True).grid(row=1, column=0, sticky='w', pady=(4, 2))
        self._label(header, 'ISO 286 · Delik / mil limitleri ve kesit gösterimi', 12, MUTED,
                    wraplength=350, justify='left').grid(row=2, column=0, sticky='w')
        actions = ctk.CTkFrame(header, fg_color='transparent')
        actions.grid(row=1, column=1, rowspan=2, sticky='e', padx=(12, 0))
        self.iso_widgets['sources'] = self._button(actions, 'Kaynaklar', self._show_iso_sources, width=104)
        self.iso_widgets['sources'].pack(side='left', padx=(0, 8))
        self.iso_widgets['export'] = self._button(actions, 'CSV kaydet', self._save_iso_report,
                                                  primary=True, icon='download', width=126)
        self.iso_widgets['export'].pack(side='left')
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=1, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        form = self._iso_card(body)
        form.configure(width=286)
        form.grid(row=0, column=0, sticky='nsew', padx=(0, 16))
        form.grid_propagate(False)
        form.grid_columnconfigure(0, weight=1)
        form.grid_rowconfigure(5, weight=1)
        self.iso_widgets['form'] = form
        method = ctk.CTkSegmentedButton(form, variable=self.iso_state['method'], values=list(METHODS),
            height=32, fg_color=SECONDARY, selected_color=ACCENT_BG, selected_hover_color=HOVER,
            unselected_color=SECONDARY, unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 11))
        method.grid(row=0, column=0, sticky='ew', padx=16, pady=(14, 0))
        self.iso_widgets['method'] = method
        nominal = ctk.CTkFrame(form, fg_color='transparent')
        nominal.grid(row=1, column=0, sticky='ew', padx=16, pady=(14, 10))
        nominal.grid_columnconfigure(0, weight=1)
        self._label(nominal, 'NOMİNAL ÇAP (mm)', 11, MUTED, True).grid(row=0, column=0, sticky='w', pady=(0, 6))
        entry = ctk.CTkEntry(nominal, textvariable=self.iso_state['diameter'], height=40,
                             fg_color=PANEL, text_color=TEXT, border_color=BORDER,
                             font=(UI_FONT, 20, 'bold'), justify='center')
        entry.grid(row=1, column=0, sticky='ew')
        self.iso_widgets['diameter'] = entry
        self._label(nominal, 'Doğrulanan aralık: 1–400 mm', 10, MUTED).grid(row=2, column=0, sticky='w', pady=(4, 0))
        selectors = ctk.CTkFrame(form, fg_color='transparent')
        selectors.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 10))
        for column, (key, caption, feature) in enumerate([('hole', 'DELİK', 'hole'), ('shaft', 'MİL', 'shaft')]):
            selectors.grid_columnconfigure(column, weight=1, uniform='iso_selectors')
            self._label(selectors, caption, 10, MUTED, True).grid(row=0, column=column, sticky='w', pady=(0, 4))
            menu = self._iso_menu(selectors, key, classes(feature), width=112)
            menu.grid(row=1, column=column, sticky='ew', padx=(0, 8) if column == 0 else (0, 0))
            self.iso_widgets[key] = menu
        toolbar = ctk.CTkFrame(form, fg_color='transparent')
        toolbar.grid(row=3, column=0, sticky='ew', padx=16)
        self._label(toolbar, 'YAYGIN EŞLEŞMELER', 10, MUTED, True).pack(side='left')
        self.iso_widgets['unit'] = self._iso_menu(toolbar, 'unit', ('mm', 'µm'), width=72)
        self.iso_widgets['unit'].pack(side='right')
        self.iso_search = tk.StringVar(self, value='')
        search_frame = ctk.CTkFrame(form, fg_color='transparent')
        search_frame.grid(row=4, column=0, sticky='ew', padx=16, pady=(8, 8))
        search_frame.grid_columnconfigure(1, weight=1)
        self._label(search_frame, 'Ara', 11, MUTED).grid(row=0, column=0, padx=(0, 6))
        self.iso_widgets['search'] = ctk.CTkEntry(search_frame, textvariable=self.iso_search, height=32, fg_color=PANEL,
                                                text_color=TEXT, border_color=BORDER, font=(UI_FONT, 11))
        self.iso_widgets['search'].grid(row=0, column=1, sticky='ew')
        presets = ctk.CTkScrollableFrame(form, fg_color='transparent', corner_radius=0,
                                        scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        presets.grid(row=5, column=0, sticky='nsew', padx=(8, 4), pady=(0, 8))
        presets.grid_columnconfigure(0, weight=1)
        presets._scrollbar.configure(width=8, height=24)
        self.iso_widgets['presets'] = presets
        self.iso_widgets['groups'] = {}
        for kind in CLASSIFICATION:
            self.iso_widgets['groups'][kind] = self._label(presets, CLASSIFICATION[kind].upper(),
                                                           10, COLORS[kind], True)
        self.iso_widgets['preset_buttons'] = {}
        for preset in PRESETS:
            button = ctk.CTkButton(presets, text=f'{preset.code}\n{preset.label}', command=lambda p=preset: self._select_iso_preset(p),
                                   height=54, anchor='w', corner_radius=7, border_width=1, border_color=BORDER,
                                   fg_color='transparent', hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 12, 'bold'))
            self.iso_widgets['preset_buttons'][preset.code] = button
        self.iso_widgets['iso_inputs'] = (selectors, toolbar, search_frame, presets)
        self._build_manual_inputs(form)
        details = ctk.CTkScrollableFrame(body, fg_color='transparent', corner_radius=0)
        details.grid(row=0, column=1, sticky='nsew')
        details.grid_columnconfigure(0, weight=1)
        details._scrollbar.configure(width=8, height=24)
        self.iso_widgets['details'] = details
        diagram = self._iso_card(details)
        diagram.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        diagram.grid_columnconfigure(0, weight=1)
        views = ctk.CTkSegmentedButton(diagram, variable=self.iso_state['view'], values=list(VIEWS),
                                       height=32, fg_color=SECONDARY, selected_color=ACCENT_BG,
                                       selected_hover_color=HOVER, unselected_color=SECONDARY,
                                       unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 11))
        views.grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 8))
        self.iso_widgets['view'] = views
        canvas = tk.Canvas(diagram, height=220, highlightthickness=0, borderwidth=0)
        canvas.grid(row=1, column=0, sticky='ew', padx=12)
        self.iso_widgets['canvas'] = canvas
        samples = ctk.CTkSegmentedButton(diagram, variable=self.iso_state['sample'], values=list(SAMPLES),
                                         height=30, fg_color=SECONDARY, selected_color=ACCENT_BG,
                                         selected_hover_color=HOVER, unselected_color=SECONDARY,
                                         unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 10))
        samples.grid(row=2, column=0, sticky='ew', padx=14, pady=(8, 4))
        self.iso_widgets['sample'] = samples
        self._label(diagram, 'Kesit şematik; sapmalar görünürlük için büyütülür.', 10, MUTED,
                    wraplength=400).grid(row=3, column=0, padx=14, pady=(2, 10))
        result = self._iso_card(details)
        result.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        result.grid_columnconfigure((0, 1), weight=1)
        self.iso_widgets['kind'] = self._label(result, '', 18, bold=True)
        self.iso_widgets['kind'].grid(row=0, column=0, columnspan=2, sticky='w', padx=14, pady=(12, 8))
        for column, key in enumerate(('minimum', 'maximum')):
            self.iso_widgets[key+'_title'] = self._label(result, '', 10, MUTED)
            self.iso_widgets[key+'_title'].grid(row=1, column=column, sticky='w', padx=14)
            self.iso_widgets[key] = self._label(result, '', 18, bold=True)
            self.iso_widgets[key].grid(row=2, column=column, sticky='w', padx=14, pady=(2, 8))
        self.iso_widgets['explanation'] = self._label(result, '', 11, MUTED, justify='left', anchor='w', wraplength=430)
        self.iso_widgets['explanation'].grid(row=3, column=0, columnspan=2, sticky='ew', padx=14, pady=(0, 12))
        limits_card = self._iso_card(details)
        limits_card.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        limits_card.grid_columnconfigure((0, 1), weight=1)
        self._label(limits_card, 'ÖLÇÜ SINIRLARI', 10, MUTED, True).grid(row=0, column=0, columnspan=2, sticky='w', padx=14, pady=(12, 6))
        for row, (key, title) in enumerate([('hole_limits', 'Delik · Dmin / Dmax'), ('shaft_limits', 'Mil · dmin / dmax'),
                                           ('hole_deviations', 'Delik · EI / ES'), ('shaft_deviations', 'Mil · ei / es')], 1):
            self._label(limits_card, title, 11, MUTED).grid(row=row, column=0, sticky='w', padx=14, pady=3)
            self.iso_widgets[key] = self._label(limits_card, '', 11, anchor='e')
            self.iso_widgets[key].grid(row=row, column=1, sticky='e', padx=14, pady=3)
        self.iso_widgets['copy'] = self._button(limits_card, 'Sonucu kopyala', self._copy_iso_result, icon='copy', width=156)
        self.iso_widgets['copy'].grid(row=5, column=0, columnspan=2, sticky='w', padx=14, pady=(8, 12))
        comparison = self._iso_card(details)
        comparison.grid(row=3, column=0, sticky='ew', pady=(0, 12))
        comparison.grid_columnconfigure(0, weight=1)
        self._label(comparison, 'ISO TABLO KONTROLÜ', 10, MUTED, True).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 6))
        self.iso_widgets['comparison'] = comparison
        self.iso_widgets['iso_comparison'] = self._label(comparison, '', 11, TEXT, justify='left', anchor='w', wraplength=430)
        self.iso_widgets['iso_comparison'].grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.iso_widgets['note'] = self._label(details,
            'Geçme türü boyut limitlerinden hesaplanır. Montaj kuvveti, yağlama veya sıcaklık kararı için malzeme, yüzey ve çalışma koşulları gerekir.',
            11, MUTED, wraplength=430, justify='left', anchor='w')
        self.iso_widgets['note'].grid(row=4, column=0, sticky='ew', pady=(0, 8))
        self.status_label = self._label(self.workspace, '', 11, MUTED, anchor='w')
        self.status_label.grid(row=2, column=0, sticky='ew', padx=24, pady=(12, 16))
        for variable in self.iso_state.values():
            variable.trace_add('write', lambda *_: self._update_iso_result()
                               if self.mode == 'iso_fits' and not self._iso_loading else None)
        self.iso_search.trace_add('write', lambda *_: self._filter_iso_presets() if self.mode == 'iso_fits' else None)
        canvas.bind('<Configure>', lambda _: self._draw_iso_diagram())
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._update_iso_result()
        self._resize_pdf_area()

    def _build_manual_inputs(self, form):
        panel = ctk.CTkScrollableFrame(form, fg_color='transparent', corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        panel.grid(row=2, column=0, rowspan=4, sticky='nsew', padx=(8, 4), pady=(0, 8))
        panel.grid_columnconfigure((0, 1), weight=1, uniform='manual_columns')
        panel._scrollbar.configure(width=8, height=24)
        self.iso_widgets['manual_inputs'] = panel
        self._label(panel, 'SAPMALAR (mm)', 11, MUTED, True).grid(row=0, column=0, columnspan=2, sticky='w', padx=6, pady=(4, 10))
        for column, (role, label) in enumerate((('hole', 'DELİK'), ('shaft', 'MİL'))):
            self._label(panel, label, 12, ACCENT, True).grid(row=1, column=column, sticky='w', padx=6)
            for row, (side, caption) in enumerate((('upper', 'Üst sapma (+/-)'), ('lower', 'Alt sapma (+/-)'))):
                key = role+'_'+side
                self._label(panel, caption, 10, MUTED).grid(row=2+row*2, column=column, sticky='w', padx=6, pady=(10, 3))
                entry = ctk.CTkEntry(panel, textvariable=self.iso_state[key], width=90, height=36,
                    fg_color=PANEL, text_color=TEXT, border_color=BORDER, font=(UI_FONT, 14), justify='center')
                entry.grid(row=3+row*2, column=column, sticky='ew', padx=6)
                self.iso_widgets[key] = entry
        self._label(panel, 'SONUÇ BİRİMİ', 10, MUTED).grid(row=6, column=0, sticky='w', padx=6, pady=(14, 4))
        self.iso_widgets['manual_unit'] = self._iso_menu(panel, 'unit', ('mm', 'µm'), width=90)
        self.iso_widgets['manual_unit'].grid(row=6, column=1, sticky='ew', padx=6, pady=(14, 4))
        self.iso_widgets['manual_example'] = self._button(panel, 'Delik +0,02 / Mil -0,02', self._fill_manual_example, width=200)
        self.iso_widgets['manual_example'].grid(
            row=7, column=0, columnspan=2, sticky='ew', padx=6, pady=(12, 10))
        self.iso_widgets['manual_help'] = self._label(panel,
            'Nominal çap delik ve mil için ortaktır.\n\n50 +0,02: alt 0, üst +0,02.\n50 -0,02: alt -0,02, üst 0.\n\n±0,02 için alt -0,02, üst +0,02 girin.\n\nGerçekleşen tek ölçü için alt ve üst sapmayı aynı girin.\n\nSapma girişleri her zaman mm; sonuçlar mm/µm seçilebilir.',
            11, MUTED, justify='left', anchor='w', wraplength=220)
        self.iso_widgets['manual_help'].grid(row=8, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 8))

    def _fill_manual_example(self):
        self._iso_loading = True
        try:
            for key, value in [('diameter', '50'), ('hole_upper', '+0,02'), ('hole_lower', '0'),
                               ('shaft_upper', '0'), ('shaft_lower', '-0,02')]:
                self.iso_state[key].set(value)
        finally:
            self._iso_loading = False
        self._update_iso_result()

    def _iso_match_text(self, band, feature):
        matches = compare_classes(band, feature)
        exact = [item.code for item in matches if item.exact]
        if exact:
            return 'Tam eşleşme: '+', '.join(exact)
        best = matches[0]
        return (f'Tam ISO eşleşmesi yok. En yakın: {best.code}.\n'
                f'Girilen - ISO: alt {format_deviation(best.lower_difference_nm, "µm")}; '
                f'üst {format_deviation(best.upper_difference_nm, "µm")}.\n'
                'Yakın sınıflar: '+', '.join(item.code for item in matches[:3]))

    def _select_iso_preset(self, preset):
        self._iso_loading = True
        try:
            self.iso_state['hole'].set(preset.hole)
            self.iso_state['shaft'].set(preset.shaft)
        finally:
            self._iso_loading = False
        self._update_iso_result()

    def _filter_iso_presets(self):
        query = self.iso_search.get().casefold().replace(' ', '')
        for widget in [*self.iso_widgets['groups'].values(), *self.iso_widgets['preset_buttons'].values()]:
            widget.grid_remove()
        row = 0
        for kind in CLASSIFICATION:
            matches = []
            for preset in PRESETS:
                if query not in (preset.code+' '+preset.label).casefold().replace(' ', ''):
                    continue
                try:
                    actual_kind = calculate(self.iso_state['diameter'].get(), preset.hole, preset.shaft).kind
                except ValueError:
                    actual_kind = 'clearance'
                if actual_kind == kind:
                    matches.append(preset)
            if not matches:
                continue
            self.iso_widgets['groups'][kind].configure(text=CLASSIFICATION[kind].upper()
                if self.iso_result else 'ÇAPI GİRİN · EŞLEŞMELER')
            self.iso_widgets['groups'][kind].grid(row=row, column=0, sticky='w', padx=8, pady=(12, 6)); row += 1
            for preset in matches:
                button = self.iso_widgets['preset_buttons'][preset.code]
                selected = (preset.hole, preset.shaft) == (self.iso_state['hole'].get(), self.iso_state['shaft'].get())
                button.configure(fg_color=ACCENT_BG if selected else 'transparent',
                                 text_color=ACCENT if selected else TEXT)
                button.grid(row=row, column=0, sticky='ew', padx=4, pady=(0, 6)); row += 1

    def _update_iso_result(self):
        manual = self.iso_state['method'].get() == 'Manuel kontrol'
        for widget in self.iso_widgets['iso_inputs']:
            widget.grid_remove() if manual else widget.grid()
        self.iso_widgets['manual_inputs'].grid() if manual else self.iso_widgets['manual_inputs'].grid_remove()
        self.iso_widgets['comparison'].grid() if manual else self.iso_widgets['comparison'].grid_remove()
        try:
            if manual:
                fit = calculate_manual(self.iso_state['diameter'].get(),
                    *(self.iso_state[key].get() for key in ('hole_lower', 'hole_upper', 'shaft_lower', 'shaft_upper')))
            else:
                fit = calculate(self.iso_state['diameter'].get(), self.iso_state['hole'].get(), self.iso_state['shaft'].get())
        except ValueError as error:
            self.iso_result = None
            self.status_label.configure(text=str(error), text_color=RED)
            for key in ('minimum', 'maximum', 'kind', 'explanation', 'hole_limits', 'shaft_limits', 'hole_deviations', 'shaft_deviations', 'iso_comparison'):
                self.iso_widgets[key].configure(text='—')
            for key in ('copy', 'export'):
                self.iso_widgets[key].configure(state='disabled')
            self._filter_iso_presets()
            self._draw_iso_diagram()
            return
        self.iso_result = fit
        unit = self.iso_state['unit'].get()
        paint = COLORS[fit.kind]
        self.iso_widgets['kind'].configure(text=CLASSIFICATION[fit.kind], text_color=paint)
        if fit.kind == 'clearance':
            metrics = (('minimum', 'MİNİMUM BOŞLUK', fit.minimum_clearance_nm),
                       ('maximum', 'MAKSİMUM BOŞLUK', fit.maximum_clearance_nm))
        elif fit.kind == 'interference':
            metrics = (('minimum', 'MİNİMUM SIKILIK', fit.minimum_interference_nm),
                       ('maximum', 'MAKSİMUM SIKILIK', fit.maximum_interference_nm))
        else:
            metrics = (('minimum', 'MAKSİMUM SIKILIK', fit.maximum_interference_nm),
                       ('maximum', 'MAKSİMUM BOŞLUK', fit.maximum_clearance_nm))
        for key, title, value in metrics:
            self.iso_widgets[key+'_title'].configure(text=title)
            self.iso_widgets[key].configure(text=format_deviation(value, unit), text_color=paint)
        if fit.kind == 'clearance':
            explanation = 'Tüm limitlerde boşluk veya sınırda temas var.'
            if fit.minimum_clearance_nm == 0:
                explanation += ' Minimum boşluk sıfır; bu bir ara geçme değildir.'
        elif fit.kind == 'transition':
            explanation = ('Parçanın gerçekleşen ölçüsüne göre boşluk veya sıkılık oluşabilir. '
                           f'En büyük sıkılık: {format_deviation(fit.maximum_interference_nm, unit)}.')
        else:
            explanation = (f'Sıkılık aralığı: {format_deviation(fit.minimum_interference_nm, unit)}'
                           f' → {format_deviation(fit.maximum_interference_nm, unit)}.')
        if manual:
            explanation += '\n'+usage_hint(fit)+'.'
            summary = []
            for band, feature, label in ((fit.hole, 'hole', 'Delik'), (fit.shaft, 'shaft', 'mil')):
                best = compare_classes(band, feature)[0]
                summary.append(f'{label} {best.code} ({"tam" if best.exact else "en yakın"})')
            explanation += '\nISO kontrolü: '+', '.join(summary)+'.'
            self.iso_widgets['iso_comparison'].configure(text=(
                'DELİK · '+self._iso_match_text(fit.hole, 'hole')+'\n\nMİL · '+self._iso_match_text(fit.shaft, 'shaft')+
                '\n\nKarşılaştırma mevcut 11 delik / 18 mil sınıfı içindedir. Yakınlık, alt/üst sapma farklarının mutlak toplamıdır. Kullanım adları öneridir; yağlama kararı için yüzey, malzeme ve çalışma koşulları gerekir.'))
        self.iso_widgets['explanation'].configure(text=explanation)
        for key, band in [('hole', fit.hole), ('shaft', fit.shaft)]:
            self.iso_widgets[key+'_limits'].configure(text=f'{format_mm(band.minimum_mm)} / {format_mm(band.maximum_mm)} mm')
            self.iso_widgets[key+'_deviations'].configure(text=f'{format_deviation(band.lower_nm, unit)} / {format_deviation(band.upper_nm, unit)}')
        for key in ('copy', 'export'):
            self.iso_widgets[key].configure(state='normal')
        pair = 'Manuel tolerans kontrolü' if manual else f'{fit.hole.code}/{fit.shaft.code}'
        self.status_label.configure(text=f'Ø{format_mm(fit.hole.nominal_mm)} · {pair} · Tablo aralığı: {fit.hole.bracket_mm[0]} < D ≤ {fit.hole.bracket_mm[1]} mm', text_color=MUTED)
        self._filter_iso_presets()
        self._draw_iso_diagram()

    def _draw_iso_diagram(self):
        draw(self.iso_widgets['canvas'], self.iso_result, self.iso_state['view'].get(),
             self.iso_state['sample'].get(), ctk.get_appearance_mode(), self.workspace._get_widget_scaling())

    def _resize_iso_workspace(self):
        self._layout_fit_id = None
        if self._closed:
            return
        scale = self.workspace._get_widget_scaling()
        width = self.workspace.winfo_width()/scale
        form_width = max(250, min(308, (width-64)*.33))
        self.iso_widgets['form'].configure(width=form_width)
        self.iso_widgets['canvas'].configure(height=round(220*scale))
        available = max(260, int(width-form_width-96))
        for key in ('explanation', 'note', 'iso_comparison'):
            self.iso_widgets[key].configure(wraplength=available)
        self.iso_widgets['manual_help'].configure(wraplength=max(170, form_width-48))
        self.status_label.configure(wraplength=max(300, width-48))
        self._draw_iso_diagram()

    def _iso_report_rows(self):
        fit = self.iso_result
        if fit is None:
            return []
        rows = [('Standart temeli', 'ISO 286-1:2010 / ISO 286-2:2010'),
                ('Hesap yöntemi', self.iso_state['method'].get()),
                ('Nominal çap (mm)', format_mm(fit.hole.nominal_mm)),
                ('Delik sınıfı', fit.hole.code), ('Mil sınıfı', fit.shaft.code),
                ('Geçme türü', CLASSIFICATION[fit.kind]),
                ('Delik minimum (mm)', format_mm(fit.hole.minimum_mm)),
                ('Delik maksimum (mm)', format_mm(fit.hole.maximum_mm)),
                ('Mil minimum (mm)', format_mm(fit.shaft.minimum_mm)),
                ('Mil maksimum (mm)', format_mm(fit.shaft.maximum_mm)),
                ('EI (µm)', format_deviation(fit.hole.lower_nm, 'µm').split(' ')[0]),
                ('ES (µm)', format_deviation(fit.hole.upper_nm, 'µm').split(' ')[0]),
                ('ei (µm)', format_deviation(fit.shaft.lower_nm, 'µm').split(' ')[0]),
                ('es (µm)', format_deviation(fit.shaft.upper_nm, 'µm').split(' ')[0]),
                ('Minimum delik − mil (mm)', format_deviation(fit.minimum_clearance_nm).split(' ')[0]),
                ('Maksimum delik − mil (mm)', format_deviation(fit.maximum_clearance_nm).split(' ')[0]),
                ('Kapsam', '1–400 mm; seçili doğrulanmış sınıflar; şematik kesit; montaj kuvveti hesabı yok')]
        if self.iso_state['method'].get() == 'Manuel kontrol':
            rows.extend([('Delik ISO kontrolü', self._iso_match_text(fit.hole, 'hole')),
                         ('Mil ISO kontrolü', self._iso_match_text(fit.shaft, 'shaft')),
                         ('Kullanım yorumu (öneri)', usage_hint(fit)),
                         ('Kullanım sınırı', 'Yağlama ve montaj kararı için yüzey/malzeme/çalışma koşulları gerekir.')])
        return rows

    def _copy_iso_result(self):
        rows = self._iso_report_rows()
        if rows:
            self.clipboard_clear()
            self.clipboard_append('\n'.join(f'{key}: {value}' for key, value in rows))

    def _save_iso_report(self):
        if self.iso_result is None:
            return
        path = filedialog.asksaveasfilename(title='ISO geçme hesabını kaydet', defaultextension='.csv',
                                           filetypes=[('CSV raporu', '*.csv')], initialfile='ISO_Gecme_Raporu.csv')
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.writer(stream, delimiter=';')
                writer.writerow(('Parametre', 'Değer')); writer.writerows(self._iso_report_rows())
            self.status_label.configure(text=f'CSV raporu kaydedildi: {path}', text_color=GREEN)
        except OSError as error:
            self.status_label.configure(text=f'CSV kaydedilemedi: {error}', text_color=RED)

    def _show_iso_sources(self):
        self._close_detail()
        window = ctk.CTkToplevel(self)
        self.detail_window = window
        window.title('ISO geçmeleri · Kaynaklar ve hesap kapsamı')
        window.geometry('700x540'); window.minsize(520, 360)
        window.configure(fg_color=PANEL); window.transient(self)
        window.grid_columnconfigure(0, weight=1); window.grid_rowconfigure(1, weight=1)
        self._label(window, 'ISO 286 · Kaynaklar ve kullanım', 20, bold=True).grid(row=0, column=0, sticky='w', padx=24, pady=(20, 12))
        content = ctk.CTkTextbox(window, fg_color=INPUT, text_color=TEXT, font=(UI_FONT, 12), wrap='word')
        content.grid(row=1, column=0, sticky='nsew', padx=24)
        content.insert('1.0', SOURCE_TEXT); content.configure(state='disabled')
        actions = ctk.CTkFrame(window, fg_color='transparent')
        actions.grid(row=2, column=0, sticky='ew', padx=24, pady=16)
        self._button(actions, 'ISO 286 kataloğu', lambda: webbrowser.open(
            'https://www.iso.org/obp/ui/#iso:std:iso:286:-2:ed-2:v1:en'), width=150).pack(side='left', padx=(0, 8))
        self._button(actions, 'Kaynak kılavuzu', lambda: webbrowser.open(
            'https://github.com/gkkizil/gokworks/blob/codex/dxf-dwg-gui-report/docs/iso-fits.md'), width=150).pack(side='left')
        self._button(actions, 'Kapat', self._close_detail, width=100).pack(side='right')
        window.protocol('WM_DELETE_WINDOW', self._close_detail)
        window.bind('<Escape>', lambda _: self._close_detail())
