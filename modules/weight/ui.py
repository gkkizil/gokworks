"""Weight calculator page: section inputs, true-proportion sketch, results, list, cost and CAD mass."""

import json

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLineEdit, QMenu, QMessageBox,
                               QTableView, QWidget)

from gui_qt.calculations import CalculationPage
from gui_qt.components import button, configure_view, fit_columns, label, section_header, show_details
from gui_qt.models import Column, TableModel
from modules.weight import catalog, export, rules as r, sections, worklist
from modules.weight.diagram import draw
from modules.weight.materials import CUSTOM_MATERIAL, MATERIAL_TYPES

DIGITS = ('0', '1', '2', '3', '4')
LIST_KEY = 'weight_worklist'


class WeightPage(CalculationPage):
    def __init__(self, context):
        settings = context.settings
        previous = settings.get('weight_material')
        if isinstance(previous, str) and previous in r.MATERIAL_ALIASES:
            settings.set('weight_material', r.MATERIAL_ALIASES[previous])
        kind = settings.get('weight_kind')
        if isinstance(kind, str) and kind in r.KIND_ALIASES:
            settings.set('weight_kind', r.KIND_ALIASES[kind])
        kind = settings.get('weight_kind')
        if isinstance(kind, str) and kind in r.KINDS:
            settings.set('weight_category', r.category_of(kind))
        super().__init__(context, 'Ağırlık hesabı',
                         'Kesit, standart profil veya CAD modelinden ağırlık; listeye ekleyip maliyet çıkarın.', 'weight_')
        self.info_action('Yöntem ve kaynaklar', self.show_sources)
        f = self.form
        f.combo('category', 'Kesit kategorisi', sections.CATEGORIES, 'Dolu malzeme')
        f.combo('kind', 'Kesit türü', r.KINDS, 'Sac levha')
        f.combo('profile', 'Standart profil', ['—'], '—')
        f.combo('material_group', 'Malzeme grubu', (*r.MATERIAL_GROUPS, 'Özel'), 'Genel')
        f.combo('material', 'Malzeme', r.MATERIALS, 'Demir / Çelik')
        f.text('material_name', 'Malzeme adı', 'Özel malzeme')
        f.text('density', 'Yoğunluk · kg/m³', '7850')
        f.combo('method', 'Hesap yöntemi', r.METHODS)
        f.combo('unit', 'Ölçü birimi', r.UNITS, 'mm')
        for key, value in r.DEFAULT_DIMENSIONS.items():
            if key != 'length':
                f.text(key, r.FIELD_LABELS.get(key, key), f'{value:g}'.replace('.', ','))
        f.combo('corner', 'Köşe biçimi', r.BOX_CORNERS, r.BOX_CORNERS[0])
        f.text('area_cm2', 'Katalog kesit alanı · cm²', '10')
        f.text('length', 'Boy / uzunluk', '1000')
        f.text('count', 'Adet', '1')
        f.combo('mass_unit', 'Sonuç birimi', r.MASS_UNITS, 'kg')
        f.combo('digits', 'Ondalık hassasiyet', DIGITS, '3')
        self.density_label = label('', 'muted')
        self.extra_layout.addWidget(self.density_label)
        self.catalog_hint = label('Profil kataloğundaki kesit alanını cm² olarak girin. Ölçüler yerine bu alan kullanılır.',
                                  'muted')
        self.extra_layout.addWidget(self.catalog_hint)
        self.missing_hint = label('IPN, HL ve 120 mm altı köşebentler için doğrulanmış katalog verisi yok; '
                                  'Açık profil türleriyle ölçü girerek hesaplayın.', 'muted')
        self.extra_layout.addWidget(self.missing_hint)
        self.cad_button = button('Aktif CAD modelinden hesapla', self.read_cad)
        self.cad_button.setToolTip('SOLIDWORKS’te açık parça veya montajın hacmini, malzemesini ve kütlesini okur.')
        self.extra_layout.addWidget(self.cad_button)
        self.cad_label = label('', 'muted')
        self.cad_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.extra_layout.addWidget(self.cad_label)
        self.controls.append(self.cad_button)
        self.cad = None
        self.old_unit = f.value('unit')
        self.current_kind = None
        self._add_section_view()
        self._build_list()
        self.sync_choices()
        self.load_dimensions(self.form.value('kind'))
        self.update_materials()
        self.update_result()

    # ---- per-kind dimensions ------------------------------------------------------------
    def store_dimensions(self, kind):
        """Each section type keeps its own values: 'b' is 1000 mm for a plate, 100 mm for a box."""
        section = sections.SECTION_TYPES.get(kind)
        if section is None:
            return
        values = {item.key: self.form.value(item.key) for item in section.fields}
        values['unit'] = self.form.value('unit')
        self.settings.set('weight_dims/' + kind, values)

    def load_dimensions(self, kind):
        section = sections.SECTION_TYPES.get(kind)
        self.current_kind = kind
        if section is None:
            return
        saved = self.settings.get('weight_dims/' + kind)
        unit = self.form.value('unit')
        factor = 1.0
        if isinstance(saved, dict) and saved.get('unit') in r.UNITS:
            factor = r.UNITS[saved['unit']] / r.UNITS[unit]
        for item in section.fields:
            value = saved.get(item.key) if isinstance(saved, dict) else None
            try:
                number = r.parse_number(value, item.label) * factor if value not in (None, '') else item.default / r.UNITS[unit]
            except ValueError:
                number = item.default / r.UNITS[unit]
            self.form.set_value(item.key, f'{number:.12g}'.replace('.', ','))

    # ---- layout pieces ---------------------------------------------------------------
    def _add_section_view(self):
        diagram = self.add_diagram('section', 'Kesit', width=650, height=330)
        diagram.setMinimumHeight(240)
        diagram.setMaximumHeight(460)
        self.diagram_tabs.setMaximumHeight(460 + self.diagram_tabs.tabBar().sizeHint().height() + 2)

    def _build_list(self):
        self.items = []
        try:
            stored = json.loads(self.settings.get(LIST_KEY, '[]') or '[]')
            self.items = [worklist.Item.from_dict(row) for row in stored]
        except (ValueError, TypeError):
            self.items = []
        self.part_name = QLineEdit(); self.part_name.setPlaceholderText('Parça adı (boşsa kesit adı)')
        self.price = QLineEdit(); self.price.setPlaceholderText('TL/kg'); self.price.setMaximumWidth(90)
        self.price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.add_button = button('Hesaplamaya ekle', self.add_item, primary=True)
        self.export_button = button('Dışa aktar')
        menu = QMenu(self)
        menu.addAction('Excel (.xlsx)…', lambda: self.export_list('xlsx'))
        menu.addAction('PDF…', lambda: self.export_list('pdf'))
        menu.addAction('CSV…', lambda: self.export_list('csv'))
        self.export_button.setMenu(menu)
        self.right.insertWidget(self.right.count() - 1, section_header('Hesaplama listesi', self.export_button))
        row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.part_name, 1); row_layout.addWidget(self.price); row_layout.addWidget(self.add_button)
        self.right.insertWidget(self.right.count() - 1, row)
        columns = (Column('Parça adı', 'name'), Column('Malzeme', 'material'), Column('Kesit / profil', 'section'),
                   Column('Ölçüler', 'dimensions'), Column('Boy · mm', 'length'), Column('Adet', 'count'),
                   Column('Birim · kg', 'unit_mass'), Column('Toplam · kg', 'total_mass'),
                   Column('Fiyat · TL/kg', 'price'), Column('Tutar · TL', 'total_price'))
        self.list_model = TableModel(columns, editable=('name', 'length', 'count', 'price'))
        self.list_model.edited.connect(self.item_edited)
        self.list_view = configure_view(QTableView())
        self.list_view.setModel(self.list_model)
        self.list_view.setSortingEnabled(False)
        self.list_view.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.list_view.setAccessibleName('Hesaplama listesi')
        self.list_view.setMinimumHeight(150); self.list_view.setMaximumHeight(280)
        fit_columns(self.list_view, elastic=0, minimum=120, defaults={4: 80, 5: 55, 6: 80, 7: 85, 8: 80, 9: 90},
                    settings=self.settings, key='weight.list')
        self.right.insertWidget(self.right.count() - 1, self.list_view)
        tools = QWidget(); tools_layout = QHBoxLayout(tools); tools_layout.setContentsMargins(0, 0, 0, 0)
        self.duplicate_button = button('Çoğalt', self.duplicate_item)
        self.remove_button = button('Sil', self.remove_item, destructive=True)
        self.clear_button = button('Listeyi temizle', self.clear_list, flat=True)
        self.scrap = QLineEdit(str(self.settings.get('weight_scrap', '0'))); self.scrap.setMaximumWidth(56)
        self.vat = QLineEdit(str(self.settings.get('weight_vat', '20'))); self.vat.setMaximumWidth(56)
        for edit in (self.scrap, self.vat):
            edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter); edit.textChanged.connect(self.refresh_list)
        tools_layout.addWidget(self.duplicate_button); tools_layout.addWidget(self.remove_button)
        tools_layout.addWidget(self.clear_button); tools_layout.addStretch()
        tools_layout.addWidget(label('Fire %', 'muted')); tools_layout.addWidget(self.scrap)
        tools_layout.addWidget(label('KDV %', 'muted')); tools_layout.addWidget(self.vat)
        self.right.insertWidget(self.right.count() - 1, tools)
        self.totals_label = label('', 'muted')
        self.totals_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.right.insertWidget(self.right.count() - 1, self.totals_label)
        self.controls.extend([self.add_button, self.duplicate_button, self.remove_button, self.clear_button])
        self.refresh_list()

    # ---- choices -----------------------------------------------------------------
    def sync_choices(self):
        """Kind list follows the category; profile list follows a standard family."""
        f = self.form
        category = f.value('category')
        kinds = r.CATEGORY_KINDS.get(category, ())
        box = f.fields['kind']
        current = r.normalise_kind(box.currentText())
        with QSignalBlocker(box):
            box.clear(); box.addItems(list(kinds))
            box.setCurrentText(current if current in kinds else kinds[0])
        kind = box.currentText()
        profile_box = f.fields['profile']
        with QSignalBlocker(profile_box):
            previous = profile_box.currentText()
            profile_box.clear()
            if kind in r.STANDARD_KINDS:
                titles = [p.title for p in r.profiles_for(kind)]
                profile_box.addItems(titles)
                saved = str(self.settings.get('weight_profile', ''))
                profile_box.setCurrentText(previous if previous in titles else saved if saved in titles else titles[0])
            else:
                profile_box.addItem('—')

    def update_materials(self):
        f = self.form
        group = f.value('material_group')
        material = f.fields['material'].currentData() or f.value('material')
        choices = r.MATERIAL_GROUPS.get(group, (CUSTOM_MATERIAL,))
        if material not in choices:
            material = choices[0]
        box = f.fields['material']
        with QSignalBlocker(box):
            box.clear()
            for name in choices:
                if name == CUSTOM_MATERIAL:
                    box.addItem('Özel malzeme · yoğunluğu siz girin', name)
                    continue
                kind = MATERIAL_TYPES.get(name, '')
                box.addItem(f'{name}' + (f' · {kind}' if kind else '') + f' · {r.MATERIALS[name]} kg/m³', name)
            box.setCurrentIndex(list(choices).index(material))
        self.settings.set('weight_material', material)

    def changed(self, key):
        if self.loading:
            return
        self.loading = True
        try:
            if key in ('category', 'kind'):
                if self.current_kind:
                    self.store_dimensions(self.current_kind)
                self.sync_choices()
                if self.form.value('kind') != self.current_kind:
                    self.load_dimensions(self.form.value('kind'))
            if key == 'profile':
                self.settings.set('weight_profile', self.form.value('profile'))
            if key == 'material_group':
                self.update_materials()
            if key == 'material':
                self.settings.set('weight_material', self.form.fields['material'].currentData())
            if key == 'unit':
                new = self.form.value('unit')
                for field in [*r.DEFAULT_DIMENSIONS]:
                    if field not in self.form.fields:
                        continue
                    try:
                        value = r.parse_number(self.form.value(field), 'Ölçü') * r.UNITS[self.old_unit] / r.UNITS[new]
                        self.form.set_value(field, f'{value:.12g}'.replace('.', ','))
                    except ValueError:
                        pass
                self.old_unit = new
        finally:
            self.loading = False
        super().changed(key)

    # ---- calculation -----------------------------------------------------------------
    def inputs(self):
        values = self.form.values()
        values['material'] = self.form.fields['material'].currentData() or values['material']
        for key in ('material_group', 'category', 'mass_unit', 'digits'):
            values.pop(key)
        if values['material'] != CUSTOM_MATERIAL:
            values.pop('density'); values.pop('material_name')
        if values['kind'] not in r.STANDARD_KINDS:
            values.pop('profile')
        return values

    def update_visibility(self, values):
        f = self.form
        kind = values['kind']
        standard = kind in r.STANDARD_KINDS
        geometry = not standard and values.get('method') == 'Ölçülerden'
        section = sections.SECTION_TYPES.get(kind)
        active = {item.key: item.label for item in section.fields} if section else {}
        corner_manual = values.get('corner') == r.BOX_CORNERS[1]
        for key in r.DEFAULT_DIMENSIONS:
            if key == 'length':
                continue
            visible = geometry and key in active and (key not in ('ro', 'ri') or corner_manual)
            f.show_field(key, visible)
            if key in active:
                f.form.labelForField(f.fields[key]).setText(f'{active[key]} · {values["unit"]}')
        f.form.labelForField(f.fields['length']).setText(
            f'{"Boy" if kind != "Sac levha" else "Boy (sac)"} · {values["unit"]}')
        f.show_field('corner', geometry and bool(section and section.options))
        f.show_field('profile', standard)
        f.show_field('method', not standard)
        f.show_field('area_cm2', not standard and not geometry)
        custom = values['material'] == CUSTOM_MATERIAL
        f.show_field('density', custom)
        f.show_field('material_name', custom)
        self.catalog_hint.setVisible(not standard and not geometry)
        self.missing_hint.setVisible(self.form.value('category') == 'Standart profil')

    def update_result(self):
        values = self.inputs()
        self.update_visibility(dict(values, density=self.form.value('density')))
        material = values['material']
        self.density_label.setText('Yoğunluğu malzeme adıyla birlikte siz girin.' if material == CUSTOM_MATERIAL
                                   else f'Sabit yoğunluk: {r.MATERIALS[material]} kg/m³ · farklı değer için Özel seçin.')
        try:
            self.result = result = r.calculate(**values)
        except ValueError as error:
            self.invalid(error)
            return
        self.store_dimensions(values['kind'])
        unit = self.form.value('mass_unit')
        digits = int(self.form.value('digits'))

        def mass(kg):
            return f'{r.fmt_fixed(r.mass_in(kg, unit), digits)} {unit}'
        self.headline.setText(f'{mass(result.total_mass_kg)} · Toplam ağırlık')
        self.summary.setText(f'{mass(result.mass_kg)} / parça · {result.count} adet · '
                             f'{r.fmt_fixed(result.kg_per_m, 3)} kg/m · {result.section_text}')
        note = '' if material == CUSTOM_MATERIAL else r.MATERIAL_NOTES.get(material, '')
        lines = [note] + list(result.notes)
        if result.approximate:
            lines.append('Sonuç yaklaşık geometrik modelle hesaplandı.')
        self.details.setText('\n'.join(line for line in lines if line))
        rows = [('Kesit kategorisi', result.category), ('Kesit / profil', result.section_text),
                ('Malzeme', result.material_label), ('Malzeme türü', MATERIAL_TYPES.get(material, '')),
                ('Yoğunluk (kg/m³)', r.fmt(result.density)), ('Adet', result.count),
                ('Boy (mm)', r.fmt(result.length_mm)),
                ('Kesit alanı (mm²)', r.fmt_fixed(result.area_mm2, 2)),
                ('Kesit alanı (cm²)', r.fmt_fixed(result.area_mm2 / 100, 3)),
                ('Birim boy ağırlığı (kg/m)', r.fmt_fixed(result.kg_per_m, 3)),
                ('Parça hacmi (cm³)', r.fmt_fixed(result.volume_m3 * 1e6, 3)),
                ('Parça hacmi (m³)', r.fmt(result.volume_m3, 9)),
                ('Toplam hacim (m³)', r.fmt(result.total_volume_m3, 9)),
                (f'Parça ağırlığı ({unit})', r.fmt_fixed(r.mass_in(result.mass_kg, unit), digits)),
                (f'Toplam ağırlık ({unit})', r.fmt_fixed(r.mass_in(result.total_mass_kg, unit), digits))]
        rows += [(f'{key} (mm)', r.fmt(value)) for key, value in result.dimensions_mm.items()]
        if result.catalog_kg_m is not None:
            rows.append(('Katalog kg/m (çelik 7850 kg/m³)', r.fmt(result.catalog_kg_m)))
            rows.append(('Katalog kesit alanı (cm²)', r.fmt(result.area_mm2 / 100)))
            difference = (result.geometric_area_mm2 - result.area_mm2) / result.area_mm2 * 100
            rows.append(('Ölçülerden geometrik alan (cm²)',
                         f'{r.fmt_fixed(result.geometric_area_mm2 / 100, 2)} (katalogdan fark %{r.fmt_fixed(difference, 2)})'))
        rows += [('Hesap yöntemi', result.method), ('Standart', result.standard), ('Kaynak', result.source),
                 ('Malzeme kaynağı', r.MATERIAL_SOURCES.get(material, 'Kullanıcı girdisi')), ('Kapsam', r.SCOPE)]
        self.present([row for row in rows if row[1] not in ('', None)])
        self.diagrams['section'].render_geometry(lambda scene: draw(scene, result, self.appearance, 1))
        self.update_cad_comparison()
        self.set_status('Ağırlık güncel.')

    # ---- calculation list --------------------------------------------------------------
    def save_list(self):
        self.settings.set(LIST_KEY, json.dumps([item.to_dict() for item in self.items], ensure_ascii=False))

    def refresh_list(self, *args):
        def num(value, digits):
            return '' if value is None else r.fmt_fixed(value, digits)
        self.list_model.replace([dict(name=i.name, material=i.material, section=i.section, dimensions=i.dimensions,
                                      length=num(i.length_mm, 1), count=str(i.count), unit_mass=num(i.unit_mass_kg, 3),
                                      total_mass=num(i.total_mass_kg, 3), price=num(i.price_per_kg, 2),
                                      total_price=num(i.total_price, 2)) for i in self.items])
        self.settings.set('weight_scrap', self.scrap.text()); self.settings.set('weight_vat', self.vat.text())
        if not self.items:
            self.totals_label.setText('Liste boş. Bir hesap yapıp “Hesaplamaya ekle” ile ekleyin.')
            return
        try:
            t = worklist.totals(self.items, self.scrap.text() or 0, self.vat.text() or 0)
        except ValueError as error:
            self.totals_label.setText(str(error)); return
        text = (f'Toplam {t.count} adet · {r.fmt_fixed(t.mass_kg, 3)} kg · fire dahil '
                f'{r.fmt_fixed(t.mass_with_scrap_kg, 3)} kg')
        if t.unpriced_rows < len(self.items):
            text += (f'\nMalzeme tutarı {r.fmt_fixed(t.net, 2)} TL + KDV {r.fmt_fixed(t.vat, 2)} TL = '
                     f'{r.fmt_fixed(t.gross, 2)} TL')
            if t.unpriced_rows:
                text += f' · {t.unpriced_rows} satırda fiyat yok'
        self.totals_label.setText(text + '\n' + worklist.COST_NOTE)

    def add_item(self):
        if self.result is None:
            self.set_status('Önce geçerli bir hesap yapın.', True); return
        price = None
        if self.price.text().strip():
            try:
                price = r.parse_number(self.price.text(), 'Birim fiyat')
            except ValueError as error:
                self.set_status(str(error), True); return
        try:
            self.items.append(worklist.from_result(self.result, self.part_name.text(), price))
        except ValueError as error:
            self.set_status(str(error), True); return
        self.part_name.clear()
        self.save_list(); self.refresh_list()
        self.list_view.selectRow(len(self.items) - 1)
        self.set_status(f'Listeye eklendi: {self.items[-1].name}')

    def selected_row(self):
        rows = self.list_view.selectionModel().selectedRows() if self.list_view.selectionModel() else []
        return rows[0].row() if rows else None

    def duplicate_item(self):
        row = self.selected_row()
        if row is None:
            self.set_status('Çoğaltmak için listeden bir satır seçin.', True); return
        self.items.insert(row + 1, self.items[row])
        self.save_list(); self.refresh_list(); self.list_view.selectRow(row + 1)

    def remove_item(self):
        row = self.selected_row()
        if row is None:
            self.set_status('Silmek için listeden bir satır seçin.', True); return
        del self.items[row]
        self.save_list(); self.refresh_list()

    def clear_list(self):
        if not self.items:
            return
        if QMessageBox.question(self, 'Listeyi temizle', f'{len(self.items)} satır silinsin mi?') != QMessageBox.Yes:
            return
        self.items = []
        self.save_list(); self.refresh_list()

    def item_edited(self, row, key, value):
        field = {'name': 'name', 'length': 'length_mm', 'count': 'count', 'price': 'price_per_kg'}[key]
        try:
            self.items[row] = worklist.edit(self.items[row], field, value)
            self.set_status('Liste güncellendi.')
        except ValueError as error:
            self.set_status(str(error), True)
        self.save_list(); self.refresh_list()

    def section_image(self):
        """Light, print-ready sketch of the current result (independent of the app theme)."""
        from gui_qt.diagrams import VectorScene
        scene = VectorScene(650, 330)
        draw(scene, self.result, 'Light', 1)
        rect = scene.itemsBoundingRect().adjusted(-8, -8, 8, 8)
        image = QImage(int(rect.width() * 2), int(rect.height() * 2), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        scene.render(painter, source=rect)
        painter.end()
        return image

    def export_list(self, kind):
        if not self.items:
            self.set_status('Dışa aktarmak için önce listeye satır ekleyin.', True); return
        patterns = {'xlsx': 'Excel (*.xlsx)', 'pdf': 'PDF (*.pdf)', 'csv': 'CSV (*.csv)'}
        path, _ = QFileDialog.getSaveFileName(self, 'Ağırlık listesini kaydet', f'GOKWORKS_agirlik.{kind}', patterns[kind])
        if not path:
            return
        try:
            if kind == 'xlsx':
                export.export_xlsx(self.items, path, self.scrap.text() or 0, self.vat.text() or 0)
            elif kind == 'csv':
                export.export_csv(self.items, path, self.scrap.text() or 0, self.vat.text() or 0)
            else:
                export.export_pdf(self.items, path, self.scrap.text() or 0, self.vat.text() or 0,
                                  image=self.section_image() if self.result else None, detail_rows=self.report[:16])
        except (OSError, ValueError, RuntimeError) as error:
            self.set_status(f'Dışa aktarılamadı: {error}', True); return
        self.set_status(f'Kaydedildi: {path}')

    # ---- CAD -------------------------------------------------------------------------------
    def read_cad(self):
        if not self.can_start():
            return
        from modules.weight import cad
        self.cad_label.setText('SOLIDWORKS etkin modeli okunuyor…')
        self.jobs.start(self, cad.worker)

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'weight_cad_phase':
                self.set_status(value)
            elif kind == 'weight_cad':
                self.cad = value
                self.update_cad_comparison()
                self.set_status('CAD modeli kütlesi okundu.')
            elif kind == 'job_error':
                self.cad_label.setText('CAD okuması başarısız: ' + str(value.get('error', '')))
        super().handle_events(events)

    def update_cad_comparison(self):
        cad = self.cad
        if cad is None:
            self.cad_label.setText('Formül hesabından ayrı yöntem: SOLIDWORKS model hacmi × malzeme yoğunluğu.')
            return
        text = (f'CAD modeli ({cad.kind}): {cad.document}' + (f' · {cad.configuration}' if cad.configuration else '') +
                f'\nMalzeme {cad.material} · yoğunluk {r.fmt_fixed(cad.density_kg_m3, 0)} kg/m³'
                f'\nHacim {r.fmt_fixed(cad.volume_m3 * 1e6, 3)} cm³ · kütle {r.fmt_fixed(cad.mass_kg, 3)} kg')
        if self.result is not None and self.result.count == 1:
            difference = (cad.mass_kg - self.result.mass_kg) / self.result.mass_kg * 100
            text += f'\nFormül hesabına göre fark: %{r.fmt_fixed(difference, 2)} (delik, pah ve boşaltmalar dahil)'
        self.cad_label.setText(text + '\n' + ' '.join(cad.notes))

    def show_sources(self):
        material = self.form.fields['material'].currentData()
        docs = catalog.sources()
        catalogue = '\n'.join(f'• {d["manufacturer"]} – {d["document"]} ({d["date"]}, {d["standard"]}): {d["url"]}'
                              for d in docs.values())
        show_details(self, 'Ağırlık hesabı ve kaynaklar',
                     r.SCOPE + '\n\nMalzeme: ' + str(r.MATERIAL_SOURCES.get(material, 'Kullanıcı girdisi')) +
                     '\n\nStandart profil kaynakları:\n' + catalogue +
                     '\n\nDoğrulanmış verisi olmayan aileler: ' + ', '.join(catalog.MISSING))


__all__ = ['WeightPage']
