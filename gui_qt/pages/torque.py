"""Small local torque calculator using the existing Qt cards/forms/theme."""

from math import isfinite

from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtWidgets import QWidget, QVBoxLayout, QBoxLayout, QApplication

from bolt.rules import THREADS, STANDARD_FINE_PITCHES
from bolt_torque import rules as r
from ..components import BasePage, ValueForm, Disclosure, card, label, scroll, button
from ..diagrams import EngineeringDiagram
from ..torque_diagram import draw_section


def fmt(value, digits=2):
    if value and (abs(value) < .01 or abs(value) >= 1e7):
        return f'{value:.4g}'.replace('.', ',')
    return f'{value:.{digits if abs(value) >= 1 or not value else 4}f}'.replace('.', ',')


class TorquePage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Hızlı Cıvata Tork Hesabı',
                         'Çapı, kaliteyi ve bağlantı koşulunu seçin; tahmini sıkma torkunu görün.')
        self.result = None
        self.loading = False
        self.compact = None
        self.copy_button = self.action('Sonucu kopyala', self.copy_result)
        self.copy_button.setEnabled(False)
        self.compact_result=label('—','section');self.compact_result.hide()
        self.compact_result.setAccessibleName('Tahmini tork ve ön yük');self.layout.addWidget(self.compact_result)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        self.columns = QBoxLayout(QBoxLayout.LeftToRight)
        body.addLayout(self.columns)
        body.addStretch()

        self.input_card, inputs = card('Cıvata ve sıkma koşulları')
        self.form = f = ValueForm(self.settings, 'torque_')
        f.combo('metric', 'Cıvata ölçüsü', r.METRICS, 'M10')
        f.combo('thread_series', 'Diş türü', r.THREAD_SERIES)
        f.combo('pitch', 'Diş adımı · mm', ('1,5',))
        self.pitch_hint = label('', 'muted')
        f.form.addRow(self.pitch_hint)
        f.combo('grade', 'Kalite sınıfı', r.GRADES, '8.8')
        f.combo('condition', 'Bağlantı koşulu', r.CONDITIONS)
        f.text('k', 'K tork katsayısı', str(r.DEFAULT_K[f.value('condition')]).replace('.', ','))
        f.text('preload_percent', 'Hedef ön yük · %', '70')
        # Let WrapLongRows move the label above the field rather than squeeze
        # numeric input on platforms with wider font metrics.
        for field in f.fields.values(): field.setMinimumWidth(112)
        inputs.addWidget(f)
        self.k_hint = label('', 'muted')
        inputs.addWidget(self.k_hint)
        self.reset_k_button = button('Varsayılan K’yı kullan', self.reset_k)
        inputs.addWidget(self.reset_k_button)
        assumptions = label(r.K_ASSUMPTION+'\n\nBağlantı koşulunu değiştirince K, o koşulun varsayılanına döner. '
                            'Ardından K’yı elle düzenleyebilirsiniz.','muted')
        self.assumptions_section = Disclosure('K katsayısı hakkında',assumptions)
        inputs.addWidget(self.assumptions_section)

        self.output_card, output = card('Tahmini Sıkma Torku')
        self.torque_value = label('—', 'result')
        self.preload_value = label('', 'section')
        self.selection_label = label('', 'muted')
        self.basis_label = label()
        self.strength_label = label('', 'muted')
        for widget in (self.torque_value, self.preload_value, self.selection_label):
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            output.addWidget(widget)
        output.addWidget(label('Bağlantı kesiti', 'section'))
        self.section_diagram = EngineeringDiagram(width=500, height=300)
        self.section_diagram.setMinimumHeight(230)
        self.section_diagram.setMaximumHeight(300)
        self.section_diagram.setAccessibleName('Cıvata, somun ve sıkılan parçaların şematik kesiti')
        output.addWidget(self.section_diagram)
        output.addWidget(label('Şematik · ölçeksiz. Parça boyları temsilidir; bağlantı kapasitesi değerlendirilmez.', 'muted'))
        for widget in (self.basis_label, self.strength_label):
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            output.addWidget(widget)
        output.addWidget(label('T = K × F × d\nF = As × akma dayanımı × ön yük oranı', 'muted'))
        output.addWidget(label(r.MANUFACTURER_NOTE))
        output.addStretch()
        self.columns.addWidget(self.input_card, 5)
        self.columns.addWidget(self.output_card, 6)
        self.columns.setAlignment(Qt.AlignTop)
        self.layout.addWidget(scroll(content), 1)
        self.finish_layout()

        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(60)
        self.update_timer.timeout.connect(self.update_result)
        self.pitch = self.settings.get('torque_pitch')
        self.sync_pitch()
        f.changed.connect(self.changed)
        self.update_result()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = event.size().width() < 760
        if hasattr(self, 'columns') and compact != self.compact:
            self.compact = compact
            self.columns.setDirection(QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight)
            self.compact_result.setVisible(compact)

    def sync_pitch(self):
        metric, series = self.form.value('metric'), self.form.value('thread_series')
        choices = r.pitch_choices(metric, series)
        try:
            selected = float(str(self.pitch).replace(',', '.'))
        except (TypeError, ValueError):
            selected = choices[0]
        if not isfinite(selected) or selected not in choices:
            selected = choices[0]
        box = self.form.fields['pitch']
        with QSignalBlocker(box):
            box.clear()
            for value in choices:
                title = ('Standart' if series == 'Normal diş' else
                         'ISO 262' if value in STANDARD_FINE_PITCHES.get(metric, ()) else 'İnce diş')
                box.addItem(f'{value:g}'.replace('.', ',') + f' mm · {title}', value)
            box.setCurrentIndex(choices.index(selected))
        box.setEnabled(series != 'Normal diş')
        self.pitch = selected
        self.settings.set('torque_pitch', str(selected))
        self.pitch_hint.setText(f'Standart normal adım: {THREADS[metric][1]:g} mm'.replace('.', ','))

    def changed(self, key):
        if self.loading:
            return
        self.loading = True
        try:
            if key in ('metric', 'thread_series'):
                self.sync_pitch()
            elif key == 'pitch':
                self.pitch = self.form.fields['pitch'].currentData()
                self.settings.set('torque_pitch', str(self.pitch))
            elif key == 'condition':
                self.form.set_value('k', str(r.DEFAULT_K[self.form.value('condition')]).replace('.', ','))
        finally:
            self.loading = False
        self.update_timer.start()

    def reset_k(self):
        self.form.set_value('k', str(r.DEFAULT_K[self.form.value('condition')]).replace('.', ','))

    def update_result(self):
        values = self.form.values()
        values['pitch'] = self.pitch
        try:
            self.result = result = r.calculate(**values)
        except ValueError as error:
            self.result = None
            self.torque_value.setText('—')
            self.compact_result.setText('Değerleri kontrol edin')
            self.preload_value.setText('Değerleri kontrol edin')
            for widget in (self.selection_label, self.basis_label, self.strength_label):
                widget.clear()
            self.copy_button.setEnabled(False)
            self.k_hint.setText('K katsayısını elle girebilir veya varsayılanına dönebilirsiniz.')
            self.reset_k_button.show()
            self.refresh_section(None)
            self.set_status(str(error), True)
            return
        self.torque_value.setText(f'{fmt(result.torque_nm)} N·m')
        self.compact_result.setText(f'{fmt(result.torque_nm)} N·m · Ön yük {fmt(result.preload_kn)} kN')
        self.preload_value.setText(f'Hesaplanan ön yük: {fmt(result.preload_kn)} kN')
        pitch_text = f'{result.pitch_mm:g}'.replace('.', ',')
        self.selection_label.setText(f'{result.metric} × {pitch_text} · {result.grade} · {result.condition}')
        self.basis_label.setText(f'Çekme alanı As: {fmt(result.tensile_area_mm2)} mm²\n'
                                 f'Akma dayanımı: {result.yield_strength_mpa:g} N/mm²\n'
                                 f'K = {result.k:g} · Ön yük = %{result.preload_percent:g}'.replace('.', ','))
        self.strength_label.setText(result.strength_basis)
        self.k_hint.setText(('Manuel K kullanılıyor. ' if result.custom_k else 'Varsayılan K kullanılıyor. ') +
                           f'{result.condition} varsayımı: {r.DEFAULT_K[result.condition]:g}'.replace('.', ','))
        self.reset_k_button.setVisible(result.custom_k)
        self.copy_button.setEnabled(True)
        self.refresh_section(result)
        self.set_status('Sonuç güncel · Tork N·m, ön yük kN olarak gösteriliyor.')

    def refresh_section(self, result):
        self.section_diagram.render_geometry(
            lambda scene: draw_section(scene, result, self.context.appearance, fmt))
        self.section_diagram.setAccessibleDescription(
            ('Kesit için geçerli hesap girdileri gerekli.' if result is None else
             f'{self.selection_label.text()}; nominal çap {result.diameter_mm:g} mm; '
             f'diş adımı {result.pitch_mm:g} mm; tahmini tork {fmt(result.torque_nm)} N·m; '
             f'hedef ön yük {fmt(result.preload_kn)} kN. Şematik ve ölçeksiz.'))

    def copy_result(self):
        # Read current fields even if the short live-update timer is pending.
        self.update_timer.stop()
        self.update_result()
        if self.result is None:
            return
        result = self.result
        text = ('GOKWORKS · Hızlı Cıvata Tork Hesabı\n'
                f'{self.selection_label.text()}\nTahmini Sıkma Torku: {fmt(result.torque_nm)} N·m\n'
                f'Hesaplanan ön yük: {fmt(result.preload_kn)} kN\n'
                f'{self.basis_label.text()}\n{result.strength_basis}\n'
                f'K kaynağı: {"manuel" if result.custom_k else "koşul varsayımı"}\n'
                'T = K × F × d; d metre, F Newton.\n'
                f'{r.K_ASSUMPTION}\n{r.MANUFACTURER_NOTE}')
        QApplication.clipboard().setText(text)
        self.set_status('Tork, ön yük ve hesap varsayımları panoya kopyalandı.')

    def theme_changed(self):
        self.update_result()
