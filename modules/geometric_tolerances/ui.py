"""ASME GD&T catalogue, native vector frames and measurement comparisons."""

from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import QFormLayout, QWidget, QVBoxLayout, QLineEdit, QTabWidget
from modules.geometric_tolerances.catalog import CATALOG, CHARACTERISTICS, GUIDE, MEASUREMENT_INPUTS
from modules.geometric_tolerances import rules as r
from modules.geometric_tolerances.diagram import draw
from gui_qt.calculations import CalculationPage
from gui_qt.calculations import pane
from gui_qt.components import Disclosure, label, scroll, show_details
from gui_qt.models import FilterProxy
from modules.geometric_tolerances.catalog_view import CatalogModel, CatalogView, LEGACY_GROUP


class GdtPage(CalculationPage):
    def __init__(self, context):
        super().__init__(context, 'Geometrik toleranslar', 'ASME Y14.5-2018 · Tolerans çerçevesi, bölge ve ölçüm karşılaştırması.', 'gdt_')
        self.info_action('Okuma rehberi', lambda: show_details(self, 'GD&T rehberi', GUIDE))
        self.kind = self.settings.get('gdt_kind', 'cylindricity')
        if not isinstance(self.kind, str) or self.kind not in CHARACTERISTICS:   # damaged settings value
            self.kind = 'cylindricity'
        f = self.form
        # Display labels only; the settings keys (gdt_size, gdt_tolerance, ...) stay as they were.
        f.text('size', 'Parça boyutu (şema için) · mm', '100')
        f.text('tolerance', 'Tolerans t · mm', '0,05')
        f.combo('datum', 'Referans sırası (datum)', r.DATUM_CHOICES, 'A')
        f.text('measured', 'Ölçülen sapma · mm', '')
        f.text('size_tolerance', 'Boyut toleransı · mm', '')
        f.set_value('measured', '')
        # Measured errors describe this inspection only; never persist them.
        self.settings.values.pop('gdt_measured', None)
        for key, hint in (('size', '100'), ('tolerance', '0,05'), ('measured', 'boş: karşılaştırma yapılmaz'),
                          ('size_tolerance', 'boş: kontrol edilmez')):
            f.fields[key].setPlaceholderText(hint)
            f.fields[key].setAlignment(Qt.AlignRight | Qt.AlignVCenter)     # numbers align right, also when empty
            f.fields[key].setClearButtonEnabled(False)
        self.datum_help = label('', 'muted')
        self.measurement_hint = label('', 'muted')
        self.size_rule_help = label('Toplam boyut toleransı, üst ve alt ölçü sınırlarının farkıdır. '
                                    'ASME 8.4: bu yüzey örneğinde geometrik tolerans bu değerden küçük olmalıdır. '
                                    'MMC zarfı burada ölçülmez.', 'muted')
        f.fields['size_tolerance'].setToolTip(self.size_rule_help.text())
        # 3 · Ölçüm kontrolü: the optional inspection inputs, in their own collapsible group.
        measure = QWidget()
        self.measure_form = QFormLayout(measure)
        self.measure_form.setContentsMargins(0, 0, 0, 0)
        self.measure_form.setSpacing(8)
        self.measure_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.measure_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for key in ('measured', 'size_tolerance'):
            taken = f.form.takeRow(f.fields[key])
            self.measure_form.addRow(taken.labelItem.widget(), taken.fieldItem.widget())
        self.measure_section = Disclosure('Ölçüm kontrolü (isteğe bağlı)', measure,
                                          expanded=bool(f.value('size_tolerance').strip()))
        self.extra_layout.addWidget(self.measure_section)
        # One note under every input: a short help text, or the rule message when the value is rejected.
        self.notes = {'size': label('Yalnız şemanın ölçeğini belirler; toleransı etkilemez.', 'muted'),
                      'tolerance': label('Çerçevedeki toplam bölge genişliği; Ø işaretli türlerde bölgenin çapı.', 'muted'),
                      'datum': self.datum_help, 'measured': self.measurement_hint,
                      'size_tolerance': label('Üst ve alt ölçü sınırı farkı. ASME 8.4: t bundan küçük olmalı.', 'muted')}
        self.note_text = {key: note.text() for key, note in self.notes.items()}
        for key, note in self.notes.items():
            layout = f.form if key in ('size', 'tolerance', 'datum') else self.measure_form
            row, _ = layout.getWidgetPosition(f.fields[key])
            layout.insertRow(row + 1, note)
        # 1 · Tolerans türü: the first choice, at the top of the parameter panel.
        self.search = QLineEdit()
        self.search.setPlaceholderText('Tolerans türü ara… (ör. diklik, runout)')
        self.search.setClearButtonEnabled(True)
        self.catalog = CatalogView()
        self.catalog.setMinimumHeight(260)
        self.catalog.setMaximumHeight(380)
        self.catalog_model = CatalogModel(self)
        self.catalog_model.set_appearance(self.appearance)
        self.catalog.delegate.appearance = self.appearance
        self.catalog_proxy = FilterProxy(self, tree=True)
        self.catalog_proxy.setSourceModel(self.catalog_model)
        self.catalog.setModel(self.catalog_proxy)
        self.expand_catalog()
        self.catalog.selectionModel().currentChanged.connect(lambda index, *_: self.select_kind(index))
        self.search.textChanged.connect(self.search_catalog)
        panel_layout = self.input_card.layout()
        panel_layout.itemAt(0).widget().setText('Tolerans türü')        # pane heading of CalculationPage
        for position, widget in enumerate((self.search, self.catalog, label('Tolerans çerçevesi', 'section')), 1):
            panel_layout.insertWidget(position, widget)
        self.show_kind()
        self.add_diagram('frame', 'Tolerans çerçevesi', height=120)
        self.add_diagram('zone', 'Tolerans bölgesi', height=300)
        self.diagram_tabs.setCurrentIndex(1)
        self.right.removeWidget(self.details)
        self.measurement_label = label()
        self.note_label = label()
        self.assessment_label = label()
        panel, body = pane(rule=True)
        self.explanation_tabs = QTabWidget()
        overview = QWidget()
        overview_body = QVBoxLayout(overview)
        overview_body.setContentsMargins(8, 8, 8, 8)
        overview_body.setSpacing(8)
        for widget in (self.details, self.assessment_label):
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

    # Rule messages begin with the rule's own input name; under the field that name is redundant.
    RULE_PREFIXES = ('Toplam tolerans t: ', 'Gösterim boyutu: ', 'İlgili boyut toleransı: ', 'Toplam geometrik hata: ')

    @staticmethod
    def _restyle(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def clear_field_errors(self):
        for key, note in self.notes.items():
            note.setText(self.note_text[key])
            note.setProperty('role', 'muted')
            self._restyle(note)
            field = self.form.fields[key]
            if field.property('invalid'):
                field.setProperty('invalid', False)
                self._restyle(field)

    def show_field_error(self, error):
        """Put a rule message under the input it concerns and outline that input in red."""
        key = getattr(error, 'field', None)
        if key not in self.notes:
            return
        message = str(error)
        for prefix in self.RULE_PREFIXES:
            if message.startswith(prefix):
                message = message[len(prefix):]
        note, field = self.notes[key], self.form.fields[key]
        note.setText(message)
        note.setProperty('role', 'error')
        self._restyle(note)
        field.setProperty('invalid', True)
        self._restyle(field)
        if key in ('measured', 'size_tolerance'):
            self.measure_section.set_expanded(True)

    def invalid(self, error):
        super().invalid(error)
        self.assessment_label.setText('Geçerli belirtim olmadan karşılaştırma yapılmaz.')

    def changed(self, key):
        if key == 'measured':
            self.settings.values.pop('gdt_measured', None)
        super().changed(key)

    def expand_catalog(self):
        """All groups open; the deleted ASME 2018 symbols stay closed until searched for."""
        self.catalog.expandAll()
        legacy = self.catalog_proxy.mapFromSource(self.catalog_model.index_of(LEGACY_GROUP))
        if legacy.isValid() and not self.search.text().strip() and self.kind not in {
                item.key for item in CATALOG if item.group == LEGACY_GROUP}:
            self.catalog.collapse(legacy)

    def search_catalog(self, text):
        self.catalog_proxy.set_query(text)
        self.expand_catalog()
        self.show_kind()

    def show_kind(self):
        index = self.catalog_proxy.mapFromSource(self.catalog_model.index_of(self.kind))
        if index.isValid():
            self.catalog.selectionModel().setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            self.catalog.scrollTo(index)

    def theme_changed(self):
        self.catalog_model.set_appearance(self.appearance)
        self.catalog.delegate.appearance = self.appearance
        self.catalog.viewport().update()
        super().theme_changed()

    def select_kind(self, index):
        row = index.data(Qt.UserRole)
        if row and 'key' in row and row['key'] != self.kind:
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
        self.note_text['measured'] = MEASUREMENT_INPUTS.get(
            item.key, 'Eski işaret için güncel ölçüm karşılaştırması yapılmaz.')
        f.fields['measured'].setToolTip(self.measurement_label.text())
        self.note_label.setText(item.note + '\n\nKullanım örneği: ' + item.example)
        self.note_text['datum'] = {
            'none': 'Şekil toleransında referans (datum) kullanılmaz.',
            'optional': 'İsteğe bağlı. Teorik ölçüler ve profil ayrıca tanımlanmalıdır.',
            'required': '* Zorunlu. A, A | B, A | B | C sırası referans önceliğini belirler.'}[item.datum]
        caption = f.form.labelForField(f.fields['datum'])
        caption.setText('Referans sırası (datum)' + (' *' if item.datum == 'required' else ''))
        self.clear_field_errors()
        self.size_rule_help.setVisible(item.group == 'Şekil')
        self.explanation_tabs.setTabVisible(3, item.group == 'Şekil')
        f.fields['datum'].setEnabled(item.active and item.datum != 'none')
        form_kind = item.group == 'Şekil'          # the size relation (ASME 8.4) only exists for form tolerances
        self.measure_form.setRowVisible(f.fields['size_tolerance'], form_kind)
        self.notes['size_tolerance'].setVisible(form_kind)
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
            self.show_field_error(error)
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
