"""Metric coarse/fine-thread strength calculation; original engineering engine."""

from PySide6.QtCore import QSignalBlocker
from bolt import rules as r
from bolt.diagram import draw, draw_dimensions
from .calculations import CalculationPage
from ..components import show_details


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
        self.details.setText('kg yük = kütle × 9,80665 N/kg. Birim değişince girilen yükler dönüştürülür.')
        self.sync_pitch()
        self.update_result()

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
        rows = [('Metrik / kalite', f'{result.metric} / {result.grade}'), ('Yük türü', mode),
                ('Diş türü', values['thread_series']), ('Diş adımı (mm)', r.fmt(result.pitch)),
                ('Çekme alanı As (mm²)', r.fmt(result.tensile_area)),
                ('Eşdeğer gerilme (MPa)', r.fmt(result.equivalent_stress)),
                ('İzin verilen gerilme (MPa)', r.fmt(result.allowable_stress)),
                ('Deney yükü gerilmesi Sp (MPa)', r.fmt(result.proof_stress)),
                ('Mevcut emniyet', r.fmt(result.available_factor) if result.available_factor is not None else 'Yük yok'),
                ('Kullanım (%)', r.fmt(result.utilization*100)), ('Gerekli en az adet', result.minimum_count),
                ('Yük marjı', f'%{r.fmt(result.safety_margin*100)}' if result.safety_margin is not None else 'Yük yok'),
                ('Çekme sınırı', r.force_text(result.tension_capacity_n, result.unit)),
                ('Kesme sınırı', r.force_text(result.shear_capacity_n, result.unit))]
        for title, force in (('Kesme sabitken çekme sınırı', result.tension_limit_with_shear_n),
                             ('Çekme sabitken kesme sınırı', result.shear_limit_with_tension_n)):
            rows.append((title, 'Geçerli sınır yok' if force is None else r.force_text(force, result.unit)))
        rows.extend((key, value) for key, value in values.items())
        rows += [('Sonuç', verdict), ('Yöntem', METHOD), ('Kapsam', r.SCOPE)]
        self.present(rows)
        self.diagrams['dimensions'].render_geometry(lambda scene: draw_dimensions(scene, result, self.appearance, 1))
        self.diagrams['load'].render_geometry(lambda scene: draw(scene, result, self.appearance, 1))
        self.set_status('Değerler güncel. ' + verdict)
