"""Hidrolik Ünite Hesaplayıcı: seven input/result tabs over the Qt-free hydraulic core.

All engineering values come from ``modules.hydraulic_unit.core`` (SI). This page
only converts display units, shows the core's issues/rows and starts the existing
save / Excel / JSON / PDF functions. Nothing is recalculated here.
"""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QRect, QSize, QCoreApplication
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (QAbstractItemView, QBoxLayout, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLineEdit, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget, QListWidget, QListWidgetItem, QStackedWidget)

from gui_qt.components import BasePage, Disclosure, button, fit_columns, label, scroll, section_header
from gui_qt.theme import COLORS, ROW_HEIGHT

from .core import models as M
from .core.catalogs import DEBOUNCE_MS, OIL_EXAMPLES, PUMP_LABELS
from .core.cylinder import areas, buckling, calculate_cylinder
from .core.piping import oil_for_grade, recommended_velocity
from .core.pump_motor import pump_for_type
from .core.service import calculate_project
from .core.units import convert
from .core.validation import InputError
from .presentation import result_rows
from . import serialization
from .guidance import STEPS, ADVANCED, SECTION_HELP, ACTIONS
from .beginner import basic_cycle, simple_supported
from .beginner_view import BeginnerView

# ---------------------------------------------------------------------------------------------
# Display units (inputs follow the metric workshop units; the result table follows display_units)
# ---------------------------------------------------------------------------------------------
PLAIN = ('1', 's', 'kg/m3', 'W/m2K')
SHOWN = Qt.UserRole + 1          # table cell: (text written by fill_table, exact SI value)


def to_si(value, unit, si):
    if unit in PLAIN or unit == si:
        return value
    if unit == 'GPa':
        return value * 1e9
    if unit == '%':
        return value / 100
    return convert(value, unit, si)


def from_si(value, unit, si):
    if value is None:
        return None
    if unit in PLAIN or unit == si:
        return value
    if unit == 'GPa':
        return value / 1e9
    if unit == '%':
        return value * 100
    return convert(value, si, unit)


def fmt(value, digits=4):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'evet' if value else 'hayır'
    text = f'{value:.{digits}f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)
    return (text if text not in ('-0', '') else '0').replace('.', ',')


def parse(text):
    """Turkish or dot decimal; empty → None. Raises ValueError for anything else."""
    text = text.strip().replace(' ', '')
    if not text:
        return None
    if text.count(',') == 1 and '.' not in text:
        text = text.replace(',', '.')
    value = float(text)
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError
    return value


CONTROL = {'fixed': 'Sabit debili', 'pressure': 'Basınç kompanzatörlü', 'power': 'Güç limitli'}
ROLE = {'pressure': 'Basınç hattı (valf → silindir)', 'return': 'Dönüş hattı', 'suction': 'Emiş hattı'}
INSTALL = {'stationary': 'Sabit tesis', 'mobile': 'Mobil makine'}
MOUNT = {'pinned_pinned': 'Mafsal – mafsal (K=1)', 'fixed_free': 'Ankastre – serbest (K=2)',
         'fixed_pinned': 'Ankastre – mafsal (K=0,7)', 'fixed_fixed': 'Ankastre – ankastre (K=0,5)'}
KIND = {'extend': 'İleri (itme)', 'regenerate': 'Rejeneratif ileri', 'retract': 'Geri (çekme)',
        'hold': 'Basınçta bekleme', 'idle': 'Boşta'}
GRADES = dict(**{g: g for g in OIL_EXAMPLES}, Custom='Kullanıcı yağı')
SEVERITY = {'info': ('Bilgi', 'muted'), 'warning': ('Uyarı', 'warning'), 'critical': ('Kritik', 'danger')}

# section -> [(field, label, display unit or choices, tooltip)]; SI units come from the model fields.
SI = {'displacement': 'm3/rev', 'angular_speed': 'rad/s', 'max_pressure': 'Pa', 'compensator_pressure': 'Pa',
      'power_limit': 'W', 'leakage_flow': 'm3/s', 'idle_pressure': 'Pa', 'target_velocity': 'm/s', 'min_velocity': 'm/s',
      'max_velocity': 'm/s', 'length': 'm', 'diameter': 'm', 'nu40': 'm2/s', 'nu100': 'm2/s', 'temperature': 'K',
      'residence_time': 's', 'width': 'm', 'height': 'm', 'ambient': 'K', 'target': 'K', 'minimum_pressure': 'Pa',
      'maximum_pressure': 'Pa', 'precharge_pressure': 'Pa', 'delivery_volume': 'm3', 'atmospheric_pressure': 'Pa',
      'relief_pressure': 'Pa', 'selected_motor': 'W', 'bore': 'm', 'rod': 'm', 'stroke': 'm', 'effective_length': 'm',
      'young_modulus': 'Pa', 'initial_position': 'm', 'force': 'N', 'speed': 'm/s', 'duration': 's', 'back_pressure': 'Pa',
      'pressure': 'Pa', 'travel': 'm'}
FORMS = {
    'pump': [('kind', 'Pompa tipi', PUMP_LABELS, 'Tip değişince tipik verimleri "Tipik değerleri uygula" ile alabilirsiniz.'),
             ('control', 'Kontrol', CONTROL, ''),
             ('displacement', 'Deplasman', 'cm3/rev', 'Vg: pompanın bir devirde bastığı geometrik hacim.'),
             ('angular_speed', 'Devir', 'rpm', '50 Hz: 2 kutup ≈ 2900, 4 kutup ≈ 1450, 6 kutup ≈ 960 dev/dak.'),
             ('volumetric_efficiency', 'Hacimsel verim ηv', '1', '0–1'),
             ('mechanical_efficiency', 'Hidromekanik verim ηhm', '1', '0–1'),
             ('max_pressure', 'Pompa azami basıncı', 'bar', ''),
             ('compensator_pressure', 'Kompansatör basıncı', 'bar', 'Yalnız basınç kompanzatörlü pompada.'),
             ('power_limit', 'Güç limiti', 'kW', 'Yalnız güç limitli pompada.'),
             ('leakage_flow', 'Kaçak debisi', 'L/min', 'Sıfırsa bekleme ideal (kaçaksız) kabul edilir.'),
             ('idle_pressure', 'Boşta basınç', 'bar', 'Boşta fazında pompanın gördüğü basınç.')],
    'project': [('relief_factor', 'Emniyet valfi katsayısı', '1', 'Ayar = max(ihtiyaç, kompansatör) × katsayı (≥ 1).'),
                ('relief_pressure', 'Emniyet valfi ayarı (elle)', 'bar', 'Boş bırakılırsa katsayıdan hesaplanır.'),
                ('overload', 'Motor aşırı yük payı', '%', 'Tepe gücü için motorun kısa süreli aşırı yük payı.'),
                ('selected_motor', 'Seçilen motor (elle)', 'kW', 'Boş bırakılırsa nominal seriden seçilir.')],
    'pipe': [('role', 'Hesaplanan hat', ROLE, 'Basınç hattı kaybı çevrim basıncına eklenir.'),
             ('target_velocity', 'Hedef akış hızı', 'm/s', ''), ('min_velocity', 'En düşük hız', 'm/s', ''),
             ('max_velocity', 'En yüksek hız', 'm/s', ''), ('length', 'Hat boyu', 'm', ''),
             ('diameter', 'İç çap (elle)', 'mm', 'Boş bırakılırsa nominal seriden seçilir.'),
             ('zeta', 'Yerel kayıp katsayıları ζ', 'list', 'Dirsek, valf vb. ζ değerleri; noktalı virgülle ayırın.'),
             ('hose_laminar', 'Hortum (laminer düzeltme)', 'bool', '')],
    'oil': [('grade', 'Yağ', GRADES, 'Örnek eğri; gerçek ν40/ν100 değerlerini ve kaynağını girin.'),
            ('nu40', 'Viskozite ν40', 'cSt', '40 °C kinematik viskozite.'),
            ('nu100', 'Viskozite ν100', 'cSt', '100 °C kinematik viskozite.'),
            ('temperature', 'Çalışma sıcaklığı', '°C', ''), ('density', 'Yoğunluk', 'kg/m3', ''),
            ('source', 'Veri kaynağı', 'text', 'Yağ veri sayfası veya üretici adı.')],
    'thermal': [('installation', 'Kurulum', INSTALL, ''),
                ('residence_time', 'Tankta kalma süresi', 's', 'Sabit tesis tipik 180–300 s, mobil 60–120 s.'),
                ('length', 'Tank boyu', 'mm', ''), ('width', 'Tank eni', 'mm', ''), ('height', 'Tank yüksekliği', 'mm', ''),
                ('fill_fraction', 'Doluluk oranı', '1', '0–1'),
                ('heat_transfer', 'Isı geçiş katsayısı k', 'W/m2K', 'Durgun hava ≈ 10–15 W/m²K.'),
                ('ambient', 'Ortam sıcaklığı', '°C', ''), ('target', 'Hedef yağ sıcaklığı', '°C', '')],
    'accumulator': [('enabled', 'Akümülatör hesabı', 'bool', 'Çevrimdeki pompa boyutunu kendiliğinden küçültmez.'),
                    ('minimum_pressure', 'En düşük çalışma basıncı p1', 'bar', 'Gösterge basıncı.'),
                    ('maximum_pressure', 'En yüksek çalışma basıncı p2', 'bar', 'Gösterge basıncı.'),
                    ('precharge_pressure', 'Ön dolum basıncı p0', 'bar', 'Boş bırakılırsa önerilen değer kullanılır.'),
                    ('delivery_volume', 'Verilecek yağ hacmi ΔV', 'L', ''),
                    ('exponent', 'Politropik üs n', '1', 'Hızlı boşalma ≈ 1,4; yavaş ≈ 1,0.'),
                    ('atmospheric_pressure', 'Atmosfer basıncı', 'bar', '')],
}
CYL_COLUMNS = [('id', 'Silindir adı', 'text'), ('bore', 'Piston Ø · mm', 'mm'), ('rod', 'Mil Ø · mm', 'mm'),
               ('stroke', 'Strok · mm', 'mm'), ('initial_position', 'Başlangıç · mm', 'mm'),
               ('efficiency', 'Verim', '1'), ('effective_length', 'Burkulma boyu · mm', 'mm'),
               ('mounting', 'Bağlantı', MOUNT), ('young_modulus', 'E · GPa', 'GPa')]
PHASE_COLUMNS = [('name', 'Faz', 'text'), ('cylinder_id', 'Silindir', 'cyl'), ('kind', 'Hareket', KIND),
                 ('force', 'Kuvvet · kN', 'kN'), ('stroke', 'Strok · mm', 'mm'), ('speed', 'Hız · mm/s', 'mm/s'),
                 ('duration', 'Süre · s', 's'), ('back_pressure', 'Karşı basınç · bar', 'bar')]


class StepChart(QWidget):
    """Cumulative-time step curve of one phase quantity (requirement, not supply)."""

    def __init__(self, title, unit):
        super().__init__()
        self.title, self.unit, self.points, self.appearance = title, unit, [], 'dark'
        self.setMinimumHeight(150)

    def set_values(self, durations, values):
        self.points = list(zip(durations, values)); self.update()

    def paintEvent(self, event):
        c = COLORS[self.appearance]
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(c['canvas']))
        p.setPen(QColor(c['text'])); bold = QFont(self.font()); bold.setBold(True); p.setFont(bold)
        p.drawText(QRectF(8, 4, self.width() - 16, 18), Qt.AlignLeft, f'{self.title} · {self.unit}')
        p.setFont(self.font())
        left, top, right, bottom = 54, 28, self.width() - 12, self.height() - 26
        if not self.points or right - left < 40 or bottom - top < 30:
            p.setPen(QColor(c['muted'])); p.drawText(self.rect(), Qt.AlignCenter, 'Geçerli sonuç yok'); return
        total = sum(d for d, _ in self.points) or 1
        top_value = max(v for _, v in self.points) or 1
        top_value *= 1.15
        sx = (right - left) / total; sy = (bottom - top) / top_value
        p.setPen(QPen(QColor(c['grid']), 1))
        for i in range(5):
            y = bottom - (bottom - top) * i / 4
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(QColor(c['muted'])); p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter, fmt(top_value * i / 4, 1))
            p.setPen(QPen(QColor(c['grid']), 1))
        p.setPen(QColor(c['muted']))
        p.drawText(QRectF(left, bottom + 4, right - left, 18), Qt.AlignRight, f'Σt = {fmt(total, 2)} s')
        pen = QPen(QColor(c['accent']), 2); p.setPen(pen)
        t = 0.; previous = None
        for duration, value in self.points:
            x0, x1, y = left + t * sx, left + (t + duration) * sx, bottom - value * sy
            if previous is not None:
                p.drawLine(QPointF(x0, previous), QPointF(x0, y))
            p.drawLine(QPointF(x0, y), QPointF(x1, y)); previous = y; t += duration
        p.end()


class FormPage(QWidget):
    """Dar alanda ayar gruplarını alt alta dizer; sayılar kesilmez."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'columns'):
            self.columns.setDirection(QBoxLayout.TopToBottom if self.width() < 680 else QBoxLayout.LeftToRight)


class IssueList(QListWidget):
    """Uyarı ve çözüm metnini dar panelde üç noktayla kesmeden sarar."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        width = max(100,self.viewport().width()-14)
        for row in range(self.count()):
            item = self.item(row)
            bounds = self.fontMetrics().boundingRect(QRect(0,0,width,10000),Qt.TextWordWrap,item.text())
            size = QSize(width,bounds.height()+12)
            if item.sizeHint() != size: item.setSizeHint(size)


def _table(headers, elastic=0, defaults=None):
    table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide(); table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    table.setSelectionBehavior(QAbstractItemView.SelectRows); table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter); table.setShowGrid(False)
    fit_columns(table, elastic=elastic, minimum=90, defaults=defaults or {})
    return table


class HydraulicPage(BasePage):
    quiet_cancel_on_close = True

    def __init__(self, context):
        super().__init__(context, 'Hidrolik Ünite Hesaplayıcı',
                         'Silindir ölçülerini ve yapılacak hareketleri girin; motor, pompa ve soğutma ihtiyacını öğrenin.')
        self.project = self.restore_project()
        self.result = None; self.pdf_job = None; self.loading = False; self.path = None
        self.fields = {}; self.invalid_widgets = []; self.advanced_sections = {}
        self.problem_field = None
        self.open_button = self.action('Proje aç…', self.open_project)
        self.save_button = self.action('Proje kaydet…', self.save_project)
        self.example_button = self.action('Örnek pres ünitesi', self.load_example)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(DEBOUNCE_MS)
        self.timer.timeout.connect(self.recalculate)

        top = QHBoxLayout(); top.setSpacing(8)
        self.name = QLineEdit(); self.name.setAccessibleName('Proje adı'); self.name.setMaximumWidth(320)
        self.name.textEdited.connect(self.changed)
        self.units = QComboBox(); self.units.addItem('Metrik (bar · L/min)', 'metric'); self.units.addItem('ABD (psi · gpm)', 'us')
        self.units.setToolTip('Yalnız sonuç tablosunun birimleri; girdiler ve SI hesap değişmez.')
        self.units.currentIndexChanged.connect(self.changed)
        top.addWidget(label('Proje', 'muted')); top.addWidget(self.name, 1); top.addStretch(1)
        self.view_mode=QComboBox();self.view_mode.addItem('Kolay kullanım',0);self.view_mode.addItem('Ayrıntılı ayarlar',1)
        self.view_mode.setAccessibleName('Hidrolik giriş görünümü');top.addWidget(self.view_mode)
        top.addWidget(label('Sonuç birimi', 'muted')); top.addWidget(self.units)
        self.layout.addLayout(top)

        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.build_cylinders(), 'Silindirler')
        self.tabs.addTab(self.build_phases(), 'Çevrim')
        self.tabs.addTab(self.form_tab(('pump', 'Pompa'), ('project', 'Emniyet valfi ve motor'), extra=self.pump_tools()), 'Pompa / motor')
        self.tabs.addTab(self.form_tab(('pipe', 'Hat'), ('oil', 'Yağ'), extra=self.pipe_tools()), 'Hat / yağ')
        self.tabs.addTab(self.form_tab(('thermal', 'Tank ve ısı dengesi'), result_key='thermal'), 'Tank / ısı')
        self.tabs.addTab(self.form_tab(('accumulator', 'Akümülatör'), result_key='accumulator'), 'Akümülatör')
        self.tabs.addTab(self.build_results(), 'Rapor')
        guide = QHBoxLayout()
        captions = QVBoxLayout(); captions.setSpacing(2)
        self.step_title = label('', 'section'); self.step_help = label('', 'muted')
        captions.addWidget(self.step_title); captions.addWidget(self.step_help)
        guide.addLayout(captions, 1)
        self.previous_button = button('← Önceki', lambda: self.tabs.setCurrentIndex(self.tabs.currentIndex()-1))
        self.next_button = button('Sonraki →', lambda: self.tabs.setCurrentIndex(self.tabs.currentIndex()+1))
        guide.addWidget(self.previous_button); guide.addWidget(self.next_button)
        self.guide_widget=QWidget();self.guide_widget.setLayout(guide);self.layout.addWidget(self.guide_widget)
        self.tabs.currentChanged.connect(self.update_step)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        self.input_stack=QStackedWidget();self.simple=BeginnerView(self)
        self.input_stack.addWidget(self.simple);self.input_stack.addWidget(self.tabs)
        self.summary_panel=self.build_summary()
        self.splitter.addWidget(self.input_stack); self.splitter.addWidget(self.summary_panel)
        self.splitter.setStretchFactor(0, 3); self.splitter.setStretchFactor(1, 1); self.splitter.setSizes([900, 360])
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()
        self.controls += [self.input_stack, self.view_mode, self.open_button, self.save_button, self.example_button]
        preferred=self.settings.get('hydraulic_view_mode',0)
        self.view_mode.setCurrentIndex(1 if preferred==1 or not simple_supported(self.project) else 0)
        self.input_stack.setCurrentIndex(self.view_mode.currentIndex())
        self.view_mode.currentIndexChanged.connect(self.switch_view)
        self.statusChanged.connect(lambda text,error:self.simple.status.setText(text))
        self.populate(); self.recalculate()
        self.update_step()
        self.apply_view_layout()
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel_pdf)

    # ----------------------------------------------------------------- building
    def apply_view_layout(self):
        detailed=self.input_stack.currentIndex()==1
        self.guide_widget.setVisible(detailed);self.summary_panel.setVisible(detailed)

    def switch_view(self,index):
        if self.loading:return
        previous=self.input_stack.currentIndex()
        try:project=self.build_project()
        except InputError as error:
            self.view_mode.blockSignals(True);self.view_mode.setCurrentIndex(previous);self.view_mode.blockSignals(False)
            self.show_invalid(error);return
        self.project=project;self.populate(reset_point=False);self.input_stack.setCurrentIndex(index)
        self.apply_view_layout();self.settings.set('hydraulic_view_mode',index);self.recalculate()

    def open_detailed(self,tab=0):
        self.view_mode.setCurrentIndex(1)
        if self.input_stack.currentIndex()==1:self.tabs.setCurrentIndex(tab)

    def use_basic_cycle(self):
        try:
            project=self.build_project();new=basic_cycle(project)
        except InputError as error:self.show_invalid(error);return
        self.simple.previous_cycle=project
        self.project=new;self.populate();self.recalculate()

    def undo_basic_cycle(self):
        if self.simple.previous_cycle is None:return
        try:self.project=replace(self.build_project(),phases=self.simple.previous_cycle.phases)
        except InputError as error:self.show_invalid(error);return
        self.simple.previous_cycle=None
        self.populate();self.recalculate()

    def use_pump_recommendation(self):
        if self.result is None:return
        value=self.result.cycle['displacement']['nominal']
        if value is None:return
        self.project=replace(self.project,pump=replace(self.project.pump,displacement=value))
        self.populate();self.recalculate()
        self.set_status('Önerilen pompa hacmi uygulandı; basınç, motor ve soğutma kontrollerini yeniden inceleyin.')

    def update_step(self, *args):
        index = self.tabs.currentIndex(); title, help_ = STEPS[index]
        self.step_title.setText(f'{index+1}/7 · {title}'); self.step_help.setText(help_)
        self.previous_button.setEnabled(index > 0); self.next_button.setEnabled(index < 6)

    def field(self, key, title, unit, tip):
        if isinstance(unit, dict):
            widget = QComboBox()
            for value, text in unit.items():
                widget.addItem(text, value)
            widget.currentIndexChanged.connect(self.changed)
        elif unit == 'bool':
            widget = QCheckBox(title); widget.toggled.connect(self.changed)
        else:
            widget = QLineEdit(); widget.textEdited.connect(self.changed)
            if unit not in ('text', 'list'):
                widget.setMinimumWidth(100)
                widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        widget.setAccessibleName(title); widget.setToolTip(tip)
        if isinstance(widget, QLineEdit) and key in ('project.relief_pressure','project.selected_motor','pipe.diameter','accumulator.precharge_pressure'):
            widget.setPlaceholderText('Otomatik')
        self.fields[key] = (widget, unit, tip)
        return widget

    def form_tab(self, *sections, extra=None, result_key=None):
        page = FormPage(); box = QVBoxLayout(page); box.setContentsMargins(8, 8, 8, 8); box.setSpacing(10)
        columns = QHBoxLayout(); columns.setSpacing(24)
        page.columns = columns
        for section, title in sections:
            column = QVBoxLayout(); column.addWidget(label(title, 'section'))
            column.addWidget(label(SECTION_HELP[section], 'muted'))
            form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            advanced = QWidget(); advanced_form = QFormLayout(advanced)
            advanced_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            for name, title_, unit, tip in FORMS[section]:
                widget = self.field(f'{section}.{name}', title_, unit, tip)
                target = advanced_form if name in ADVANCED[section] else form
                if unit == 'bool':
                    target.addRow(widget)
                else:
                    shown = '' if isinstance(unit, dict) or unit in ('1', 'text', 'list') else f' · {unit.replace("3", "³").replace("m2", "m²")}'
                    target.addRow(title_ + shown, widget)
            column.addLayout(form)
            disclosure = Disclosure('Gelişmiş ayarlar', advanced)
            self.advanced_sections[section] = disclosure
            column.addWidget(disclosure); column.addStretch(1); columns.addLayout(column, 1)
        box.addLayout(columns)
        if extra is not None:
            box.addWidget(extra)
        if result_key:
            table = _table(['Sonuç', 'Değer']); table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setMinimumHeight(150); setattr(self, f'{result_key}_table', table)
            box.addWidget(label('Sonuç', 'section')); box.addWidget(table)
        box.addStretch(1)
        return scroll(page)

    def pump_tools(self):
        row = QWidget(); box = QHBoxLayout(row); box.setContentsMargins(0, 0, 0, 0)
        self.pump_defaults_button = button('Tipik değerleri uygula', self.apply_pump_defaults)
        self.pump_defaults_button.setToolTip('Seçili pompa tipinin örnek verimlerini ve azami basıncını yazar (üretici verisi değildir).')
        box.addWidget(self.pump_defaults_button); box.addStretch(1)
        return row

    def pipe_tools(self):
        row = QWidget(); box = QHBoxLayout(row); box.setContentsMargins(0, 0, 0, 0)
        self.velocity_button = button('Önerilen hızları uygula', self.apply_recommended_velocity)
        self.velocity_button.setToolTip('Hat rolüne ve basınca göre başlangıç önerisi; yalnız siz basınca uygulanır.')
        self.oil_button = button('Örnek yağ verilerini kullan', self.apply_oil_grade)
        box.addWidget(self.velocity_button); box.addWidget(self.oil_button); box.addStretch(1)
        return row

    def build_cylinders(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(8, 8, 8, 8); box.setSpacing(8)
        box.addWidget(label('Önce silindirin ölçülerini girin. Çevrimde hareketleri bu silindir adıyla seçeceksiniz. Hücreye çift tıklayarak düzenleyin.', 'muted'))
        commands = QHBoxLayout()
        self.add_cylinder_button = button('+ Silindir', self.add_cylinder)
        self.remove_cylinder_button = button('Seçiliyi sil', self.remove_cylinder)
        commands.addWidget(self.add_cylinder_button); commands.addWidget(self.remove_cylinder_button); commands.addStretch(1)
        box.addLayout(commands)
        self.cylinder_advanced = QCheckBox('Verim ve burkulma ayarlarını göster')
        self.cylinder_advanced.toggled.connect(self.show_cylinder_advanced)
        box.addWidget(self.cylinder_advanced)
        self.cylinder_table = _table([title for _, title, _ in CYL_COLUMNS], elastic=7, defaults={0: 80}); self.cylinder_table.setMinimumHeight(120)
        self.cylinder_table.setMaximumHeight(220)
        self.show_cylinder_advanced(False)
        self.cylinder_table.cellChanged.connect(self.changed)
        self.cylinder_table.itemSelectionChanged.connect(self.update_cylinder_check)
        box.addWidget(self.cylinder_table, 1)
        check_page = QWidget(); check_box = QVBoxLayout(check_page); check_box.setContentsMargins(0,0,0,0)
        check_box.addWidget(label('Seçili silindiri bağımsız inceler. Buradaki hız ve kuvvet çevrim fazlarını değiştirmez.', 'muted'))
        check = QHBoxLayout(); check.setSpacing(24)
        form = QFormLayout()
        self.point = {}
        for key, title, unit in (('kind', 'Hareket', {k: KIND[k] for k in ('extend', 'retract', 'regenerate')}),
                                 ('pressure', 'Çalışma basıncı · bar', 'bar'), ('force', 'Gerekli kuvvet · kN', 'kN'),
                                 ('speed', 'Hız · mm/s', 'mm/s'), ('travel', 'Hareket boyu · mm', 'mm'),
                                 ('back_pressure', 'Karşı basınç · bar', 'bar')):
            widget = self.field('point.' + key, title, unit, '')
            form.addRow(title, widget); self.point[key] = widget
        check.addLayout(form, 1)
        self.cylinder_result = _table(['Büyüklük', 'Değer']); self.cylinder_result.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cylinder_result.setMinimumHeight(180)
        check.addWidget(self.cylinder_result, 1)
        check_box.addLayout(check)
        self.cylinder_check_section = Disclosure('Seçili silindiri ayrıca kontrol et', check_page)
        box.addWidget(self.cylinder_check_section); box.addStretch(1)
        return scroll(page)

    def show_cylinder_advanced(self, visible):
        for col in range(5, len(CYL_COLUMNS)):
            self.cylinder_table.setColumnHidden(col, not visible)

    def build_phases(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(8, 8, 8, 8); box.setSpacing(8)
        box.addWidget(label('Fazlar sırayla çalışır. Harekette hız veya süreden yalnız birini girin; bekleme ve boşta yalnız süre.', 'muted'))
        commands = QHBoxLayout()
        for text, callback in (('+ Faz', self.add_phase), ('Kopyala', lambda: self.add_phase(copy=True)), ('Sil', self.remove_phase),
                               ('↑', lambda: self.move_phase(-1)), ('↓', lambda: self.move_phase(1))):
            control = button(text, callback)
            if text in ('↑', '↓'):
                control.setFixedWidth(32)
            commands.addWidget(control)
        commands.addStretch(1); box.addLayout(commands)
        entry = QHBoxLayout()
        entry.addWidget(label('Seçili hareketi tanımlama', 'muted'))
        self.phase_input_method = QComboBox()
        self.phase_input_method.addItem('Hız gir — süre hesaplansın', 'speed')
        self.phase_input_method.addItem('Süre gir — hız hesaplansın', 'duration')
        self.phase_input_method.setAccessibleName('Seçili faz için hız veya süre girişi')
        self.phase_input_method.currentIndexChanged.connect(self.choose_phase_input)
        entry.addWidget(self.phase_input_method); entry.addStretch(1); box.addLayout(entry)
        self.phase_table = _table([title for _, title, _ in PHASE_COLUMNS], defaults={1: 96, 2: 170}); self.phase_table.setMinimumHeight(150)
        self.phase_table.cellChanged.connect(self.changed)
        self.phase_table.itemSelectionChanged.connect(self.update_phase_input)
        box.addWidget(self.phase_table, 1)
        box.addWidget(label('Faz sonuçları', 'section'))
        self.phase_results = _table(['Faz', 'Konum · mm', 'Süre · s', 'Gerekli basınç · bar', 'Gerekli debi · L/min',
                                     'Besleme basıncı · bar', 'Mil gücü · kW', 'Karşılanıyor'])
        self.phase_results.setEditTriggers(QAbstractItemView.NoEditTriggers); self.phase_results.setMinimumHeight(140)
        box.addWidget(self.phase_results, 1)
        return page

    def build_results(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(8, 8, 8, 8); box.setSpacing(8)
        reports = QHBoxLayout()
        self.excel_button = button('Excel raporu…', lambda: self.export('excel'))
        self.json_button = button('JSON…', lambda: self.export('json'))
        self.pdf_button = button('PDF raporu…', self.export_pdf, primary=False)
        self.cancel_pdf_button = button('PDF işlemini durdur', self.cancel_pdf); self.cancel_pdf_button.hide()
        self.report_status = label('', 'muted')
        for widget in (self.excel_button, self.json_button, self.pdf_button, self.cancel_pdf_button):
            reports.addWidget(widget)
        reports.addWidget(self.report_status, 1)
        box.addLayout(reports)
        charts = QHBoxLayout(); charts.setSpacing(8)
        self.charts = {'pressure': StepChart('Gerekli basınç', 'bar'), 'flow': StepChart('Gerekli debi', 'L/min'),
                       'shaft_power': StepChart('Pompa mil gücü', 'kW')}
        for chart in self.charts.values():
            chart.appearance = self.context.appearance
            charts.addWidget(chart, 1)
        box.addLayout(charts)
        box.addWidget(label('Mil gücü elektrik şebekesinden çekilen güç değildir. Basınç/debi eğrileri ihtiyaçtır, pompa beslemesi değildir.', 'muted'))
        self.rows_table = _table(['Sonuç', 'Değer', 'Birim']); self.rows_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rows_table.setMinimumHeight(220)
        box.addWidget(self.rows_table, 1)
        self.assumptions = label('', 'muted')
        box.addWidget(Disclosure('Varsayımlar ve kapsam', self.assumptions))
        return scroll(page)

    def build_summary(self):
        panel = QWidget(); box = QVBoxLayout(panel); box.setContentsMargins(8, 0, 0, 0); box.setSpacing(6)
        self.headline = label('—', 'result'); box.addWidget(self.headline)
        self.status_note = label('', 'muted'); box.addWidget(self.status_note)
        self.status_note.setTextFormat(Qt.PlainText)
        self.fix_button = button('İlgili ayara git →', self.focus_first_problem)
        self.fix_button.hide(); box.addWidget(self.fix_button)
        self.summary_table = _table(['Özet', 'Değer']); self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        fit_columns(self.summary_table,elastic=0,minimum=120,defaults={1:110},autofit=())
        self.summary_table.setMinimumHeight(300); self.summary_table.setMaximumHeight(330)
        box.addWidget(self.summary_table)
        box.addWidget(section_header('Uyarılar'))
        self.issue_list = IssueList(); self.issue_list.setWordWrap(True); self.issue_list.setAccessibleName('Hesap uyarıları')
        self.issue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.issue_list.setTextElideMode(Qt.ElideNone); self.issue_list.setResizeMode(QListWidget.Adjust)
        self.issue_list.itemActivated.connect(self.focus_issue); self.issue_list.itemClicked.connect(self.focus_issue)
        box.addWidget(self.issue_list, 1)
        panel.setMinimumWidth(280)
        return panel

    # ----------------------------------------------------------------- project <-> widgets
    def restore_project(self):
        text = self.settings.get('hydraulic_unit_project')
        if isinstance(text, str):
            try:
                return serialization.loads(text)
            except Exception:
                pass
        return M.Project()

    def set_widget(self, key, value):
        widget, unit, _ = self.fields[key]
        if isinstance(widget, QComboBox):
            widget.setCurrentIndex(max(widget.findData(value), 0))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif unit == 'list':
            widget.setText('; '.join(fmt(v) for v in value))
        elif unit == 'text':
            widget.setText(str(value))
        else:
            name = key.split('.')[-1]
            widget.setText('' if value is None else fmt(from_si(value, unit, SI.get(name, unit)), 6))
            widget._shown = (widget.text(), value)     # untouched text reads back the exact stored SI value

    def populate(self, *, reset_point=True):
        self.loading = True
        try:
            p = self.project
            self.name.setText(p.name); self.units.setCurrentIndex(max(self.units.findData(p.display_units), 0))
            for section in ('pump', 'pipe', 'oil', 'thermal', 'accumulator'):
                for name, *_ in FORMS[section]:
                    self.set_widget(f'{section}.{name}', getattr(getattr(p, section), name))
            for name, *_ in FORMS['project']:
                self.set_widget(f'project.{name}', getattr(p, name))
            if reset_point:
                point = M.CylinderOperatingPoint()
                for name in self.point:
                    self.set_widget('point.' + name, getattr(point, name))
            self.fill_table(self.cylinder_table, CYL_COLUMNS, p.cylinders)
            self.fill_table(self.phase_table, PHASE_COLUMNS, p.phases)
            if hasattr(self,'simple'):self.simple.populate(p)
        finally:
            self.loading = False
        self.sync_optional_controls()

    def fill_table(self, table, columns, items):
        table.blockSignals(True)
        for row in range(table.rowCount()):            # drop old row editors now, not at the next deferred delete
            for col in range(table.columnCount()):
                widget = table.cellWidget(row, col)
                if widget is not None:
                    widget.hide(); table.removeCellWidget(row, col)
        table.setRowCount(len(items))
        for row, item in enumerate(items):
            for col, (name, _, unit) in enumerate(columns):
                value = getattr(item, name)
                if isinstance(unit, dict) or unit == 'cyl':
                    combo = QComboBox(); combo.setMinimumWidth(0)       # never wider than its column
                    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); combo.setMinimumContentsLength(2)
                    options = unit if isinstance(unit, dict) else {c.id: c.id for c in self.project.cylinders}
                    for key, text in options.items():
                        combo.addItem(text, key)
                    combo.setCurrentIndex(max(combo.findData(value), 0))
                    combo.currentIndexChanged.connect(self.changed)
                    if table is self.phase_table and name == 'kind':
                        combo.currentIndexChanged.connect(lambda _, row=row: self.phase_kind_changed(row))
                    table.setCellWidget(row, col, combo)
                else:
                    text = str(value) if unit == 'text' else '' if value is None else fmt(from_si(value, unit, SI.get(name, unit)), 6)
                    cell = QTableWidgetItem(text); cell.setData(SHOWN, (text, value))
                    if unit != 'text':
                        cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    table.setItem(row, col, cell)
        table.blockSignals(False)
        if table is self.phase_table:
            self.configure_phase_cells()
            self.update_phase_input()

    def configure_phase_cells(self):
        """Hız/süre ve hareket/bekleme için yalnız kullanılabilir hücreler düzenlenir."""
        names = [c[0] for c in PHASE_COLUMNS]
        for row in range(self.phase_table.rowCount()):
            kind = self.phase_table.cellWidget(row,names.index('kind')).currentData()
            moving = kind in ('extend','retract','regenerate')
            for name in ('stroke','speed','duration','force','back_pressure'):
                item = self.phase_table.item(row,names.index(name))
                allowed = moving or name in ('duration','force','back_pressure') and kind == 'hold' or name == 'duration' and kind == 'idle'
                item.setFlags(item.flags() | Qt.ItemIsEditable if allowed else item.flags() & ~Qt.ItemIsEditable)
                item.setToolTip('Hareket boyu bu fazdaki mesafedir; toplam silindir stroku değildir.' if name == 'stroke' and moving
                    else 'Hız veya süre girin. Seçimi yukarıdaki menüden değiştirebilirsiniz.' if name in ('speed','duration') and moving
                    else 'Bu hareket türünde kullanılmıyor.' if not allowed else '')

    def update_phase_input(self):
        if not self.phase_table.rowCount(): return
        row = self._phase_index()
        names = [c[0] for c in PHASE_COLUMNS]
        kind = self.phase_table.cellWidget(row,names.index('kind')).currentData()
        speed = self.phase_table.item(row,names.index('speed')).text().strip()
        self.phase_input_method.blockSignals(True)
        self.phase_input_method.setCurrentIndex(0 if speed else 1)
        self.phase_input_method.setEnabled(kind in ('extend','retract','regenerate'))
        self.phase_input_method.blockSignals(False)

    def choose_phase_input(self, *args):
        if self.loading or not self.phase_table.rowCount(): return
        row = self._phase_index(); names = [c[0] for c in PHASE_COLUMNS]
        selected = self.phase_input_method.currentData()
        other = 'duration' if selected == 'speed' else 'speed'
        self.phase_table.blockSignals(True)
        self.phase_table.item(row,names.index(other)).setText('')
        item = self.phase_table.item(row,names.index(selected))
        self.phase_table.setCurrentCell(row,names.index(selected))
        self.phase_table.blockSignals(False)
        self.phase_table.editItem(item)
        self.changed()

    def phase_kind_changed(self, row):
        if self.loading: return
        names = [c[0] for c in PHASE_COLUMNS]
        kind = self.phase_table.cellWidget(row,names.index('kind')).currentData()
        if kind in ('hold','idle'):
            self.phase_table.item(row,names.index('speed')).setText('')
        if kind == 'idle':
            self.phase_table.item(row,names.index('force')).setText('0')
        self.configure_phase_cells(); self.update_phase_input()

    def read_value(self, key):
        widget, unit, _ = self.fields[key]
        if isinstance(widget, QComboBox):
            return widget.currentData()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if unit == 'text':
            return widget.text()
        if unit == 'list':
            parts = [part for part in widget.text().replace(',', '.').split(';') if part.strip()]
            try:
                return tuple(float(part) for part in parts)
            except ValueError:
                raise InputError(key, 'ζ değerlerini noktalı virgülle ayırın (ör. 1; 0,5).') from None
        shown = getattr(widget, '_shown', None)
        if shown is not None and shown[0] == widget.text():
            return shown[1]
        try:
            value = parse(widget.text())
        except ValueError:
            raise InputError(key, 'Sayı girin (ondalık için virgül).') from None
        if value is None:
            return None
        return to_si(value, unit, SI.get(key.split('.')[-1], unit))

    def read_table(self, table, columns, factory, prefix):
        items = []
        for row in range(table.rowCount()):
            values = {}
            kind = table.cellWidget(row,2).currentData() if factory is M.Phase else None
            for col, (name, _, unit) in enumerate(columns):
                key = f'{prefix}.{row}.{name}'
                if factory is M.Phase and kind in ('hold','idle'):
                    if name == 'speed':
                        values[name] = None; continue
                    if name == 'stroke':
                        values[name] = self.project.phases[row].stroke if row < len(self.project.phases) else M.Phase().stroke
                        continue
                    if kind == 'idle' and name in ('force','back_pressure'):
                        values[name] = 0.; continue
                if isinstance(unit, dict) or unit == 'cyl':
                    values[name] = table.cellWidget(row, col).currentData(); continue
                cell = table.item(row, col); text = cell.text() if cell else ''
                if unit == 'text':
                    values[name] = text; continue
                shown = cell.data(SHOWN) if cell else None
                if shown and shown[0] == text and shown[1] is not None:
                    values[name] = shown[1]; continue
                try:
                    value = parse(text)
                except ValueError:
                    raise InputError(key, 'Sayı girin (ondalık için virgül).') from None
                values[name] = None if value is None else to_si(value, unit, SI.get(name, unit))
                if values[name] is None and name not in ('speed', 'duration'):
                    raise InputError(key, 'Değer gerekli.')
            items.append(factory(**values))
        return tuple(items)

    def build_project(self):
        if hasattr(self,'simple') and self.input_stack.currentIndex()==0:
            return replace(self.simple.read_project(self.project),name=self.name.text(),display_units=self.units.currentData())
        sections = {}
        for section, cls in (('pump', M.Pump), ('pipe', M.Pipe), ('oil', M.Oil), ('thermal', M.Thermal), ('accumulator', M.Accumulator)):
            if section == 'accumulator' and not self.fields['accumulator.enabled'][0].isChecked():
                sections[section] = replace(self.project.accumulator, enabled=False)
                continue
            ignored = set()
            if section == 'pump':
                control = self.fields['pump.control'][0].currentData()
                if control != 'pressure': ignored.add('compensator_pressure')
                if control != 'power': ignored.add('power_limit')
            values = {name: getattr(getattr(self.project,section),name) if name in ignored else self.read_value(f'{section}.{name}')
                      for name, *_ in FORMS[section]}
            for name, value in values.items():
                if value is None and name not in ('diameter', 'precharge_pressure'):
                    raise InputError(f'{section}.{name}', 'Değer gerekli.')
            sections[section] = cls(**values)
        extra = {name: self.read_value(f'project.{name}') for name, *_ in FORMS['project']}
        for name in ('relief_factor', 'overload'):
            if extra[name] is None:
                raise InputError(f'project.{name}', 'Değer gerekli.')
        cylinders = self.read_table(self.cylinder_table, CYL_COLUMNS, M.Cylinder, 'cylinders')
        for index, cylinder in enumerate(cylinders):       # name the row of a cylinder-local error
            try:
                areas(cylinder); buckling(cylinder, 0)
            except InputError as error:
                raise InputError(f'cylinders.{index}.{error.field}', str(error)) from None
        phases = self.read_table(self.phase_table, PHASE_COLUMNS, M.Phase, 'phases')
        return M.Project(name=self.name.text(), cylinders=cylinders, phases=phases, display_units=self.units.currentData(),
                         **sections, **extra)

    # ----------------------------------------------------------------- calculation
    def changed(self, *args):
        if self.loading:
            return
        self.sync_optional_controls()
        self.result = None
        self.headline.setText('Hesap güncelleniyor…')
        if hasattr(self,'simple'):
            self.simple.verdict.setText('Bilgiler değişti; hesap güncelleniyor…');self.simple.results.setRowCount(0)
        self.status_note.setText('Girdiler değişti. Sonuçlar yeniden hesaplanıyor; rapor almak için tamamlanmasını bekleyin.')
        self.refresh_actions()
        self.timer.start()

    def sync_optional_controls(self):
        control = self.fields['pump.control'][0].currentData()
        for field, mode in (('compensator_pressure','pressure'),('power_limit','power')):
            self.fields['pump.'+field][0].setEnabled(control == mode)
        enabled = self.fields['accumulator.enabled'][0].isChecked()
        for name, *_ in FORMS['accumulator']:
            if name != 'enabled': self.fields['accumulator.'+name][0].setEnabled(enabled)

    def clear_invalid(self):
        for widget in self.invalid_widgets:
            try:
                widget.setProperty('invalid', False); widget.setToolTip(getattr(widget, '_tip', ''))
                widget.style().unpolish(widget); widget.style().polish(widget)
            except RuntimeError:
                pass
        for table in (self.cylinder_table, self.phase_table):
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item is not None and item.data(Qt.UserRole):
                        item.setBackground(QColor(0, 0, 0, 0)); item.setToolTip(''); item.setData(Qt.UserRole, False)
        self.invalid_widgets = []

    def mark_invalid(self, field, message):
        """Outline the field an InputError names; tables colour the cell and select its tab."""
        parts = field.split('.')
        if parts[0] in ('cylinders', 'phases') and len(parts) >= 2 and parts[1].isdigit():
            table, columns, tab = ((self.cylinder_table, CYL_COLUMNS, 0) if parts[0] == 'cylinders'
                                   else (self.phase_table, PHASE_COLUMNS, 1))
            row = int(parts[1]); names = [c[0] for c in columns]
            col = names.index(parts[2]) if len(parts) > 2 and parts[2] in names else 0
            if row < table.rowCount():
                if parts[0] == 'cylinders' and col >= 5:
                    self.cylinder_advanced.setChecked(True)
                item = table.item(row, col)
                if item is not None:
                    item.setBackground(QColor(COLORS[self.context.appearance]['danger']).lighter(160 if self.context.appearance == 'light' else 60))
                    item.setToolTip(message); item.setData(Qt.UserRole, True)
                widget = table.cellWidget(row, col)
                if widget is not None:
                    self._flag(widget, message)
            return tab
        key = field if field in self.fields else next((k for k in self.fields if k.split('.', 1)[-1] == field
                                                       or k == 'project.' + field), None)
        if key is None and parts[0] in ('pump', 'pipe', 'oil', 'thermal', 'accumulator'):
            return {'pump': 2, 'pipe': 3, 'oil': 3, 'thermal': 4, 'accumulator': 5}[parts[0]]
        if key is None:
            return None
        section, name = key.split('.',1)
        if name in ADVANCED.get(section,set()):
            self.advanced_sections[section].set_expanded(True)
        if section == 'point': self.cylinder_check_section.set_expanded(True)
        self._flag(self.fields[key][0], message)
        return {'pump': 2, 'project': 2, 'pipe': 3, 'oil': 3, 'thermal': 4, 'accumulator': 5, 'point': 0}.get(key.split('.')[0])

    def _flag(self, widget, message):
        widget._tip = widget.toolTip() if not widget.property('invalid') else getattr(widget, '_tip', '')
        widget.setProperty('invalid', True); widget.setToolTip(message)
        widget.style().unpolish(widget); widget.style().polish(widget)
        self.invalid_widgets.append(widget)

    def recalculate(self):
        self.timer.stop(); self.clear_invalid()
        try:
            project = self.build_project()
            result = calculate_project(project)
        except InputError as error:
            self.show_invalid(error); return
        self.project, self.result = project, result
        try:
            self.settings.set('hydraulic_unit_project', serialization.dumps(project))
        except Exception:
            pass
        self.show_result()
        self.update_cylinder_check()

    def show_invalid(self, error):
        self.result = None
        if hasattr(self,'simple'):self.simple.show_error(error)
        self.problem_field = error.field
        tab = self.mark_invalid(error.field, str(error))
        self.headline.setText('Girdileri kontrol edin')
        self.status_note.setText(f'{error}\nDüzeltilecek alanı açmak için aşağıdaki düğmeyi kullanın.'); self.status_note.setProperty('role', 'error')
        self.fix_button.setVisible(tab is not None)
        self.status_note.style().unpolish(self.status_note); self.status_note.style().polish(self.status_note)
        for table in (self.summary_table, self.rows_table, self.phase_results, self.thermal_table, self.accumulator_table):
            table.setRowCount(0)
        self.issue_list.clear()
        for chart in self.charts.values():
            chart.set_values([], [])
        self.assumptions.setText('')
        self.refresh_actions()
        self.set_status(str(error), True)
        if tab is not None and self.tabs.currentIndex() != 6:
            self.tabs.tabBar().setTabTextColor(tab, QColor(COLORS[self.context.appearance]['danger']))

    def refresh_actions(self):
        ready = self.result is not None and self.pdf_job is None and not self.busy
        for widget in (self.excel_button, self.json_button, self.pdf_button):
            widget.setEnabled(ready)
            widget.setToolTip('' if ready else 'Geçerli bir sonuç gerekli.')
        self.save_button.setEnabled(self.result is not None and not self.busy)
        if hasattr(self,'simple'):self.simple.update_actions(self.result,self.busy,self.pdf_job is not None)

    def _rows(self, table, rows, tips=None):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value if isinstance(value, str) else fmt(value, 3))
                if c and not isinstance(value, str):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if tips and tips[r]:
                    item.setToolTip(tips[r])
                table.setItem(r, c, item)

    def show_result(self):
        r, p = self.result, self.project
        if hasattr(self,'simple'):self.simple.show_result(p,r)
        for index in range(self.tabs.count()):
            self.tabs.tabBar().setTabTextColor(index, QColor())
        cycle = r.cycle
        critical = [i for i in r.issues if i.severity == 'critical']
        self.headline.setText('Kritik kontrol yok' if r.feasible else f'{len(critical)} konu çözülmeli')
        notes = []
        if not cycle['demand_met']:
            notes.append('Pompa bazı fazlarda ihtiyacı karşılamıyor; sonuçlar senaryodur.')
        if r.thermal.get('status') == 'scenario_only':
            notes.append('Isı sonuçları gerçekleşmiş performans değil, varsayımsal senaryodur.')
        if p.pump.leakage_flow == 0:
            notes.append('Kaçak sıfır: bekleme ideal kabul edildi.')
        notes.append('Uygunluk üretici veya ürün onayı değildir.')
        self.status_note.setText('\n'.join(notes))
        first = next((issue for issue in sorted(r.issues,key=lambda i: ('critical','warning','info').index(i.severity)) if issue.field),None)
        self.problem_field = first.field if first else None
        self.fix_button.setVisible(first is not None)
        self.status_note.setProperty('role', 'warning' if not cycle['demand_met'] or not r.feasible else 'muted')
        self.status_note.style().unpolish(self.status_note); self.status_note.style().polish(self.status_note)
        rows = result_rows(p, r)
        lookup = {label_: (value, unit) for label_, value, unit, _ in rows}
        short = {'Maksimum gerekli basınç':'Basınç ihtiyacı','Maksimum gerekli debi':'Debi ihtiyacı',
                 'Emniyet valfi ayarı':'Valf ayarı','Seçilen motor':'Motor seçimi',
                 'Nominal deplasman adayı':'Pompa hacmi','Gerekli soğutucu':'Soğutucu ihtiyacı'}
        summary = [(short.get(name,name), f'{fmt(lookup[name][0], 2)} {lookup[name][1]}') for name in
                   ('Maksimum gerekli basınç', 'Maksimum gerekli debi', 'Emniyet valfi ayarı', 'Tepe mil gücü',
                    'Seçilen motor', 'Nominal deplasman adayı', 'Çevrim süresi', 'Gerekli soğutucu') if name in lookup]
        summary.insert(0, ('Pompa yeterli mi?', 'evet' if cycle['demand_met'] else 'HAYIR'))
        self._rows(self.summary_table, summary)
        self._rows(self.rows_table, [(label_, value, unit) for label_, value, unit, _ in rows],
                   tips=[formula for *_, formula in rows])
        self.issue_list.clear()
        for issue in sorted(r.issues, key=lambda i: ('critical', 'warning', 'info').index(i.severity)):
            title, token = SEVERITY.get(issue.severity, ('Uyarı', 'warning'))
            action = ACTIONS.get(issue.code,'')
            item = QListWidgetItem(f'{title} · {issue.message}' + (f'\n→ {action}' if action else '')); item.setData(Qt.UserRole, issue.field)
            item.setForeground(QColor(COLORS[self.context.appearance][token if token != 'muted' else 'muted']))
            item.setToolTip(f'{issue.code}' + (f' · {issue.field}' if issue.field else ''))
            self.issue_list.addItem(item)
        self.issue_list.reflow()
        phase_rows = []
        for f in cycle['phases']:
            phase_rows.append((f.name, f'{fmt(f.start_position * 1000, 1)} → {fmt(f.end_position * 1000, 1)}', f.duration,
                               convert(f.pressure, 'Pa', 'bar'), convert(f.flow, 'm3/s', 'L/min'),
                               convert(f.supply_pressure, 'Pa', 'bar'), f.shaft_power / 1000, 'evet' if f.feasible else 'HAYIR'))
        self._rows(self.phase_results, phase_rows)
        durations = [f.duration for f in cycle['phases']]
        self.charts['pressure'].set_values(durations, [convert(f.pressure, 'Pa', 'bar') for f in cycle['phases']])
        self.charts['flow'].set_values(durations, [convert(f.flow, 'm3/s', 'L/min') for f in cycle['phases']])
        self.charts['shaft_power'].set_values(durations, [f.shaft_power / 1000 for f in cycle['phases']])
        t = r.thermal
        self._rows(self.thermal_table, [
            ('Durum', 'yalnız senaryo' if t.get('status') == 'scenario_only' else 'hesaplandı'),
            ('Gerekli kullanılabilir hacim · L', t['required_volume'] * 1000), ('Mevcut kullanılabilir hacim · L', t['usable_volume'] * 1000),
            ('Isı atan yüzey · m²', t['exposed_area']), ('Ortalama ısı yükü · kW', t['average_loss'] / 1000),
            ('Soğutucusuz denge · °C', convert(t['equilibrium_temperature'], 'K', '°C')), ('Gerekli soğutucu · kW', t['cooler_power'] / 1000)])
        a = r.accumulator
        self._rows(self.accumulator_table, [('Durum', 'Kullanılmıyor — isteğe bağlı hesap kapalı')] if a.get('status') == 'disabled' else [
            ('Gerekli gaz hacmi · L', a['required_volume'] * 1000),
            ('Nominal hacim adayı · L', None if a['nominal_volume'] is None else a['nominal_volume'] * 1000),
            ('Ön dolum · bar (gösterge)', convert(a['precharge_absolute']-p.accumulator.atmospheric_pressure,'Pa','bar')),
            ('En düşük basınç · bar (gösterge)', convert(a['minimum_absolute']-p.accumulator.atmospheric_pressure,'Pa','bar')),
            ('En yüksek basınç · bar (gösterge)', convert(a['maximum_absolute']-p.accumulator.atmospheric_pressure,'Pa','bar'))])
        self.assumptions.setText('\n'.join('• ' + text for text in r.assumptions))
        self.refresh_actions()
        self.set_status('Hesap güncel · ' + ('kritik kontrol yok' if r.feasible else 'kritik uyarılar var'),
                        tone='success' if r.feasible else 'warning')

    def update_cylinder_check(self):
        if self.loading or self.project is None:
            return
        rows = self.cylinder_table.selectionModel().selectedRows() if self.cylinder_table.selectionModel() else []
        index = rows[0].row() if rows else 0
        if not self.project.cylinders:
            return
        cylinder = self.project.cylinders[min(index, len(self.project.cylinders) - 1)]
        try:
            values = {name: self.read_value('point.' + name) for name in self.point}
            if values['speed'] is None:
                raise InputError('point.speed', 'Hız gerekli.')
            check = calculate_cylinder(cylinder, M.CylinderOperatingPoint(**values, duration=None))
        except InputError as error:
            field = error.field if error.field.startswith('point.') else 'point.' + error.field
            if field in self.fields:
                self._flag(self.fields[field][0], str(error))
            self.cylinder_result.setRowCount(0); return
        b = check['buckling']
        self._rows(self.cylinder_result, [
            (f'Silindir', cylinder.id), ('Piston alanı · cm²', check['piston_area'] * 1e4), ('Halka alanı · cm²', check['annular_area'] * 1e4),
            ('Alan oranı φ', check['area_ratio']), ('Bu basınçta kuvvet · kN', check['force'] / 1000),
            ('Gerekli basınç · bar', convert(check['required_pressure'], 'Pa', 'bar')),
            ('Debi · L/min', convert(check['flow'], 'm3/s', 'L/min')), ('Süre · s', check['duration']),
            ('Gerekli piston Ø (teorik) · mm', None if check['theoretical_bore'] is None else check['theoretical_bore'] * 1000),
            ('Nominal piston Ø · mm', None if check['nominal_bore'] is None else check['nominal_bore'] * 1000),
            ('Euler kritik kuvvet · kN', b['critical_force'] / 1000),
            ('Burkulma emniyeti', b['safety']), ('Euler kontrolü (≥ 3,5)', 'geçti' if b['passed'] else 'KALDI')])

    # ----------------------------------------------------------------- table commands
    def _commit(self):
        """Apply the current table text to the project when it is valid (adding rows keeps edits)."""
        try:
            self.project = self.build_project()
            return True
        except InputError as error:
            self.show_invalid(error)
            return False

    def add_cylinder(self):
        if not self._commit(): return
        ids = {c.id for c in self.project.cylinders}
        n = len(ids) + 1
        while f'C{n}' in ids:
            n += 1
        self.project = replace(self.project, cylinders=self.project.cylinders + (M.Cylinder(id=f'C{n}'),))
        self.populate(); self.recalculate()

    def remove_cylinder(self):
        rows = self.cylinder_table.selectionModel().selectedRows()
        if not rows or len(self.project.cylinders) <= 1:
            self.set_status('En az bir silindir gerekli.', True); return
        if not self._commit(): return
        index = rows[0].row()
        cylinders = tuple(c for i, c in enumerate(self.project.cylinders) if i != index)
        self.project = replace(self.project, cylinders=cylinders)
        self.populate(); self.recalculate()

    def _phase_index(self):
        rows = self.phase_table.selectionModel().selectedRows()
        return rows[0].row() if rows else len(self.project.phases) - 1

    def add_phase(self, copy=False):
        if not self._commit(): return
        index = self._phase_index(); phases = list(self.project.phases)
        phase = phases[index] if copy and phases else M.Phase(cylinder_id=self.project.cylinders[0].id)
        phases.insert(index + 1, replace(phase, name=phase.name + (' (kopya)' if copy else '')) if copy else phase)
        self.project = replace(self.project, phases=tuple(phases)); self.populate(); self.recalculate()
        self.phase_table.selectRow(index + 1)

    def remove_phase(self):
        if len(self.project.phases) <= 1:
            self.set_status('En az bir faz gerekli.', True); return
        if not self._commit(): return
        index = self._phase_index()
        self.project = replace(self.project, phases=tuple(p for i, p in enumerate(self.project.phases) if i != index))
        self.populate(); self.recalculate()

    def move_phase(self, step):
        if not self._commit(): return
        index = self._phase_index(); target = index + step
        phases = list(self.project.phases)
        if not 0 <= target < len(phases):
            return
        phases[index], phases[target] = phases[target], phases[index]
        self.project = replace(self.project, phases=tuple(phases)); self.populate(); self.recalculate()
        self.phase_table.selectRow(target)

    # ----------------------------------------------------------------- helper actions (explicit, never automatic)
    def apply_pump_defaults(self):
        pump = pump_for_type(self.fields['pump.kind'][0].currentData())
        for name in ('volumetric_efficiency', 'mechanical_efficiency', 'max_pressure'):
            self.set_widget(f'pump.{name}', getattr(pump, name))
        self.changed(); self.set_status('Tipik pompa değerleri yazıldı (örnek; üretici verisi değildir).')

    def apply_recommended_velocity(self):
        role = self.fields['pipe.role'][0].currentData()
        pressure = self.result.cycle['max_pressure'] if self.result is not None else 0.
        low, high = recommended_velocity(role, pressure)
        self.set_widget('pipe.min_velocity', low); self.set_widget('pipe.max_velocity', high)
        self.set_widget('pipe.target_velocity', (low + high) / 2)
        self.changed(); self.set_status(f'Önerilen hız aralığı yazıldı: {fmt(low)}–{fmt(high)} m/s (başlangıç önerisi).')

    def apply_oil_grade(self):
        grade = self.fields['oil.grade'][0].currentData()
        if grade not in OIL_EXAMPLES:
            self.set_status('Kullanıcı yağında ν40/ν100 değerlerini veri sayfasından girin.', True); return
        oil = oil_for_grade(grade)
        for name in ('nu40', 'nu100', 'source'):
            self.set_widget(f'oil.{name}', getattr(oil, name))
        self.changed()

    def focus_issue(self, item):
        self.navigate_to_field(item.data(Qt.UserRole) or '')

    def focus_first_problem(self):
        self.navigate_to_field(self.problem_field or '')

    def navigate_to_field(self, field):
        """Uyarıdaki ayarı açar; geçerli girdiyi kırmızı hata olarak işaretlemez."""
        self.open_detailed()
        if self.input_stack.currentIndex()!=1:return
        field = field.removeprefix('project.') if field not in self.fields else field
        parts = field.split('.')
        tab = {'cylinders':0,'phases':1,'pump':2,'project':2,'pipe':3,'oil':3,'thermal':4,'accumulator':5,'point':0}.get(parts[0])
        key = field if field in self.fields else next((k for k in self.fields if k == 'project.'+field),None)
        if key:
            section,name = key.split('.',1)
            tab = {'pump':2,'project':2,'pipe':3,'oil':3,'thermal':4,'accumulator':5,'point':0}[section]
            if name in ADVANCED.get(section,set()): self.advanced_sections[section].set_expanded(True)
            if section == 'point': self.cylinder_check_section.set_expanded(True)
            self.fields[key][0].setFocus()
        elif parts[0] in ('cylinders','phases') and len(parts)>1 and parts[1].isdigit():
            table = self.cylinder_table if parts[0] == 'cylinders' else self.phase_table
            row = min(int(parts[1]),table.rowCount()-1)
            if parts[0] == 'cylinders': self.cylinder_advanced.setChecked(True)
            if row >= 0: table.selectRow(row); table.setFocus()
        if tab is not None:
            self.tabs.setCurrentIndex(tab)
            if key:
                widget = self.fields[key][0]
                container = self.tabs.widget(tab)
                if hasattr(container,'ensureWidgetVisible'): container.ensureWidgetVisible(widget)
                widget.setFocus()

    # ----------------------------------------------------------------- files
    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Hidrolik proje aç', '', 'Hidrolik ünite (*.gwhyd)')
        if path:
            self.load_path(path)

    def load_example(self):
        self.load_path(Path(__file__).resolve().parents[2] / 'examples' / 'ornek_pres_unitesi.gwhyd')

    def load_path(self, path):
        try:
            project = serialization.load(path)
        except (OSError, ValueError) as error:
            self.set_status(f'Proje açılamadı: {error}', True); return
        self.project, self.path = project, Path(path)
        self.simple.previous_cycle=None
        if not simple_supported(project):
            self.view_mode.blockSignals(True);self.view_mode.setCurrentIndex(1);self.view_mode.blockSignals(False)
            self.input_stack.setCurrentIndex(1);self.apply_view_layout()
        self.populate(); self.recalculate()
        self.set_status(f'Proje açıldı: {Path(path).name}')

    def save_project(self):
        if self.result is None:
            return
        name = str(self.path or (self.project.name + '.gwhyd'))
        path, _ = QFileDialog.getSaveFileName(self, 'Hidrolik projeyi kaydet', name, 'Hidrolik ünite (*.gwhyd)')
        if not path:
            return
        if not path.lower().endswith('.gwhyd'):
            path += '.gwhyd'
        try:
            serialization.save(self.project, path)
        except (OSError, ValueError) as error:
            self.set_status(f'Kaydedilemedi: {error}', True); return
        self.path = Path(path); self.set_status(f'Proje kaydedildi: {Path(path).name}')

    def export(self, kind):
        if self.result is None or not self.can_start():
            return
        suffix, title = ('xlsx', 'Excel (*.xlsx)') if kind == 'excel' else ('json', 'JSON (*.json)')
        path, _ = QFileDialog.getSaveFileName(self, 'Raporu kaydet', f'{self.project.name}.{suffix}', title)
        if not path:
            return
        from .report.export import export_excel, export_json
        writer = export_excel if kind == 'excel' else export_json
        project, result = self.project, self.result

        def run(events, stop):
            writer(project, result, path, stop=stop)
            events.put(('hydraulic_report', path))
        self.set_status('Rapor hazırlanıyor…'); self.jobs.start(self, run)

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'hydraulic_report':
                self.set_status(f'Rapor kaydedildi: {Path(value).name}')
        super().handle_events(events)

    def export_pdf(self):
        if self.result is None or self.pdf_job is not None or self.busy:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'PDF raporu kaydet', f'{self.project.name}.pdf', 'PDF (*.pdf)')
        if not path:
            return
        from .report.export import create_pdf_job
        job = create_pdf_job(self.project, self.result, path, parent=self)
        job.progress.connect(lambda page, total: self.report_status.setText(f'PDF: sayfa {page}/{total}'))
        job.progress.connect(lambda page,total:self.simple.status.setText(f'PDF raporu hazırlanıyor: {page}/{total} sayfa'))
        job.finished.connect(self.pdf_finished); job.failed.connect(self.pdf_failed)
        self.pdf_job = job; self.cancel_pdf_button.show(); self.refresh_actions()
        self.report_status.setText('PDF hazırlanıyor…'); job.start()

    def _pdf_done(self):
        job, self.pdf_job = self.pdf_job, None
        if job is not None:
            job.deleteLater()
        self.cancel_pdf_button.hide(); self.refresh_actions()

    def pdf_finished(self, path):
        self._pdf_done(); self.report_status.setText(''); self.set_status(f'PDF raporu kaydedildi: {Path(path).name}')

    def pdf_failed(self, message):
        self._pdf_done(); self.report_status.setText(''); self.set_status(message, True)

    def cancel_pdf(self):
        if self.pdf_job is not None:
            self.pdf_job.cancel()

    def set_busy(self, busy):
        super().set_busy(busy)
        if hasattr(self, 'excel_button'):
            self.refresh_actions()

    def theme_changed(self):
        for chart in getattr(self, 'charts', {}).values():
            chart.appearance = self.context.appearance; chart.update()
        if self.result is not None:
            self.show_result()
