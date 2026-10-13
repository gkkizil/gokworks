"""Live bolt calculation workspace, independent of SolidWorks."""

import tkinter as tk
import customtkinter as ctk

from bolt.diagram import draw
from bolt.rules import (THREADS, PROOF_STRESS, MODES, UNITS, UNIT_LABELS, SECTIONS, PLANES,
                        SCOPE, calculate, fmt, force_text, number)
from gui.icons import set_window_icon
from gui.rendering import configure_changed
from gui.theme import (PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       GREEN, AMBER, RED, SECONDARY, HOVER, UI_FONT)


class BoltView:
    def _create_bolt_state(self, saved):
        defaults = dict(metric='M10', grade='8.8', mode='Çekme', tension='10', shear='4',
                        unit='kN', count='1', safety_factor='2', section='Dişli kesit', planes='Tek kesme')
        self.bolt_state = {key: tk.StringVar(self, value=str(saved.get('bolt_'+key, value)))
                           for key, value in defaults.items()}
        if self.bolt_state['unit'].get() == 'kgf':
            self.bolt_state['unit'].set('kg')
        for key, choices in (('metric', THREADS), ('grade', PROOF_STRESS), ('mode', MODES),
                             ('unit', UNITS), ('section', SECTIONS), ('planes', PLANES)):
            if self.bolt_state[key].get() not in choices:
                self.bolt_state[key].set(defaults[key])
        self.bolt_result = None
        self.bolt_widgets = {'unit': self.bolt_state['unit'].get(), 'loading': False}

    def _bolt_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)

    def _bolt_field(self, parent, key, title, row, column, choices=None):
        self._label(parent, title, 11, MUTED).grid(row=row, column=column, sticky='w', padx=8, pady=(12, 5))
        if choices:
            control = ctk.CTkOptionMenu(parent, variable=self.bolt_state[key], values=list(choices),
                height=36, width=110, fg_color=INPUT, button_color=INPUT, button_hover_color=HOVER,
                dropdown_fg_color=PANEL, dropdown_hover_color=HOVER, dropdown_text_color=TEXT,
                text_color=TEXT, font=(UI_FONT, 12), dropdown_font=(UI_FONT, 12), dynamic_resizing=False)
        else:
            control = ctk.CTkEntry(parent, textvariable=self.bolt_state[key], width=110, height=36,
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
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        form = ctk.CTkScrollableFrame(body, width=270, fg_color=PANEL, corner_radius=14,
            border_width=1, border_color=BORDER, scrollbar_button_color=BORDER)
        form.grid(row=0, column=0, sticky='ns', padx=(0, 14))
        form.grid_columnconfigure((0, 1), weight=1, uniform='bolt_form')
        w['form'] = form
        self._label(form, '01   Cıvata seçimi', 14, bold=True).grid(row=0, column=0, columnspan=2, sticky='w', padx=8, pady=(12, 0))
        self._bolt_field(form, 'metric', 'Metrik ölçü', 1, 0, THREADS)
        self._bolt_field(form, 'grade', 'Kalite sınıfı', 1, 1, PROOF_STRESS)
        w['thread'] = self._label(form, '', 10, MUTED)
        w['thread'].grid(row=3, column=0, columnspan=2, sticky='w', padx=8, pady=(6, 4))
        self._label(form, '02   Yük durumu', 14, bold=True).grid(row=4, column=0, columnspan=2, sticky='w', padx=8, pady=(16, 8))
        modes = ctk.CTkSegmentedButton(form, variable=self.bolt_state['mode'], values=list(MODES),
            height=36, fg_color=INPUT, selected_color=ACCENT_BG, selected_hover_color=HOVER,
            unselected_color=INPUT, unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 11))
        modes.grid(row=5, column=0, columnspan=2, sticky='ew', padx=8)
        self._label(form, 'Yük birimi', 11, MUTED).grid(row=6, column=0, columnspan=2, sticky='w', padx=8, pady=(12, 5))
        w['unit_input'] = ctk.CTkSegmentedButton(form, values=list(UNIT_LABELS.values()),
            command=self._select_bolt_unit, height=36, fg_color=INPUT,
            selected_color=ACCENT_BG, selected_hover_color=HOVER, unselected_color=INPUT,
            unselected_hover_color=HOVER, text_color=TEXT, font=(UI_FONT, 12))
        w['unit_input'].grid(row=7, column=0, columnspan=2, sticky='ew', padx=8)
        self._bolt_field(form, 'tension', 'Toplam çekme · Ft', 8, 0)
        self._bolt_field(form, 'shear', 'Toplam kesme · Fv', 8, 1)
        self._bolt_field(form, 'section', 'Kesme kesiti', 10, 0, SECTIONS)
        self._bolt_field(form, 'planes', 'Kesme düzlemi', 10, 1, PLANES)
        self._label(form, '03   Güvenlik hedefi', 14, bold=True).grid(row=12, column=0, columnspan=2, sticky='w', padx=8, pady=(20, 0))
        self._bolt_field(form, 'safety_factor', 'Emniyet katsayısı', 13, 0)
        self._bolt_field(form, 'count', 'Cıvata adedi', 13, 1)
        w['unit_hint'] = self._label(form, '', 10, MUTED, justify='left', wraplength=245)
        w['unit_hint'].grid(row=15, column=0, columnspan=2, sticky='w', padx=8, pady=(12, 6))
        self._label(form, 'Emniyet varsayılanı: 2 · Eşit yük paylaşımı\nKaba diş · karbon / alaşımlı çelik', 10, MUTED,
                    justify='left').grid(row=16, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 14))
        details = ctk.CTkScrollableFrame(body, fg_color='transparent', corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED)
        details.grid(row=0, column=1, sticky='nsew')
        details.grid_columnconfigure(0, weight=1)
        w['details'] = details
        result = self._bolt_card(details)
        result.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        result.grid_columnconfigure(0, weight=1)
        w['result_card'] = result
        self._label(result, 'CIVATA GÖVDESİ · STATİK ÖN KONTROL', 10, MUTED, True).grid(row=0, column=0, sticky='w', padx=18, pady=(14, 0))
        w['verdict'] = self._label(result, '', 26, bold=True, anchor='w')
        w['verdict'].grid(row=1, column=0, sticky='ew', padx=18, pady=(5, 2))
        w['summary'] = self._label(result, '', 11, MUTED, anchor='w', justify='left', wraplength=390)
        w['summary'].grid(row=2, column=0, sticky='ew', padx=18, pady=(0, 10))
        w['progress'] = ctk.CTkProgressBar(result, height=7, fg_color=INPUT, progress_color=ACCENT)
        w['progress'].grid(row=3, column=0, sticky='ew', padx=18)
        w['usage'] = self._label(result, '', 11, MUTED, anchor='w')
        w['usage'].grid(row=4, column=0, sticky='ew', padx=18, pady=(6, 14))
        visual = self._bolt_card(details)
        visual.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        visual.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(visual, width=1, height=230, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        w['canvas'] = canvas
        metrics = self._bolt_card(details)
        metrics.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        metrics.grid_columnconfigure((0, 1), weight=1, uniform='bolt_metrics')
        for index, (key, title) in enumerate((('stress', 'Eşdeğer gerilme'), ('allowable', 'İzin verilen gerilme'),
                                            ('factor', 'Mevcut emniyet'), ('area', 'Çekme alanı · As'))):
            row, col = divmod(index, 2)
            self._label(metrics, title, 10, MUTED).grid(row=row*2, column=col, sticky='w', padx=16, pady=(12, 2))
            w[key] = self._label(metrics, '—', 18, bold=True)
            w[key].grid(row=row*2+1, column=col, sticky='w', padx=16, pady=(0, 12))
        w['capacity'] = self._label(details, '', 11, MUTED, justify='left', anchor='w', wraplength=400)
        w['capacity'].grid(row=3, column=0, sticky='ew', padx=4, pady=(0, 10))
        w['scope'] = self._label(details,
            'Ön kontrol · Ön sıkma, diş sıyırması ve bağlantı plakaları ayrıca kontrol edilmelidir.',
            11, MUTED, justify='left', anchor='w', wraplength=400)
        w['scope'].grid(row=4, column=0, sticky='ew', padx=4, pady=(0, 12))
        w['copy'] = self._button(details, 'Hesabı kopyala', self._copy_bolt_result, icon='copy', width=150)
        w['copy'].grid(row=5, column=0, sticky='w', pady=(0, 10))
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
        diameter, pitch = THREADS[state['metric'].get()]
        configure_changed(w['thread'], text=f'Ø {diameter} mm · Adım {fmt(pitch)} mm')
        try:
            self.bolt_result = r = calculate(**{key: value.get() for key, value in state.items()})
        except ValueError as error:
            self.bolt_result = None
            verdict, summary, color, usage = 'Değerleri kontrol edin', str(error), AMBER, 'Hesaplanamadı'
            for key in ('stress', 'allowable', 'factor', 'area'):
                configure_changed(w[key], text='—')
            configure_changed(w['capacity'], text='Geçerli değerler girildiğinde kapasite burada görünür.')
        else:
            verdict = 'Yük yok' if not r.loaded else 'Güvenli' if r.safe else 'Güvensiz'
            color = AMBER if not r.loaded else GREEN if r.safe else RED
            summary = ('Bir yük girerek dayanımı kontrol edin.' if not r.loaded else
                       f'Seçilen {fmt(r.safety_factor)} emniyet hedefi ' + ('sağlanıyor.' if r.safe else 'sağlanmıyor.'))
            usage = f'Kapasite kullanımı: %{fmt(r.utilization*100, 1)}'
            for key, value in dict(stress=fmt(r.equivalent_stress)+' MPa', allowable=fmt(r.allowable_stress)+' MPa',
                                    factor=fmt(r.available_factor) if r.available_factor is not None else '—',
                                    area=fmt(r.tensile_area)+' mm²').items():
                configure_changed(w[key], text=value)
            configure_changed(w['capacity'], text=(
                f'{r.count} cıvata için tek başına yük sınırları:\n'
                f'Çekme: {force_text(r.tension_capacity_n, r.unit)}\n'
                f'Kesme: {force_text(r.shear_capacity_n, r.unit)}\n'
                'Birleşik yükte bu iki sınır aynı anda kullanılamaz.'))
        configure_changed(w['verdict'], text=verdict, text_color=color)
        configure_changed(w['result_card'], border_color=color)
        configure_changed(w['summary'], text=summary)
        configure_changed(w['usage'], text=usage)
        configure_changed(w['progress'], progress_color=color)
        w['progress'].set(min(1., self.bolt_result.utilization) if self.bolt_result else 0.)
        configure_changed(w['copy'], state='normal' if self.bolt_result else 'disabled')
        self._draw_bolt_diagram()

    def _draw_bolt_diagram(self):
        canvas = self.bolt_widgets['canvas']
        scale = self.workspace._get_widget_scaling()
        key = (canvas.winfo_width(), canvas.winfo_height(), ctk.get_appearance_mode(), scale, self.bolt_result)
        if self.bolt_widgets.get('draw_key') != key:
            draw(canvas, self.bolt_result, ctk.get_appearance_mode(), scale)
            self.bolt_widgets['draw_key'] = key

    def _resize_bolt_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.mode != 'bolt':
            return
        w = self.bolt_widgets
        scale = self.workspace._get_widget_scaling()
        width = max(220, w['details'].winfo_width()/scale-38)
        for key in ('summary', 'capacity', 'scope'):
            configure_changed(w[key], wraplength=width)
        height = round(230*scale)
        if int(w['canvas'].cget('height')) != height:
            w['canvas'].configure(height=height)
        self._configure_table_style()
        self._draw_bolt_diagram()

    def _copy_bolt_result(self):
        r = self.bolt_result
        if r is None:
            return
        text = (f'Cıvata hesabı · {r.metric} × {fmt(r.pitch)} · {r.grade}\n'
                f'{r.mode} · {r.count} cıvata · {r.section} · {r.planes} kesme düzlemi\n'
                f'Seçili birim: {UNIT_LABELS[r.unit]}\n'
                f'Çekme: {force_text(r.tension_n, r.unit)} · Kesme: {force_text(r.shear_n, r.unit)}\n'
                f'Toplam Ft = {fmt(r.tension_n)} N · Toplam Fv = {fmt(r.shear_n)} N\n'
                f'As = {fmt(r.tensile_area)} mm² · Akesme = {fmt(r.shear_area)} mm²\n'
                f'σ = {fmt(r.tensile_stress)} MPa · τ = {fmt(r.shear_stress)} MPa\n'
                f'σeş = {fmt(r.equivalent_stress)} MPa · Sp = {fmt(r.proof_stress)} MPa\n'
                f'Emniyet hedefi = {fmt(r.safety_factor)} · İzin verilen = {fmt(r.allowable_stress)} MPa\n'
                f'Sonuç: {self.bolt_widgets["verdict"].cget("text")} · Kullanım %{fmt(r.utilization*100, 1)}\n'
                f'kg yük dönüşümü: standart yerçekimi g = 9,80665 m/s².\n\n{SCOPE}')
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_label.configure(text='Hesap ve varsayımlar panoya kopyalandı.', text_color=GREEN)

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
        box.insert('1.0', 'Ölçüler: ISO metrik kaba diş, M3–M39. Malzeme sınıfları: ISO 898-1 çelik cıvatalar.\n\n'
            'As = π/4 × (d − 0,938194 × P)²\n'
            'Dişli kesmede Ak = π/4 × (d − 1,226869 × P)²; dişsiz gövdede Ak = πd²/4.\n'
            'σ = Ft / (adet × As)\nτ = Fv / (adet × kesme düzlemi × Ak)\n'
            'von Mises eşdeğer gerilmesi: σeş = √(σ² + 3τ²)\n'
            'İzin verilen gerilme = Sp / emniyet katsayısı\n'
            'Güvenli koşulu: σeş ≤ izin verilen gerilme.\n\n'
            'Deney yükü gerilmesi Sp (MPa): 4.6: 225; 5.6: 280; 8.8: 580 (M16 ve altı), '
            '600 (M16 üstü); 10.9: 830; 12.9: 970. Sp kopma dayanımı değildir. '
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
