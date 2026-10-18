"""ASME GD&T catalogue, native vector frames and measurement comparisons."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView, QLineEdit
from geometric_tolerances.catalog import CATALOG, CHARACTERISTICS, GROUPS, GUIDE, MEASUREMENT_INPUTS
from geometric_tolerances import rules as r
from geometric_tolerances.diagram import draw
from .calculations import CalculationPage
from ..components import configure_view, show_details
from ..models import TreeModel, FilterProxy, Column


class GdtPage(CalculationPage):
    def __init__(self, context):
        super().__init__(context, 'Geometrik toleranslar', 'ASME Y14.5-2018 · Tolerans çerçevesi, bölge ve ölçüm karşılaştırması.', 'gdt_')
        self.action('Okuma rehberi', lambda: show_details(self, 'GD&T rehberi', GUIDE))
        self.kind = self.settings.get('gdt_kind', 'cylindricity')
        if self.kind not in CHARACTERISTICS:
            self.kind = 'cylindricity'
        f = self.form
        f.text('size', 'Gösterim boyutu · mm', '100')
        f.text('tolerance', 'Toplam tolerans t · mm', '0,05')
        f.combo('datum', 'Referans sırası', r.DATUM_CHOICES, 'A')
        f.text('size_tolerance', 'İlgili boyut toleransı · mm', '')
        f.text('measured', 'Ölçülmüş toplam geometrik hata · mm', '')
        f.set_value('measured', '')
        # Measured errors describe this inspection only; never persist them.
        self.settings.values.pop('gdt_measured', None)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Tolerans türü ara…')
        self.extra_layout.addWidget(self.search)
        self.catalog = configure_view(QTreeView())
        self.catalog.setSortingEnabled(False)
        self.catalog.setMinimumHeight(300)
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
        self.update_result()

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
        self.details.setText(item.description + '\n\n' + item.zone + '\n\nMesafe girişinin anlamı: ' + MEASUREMENT_INPUTS.get(item.key, '') + '\n\n' + item.measurement + '\n\n' + item.note + '\n\nKullanım: ' + item.example)
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
        self.summary.setText(f'{item.english} · § {item.reference}\n{assessment}')
        rows = [('Standart', 'ASME Y14.5-2018'), ('Bölüm', item.reference), ('Özellik', item.name), ('Kategori', item.group),
                ('İngilizce', item.english), ('Açıklama', item.description), ('Gösterim boyutu (mm)', r.fmt(spec.size)),
                ('Toplam tolerans t (mm)', r.fmt(spec.tolerance)), ('Referans sırası', ' | '.join(spec.datums) or 'Yok'),
                ('Örnek çerçeve', spec.frame), ('Bölge', item.zone), ('Ölçüm yöntemi', item.measurement),
                ('Üretim notu', item.note), ('Kullanım örneği', item.example), ('Ölçüm girişinin anlamı', MEASUREMENT_INPUTS[item.key]),
                ('İlgili boyut toleransı (mm)', '' if spec.size_tolerance is None else r.fmt(spec.size_tolerance)),
                ('Ölçülmüş toplam hata (mm)', '' if spec.measured is None else r.fmt(spec.measured)),
                ('Aritmetik karşılaştırma', assessment),
                ('Kapsam', 'Öğretici şema. Hata ≤ t karşılaştırması; tam resim/model uygunluğu ve ölçüm belirsizliği değerlendirilmez. Boyut özelliğinde RFS / datum boyut özelliğinde RMB. Şekil-boyut ilişkisi ve MMC zarfı ayrıca kontrol edilir.')]
        self.present(rows)
        for key in ('frame', 'zone'):
            self.diagrams[key].render_geometry(lambda scene, frame=key == 'frame': draw(scene, spec, self.appearance, 1, frame=frame))
        self.set_status(f'ASME Y14.5-2018 · § {item.reference} · {assessment}')
