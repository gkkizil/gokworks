"""Embedded manual SheetMetal assignment, independent calculations and verified jobs."""

import json
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QTabWidget, QTableView, QHBoxLayout

from k_factor import apply as engine
from k_factor.rules import (ManualAssignment, AssignmentTable, Recipe, calculate, number,
                            MATERIALS, DIE_OPENINGS, PUNCH_RADII, TOOL_ANGLES, ba_from_outside_dimensions)
from ..components import BasePage, ValueForm, ResultsPanel, card, scroll, button, label, configure_view
from ..models import TableModel, Column


class KrPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'K faktörü / yarıçap', 'Girdiğiniz K ve R’yi kalınlık eşleştirerek Sac-Levha parametrelerine yazın.')
        self.preview = False
        self.pending_apply = None
        self.summary = None
        self.scan_button = self.action('Montajı tara', self.scan)
        self.apply_button = self.action('Montaja K/R uygula', self.apply, primary=True)
        self.stop_button = self.action('Durdur', self.stop, locked=False)
        self.stop_button.setEnabled(False)
        self.tabs = QTabWidget()
        manual, body = card('Sac kalınlığı → K / R ataması')
        first = {key: str(self.settings.get('kr_manual_' + field, default))
                 for key, field, default in (('thickness', 'thickness', '2'), ('k', 'k', ''), ('r', 'r', ''))}
        try:
            saved_rows = json.loads(self.settings.get('kr_manual_rows', '[]'))
        except (ValueError, TypeError):
            saved_rows = []
        rows = [first] + [{key: str(row.get(key, '')) for key in ('thickness', 'k', 'r')}
                           for row in saved_rows if isinstance(row, dict)] if isinstance(saved_rows, list) else [first]
        self.rows_model = TableModel((Column('Sac kalınlığı (mm)', 'thickness'), Column('K faktörü (0–1)', 'k'),
                                      Column('İç yarıçap R (mm)', 'r')), rows, editable=('thickness', 'k', 'r'))
        self.rows = configure_view(QTableView())
        self.rows.setSortingEnabled(False)
        self.rows.setModel(self.rows_model)
        self.rows_model.edited.connect(self.persist_rows)
        body.addWidget(self.rows, 1)
        actions = QHBoxLayout()
        self.add_row = button('Satır ekle', self.add_assignment)
        self.remove_row = button('Seçili satırı sil', self.remove_assignment)
        actions.addWidget(self.add_row)
        actions.addWidget(self.remove_row)
        actions.addStretch()
        body.addLayout(actions)
        self.save_form = ValueForm(self.settings, 'kr_')
        self.save_files = self.save_form.check('save', 'Parça dosyalarını kaydet', False, persist=False)
        body.addWidget(self.save_form)
        body.addWidget(label('Yalnız ana Sac-Levha K faktörü ve iç yarıçapı değiştirilir. Kalınlık ve özel alt büküm ayarları korunur. Büküm tablosundan değer alınmaz.', 'muted'))
        self.tabs.addTab(manual, 'Manuel K / R')
        helper, helper_body = card('Hesap yardımı · atamadan bağımsız')
        self.helper = ValueForm(self.settings, 'kr_')
        self.helper.combo('material', 'Malzeme', [item.label for item in MATERIALS])
        self.helper.combo('punch', 'Üst bıçak uç R (mm)', [str(value) for value in PUNCH_RADII], '1', editable=True)
        self.helper.combo('die', 'Kalıp V açıklığı (mm)', ['Otomatik (8 × t)'] + [str(value) for value in DIE_OPENINGS], editable=True)
        self.helper.combo('punch_angle', 'Üst bıçak açısı (°)', [str(x) for x in TOOL_ANGLES], '85', editable=True)
        self.helper.combo('die_angle', 'Alt kalıp açısı (°)', [str(x) for x in TOOL_ANGLES], '85', editable=True)
        for key, title, default in (('thickness', 'Numune kalınlığı (mm)', '2'), ('angle', 'Düz sactan büküm açısı (°)', '90'),
                                     ('radius', 'Ölçülmüş iç R (mm, isteğe bağlı)', ''), ('ba', 'Ölçülmüş BA (mm)', ''),
                                     ('outside_a', 'Dış ölçü A (mm)', ''), ('outside_b', 'Dış ölçü B (mm)', ''),
                                     ('flat', 'Ölçülmüş açınım boyu (mm)', '')):
            self.helper.text(key, title, default)
        self.helper.combo('method', 'Hesap yöntemi', ('Tablo', 'BA ölçümü'))
        helper_body.addWidget(self.helper)
        self.calculation_text = label('', 'section')
        helper_body.addWidget(self.calculation_text)
        helper_body.addWidget(label('Hesap sonucu manuel satırlara otomatik aktarılmaz. Üretim değerlerini Manuel K / R bölümüne kendiniz girin.', 'muted'))
        self.tabs.addTab(scroll(helper), 'Hesap yardımı')
        self.results = ResultsPanel(success_label='Uygulandı')
        self.tabs.addTab(self.results, 'Montaj sonuçları')
        self.layout.addWidget(self.tabs, 1)
        self.controls.extend((self.rows, self.add_row, self.remove_row, self.save_form))
        self.helper.changed.connect(self.calculate_helper)
        self.finish_layout()
        self.calculate_helper()

    def persist_rows(self, *args):
        first = self.rows_model.rows[0]
        for key in ('thickness', 'k', 'r'):
            self.settings.set('kr_manual_' + key, first[key])
        self.settings.set('kr_manual_rows', json.dumps(self.rows_model.rows[1:], ensure_ascii=False))

    def add_assignment(self):
        if not self.busy:
            self.rows_model.append([dict(thickness='', k='', r='')])
            self.persist_rows()

    def remove_assignment(self):
        if self.busy:
            return
        index = self.rows.currentIndex()
        if index.isValid() and len(self.rows_model.rows) > 1:
            rows = list(self.rows_model.rows)
            rows.pop(index.row())
            self.rows_model.replace(rows)
            self.persist_rows()

    def recipe(self):
        rows = tuple(ManualAssignment(number(row['thickness'], 'Sac kalınlığı'),
                number(row['k'], 'K faktörü', zero=True), number(row['r'], 'İç yarıçap')) for row in self.rows_model.rows)
        result = AssignmentTable(rows, all_bends=False)
        result.validate()
        return result

    def calculate_helper(self, *args):
        values = self.helper.values()
        try:
            thickness = number(values['thickness'], 'Numune kalınlığı')
            radius = number(values['radius'], 'İç yarıçap') if values['radius'].strip() else None
            measured_ba = None
            if values['method'] == 'BA ölçümü':
                if radius is None:
                    raise ValueError('BA kalibrasyonu için ölçülmüş iç R girin.')
                measured_ba = number(values['ba'], 'Ölçülmüş BA') if values['ba'].strip() else ba_from_outside_dimensions(
                    thickness, radius, values['outside_a'], values['outside_b'], values['flat'], values['angle'])
            material = next(item.key for item in MATERIALS if item.label == values['material'])
            recipe = Recipe(material=material, punch_radius_mm=number(values['punch'], 'Üst bıçak R'),
                die_opening_mm=None if values['die'] == 'Otomatik (8 × t)' else number(values['die'], 'Kalıp V'),
                measured_radius_mm=radius, angle_deg=number(values['angle'], 'Büküm açısı'),
                calibration_thickness_mm=thickness if measured_ba is not None else None, measured_ba_mm=measured_ba,
                punch_angle_deg=number(values['punch_angle'], 'Üst bıçak açısı'), die_angle_deg=number(values['die_angle'], 'Kalıp açısı'))
            self.helper_result = result = calculate(thickness, recipe)
            self.calculation_text.setText(f'K = {result.k_factor:.6g} · İç R = {result.radius_mm:.6g} mm\n'
                f'V = {result.die_opening_mm:g} mm · BA = {result.ba_mm:.9g} mm · BD = {result.bd_mm:.9g} mm\n'
                + '\n'.join(result.notes))
        except (ValueError, StopIteration) as error:
            self.helper_result = None
            self.calculation_text.setText(str(error))

    def set_busy(self, busy):
        super().set_busy(busy)
        if busy and self.preview and self.pending_apply is None:
            self.apply_button.setEnabled(True)

    def scan(self):
        if not self.can_start():
            return
        try:
            recipe = self.recipe()
        except ValueError as error:
            self.tabs.setCurrentIndex(0)
            return self.set_status(error, True)
        self.start_operation(recipe, True, False)

    def apply(self):
        try:
            recipe = self.recipe()
        except ValueError as error:
            self.tabs.setCurrentIndex(0)
            return self.set_status(error, True)
        save = self.save_files.isChecked()
        if self.jobs.busy:
            if self.jobs.owner is self and self.preview:
                self.pending_apply = recipe, save
                self.apply_button.setEnabled(False)
                return self.set_status('Atama sıraya alındı; montaj kontrolü tamamlandıktan sonra başlayacak.')
            return self.can_start()
        self.start_operation(recipe, False, save)

    def start_operation(self, recipe, preview, save, scope=None):
        self.preview, self.summary = preview, None
        self.results.reset()
        self.results.append_log('Montaj kontrolü; değişiklik yapılmaz.' if preview else 'Manuel Sac-Levha ataması başladı.')
        self.results.append_log(' | '.join(f't={row.thickness_mm:g} mm · K={row.k_factor:.12g} · R={row.radius_mm:.12g} mm' for row in recipe.rows))
        self.tabs.setCurrentIndex(2)
        self.jobs.start(self, lambda sink, stop: engine.update_assembly(recipe, sink, stop,
                         preview=preview, save=save, expected_scope=scope))
        self.set_status('Montaj kontrol ediliyor…' if preview else 'K/R değerleri yazılıyor ve geri okunuyor…')

    def stop(self):
        self.pending_apply = None
        self.jobs.cancel()

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'files':
                self.results.files(value)
            elif kind == 'current':
                self.results.model.upsert(dict(source=value, status='running'))
            elif kind == 'result':
                self.results.result(value)
            elif kind in ('phase', 'log'):
                self.set_status(value)
                if kind == 'log':
                    self.results.append_log(value)
            elif kind == 'progress':
                self.progressChanged.emit(*value)
            elif kind == 'done':
                self.summary = value
                if value.get('state') == 'error':
                    self.set_status(value.get('error', 'K/R tamamlanamadı.'), True)
                    self.results.append_log(value.get('error', ''))
                    self.results.tabs.setCurrentIndex(1)
                elif value.get('state') == 'cancelled':
                    self.pending_apply = None
                    self.set_status('K/R işlemi durduruldu; tamamlanan doğrulamalar korundu.')
                else:
                    caption = 'hazır' if self.preview else 'uygulanan'
                    self.set_status(f"{'Kontrol' if self.preview else 'Atama'} tamamlandı · {value.get('succeeded', 0)} {caption}, "
                                    f"{value.get('skipped', 0)} atlanan, {value.get('failed', 0)} hatalı."
                                    + (' K/R uygulanmadı.' if self.preview else ''))
                    if value.get('failed'):
                        self.results.tabs.setCurrentIndex(1)
            elif kind == 'job_error':
                self.pending_apply = None
                self.results.append_log(value['error'])
                self.set_status(value['error'], True)

    def job_finished(self):
        pending, self.pending_apply = self.pending_apply, None
        if pending and self.summary and self.summary.get('state') == 'completed' and self.summary.get('scope'):
            recipe, save = pending
            scope = self.summary['scope']
            QTimer.singleShot(0, lambda: self.start_operation(recipe, False, save, scope))
