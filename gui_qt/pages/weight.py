"""Fixed-density material weights and original cross-section geometry."""

from PySide6.QtCore import QSignalBlocker
from weight import rules as r
from weight.materials import MATERIAL_TYPES
from weight.diagram import draw
from .calculations import CalculationPage
from ..components import label, show_details


class WeightPage(CalculationPage):
    def __init__(self, context):
        previous = context.settings.get('weight_material')
        if previous in r.MATERIAL_ALIASES:
            context.settings.set('weight_material', r.MATERIAL_ALIASES[previous])
        super().__init__(context, 'Ağırlık hesabı', 'Kesiti ve malzemeyi seçin; parça ve toplam ağırlığı görün.', 'weight_')
        self.action('Yöntem ve kaynaklar', self.show_sources)
        f = self.form
        f.combo('kind', 'Kesit türü', r.KINDS, 'Sac levha')
        f.combo('material_group', 'Malzeme grubu', r.MATERIAL_GROUPS, 'Genel')
        f.combo('material', 'Malzeme', r.MATERIALS, 'Demir / Çelik')
        f.combo('method', 'Hesap yöntemi', r.METHODS)
        f.combo('unit', 'Ölçü birimi', r.UNITS, 'mm')
        for key, value in r.DEFAULT_DIMENSIONS.items():
            f.text(key, r.FIELD_LABELS[key], str(value))
        f.text('area_cm2', 'Katalog kesit alanı · cm²', '10')
        f.text('count', 'Adet', '1')
        self.density_label = label('', 'subtitle')
        self.extra_layout.addWidget(self.density_label)
        self.old_unit = f.value('unit')
        self.add_diagram('section', 'Kesit şeması')
        self.update_materials()
        self.update_result()

    def update_materials(self):
        f = self.form
        group = f.value('material_group')
        material = f.fields['material'].currentData() or f.value('material')
        choices = r.MATERIAL_GROUPS[group]
        if material not in choices:
            material = choices[0]
        box = f.fields['material']
        with QSignalBlocker(box):
            box.clear()
            for name in choices:
                kind = MATERIAL_TYPES.get(name, '')
                box.addItem(f'{name}' + (f' · {kind}' if kind else '') + f' · {r.MATERIALS[name]} kg/m³', name)
            box.setCurrentIndex(choices.index(material))
        self.settings.set('weight_material', material)

    def changed(self, key):
        if self.loading:
            return
        self.loading = True
        try:
            if key == 'material_group':
                self.update_materials()
            if key == 'material':
                self.settings.set('weight_material', self.form.fields['material'].currentData())
            if key == 'unit':
                new = self.form.value('unit')
                for field in r.DEFAULT_DIMENSIONS:
                    try:
                        value = r._number(self.form.value(field), 'Ölçü') * r.UNITS[self.old_unit] / r.UNITS[new]
                        self.form.set_value(field, f'{value:.12g}'.replace('.', ','))
                    except ValueError:
                        pass
                self.old_unit = new
        finally:
            self.loading = False
        super().changed(key)

    def update_result(self):
        values = self.form.values()
        values['material'] = self.form.fields['material'].currentData()
        values.pop('material_group')
        geometry = values['method'] == 'Ölçülerden'
        for key in r.DEFAULT_DIMENSIONS:
            self.form.show_field(key, key == 'length' or (geometry and key in r.FIELDS[values['kind']]))
        self.form.show_field('area_cm2', not geometry)
        for key in r.DEFAULT_DIMENSIONS:
            self.form.form.labelForField(self.form.fields[key]).setText(f'{r.FIELD_LABELS[key]} · {values["unit"]}')
        material = values['material']
        self.density_label.setText(f'Sabit yoğunluk: {r.MATERIALS[material]} kg/m³')
        try:
            self.result = result = r.calculate(**values)
        except ValueError as error:
            self.invalid(error)
            return
        self.headline.setText(result.total_text + ' · Toplam ağırlık')
        self.summary.setText(f'{result.piece_text} / parça · {result.count} adet · {result.kind}')
        note = r.MATERIAL_NOTES.get(material, '')
        self.details.setText(note + ('\nKeskin köşeli kesit yaklaşımı.' if result.approximate else ''))
        rows = [('Kesit türü', result.kind), ('Malzeme', material), ('Malzeme türü', MATERIAL_TYPES.get(material, '')),
                ('Yoğunluk (kg/m³)', r.fmt(result.density)), ('Adet', result.count),
                ('Boy (mm)', r.fmt(result.length_mm)), ('Kesit alanı (mm²)', r.fmt(result.area_mm2)),
                ('Birim boy ağırlığı (kg/m)', r.fmt(result.kg_per_m)),
                ('Parça hacmi (m³)', r.fmt(result.volume_m3, 9)),
                ('Toplam hacim (m³)', r.fmt(result.total_volume_m3, 9)),
                ('Parça ağırlığı (kg)', r.fmt(result.mass_kg)), ('Toplam ağırlık (kg)', r.fmt(result.total_mass_kg))]
        rows += [(r.FIELD_LABELS[key] + ' (mm)', r.fmt(value)) for key, value in result.dimensions_mm.items()]
        rows += [('Hesap yöntemi', result.method), ('Malzeme notu', note),
                 ('Kaynak', r.MATERIAL_SOURCES.get(material, '')), ('Kapsam', r.SCOPE)]
        self.present(rows)
        self.diagrams['section'].render_geometry(lambda scene: draw(scene, result, self.appearance, 1))
        self.set_status('Ağırlık güncel. Yoğunluk malzemeye göre sabittir.')

    def show_sources(self):
        material = self.form.fields['material'].currentData()
        show_details(self, 'Ağırlık hesabı ve kaynaklar', r.SCOPE + '\n\n' + str(r.MATERIAL_SOURCES.get(material, '')))
