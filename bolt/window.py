"""Live bolt calculation workspace, independent of SolidWorks."""

import tkinter as tk
import customtkinter as ctk

from bolt.diagram import draw, draw_dimensions
from bolt.rules import (THREADS, PROOF_STRESS, MODES, UNITS, UNIT_LABELS, SECTIONS, PLANES,
                        THREAD_SERIES, pitch_choices, thread_geometry,
                        SCOPE, calculate, fmt, force_text, number)
from gui.icons import set_window_icon
from gui.rendering import configure_changed
from gui.theme import (PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       SUCCESS, AMBER, RED, SECONDARY, HOVER, UI_FONT)


class BoltView:
    def _create_bolt_state(self, saved):
        defaults = dict(metric='M10', grade='8.8', mode='Çekme', tension='10', shear='4',
                        unit='kN', count='1', safety_factor='2', section='Dişli kesit', planes='Tek kesme',
                        thread_series='Kaba diş', pitch='1,5')
        self.bolt_state = {key: tk.StringVar(self, value=str(saved.get('bolt_'+key, value)))
                           for key, value in defaults.items()}
        if self.bolt_state['unit'].get() == 'kgf':
            self.bolt_state['unit'].set('kg')
        for key, choices in (('metric', THREADS), ('grade', PROOF_STRESS), ('mode', MODES),
                             ('unit', UNITS), ('section', SECTIONS), ('planes', PLANES),
                             ('thread_series', THREAD_SERIES)):
            if self.bolt_state[key].get() not in choices:
                self.bolt_state[key].set(defaults[key])
        metric, series = self.bolt_state['metric'].get(), self.bolt_state['thread_series'].get()
        try:
            _, pitch = thread_geometry(metric, series, self.bolt_state['pitch'].get())
        except ValueError:
            pitch = pitch_choices(metric, series)[0]
        self.bolt_state['pitch'].set(self._bolt_pitch_text(pitch))
        self.bolt_result = None
        self.bolt_widgets = {'unit': self.bolt_state['unit'].get(), 'loading': False}
        self.bolt_state['view'] = tk.StringVar(self, value='Ölçüler')

    @staticmethod
    def _bolt_pitch_text(pitch):
        return f'{pitch:g}'.replace('.', ',')

    def _sync_bolt_pitch(self):
        """Refresh available pitches without producing a second calculation."""
        state, control = self.bolt_state, self.bolt_widgets['pitch_input']
        metric, series = state['metric'].get(), state['thread_series'].get()
        try:
            choices = pitch_choices(metric, series)
        except ValueError:
            configure_changed(control, state='disabled')
            return
        try:
            _, pitch = thread_geometry(metric, series, state['pitch'].get())
        except ValueError:
            pitch = choices[0]
        configure_changed(control, values=[self._bolt_pitch_text(value) for value in choices],
                          state='disabled' if series == 'Kaba diş' else 'normal')
        selected = self._bolt_pitch_text(pitch)
        if state['pitch'].get() != selected:
            state['pitch'].set(selected)

    def _bolt_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)

    def _bolt_field(self, parent, key, title, row, column, choices=None):
        self._label(parent, title, 11, MUTED).grid(row=row, column=column, sticky='w', padx=8, pady=(12, 5))
        if choices:
            control = ctk.CTkOptionMenu(parent, variable=self.bolt_state[key], values=list(choices),
                height=36, width=1, fg_color=INPUT, button_color=INPUT, button_hover_color=HOVER,
                dropdown_fg_color=PANEL, dropdown_hover_color=HOVER, dropdown_text_color=TEXT,
                text_color=TEXT, font=(UI_FONT, 12), dropdown_font=(UI_FONT, 12), dynamic_resizing=False)
        else:
            control = ctk.CTkEntry(parent, textvariable=self.bolt_state[key], width=1, height=36,
                fg_color=INPUT, text_color=TEXT, border_color=BORDER, font=(UI_FONT, 14))
        control.grid(row=row+1, column=column, sticky='ew', padx=8)
        self.bolt_widgets[key+'_input'] = control

    def _build_bolt_workspace(self):
        self.workspace = self._workspace_shell()
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)
        w = self.bolt_widgets
        header, actions, _ = self._page_header('Cıvata hesabı',
            'Ölçüyü seçin, yükü girin, dayanımı görün.', 'MÜHENDİSLİK / BAĞLANTI ELEMANLARI', 'bolt')
        self._button(actions, 'Hesap yöntemi', self._show_bolt_method, width=124).pack()
        body = ctk.CTkFrame(self.workspace, fg_color='transparent')
        body.grid(row=1, column=0, sticky='nsew', padx=24)
        body.grid_columnconfigure((0, 1), weight=1, uniform='bolt_columns')
        body.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(body, width=1, fg_color='transparent', corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        w['form'] = left
        form = self._bolt_card(left)
        form.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        form.grid_columnconfigure((0, 1), weight=1, uniform='bolt_form')
        self._label(form, 'CIVATA PARAMETRELERİ', 13, ACCENT, bold=True).grid(row=0, column=0, columnspan=2, sticky='w', padx=14, pady=(16, 0))
        self._bolt_field(form, 'metric', 'Metrik ölçü', 1, 0, THREADS)
        self._bolt_field(form, 'grade', 'Kalite sınıfı', 1, 1, PROOF_STRESS)
        w['thread'] = self._label(form, '', 10, MUTED)
        w['thread'].grid(row=3, column=0, columnspan=2, sticky='w', padx=8, pady=(6, 0))
        self._bolt_field(form, 'thread_series', 'Diş türü', 4, 0, THREAD_SERIES)
        self._bolt_field(form, 'pitch', 'Diş adımı (mm)', 4, 1,
                         [self._bolt_pitch_text(value) for value in
                          pitch_choices(self.bolt_state['metric'].get(), self.bolt_state['thread_series'].get())])
        self._sync_bolt_pitch()
        self._bolt_field(form, 'mode', 'Yük türü', 6, 0, MODES)
        self._label(form, 'Yük birimi', 11, MUTED).grid(row=6, column=1, sticky='w', padx=8, pady=(12, 5))
        w['unit_input'] = ctk.CTkOptionMenu(form, values=list(UNIT_LABELS.values()),
            command=self._select_bolt_unit, height=36, width=1, fg_color=INPUT,
            button_color=INPUT, button_hover_color=HOVER, dropdown_fg_color=PANEL,
            dropdown_hover_color=HOVER, dropdown_text_color=TEXT, text_color=TEXT,
            font=(UI_FONT, 12), dynamic_resizing=False)
        w['unit_input'].grid(row=7, column=1, sticky='ew', padx=8)
        self._bolt_field(form, 'tension', 'Toplam çekme · Ft', 8, 0)
        self._bolt_field(form, 'shear', 'Toplam kesme · Fv', 8, 1)
        self._bolt_field(form, 'section', 'Kesme kesiti', 10, 0, SECTIONS)
        self._bolt_field(form, 'planes', 'Kesme düzlemi', 10, 1, PLANES)
        self._bolt_field(form, 'safety_factor', 'Emniyet katsayısı', 12, 0)
        self._bolt_field(form, 'count', 'Cıvata adedi', 12, 1)
        self._button(form, 'Yükü hesapla', self._update_bolt_result, primary=True).grid(row=14, column=0, columnspan=2, sticky='ew', padx=8, pady=(14, 0))
        w['unit_hint'] = self._label(form, '', 10, MUTED, justify='left', wraplength=245)
        w['unit_hint'].grid(row=15, column=0, columnspan=2, sticky='w', padx=8, pady=(10, 14))
        bank = self._bolt_card(left)
        bank.grid(row=1, column=0, sticky='ew')
        bank.grid_columnconfigure(0, weight=1)
        self._label(bank, 'TEKNİK BİLGİ', 13, ACCENT, bold=True).grid(row=0, column=0, sticky='w', padx=14, pady=(14, 8))
        w['bank'] = self._label(bank,
            'Kaba / ince diş · 4.6 / 5.6 / 8.8 / 10.9 / 12.9\n\n'
            'As = π/4 × (d − 0,938194P)²\n'
            'İzin verilen gerilme = Sp / emniyet katsayısı\n'
            'Birleşik yük: σeş = √(σ² + 3τ²)\n\n'
            'Cıvata gövdesi · Statik ön kontrol\n'
            'Eşit yük paylaşımı kabul edilir.\n'
            'Ön sıkma ve bağlantı plakaları ayrıca kontrol edilir.',
            11, MUTED, justify='left', anchor='w', wraplength=360)
        w['bank'].grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 14))
        details = ctk.CTkScrollableFrame(body, width=1, fg_color='transparent', corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        details.grid(row=0, column=1, sticky='nsew')
        details.grid_columnconfigure(0, weight=1)
        w['details'] = details
        banner = ctk.CTkFrame(details, fg_color=('#2F68AD', '#235E9E'), corner_radius=14)
        banner.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        banner.grid_columnconfigure(0, weight=1)
        w['capacity_title'] = self._label(banner, 'ÇEKME YÜK SINIRI', 10, '#DAEAFE', bold=True)
        w['capacity_title'].grid(row=0, column=0, sticky='ew', padx=16, pady=(14, 2))
        w['capacity_value'] = self._label(banner, '—', 29, '#FFFFFF', bold=True)
        w['capacity_value'].grid(row=1, column=0, sticky='ew', padx=16, pady=2)
        w['capacity_context'] = self._label(banner, '', 10, '#DAEAFE', wraplength=360)
        w['capacity_context'].grid(row=2, column=0, sticky='ew', padx=16, pady=(2, 14))
        result = self._bolt_card(details)
        result.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        result.grid_columnconfigure(0, weight=1)
        w['result_card'] = result
        w['verdict'] = self._label(result, '', 20, bold=True, anchor='w')
        w['verdict'].grid(row=1, column=0, sticky='ew', padx=18, pady=(10, 2))
        w['summary'] = self._label(result, '', 11, MUTED, anchor='w', justify='left', wraplength=390)
        w['summary'].grid(row=2, column=0, sticky='ew', padx=18, pady=(0, 6))
        w['progress'] = ctk.CTkProgressBar(result, height=7, fg_color=INPUT, progress_color=ACCENT)
        w['progress'].grid(row=3, column=0, sticky='ew', padx=18)
        w['usage'] = self._label(result, '', 11, MUTED, anchor='w', justify='left', wraplength=390)
        w['usage'].grid(row=4, column=0, sticky='ew', padx=18, pady=(4, 8))
        visual = self._bolt_card(details)
        visual.grid(row=3, column=0, sticky='ew', pady=(0, 12))
        visual.grid_columnconfigure(0, weight=1)
        views = ctk.CTkSegmentedButton(visual, variable=self.bolt_state['view'], values=['Ölçüler', 'Yük gösterimi'],
            height=30, fg_color=INPUT, selected_color=ACCENT_BG, selected_hover_color=HOVER,
            unselected_color=INPUT, unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 11))
        views.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 0))
        w['view_input'] = views
        canvas = tk.Canvas(visual, width=1, height=260, highlightthickness=0, borderwidth=0)
        canvas.grid(row=1, column=0, sticky='ew', padx=8, pady=8)
        w['canvas'] = canvas
        metrics = self._bolt_card(details)
        metrics.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        metrics.grid_columnconfigure((0, 1), weight=1, uniform='bolt_metrics')
        for index, (key, title) in enumerate((('stress', 'Eşdeğer gerilme'), ('allowable', 'İzin verilen gerilme'),
                                            ('factor', 'Mevcut emniyet'), ('area', 'Çekme alanı · As'))):
            row, col = divmod(index, 2)
            self._label(metrics, title, 10, MUTED).grid(row=row*2, column=col, sticky='w', padx=16, pady=(8, 0))
            w[key] = self._label(metrics, '—', 18, bold=True)
            w[key].grid(row=row*2+1, column=col, sticky='w', padx=16, pady=(0, 8))
        w['capacity'] = self._label(details, '', 11, MUTED, justify='left', anchor='w', wraplength=400)
        w['capacity'].grid(row=4, column=0, sticky='ew', padx=4, pady=(0, 10))
        w['scope'] = self._label(details,
            'Ön kontrol · Ön sıkma, diş sıyırması ve bağlantı plakaları ayrıca kontrol edilmelidir.',
            11, MUTED, justify='left', anchor='w', wraplength=400)
        w['scope'].grid(row=5, column=0, sticky='ew', padx=4, pady=(0, 12))
        w['copy'] = self._button(details, 'Hesabı kopyala', self._copy_bolt_result, icon='copy', width=150)
        w['copy'].grid(row=6, column=0, sticky='w', pady=(0, 10))
        self.status_label = self._label(self.workspace, 'Değerleri değiştirdiğinizde sonuç güncellenir.', 11, MUTED, anchor='w')
        self.status_label.grid(row=2, column=0, sticky='ew', padx=24, pady=(10, 12))
        for key, variable in self.bolt_state.items():
            variable.trace_add('write', lambda *_, key=key: self._bolt_changed(key) if self.mode == 'bolt' else None)
        canvas.bind('<Configure>', lambda _: self._draw_bolt_diagram() if self.mode == 'bolt' else None)
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._update_bolt_result()
        self._resize_pdf_area()

    def _select_bolt_unit(self, label):
        unit = next(key for key, value in UNIT_LABELS.items() if value == label)
        self.bolt_state['unit'].set(unit)

    def _bolt_changed(self, key):
        w = self.bolt_widgets
        if w['loading']:
            return
        if key in ('metric', 'thread_series'):
            w['loading'] = True
            try:
                self._sync_bolt_pitch()
            finally:
                w['loading'] = False
        if key == 'unit':
            old, new = w['unit'], self.bolt_state['unit'].get()
            if new in UNITS:
                w['loading'] = True
                try:
                    for field in ('tension', 'shear'):
                        try:
                            value = number(self.bolt_state[field].get(), 'Yük')*UNITS[old]/UNITS[new]
                            self.bolt_state[field].set(f'{value:.12g}'.replace('.', ','))
                        except ValueError:
                            pass
                finally:
                    w['loading'] = False
                w['unit'] = new
        self._update_bolt_result()
        self._schedule_preferences()

    def _update_bolt_result(self):
        w, state = self.bolt_widgets, self.bolt_state
        unit = state['unit'].get()
        w['unit_input'].set(UNIT_LABELS.get(unit, 'kg yük'))
        configure_changed(w['unit_hint'], text=(
            'kg yük: girilen kütlenin ağırlığı hesaplanır.\n1 kg yük = 9,80665 N (standart yerçekimi).'
            if unit in ('kg', 'kgf') else 'Birim değişince girilen yük dönüştürülür.\n1 kN = 1.000 N'))
        for key in ('shear', 'section', 'planes'):
            configure_changed(w[key+'_input'], state='disabled' if state['mode'].get() == 'Çekme' else 'normal')
        configure_changed(w['tension_input'], state='disabled' if state['mode'].get() == 'Kesme' else 'normal')
        for key, inactive_mode in (('tension', 'Kesme'), ('shear', 'Çekme')):
            configure_changed(w[key+'_input'], text_color=MUTED if state['mode'].get() == inactive_mode else TEXT)
        try:
            diameter, pitch = thread_geometry(state['metric'].get(), state['thread_series'].get(), state['pitch'].get())
        except ValueError:
            configure_changed(w['thread'], text='Diş türünü ve adımını kontrol edin.')
        else:
            configure_changed(w['thread'], text=f'Ø {diameter} mm · {state["thread_series"].get()} · Adım {fmt(pitch)} mm')
        try:
            self.bolt_result = r = calculate(**{key: value.get() for key, value in state.items() if key != 'view'})
        except ValueError as error:
            self.bolt_result = None
            verdict, summary, color, usage = 'Değerleri kontrol edin', str(error), AMBER, 'Hesaplanamadı'
            for key in ('stress', 'allowable', 'factor', 'area'):
                configure_changed(w[key], text='—')
            configure_changed(w['capacity'], text='Geçerli değerler girildiğinde kapasite burada görünür.')
            configure_changed(w['capacity_value'], text='—')
            configure_changed(w['capacity_context'], text='Geçerli yük ve güvenlik değerlerini girin.')
        else:
            verdict = 'Yük yok' if not r.loaded else 'Güvenli' if r.safe else 'Güvensiz'
            color = AMBER if not r.loaded else SUCCESS if r.safe else RED
            summary = ('Cıvata gövdesini kontrol etmek için yük girin.' if not r.loaded else
                       f'Cıvata gövdesi: {fmt(r.safety_factor)} emniyet hedefi ' + ('sağlanıyor.' if r.safe else 'sağlanmıyor.'))
            usage = (f'Kullanım: %{fmt(r.utilization*100, 1)} · '
                     f'Yük marjı: {self._bolt_margin_text(r)}\n{self._bolt_minimum_text(r)}')
            for key, value in dict(stress=fmt(r.equivalent_stress)+' MPa', allowable=fmt(r.allowable_stress)+' MPa',
                                    factor=fmt(r.available_factor) if r.available_factor is not None else '—',
                                    area=fmt(r.tensile_area)+' mm²').items():
                configure_changed(w[key], text=value)
            configure_changed(w['capacity'], text=self._bolt_capacity_text(r))
            if r.mode == 'Birleşik yük':
                configure_changed(w['capacity_title'], text='BİRLEŞİK YÜK · KAPASİTE KULLANIMI')
                configure_changed(w['capacity_value'], text=f'%{fmt(r.utilization*100, 1)}')
            else:
                configure_changed(w['capacity_title'], text=f'{r.mode.upper()} YÜK SINIRI')
                capacity = r.tension_capacity_n if r.mode == 'Çekme' else r.shear_capacity_n
                configure_changed(w['capacity_value'], text=force_text(capacity, r.unit))
            configure_changed(w['capacity_context'], text=f'{r.count} cıvata · {r.mode} · Emniyet {fmt(r.safety_factor, 1)}')
        configure_changed(w['verdict'], text=verdict, text_color=color)
        configure_changed(w['result_card'], border_color=color)
        configure_changed(w['summary'], text=summary)
        configure_changed(w['usage'], text=usage)
        configure_changed(w['progress'], progress_color=color)
        w['progress'].set(min(1., self.bolt_result.utilization) if self.bolt_result else 0.)
        configure_changed(w['copy'], state='normal' if self.bolt_result else 'disabled')
        self._draw_bolt_diagram()

    @staticmethod
    def _bolt_margin_text(result):
        margin = result.safety_margin
        if margin is None:
            return 'yük yok'
        sign = '+' if margin > 0 else '-' if margin < 0 else ''
        return sign+'%'+fmt(abs(margin)*100, 1)

    @staticmethod
    def _bolt_minimum_text(result):
        minimum = result.minimum_count
        if minimum is None:
            return 'Minimum adet: yük girildiğinde hesaplanır.'
        if minimum > 1000:
            return 'Gerekli adet, 1000 adet sınırını aşıyor.'
        return f'Eşit yük paylaşımıyla gerekli en az: {minimum} cıvata.'

    @staticmethod
    def _bolt_capacity_text(result):
        r = result
        text = (f'{r.count} cıvata için tek başına yük sınırları:\n'
                f'Çekme: {force_text(r.tension_capacity_n, r.unit)}\n'
                f'Kesme: {force_text(r.shear_capacity_n, r.unit)}\n'
                'Birleşik yükte bu iki sınır aynı anda kullanılamaz.')
        if r.mode == 'Birleşik yük':
            tension = r.tension_limit_with_shear_n
            shear = r.shear_limit_with_tension_n
            text += (f'\n\nMevcut kesme ({force_text(r.shear_n, r.unit)}) sabitken çekme sınırı: '
                     + (force_text(tension, r.unit) if tension is not None else
                        'yok; kesme tek başına sınırı aşıyor.')
                     + f'\nMevcut çekme ({force_text(r.tension_n, r.unit)}) sabitken kesme sınırı: '
                     + (force_text(shear, r.unit) if shear is not None else
                        'yok; çekme tek başına sınırı aşıyor.')
                     + '\nBunlar toplam yük sınırıdır; eklenebilecek yük değildir.')
        return text

    def _draw_bolt_diagram(self):
        canvas = self.bolt_widgets['canvas']
        scale = self.workspace._get_widget_scaling()
        view = self.bolt_state['view'].get()
        key = (canvas.winfo_width(), canvas.winfo_height(), ctk.get_appearance_mode(), scale, self.bolt_result,
               view, self.bolt_state['metric'].get(), self.bolt_state['grade'].get(),
               self.bolt_state['thread_series'].get(), self.bolt_state['pitch'].get())
        if self.bolt_widgets.get('draw_key') != key:
            if view == 'Ölçüler':
                try:
                    thread_geometry(self.bolt_state['metric'].get(), self.bolt_state['thread_series'].get(),
                                    self.bolt_state['pitch'].get())
                except ValueError:
                    draw(canvas, None, ctk.get_appearance_mode(), scale)
                else:
                    draw_dimensions(canvas, self.bolt_result, ctk.get_appearance_mode(), scale,
                                    self.bolt_state['metric'].get(), self.bolt_state['grade'].get(),
                                    self.bolt_state['thread_series'].get(), self.bolt_state['pitch'].get())
            else:
                draw(canvas, self.bolt_result, ctk.get_appearance_mode(), scale)
            self.bolt_widgets['draw_key'] = key

    def _resize_bolt_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.mode != 'bolt':
            return
        w = self.bolt_widgets
        scale = self.workspace._get_widget_scaling()
        width = max(220, w['details'].winfo_width()/scale-38)
        for key in ('summary', 'usage', 'capacity', 'scope', 'capacity_context'):
            configure_changed(w[key], wraplength=width)
        configure_changed(w['bank'], wraplength=max(190, w['form'].winfo_width()/scale-38))
        height = round(260*scale)
        if int(w['canvas'].cget('height')) != height:
            w['canvas'].configure(height=height)
        self._configure_table_style()
        self._draw_bolt_diagram()

    def _copy_bolt_result(self):
        r = self.bolt_result
        if r is None:
            return
        text = (f'Cıvata hesabı · {r.metric} × {fmt(r.pitch)} · {r.thread_series} · {r.grade}\n'
                f'{r.mode} · {r.count} cıvata · {r.section} · {r.planes} kesme düzlemi\n'
                f'Seçili birim: {UNIT_LABELS[r.unit]}\n'
                f'Çekme: {force_text(r.tension_n, r.unit)} · Kesme: {force_text(r.shear_n, r.unit)}\n'
                f'Toplam Ft = {fmt(r.tension_n)} N · Toplam Fv = {fmt(r.shear_n)} N\n'
                f'As = {fmt(r.tensile_area)} mm² · Akesme = {fmt(r.shear_area)} mm²\n'
                f'σ = {fmt(r.tensile_stress)} MPa · τ = {fmt(r.shear_stress)} MPa\n'
                f'σeş = {fmt(r.equivalent_stress)} MPa · Sp = {fmt(r.proof_stress)} MPa\n'
                + ('İnce dişte mevcut muhafazakâr Sp sınırı kullanılır.\n' if r.thread_series == 'İnce diş' else '')
                +
                f'Emniyet hedefi = {fmt(r.safety_factor)} · İzin verilen = {fmt(r.allowable_stress)} MPa\n'
                f'Sonuç: {self.bolt_widgets["verdict"].cget("text")} · Kullanım %{fmt(r.utilization*100, 1)}\n'
                f'Seçili emniyet hedefine göre yük marjı = {self._bolt_margin_text(r)}\n'
                f'{self._bolt_minimum_text(r)}\n'
                'Minimum adet cıvata gövdesi, seçili emniyet ve eşit yük paylaşımı içindir; '
                'adet otomatik değiştirilmez.\n'
                f'{self._bolt_capacity_text(r)}\n'
                f'kg yük dönüşümü: standart yerçekimi g = 9,80665 m/s².\n\n{SCOPE}')
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_label.configure(text='Hesap ve varsayımlar panoya kopyalandı.', text_color=SUCCESS)

    def _show_bolt_method(self):
        self._close_detail()
        window = ctk.CTkToplevel(self)
        set_window_icon(window)
        self.detail_window = window
        window.title('Cıvata hesabı · Yöntem ve kapsam')
        window.geometry('720x560')
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        self._label(window, 'Statik cıvata dayanımı', 22, bold=True).grid(row=0, column=0, sticky='w', padx=24, pady=20)
        box = ctk.CTkTextbox(window, fg_color=INPUT, text_color=TEXT, font=(UI_FONT, 13), wrap='word')
        box.grid(row=1, column=0, sticky='nsew', padx=24)
        box.insert('1.0', 'Ölçüler: ISO metrik kaba ve ince diş, M3–M39. '
            'İnce dişte çap için sunulan diş adımını seçin; kaba dişte standart adım sabittir. '
            'Alanlar ve yaklaşık kılavuz deliği seçili adımla hesaplanır. '
            'Malzeme sınıfları: ISO 898-1 çelik cıvatalar.\n\n'
            'As = π/4 × (d − 0,938194 × P)²\n'
            'Dişli kesmede Ak = π/4 × (d − 1,226869 × P)²; dişsiz gövdede Ak = πd²/4.\n'
            'σ = Ft / (adet × As)\nτ = Fv / (adet × kesme düzlemi × Ak)\n'
            'von Mises eşdeğer gerilmesi: σeş = √(σ² + 3τ²)\n'
            'İzin verilen gerilme = Sp / emniyet katsayısı\n'
            'Güvenli koşulu: σeş ≤ izin verilen gerilme.\n\n'
            'Yük marjı = 1 / kullanım − 1. Pozitif marj, kuvvetlerin aynı oranda '
            'artırılmasıyla seçili sınırın ne kadar uzakta olduğunu gösterir. '
            'Yük yoksa marj verilmez.\n'
            'Gerekli en az cıvata adedi eşit yük paylaşımına göre hesaplanır; '
            'girişteki adet otomatik değiştirilmez.\n'
            'Birleşik yük sınırlarında diğer kuvvet sabit tutulur. Gösterilen değer '
            'toplam kuvvet sınırıdır; eklenebilecek yük değildir. Diğer kuvvet tek başına '
            'sınırı aşıyorsa geçerli sınır yoktur.\n\n'
            'Hesapta kullanılan muhafazakâr deney yükü gerilmesi Sp, kalite sınıfı ve nominal çapa göre belirlenir; '
            'hesapta kullanılan Sp değeri kopyalanan raporda gösterilir. Sp kopma dayanımı değildir. '
            'İnce dişte de mevcut muhafazakâr Sp sınırları korunur. '
            'Bu sınırla von Mises karşılaştırması, uygulamanın ihtiyatlı ön kontrol yöntemidir; '
            'ISO 898-1 bir bağlantı tasarım standardı değildir.\n\n'
            'Varsayılan emniyet katsayısı 2’dir; uygulamanızın gerektirdiği katsayıyı seçin. '
            'kg yük seçiminde girilen kütle standart yerçekimiyle kuvvete çevrilir: F = m × 9,80665. '
            'Newton (N) seçiminde değer doğrudan kuvvettir; 1 kN = 1.000 N. '
            'Çift kesmede iki kesme düzleminin eşit yük taşıdığı kabul edilir. '
            'Kapasiteler yalnız çekme veya yalnız kesme için ayrı ayrı verilir.\n\n'+SCOPE)
        box.configure(state='disabled')
        self._button(window, 'Kapat', self._close_detail, width=100).grid(row=2, column=0, sticky='e', padx=24, pady=16)
        window.protocol('WM_DELETE_WINDOW', self._close_detail)
        window.bind('<Escape>', lambda _: self._close_detail())
