"""ASME geometrik toleranslar için bağımsız, temalı öğretici çalışma alanı."""

import csv
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from geometric_tolerances.catalog import CATALOG, CHARACTERISTICS, GROUPS, GUIDE
from geometric_tolerances.diagram import draw, symbol
from geometric_tolerances.rules import DATUM_CHOICES, fmt, specify
from gui.theme import (PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       GREEN, AMBER, RED, SECONDARY, HOVER, UI_FONT)


class GeometricTolerancesView:
    def _create_gdt_state(self, saved):
        defaults = {'kind': 'cylindricity', 'size': '100', 'tolerance': '0,05', 'datum': 'A', 'size_tolerance': ''}
        self.gdt_state = {key: tk.StringVar(self, value=str(saved.get(f'gdt_{key}', value)))
                          for key, value in defaults.items()}
        for key, choices in [('kind', CHARACTERISTICS), ('datum', DATUM_CHOICES)]:
            if self.gdt_state[key].get() not in choices:
                self.gdt_state[key].set(defaults[key])
        # Measurement belongs to a particular feature/session, never to a saved default.
        self.gdt_state['measured'] = tk.StringVar(self, value='')
        self.gdt_search = tk.StringVar(self, value='')
        self.gdt_widgets, self.gdt_result = {}, None
        self._gdt_loading = False

    def _gdt_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=INPUT, border_color=BORDER,
                            border_width=1, corner_radius=12)

    def _build_gdt_workspace(self):
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self.workspace, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 16))
        header.grid_columnconfigure(0, weight=1)
        self._label(header, 'GOKWORKS  /  ASME Y14.5-2018', 10, MUTED, True).grid(row=0, column=0, sticky='w')
        self._label(header, 'Geometrik Toleranslar', 24, bold=True).grid(row=1, column=0, sticky='w', pady=(4, 2))
        self._label(header, 'GD&T · 12 güncel özellik ve eski işaretler', 12, MUTED,
                    wraplength=340, justify='left').grid(row=2, column=0, sticky='w')
        actions = ctk.CTkFrame(header, fg_color='transparent')
        actions.grid(row=1, column=1, rowspan=2, sticky='e', padx=(12, 0))
        self.gdt_widgets['guide'] = self._button(actions, 'Rehber', self._show_gdt_guide, width=90)
        self.gdt_widgets['guide'].pack(side='left', padx=(0, 8))
        self.gdt_widgets['export'] = self._button(actions, 'CSV kaydet', self._save_gdt_report,
                                                  primary=True, icon='download', width=126)
        self.gdt_widgets['export'].pack(side='left')
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=1, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        catalog = self._gdt_card(body)
        catalog.configure(width=258)
        catalog.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        catalog.grid_propagate(False)
        catalog.grid_columnconfigure(0, weight=1)
        catalog.grid_rowconfigure(2, weight=1)
        self.gdt_widgets['catalog'] = catalog
        self._label(catalog, 'GEOMETRİK ÖZELLİKLER', 11, MUTED, True).grid(row=0, column=0, sticky='w', padx=16, pady=(16, 8))
        search_row = ctk.CTkFrame(catalog, fg_color='transparent')
        search_row.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 10))
        search_row.grid_columnconfigure(1, weight=1)
        self._label(search_row, 'Ara', 11, MUTED).grid(row=0, column=0, padx=(0, 6))
        search = ctk.CTkEntry(search_row, textvariable=self.gdt_search, height=34,
                              fg_color=PANEL, text_color=TEXT, border_color=BORDER,
                              placeholder_text='Tür veya kullanım ara', font=(UI_FONT, 12))
        search.grid(row=0, column=1, sticky='ew')
        self.gdt_widgets['search'] = search
        listing = ctk.CTkScrollableFrame(catalog, fg_color='transparent', corner_radius=0,
                                         scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        listing.grid(row=2, column=0, sticky='nsew', padx=(8, 4), pady=(0, 8))
        listing.grid_columnconfigure(0, weight=1)
        listing._scrollbar.configure(width=8, height=24)
        self.gdt_widgets['listing'] = listing
        self.gdt_widgets['groups'] = {group: self._label(listing, group.upper(), 10, MUTED, True) for group in GROUPS}
        self.gdt_widgets['choices'] = {}
        for item in CATALOG:
            button = ctk.CTkButton(listing, text=item.name,
                height=38, anchor='w', corner_radius=7, border_width=1, border_color=BORDER,
                fg_color='transparent', hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 12),
                command=lambda key=item.key: self._select_gdt(key))
            self.gdt_widgets['choices'][item.key] = button
        self.gdt_widgets['count'] = self._label(catalog, '', 10, MUTED)
        self.gdt_widgets['count'].grid(row=3, column=0, sticky='w', padx=16, pady=(0, 12))
        details = ctk.CTkScrollableFrame(body, fg_color='transparent', corner_radius=0,
                                         scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        details.grid(row=0, column=1, sticky='nsew')
        details.grid_columnconfigure(0, weight=1)
        details._scrollbar.configure(width=8, height=24)
        self.gdt_widgets['details'] = details
        heading = self._gdt_card(details)
        heading.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        heading.grid_columnconfigure(1, weight=1)
        icon = tk.Canvas(heading, width=50, height=54, borderwidth=0, highlightthickness=0)
        icon.grid(row=0, column=0, rowspan=3, padx=(14, 12), pady=14)
        self.gdt_widgets['symbol'] = icon
        for row, key, size, color, bold in [(0, 'title', 20, TEXT, True), (1, 'english', 11, ACCENT, True), (2, 'description', 12, MUTED, False)]:
            label = self._label(heading, '', size, color, bold, justify='left', anchor='w', wraplength=370)
            label.grid(row=row, column=1, sticky='ew', padx=(0, 14), pady=(12 if row == 0 else 2, 12 if row == 2 else 0))
            self.gdt_widgets[key] = label
        inputs = self._gdt_card(details)
        inputs.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        inputs.grid_columnconfigure((0, 1), weight=1, uniform='gdt_inputs')
        for key, label, row, column in [('size', 'GÖSTERİM BOYUTU (mm)', 0, 0),
                                       ('tolerance', 'TOPLAM TOLERANS t (mm)', 0, 1)]:
            self._label(inputs, label, 10, MUTED, True, wraplength=170, justify='left', anchor='w').grid(row=row, column=column, sticky='ew', padx=14, pady=(12, 5))
            entry = ctk.CTkEntry(inputs, textvariable=self.gdt_state[key], height=34,
                                 fg_color=PANEL, text_color=TEXT, border_color=BORDER,
                                 font=(UI_FONT, 14), placeholder_text='İsteğe bağlı' if key == 'measured' else '')
            entry.grid(row=row+1, column=column, sticky='ew', padx=14, pady=(0, 4))
            self.gdt_widgets[key] = entry
        self._label(inputs, 'DATUM SİSTEMİ / ÖNCELİK', 10, MUTED, True, wraplength=170,
                    justify='left', anchor='w').grid(row=2, column=0, sticky='ew', padx=14, pady=(12, 5))
        menu = ctk.CTkOptionMenu(inputs, variable=self.gdt_state['datum'], values=list(DATUM_CHOICES),
            width=140, height=34, fg_color=SECONDARY, button_color=SECONDARY, button_hover_color=HOVER,
            dropdown_fg_color=PANEL, dropdown_hover_color=HOVER, dropdown_text_color=TEXT, text_color=TEXT,
            text_color_disabled=MUTED, font=(UI_FONT, 12), dropdown_font=(UI_FONT, 12))
        menu.grid(row=3, column=0, sticky='ew', padx=14, pady=(0, 4))
        self.gdt_widgets['datum'] = menu
        self.gdt_widgets['datum_display'] = tk.StringVar(self, value='Gerekmez')
        self.gdt_widgets['value'] = self._label(inputs, '', 16, ACCENT, True, anchor='w', justify='left', wraplength=180)
        self.gdt_widgets['value'].grid(row=2, column=1, rowspan=2, sticky='ew', padx=14, pady=(8, 2))
        self.gdt_widgets['datum_note'] = self._label(inputs, '', 11, MUTED, justify='left', anchor='w', wraplength=400)
        self.gdt_widgets['datum_note'].grid(row=4, column=0, columnspan=2, sticky='ew', padx=14, pady=(4, 12))
        diagram = self._gdt_card(details)
        diagram.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        diagram.grid_columnconfigure(0, weight=1)
        self._label(diagram, 'TOLERANS ÇERÇEVESİ / BÖLGE', 10, MUTED, True).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 0))
        for row, key, height in [(1, 'frame', 62), (2, 'canvas', 214)]:
            canvas = tk.Canvas(diagram, height=height, borderwidth=0, highlightthickness=0)
            canvas.grid(row=row, column=0, sticky='ew', padx=12)
            canvas.bind('<Configure>', lambda _: self._draw_gdt_diagram() if self.mode == 'geometric_tolerances' else None)
            self.gdt_widgets[key] = canvas
        self.gdt_widgets['zone'] = self._label(diagram, '', 12, TEXT, justify='left', anchor='w', wraplength=400)
        self.gdt_widgets['zone'].grid(row=3, column=0, sticky='ew', padx=14, pady=(6, 14))
        for row, key, caption in [(3, 'measurement', 'NASIL ÖLÇÜLÜR?'), (4, 'note', 'ÜRETİM / TASARIM NOTU'),
                                  (5, 'assessment', 'ÖLÇÜM KARŞILAŞTIRMASI')]:
            card = self._gdt_card(details)
            card.grid(row=row, column=0, sticky='ew', pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)
            self._label(card, caption, 10, ACCENT, True).grid(row=0, column=0, sticky='w', padx=14, pady=(12, 6))
            if key == 'assessment':
                rule = ctk.CTkFrame(card, fg_color='transparent')
                rule.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
                rule.grid_columnconfigure(0, weight=1)
                self.gdt_widgets['size_rule'] = rule
                self._label(rule, 'İlgili boyut toleransı (mm, isteğe bağlı)', 11, MUTED, wraplength=240, justify='left').grid(row=0, column=0, sticky='w')
                size_entry = ctk.CTkEntry(rule, textvariable=self.gdt_state['size_tolerance'], height=34,
                    fg_color=PANEL, text_color=TEXT, border_color=BORDER, font=(UI_FONT, 14))
                size_entry.grid(row=1, column=0, sticky='ew', pady=(5, 6))
                self.gdt_widgets['size_tolerance'] = size_entry
                self.gdt_widgets['size_rule_help'] = self._label(rule,
                    'Normal, boyutla ilişkili yüzey için toplam boyut toleransı: üst limit - alt limit. ASME 8.4: t < boyut toleransı. MMC zarfı ölçümü değildir.',
                    11, MUTED, wraplength=400, anchor='w', justify='left')
                self.gdt_widgets['size_rule_help'].grid(row=2, column=0, sticky='ew')
                self._label(card, 'Ölçülmüş toplam geometrik hata (mm)', 11, MUTED).grid(row=2, column=0, sticky='w', padx=14)
                entry = ctk.CTkEntry(card, textvariable=self.gdt_state['measured'], height=34,
                    fg_color=PANEL, text_color=TEXT, border_color=BORDER, font=(UI_FONT, 14))
                entry.grid(row=3, column=0, sticky='ew', padx=14, pady=(5, 10))
                self.gdt_widgets['measured'] = entry
            self.gdt_widgets[key] = self._label(card, '', 12, TEXT, justify='left', anchor='w', wraplength=400)
            self.gdt_widgets[key].grid(row=4 if key == 'assessment' else 1, column=0, sticky='ew', padx=14, pady=(0, 14))
        self.gdt_widgets['example'] = self._label(details, '', 11, MUTED, justify='left', anchor='w', wraplength=400)
        self.gdt_widgets['example'].grid(row=6, column=0, sticky='ew', padx=4, pady=(0, 8))
        self.gdt_widgets['copy'] = self._button(details, 'Belirtimi kopyala', self._copy_gdt_report, icon='copy', width=165)
        self.gdt_widgets['copy'].grid(row=7, column=0, sticky='w', padx=4, pady=(0, 14))
        self.status_label = self._label(self.workspace, '', 11, MUTED, anchor='w', justify='left', wraplength=700)
        self.status_label.grid(row=2, column=0, sticky='ew', padx=24, pady=(10, 16))
        for variable in self.gdt_state.values():
            variable.trace_add('write', lambda *_: self._update_gdt_result() if self.mode == 'geometric_tolerances' and not self._gdt_loading else None)
        self.gdt_search.trace_add('write', lambda *_: self._filter_gdt_catalog(reset=True) if self.mode == 'geometric_tolerances' else None)
        self._update_gdt_result()
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._resize_pdf_area()

    def _select_gdt(self, key):
        self._gdt_loading = True
        try:
            self.gdt_state['kind'].set(key)
            self.gdt_state['measured'].set('')
            self.gdt_state['size_tolerance'].set('')
        finally:
            self._gdt_loading = False
        self.gdt_widgets['details']._parent_canvas.yview_moveto(0)
        self._update_gdt_result()
        listing = self.gdt_widgets['listing']
        listing.update_idletasks()
        button = self.gdt_widgets['choices'][key]
        if button.grid_info():
            viewport = listing._parent_canvas
            viewport.yview_moveto(max(0, button.winfo_y()-viewport.winfo_height()*.4)/max(1, listing.winfo_height()))

    def _filter_gdt_catalog(self, reset=False):
        normalize = lambda value: value.casefold().replace('\u0307', '')
        query = normalize(self.gdt_search.get().strip())
        for widget in (*self.gdt_widgets['groups'].values(), *self.gdt_widgets['choices'].values()):
            widget.grid_remove()
        row, count = 0, 0
        for group in GROUPS:
            items = [item for item in CATALOG if item.group == group and query in normalize(
                ' '.join((item.name, item.english, item.group, item.example)))]
            if not items:
                continue
            self.gdt_widgets['groups'][group].grid(row=row, column=0, sticky='w', padx=6, pady=(8, 5))
            row += 1
            for item in items:
                active = item.key == self.gdt_state['kind'].get()
                button = self.gdt_widgets['choices'][item.key]
                button.configure(fg_color=ACCENT_BG if active else 'transparent', text_color=ACCENT if active else TEXT)
                button.grid(row=row, column=0, sticky='ew', padx=4, pady=(0, 5))
                row += 1
                count += 1
        if reset:
            self.gdt_widgets['listing']._parent_canvas.yview_moveto(0)
        self.gdt_widgets['count'].configure(text=f'{count} / {len(CATALOG)} · 12 güncel + 2 eski' if count else 'Eşleşen özellik bulunamadı.')

    def _update_gdt_result(self):
        item = CHARACTERISTICS.get(self.gdt_state['kind'].get())
        if item is None:
            self.gdt_result = None
            self._show_gdt_error('Geometrik tolerans türünü seçin.')
            return
        for key, text in [('title', item.name), ('english', f'{item.english} · § {item.reference}'),
                          ('description', item.description), ('zone', item.zone),
                          ('measurement', item.measurement), ('note', item.note),
                          ('example', 'Kullanım örneği: '+item.example)]:
            self.gdt_widgets[key].configure(text=text)
        for key in ('size', 'tolerance', 'measured', 'size_tolerance'):
            self.gdt_widgets[key].configure(state='normal' if item.active else 'disabled')
        self.gdt_widgets['size_rule'].grid() if item.group == 'Şekil' else self.gdt_widgets['size_rule'].grid_remove()
        self.gdt_widgets['datum'].configure(state='disabled' if item.datum == 'none' or not item.active else 'normal',
            variable=self.gdt_widgets['datum_display'] if item.datum == 'none' else self.gdt_state['datum'])
        self.gdt_widgets['datum_note'].configure(text={
            'none': 'Şekil toleransı: datum çerçeveye eklenmez.',
            'optional': 'Datum seçime bağlıdır; teorik ölçü/profil tanımı ayrıca gerekir.',
            'required': 'Bu örnek referanslıdır; datum sırası ölçüm önceliğini belirler.'}[item.datum])
        if not item.active:
            self.gdt_result = None
            self._show_gdt_error('ASME 2018: eski sembol; position/profile/runout ile işlevine göre yeniden belirtin.')
            self.gdt_widgets['value'].configure(text='2018’de kaldırıldı', text_color=AMBER)
            self.gdt_widgets['datum_note'].configure(text='Eski çizim okuma bilgisi · güncel belirtim oluşturulmaz.')
            self._filter_gdt_catalog()
            return
        try:
            self.gdt_result = specify(*(self.gdt_state[key].get() for key in ('kind', 'size', 'tolerance', 'datum', 'measured', 'size_tolerance')))
        except ValueError as error:
            self.gdt_result = None
            self._show_gdt_error(str(error))
        else:
            spec = self.gdt_result
            value = ('Øt' if item.diametrical else 't') + ' = '+fmt(spec.tolerance)+' mm'
            if item.diametrical:
                value += '\nRadyal pay: '+fmt(spec.tolerance/2)+' mm'
            self.gdt_widgets['value'].configure(text=value, text_color=ACCENT)
            self.gdt_widgets['assessment'].configure(text=self._gdt_assessment(), text_color=
                MUTED if spec.accepted is None else GREEN if spec.accepted else RED)
            self.status_label.configure(text=f'ASME Y14.5-2018 · § {item.reference} · Kullanıcı belirtimi; basic ölçüler/boyut limitleri ayrıca gerekir.', text_color=MUTED)
            for key in ('copy', 'export'):
                self.gdt_widgets[key].configure(state='normal')
            self._draw_gdt_diagram()
        self._filter_gdt_catalog()

    def _show_gdt_error(self, message):
        self.gdt_widgets['value'].configure(text='Değerleri kontrol edin.', text_color=RED)
        self.gdt_widgets['assessment'].configure(text='Geçerli belirtim olmadan karşılaştırma yapılmaz.', text_color=MUTED)
        self.status_label.configure(text=message, text_color=RED)
        for key in ('copy', 'export'):
            self.gdt_widgets[key].configure(state='disabled')
        self._draw_gdt_diagram()

    def _gdt_assessment(self):
        spec = self.gdt_result
        relation = (('Boyut ilişkisi: t < '+fmt(spec.size_tolerance)+' mm kontrol edildi; MMC zarfı ölçülmedi.\n')
                    if spec.size_tolerance is not None else
                    'Boyut toleransı girilmedi; Rule #1 boyut/şekil ilişkisi ayrıca kontrol edilir.\n' if spec.characteristic.group == 'Şekil' else '')
        if spec.measured is None:
            return relation+'Ölçüm girilmedi. İlgili özellik için değerlendirilmiş toplam geometrik hatayı girin; tek çap veya nokta ölçüsü yeterli değildir.'
        verdict = 'Matematiksel sınır içinde' if spec.accepted else 'Matematiksel sınır dışında'
        if spec.margin == 0:
            verdict += ' · tam sınırda'
        return (relation+f'{verdict}\nHata {fmt(spec.measured)} mm; sınır {fmt(spec.tolerance)} mm.\n'
                f'Kalan pay: {fmt(spec.margin)} mm.\n'
                'Yalnızca hata <= t karşılaştırması; tam resim/model uygunluğu, ölçüm belirsizliği ve kalite kabulü değerlendirilmez.')

    def _draw_gdt_diagram(self):
        scale = self.workspace._get_widget_scaling()
        theme = ctk.get_appearance_mode()
        for key in ('canvas', 'frame'):
            draw(self.gdt_widgets[key], self.gdt_result, theme, scale, frame=key == 'frame')
        item = CHARACTERISTICS.get(self.gdt_state['kind'].get())
        if item is not None and not item.active:
            for key in ('frame', 'canvas'):
                area = self.gdt_widgets[key]
                area.delete('all')
                area.create_text(area.winfo_width()/2, area.winfo_height()/2,
                    text='ASME 2018’de kaldırıldı\nGüncel çerçeve / bölge üretilmez.',
                    fill=AMBER[1 if theme == 'Dark' else 0], font=(UI_FONT, -round(12*scale)),
                    width=max(100, area.winfo_width()-24*scale), tags='legacy')
        canvas = self.gdt_widgets['symbol']
        color = lambda pair: pair[1 if theme == 'Dark' else 0]
        canvas.configure(background=color(INPUT), width=round(50*scale), height=round(54*scale))
        canvas.delete('all')
        kind = self.gdt_state['kind'].get()
        if kind in CHARACTERISTICS:
            symbol(canvas, kind, 25*scale, 27*scale, 26*scale, color(ACCENT if item.active else AMBER), 2*scale)

    def _resize_gdt_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.mode != 'geometric_tolerances':
            return
        scale = self.workspace._get_widget_scaling()
        width = self.workspace.winfo_width()/scale
        form_width = max(224, min(270, (width-64)*.29))
        self.gdt_widgets['catalog'].configure(width=form_width)
        available = max(240, int(width-form_width-104))
        self.gdt_widgets['value'].configure(wraplength=max(140, (available-28)/2))
        for key in ('zone', 'measurement', 'note', 'assessment', 'example', 'datum_note', 'size_rule_help'):
            self.gdt_widgets[key].configure(wraplength=available)
        for key in ('title', 'english', 'description'):
            self.gdt_widgets[key].configure(wraplength=max(180, available-74))
        self.gdt_widgets['canvas'].configure(height=round(214*scale))
        self.gdt_widgets['frame'].configure(height=round(62*scale))
        self.status_label.configure(wraplength=max(300, width-48))
        self._draw_gdt_diagram()

    def _gdt_report_rows(self):
        spec = self.gdt_result
        if spec is None:
            return []
        item = spec.characteristic
        return [('Standart temeli', 'ASME Y14.5-2018'), ('Belge bölümü', item.reference),
                ('Değiştirici varsayımı', 'Boyut özelliğinde RFS / datum boyut özelliğinde RMB (5.9.1); yüzey şekli için M/L yok'), ('Özellik', item.name),
                ('İngilizce', item.english), ('Kategori', item.group), ('Açıklama', item.description),
                ('Gösterim boyutu (mm)', fmt(spec.size)), ('Toplam tolerans t (mm)', fmt(spec.tolerance)),
                ('İlgili boyut toleransı (mm)', '' if spec.size_tolerance is None else fmt(spec.size_tolerance)),
                ('Bölge değerinin anlamı', 'Çap' if item.diametrical else 'Toplam genişlik / radyal mesafe'),
                ('Datum sırası', ' | '.join(spec.datums) or 'Yok'), ('Örnek çerçeve', spec.frame),
                ('Bölge', item.zone), ('Ölçüm yöntemi', item.measurement), ('Üretim notu', item.note),
                ('Kullanım örneği', item.example),
                ('Ölçülmüş toplam geometrik hata (mm)', '' if spec.measured is None else fmt(spec.measured)),
                ('Aritmetik karşılaştırma', self._gdt_assessment()),
                ('Kapsam', 'Öğretici şema; tasarımcı belirtimi; CAD değişikliği veya belirsizlikle kalite kabulü değildir.')]

    def _copy_gdt_report(self):
        rows = self._gdt_report_rows()
        if rows:
            self.clipboard_clear()
            self.clipboard_append('\n'.join(f'{key}: {value}' for key, value in rows))
            self.status_label.configure(text='Geometrik tolerans belirtimi panoya kopyalandı.', text_color=GREEN)

    def _save_gdt_report(self):
        rows = self._gdt_report_rows()
        if not rows:
            return
        path = filedialog.asksaveasfilename(parent=self, title='Geometrik tolerans belirtimini kaydet',
            initialfile='GOKWORKS_Geometrik_Tolerans.csv', defaultextension='.csv', filetypes=[('CSV raporu', '*.csv')])
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.writer(stream, delimiter=';')
                writer.writerow(('Alan', 'Değer'))
                writer.writerows(rows)
        except OSError as error:
            self.status_label.configure(text=f'CSV kaydedilemedi: {error}', text_color=RED)
        else:
            self.status_label.configure(text='Geometrik tolerans CSV raporu kaydedildi.', text_color=GREEN)

    def _show_gdt_guide(self):
        self._close_detail()
        window = ctk.CTkToplevel(self)
        self.detail_window = window
        window.title('GOKWORKS · Geometrik tolerans rehberi')
        window.geometry('760x580')
        window.minsize(540, 400)
        window.configure(fg_color=PANEL)
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        self._label(window, 'GD&T / ASME 2018 · Okuma rehberi', 20, bold=True, wraplength=490,
                    justify='left').grid(row=0, column=0, sticky='w', padx=24, pady=(20, 12))
        self.gdt_widgets['guide_text'] = ctk.CTkTextbox(window, fg_color=INPUT, text_color=TEXT, wrap='word', font=(UI_FONT, 13))
        self.gdt_widgets['guide_text'].grid(row=1, column=0, sticky='nsew', padx=24)
        self.gdt_widgets['guide_text'].insert('1.0', GUIDE)
        self.gdt_widgets['guide_text'].configure(state='disabled')
        self._button(window, 'Kapat', self._close_detail, width=90).grid(row=2, column=0, sticky='e', padx=24, pady=18)
        window.protocol('WM_DELETE_WINDOW', self._close_detail)
        window.bind('<Escape>', lambda _: self._close_detail())
