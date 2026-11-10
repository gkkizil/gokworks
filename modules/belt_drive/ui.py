"""Kayış–Kasnak Tasarımı page: manual design, automatic search, catalogue, comparison.

The page is a thin Qt layer over the existing engine. It never computes belt
mathematics itself, never promotes PROVISIONAL / NOT_EVALUATED states, and
invalidates every shown result as soon as an input changes.
"""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHeaderView, QLineEdit, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from gui_qt.components import BasePage, Disclosure, NumberSpinBox, button, label, scroll, section_header, turkish_locale
from gui_qt.theme import COLORS, ROW_HEIGHT
from shared.files import write_text_atomic

from . import controller
from .calculation import calculate
from .catalog.importers import load_catalog
from .catalog.profiles import get_profile
from .design_models import DesignRequest
from .design_serialization import DesignProject, project_dumps, project_loads, report_to_dict
from .models import (BeltDriveSpecification, BeltSpecification, CenterSpecification, LoadSpecification,
                     PulleySpecification, SpecificationError)
from .nominal_design import NominalSizingOptions, NominalSizingReport, NominalCandidate
from .serialization import MAX_JSON_SIZE
from .ui_support import (BUNDLED_CATALOGS, CANDIDATE_TITLES, CAPACITY_TITLES, FAMILY_TITLES, METRIC_TITLES,
                         PRIORITY_TITLES, REJECTION_TITLES, SEVERITY_TITLES, SEVERITY_TOKENS, SOURCE_TITLES,
                         load_bundled, number, profile_title, profiles, project_job, pulley_pairs_job, tosyali_audit)
from .view import BeltCanvas

import json

STALE = 'Girdiler değişti; önceki sonuç geçersiz.'


# ---- small widgets ------------------------------------------------------------------------
def real(value, low, high, decimals=3, *, empty=None, step=1.):
    """Number field. ``empty`` names the minimum as 'not given' (shown as text, read as None)."""
    box = NumberSpinBox(decimals); box.setRange(low, high); box.setSingleStep(step)
    if empty:
        box.setSpecialValueText(empty)
    box.setValue(value)
    return box


def whole(value, low, high, *, empty=None):
    box = QSpinBox(); box.setLocale(turkish_locale()); box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    box.setRange(low, high)
    if empty:
        box.setSpecialValueText(empty)
    box.setValue(value)
    return box


def optional(box):
    """None when a field with special 'empty' text sits on its minimum."""
    return None if box.specialValueText() and box.value() == box.minimum() else box.value()


def table(headers, *, stretch=None):
    view = QTableWidget(0, len(headers)); view.setHorizontalHeaderLabels(headers)
    view.verticalHeader().setVisible(False); view.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    view.setEditTriggers(QAbstractItemView.NoEditTriggers); view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setSelectionMode(QAbstractItemView.SingleSelection); view.setShowGrid(False); view.setWordWrap(False)
    view.setAlternatingRowColors(True)
    header = view.horizontalHeader(); header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.setHighlightSections(False); header.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch is not None:
        header.setSectionResizeMode(stretch, QHeaderView.Stretch)
    view.setMinimumHeight(90)
    return view


def fill(view, rows, colours=None):
    view.setRowCount(0)
    for r, row in enumerate(rows):
        view.insertRow(r)
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value)); item.setToolTip(str(value))
            if colours and colours[r] and c == 0:
                item.setForeground(QColor(colours[r]))
            view.setItem(r, c, item)


class Workspace(QStackedWidget):
    """Parameters | 2D view | results side by side; three tabs on narrow windows."""

    def __init__(self, panels, titles, sizes=(300, 520, 360), threshold=1000):
        super().__init__()
        self.panels, self.titles, self.sizes, self.threshold = panels, titles, sizes, threshold
        self.compact_mode = False
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        for panel in panels:
            self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(1, 1); self.splitter.setSizes(list(sizes))
        self.tabs = QTabWidget(); self.addWidget(self.splitter); self.addWidget(self.tabs)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < self.threshold
        if compact == self.compact_mode:
            if not compact and not getattr(self, '_fitted', False) and self.width() > 0:
                self._fitted = True; self.fit_sizes()
            return
        self.compact_mode = compact
        if compact:
            for panel, title in zip(self.panels, self.titles):
                self.tabs.addTab(panel, title)
            self.tabs.setCurrentIndex(1); self.setCurrentWidget(self.tabs)
        else:
            while self.tabs.count():
                self.tabs.removeTab(0)
            for panel in self.panels:
                self.splitter.addWidget(panel); panel.show()
            self.setCurrentWidget(self.splitter); self.fit_sizes()

    def fit_sizes(self):
        total = max(self.width(), sum(self.sizes))
        scale = total / sum(self.sizes)
        self.splitter.setSizes([int(size * scale) for size in self.sizes])


def panel(*widgets, margins=(6, 6, 6, 6)):
    host = QWidget(); box = QVBoxLayout(host); box.setContentsMargins(*margins); box.setSpacing(6)
    for widget in widgets:
        if isinstance(widget, int):
            box.addStretch(widget)
        else:
            box.addWidget(widget)
    return host


def form():
    layout = QFormLayout(); layout.setRowWrapPolicy(QFormLayout.WrapLongRows); layout.setSpacing(6)
    host = QWidget(); host.setLayout(layout); layout.setContentsMargins(0, 0, 0, 0)
    return host, layout


# ---- the page -----------------------------------------------------------------------------
class BeltDrivePage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Kayış–Kasnak Tasarımı',
                         'V ve triger-senkron kayışta nominal hesap, katalogdan otomatik tasarım ve karşılaştırma. '
                         'Üretim onayı vermez.')
        self.manual_result = None
        self._ready=False
        self.nominal_options=NominalSizingOptions()
        self.catalog = None; self.catalog_key = None; self.catalog_title = ''
        self.request = None; self.report = None; self.pairs = None
        self.compare_ids = []
        self.search_token = 0; self.running = None
        self.open_button = self.action('Proje aç…', self.open_project)
        self.save_button = self.action('Projeyi kaydet…', self.save_project)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.build_manual(), 'Manuel Tasarım')
        self.tabs.addTab(self.build_auto(), 'Otomatik Tasarım')
        self.tabs.addTab(self.build_catalog(), 'Katalog ve Kaynaklar')
        self.tabs.addTab(self.build_compare(), 'Tasarım Karşılaştırma')
        self.layout.addWidget(self.tabs, 1)
        self.finish_layout()
        self.manual_timer = QTimer(self); self.manual_timer.setSingleShot(True); self.manual_timer.setInterval(120)
        self.manual_timer.timeout.connect(self.calculate_manual)
        self.family_changed(); self.load_mode_changed(); self.center_mode_changed()
        self.select_catalog(0)
        self._ready=True
        self.calculate_manual()

    # ======================================================================================
    # Manual design
    # ======================================================================================
    def build_manual(self):
        belt_host, belt = form()
        self.family = QComboBox()
        for key in ('v', 'timing'):
            self.family.addItem(FAMILY_TITLES[key], key)
        self.family.setAccessibleName('Kayış ailesi')
        self.profile = QComboBox(); self.profile.setAccessibleName('Kayış profili')
        self.pitch_label = label('', 'muted')
        belt.addRow('Kayış ailesi', self.family); belt.addRow('Profil', self.profile); belt.addRow('', self.pitch_label)
        self.count = whole(1, 1, 100000)

        pulley_host, pulley = form()
        self.d1 = real(100., .000001, 1e7, 6); self.d2 = real(200., .000001, 1e7, 6)
        self.z1 = whole(20, 1, 1000000); self.z2 = whole(40, 1, 1000000)
        self.d1_row = ('Sürücü datum çapı D₁ · mm', self.d1); self.d2_row = ('Sürülen datum çapı D₂ · mm', self.d2)
        for title, widget in (self.d1_row, self.d2_row, ('Sürücü diş sayısı z₁', self.z1), ('Sürülen diş sayısı z₂', self.z2)):
            pulley.addRow(title, widget)
        self.pulley_form = pulley

        load_host, load = form()
        self.load_mode = QComboBox(); self.load_mode.addItem('Güç P (tork hesaplanır)', 'power')
        self.load_mode.addItem('Tork T₁ (güç hesaplanır)', 'torque'); self.load_mode.setAccessibleName('Birincil yük girdisi')
        self.rpm = real(1450., .000001, 1e7, 6)
        self.power = real(5., .000001, 1e9, 6); self.torque = real(30., .000001, 1e10, 6)
        self.efficiency = real(0., 0., 1., 6, empty='verilmedi', step=.01)
        self.service = real(0., 0., 1000., 6, empty='verilmedi', step=.1)
        for title, widget in (('Giriş devri n₁ · dev/dak', self.rpm), ('Yük girişi', self.load_mode),
                              ('Giriş gücü P · kW', self.power), ('Giriş torku T₁ · N·m', self.torque)):
            load.addRow(title, widget)
        self.load_form = load

        center_host, center = form()
        self.center_mode = QComboBox()
        self.center_mode.addItem('Eksen mesafesi C → kayış uzunluğu', 'center')
        self.center_mode.addItem('Seçilen kayış uzunluğu → eksen mesafesi', 'length')
        self.center_mode.setAccessibleName('Eksen yöntemi')
        self.distance = real(400., .000001, 1e8, 6); self.length = real(1300., .000001, 1e9, 6)
        self.belt_teeth = whole(110, 1, 100000000)
        self.angle = real(0., -360., 360., 6)
        self.origin_x = real(0., -1e8, 1e8, 6); self.origin_y = real(0., -1e8, 1e8, 6)
        self.rotation = QComboBox(); self.rotation.addItem('Saat yönünün tersi (CCW)', 'ccw'); self.rotation.addItem('Saat yönü (CW)', 'cw')
        self.pretension = real(0., 0., 1e10, 6, empty='verilmedi')
        for title, widget in (('Ne biliniyor?', self.center_mode), ('Eksen mesafesi C · mm', self.distance),
                              ('Datum uzunluğu Ld · mm', self.length), ('Kayış diş adedi N', self.belt_teeth)):
            center.addRow(title, widget)
        self.center_form = center
        self.length_hint = label('', 'muted')
        advanced_host, advanced = form()
        for title, widget in (('Kayış adedi (V, kullanıcı seçimi)', self.count), ('Verim η', self.efficiency),
                              ('Servis faktörü K', self.service), ('Kayış başına ön germe F₀ · N', self.pretension),
                              ('Sürücü dönüş yönü', self.rotation), ('Eksen açısı · °', self.angle),
                              ('Sürücü merkezi X · mm', self.origin_x), ('Sürücü merkezi Y · mm', self.origin_y)):
            advanced.addRow(title, widget)
        self.advanced_form = advanced
        advanced_box = panel(advanced_host, label('Boş bırakılan verim, servis faktörü ve ön germe için otomatik katsayı atanmaz; '
                                                  'ilgili sonuçlar "değerlendirilmedi" olur.', 'muted'), margins=(0, 0, 0, 0))
        self.manual_advanced = Disclosure('Gelişmiş ayarlar (isteğe bağlı)', advanced_box)

        inputs = panel(label('Kayış ve kasnak ölçülerini, devri ve gücü girin; sonuç anında hesaplanır.', 'muted'),
                       label('1 · Kayış', 'section'), belt_host, label('2 · Kasnaklar', 'section'), pulley_host,
                       label('3 · Devir ve yük', 'section'), load_host, label('4 · Eksen mesafesi veya kayış boyu', 'section'),
                       center_host, self.length_hint, self.manual_advanced, 1)
        self.manual_inputs = inputs
        self.manual_scroll = scroll(inputs); self.manual_scroll.setMinimumWidth(250)
        self.manual_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls.append(inputs)

        self.canvas = BeltCanvas()
        self.animate = button('Nominal hareketi göster')
        self.animate.setCheckable(True); self.animate.toggled.connect(self.canvas.set_animating)
        self.canvas.animationChanged.connect(self.sync_animation_button)
        viewer = panel(section_header('Kayış güzergâhı', self.animate), self.canvas,
                       label('Animasyon yalnız nominal kinematiktir: kaymasız, rijit; iki kasnak aynı yönde, ω₂ = ω₁/i.', 'muted'))
        viewer.layout().setStretch(1, 1)

        self.manual_status = label('', 'muted')
        self.summary = table(['Sonuç', 'Değer'], stretch=0); self.summary.horizontalHeader().hide()
        self.result_table = table(['Büyüklük', 'Değer', 'Birim'], stretch=0); self.result_table.setMinimumHeight(260)
        self.check_table = QTextBrowser(); self.check_table.setAccessibleName('Mühendislik kontrolleri')
        self.check_table.setMinimumHeight(220)
        self.assumptions = QTextBrowser(); self.assumptions.setMinimumHeight(120)
        self.all_results = Disclosure('Tüm sonuçlar', self.result_table)
        self.checks_box = Disclosure('Kontrol edilmeyen konular', self.check_table)
        self.assumption_box = Disclosure('Hesap varsayımları', self.assumptions)
        result_body = panel(self.summary, self.all_results, self.checks_box, self.assumption_box, 1, margins=(0, 0, 0, 0))
        results = panel(label('Sonuçlar', 'section'), self.manual_status, scroll(result_body))
        results.layout().setStretch(2, 1)
        self.manual_workspace = Workspace((self.manual_scroll, viewer, results), ('Parametreler', 'Görünüm', 'Sonuçlar'), (300, 560, 420))

        for widget in (self.family, self.profile, self.load_mode, self.center_mode, self.rotation):
            widget.currentIndexChanged.connect(self.manual_changed)
        for widget in (self.count, self.d1, self.d2, self.z1, self.z2, self.rpm, self.power, self.torque, self.efficiency,
                       self.service, self.distance, self.length, self.belt_teeth, self.angle, self.pretension,
                       self.origin_x, self.origin_y):
            widget.valueChanged.connect(self.manual_changed)
        self.family.currentIndexChanged.connect(self.family_changed)
        self.load_mode.currentIndexChanged.connect(self.load_mode_changed)
        self.center_mode.currentIndexChanged.connect(self.center_mode_changed)
        return self.manual_workspace

    @Slot(bool)
    def sync_animation_button(self, on):
        # A QObject-bound slot is disconnected when the page is destroyed;
        # an anonymous closure retained the page through canvas teardown.
        blocked = self.animate.blockSignals(True)
        try:
            self.animate.setChecked(on)
        finally:
            self.animate.blockSignals(blocked)

    def _row_visible(self, layout, widget, visible):
        layout.setRowVisible(widget, visible)

    def family_changed(self, *args):
        family = self.family.currentData()
        current = self.profile.currentData()
        self.profile.blockSignals(True); self.profile.clear()
        for profile in profiles(family):
            self.profile.addItem(profile_title(profile), profile.key)
        index = self.profile.findData(current)
        self.profile.setCurrentIndex(index if index >= 0 else (self.profile.findData('A') if family == 'v' else self.profile.findData('HTD_5M')))
        self.profile.blockSignals(False)
        timing = family == 'timing'
        for widget in (self.d1, self.d2):
            self._row_visible(self.pulley_form, widget, not timing)
        for widget in (self.z1, self.z2):
            self._row_visible(self.pulley_form, widget, timing)
        self.center_mode_changed()
        self.manual_changed()

    def load_mode_changed(self, *args):
        power = self.load_mode.currentData() == 'power'
        self._row_visible(self.load_form, self.power, power); self._row_visible(self.load_form, self.torque, not power)

    def center_mode_changed(self, *args):
        by_length = self.center_mode.currentData() == 'length'
        timing = self.family.currentData() == 'timing'
        self._row_visible(self.center_form, self.distance, not by_length)
        self._row_visible(self.center_form, self.length, by_length and not timing)
        self._row_visible(self.center_form, self.belt_teeth, by_length and timing)

    def manual_specification(self):
        """Current inputs as a BeltDriveSpecification. Only one primary load is passed."""
        timing = self.family.currentData() == 'timing'
        profile = self.profile.currentData()
        by_length = self.center_mode.currentData() == 'length'
        power_mode = self.load_mode.currentData() == 'power'
        return BeltDriveSpecification(
            belt=BeltSpecification(self.family.currentData(), profile, None, 1 if timing else self.count.value()),
            driver=PulleySpecification(None, self.z1.value()) if timing else PulleySpecification(self.d1.value(), None),
            driven=PulleySpecification(None, self.z2.value()) if timing else PulleySpecification(self.d2.value(), None),
            load=LoadSpecification(self.rpm.value(), self.power.value() if power_mode else None,
                                   None if power_mode else self.torque.value(), optional(self.efficiency), optional(self.service)),
            center=CenterSpecification('length' if by_length else 'center', None if by_length else self.distance.value(),
                                       self.length.value() if by_length and not timing else None,
                                       self.belt_teeth.value() if by_length and timing else None,
                                       self.origin_x.value(), self.origin_y.value(), self.angle.value()),
            pretension_per_belt_n=optional(self.pretension), rotation=self.rotation.currentData())

    def set_manual_specification(self, spec):
        """Load a specification into the form (from a project or a chosen candidate)."""
        widgets = (self.family, self.profile, self.load_mode, self.center_mode, self.rotation, self.count, self.d1, self.d2,
                   self.z1, self.z2, self.rpm, self.power, self.torque, self.efficiency, self.service, self.distance,
                   self.length, self.belt_teeth, self.angle, self.pretension, self.origin_x, self.origin_y)
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.family.setCurrentIndex(self.family.findData(spec.belt.family))
        finally:
            self.family.blockSignals(False)
        self.family_changed()
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.profile.setCurrentIndex(self.profile.findData(spec.belt.profile))
            self.count.setValue(spec.belt.count)
            if spec.belt.family == 'timing':
                self.z1.setValue(spec.driver.teeth); self.z2.setValue(spec.driven.teeth)
            else:
                self.d1.setValue(spec.driver.datum_diameter_mm); self.d2.setValue(spec.driven.datum_diameter_mm)
            load = spec.load
            self.load_mode.setCurrentIndex(self.load_mode.findData('power' if load.power_kw is not None else 'torque'))
            self.rpm.setValue(load.input_rpm)
            if load.power_kw is not None:
                self.power.setValue(load.power_kw)
            else:
                self.torque.setValue(load.torque_nm)
            self.efficiency.setValue(load.efficiency or 0.); self.service.setValue(load.service_factor or 0.)
            center = spec.center
            self.center_mode.setCurrentIndex(self.center_mode.findData(center.mode))
            if center.distance_mm is not None:
                self.distance.setValue(center.distance_mm)
            if center.length_mm is not None:
                self.length.setValue(center.length_mm)
            if center.belt_teeth is not None:
                self.belt_teeth.setValue(center.belt_teeth)
            self.angle.setValue(center.axis_angle_deg)
            self.origin_x.setValue(center.driver_x_mm); self.origin_y.setValue(center.driver_y_mm)
            self.rotation.setCurrentIndex(self.rotation.findData(spec.rotation))
            self.pretension.setValue(spec.pretension_per_belt_n or 0.)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self.load_mode_changed(); self.center_mode_changed()
        self.calculate_manual()
        shown = self.manual_specification()
        if shown != spec:
            # A value outside a field's range/precision must never change the design silently.
            changed = self._differences(spec, shown)
            self.set_status('Bazı değerler ekran alanlarına sığmadığı için değişti; kontrol edin: ' + '; '.join(changed), True)
            return False
        return True

    @staticmethod
    def _differences(original, shown):
        from dataclasses import fields, is_dataclass
        out = []
        def walk(a, b, path):
            if is_dataclass(a):
                for f in fields(a):
                    walk(getattr(a, f.name), getattr(b, f.name), path + [f.name])
            elif a != b:
                out.append(f'{".".join(path)}: {a} → {b}')
        walk(original, shown, [])
        return out[:6]

    def manual_changed(self, *args):
        if self.manual_result is not None:
            self.manual_result = None
            self.canvas.set_drive(None, STALE)
            self.manual_status.setText(STALE)
        self.manual_timer.start()

    def calculate_manual(self):
        self.manual_timer.stop()
        profile = self.profile.currentData()
        if profile:
            p = get_profile(profile)
            self.pitch_label.setText(f'Adım p = {number(p.pitch_mm)} mm · bölüm çizgisi' if p.family == 'timing'
                                     else 'Datum çapı ve datum uzunluğu ile hesaplanır.')
            if p.family == 'timing':
                self.length_hint.setText(f'Bölüm uzunluğu Lp = N × p = {number(self.belt_teeth.value() * p.pitch_mm)} mm')
            else:
                self.length_hint.setText('')
        try:
            result = calculate(self.manual_specification())
        except SpecificationError as error:
            self.manual_result = None
            self.canvas.set_drive(None, 'Tasarım hesaplanamadı. Sağdaki hataları düzeltin.')
            self.manual_status.setText('Hesap yapılamadı; girdileri düzeltin.')
            fill(self.result_table, []); fill(self.summary, [])
            self.show_checks([(item.code, item.message, 'ERROR') for item in error.issues])
            self.assumptions.clear()
            return None
        self.show_manual(result)
        return result

    def show_manual(self, r):
        self.manual_result = r
        self.canvas.set_drive(r)
        timing = r.specification.belt.family == 'timing'
        self.manual_status.setText('Nominal hesap güncel. Bu sonuç güç kapasitesi, ömür veya üretim onayı değildir.')
        fill(self.summary, [
            ('Çıkış devri' + (' (ideal, kayma hariç)' if not timing else ''), f'{number(r.nominal_output_rpm, 1)} dev/dak'),
            ('Aktarma oranı', number(r.ratio, 3)),
            ('Kayış boyu' + (' (bölüm)' if timing else ' (datum)'), f'{number(r.length_exact_mm, 1)} mm'
             + (f' · {number(r.selected_belt_teeth or r.theoretical_belt_teeth, 2)} diş' if timing else '')),
            ('Eksen mesafesi', f'{number(r.center_mm, 1)} mm'),
            ('Kayış hızı', f'{number(r.speed_m_s, 2)} m/s'),
            ('Küçük kasnakta sarılma', f'{number(min(r.driver_wrap_deg, r.driven_wrap_deg), 1)}°'),
            ('Giriş torku', f'{number(r.input_torque_nm, 2)} N·m'),
        ])
        rows = [
            ('Referans çizgisi', 'bölüm çizgisi' if r.reference_line == 'pitch' else 'datum', ''),
            ('Sürücü referans çapı D₁', number(r.driver_reference_diameter_mm), 'mm'),
            ('Sürülen referans çapı D₂', number(r.driven_reference_diameter_mm), 'mm'),
            ('Aktarma oranı i', number(r.ratio, 5), ''),
            ('İdeal çıkış devri n₂ (kayma hariç)' if not timing else 'Nominal çıkış devri n₂', number(r.nominal_output_rpm), 'dev/dak'),
            ('Giriş gücü P', number(r.input_power_kw, 4), 'kW'),
            ('Giriş torku T₁', number(r.input_torque_nm, 4), 'N·m'),
            ('İdeal çıkış torku T₂', number(r.ideal_output_torque_nm, 4), 'N·m'),
            ('η ile çıkış gücü', number(r.efficiency_output_power_kw, 4) if r.efficiency_output_power_kw is not None else 'değerlendirilmedi', 'kW'),
            ('η ile çıkış torku (nominal devirde)', number(r.efficiency_output_torque_nm, 4) if r.efficiency_output_torque_nm is not None else 'değerlendirilmedi', 'N·m'),
            ('Tasarım gücü P·K', number(r.design_power_kw, 4) if r.design_power_kw is not None else 'değerlendirilmedi', 'kW'),
            ('Kayış hızı v', number(r.speed_m_s, 4), 'm/s'),
            ('Etkin kuvvet farkı Ft = F₁ − F₂', number(r.effective_force_delta_n, 2), 'N'),
            ('Tasarım etkin kuvvet farkı', number(r.design_force_delta_n, 2) if r.design_force_delta_n is not None else 'değerlendirilmedi', 'N'),
            ('Eksen mesafesi C', number(r.center_mm, 4), 'mm'),
            ('Kayış uzunluğu (tam)', number(r.length_exact_mm, 4), 'mm'),
            ('Yaklaşık formül uzunluğu', number(r.length_approximate_mm, 4), 'mm'),
            ('Yaklaşık − tam', number(r.approximation_minus_exact_mm, 4), 'mm'),
        ]
        if r.selected_length_mm is not None:
            rows += [('Seçilen uzunluk', number(r.selected_length_mm, 4), 'mm'),
                     ('Ters çözüm kalanı', number(r.inverse_residual_mm, 9), 'mm')]
        rows += [('Sürücü sarılma açısı β₁', number(r.driver_wrap_deg, 3), '°'),
                 ('Sürülen sarılma açısı β₂', number(r.driven_wrap_deg, 3), '°')]
        if timing:
            rows += [('Teorik kayış diş adedi L/p', number(r.theoretical_belt_teeth, 4), 'diş'),
                     ('Seçilen kayış diş adedi', number(r.selected_belt_teeth), 'diş'),
                     ('Kavrayan diş tahmini (sürücü)', number(r.engaged_driver_teeth_estimate, 2), 'diş'),
                     ('Kavrayan diş tahmini (sürülen)', number(r.engaged_driven_teeth_estimate, 2), 'diş')]
        forces = r.shaft_forces
        if forces is None:
            rows.append(('Mil bileşke kuvveti', 'değerlendirilmedi (F₀ verilmedi)', ''))
        else:
            rows += [('Gergin kol F₁ (kayış başına)', number(forces.tight_per_belt_n, 2), 'N'),
                     ('Gevşek kol F₂ (kayış başına)', number(forces.slack_per_belt_n, 2), 'N'),
                     ('Sürücü mili kuvveti Fx / Fy', f'{number(forces.driver_fx_n, 2)} / {number(forces.driver_fy_n, 2)}', 'N'),
                     ('Mil bileşke kuvveti (basitleştirilmiş)', number(forces.resultant_n, 2), 'N')]
        fill(self.result_table, rows)
        self.show_checks([(i.code, i.message, i.severity) for i in r.checks])
        self.assumptions.setPlainText('\n'.join('• ' + a for a in r.assumptions))

    def show_checks(self, items):
        """Severity first; NOT_EVALUATED keeps a neutral colour and is never shown as passed."""
        colours = COLORS[self.context.appearance]
        order = {'ERROR': 0, 'WARNING': 1, 'NOT_EVALUATED': 2, 'INFO': 3}
        html = []
        for code, message, severity in sorted(items, key=lambda x: order.get(x[2], 9)):
            colour = colours[SEVERITY_TOKENS.get(severity, 'muted')]
            html.append(f'<p style="margin:0 0 4px 0"><span style="color:{colour}"><b>{SEVERITY_TITLES.get(severity, severity)}</b></span>'
                        f' · <code>{code}</code><br>{message}</p>')
        self.check_table.setHtml(''.join(html))
        count = lambda severity: sum(1 for _, _, sev in items if sev == severity)
        errors, warnings, missing = count('ERROR'), count('WARNING'), count('NOT_EVALUATED')
        parts = ([f'Hatalar ({errors})'] if errors else []) + ([f'Uyarılar ({warnings})'] if warnings else []) \
            + [f'Kontrol edilmeyen konular ({missing})']
        self.checks_box.toggle.setText(' · '.join(parts))
        if errors or warnings:
            self.checks_box.set_expanded(True)
        self.check_codes = tuple((code, severity) for code, message, severity in items)

    # ======================================================================================
    # Automatic design
    # ======================================================================================
    def build_auto(self):
        host, f = form()
        self.a_basis=QComboBox()
        self.a_basis.addItem('Genel boyutlandırma · katalog gerekmez','nominal')
        self.a_basis.addItem('Katalogdan ürün seçimi','catalog')
        self.a_basis.setAccessibleName('Otomatik tasarım yöntemi')
        f.addRow('Hesap yöntemi',self.a_basis)
        self.a_power = real(1.5, .0001, 1e6, 4); self.a_rpm = real(1450., .001, 100000., 3); self.a_target = real(700., .001, 100000., 3)
        self.a_family = QComboBox()
        for key in ('v', 'timing'):
            self.a_family.addItem(FAMILY_TITLES[key], key)
        self.a_profile = QComboBox(); self.a_manufacturer = QComboBox(); self.a_series = QComboBox()
        self.a_mode = QComboBox()
        for key, title in (('auto', 'Otomatik (katalogdaki tüm seçenekler)'), ('fixed', 'Sabit C ± tolerans'), ('range', 'C aralığı')):
            self.a_mode.addItem(title, key)
        self.a_target_c = real(400., 0., 1e6, 2, empty='otomatik'); self.a_tolerance = real(0., -1., 1e5, 3, empty='verilmedi')
        self.a_cmin = real(0., 0., 1e6, 2, empty='verilmedi'); self.a_cmax = real(0., 0., 1e6, 2, empty='verilmedi')
        self.a_rpm_error = real(1., -1., 100., 3, empty='sınırsız')
        for title, widget in (('Motor gücü P · kW', self.a_power), ('Giriş devri n₁ · dev/dak', self.a_rpm),
                              ('İstenen çıkış devri · dev/dak', self.a_target), ('İzin verilen devir sapması · %', self.a_rpm_error),
                              ('Kayış ailesi', self.a_family), ('Profil / kesit',self.a_profile), ('Eksen mesafesi', self.a_mode), ('C hedefi · mm', self.a_target_c),
                              ('C toleransı ± mm', self.a_tolerance), ('C en az · mm', self.a_cmin), ('C en çok · mm', self.a_cmax)):
            f.addRow(title, widget)
        self.auto_form = f
        self.a_length_policy=QComboBox()
        self.a_length_policy.addItem('Tercihli boy seç; C mesafesini yeniden çöz','preferred')
        self.a_length_policy.addItem('C mesafesinden gerekli teorik boyu hesapla','required')
        f.addRow('Kayış boyu',self.a_length_policy)
        limits_host, limits = form()
        self.auto_limits_form=limits
        self.a_dmin = real(0., 0., 1e5, 2, empty='sınırsız'); self.a_dmax = real(0., 0., 1e5, 2, empty='sınırsız')
        self.a_odmax = real(0., 0., 1e5, 2, empty='sınırsız')
        self.a_zmin = whole(0, 0, 10000, empty='sınırsız'); self.a_zmax = whole(0, 0, 10000, empty='sınırsız')
        self.a_width = real(0., 0., 1e5, 2, empty='sınırsız'); self.a_belts = whole(0, 0, 100, empty='sınırsız')
        self.a_install = real(-1., -1., 1e5, 2, empty='bilinmiyor')
        self.a_tension = real(-1., -1., 1e5, 2, empty='bilinmiyor')
        self.a_service = real(0., 0., 10., 3, empty='verilmedi', step=.1)
        for title, widget in (('Üretici', self.a_manufacturer), ('Seri', self.a_series),
                              ('Çap en az · mm', self.a_dmin),
                              ('Çap en çok · mm', self.a_dmax), ('Dış çap en çok · mm', self.a_odmax),
                              ('Diş sayısı en az', self.a_zmin), ('Diş sayısı en çok', self.a_zmax),
                              ('Toplam eksenel genişlik en çok · mm', self.a_width), ('Kayış adedi en çok', self.a_belts),
                              ('Kurulum ayar mesafesi · mm', self.a_install), ('Germe ayar mesafesi · mm', self.a_tension),
                              ('Servis faktörü (isteğe bağlı)', self.a_service)):
            limits.addRow(title, widget)
        rank_host, rank = form()
        self.a_priority = QComboBox()
        for key, title in PRIORITY_TITLES:
            self.a_priority.addItem(title, key)
        rank.addRow('Sıralama önceliği', self.a_priority)
        self.weights = {}
        for key, title in METRIC_TITLES:
            box = real(1. if key in ('speed', 'center', 'area', 'belts') else 0., 0., 100., 2, step=.5)
            self.weights[key] = box; rank.addRow(f'Ağırlık · {title}', box)
        self.rank_form = rank
        self.a_unverified = QCheckBox('Doğrulanmamış adayları göster')
        self.a_unverified.setChecked(False)
        self.a_unverified.setToolTip('Üretici kapasite onayı olmayan adaylar ayrı grupta listelenir.')
        self.a_result_limit = whole(200, 1, 5000); self.a_work_limit = whole(50000, 100, 1000000)
        rank.addRow('', self.a_unverified); rank.addRow('Sonuç sınırı', self.a_result_limit)
        rank.addRow('İş adımı sınırı (hesap bütçesi)', self.a_work_limit)
        self.search_button = button('Tasarım ara', self.start_search, primary=True)
        self.search_button.setToolTip('Katalogdaki kasnak ve kayışlardan tam tasarımlar arar.')
        self.pairs_button = button('Yalnız kasnak çifti ara', self.start_pairs)
        self.pairs_button.setToolTip('Kayış ürünü olmayan kataloglar için: yalnız devir oranına uyan kasnak çiftleri. Tam aktarım değildir.')
        self.auto_catalog_label = label('', 'muted')
        advanced = panel(label('Filtreler ve sınırlar', 'section'), limits_host, label('Sıralama ve kapsam', 'section'), rank_host,
                         label('Boş sınırlar gizli varsayılanla doldurulmaz.', 'muted'), margins=(0, 0, 0, 0))
        self.auto_advanced = Disclosure('Gelişmiş ayarlar (filtre, sınır, sıralama)', advanced)
        inputs = panel(label('Motor gücü ve hedef devre göre kasnakları ve gerekli kayış boyunu hesaplayın. '
                             'Ürün koduyla seçim için katalog yöntemini kullanın.', 'muted'), self.auto_catalog_label, host,
                       self.search_button, self.pairs_button, self.auto_advanced, 1)
        self.auto_inputs = inputs
        self.auto_scroll = scroll(inputs); self.auto_scroll.setMinimumWidth(260)
        self.auto_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls += [inputs]

        self.coverage = label('Henüz arama yapılmadı.', 'muted')
        self.candidates = table(['Sürücü', 'Sürülen', 'Kayış / boy', 'Çıkış devri · dev/dak', 'Sapma %', 'C · mm',
                                 'Adet / genişlik', 'Kapasite', 'Durum'])
        self.candidates.itemSelectionChanged.connect(self.candidate_selected)
        self.pair_banner = label('Kasnak çifti sonuçları tam aktarım değildir: kayış ürünü, gerçekleşen C ve kapasite seçilmedi.', 'muted')
        self.pair_table = table(['Sürücü', 'Sürülen', 'z₁', 'z₂', 'Oran', 'İdeal n₂ · dev/dak', 'Sapma %', 'Seri'])
        self.result_stack = QStackedWidget()
        self.result_stack.addWidget(self.candidates)
        self.result_stack.addWidget(panel(self.pair_banner, self.pair_table, margins=(0, 0, 0, 0)))
        self.auto_canvas = BeltCanvas()
        self.auto_canvas.set_drive(None, 'Bir tam tasarım adayı seçin.')
        middle = QSplitter(Qt.Vertical); middle.addWidget(panel(section_header('Adaylar'), self.coverage, self.result_stack))
        middle.addWidget(self.auto_canvas); middle.setSizes([360, 260])
        self.to_manual = button('Manuel ekrana aktar', self.transfer_to_manual)
        self.add_compare = button('Karşılaştırmaya ekle', self.add_to_compare)
        self.to_manual.setEnabled(False); self.add_compare.setEnabled(False)
        self.candidate_details = QTextBrowser()
        self.rejections = table(['Elenme nedeni', 'Adet'], stretch=0)
        self.rejection_box = Disclosure('Elenen kombinasyonlar', self.rejections)
        details = panel(label('Seçilen aday', 'section'), self.to_manual, self.add_compare, self.candidate_details,
                        self.rejection_box)
        details.layout().setStretch(3, 1)
        self.auto_workspace = Workspace((self.auto_scroll, middle, details), ('İstek', 'Adaylar', 'Ayrıntı'), (300, 620, 340))

        for widget in (self.a_family, self.a_profile, self.a_manufacturer, self.a_series, self.a_mode, self.a_priority):
            widget.currentIndexChanged.connect(self.auto_changed)
        for widget in (self.a_power, self.a_rpm, self.a_target, self.a_target_c, self.a_tolerance, self.a_cmin, self.a_cmax,
                       self.a_rpm_error, self.a_dmin, self.a_dmax, self.a_odmax, self.a_zmin, self.a_zmax, self.a_width,
                       self.a_belts, self.a_install, self.a_tension, self.a_service, self.a_result_limit, self.a_work_limit,
                       *self.weights.values()):
            widget.valueChanged.connect(self.auto_changed)
        self.a_unverified.toggled.connect(self.auto_changed)
        self.a_family.currentIndexChanged.connect(self.auto_family_changed)
        self.a_mode.currentIndexChanged.connect(self.auto_mode_changed)
        self.a_priority.currentIndexChanged.connect(self.priority_changed)
        self.a_basis.currentIndexChanged.connect(self.basis_changed)
        self.a_length_policy.currentIndexChanged.connect(self.auto_changed)
        self.auto_family_changed(); self.basis_changed()
        return self.auto_workspace

    def nominal_mode(self):
        return self.a_basis.currentData()=='nominal'

    def basis_changed(self,*args):
        nominal=self.nominal_mode()
        if not nominal and self.catalog is not None:
            families={get_profile(p.profile).family for p in (*self.catalog.belts,*self.catalog.pulleys)}
            if families and self.a_family.currentData() not in families:
                self.a_family.setCurrentIndex(self.a_family.findData(sorted(families)[0]))
        self.a_mode.setItemText(0,'Otomatik · C isteğe bağlı' if nominal else 'Otomatik · katalogdaki seçenekler')
        self.auto_form.setRowVisible(self.a_length_policy,nominal)
        for widget in (self.a_manufacturer,self.a_series,self.a_odmax,self.a_width,self.a_belts,self.a_install,self.a_tension):
            self.auto_limits_form.setRowVisible(widget,not nominal)
        self.a_unverified.setEnabled(not nominal)
        self.a_unverified.setToolTip('Katalog adaylarının görünürlüğüdür; genel hesap sonuçları her zaman gösterilir.')
        for i in range(self.a_priority.count()):
            self.a_priority.model().item(i).setEnabled(not nominal or self.a_priority.itemData(i) not in ('capacity','fewest_belts'))
        if nominal and self.a_priority.currentData() in ('capacity','fewest_belts'):
            self.a_priority.setCurrentIndex(0)
        self.search_button.setText('Hesapla ve boyutlandır' if nominal else 'Katalogdan tasarım ara')
        self.search_button.setToolTip('Katalog olmadan çap, devir, uzunluk ve C hesaplar.' if nominal else 'Katalogdaki gerçek kayış ve kasnakları eşleştirir.')
        self.pairs_button.setVisible(not nominal)
        self.auto_family_changed();self.auto_mode_changed();self.priority_changed();self.auto_changed()
        self.update_auto_hint()

    def update_auto_hint(self):
        if self.nominal_mode():
            scope=(f'R40 çap arama kapsamı varsayılan {number(self.nominal_options.diameter_min_mm)}–{number(self.nominal_options.diameter_max_mm)} mm'
                   if self.a_family.currentData()=='v' else
                   f'Kasnak diş arama kapsamı varsayılan {self.nominal_options.teeth_min}–{self.nominal_options.teeth_max}')
            self.auto_catalog_label.setText('Genel hesap; ürün kodu gerekmez. '+scope+' (gelişmiş ayarlardan değişir). '
                'C boşsa D₁+D₂ başlangıç mesafesi kullanılır. Kesit/adet güç tablosuyla seçilmiş sayılmaz.')
        elif self.catalog is not None:
            self.auto_catalog_label.setText(f'Katalog: {self.catalog_title} — {len(self.catalog.pulleys)} kasnak, '
                f'{len(self.catalog.belts)} kayış, {len(self.catalog.ratings)} kapasite tablosu.')

    def use_catalog_mode(self):
        if self.nominal_mode():self.a_basis.setCurrentIndex(self.a_basis.findData('catalog'))
        else:self.basis_changed()

    def auto_family_changed(self, *args):
        family = self.a_family.currentData()
        current=self.a_profile.currentData()
        self.a_profile.blockSignals(True); self.a_profile.clear()
        if not self.nominal_mode():self.a_profile.addItem('Tümü',None)
        for profile in profiles(family):
            self.a_profile.addItem(profile_title(profile), profile.key)
        index=self.a_profile.findData(current)
        fallback='A' if family=='v' else 'HTD_5M'
        self.a_profile.setCurrentIndex(index if index>=0 else self.a_profile.findData(fallback) if self.nominal_mode() else 0)
        self.a_profile.blockSignals(False)
        self.fill_catalog_filters()
        self.update_auto_hint()

    def auto_mode_changed(self, *args):
        mode = self.a_mode.currentData()
        # Only the fields of the chosen mode are shown and sent; nothing hidden is applied.
        self.auto_form.setRowVisible(self.a_target_c, mode == 'fixed' or mode=='auto' and self.nominal_mode() or self.a_priority.currentData()=='center')
        self.auto_form.setRowVisible(self.a_tolerance, mode == 'fixed')
        self.auto_form.setRowVisible(self.a_cmin, mode == 'range'); self.auto_form.setRowVisible(self.a_cmax, mode == 'range')

    def priority_changed(self, *args):
        balanced = self.a_priority.currentData() == 'balanced'
        for box in self.weights.values():
            self.rank_form.setRowVisible(box, balanced)
        if self.nominal_mode():
            for key,box in self.weights.items():self.rank_form.setRowVisible(box,balanced and key in ('speed','center','area'))
        self.auto_mode_changed()

    def fill_catalog_filters(self):
        if not hasattr(self, 'a_manufacturer'):
            return
        family = self.a_family.currentData()
        manufacturers, series = set(), set()
        if self.catalog is not None:
            for item in (*self.catalog.belts, *self.catalog.pulleys):
                if get_profile(item.profile).family == family:
                    manufacturers.add(self.catalog.source(item.source_id).manufacturer); series.add(item.series_id)
        for box, values in ((self.a_manufacturer, manufacturers), (self.a_series, series)):
            current = box.currentData()
            box.blockSignals(True); box.clear(); box.addItem('Tümü', None)
            for value in sorted(values):
                box.addItem(value, value)
            index = box.findData(current); box.setCurrentIndex(index if index >= 0 else 0)
            box.blockSignals(False)

    def design_request(self):
        mode = self.a_mode.currentData()
        priority = self.a_priority.currentData()
        nominal=self.nominal_mode()
        weights = tuple((k,b.value()) for k,b in self.weights.items() if b.value()>0 and
            (not nominal or k in ('speed','center','area'))) if priority=='balanced' else ()
        if priority == 'balanced' and not weights:
            raise ValueError('Dengeli sıralamada en az bir ağırlık 0\'dan büyük olmalı.')
        target_c = optional(self.a_target_c) if mode=='fixed' or priority=='center' or nominal and mode=='auto' else None
        return DesignRequest(
            power_kw=self.a_power.value(), input_rpm=self.a_rpm.value(), target_rpm=self.a_target.value(),
            family=self.a_family.currentData(), profile=self.a_profile.currentData(),
            manufacturer=None if nominal else self.a_manufacturer.currentData(), series_id=None if nominal else self.a_series.currentData(), mode=mode,
            center_target_mm=target_c, center_min_mm=optional(self.a_cmin) if mode == 'range' else None,
            center_max_mm=optional(self.a_cmax) if mode == 'range' else None,
            center_tolerance_mm=optional(self.a_tolerance) if mode == 'fixed' else None,
            diameter_min_mm=optional(self.a_dmin), diameter_max_mm=optional(self.a_dmax),
            outside_diameter_max_mm=None if nominal else optional(self.a_odmax), teeth_min=optional(self.a_zmin), teeth_max=optional(self.a_zmax),
            rpm_error_max_percent=optional(self.a_rpm_error), system_width_max_mm=None if nominal else optional(self.a_width),
            max_belts=None if nominal else optional(self.a_belts), available_installation_travel_mm=None if nominal else optional(self.a_install),
            available_tensioning_travel_mm=None if nominal else optional(self.a_tension), service_factor=optional(self.a_service),
            priority=priority, weights=weights, include_unverified=self.a_unverified.isChecked(),
            result_limit=self.a_result_limit.value(), work_limit=self.a_work_limit.value())

    def auto_changed(self, *args):
        """Any request change makes the shown search obsolete, including a running one."""
        self.search_token += 1
        if self.report is not None or self.pairs is not None:
            self.clear_search(STALE)

    def clear_search(self, message):
        self.report = self.pairs = self.request = None
        self.candidates.setRowCount(0); self.pair_table.setRowCount(0); self.rejections.setRowCount(0)
        self.candidate_details.clear(); self.auto_canvas.set_drive(None, message)
        self.coverage.setText(message)
        self.to_manual.setEnabled(False); self.add_compare.setEnabled(False)
        if self.compare_ids:
            self.compare_ids = []; self.refresh_compare()

    def start_search(self):
        self._start('search')

    def start_pairs(self):
        self.use_catalog_mode()
        self._start('pairs')

    def _start(self, kind):
        if not self.can_start():
            return
        nominal=kind=='search' and self.nominal_mode()
        if not nominal and self.catalog is None:
            self.set_status('Önce bir katalog seçin.', True); return
        try:
            request = self.design_request()
            if not nominal and not any(get_profile(p.profile).family==request.family for p in (*self.catalog.belts,*self.catalog.pulleys)):
                raise ValueError('Seçilen katalogda bu kayış ailesi yok. Katalogsuz hesap için Genel boyutlandırma yöntemini seçin.')
            if kind == 'pairs' and request.priority != 'speed':
                raise ValueError('Kasnak çifti araması yalnız "Devir sapması en küçük" önceliğiyle çalışır.')
        except (ValueError, TypeError) as error:
            self.set_status(f'İstek geçersiz: {error}', True); return
        if kind == 'pairs':
            request = replace(request, include_unverified=True)  # pair alternatives are listed, never "verified".
        if nominal:kind='nominal'
        self.clear_search('Arama sürüyor…')
        self.search_token += 1; self.running = (kind, self.search_token, request)
        self.set_status('Genel boyutlandırma hesaplanıyor…' if nominal else 'Kasnak çiftleri aranıyor…' if kind=='pairs' else 'Katalogdan tasarım aranıyor…')
        operation = controller.nominal_design_job(request,self.current_nominal_options()) if nominal else \
            pulley_pairs_job(request,self.catalog) if kind=='pairs' else controller.automatic_design_job(request,self.catalog)
        self.jobs.start(self, operation)

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'belt_design_progress':
                pairs, lengths = value
                self.coverage.setText(f'Aranıyor… {pairs} kasnak çifti, {lengths} kayış uzunluğu değerlendirildi.')
            elif kind=='belt_nominal_progress':
                pairs,solved=value
                self.coverage.setText(f'Genel hesap… {pairs} çift tarandı, {solved} geometrik aday hesaplandı.')
            elif kind in ('belt_design_result', 'belt_design_cancelled', 'belt_pairs_result', 'belt_pairs_cancelled','belt_nominal_result','belt_nominal_cancelled'):
                self.search_finished(kind, value)
            elif kind == 'belt_project_result':
                self.project_recalculated(*value)
            elif kind == 'job_error':
                self.running = None
                message=str(value.get('error','Hesap tamamlanamadı.'))
                self.coverage.setText('Hesaplanamadı: '+message)
                self.auto_canvas.set_drive(None,message)
        super().handle_events(events)

    def _current(self):
        running, self.running = self.running, None
        return running is not None and running[1] == self.search_token, running

    def search_finished(self, kind, report):
        current, running = self._current()
        if not current:
            self.clear_search('Girdiler arama sırasında değişti; sonuç gösterilmedi. Yeniden arayın.')
            self.set_status('Girdiler değiştiği için arama sonucu kullanılmadı.', tone='warning')
            return
        self.request = running[2]
        if isinstance(report,NominalSizingReport):
            self.show_nominal_report(report)
            return
        if kind.startswith('belt_pairs'):
            self.pairs = report; self.result_stack.setCurrentIndex(1)
            fill(self.pair_table, [(a.driver_code, a.driven_code, number(a.driver_teeth), number(a.driven_teeth),
                                    number(a.ratio, 5), number(a.nominal_output_rpm), number(a.rpm_error_percent),
                                    a.series_id) for a in report.alternatives])
            state = 'iptal edildi, kapsam eksik' if report.cancelled else ('tamamlandı' if report.search_complete else 'iş sınırında durdu, kapsam eksik')
            self.coverage.setText(f'Kasnak çifti araması {state}: {report.pairs_visited} çift tarandı, {report.matching_count} '
                                  f'çift devir koşuluna uydu, {len(report.alternatives)} gösteriliyor'
                                  + (' (sonuç sınırı)' if report.results_limited else '') + '. Tam aktarım değildir.')
            self.auto_canvas.set_drive(None, 'Kasnak çifti sonucu tam aktarım değildir; kayış ve gerçekleşen C seçilmediği için güzergâh çizilmez.')
            self.set_status(f'Kasnak çifti araması {state}.', tone='warning' if not report.search_complete else None)
            return
        self.report = report; self.result_stack.setCurrentIndex(0)
        rows, colours = [], []
        colors = COLORS[self.context.appearance]
        for group, items in (('Kapasite kaynağı doğrulanmış', report.capacity_verified), ('Doğrulanmamış', report.unverified)):
            for c in items:
                r = c.result
                amount = self.amount(c)
                rows.append((c.driver.code, c.driven.code, c.belt.code, number(r.nominal_output_rpm, 1), number(c.rpm_error_percent, 2),
                             number(r.center_mm, 1), amount, CAPACITY_TITLES.get(c.capacity.status, c.capacity.status), group))
                colours.append(colors['muted'] if group == 'Doğrulanmamış' else colors['text'])
        self._row_candidates = (*report.capacity_verified, *report.unverified)
        fill(self.candidates, rows, colours)
        fill(self.rejections, [(REJECTION_TITLES.get(k, k), v) for k, v in report.rejection_counts])
        state = 'iptal edildi' if report.cancelled else 'tamamlandı' if report.search_complete else 'tamamlanmadı (iş adımı sınırı)'
        hidden = '' if report.request.include_unverified else \
            f' {report.unverified_count} doğrulanmamış aday gizli ("Doğrulanmamış adayları göster" ile listelenir).'
        self.coverage.setText(
            f'Arama {state}: {report.pairs_visited} kasnak çifti, {report.lengths_evaluated} kayış uzunluğu, '
            f'{report.geometry_solved} geometri çözüldü; {report.capacity_verified_count} kapasite kaynağı doğrulanmış, '
            f'{report.unverified_count} doğrulanmamış aday.' + hidden
            + (' Sonuçlar sınırlı listelendi.' if report.results_limited else '')
            + (f' {report.stop_reason}' if report.stop_reason else '') + f' Katalog: {report.catalog_id} · {report.catalog_revision}.')
        if not rows:
            hint = ('Bu katalogda kayış ürünü yok; "Yalnız kasnak çifti ara" ile uygun kasnak oranlarını görebilirsiniz.'
                    if self.catalog is not None and not self.catalog.belts else
                    'Uygun aday yok. Devir sapmasını veya C sınırlarını genişletin; doğrulanmamış adaylar için '
                    '"Gelişmiş ayarlar" içinden "Doğrulanmamış adayları göster"i açın.')
            self.auto_canvas.set_drive(None, hint); self.coverage.setText(self.coverage.text() + ' ' + hint)
        self.set_status(f'Tasarım araması {state}: {len(rows)} aday gösteriliyor.',
                        tone='warning' if report.cancelled or not report.search_complete else None)

    def current_nominal_options(self):
        return replace(self.nominal_options,length_policy=self.a_length_policy.currentData())

    @staticmethod
    def candidate_labels(c):
        if not isinstance(c,NominalCandidate):return c.driver.code,c.driven.code,c.belt.code
        r=c.result
        timing=r.specification.belt.family=='timing'
        driver=f'z₁={r.specification.driver.teeth}' if timing else f'Ø {number(r.driver_reference_diameter_mm,2)} datum'
        driven=f'z₂={r.specification.driven.teeth}' if timing else f'Ø {number(r.driven_reference_diameter_mm,2)} datum'
        kind={'required':'hesaplanan','preferred_r40':'R40 tercihli','integer_pitch':'tam dişli nominal'}[c.length_kind]
        belt=f'{r.specification.belt.profile} · L{"p" if timing else "d"} {number(r.length_exact_mm,2)} mm · {kind}'
        return driver,driven,belt

    def show_nominal_report(self,report):
        self.report=report;self.result_stack.setCurrentIndex(0)
        self._row_candidates=report.candidates
        rows=[]
        for c in report.candidates:
            labels=self.candidate_labels(c);r=c.result
            rows.append((*labels,number(r.nominal_output_rpm,2),number(c.rpm_error_percent,3),number(r.center_mm,3),
                         'Boyutlandırılmadı','Değerlendirilmedi','Geometrik hesap'))
        fill(self.candidates,rows)
        fill(self.rejections,[(REJECTION_TITLES.get(k,k),v) for k,v in report.rejection_counts])
        state='iptal edildi' if report.cancelled else 'tamamlandı' if report.search_complete else 'iş sınırında durdu'
        center=(' C belirtilmedi; başlangıç mesafesi D₁+D₂ alındı.' if report.request.center_target_mm is None and
                report.request.center_min_mm is None and report.request.center_max_mm is None else '')
        self.coverage.setText(f'Genel boyutlandırma {state}: {report.pairs_visited} çift tarandı, '
            f'{report.matching_count} geometrik aday, {len(rows)} sonuç gösteriliyor. Kayış boyları hesaplandı; ürün kodu aranmadı.'+
            center+(' Sonuç listesi sınırlandırıldı.' if report.results_limited else ''))
        if rows:self.candidates.selectRow(0)
        else:
            hint='Devir sapmasına/çap veya C sınırlarına uyan aday yok; elenen nedenleri inceleyin.'
            self.coverage.setText(self.coverage.text()+' '+hint);self.auto_canvas.set_drive(None,hint)
        self.set_status(f'Genel boyutlandırma {state}: {len(rows)} aday, kayış boyu ve C hesaplandı.',
                        tone='warning' if not report.search_complete else None)

    def show_nominal_candidate(self,c):
        r=c.result;labels=self.candidate_labels(c)
        kind={'required':'C mesafesinden hesaplanan teorik boy','preferred_r40':'R40 tercihli nominal boy (stok ürünü değildir)',
              'integer_pitch':'Tam kayış diş sayısından bölüm boyu (stok ürünü değildir)'}[c.length_kind]
        lines=[f'<b>{labels[0]} → {labels[1]}</b>',f'Profil / kesit: {r.specification.belt.profile}',
            'Genel geometrik hesap; üretici/katalog ürünü seçilmedi.',
            f'İdeal çıkış devri: {number(r.nominal_output_rpm,4)} dev/dak · sapma %{number(c.rpm_error_percent,4)}',
            f'Çap oranı: {number(r.ratio,6)}',
            '<br><b>Kayış boyu ve eksen mesafesi</b>',
            f'Hedef C için gerekli teorik boy: {number(c.required_length_mm,6)} mm',
            f'Hesapta kullanılan boy: {number(r.length_exact_mm,6)} mm · {kind}',
            f'Bu boydaki C: {number(r.center_mm,6)} mm · hedef farkı {number(c.center_deviation_mm,6)} mm',
            f'Sürücü / sürülen referans çapı: {number(r.driver_reference_diameter_mm,4)} / {number(r.driven_reference_diameter_mm,4)} mm',
            f'Sarılma açıları: {number(r.driver_wrap_deg,3)}° / {number(r.driven_wrap_deg,3)}°',
            f'Kayış hızı: {number(r.speed_m_s,4)} m/s',f'Etkin kuvvet farkı Ft: {number(r.effective_force_delta_n,3)} N',
            f'Giriş / ideal çıkış torku: {number(r.input_torque_nm,3)} / {number(r.ideal_output_torque_nm,3)} N·m',
            '<br><b>Seçim sınırları</b>',
            'Kesit ve gerekli adet güç tablosuyla seçilmedi; kapasite, germe, dış gövde ve ömür onayı yoktur.']
        if r.specification.belt.family=='timing':
            lines.extend((f'Teorik kayış diş adedi Lp/p: {number(r.theoretical_belt_teeth,6)}',
                          f'Seçilen tam kayış diş adedi: {r.selected_belt_teeth if r.selected_belt_teeth is not None else "henüz seçilmedi"}'))
        lines.extend(f'{SEVERITY_TITLES.get(i.severity,i.severity)} · {i.message}' for i in c.checks)
        lines.extend(report_line for report_line in self.report.assumptions)
        self.candidate_details.setHtml('<br>'.join(lines))

    @staticmethod
    def amount(c):
        """V: belt count (grooves); triger-senkron: belt width. Unknown stays unknown."""
        if isinstance(c,NominalCandidate):return 'Adet / genişlik seçilmedi'
        if c.result.specification.belt.family == 'v':
            return f'{c.belt_count} kayış' if c.belt_count is not None else 'adet bilinmiyor'
        return f'{number(c.belt.width_mm)} mm genişlik' if c.belt.width_mm is not None else 'genişlik bilinmiyor'

    def selected_candidate(self):
        rows = self.candidates.selectionModel().selectedRows() if self.report is not None else []
        if not rows or self.result_stack.currentIndex() != 0:
            return None
        return self._row_candidates[rows[0].row()]

    def candidate_selected(self):
        c = self.selected_candidate()
        self.to_manual.setEnabled(c is not None); self.add_compare.setEnabled(c is not None)
        if c is None:
            self.candidate_details.clear(); return
        self.auto_canvas.set_drive(c.result)
        if isinstance(c,NominalCandidate):
            self.show_nominal_candidate(c)
            return
        cap = c.capacity
        width = (f'{number(c.system_width_mm, 2)} mm (bilinen eksenel zarflardan)' if c.system_width_mm is not None else
                 'bilinmiyor' + (f' — alt sınır en az {number(c.system_width_lower_bound_mm, 2)} mm' if c.system_width_lower_bound_mm is not None else ''))
        def pulley(p):
            return (f'{p.code}: {"z = " + str(p.teeth) if p.teeth else "Ø datum " + number(p.datum_diameter_mm)}; '
                    f'nominal kayış genişliği {number(p.nominal_belt_width_mm)} mm; F {number(p.catalog_face_dimension_f_mm)} mm; '
                    f'toplam L {number(p.overall_width_mm)} mm; pilot delik {number(p.pilot_bore_mm)} mm (bitmiş mil deliği değildir); '
                    f'dış zarf Ø {number(p.outside_diameter_mm)} mm')
        lines = [f'<b>{c.driver.code} → {c.driven.code} · {c.belt.code}</b>',
                 f'Durum: {CANDIDATE_TITLES.get(c.status, c.status)} · mühendislik onayı yok',
                 f'Üretici/seri: {c.manufacturer} · {c.series_id}',
                 f'İdeal çıkış devri: {number(c.result.nominal_output_rpm)} dev/dak (sapma {number(c.rpm_error_percent)} %)',
                 f'Gerçekleşen C: {number(c.result.center_mm, 3)} mm' + (f' (hedeften {number(c.center_deviation_mm, 3)} mm)' if c.center_deviation_mm is not None else ''),
                 f'Toplam eksenel genişlik: {width}',
                 f'Referans çemberi alanı (gerçek dış zarf değil): {number(c.reference_area_mm2, 0)} mm²',
                 '<br><b>Kapasite</b>',
                 f'Durum: {CAPACITY_TITLES.get(cap.status, cap.status)}',
                 f'Tablo: {cap.table_id or "—"} · yöntem: {cap.method or "—"}',
                 f'Kayış başına kapasite: {number(cap.per_belt_power_kw, 4)} kW · toplam: {number(cap.total_power_kw, 4)} kW',
                 f'Tasarım gücü: {number(cap.design_power_kw, 4) if cap.design_power_kw is not None else "değerlendirilmedi"} kW',
                 f'Kapasite oranı (tüm tasarımın emniyet katsayısı değildir): {number(cap.capacity_margin, 3)}',
                 f'Gerekli kayış adedi: {number(cap.required_belts)}',
                 '<br><b>Kasnaklar</b>', pulley(c.driver), pulley(c.driven),
                 '<br><b>Kontroller</b>']
        lines += [f'{SEVERITY_TITLES.get(i.severity, i.severity)} · {i.code}: {i.message}' for i in c.checks]
        self.candidate_details.setHtml('<br>'.join(lines))

    def transfer_to_manual(self):
        c = self.selected_candidate()
        if c is None or self.report is None:
            self.set_status('Aktarmak için güncel bir hesap veya katalog adayı seçin.', True); return
        exact = self.set_manual_specification(c.result.specification)
        self.tabs.setCurrentIndex(0)
        if exact:
            self.set_status(' / '.join(self.candidate_labels(c))+' manuel ekrana aktarıldı ve yeniden hesaplandı.'+
                            (' Adet/kapasite güçten seçilmedi.' if isinstance(c,NominalCandidate) else ''))

    # ======================================================================================
    # Catalogue and sources
    # ======================================================================================
    def build_catalog(self):
        self.catalog_picker = QComboBox()
        for key, title, path in BUNDLED_CATALOGS:
            self.catalog_picker.addItem(title, key)
        self.catalog_picker.currentIndexChanged.connect(self.select_catalog)
        self.catalog_file = button('Katalog dosyası aç… (JSON/CSV)', self.open_catalog)
        self.controls += [self.catalog_picker, self.catalog_file]
        self.catalog_summary = label('', 'muted')
        notice = label('Güncel Gates/Optibelt ürün ve kapasite tabloları bu sürümde yoktur. Bir dosyada OFFICIAL_VERIFIED '
                       'yazılması resmî onay oluşturmaz; bu kaynaklar "kullanıcı tarafından sağlanan" olarak işlenir.', 'muted')
        self.sources = table(['Üretici', 'Belge', 'Revizyon', 'Sayfa', 'Beyan edilen durum', 'İşlenen durum', 'Kullanım izni', 'Kaynak'])
        self.product_filter = QLineEdit(); self.product_filter.setPlaceholderText('Ürün kodu, profil veya seri ara…')
        self.product_filter.setClearButtonEnabled(True); self.product_filter.textChanged.connect(self.filter_products)
        self.products = table(['Tür', 'Ürün kodu', 'Profil', 'Seri', 'z / Ø datum', 'Kayış boyu · mm', 'Nominal kayış genişliği · mm',
                               'F · mm', 'Toplam L · mm', 'Pilot delik · mm', 'Dış zarf Ø · mm', 'Kaynak sayfası'])
        self.audit_summary = label('', 'muted')
        self.quarantine = table(['PDF sayfası', 'Ürün kodu', 'Karantina nedeni'], stretch=2)
        top = panel(section_header('Katalog', self.catalog_picker, self.catalog_file), self.catalog_summary, notice,
                    label('Kaynaklar', 'section'), self.sources, margins=(0, 0, 0, 0))
        products = panel(section_header('Ürünler', self.product_filter), self.products, margins=(0, 0, 0, 0))
        audit = panel(label('İçe aktarma denetimi', 'section'), self.audit_summary, self.quarantine, margins=(0, 0, 0, 0))
        split = QSplitter(Qt.Vertical); split.addWidget(top); split.addWidget(products); split.addWidget(audit)
        split.setSizes([220, 360, 200])
        return panel(split, margins=(4, 4, 4, 4))

    def select_catalog(self, index):
        key = self.catalog_picker.itemData(index)
        if key in ('project', 'file'):
            snapshot = getattr(self, '_extra_catalogs', {}).get(key)
            if snapshot is not None:
                self.set_catalog(snapshot, key, self.catalog_picker.itemText(index))
                if self._ready:self.use_catalog_mode()
            return
        try:
            catalog = load_bundled(key)
        except (OSError, ValueError) as error:
            self.set_status(f'Katalog açılamadı: {error}', True); return
        self.set_catalog(catalog, key, self.catalog_picker.itemText(index))
        if self._ready:self.use_catalog_mode()

    def open_catalog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Kayış/kasnak kataloğu', '', 'Ürün kataloğu (*.json *.csv)')
        if not path:
            return
        try:
            catalog = load_catalog(path)
        except (OSError, ValueError, UnicodeError) as error:
            self.set_status(f'Katalog okunamadı: {error}', True); return
        self.remember_catalog('file', f'Dosya: {Path(path).name}', catalog)
        self.use_catalog_mode()
        self.set_status(f'Katalog okundu: {Path(path).name}')

    def remember_catalog(self, key, title, catalog):
        """Show a file/project catalogue in the picker so the picker never lies about the active data."""
        self._extra_catalogs = getattr(self, '_extra_catalogs', {}); self._extra_catalogs[key] = catalog
        index = self.catalog_picker.findData(key)
        if index < 0:
            self.catalog_picker.addItem(title, key); index = self.catalog_picker.count() - 1
        else:
            self.catalog_picker.setItemText(index, title)
        self.catalog_picker.blockSignals(True); self.catalog_picker.setCurrentIndex(index); self.catalog_picker.blockSignals(False)
        self.set_catalog(catalog, key, title)

    def set_catalog(self, catalog, key, title):
        self.catalog, self.catalog_key, self.catalog_title = catalog, key, title
        self.auto_changed()
        self.fill_catalog_filters()
        families = sorted({FAMILY_TITLES[get_profile(p.profile).family] for p in (*catalog.belts, *catalog.pulleys)})
        self.catalog_summary.setText(
            f'{catalog.identifier} · revizyon {catalog.revision} · {len(catalog.pulleys)} kasnak, {len(catalog.belts)} kayış, '
            f'{len(catalog.ratings)} kapasite tablosu · {", ".join(families) or "ürün yok"}.'
            + (' Kayış ürünü ve kapasite tablosu olmadığı için tam aktarım araması aday üretmez; yalnız kasnak çifti araması '
               'kullanılabilir.' if not catalog.belts else ''))
        self.auto_catalog_label.setText(f'Katalog: {title} — {len(catalog.pulleys)} kasnak, {len(catalog.belts)} kayış, '
                                        f'{len(catalog.ratings)} kapasite tablosu.')
        fill(self.sources, [(s.manufacturer, s.document or '—', s.revision or '—', s.page or '—',
                             SOURCE_TITLES.get(s.verification_status, s.verification_status),
                             SOURCE_TITLES.get(s.effective_status, s.effective_status), s.usage_permission or '—',
                             s.url or s.identifier) for s in catalog.sources])
        pages = {s.identifier: s.page for s in catalog.sources}
        self._product_rows = []
        for b in catalog.belts:
            self._product_rows.append(('Kayış', b.code, b.profile, b.series_id, number(b.tooth_count) if b.tooth_count else '—',
                                       number(b.length_mm, 2), number(b.width_mm), '—', '—', '—', '—', pages.get(b.source_id, '—')))
        for p in catalog.pulleys:
            self._product_rows.append(('Kasnak', p.code, p.profile, p.series_id,
                                       f'z = {p.teeth}' if p.teeth else f'Ø {number(p.datum_diameter_mm)}', '—',
                                       number(p.nominal_belt_width_mm), number(p.catalog_face_dimension_f_mm),
                                       number(p.overall_width_mm), number(p.pilot_bore_mm), number(p.outside_diameter_mm),
                                       pages.get(p.source_id, '—')))
        self.filter_products()
        if key == 'tosyali':
            audit = tosyali_audit()
            self.audit_summary.setText(
                f'Kaynak PDF SHA-256 {audit["document_sha256"][:16]}… · {audit["recognized_rows"]} tanınan satır, '
                f'{audit["accepted_rows"]} kabul edilen kasnak, {len(audit["quarantined"])} karantina, '
                f'{audit["unsupported_rows"]} burçlu (kapsam dışı) satır. Karantinadaki satırlar düzeltilmeden dışarıda bırakıldı. '
                'Revizyon belirtilmemiş; güncellik bağımsız doğrulanmadı.')
            fill(self.quarantine, [(q['pdf_page'], q['code'], q['reason']) for q in audit['quarantined']])
        else:
            self.audit_summary.setText('Bu katalog için içe aktarma denetim kaydı yok.')
            self.quarantine.setRowCount(0)
        self.update_auto_hint()

    def filter_products(self, *args):
        needle = self.product_filter.text().strip().casefold()
        rows = [r for r in getattr(self, '_product_rows', ()) if not needle or needle in ' '.join(map(str, r[1:4])).casefold()]
        fill(self.products, rows)

    # ======================================================================================
    # Comparison and projects
    # ======================================================================================
    def build_compare(self):
        self.compare = table(['Sürücü', 'Sürülen', 'Kayış', 'Sapma %', 'C · mm', 'L · mm', 'Küçük sarılma · °', 'v · m/s',
                              'Adet / genişlik', 'Kapasite', 'Uyarılar'], stretch=10)
        self.remove_compare = button('Seçileni çıkar', self.remove_from_compare)
        self.export_compare = button('Karşılaştırma JSON kaydet…', self.save_comparison)
        self.compare_note = label('Karşılaştırma güncel aramanın adaylarından oluşur. Arama girdileri değişirse liste temizlenir; '
                                  'kayıtlı projeler açılırken yeniden hesaplanır.', 'muted')
        self.controls += [self.remove_compare, self.export_compare]
        self.refresh_compare()
        return panel(section_header('Karşılaştırılan adaylar', self.remove_compare, self.export_compare), self.compare_note,
                     self.compare, margins=(4, 4, 4, 4))

    def _candidates_by_id(self):
        if self.report is None:
            return {}
        return {c.identifier: c for c in (*self.report.capacity_verified, *self.report.unverified)}

    def add_to_compare(self):
        c = self.selected_candidate()
        if c is None:
            return
        if c.identifier not in self.compare_ids:
            self.compare_ids.append(c.identifier)
        self.refresh_compare(); self.set_status('Karşılaştırmaya eklendi: '+self.candidate_labels(c)[2])

    def remove_from_compare(self):
        rows = self.compare.selectionModel().selectedRows()
        if rows:
            del self.compare_ids[rows[0].row()]
            self.refresh_compare()

    def refresh_compare(self):
        known = self._candidates_by_id()
        self.compare_ids = [i for i in self.compare_ids if i in known]
        rows = []
        for identifier in self.compare_ids:
            c = known[identifier]; r = c.result
            amount = self.amount(c)
            warnings = '; '.join(f'{i.code}' for i in c.checks if i.severity in ('WARNING', 'NOT_EVALUATED'))
            rows.append((*self.candidate_labels(c), number(c.rpm_error_percent), number(r.center_mm, 2),
                         number(r.length_exact_mm, 2), number(min(r.driver_wrap_deg, r.driven_wrap_deg), 2),
                         number(r.speed_m_s, 3), amount, 'Değerlendirilmedi' if isinstance(c,NominalCandidate) else CAPACITY_TITLES.get(c.capacity.status,c.capacity.status), warnings))
        fill(self.compare, rows)
        self.export_compare.setEnabled(bool(rows) and not self.busy)

    def save_comparison(self):
        if self.report is None or not self.compare_ids:
            self.set_status('Kaydedilecek güncel karşılaştırma yok.', True); return
        path, _ = QFileDialog.getSaveFileName(self, 'Karşılaştırma kaydet', 'kayis_karsilastirma.json', 'JSON (*.json)')
        if not path:
            return
        try:
            data = report_to_dict(self.report, selected_ids=tuple(self.compare_ids))
            write_text_atomic(path, json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, default=list))
        except (OSError, ValueError, TypeError) as error:
            self.set_status(f'Karşılaştırma kaydedilemedi: {error}', True); return
        self.set_status(f'Karşılaştırma kaydedildi: {Path(path).name}')

    def save_project(self):
        if self.manual_timer.isActive():
            self.calculate_manual()          # the latest typed value is part of the saved design
        manual = self.manual_result.specification if self.manual_result is not None else None
        # The automatic request and its catalogue snapshot are saved only after a current search.
        request = self.request if self.report is not None or self.pairs is not None else None
        if manual is None and request is None:
            self.set_status('Kaydedilecek geçerli tasarım yok: manuel girdileri düzeltin veya bir arama yapın.', True); return
        if manual is None:
            self.set_status('Manuel tasarım geçersiz olduğu için projeye yalnız otomatik arama kaydediliyor.', tone='warning')
        selected = tuple(self.compare_ids) if self.report is not None and request is not None else ()
        try:
            nominal=request is not None and self.nominal_mode()
            project = DesignProject(request=request, catalog=self.catalog if request is not None and not nominal else None,
                                    manual=manual, selected_ids=selected,
                                    nominal_options=self.current_nominal_options() if nominal else None)
            text = project_dumps(project)
        except (ValueError, TypeError) as error:
            self.set_status(f'Proje oluşturulamadı: {error}', True); return
        if len(text.encode('utf-8')) > MAX_JSON_SIZE:
            self.set_status('Proje 2 MiB sınırını aşıyor; daha küçük bir katalogla kaydedin.', True); return
        path, _ = QFileDialog.getSaveFileName(self, 'Kayış projesini kaydet', 'kayis_projesi.json', 'Kayış projesi (*.json)')
        if not path:
            return
        try:
            write_text_atomic(path, text)
        except OSError as error:
            self.set_status(f'Proje kaydedilemedi: {error}', True); return
        self.set_status(f'Proje kaydedildi: {Path(path).name} (' + ('manuel tasarım ve otomatik arama' if manual and request else
                        'manuel tasarım' if manual else 'otomatik arama') + '; sonuçlar açılışta yeniden hesaplanır).')

    def open_project(self):
        if not self.can_start():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Kayış projesi aç', '', 'Kayış projesi (*.json)')
        if not path:
            return
        try:
            with open(path, 'rb') as stream:
                content = stream.read(MAX_JSON_SIZE + 1)
            if len(content) > MAX_JSON_SIZE:
                raise ValueError('Proje en çok 2 MiB olabilir.')
            project = project_loads(content)
        except (OSError, ValueError, UnicodeError) as error:
            self.set_status(f'Proje açılamadı: {error}', True); return
        self.search_token += 1; self.running = ('project', self.search_token, project.request)
        self.set_status('Proje açıldı; sonuçlar yeniden hesaplanıyor…')
        self.jobs.start(self, project_job(project))

    def project_recalculated(self, project, outcome, selected):
        current, running = self._current()
        if not current:
            self.set_status('Proje yeniden hesaplanırken girdiler değişti; sonuç gösterilmedi.', tone='warning'); return
        exact = self.set_manual_specification(project.manual) if project.manual is not None else True
        if project.request is None:
            if exact:
                self.set_status('Proje açıldı; manuel tasarım güncel motorla yeniden hesaplandı.')
            return
        self.load_request(project.request, project.catalog,project.nominal_options)
        self.search_token += 1; self.running = ('search', self.search_token, project.request)
        self.search_finished('belt_design_cancelled' if outcome.cancelled else 'belt_design_result', outcome)
        self.compare_ids = list(selected); self.refresh_compare()
        dropped = len(project.selected_ids) - len(selected)
        if not exact:
            return
        self.set_status(('Proje açıldı; genel boyutlandırma güncel motorla yeniden hesaplandı.' if project.nominal_options is not None else
                         'Proje açıldı; arama güncel katalog snapshot\'ı ile yeniden yapıldı.')
                        + (f' {dropped} eski seçim güncel sonuçlarda bulunmadığı için atıldı.' if dropped else ''),
                        tone='warning' if dropped else None)

    def load_request(self, request, catalog,nominal_options=None):
        widgets = [self.a_basis,self.a_length_policy,self.a_family, self.a_profile, self.a_manufacturer, self.a_series, self.a_mode, self.a_priority,
                   self.a_power, self.a_rpm, self.a_target, self.a_target_c, self.a_tolerance, self.a_cmin, self.a_cmax,
                   self.a_rpm_error, self.a_dmin, self.a_dmax, self.a_odmax, self.a_zmin, self.a_zmax, self.a_width,
                   self.a_belts, self.a_install, self.a_tension, self.a_service, self.a_result_limit, self.a_work_limit,
                   self.a_unverified, self.catalog_picker, *self.weights.values()]
        for w in widgets:
            w.blockSignals(True)
        try:
            self.a_basis.setCurrentIndex(self.a_basis.findData('nominal' if nominal_options is not None else 'catalog'))
            if nominal_options is not None:
                self.nominal_options=nominal_options
                self.a_length_policy.setCurrentIndex(self.a_length_policy.findData(nominal_options.length_policy))
            else:self.catalog, self.catalog_key = catalog, 'project'
            self.a_family.setCurrentIndex(self.a_family.findData(request.family))
            self.auto_family_changed()
            if catalog is not None:self.set_catalog_quiet(catalog)
            for box, value in ((self.a_profile, request.profile), (self.a_manufacturer, request.manufacturer),
                               (self.a_series, request.series_id), (self.a_mode, request.mode), (self.a_priority, request.priority)):
                box.setCurrentIndex(max(box.findData(value), 0))
            for box, value in ((self.a_power, request.power_kw), (self.a_rpm, request.input_rpm), (self.a_target, request.target_rpm)):
                box.setValue(value)
            for box, value in ((self.a_target_c, request.center_target_mm), (self.a_tolerance, request.center_tolerance_mm),
                               (self.a_cmin, request.center_min_mm), (self.a_cmax, request.center_max_mm),
                               (self.a_rpm_error, request.rpm_error_max_percent), (self.a_dmin, request.diameter_min_mm),
                               (self.a_dmax, request.diameter_max_mm), (self.a_odmax, request.outside_diameter_max_mm),
                               (self.a_zmin, request.teeth_min), (self.a_zmax, request.teeth_max),
                               (self.a_width, request.system_width_max_mm), (self.a_belts, request.max_belts),
                               (self.a_install, request.available_installation_travel_mm),
                               (self.a_tension, request.available_tensioning_travel_mm), (self.a_service, request.service_factor)):
                box.setValue(box.minimum() if value is None else value)
            for key, box in self.weights.items():
                box.setValue(dict(request.weights).get(key, 0.))
            self.a_unverified.setChecked(request.include_unverified)
            self.a_result_limit.setValue(request.result_limit); self.a_work_limit.setValue(request.work_limit)
        finally:
            for w in widgets:
                w.blockSignals(False)
        self.basis_changed()

    def set_catalog_quiet(self, catalog):
        """Show a project snapshot without restarting the search invalidation chain."""
        token = self.search_token
        self.remember_catalog('project', 'Proje katalog snapshot\'ı', catalog)
        self.search_token = token

    # ---- shared page hooks --------------------------------------------------------------------
    def set_busy(self, busy):
        super().set_busy(busy)
        self.tabs.tabBar().setEnabled(True)
        if hasattr(self, 'export_compare'):
            self.export_compare.setEnabled(not busy and bool(self.compare_ids))

    def job_finished(self):
        if self.running is not None:
            kind = self.running[0]; self.running = None
            if kind != 'project':
                self.clear_search('Arama sonuç üretmeden bitti.')

    def theme_changed(self):
        for view in (self.canvas, self.auto_canvas):
            view.set_appearance(self.context.appearance)
        if self.manual_result is not None:
            self.show_manual(self.manual_result)
