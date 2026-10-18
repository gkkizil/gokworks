"""ISO 286 selection and independent manual limits with exact Decimal results."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTreeView, QTabWidget
from iso_fits import rules as r
from iso_fits import manual as m
from iso_fits.diagram import draw
from iso_fits.selection_diagram import draw_selection
from .calculations import CalculationPage
from ..components import label, configure_view, show_details
from ..models import TreeModel, FilterProxy, Column


HELP = ('ISO 286-1:2010 / ISO 286-2:2010 · Doğrulanan tablo: 1–400 mm.\n'
        'C = delik − mil: (+) boşluk, (−) sıkılık, 0 temas.\n'
        'Manuel sapmalar mm olarak girilir; rapor birimi girişleri değiştirmez.\n'
        'Şema merkezlidir ve ölçekli değildir. Küçük farklar görünür çizilir.\n'
        'Montaj kuvveti, malzeme, sıcaklık, yüzey ve yağlama ayrıca değerlendirilir.\n'
        'En yakın ISO eşleşmesi referanstır; girilen sınırlar standarda dönüştürülmez.')
SAMPLES = ('En az boşluk', 'Orta değer', 'En çok boşluk')
VIEWS = ('Montaj kesiti', 'Tolerans bölgeleri')
BASES = ('Tümü', 'Delik esaslı', 'Mil esaslı')
SECTION_HELP = HELP


class IsoPage(CalculationPage):
    def __init__(self, context):
        super().__init__(context, 'ISO geçme toleransları', 'ISO sınıfı seçin veya kendi ölçü sınırlarınızı kontrol edin.', 'iso_')
        self.action('Geçme rehberi', lambda: show_details(self, 'ISO tolerans rehberi', HELP))
        f = self.form
        f.combo('method', 'Hesap yöntemi', ('ISO seçimi', 'Manuel kontrol'))
        f.text('diameter', 'Nominal çap · mm', '50')
        f.combo('hole', 'Delik sınıfı', r.classes('hole'), 'H7')
        f.combo('shaft', 'Mil sınıfı', r.classes('shaft'), 'g6')
        f.combo('unit', 'Sapma gösterimi', ('mm', 'µm'))
        for key, title, default in (('hole_lower', 'Delik alt sapma · mm', '0'),
                                     ('hole_upper', 'Delik üst sapma · mm', '0,02'),
                                     ('shaft_lower', 'Mil alt sapma · mm', '-0,02'),
                                     ('shaft_upper', 'Mil üst sapma · mm', '0')):
            f.text(key, title, default)
        f.combo('target', 'Montaj hedefi', m.TARGETS)
        f.combo('sample', 'Kesit örneği', ('En az boşluk', 'Orta değer', 'En çok boşluk'), 'Orta değer')
        f.combo('view', 'Şema', ('Montaj kesiti', 'Tolerans bölgeleri'))
        f.combo('basis', 'Geçme esası', ('Tümü', 'Delik esaslı', 'Mil esaslı'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Hazır geçme ara…')
        self.extra_layout.addWidget(self.search)
        self.presets = configure_view(QTreeView())
        self.presets.setSortingEnabled(False)
        self.preset_model = TreeModel((Column('Hazır geçmeler', 'name'),))
        self.preset_proxy = FilterProxy(self, tree=True)
        self.preset_proxy.setSourceModel(self.preset_model)
        self.presets.setModel(self.preset_proxy)
        self.presets.setMinimumHeight(250)
        self.extra_layout.addWidget(self.presets)
        self.search.textChanged.connect(self.preset_proxy.set_query)
        self.presets.clicked.connect(self.select_preset)
        self.add_diagram('fit', 'Montaj ve tolerans şeması', height=330)
        self.manual_tabs = QTabWidget()
        self.compatibility_label = label()
        self.limits_label = label()
        self.comparison_label = label()
        self.manual_tabs.addTab(self.compatibility_label, 'Montaj uyumu')
        self.manual_tabs.addTab(self.limits_label, 'Ölçü sınırları')
        self.manual_tabs.addTab(self.comparison_label, 'ISO karşılaştırması')
        self.right.insertWidget(4, self.manual_tabs)
        self.update_result()

    def select_preset(self, index):
        row = index.data(Qt.UserRole)
        if row and 'hole' in row:
            self.loading = True
            self.form.set_value('hole', row['hole'])
            self.form.set_value('shaft', row['shaft'])
            self.form.set_value('method', 'ISO seçimi')
            self.loading = False
            self.update_result()

    def populate_presets(self):
        basis = self.form.value('basis')
        key = (self.form.value('diameter'), basis)
        if getattr(self, '_preset_key', None) == key:
            return
        rows = [dict(id=kind, parent='', name=title) for kind, title in r.CLASSIFICATION.items()]
        for preset in r.PRESETS:
            if basis not in ('Tümü', preset.basis):
                continue
            try:
                kind = r.calculate(key[0], preset.hole, preset.shaft).kind
            except ValueError:
                kind = 'clearance'
            rows.append(dict(id=preset.code, parent=kind, name=f'{preset.code} · {preset.label}', hole=preset.hole, shaft=preset.shaft))
        self.preset_model.replace(rows)
        self.presets.expandAll()
        self._preset_key = key

    @staticmethod
    def match_text(band, feature):
        nearest = m.closest_classes(band, feature)
        matches = m.compare_classes(band, feature)
        if nearest[0].exact:
            return 'Tam ISO eşleşmesi: ' + ', '.join(item.code for item in nearest)
        return ('Tam eşleşme yok. En yakın: ' + ', '.join(item.code for item in nearest) + ' (referans).\n' +
                '\n'.join(f'{item.code}: alt fark {r.format_deviation(item.lower_difference_nm, "µm")}, üst fark {r.format_deviation(item.upper_difference_nm, "µm")}' for item in matches[:3]))

    def update_result(self):
        f = self.form
        manual = f.value('method') == 'Manuel kontrol'
        for key in ('hole_lower', 'hole_upper', 'shaft_lower', 'shaft_upper', 'target'):
            f.show_field(key, manual)
        for key in ('hole', 'shaft', 'basis'):
            f.show_field(key, not manual)
        self.search.setVisible(not manual)
        self.presets.setVisible(not manual)
        self.manual_tabs.setVisible(manual)
        self.populate_presets()
        try:
            self.result = fit = (m.calculate_manual(f.value('diameter'), *(f.value(key) for key in
                                   ('hole_lower', 'hole_upper', 'shaft_lower', 'shaft_upper'))) if manual else
                                 r.calculate(f.value('diameter'), f.value('hole'), f.value('shaft')))
        except ValueError as error:
            self.invalid(error)
            for widget in (self.compatibility_label, self.limits_label, self.comparison_label):
                widget.setText('Geçerli sınırlar girin.')
            return
        unit = f.value('unit')
        self.headline.setText(r.CLASSIFICATION[fit.kind])
        self.summary.setText(f'Cmin = {r.format_deviation(fit.minimum_clearance_nm, unit)}    ·    Cmax = {r.format_deviation(fit.maximum_clearance_nm, unit)}')
        self.details.setText(m.usage_hint(fit) + '\n' + HELP.split('\n')[1])
        rows = [('Standart', 'ISO 286-1:2010 / ISO 286-2:2010'), ('Hesap yöntemi', f.value('method')),
                ('Nominal çap (mm)', r.format_mm(fit.hole.nominal_mm)), ('Geçme türü', r.CLASSIFICATION[fit.kind]),
                ('Delik sınıfı', fit.hole.code), ('Mil sınıfı', fit.shaft.code)]
        for title, band in (('Delik', fit.hole), ('Mil', fit.shaft)):
            rows.extend([(title + ' minimum (mm)', r.format_mm(band.minimum_mm)),
                         (title + ' maksimum (mm)', r.format_mm(band.maximum_mm)),
                         (title + ' alt sapma', r.format_deviation(band.lower_nm, unit)),
                         (title + ' üst sapma', r.format_deviation(band.upper_nm, unit))])
        rows += [('Minimum delik − mil', r.format_deviation(fit.minimum_clearance_nm, unit)),
                 ('Maksimum delik − mil', r.format_deviation(fit.maximum_clearance_nm, unit))]
        sample = f.value('sample')
        hole, shaft = fit.sample(sample)
        rows += [('Kesit örneği', sample), ('Örnek delik (mm)', r.format_mm(hole)), ('Örnek mil (mm)', r.format_mm(shaft)),
                 ('Çapsal fark (mm)', r.format_mm(hole-shaft, signed=True)), ('Tek taraflı fark (mm)', r.format_mm(abs(hole-shaft)/2))]
        if manual:
            check = m.compatibility(fit, f.value('target'))
            nearest = m.closest_pair(fit)
            preset = m.closest_preset(fit)
            rows += [('Montaj hedefi', f.value('target')), ('Montaj uyumu', check.title + '\n' + check.explanation),
                     ('Delik ISO kontrolü', self.match_text(fit.hole, 'hole')), ('Mil ISO kontrolü', self.match_text(fit.shaft, 'shaft')),
                     ('En yakın ISO çifti', nearest.code + ' (referans)'),
                     ('Toplam limit farkı', r.format_deviation(nearest.distance_nm, unit)),
                     ('En büyük limit farkı', r.format_deviation(nearest.worst_limit_difference_nm, unit)),
                     ('En yakın hazır eşleşme', preset.code + ' (referans)')]
            self.compatibility_label.setText(check.title + '\n\n' + check.explanation + '\n\nEn yakın ISO çifti: ' + nearest.code + ' (referans). Girilen limitler değiştirilmez.')
            self.limits_label.setText('\n'.join(f'{key}: {value}' for key, value in rows[6:14]))
            self.comparison_label.setText('DELİK: ' + self.match_text(fit.hole, 'hole') + '\n\nMİL: ' + self.match_text(fit.shaft, 'shaft'))
        rows.append(('Kapsam', HELP))
        self.present(rows)
        diagram = self.diagrams['fit']
        if not manual and f.value('view') == 'Montaj kesiti':
            diagram.render_geometry(lambda scene: draw_selection(scene, fit, self.appearance, 1, sample))
        else:
            diagram.render_geometry(lambda scene: draw(scene, fit, f.value('view'), sample, self.appearance, 1))
        self.set_status('Ölçü sınırları güncel. ' + m.usage_hint(fit))
