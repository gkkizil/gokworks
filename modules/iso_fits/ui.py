"""ISO 286 selection and independent manual limits with exact Decimal results."""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QTreeView, QTabWidget, QTabBar
from modules.iso_fits import rules as r
from modules.iso_fits import manual as m
from modules.iso_fits.diagram import draw
from modules.iso_fits.selection_diagram import draw_selection
from gui_qt.calculations import CalculationPage
from gui_qt.components import Disclosure, card, label, scroll, configure_view, show_details
from gui_qt.models import TreeModel, FilterProxy, Column


HELP = ('ISO 286-1:2010 / ISO 286-2:2010 · Doğrulanan tablo: 1–400 mm.\n'
        'C = delik − mil: (+) boşluk, (−) sıkılık, 0 temas.\n'
        'Manuel sapmalar mm olarak girilir; rapor birimi girişleri değiştirmez.\n'
        'Şema merkezlidir ve ölçekli değildir. Küçük farklar görünür çizilir.\n'
        'Montaj kuvveti, malzeme, sıcaklık, yüzey ve yağlama ayrıca değerlendirilir.\n'
        'En yakın ISO eşleşmesi referanstır; girilen sınırlar standarda dönüştürülmez.')
SAMPLES = ('En az boşluk', 'Orta değer', 'En çok boşluk')
VIEWS = ('Montaj kesiti', 'Tolerans bölgeleri')
BASES = ('Tümü', 'Delik esaslı', 'Mil esaslı')
SECTION_HELP = ('D: delik çapı · d: mil çapı · g: tek taraftaki boşluk / çakışma.\n'
                'Kesit eş merkezli ve ölçeksizdir; küçük farklar görünür çizilir.\n'
                'Kırmızı alan: deformasyon öncesi boyutsal çakışma.\n'
                'Orta değer, ölçü sınırlarının ortasıdır; üretimde en sık oluşacak ölçü anlamına gelmez.')
GUIDE = '''Nominal çap, delik ve mil için ortak ana ölçüdür. Bu ekran 1–400 mm aralığında, tablolarla doğrulanan 11 delik ve 18 mil sınıfını sunar. Delik sınıfı büyük harfle, mil sınıfı küçük harfle gösterilir. Örneğin H7/h6, H7 deliği ile h6 milinin eşleşmesidir.

Alt ve üst sapmalar ölçü sınırlarını belirler. EI ve ES delik sapmalarıdır; ei ve es mil sapmalarıdır. Çap aralıklarında alt sınır hariç, üst sınır dahildir.

En az delik − mil farkı: Cmin = EI − es.
En çok delik − mil farkı: Cmax = ES − ei.
Pozitif fark boşluk, negatif fark sıkılık, sıfır fark sınırda temas demektir. Boşluklu geçmede en küçük fark sıfır veya pozitiftir. Sıkı geçmede en büyük fark sıfır veya negatiftir; en küçük fark negatiftir. Ara geçmede fark hem pozitif hem negatif olabilir. H7/h6 gibi en az boşluğu sıfır olan eşleşmeler ara geçme değildir.

Montaj kesiti açıklama amaçlıdır; küçük farklar görünürlük için büyütülür. Tolerans bölgeleri sayısal sapma ölçeğini gösterir. “Orta değer” yalnız ölçü sınırlarının ortasıdır; üretimde en sık oluşacak ölçü anlamına gelmez.

Manuel kontrolde delik ve mil için ortak nominal çap ile ayrı alt/üst sapmalar girilir. Geçme girilen ölçü limitlerinden hesaplanır. Tam ISO eşleşmesi iki sapmanın da aynı olmasıdır; en yakın sınıf mevcut sınıflar içindeki alt/üst farkların mutlak toplamına göre seçilir. Yakın sınıf girilen toleransları değiştirmez. Kayar/yağlı kullanım adları öneridir; yağlama veya montaj kuvveti sonucu değildir.

Eşleşme örnekleri delik esaslı (H: EI=0) ve mil esaslı (h: es=0) olarak filtrelenir. Aynı H7 deliği farklı millerle farklı geçmeler oluşturabilir; H7 tek başına geçme türü değildir. Liste bütün ISO çiftlerini değil, doğrulanan tablolardan 23 örneği gösterir. Delik/mil menülerinden 198 çift serbestçe seçilebilir. Her örneğin grubu seçilen çaptaki gerçek limitlere göre hesaplanır. Manuel kontrolde eşit uzaklıktaki sınıflar birlikte verilir; hazır örneklerden birine zorla eşleştirme yapılmaz.

Geçme türü, ölçü sınırlarından hesaplanır. Montaj veya pres kuvveti, yağlama ve sıcaklık seçimi için malzeme, yüzey ve çalışma koşulları ayrıca değerlendirilmelidir. Bu sekme geometrik tolerans hesabı yapmaz.

Standart temeli ISO 286-1:2010 ve ISO 286-2:2010’dur. Karşılaştırılan açık kaynak tablolar: parkergreene/isofits, lachr/Passungsrechner ve bell-jamie/iso-286. Kaynak kayıtları ve tablo karşılaştırmaları docs/iso-fits.md içindedir. Uygulama standardın tam metnini içermez; resmî kapsam ve güncellik ISO kataloğundan kontrol edilmelidir.'''


class IsoPage(CalculationPage):
    def __init__(self, context):
        super().__init__(context, 'ISO geçme toleransları', 'ISO sınıfı seçin veya kendi ölçü sınırlarınızı kontrol edin.', 'iso_')
        self.info_action('Geçme rehberi', lambda: show_details(self, 'ISO tolerans rehberi', GUIDE))
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
        preset_content = QWidget()
        preset_layout = QVBoxLayout(preset_content)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        preset_layout.addWidget(self.search)
        self.presets = configure_view(QTreeView())
        self.presets.setSortingEnabled(False)
        self.preset_model = TreeModel((Column('Hazır geçmeler', 'name'),))
        self.preset_proxy = FilterProxy(self, tree=True)
        self.preset_proxy.setSourceModel(self.preset_model)
        self.presets.setModel(self.preset_proxy)
        self.presets.setMinimumHeight(180)
        preset_layout.addWidget(self.presets)
        self.preset_section = Disclosure('Hazır geçme örnekleri', preset_content)
        self.extra_layout.addWidget(self.preset_section)
        self.search.textChanged.connect(self.preset_proxy.set_query)
        self.presets.clicked.connect(self.select_preset)
        # The manual section includes result labels through y=290. Keep them
        # inside the scene and reserve matching space above the sample tabs.
        self.add_diagram('fit', 'Montaj ve tolerans şeması', height=320)
        self.diagram_tabs.setMaximumHeight(340)
        self.diagram_tabs.tabBar().hide()
        self.view_tabs = QTabBar()
        self.sample_tabs = QTabBar()
        for bar, values, key in ((self.view_tabs, VIEWS, 'view'), (self.sample_tabs, SAMPLES, 'sample')):
            bar.setExpanding(True)
            bar.setDrawBase(False)
            for value in values:
                bar.addTab(value)
            bar.setCurrentIndex(values.index(f.value(key)))
            bar.currentChanged.connect(lambda index, key=key, values=values: f.set_value(key, values[index]))
            f.show_field(key, False)
        self.right.insertWidget(self.right.indexOf(self.diagram_tabs), self.view_tabs)
        self.right.insertWidget(self.right.indexOf(self.diagram_tabs) + 1, self.sample_tabs)
        self.explanation_card, explanation = card('Geçme yorumu')
        self.right.removeWidget(self.details)
        explanation.addWidget(self.details)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.usage_label = label('', 'muted')
        explanation.addWidget(self.usage_label)
        self.right.insertWidget(self.right.indexOf(self.sample_tabs) + 1, self.explanation_card)
        self.section_help = label(SECTION_HELP, 'muted')
        self.section_summary = label('', 'muted')
        self.right.insertWidget(self.right.indexOf(self.sample_tabs) + 1, self.section_summary)
        self.section_notes = Disclosure('Şemayı okuma ve kapsam', self.section_help)
        self.right.insertWidget(self.right.indexOf(self.explanation_card) + 1, self.section_notes)
        self.manual_tabs = QTabWidget()
        self.compatibility_label = label()
        self.limits_label = label()
        self.comparison_label = label()
        for widget, title in ((self.compatibility_label, 'Montaj uyumu'),
                              (self.limits_label, 'Ölçü sınırları'),
                              (self.comparison_label, 'ISO karşılaştırması')):
            widget.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.manual_tabs.addTab(scroll(widget), title)
        self.manual_tabs.setMinimumHeight(240)
        self.right.insertWidget(self.right.indexOf(self.explanation_card) + 1, self.manual_tabs)
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
        return ('Tam ISO eşleşmesi yok. En yakın: ' + ', '.join(item.code for item in nearest) + ' (referans).\n' +
                '\n'.join(f'{item.code} · Girilen − ISO: alt {r.format_deviation(item.lower_difference_nm, "µm")}, üst {r.format_deviation(item.upper_difference_nm, "µm")}' for item in matches[:3]))

    @staticmethod
    def fit_explanation(fit, unit):
        if fit.kind == 'clearance':
            text = 'Tüm limitlerde boşluk veya sınırda temas var.'
            if fit.minimum_clearance_nm == 0:
                text += ' Minimum boşluk sıfır; bu bir ara geçme değildir.'
            return text
        if fit.kind == 'transition':
            return ('Parçanın gerçekleşen ölçüsüne göre boşluk veya sıkılık oluşabilir. '
                    f'En büyük sıkılık: {r.format_deviation(fit.maximum_interference_nm, unit)}.')
        return (f'Sıkılık aralığı: {r.format_deviation(fit.minimum_interference_nm, unit)}'
                f' → {r.format_deviation(fit.maximum_interference_nm, unit)}.')

    @staticmethod
    def compatibility_text(fit, check, nearest, unit):
        heading = 'Tam ISO çift eşleşmesi' if nearest.distance_nm == 0 else 'En yakın ISO çift (yalnız referans)'
        text = (f'{check.title}\n\nGirilen limitlerin sonucu: {r.CLASSIFICATION[fit.kind]}.\n{check.explanation}\n\n'
                f'{heading}: {nearest.code}. Referansın türü: {r.CLASSIFICATION[nearest.fit.kind]}. '
                f'Toplam limit farkı: {r.format_deviation(nearest.distance_nm, unit)}. '
                f'En büyük tek limit farkı: {r.format_deviation(nearest.worst_limit_difference_nm, unit)}.')
        for band, feature, title in ((fit.hole, 'hole', 'Delik'), (fit.shaft, 'shaft', 'Mil')):
            tied = m.closest_classes(band, feature)
            if len(tied) > 1:
                text += f'\n{title}: eşit uzaklıktaki sınıflar ' + ', '.join(item.code for item in tied) + '.'
        if nearest.fit.kind != fit.kind:
            text += '\nYakın referansın türü girilen ölçülerin türünden farklı olabilir; montaj hesabı girilen limitlere aittir.'
        if nearest.beyond_reference_width:
            text += ('\nISO çiftinden en az bir sınır farkı, o parçanın referans tolerans genişliğini aşıyor; '
                     'en yakın etiketi ISO uyumu veya uygun üretim toleransı anlamına gelmez.')
        return text + ('\n\nGirilen limitler değiştirilmez. Bu kontrol boyutsaldır; gerçek montaj kuvveti, '
                       'yüzey, şekil ve çalışma koşulları ayrıca değerlendirilir.')

    def invalid(self, error):
        super().invalid(error)
        self.details.setText('Geçerli sınırlar girildiğinde geçme açıklaması burada görünür.')
        self.usage_label.clear()
        self.section_summary.clear()
        self.section_help.setText(SECTION_HELP)

    def update_result(self):
        f = self.form
        for bar, values, key in ((self.view_tabs, VIEWS, 'view'), (self.sample_tabs, SAMPLES, 'sample')):
            with QSignalBlocker(bar):
                bar.setCurrentIndex(values.index(f.value(key)))
        manual = f.value('method') == 'Manuel kontrol'
        for key in ('hole_lower', 'hole_upper', 'shaft_lower', 'shaft_upper', 'target'):
            f.show_field(key, manual)
        for key in ('hole', 'shaft', 'basis'):
            f.show_field(key, not manual)
        self.search.setVisible(not manual)
        self.presets.setVisible(not manual)
        self.preset_section.setVisible(not manual)
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
        explanation = self.fit_explanation(fit, unit)
        self.details.setText(explanation)
        self.usage_label.setText('Kullanım yorumu (öneri): ' + m.usage_hint(fit) + '\n' +
                                HELP.split('\n')[1] + '\n' + HELP.split('\n')[4])
        self.section_summary.setVisible(f.value('view') == 'Montaj kesiti')
        self.section_notes.setVisible(f.value('view') == 'Montaj kesiti')
        rows = [('Standart', 'ISO 286-1:2010 / ISO 286-2:2010'), ('Hesap yöntemi', f.value('method')),
                ('Nominal çap (mm)', r.format_mm(fit.hole.nominal_mm)), ('Geçme türü', r.CLASSIFICATION[fit.kind]),
                ('Delik sınıfı', fit.hole.code), ('Mil sınıfı', fit.shaft.code)]
        for title, band in (('Delik', fit.hole), ('Mil', fit.shaft)):
            rows.extend([(title + ' minimum (mm)', r.format_mm(band.minimum_mm)),
                         (title + ' maksimum (mm)', r.format_mm(band.maximum_mm)),
                         (title + ' alt sapma', r.format_deviation(band.lower_nm, unit)),
                         (title + ' üst sapma', r.format_deviation(band.upper_nm, unit))])
        rows += [('Minimum delik − mil', r.format_deviation(fit.minimum_clearance_nm, unit)),
                 ('Maksimum delik − mil', r.format_deviation(fit.maximum_clearance_nm, unit)),
                 ('Geçme açıklaması', explanation), ('Kullanım yorumu (öneri)', m.usage_hint(fit))]
        sample = f.value('sample')
        hole, shaft = fit.sample(sample)
        rows += [('Kesit örneği', sample), ('Örnek delik (mm)', r.format_mm(hole)), ('Örnek mil (mm)', r.format_mm(shaft)),
                 ('Çapsal fark (mm)', r.format_mm(hole-shaft, signed=True)), ('Tek taraflı fark (mm)', r.format_mm(abs(hole-shaft)/2))]
        self.section_help.setText(f'{sample} · D = {r.format_mm(hole)} mm · d = {r.format_mm(shaft)} mm\n'
                                  f'Çapsal fark = {r.format_mm(hole-shaft, signed=True)} mm · '
                                  f'Tek tarafta g = {r.format_mm(abs(hole-shaft)/2)} mm\n' + SECTION_HELP)
        self.section_summary.setText(f'D = {r.format_mm(hole)} mm · d = {r.format_mm(shaft)} mm\n'
                                     f'Çapsal fark = {r.format_mm(hole-shaft, signed=True)} mm · '
                                     f'g = {r.format_mm(abs(hole-shaft)/2)} mm · Ölçeksiz şema')
        if manual:
            check = m.compatibility(fit, f.value('target'))
            nearest = m.closest_pair(fit)
            preset = m.closest_preset(fit)
            compatibility = self.compatibility_text(fit, check, nearest, unit)
            comparison = ('DELİK · ' + self.match_text(fit.hole, 'hole') + '\n\nMİL · ' + self.match_text(fit.shaft, 'shaft') +
                          '\n\nKarşılaştırma mevcut 11 delik / 18 mil sınıfı içindedir. '
                          'Yakınlık, alt/üst sapma farklarının mutlak toplamıdır. Kullanım adları öneridir; '
                          'yağlama kararı için yüzey, malzeme ve çalışma koşulları gerekir.')
            rows += [('Montaj hedefi', f.value('target')), ('Montaj uyumu', compatibility),
                     ('Delik ISO kontrolü', self.match_text(fit.hole, 'hole')), ('Mil ISO kontrolü', self.match_text(fit.shaft, 'shaft')),
                     ('En yakın ISO çifti', nearest.code + ' (referans)'),
                     ('Toplam limit farkı', r.format_deviation(nearest.distance_nm, unit)),
                     ('En büyük limit farkı', r.format_deviation(nearest.worst_limit_difference_nm, unit)),
                     ('En yakın hazır eşleşme', preset.code + ' (referans)')]
            self.compatibility_label.setText(compatibility)
            self.limits_label.setText('\n'.join(f'{key}: {value}' for key, value in rows[6:14]))
            self.comparison_label.setText(comparison)
            iso_summary = []
            for band, feature, title in ((fit.hole, 'hole', 'Delik'), (fit.shaft, 'shaft', 'Mil')):
                candidates = m.closest_classes(band, feature)
                iso_summary.append(title + ' ' + '/'.join(item.code for item in candidates) +
                                   (' (tam eşleşme)' if candidates[0].exact else ' (tam eşleşme yok; referans)'))
            self.details.setText(explanation + '\nISO kontrolü: ' + ', '.join(iso_summary) +
                                 f'.\nEn yakın çift: {nearest.code}' +
                                 (' (tam eşleşme).' if nearest.distance_nm == 0 else
                                  f' (referans). Toplam limit farkı: {r.format_deviation(nearest.distance_nm, unit)}. '
                                  'Girilen ölçüler ISO sınıfına dönüştürülmez.'))
        rows += [('Şema açıklaması', self.section_help.text()), ('Kapsam', HELP)]
        self.present(rows)
        diagram = self.diagrams['fit']
        if not manual and f.value('view') == 'Montaj kesiti':
            diagram.render_geometry(lambda scene: draw_selection(scene, fit, self.appearance, 1, sample))
        else:
            diagram.render_geometry(lambda scene: draw(scene, fit, f.value('view'), sample, self.appearance, 1))
        self.set_status('Ölçü sınırları güncel. ' + m.usage_hint(fit))
