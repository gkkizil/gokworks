"""DFM Analyzer page: settings | 2D preview with findings | results and details."""

import copy
from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItem, QStandardItemModel, QColor
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QListWidget,
                               QListWidgetItem, QSplitter, QTableView, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget, QCheckBox, QMenu)

from gui_qt.components import BasePage, button, configure_view, fit_columns, label, pane, scroll, NumberSpinBox, section_header
from gui_qt.theme import COLORS
from . import controller, reporting
from .models import SEVERITY_TITLES, STATUS_TITLES, ERROR, WARNING, INFO, NOT_EVALUATED, FAILED
from .profiles import load as load_profile
from .rules import REGISTRY
from .visualization.view import DfmView

UNITS = (('Otomatik ($INSUNITS)', None), ('mm', 'mm'), ('cm', 'cm'), ('m', 'm'), ('inch', 'inch'))
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


class FindingFilter(QSortFilterProxyModel):
    """Free text over every column plus an exact severity match (stored on column 0)."""
    severity = ''

    def filterAcceptsRow(self, row, parent):
        if self.severity and self.sourceModel().index(row, 0, parent).data(Qt.UserRole + 2) != self.severity:
            return False
        return super().filterAcceptsRow(row, parent)

    def set_filter(self, severity, text):
        if hasattr(self, 'beginFilterChange'):                     # Qt ≥ 6.9
            self.beginFilterChange(); self.severity = severity; self.endFilterChange()
        else:
            self.severity = severity; self.invalidateRowsFilter()
        self.setFilterFixedString(text)


def _number(value):
    return '' if value is None else f'{value:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


class DfmPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'DFM · İmalat uygunluk analizi',
                         'DXF kesim geometrisini seçilen makine/kural profiline göre kontrol eder; '
                         'bulguları geometri üzerinde gösterir. Kaynak dosya yalnız okunur.')
        self.result = None
        self.profiles = controller.profiles()
        self.custom_profile = None
        self.start_button = self.action('Analiz et', self.start, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.open_button = self.action('Sonucu aç…', self.open_result)
        self.save_button = self.action('Rapor kaydet', None)
        menu = QMenu(self.save_button)
        menu.addAction('JSON analiz sonucu…', lambda: self.save_report('json'))
        menu.addAction('CSV bulgu listesi…', lambda: self.save_report('csv'))
        self.save_button.setMenu(menu); self.save_button.setEnabled(False)
        self.controls.remove(self.save_button)

        # ---- left: analysis settings --------------------------------------------------
        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(0, 0, 4, 0)
        source, source_layout = pane('Kaynak')
        row = QHBoxLayout(); self.path = QLineEdit(str(self.settings.get('dfm_path', '') or ''))
        self.path.setPlaceholderText('DXF dosyası'); self.path.setClearButtonEnabled(True)
        self.path.setAccessibleName('DXF dosyası')
        self.browse = button('Dosya seç…', self.choose_file)
        row.addWidget(self.path, 1); row.addWidget(self.browse); source_layout.addLayout(row)
        form = QFormLayout(); form.setSpacing(6)
        self.unit = QComboBox()
        for title, value in UNITS:
            self.unit.addItem(title, value)
        self.unit.setToolTip('DXF $INSUNITS içermiyorsa analiz birim seçmenizi ister.')
        form.addRow('Birim', self.unit)
        self.tolerance = NumberSpinBox(3); self.tolerance.setRange(.001, .1); self.tolerance.setSingleStep(.005)
        self.tolerance.setValue(float(self.settings.get('dfm_tolerance', .01) or .01))
        self.tolerance.setToolTip('Yay ve eğrilerin düzleştirme hatası; ölçümler bu kadar sapabilir.')
        form.addRow('Eğri doğruluğu · mm', self.tolerance)
        self.excluded = QLineEdit(str(self.settings.get('dfm_excluded', '') or ''))
        self.excluded.setPlaceholderText('ör. ÖLÇÜ; YAZI')
        form.addRow('Hariç katmanlar', self.excluded)
        source_layout.addLayout(form)
        left_layout.addWidget(source)

        process, process_layout = pane('Profil ve malzeme', rule=True)
        pform = QFormLayout(); pform.setSpacing(6)
        self.profile = QComboBox()
        self.profile.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.profile.setMinimumContentsLength(10)
        self.fill_profiles()
        self.profile.currentIndexChanged.connect(self.profile_changed)
        self.load_profile_button = button('Profil dosyası…', self.choose_profile)
        pform.addRow('Kural profili', self.profile)
        pform.addRow('', self.load_profile_button)
        self.material = QLineEdit(str(self.settings.get('dfm_material', '') or ''))
        self.material.setPlaceholderText('ör. S235JR')
        pform.addRow('Malzeme', self.material)
        self.thickness = NumberSpinBox(3); self.thickness.setRange(0, 200); self.thickness.setSingleStep(.5)
        self.thickness.setSpecialValueText('girilmedi')
        self.thickness.setValue(float(self.settings.get('dfm_thickness', 0) or 0))
        self.thickness.setToolTip('0 = girilmedi: kalınlığa bağlı kurallar “değerlendirilemedi” olur.')
        pform.addRow('Sac kalınlığı · mm', self.thickness)
        process_layout.addLayout(pform)
        self.profile_note = label('', 'muted')
        process_layout.addWidget(self.profile_note)
        left_layout.addWidget(process)

        rules, rules_layout = pane('Analiz kuralları', rule=True)
        self.rule_list = QListWidget(); self.rule_list.setAccessibleName('Analiz kuralları')
        self.rule_list.setMinimumHeight(160); self.rule_list.setTextElideMode(Qt.ElideRight)
        self.rule_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rules_layout.addWidget(self.rule_list)
        left_layout.addWidget(rules, 1)
        self.controls += [self.path, self.browse, self.unit, self.tolerance, self.excluded, self.profile,
                          self.load_profile_button, self.material, self.thickness, self.rule_list]

        # ---- centre: preview ----------------------------------------------------------
        centre = QWidget(); centre_layout = QVBoxLayout(centre); centre_layout.setContentsMargins(4, 0, 4, 0)
        self.show_marks = QCheckBox('Bulguları göster'); self.show_marks.setChecked(True)
        self.show_marks.toggled.connect(lambda on: self.view.set_show_findings(on))
        self.fit_button = button('Sığdır', lambda: self.view.fit())
        centre_layout.addWidget(section_header('Geometri önizlemesi', self.show_marks, self.fit_button))
        self.view = DfmView(); self.view.set_appearance(self.context.appearance)
        self.view.findingClicked.connect(self.select_finding_row)
        centre_layout.addWidget(self.view, 1)
        self.view_caption = label('Bir DXF seçip “Analiz et” deyin. Kırmızı: hata · Turuncu: uyarı · Gri: bilgi.', 'muted')
        centre_layout.addWidget(self.view_caption)

        # ---- right: results -----------------------------------------------------------
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.setContentsMargins(4, 0, 0, 0)
        self.summary = label('Henüz analiz yok.', 'muted')
        right_layout.addWidget(section_header('Sonuçlar'))
        right_layout.addWidget(self.summary)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Bulgu, kural veya parça ara…')
        self.search.setClearButtonEnabled(True)
        self.severity = QComboBox()
        for title, value in (('Tüm önemler', ''), ('Hata', ERROR), ('Uyarı', WARNING), ('Bilgi', INFO)):
            self.severity.addItem(title, value)
        filters.addWidget(self.search, 1); filters.addWidget(self.severity)
        right_layout.addLayout(filters)
        self.tabs = QTabWidget()
        self.model = QStandardItemModel(0, 6)
        self.model.setHorizontalHeaderLabels(['Önem', 'Kural', 'Bulgu', 'Ölçülen', 'Sınır', 'Parça'])
        self.proxy = FindingFilter(self); self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive); self.proxy.setFilterKeyColumn(-1)
        self.proxy.setSortRole(Qt.UserRole + 1)
        self.table = QTableView(); self.table.setModel(self.proxy); configure_view(self.table)
        self.table.setTextElideMode(Qt.ElideRight)
        fit_columns(self.table, elastic=2, minimum=160, autofit=(0, 1, 3, 4, 5), settings=self.settings, key='dfm_findings')
        self.table.selectionModel().selectionChanged.connect(self.finding_selected)
        self.search.textChanged.connect(self.apply_filter); self.severity.currentIndexChanged.connect(self.apply_filter)
        findings_tab = QWidget(); ft = QVBoxLayout(findings_tab); ft.setContentsMargins(0, 4, 0, 0)
        ft.addWidget(self.table, 2)
        self.details = QTextBrowser(); self.details.setOpenLinks(False); self.details.setAccessibleName('Bulgu ayrıntısı')
        ft.addWidget(self.details, 1)
        self.tabs.addTab(findings_tab, 'Bulgular')
        self.outcomes = QStandardItemModel(0, 4)
        self.outcomes.setHorizontalHeaderLabels(['Durum', 'Kural', 'Sınır', 'Açıklama'])
        self.outcome_table = QTableView(); self.outcome_table.setModel(self.outcomes); configure_view(self.outcome_table)
        fit_columns(self.outcome_table, elastic=3, minimum=180, autofit=(0, 1, 2), settings=self.settings, key='dfm_outcomes')
        self.tabs.addTab(self.outcome_table, 'Kural sonuçları')
        self.notes = QTextBrowser()
        self.tabs.addTab(self.notes, 'Kapsam ve notlar')
        right_layout.addWidget(self.tabs, 1)

        self.splitter = QSplitter(Qt.Horizontal)
        left_scroll = scroll(left); left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.splitter.addWidget(left_scroll); self.splitter.addWidget(centre); self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 0); self.splitter.setStretchFactor(1, 3); self.splitter.setStretchFactor(2, 2)
        self.splitter.setSizes([320, 540, 600])
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()
        self.profile_changed()

    # ---- profiles --------------------------------------------------------------------
    def fill_profiles(self):
        wanted = self.settings.get('dfm_profile', 'laser_generic')
        self.profile.blockSignals(True); self.profile.clear()
        for pid, p in self.profiles.items():
            self.profile.addItem(p.name + ('' if p.verified else '  (doğrulanmamış örnek)'), pid)
        if self.custom_profile is not None:
            self.profile.addItem(self.custom_profile.name + ' · dosya', '__custom__')
        index = self.profile.findData(wanted)
        self.profile.setCurrentIndex(index if index >= 0 else 0)
        self.profile.blockSignals(False)

    def current_profile(self):
        pid = self.profile.currentData()
        return self.custom_profile if pid == '__custom__' else self.profiles.get(pid)

    def profile_changed(self, *args):
        profile = self.current_profile()
        if profile is None:
            return
        self.settings.set('dfm_profile', self.profile.currentData())
        verified = 'Doğrulanmış profil.' if profile.verified else 'Doğrulanmamış örnek başlangıç profili.'
        first = profile.note.split('. ')[0].rstrip('.') + '.' if profile.note else ''
        self.profile_note.setText(f'{verified} Sürüm {profile.profile_version}. {first}'.strip())
        self.profile_note.setToolTip(profile.note)
        self.rule_list.clear()
        for rid, cfg in profile.rules.items():
            rule = REGISTRY[rid]
            limit = []
            if cfg.get('factor_t'):
                limit.append(f'{_number(cfg["factor_t"])}×t')
            if cfg.get('min_mm') is not None:
                limit.append(f'≥ {_number(cfg["min_mm"])} mm')
            text = f'{rid} · {rule.name}' + (f'  ({", ".join(limit)})' if limit else '')
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, rid)
            item.setToolTip(f'{rule.description}\nKullanılan geometri: {rule.uses}\n{rule.assumptions}'.strip())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if cfg.get('enabled', True) else Qt.Unchecked)
            self.rule_list.addItem(item)

    def choose_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'DFM profil dosyası', '', 'DFM profili (*.json)')
        if not path:
            return
        try:
            self.custom_profile = load_profile(path)
        except ValueError as error:
            self.set_status(str(error), True); return
        self.settings.set('dfm_profile', '__custom__')
        self.fill_profiles(); self.profile_changed()
        self.set_status(f'Profil okundu: {self.custom_profile.name}')

    # ---- analysis --------------------------------------------------------------------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'DXF seç', self.path.text(), 'DXF (*.dxf *.DXF)')
        if path:
            self.path.setText(path)

    def start(self):
        if not self.can_start():
            return
        path = Path(self.path.text().strip())
        if not self.path.text().strip() or not path.is_file():
            self.set_status('Önce mevcut bir DXF dosyası seçin.', True); return
        profile = copy.deepcopy(self.current_profile())
        for i in range(self.rule_list.count()):
            item = self.rule_list.item(i)
            profile.rules[item.data(Qt.UserRole)]['enabled'] = item.checkState() == Qt.Checked
        if not any(cfg.get('enabled', True) for cfg in profile.rules.values()):
            self.set_status('En az bir kural seçin.', True); return
        thickness = self.thickness.value() or None
        options = dict(thickness=thickness, material=self.material.text().strip(), unit=self.unit.currentData(),
                       tolerance=self.tolerance.value(),
                       excluded_layers=[s.strip() for s in self.excluded.text().split(';') if s.strip()])
        for key, value in (('dfm_path', str(path)), ('dfm_thickness', thickness or 0), ('dfm_material', options['material']),
                           ('dfm_tolerance', options['tolerance']), ('dfm_excluded', self.excluded.text())):
            self.settings.set(key, value)
        self.set_status('DFM analizi başlatıldı…')
        self.jobs.start(self, controller.worker(str(path), profile, options))

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'dfm_progress':
                index, total, text = value
                self.set_status(f'{text}…')
                self.progressChanged.emit(index, total)
            elif kind == 'dfm_result':
                self.show_result(value)
            elif kind == 'job_error' and 'birim' in str(value.get('error', '')).casefold():
                self.unit.setFocus()
        super().handle_events(events)

    def set_busy(self, busy):
        super().set_busy(busy)
        self.save_button.setEnabled(not busy and self.result is not None)

    # ---- results ---------------------------------------------------------------------
    def show_result(self, result):
        self.result = result
        self.view.set_result(result)
        s = result.summary()
        self.summary.setText(f'{s["rules"]} kural · {s["passed"]} geçti · {s["failed"]} bulgulu · '
                             f'{s["not_evaluated"]} değerlendirilemedi\n'
                             f'{s["error"]} hata · {s["warning"]} uyarı · {s["info"]} bilgi · {len(result.parts)} parça')
        colours = COLORS[self.context.appearance]
        tone = {ERROR: colours['danger'], WARNING: colours['warning'], INFO: colours['muted']}
        self.model.removeRows(0, self.model.rowCount())
        for index, f in enumerate(result.findings):
            cells = [SEVERITY_TITLES[f.severity], f.rule_id, f.message, _number(f.measured), _number(f.limit), f.part]
            sort = [SEVERITY_ORDER[f.severity], f.rule_id, f.message, f.measured if f.measured is not None else -1,
                    f.limit if f.limit is not None else -1, f.part]
            row = []
            for text, key in zip(cells, sort):
                item = QStandardItem(text); item.setEditable(False)
                item.setData(index, Qt.UserRole); item.setData(key, Qt.UserRole + 1)
                row.append(item)
            row[0].setForeground(QColor(tone[f.severity])); row[0].setData(f.severity, Qt.UserRole + 2)
            self.model.appendRow(row)
        self.proxy.sort(0)
        self.outcomes.removeRows(0, self.outcomes.rowCount())
        for o in result.outcomes:
            cells = [STATUS_TITLES[o.status], f'{o.rule_id} · {o.rule_name}', _number(o.limit),
                     o.reason if o.status == NOT_EVALUATED else (f'{o.findings} bulgu' if o.status == FAILED else o.reason)]
            items = [QStandardItem(c) for c in cells]
            for item in items:
                item.setEditable(False)
            if o.status == NOT_EVALUATED:
                items[0].setForeground(QColor(colours['warning']))
            self.outcomes.appendRow(items)
        self.notes.setPlainText('\n'.join([result.scope, ''] + result.notes +
                                          ['', f'Profil: {result.profile_name} · sürüm {result.profile_version}'
                                           + ('' if result.profile_verified else ' · doğrulanmamış örnek'),
                                           f'Kaynak: {result.source}', f'SHA-256: {result.sha256}',
                                           f'Analiz: {result.analysed_at}']))
        self.details.clear()
        self.save_button.setEnabled(True)
        self.view_caption.setText(f'{Path(result.source).name} · {len(result.findings)} bulgu. Bulguya tıklayınca geometrisine gidilir.')
        if s['error'] or s['warning']:
            self.set_status(f'Analiz tamamlandı: {s["error"]} hata, {s["warning"]} uyarı, {s["not_evaluated"]} kural değerlendirilemedi.',
                            tone='warning')
        else:
            self.set_status(f'Analiz tamamlandı: seçili kurallarda bulgu yok ({s["not_evaluated"]} kural değerlendirilemedi).',
                            tone='success')

    def apply_filter(self, *args):
        self.proxy.set_filter(self.severity.currentData() or '', self.search.text().strip())

    def finding_selected(self, *args):
        rows = self.table.selectionModel().selectedRows()
        if not rows or self.result is None:
            return
        index = rows[0].data(Qt.UserRole)
        f = self.result.findings[index]
        self.view.select(index)
        lines = [f'<b>{f.rule_id} · {f.rule_name}</b>', f'Önem: {SEVERITY_TITLES[f.severity]}' + (f' · {f.part}' if f.part else ''),
                 '', f.message]
        if f.measured is not None:
            lines.append(f'Ölçülen değer: {_number(f.measured)} {f.unit}')
        if f.limit is not None:
            lines.append(f'Profil sınırı: {_number(f.limit)} {f.unit}')
        if f.difference is not None and f.measured is not None and f.limit is not None:
            lines.append(f'Fark: {_number(f.difference)} {f.unit}')
        lines += ['', f'<b>Öneri:</b> {f.suggestion}']
        rule = REGISTRY.get(f.rule_id)
        if rule is not None:
            outcome = next((o for o in self.result.outcomes if o.rule_id == f.rule_id), None)
            reference = outcome.reference if outcome is not None else rule.reference
            if reference:
                lines.append(f'Kaynak: {reference}')
            if rule.assumptions:
                lines.append(f'Varsayım: {rule.assumptions}')
        if f.entities:
            lines.append('DXF nesneleri: ' + ', '.join(f.entities[:12]))
        self.details.setHtml('<br>'.join(lines))

    def select_finding_row(self, index):
        for row in range(self.proxy.rowCount()):
            if self.proxy.index(row, 0).data(Qt.UserRole) == index:
                self.table.selectRow(row); break

    # ---- files -----------------------------------------------------------------------
    def save_report(self, kind):
        if self.result is None:
            return
        stem = Path(self.result.source).stem + '_DFM'
        filters = {'json': 'DFM analiz sonucu (*.json)', 'csv': 'CSV (*.csv)'}
        path, _ = QFileDialog.getSaveFileName(self, 'DFM raporu kaydet', f'{stem}.{kind}', filters[kind])
        if not path:
            return
        try:
            (reporting.write_json if kind == 'json' else reporting.write_csv)(self.result, path)
        except (OSError, ValueError) as error:
            self.set_status(f'Rapor kaydedilemedi: {error}', True); return
        self.set_status(f'Rapor kaydedildi: {path}')

    def open_result(self):
        path, _ = QFileDialog.getOpenFileName(self, 'DFM analiz sonucu aç', '', 'DFM analiz sonucu (*.json)')
        if not path:
            return
        try:
            result = reporting.read_json(path)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.set_status(f'Analiz sonucu açılamadı: {error}', True); return
        self.show_result(result)
        self.set_status(f'Analiz sonucu açıldı: {Path(path).name}')

    def theme_changed(self):
        self.view.set_appearance(self.context.appearance)
        if self.result is not None:
            self.show_result(self.result)
