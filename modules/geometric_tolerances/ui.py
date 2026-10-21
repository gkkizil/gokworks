"""ASME GD&T catalogue, native vector frames and measurement comparisons."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QLineEdit, QTabWidget
from modules.geometric_tolerances.catalog import CATALOG, CHARACTERISTICS, GROUPS, GUIDE, MEASUREMENT_INPUTS
from modules.geometric_tolerances import rules as r
from modules.geometric_tolerances.diagram import draw
from gui_qt.calculations import CalculationPage
from gui_qt.components import card, label, scroll, configure_view, show_details
from gui_qt.models import TreeModel, FilterProxy, Column


class GdtPage(CalculationPage):
    def __init__(self, context):
        super().__init__(context, 'Geometrik toleranslar', 'ASME Y14.5-2018 · Tolerans çerçevesi, bölge ve ölçüm karşılaştırması.', 'gdt_')
        self.info_action('Okuma rehberi', lambda: show_details(self, 'GD&T rehberi', GUIDE))
        self.kind = self.settings.get('gdt_kind', 'cylindricity')
        if self.kind not in CHARACTERISTICS:
            self.kind = 'cylindricity'
        f = self.form
        f.text('size', 'Gösterim boyutu · mm', '100')
        f.text('tolerance', 'Toplam tolerans t · mm', '0,05')
        f.combo('datum', 'Referans sırası', r.DATUM_CHOICES, 'A')
        f.text('size_tolerance', 'İlgili boyut toleransı · mm', '')
        f.text('measured', 'Toplam geometrik hata · mm', '')
        f.set_value('measured', '')
        # Measured errors describe this inspection only; never persist them.
        self.settings.values.pop('gdt_measured', None)
        self.datum_help = label('', 'muted')
        self.size_rule_help = label('Toplam boyut toleransı, üst ve alt ölçü sınırlarının farkıdır. '
                                    'ASME 8.4: bu yüzey örneğinde geometrik tolerans bu değerden küçük olmalıdır. '
                                    'MMC zarfı burada ölçülmez.', 'muted')
        self.extra_layout.addWidget(self.datum_help)
        f.fields['size_tolerance'].setToolTip(self.size_rule_help.text())
        self.search = QLineEdit()
        self.search.setPlaceholderText('Tolerans türü ara…')
        self.extra_layout.addWidget(self.search)
        self.catalog = configure_view(QTreeView())
        self.catalog.setSortingEnabled(False)
        self.catalog.setMinimumHeight(200)
        self.catalog_model = TreeModel((Column('Tolerans türü', 'name'),))
        rows = [dict(id=group, parent='', name=group) for group in GROUPS]
        rows += [dict(id=item.key, parent=item.group, name=f'{item.name} · {item.english}' + (' (eski)' if not item.active else ''), key=item.key,
                      example=item.example) for item in CATALOG]
        self.catalog_model.replace(rows)
        self.catalog_proxy = FilterProxy(self, tree=True)
        self.catalog_proxy.setSourceModel(self.catalog_model)
        self.catalog.setModel(self.catalog_proxy)
        self.catalog.expandAll()
        self.catalog.clicked.connect(self.select_kind)
        self.search.textChanged.connect(self.catalog_proxy.set_query)
        self.extra_layout.addWidget(self.catalog)
        self.add_diagram('frame', 'Tolerans çerçevesi', height=120)
        self.add_diagram('zone', 'Tolerans bölgesi', height=300)
        self.diagram_tabs.setCurrentIndex(1)
        self.right.removeWidget(self.details)
        self.measurement_label = label()
        self.measurement_hint = label('', 'muted')
        self.note_label = label()
        self.assessment_label = label()
        panel, body = card()
        self.explanation_tabs = QTabWidget()
        overview = QWidget()
        overview_body = QVBoxLayout(overview)
        overview_body.setContentsMargins(8, 8, 8, 8)
        overview_body.setSpacing(8)
        for widget in (self.details, self.measurement_hint, self.assessment_label):
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            overview_body.addWidget(widget)
        self.explanation_tabs.addTab(overview, 'Anlam ve kontrol')
        for title, widget in (('Ölçüm rehberi', self.measurement_label),
                              ('Üretim notu', self.note_label),
                              ('Boyut ilişkisi', self.size_rule_help)):
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.explanation_tabs.addTab(scroll(widget), title)
        body.addWidget(self.explanation_tabs)
        self.right.insertWidget(self.right.indexOf(self.diagram_tabs) + 1, panel)
        self.update_result()

    @staticmethod
    def assessment_text(spec):
        relation = (f'Boyut ilişkisi: t < {r.fmt(spec.size_tolerance)} mm kontrol edildi; MMC zarfı ölçülmedi.\n'
                    if spec.size_tolerance is not None else
                    'Boyut toleransı girilmedi. ASME Kural 1 kapsamındaki boyut ve şekil ilişkisini ayrıca kontrol edin.\n'
                    if spec.characteristic.group == 'Şekil' else '')
        if spec.measured is None:
            return relation + ('Ölçüm girilmedi. İlgili özellik için değerlendirilmiş toplam geometrik hatayı girin; '
                               'tek çap veya nokta ölçüsü yeterli değildir.')
        verdict = 'Girilen hata tolerans içinde' if spec.accepted else 'Girilen hata tolerans dışında'
        if spec.margin == 0:
            verdict += ' · tam sınırda'
        return (relation + f'{verdict}\nHata {r.fmt(spec.measured)} mm; sınır {r.fmt(spec.tolerance)} mm.\n'
                f'Kalan pay: {r.fmt(spec.margin)} mm.\n'
                'Yalnızca hata ≤ t karşılaştırması; tam resim/model uygunluğu, ölçüm belirsizliği ve kalite kabulü değerlendirilmez.')

    def invalid(self, error):
        super().invalid(error)
        self.assessment_label.setText('Geçerli belirtim olmadan karşılaştırma yapılmaz.')

    def changed(self, key):
        if key == 'measured':
            self.settings.values.pop('gdt_measured', None)
        super().changed(key)

    def select_kind(self, index):
        row = index.data(Qt.UserRole)
        if row and 'key' in row:
            self.kind = row['key']
            self.settings.set('gdt_kind', self.kind)
            self.form.set_value('measured', '')
            self.form.set_value('size_tolerance', '')
            self.update_result()

    def update_result(self):
        item = CHARACTERISTICS[self.kind]
        f = self.form
        self.details.setText(item.description + '\n\nTolerans bölgesi: ' + item.zone)
        self.measurement_label.setText('Ölçüm girişinin anlamı: ' + MEASUREMENT_INPUTS.get(
            item.key, 'Eski işaret için güncel ölçüm karşılaştırması yapılmaz.') + '\n\n' + item.measurement)
        self.measurement_hint.setText('Ölçüm girişi: ' + MEASUREMENT_INPUTS.get(
            item.key, 'Eski işaret için güncel ölçüm karşılaştırması yapılmaz.'))
        f.fields['measured'].setToolTip(self.measurement_label.text())
        self.note_label.setText(item.note + '\n\nKullanım örneği: ' + item.example)
        self.datum_help.setText({
            'none': 'Şekil toleransında referans (datum) kullanılmaz.',
            'optional': 'Referans seçimi isteğe bağlıdır. Teorik ölçüler ve profil ayrıca tanımlanmalıdır.',
            'required': 'Bu örnek referans gerektirir. A, B, C sırası referans önceliğini belirler.'}[item.datum])
        self.size_rule_help.setVisible(item.group == 'Şekil')
        self.explanation_tabs.setTabVisible(3, item.group == 'Şekil')
        f.fields['datum'].setEnabled(item.active and item.datum != 'none')
        f.show_field('size_tolerance', item.group == 'Şekil')
        for key in ('size', 'tolerance', 'measured', 'size_tolerance'):
            f.fields[key].setEnabled(item.active)
        if not item.active:
            self.invalid('ASME 2018’de kaldırılmış sembol. Güncel çerçeve veya bölge üretilmez.')
            self.headline.setText(item.name + ' · Eski sembol')
            return
        try:
            self.result = spec = r.specify(self.kind, *(f.value(key) for key in ('size', 'tolerance', 'datum', 'measured', 'size_tolerance')))
        except ValueError as error:
            self.invalid(error)
            return
        self.headline.setText(item.name + ' · ' + ('Øt' if item.diametrical else 't') + ' = ' + r.fmt(spec.tolerance) + ' mm')
        assessment = ('Ölçüm girilmedi.' if spec.accepted is None else
                      ('Tolerans içinde' if spec.accepted else 'Tolerans dışında') + f' · Kalan pay: {r.fmt(spec.margin)} mm')
        amount = (f'\nRadyal pay: {r.fmt(spec.tolerance/2)} mm' if item.diametrical else
                  f'\nNormal sınır: ±{r.fmt(spec.tolerance/2)} mm' if item.group == 'Profil' else '')
        self.summary.setText(f'{item.english} · § {item.reference}\n{assessment}' + amount)
        self.assessment_label.setText(self.assessment_text(spec))
        rows = [('Standart', 'ASME Y14.5-2018'), ('Bölüm', item.reference), ('Özellik', item.name), ('Kategori', item.group),
                ('İngilizce', item.english), ('Açıklama', item.description), ('Gösterim boyutu (mm)', r.fmt(spec.size)),
                ('Toplam tolerans t (mm)', r.fmt(spec.tolerance)), ('Referans sırası', ' | '.join(spec.datums) or 'Yok'),
                ('Örnek çerçeve', spec.frame), ('Bölge', item.zone), ('Ölçüm yöntemi', item.measurement),
                ('Üretim notu', item.note), ('Kullanım örneği', item.example), ('Ölçüm girişinin anlamı', MEASUREMENT_INPUTS[item.key]),
                ('İlgili boyut toleransı (mm)', '' if spec.size_tolerance is None else r.fmt(spec.size_tolerance)),
                ('Ölçülmüş toplam hata (mm)', '' if spec.measured is None else r.fmt(spec.measured)),
                ('Aritmetik karşılaştırma', assessment),
                ('Ölçüm değerlendirmesi', self.assessment_label.text()),
                ('Referans açıklaması', self.datum_help.text()),
                ('Kapsam', 'Öğretici şema. Hata ≤ t karşılaştırması; tam resim/model uygunluğu ve ölçüm belirsizliği değerlendirilmez. Boyut özelliğinde RFS / datum boyut özelliğinde RMB. Şekil-boyut ilişkisi ve MMC zarfı ayrıca kontrol edilir.')]
        self.present(rows)
        for key in ('frame', 'zone'):
            self.diagrams[key].render_geometry(lambda scene, frame=key == 'frame': draw(scene, spec, self.appearance, 1, frame=frame))
        self.set_status(f'ASME Y14.5-2018 · § {item.reference} · {assessment}')
