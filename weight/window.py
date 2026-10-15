"""Material weight workspace with live geometry and density inputs."""

from math import isfinite
import tkinter as tk

import customtkinter as ctk

from gui.rendering import configure_changed
from gui.theme import (PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       AMBER, RED, HOVER, UI_FONT)
from weight.diagram import draw, draw_icon
from weight.rules import (KINDS, MATERIALS, UNITS, METHODS, FIELDS, FIELD_LABELS,
                          DEFAULT_DIMENSIONS, calculate)


LINEAR_FIELDS = ('b', 'h', 't', 'tw', 'tf', 'd', 's', 'length')


def _number(value):
    try:
        result = float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError):
        return None
    return result if isfinite(result) else None


def _fmt(value, digits=3):
    if abs(value) >= 1e9:
        return f'{value:.3e}'.replace('.', ',')
    if value != 0 and abs(value) < .5*10**(-digits):
        return f'{value:.3g}'.replace('.', ',')
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class WeightView:
    def _create_weight_state(self, saved):
        defaults = dict(DEFAULT_DIMENSIONS, kind='Sac levha', material='Demir / Çelik',
                        unit='mm', length='1000', count='1', method='Ölçülerden', area_cm2='10')
        self.weight_state = {key: tk.StringVar(self, value=str(saved.get('weight_'+key, value)))
                             for key, value in defaults.items()}
        for key, choices in (('kind', KINDS), ('material', MATERIALS), ('unit', UNITS), ('method', METHODS)):
            if self.weight_state[key].get() not in choices:
                self.weight_state[key].set(defaults[key])
        density = saved.get('weight_density', MATERIALS[self.weight_state['material'].get()])
        self.weight_state['density'] = tk.StringVar(self, value=str(density))
        self.weight_result = None
        self.weight_widgets = {'loading': False, 'unit': self.weight_state['unit'].get()}

    def _weight_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)

    def _weight_menu(self, parent, key, values):
        return ctk.CTkOptionMenu(parent, variable=self.weight_state[key], values=list(values),
            width=1, height=34, fg_color=INPUT, button_color=INPUT, button_hover_color=HOVER,
            dropdown_fg_color=PANEL, dropdown_hover_color=HOVER, dropdown_text_color=TEXT,
            text_color=TEXT, font=(UI_FONT, 12), dropdown_font=(UI_FONT, 12), dynamic_resizing=False)

    def _weight_input(self, parent, key, title, row, column, choices=None):
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.grid(row=row, column=column, sticky='ew', padx=8, pady=(8, 0))
        frame.grid_columnconfigure(0, weight=1)
        label = self._label(frame, title, 11, MUTED, anchor='w')
        label.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        control = (self._weight_menu(frame, key, choices) if choices else
                   ctk.CTkEntry(frame, textvariable=self.weight_state[key], width=1, height=34,
                               fg_color=INPUT, text_color=TEXT, border_color=BORDER, font=(UI_FONT, 13)))
        control.grid(row=1, column=0, sticky='ew')
        self.weight_widgets[key+'_input'] = control
        self.weight_widgets[key+'_label'] = label
        return frame

    def _build_weight_workspace(self):
        self.workspace = self._workspace_shell()
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)
        w = self.weight_widgets
        _, actions, _ = self._page_header('Ağırlık hesabı',
            'Kesiti seçin, ölçü ve malzemeden ağırlığı hesaplayın.',
            'MÜHENDİSLİK / MALZEME', 'layers')
        w['copy'] = self._button(actions, 'Hesabı kopyala', self._copy_weight_result,
                                icon='copy', width=140)
        w['copy'].pack()
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=1, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure((0, 1), weight=1, uniform='weight_columns')
        body.grid_rowconfigure(0, weight=1)
        for column, key in enumerate(('form', 'details')):
            panel = ctk.CTkScrollableFrame(body, width=1, fg_color='transparent', corner_radius=0,
                scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
            panel.grid(row=0, column=column, sticky='nsew', padx=(0, 12) if column == 0 else 0)
            panel.grid_columnconfigure(0, weight=1)
            panel._scrollbar.configure(width=8, height=0)
            w[key] = panel
        selector = self._weight_card(w['form'])
        selector.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        selector.grid_columnconfigure(0, weight=1)
        self._label(selector, 'KESİT SEÇİMİ', 12, ACCENT, bold=True).grid(
            row=0, column=0, sticky='w', padx=12, pady=(12, 6))
        listing = ctk.CTkScrollableFrame(selector, height=174, width=1, fg_color='transparent',
            corner_radius=0, scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        listing.grid(row=1, column=0, sticky='ew', padx=(6, 2), pady=(0, 8))
        listing.grid_columnconfigure((0, 1, 2), weight=1, uniform='weight_kinds')
        listing._scrollbar.configure(width=7, height=0)
        w['listing'], w['choices'], w['icons'], w['tiles'] = listing, {}, {}, {}
        for index, kind in enumerate(KINDS):
            tile = ctk.CTkFrame(listing, fg_color=INPUT, corner_radius=9, border_width=1, border_color=BORDER)
            tile.grid(row=index//3, column=index % 3, sticky='ew', padx=3, pady=3)
            tile.grid_columnconfigure(0, weight=1)
            canvas = tk.Canvas(tile, width=34, height=32, highlightthickness=0, borderwidth=0)
            canvas.grid(row=0, column=0, pady=(5, 0))
            button = ctk.CTkButton(tile, text=kind, width=1, height=25, fg_color='transparent',
                text_color=TEXT, hover_color=HOVER, font=(UI_FONT, 10),
                command=lambda value=kind: self._select_weight_kind(value))
            button.grid(row=1, column=0, sticky='ew', padx=2, pady=(0, 4))
            tile.bind('<Button-1>', lambda _, value=kind: self._select_weight_kind(value))
            canvas.bind('<Button-1>', lambda _, value=kind: self._select_weight_kind(value))
            w['choices'][kind], w['icons'][kind], w['tiles'][kind] = button, canvas, tile
        form = self._weight_card(w['form'])
        form.grid(row=1, column=0, sticky='ew')
        form.grid_columnconfigure((0, 1), weight=1, uniform='weight_inputs')
        self._label(form, 'ÖLÇÜLER VE MALZEME', 12, ACCENT, bold=True).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=12, pady=(12, 8))
        method = ctk.CTkSegmentedButton(form, variable=self.weight_state['method'], values=list(METHODS),
            height=34, fg_color=INPUT, selected_color=ACCENT_BG, selected_hover_color=HOVER,
            unselected_color=INPUT, unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 11))
        method.grid(row=1, column=0, columnspan=2, sticky='ew', padx=8)
        w['method_input'] = method
        self._weight_input(form, 'material', 'Malzeme', 2, 0, MATERIALS)
        self._weight_input(form, 'density', 'Yoğunluk (kg/m³)', 2, 1)
        self._weight_input(form, 'unit', 'Ölçü birimi', 3, 0, UNITS)
        self._weight_input(form, 'count', 'Adet', 3, 1)
        self._weight_input(form, 'length', 'Boy / uzunluk (mm)', 4, 0)
        w['area_frame'] = self._weight_input(form, 'area_cm2', 'Katalog kesit alanı (cm²)', 4, 1)
        dimensions = ctk.CTkFrame(form, fg_color='transparent')
        dimensions.grid(row=5, column=0, columnspan=2, sticky='ew')
        dimensions.grid_columnconfigure((0, 1), weight=1, uniform='weight_dimensions')
        w['dimensions'], w['dim_frames'] = dimensions, {}
        for index, key in enumerate(key for key in LINEAR_FIELDS if key != 'length'):
            w['dim_frames'][key] = self._weight_input(dimensions, key, FIELD_LABELS[key]+' (mm)', index//2, index % 2)
        w['unit_hint'] = self._label(form,
            'Birim değişince boy ve kesit ölçüleri dönüştürülür.\nYoğunluğu gerektiğinde elle değiştirebilirsiniz.',
            10, MUTED, anchor='w', justify='left', wraplength=350)
        w['unit_hint'].grid(row=6, column=0, columnspan=2, sticky='ew', padx=10, pady=(12, 14))
        details = w['details']
        result = ctk.CTkFrame(details, fg_color=('#2F68AD', '#235E9E'), corner_radius=14)
        result.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        result.grid_columnconfigure(0, weight=1)
        w['result_title'] = self._label(result, 'TOPLAM AĞIRLIK', 11, '#DAEAFE', bold=True)
        w['result_title'].grid(row=0, column=0, sticky='ew', padx=16, pady=(16, 2))
        w['total'] = self._label(result, '—', 32, '#FFFFFF', bold=True)
        w['total'].grid(row=1, column=0, sticky='ew', padx=16, pady=2)
        w['context'] = self._label(result, '', 11, '#DAEAFE', wraplength=360)
        w['context'].grid(row=2, column=0, sticky='ew', padx=16, pady=(2, 16))
        metrics = self._weight_card(details)
        metrics.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        metrics.grid_columnconfigure((0, 1), weight=1, uniform='weight_metrics')
        for index, (key, title) in enumerate((('each', 'Bir adet'), ('per_m', 'Birim boy ağırlığı'),
                                             ('area', 'Kesit alanı'), ('volume', 'Toplam hacim'))):
            row, column = divmod(index, 2)
            self._label(metrics, title, 10, MUTED).grid(row=row*2, column=column,
                sticky='w', padx=14, pady=(10, 2))
            w[key] = self._label(metrics, '—', 17, bold=True, anchor='w')
            w[key].grid(row=row*2+1, column=column, sticky='ew', padx=14, pady=(0, 10))
        visual = self._weight_card(details)
        visual.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        visual.grid_columnconfigure(0, weight=1)
        w['shape_title'] = self._label(visual, '', 13, ACCENT, bold=True, anchor='w')
        w['shape_title'].grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 2))
        canvas = tk.Canvas(visual, width=1, height=300, highlightthickness=0, borderwidth=0)
        canvas.grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 8))
        w['canvas'] = canvas
        w['note'] = self._label(details, '', 11, MUTED, anchor='w', justify='left', wraplength=380)
        w['note'].grid(row=3, column=0, sticky='ew', padx=4, pady=(0, 12))
        self.status_label = self._label(self.workspace,
            'Ölçüleri değiştirdiğinizde ağırlık güncellenir.', 11, MUTED, anchor='w')
        self.status_label.grid(row=2, column=0, sticky='ew', padx=24, pady=(10, 12))
        for key, variable in self.weight_state.items():
            variable.trace_add('write', lambda *_, key=key: self._weight_changed(key) if self.mode == 'weight' else None)
        canvas.bind('<Configure>', lambda _: self._draw_weight_diagram() if self.mode == 'weight' else None)
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._update_weight_result()
        self._resize_pdf_area()

    def _select_weight_kind(self, kind):
        self.weight_state['kind'].set(kind)

    def _weight_changed(self, key):
        w, state = self.weight_widgets, self.weight_state
        if w['loading']:
            return
        w['loading'] = True
        try:
            if key == 'material' and state['material'].get() in MATERIALS:
                state['density'].set(str(MATERIALS[state['material'].get()]))
            if key == 'unit' and state['unit'].get() in UNITS:
                old, new = w['unit'], state['unit'].get()
                for field in LINEAR_FIELDS:
                    value = _number(state[field].get())
                    if value is not None:
                        state[field].set(f'{value*UNITS[old]/UNITS[new]:.12g}'.replace('.', ','))
                w['unit'] = new
        finally:
            w['loading'] = False
        self._update_weight_result()
        self._schedule_preferences()

    def _update_weight_fields(self):
        state, w = self.weight_state, self.weight_widgets
        kind, unit = state['kind'].get(), state['unit'].get()
        geometry = state['method'].get() == 'Ölçülerden'
        for frame in w['dim_frames'].values():
            frame.grid_remove()
        for index, key in enumerate(FIELDS.get(kind, ()) if geometry else ()):
            w['dim_frames'][key].grid(row=index//2, column=index % 2, sticky='ew', padx=8, pady=(8, 0))
            configure_changed(w[key+'_label'], text=f'{FIELD_LABELS[key]} ({unit})')
        if geometry:
            w['area_frame'].grid_remove()
        else:
            w['area_frame'].grid()
        configure_changed(w['length_label'], text=f'Boy / uzunluk ({unit})')
        configure_changed(w['shape_title'], text=kind)
        for item, tile in w['tiles'].items():
            selected = item == kind
            configure_changed(tile, fg_color=ACCENT_BG if selected else INPUT,
                              border_color=ACCENT if selected else BORDER)

    def _update_weight_result(self):
        state, w = self.weight_state, self.weight_widgets
        self._update_weight_fields()
        try:
            self.weight_result = r = calculate(**{key: value.get() for key, value in state.items()})
        except ValueError as error:
            self.weight_result = None
            configure_changed(w['result_title'], text='DEĞERLERİ KONTROL EDİN')
            configure_changed(w['total'], text='—')
            configure_changed(w['context'], text=str(error))
            configure_changed(w['note'], text='Geçerli ölçü, adet ve yoğunluk girildiğinde sonuç burada görünür.', text_color=AMBER)
            for key in ('each', 'per_m', 'area', 'volume'):
                configure_changed(w[key], text='—')
        else:
            configure_changed(w['result_title'], text='YAKLAŞIK TOPLAM AĞIRLIK' if r.approximate else 'TOPLAM AĞIRLIK')
            configure_changed(w['total'], text=f'{_fmt(r.total_mass_kg, 3 if r.total_mass_kg >= .001 else 6)} kg')
            configure_changed(w['context'], text=f'{r.count} adet · {r.material}\nYoğunluk: {_fmt(r.density, 0)} kg/m³')
            for key, text in dict(each=f'{_fmt(r.mass_kg)} kg', per_m=f'{_fmt(r.kg_per_m)} kg/m',
                                  area=f'{_fmt(r.area_mm2/100)} cm²', volume=f'{_fmt(r.total_volume_m3, 6)} m³').items():
                configure_changed(w[key], text=text)
            note = ('Keskin köşeli kesit yaklaşımı. Katalog alanı girerek gerçek kesit alanını kullanabilirsiniz.'
                    if r.approximate else 'Kesit alanı × boy × yoğunluk × adet ile hesaplandı.')
            if r.method == 'Katalog alanından':
                note = 'Girdiğiniz katalog kesit alanı kullanıldı. Görsel kesit şematiktir.'
            configure_changed(w['note'], text=note, text_color=MUTED)
        configure_changed(w['copy'], state='normal' if self.weight_result else 'disabled')
        self._draw_weight_diagram()

    def _draw_weight_diagram(self):
        w, state = self.weight_widgets, self.weight_state
        canvas = w['canvas']
        scale = self.workspace._get_widget_scaling()
        appearance = ctk.get_appearance_mode()
        dimensions = {}
        unit = UNITS.get(state['unit'].get(), 1)
        for key in LINEAR_FIELDS:
            value = _number(state[key].get())
            if value is not None and value > 0:
                scaled = value*unit
                if isfinite(scaled):
                    dimensions[key] = scaled
        key = (canvas.winfo_width(), canvas.winfo_height(), appearance, scale, self.weight_result,
               state['kind'].get(), tuple(sorted(dimensions.items())), state['method'].get())
        if w.get('draw_key') != key:
            draw(canvas, self.weight_result, appearance, scale, state['kind'].get(), dimensions)
            w['draw_key'] = key
        icon_key = (appearance, scale, state['kind'].get())
        if w.get('icon_key') != icon_key:
            dark = appearance == 'Dark'
            for kind, icon in w['icons'].items():
                selected = kind == state['kind'].get()
                paint, background = (ACCENT if selected else MUTED)[dark], (ACCENT_BG if selected else INPUT)[dark]
                icon.configure(width=round(34*scale), height=round(32*scale))
                draw_icon(icon, kind, paint, background, size=round(30*scale))
            w['icon_key'] = icon_key

    def _resize_weight_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.mode != 'weight':
            return
        w = self.weight_widgets
        scale = self.workspace._get_widget_scaling()
        for key in ('context', 'note'):
            configure_changed(w[key], wraplength=max(200, w['details'].winfo_width()/scale-40))
        configure_changed(w['unit_hint'], wraplength=max(190, w['form'].winfo_width()/scale-40))
        height = round(300*scale)
        if int(w['canvas'].cget('height')) != height:
            w['canvas'].configure(height=height)
        self._draw_weight_diagram()

    def _copy_weight_result(self):
        r = self.weight_result
        if r is None:
            return
        dimensions = ' · '.join(f'{FIELD_LABELS.get(key, key)}: {_fmt(value)} mm'
                                for key, value in r.dimensions_mm.items() if key != 'length')
        report = (f'Ağırlık hesabı · {r.kind}\nYöntem: {r.method}\n'
                  f'Malzeme: {r.material} · Yoğunluk: {_fmt(r.density)} kg/m³\n'
                  f'{dimensions}\nBoy: {_fmt(r.length_mm)} mm · Adet: {r.count}\n'
                  f'Kesit alanı: {_fmt(r.area_mm2/100)} cm²\n'
                  f'Birim boy: {_fmt(r.kg_per_m)} kg/m · Bir adet: {_fmt(r.mass_kg)} kg\n'
                  f'Toplam hacim: {_fmt(r.total_volume_m3, 6)} m³\n'
                  f'Toplam ağırlık: {_fmt(r.total_mass_kg)} kg\n'
                  f'{self.weight_widgets["note"].cget("text")}')
        self.clipboard_clear()
        self.clipboard_append(report)
        configure_changed(self.status_label, text='Ağırlık hesabı panoya kopyalandı.', text_color=ACCENT)
