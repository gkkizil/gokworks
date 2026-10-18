"""Metric coarse/fine-thread strength calculation; original engineering engine."""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QProgressBar
from bolt import rules as r
from bolt.diagram import draw, draw_dimensions
from .calculations import CalculationPage
from ..components import card, label, show_details
from ..theme import COLORS


METHOD = ('As = π/4 × (d − 0,938194P)²\n'
          'Ak (dişli kesme) = π/4 × (d − 1,226869P)²\n'
          'σ = Ft/(adet × As); τ = Fv/(adet × kesme düzlemi × Ak)\n'
          'σeş = √(σ² + 3τ²); izin verilen = Sp/emniyet katsayısı\n'
          'Güvenli: σeş ≤ izin verilen. Sp deney yükü gerilmesidir.\n'
          'Yükler eşit paylaşılır. kg yük × 9,80665 = N.\n'
          'Kaba adım sabittir; ISO 262 etiketi standart seçili ince adımı belirtir.\n\n' + r.SCOPE)


class BoltPage(CalculationPage):
    def __init__(self, context):
        if context.settings.get('bolt_unit') == 'kgf':
            context.settings.set('bolt_unit', 'kg')
        super().__init__(context, 'Cıvata hesabı', 'Metrik ölçü, kalite ve yük ile statik dayanım kontrolü.', 'bolt_')
        self.action('Hesap yöntemi', lambda: show_details(self, 'Cıvata hesabı', METHOD))
        f = self.form
        f.combo('metric', 'Metrik ölçü', r.THREADS, 'M10')
        f.combo('grade', 'Kalite sınıfı', r.PROOF_STRESS, '8.8')
        f.combo('thread_series', 'Diş türü', r.THREAD_SERIES, 'Kaba diş')
        f.combo('pitch', 'Diş adımı · mm', ['1,5'])
        f.combo('mode', 'Yük türü', r.MODES, 'Çekme')
        f.combo('unit', 'Yük birimi', ('kg', 'N', 'kN'), 'kN')
        f.text('tension', 'Toplam çekme · Ft', '10')
        f.text('shear', 'Toplam kesme · Fv', '4')
        f.combo('section', 'Kesme kesiti', r.SECTIONS, 'Dişli kesit')
        f.combo('planes', 'Kesme düzlemi', r.PLANES, 'Tek kesme')
        f.text('safety_factor', 'Emniyet katsayısı', '2')
        f.text('count', 'Cıvata adedi', '1')
        self.old_unit = f.value('unit')
        self.pitch = self.settings.get('bolt_pitch', '1,5')
        self.add_diagram('dimensions', 'Ölçüler')
        self.add_diagram('load', 'Yük gösterimi')
        self.diagram_tabs.setCurrentIndex(1 if self.settings.get('bolt_view') == 'Yük gösterimi' else 0)
        self.diagram_tabs.currentChanged.connect(
            lambda index: self.settings.set('bolt_view', self.diagram_tabs.tabText(index)))

        self.safety_card, safety = card('Güvenlik kontrolü')
        self.safety_card.setObjectName('boltSafetyCard')
        self.safety_verdict = label()
        self.safety_progress = QProgressBar()
        self.safety_progress.setObjectName('boltUtilization')
        self.safety_progress.setRange(0, 1000)
        self.safety_progress.setTextVisible(False)
        self.safety_progress.setAccessibleName('Cıvata kapasite kullanımı')
        self.safety_progress.setFixedHeight(8)
        self.safety_usage = label()
        for widget in (self.safety_verdict, self.safety_progress, self.safety_usage):
            safety.addWidget(widget)
        self.right.insertWidget(self.right.indexOf(self.diagram_tabs), self.safety_card)

        self.capacity_card, capacity = card('Taşıma sınırları')
        self.capacity_text = label()
        self.capacity_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        capacity.addWidget(self.capacity_text)
        self.right.insertWidget(self.right.indexOf(self.details), self.capacity_card)
        self.details.hide()
        technical_card, technical = card('Teknik bilgi')
        technical.addWidget(label('As = π/4 × (d − 0,938194P)²\n'
                                 'İzin verilen gerilme = Sp / emniyet katsayısı\n'
                                 'Birleşik yük: σeş = √(σ² + 3τ²)\n\n'
                                 'Statik yük ve eşit yük paylaşımı kabul edilir. '
                                 'Ön sıkma, diş sıyırması ve bağlantı plakaları ayrıca kontrol edilir.'))
        technical.addWidget(label('kg yük × 9,80665 = N. Birim değişince girilen yükler dönüştürülür.', 'muted'))
        self.extra_layout.addWidget(technical_card)
        self.sync_pitch()
        self.update_result()

    def paint_safety(self, state):
        colors = COLORS[self.context.appearance]
        color = colors[{'safe': 'accent', 'unsafe': 'danger', 'empty': 'warning'}[state]]
        self.safety_card.setStyleSheet(f'QFrame#boltSafetyCard {{ border-color: {color}; }}')
        self.safety_verdict.setStyleSheet(f'font-size: 19px; font-weight: 650; color: {color};')
        self.safety_progress.setStyleSheet(
            f'QProgressBar#boltUtilization {{ background: {colors["input"]}; border-radius: 4px; }}'
            f'QProgressBar#boltUtilization::chunk {{ background: {color}; border-radius: 4px; }}')

    def invalid(self, error):
        super().invalid(error)
        self.safety_verdict.setText('Hesaplanamadı · değerleri kontrol edin')
        self.safety_progress.setValue(0)
        self.safety_progress.setToolTip('Geçerli yük ve cıvata değerleri girin.')
        self.safety_progress.setAccessibleDescription(self.safety_progress.toolTip())
        self.safety_usage.clear()
        self.capacity_text.setText('Geçerli değerler girildiğinde taşıma sınırları burada görünür.')
        self.paint_safety('empty')

    def show_safety(self, result, verdict):
        self.paint_safety('empty' if not result.loaded else 'safe' if result.safe else 'unsafe')
        self.safety_verdict.setText(verdict + (f' · {r.fmt(result.safety_factor)} emniyet hedefi ' +
            ('sağlanıyor' if result.safe else 'sağlanmıyor') if result.loaded else ' · kontrol için yük girin'))
        percent = r.fmt(result.utilization*100, 1)
        self.safety_progress.setValue(round(min(1., result.utilization)*1000))
        self.safety_progress.setToolTip(f'Kullanım: %{percent}. %100, seçilen emniyet katsayısındaki sınırdır.')
        self.safety_progress.setAccessibleDescription(self.safety_progress.toolTip())
        margin = result.safety_margin
        margin_text = 'yük yok' if margin is None else ('+' if margin > 0 else '−' if margin < 0 else '') + '%' + r.fmt(abs(margin)*100, 1)
        minimum = result.minimum_count
        minimum_text = ('Minimum adet, yük girildiğinde hesaplanır.' if minimum is None else
                        'Gerekli adet, 1000 adet sınırını aşıyor.' if minimum > 1000 else
                        f'Eşit yük paylaşımıyla gerekli en az: {minimum} cıvata.')
        self.safety_usage.setText(f'Kullanım: %{percent} · Yük marjı: {margin_text}\n{minimum_text}')
        text = (f'{result.count} cıvata için tek başına yük sınırları:\n'
                f'Çekme: {r.force_text(result.tension_capacity_n, result.unit)}\n'
                f'Kesme: {r.force_text(result.shear_capacity_n, result.unit)}\n'
                'Birleşik yükte bu iki sınır aynı anda kullanılamaz.')
        if result.mode == 'Birleşik yük':
            for title, load, limit in (
                ('Kesme', result.shear_n, result.tension_limit_with_shear_n),
                ('Çekme', result.tension_n, result.shear_limit_with_tension_n)):
                other = 'çekme' if title == 'Kesme' else 'kesme'
                text += (f'\n\n{title} ({r.force_text(load, result.unit)}) sabitken {other} sınırı: ' +
                         (r.force_text(limit, result.unit) if limit is not None else
                          'yok; sabit tutulan yük tek başına sınırı aşıyor.'))
            text += '\nBunlar toplam yük sınırıdır; eklenebilecek yük değildir.'
        self.capacity_text.setText(text)

    def sync_pitch(self):
        f = self.form
        metric, series = f.value('metric'), f.value('thread_series')
        choices = r.pitch_choices(metric, series)
        try:
            _, selected = r.thread_geometry(metric, series, self.pitch)
        except ValueError:
            selected = choices[0]
        box = f.fields['pitch']
        with QSignalBlocker(box):
            box.clear()
            for value in choices:
                kind = 'Standart' if series == 'Kaba diş' else 'ISO 262' if value in r.STANDARD_FINE_PITCHES.get(metric, ()) else 'İnce diş'
                box.addItem(f'{r.fmt(value)} mm · {kind}', value)
            box.setCurrentIndex(choices.index(selected))
        box.setEnabled(series != 'Kaba diş')
        self.pitch = str(selected)
        self.settings.set('bolt_pitch', self.pitch)

    def changed(self, key):
        if self.loading:
            return
        self.loading = True
        try:
            if key in ('metric', 'thread_series'):
                self.sync_pitch()
            elif key == 'pitch':
                self.pitch = str(self.form.fields['pitch'].currentData())
                self.settings.set('bolt_pitch', self.pitch)
            elif key == 'unit':
                new = self.form.value('unit')
                for field in ('tension', 'shear'):
                    try:
                        value = r.number(self.form.value(field), 'Yük') * r.UNITS[self.old_unit] / r.UNITS[new]
                        self.form.set_value(field, f'{value:.12g}'.replace('.', ','))
                    except ValueError:
                        pass
                self.old_unit = new
        finally:
            self.loading = False
        super().changed(key)

    def update_result(self):
        values = self.form.values()
        values['pitch'] = self.pitch
        mode = values['mode']
        for key in ('shear', 'section', 'planes'):
            self.form.fields[key].setEnabled(mode != 'Çekme')
        self.form.fields['tension'].setEnabled(mode != 'Kesme')
        try:
            self.result = result = r.calculate(**values)
        except ValueError as error:
            self.invalid(error)
            return
        verdict = 'Yük yok' if not result.loaded else 'Güvenli' if result.safe else 'Güvensiz'
        capacity = result.tension_capacity_n if mode == 'Çekme' else result.shear_capacity_n
        self.headline.setText((f'%{r.fmt(result.utilization*100, 1)} kullanım' if mode == 'Birleşik yük' else r.force_text(capacity, result.unit)) + ' · ' + verdict)
        self.summary.setText(f'{result.metric} · {result.grade} · {result.count} cıvata · {mode} · Emniyet {r.fmt(result.safety_factor)}\nStandart kaba adım: {r.fmt(r.THREADS[result.metric][1])} mm')
        self.show_safety(result, verdict)
        rows = [('Metrik / kalite', f'{result.metric} / {result.grade}'), ('Yük türü', mode),
                ('Diş türü', values['thread_series']), ('Diş adımı (mm)', r.fmt(result.pitch)),
                ('Çekme alanı As (mm²)', r.fmt(result.tensile_area)),
                ('Kesme alanı Ak (mm²)', r.fmt(result.shear_area)),
                ('Çekme gerilmesi (MPa)', r.fmt(result.tensile_stress)),
                ('Kesme gerilmesi (MPa)', r.fmt(result.shear_stress)),
                ('Eşdeğer gerilme (MPa)', r.fmt(result.equivalent_stress)),
                ('İzin verilen gerilme (MPa)', r.fmt(result.allowable_stress)),
                ('Deney yükü gerilmesi Sp (MPa)', r.fmt(result.proof_stress)),
                ('Mevcut emniyet', r.fmt(result.available_factor) if result.available_factor is not None else 'Yük yok'),
                ('Kullanım (%)', r.fmt(result.utilization*100)), ('Gerekli en az adet', result.minimum_count if result.loaded else 'Yük yok'),
                ('Yük marjı', f'%{r.fmt(result.safety_margin*100)}' if result.safety_margin is not None else 'Yük yok'),
                ('Çekme sınırı', r.force_text(result.tension_capacity_n, result.unit)),
                ('Kesme sınırı', r.force_text(result.shear_capacity_n, result.unit))]
        for title, force in (('Kesme sabitken çekme sınırı', result.tension_limit_with_shear_n),
                             ('Çekme sabitken kesme sınırı', result.shear_limit_with_tension_n)):
            rows.append((title, 'Geçerli sınır yok' if force is None else r.force_text(force, result.unit)))
        rows += [('Toplam çekme', r.force_text(result.tension_n, result.unit)),
                 ('Toplam kesme', r.force_text(result.shear_n, result.unit)),
                 ('Kesme kesiti', result.section), ('Kesme düzlemi', values['planes']),
                 ('Cıvata adedi', result.count), ('Emniyet katsayısı', r.fmt(result.safety_factor)),
                 ('Güvenlik açıklaması', self.safety_usage.text()), ('Taşıma sınırları', self.capacity_text.text())]
        rows += [('Sonuç', verdict), ('Yöntem', METHOD), ('Kapsam', r.SCOPE)]
        self.present(rows)
        self.diagrams['dimensions'].render_geometry(lambda scene: draw_dimensions(scene, result, self.appearance, 1))
        self.diagrams['load'].render_geometry(lambda scene: draw(scene, result, self.appearance, 1))
        self.set_status('Değerler güncel. ' + verdict)
