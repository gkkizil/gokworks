"""Sac Açınımı page: shape → dimensions → preview → development → output.

Geometry, validation, development and file output belong to the unfolding
service. This page only builds requests from the service schema, shows the
service's answers and keeps stale results from being mistaken for current ones.
"""

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, QPointF, QEvent
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QStackedWidget, QTextBrowser)

from gui_qt.components import AdaptiveRow, BasePage, Disclosure, button, label, scroll, section_header
from gui_qt.theme import COLORS

from .drawing import LAYERS, DevelopmentView, ReferenceSketch, SchemaSketch
from .service import DUCT_LAP_TITLES, LAP_TITLES, search_text
from .numbers import METHOD_TITLES, REFERENCE_TITLES, fmt, parse, to_display, to_mm
from .service import resolve_service

DEBOUNCE_MS = 350
STATES = {  # key: (text, colour token)
    'missing': ('Eksik veya hatalı girdi', 'warning'),
    'invalid_stale': ('Eksik veya hatalı girdi — gösterilen çizim eski', 'warning'), 'running': ('Hesaplanıyor…', 'muted'), 'ok': ('Geçerli sonuç', 'success'),
    'warning': ('Uyarılı sonuç', 'warning'), 'example': ('ÖRNEK VERİ — girdilerden hesaplanmadı', 'warning'),
    'error': ('Hata', 'danger'), 'cancelled': ('İptal edildi', 'muted'),
    'stale': ('Ölçüler değişti — yeniden hesaplanmalı', 'warning'), 'idle': ('Hesap bekleniyor', 'muted'),
}
EXPORTS = (('dxf', 'DXF'), ('dwg','DWG'), ('pdf', 'PDF'), ('step', 'STEP (katı model)'), ('zip', 'Toplu ZIP'))
EXPORT_FILTERS = {'dxf': 'DXF (*.dxf)', 'dwg':'DWG (*.dwg)', 'pdf': 'PDF (*.pdf)', 'step': 'STEP (*.step *.stp)', 'zip': 'ZIP (*.zip)'}
PRODUCTION_FIELDS = ('thickness', 'joint', 'seam_angle', 'split_count', 'price')
JOINT_TITLES = {'butt': 'Alın alına', 'lap': 'Bindirmeli'}


def _table(headers, stretch=None):
    """Read-only grid with the application's shared, draggable column behaviour."""
    from gui_qt.components import configure_view, fit_columns
    view = QTableWidget(0, len(headers)); view.setHorizontalHeaderLabels(headers)
    view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    configure_view(view); view.setSortingEnabled(False)       # row order follows the service parts
    fit_columns(view, elastic=stretch if stretch is not None else 0, minimum=120)
    return view


def _fill(view, rows, align_right=()):
    view.setRowCount(0)
    for r, row in enumerate(rows):
        view.insertRow(r)
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value)); item.setToolTip(str(value))
            if c in align_right:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            view.setItem(r, c, item)


def preview_icon(polylines, colour, size=64, fill=None):
    """Shape thumbnail from the service preview lines (0–1 box); a dashed frame when none is given."""
    pixmap = QPixmap(size * 2, size * 2); pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
    m, w = size * .16, size * .68
    to = lambda p: QPointF(m + p[0] * w, size - m - p[1] * w)
    if not polylines:
        painter.setPen(QPen(QColor(colour), 1.2, Qt.DashLine)); painter.drawRoundedRect(m, m, w, w, 4, 4)
    else:
        if fill:
            from PySide6.QtGui import QPolygonF
            tint = QColor(fill); tint.setAlpha(48); painter.setBrush(tint); painter.setPen(Qt.NoPen)
            closed = [line for line in polylines if len(line) > 3 and line[0] == line[-1]]
            for line in closed:
                painter.drawPolygon(QPolygonF([to(p) for p in line]))
        painter.setPen(QPen(QColor(colour), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); painter.setBrush(Qt.NoBrush)
        for line in polylines:
            for a, b in zip(line, line[1:]):
                painter.drawLine(to(a), to(b))
    painter.end()
    return QIcon(pixmap)


class MetricStrip(QWidget):
    """Compact key figures in one row: small caption over a tabular value (no giant cards)."""

    def __init__(self, keys, parent=None):
        super().__init__(parent)
        box = QHBoxLayout(self); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(18)
        self.values = {}
        for key, title in keys:
            cell = QWidget(); column = QVBoxLayout(cell); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(0)
            caption = label(title, 'muted', wrap=False); value = label('—', wrap=False)
            value.setStyleSheet('font-size: 15px; font-weight: 600;')
            column.addWidget(caption); column.addWidget(value); box.addWidget(cell)
            self.values[key] = value
        box.addStretch(1)

    def set(self, key, text):
        self.values[key].setText(text)


class UnfoldPage(BasePage):
    # Closing the window stops a running preview calculation without asking; file exports still ask.
    quiet_cancel_on_close = True

    def __init__(self, context, service=None):
        super().__init__(context, 'Sac Açınımı', 'Şekil → ölçü → önizleme → açınım → çıktı. Hesap ve dosyalar açınım servisinden gelir.')
        self.service = service or resolve_service()
        self.shapes = self.service.list_shapes()
        from modules.weight.materials import MATERIALS
        self.materials = [dict(id='', title='Malzeme seçilmedi', density_kg_m3=None)] + \
            [dict(id=name, title=name, density_kg_m3=float(density)) for name, density in MATERIALS.items()]
        self.schema = None; self.shape_id = self.variant_id = None
        self.fields = {}; self.values = {}; self.errors = {}; self.applied_text = {}
        self.development_options = {}; self.loaded_material = None
        self.price_unit = 'kg'; self.price_currency = 'TL'
        self.revision = 0; self.pending_request = None; self.running_request = None; self.queued = False
        self.result = None; self.result_revision = None; self.result_request = None; self.state = 'idle'
        self.project_parts = []; self.project_metadata = {}; self.dirty = False
        self.open_button = self.action('Proje aç…', self.open_project)
        self.save_button = self.action('Projeyi kaydet…', self.save_project)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.calc_timer = QTimer(self); self.calc_timer.setSingleShot(True); self.calc_timer.setInterval(DEBOUNCE_MS)
        self.calc_timer.timeout.connect(self.calculate)

        self.banner = label(getattr(self.service, 'notice', ''), 'muted')
        self.banner.setObjectName('unfoldFixtureBanner')
        toolbar = QHBoxLayout(); toolbar.setSpacing(6)
        self.project_name = QLineEdit('Yeni proje'); self.project_name.setAccessibleName('Proje adı'); self.project_name.setMaximumWidth(260)
        self.project_name.textEdited.connect(lambda *_: self.mark_dirty())
        self.layout_mode = QComboBox(); self.layout_mode.addItem('Görünümler yan yana', 'side'); self.layout_mode.addItem('Görünümler sekmeli', 'tabs')
        self.layout_mode.currentIndexChanged.connect(self.apply_view_layout)
        toolbar.addWidget(label('Proje', 'muted')); toolbar.addWidget(self.project_name); toolbar.addStretch(1)
        toolbar.addWidget(self.layout_mode)
        self.layout.addWidget(self.banner); self.layout.addLayout(toolbar)
        self.banner.setVisible(self.service.is_fixture)     # only after it has a parent (else it becomes a window)

        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.build_shapes()); self.splitter.addWidget(self.build_parameters())
        self.splitter.addWidget(self.build_workspace())
        self.splitter.setStretchFactor(2, 1); self.splitter.setSizes([230, 330, 900])
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()
        self.controls += [self.shape_tree, self.variant]
        first = next((s for s in self.shapes if s['status'] == 'implemented'), None)
        if first:
            self.choose_shape(first['shape_id'], first['variants'][0]['variant_id'])
        self.refresh_actions()

    # ==================================================================================
    # Left: shape browser
    # ==================================================================================
    def build_shapes(self):
        self.shape_search = QLineEdit(); self.shape_search.setPlaceholderText('Şekil ara: kare yuvarlak, redüksiyon, kurtağzı…')
        self.shape_search.setClearButtonEnabled(True); self.shape_search.textChanged.connect(self.fill_shapes)
        self.category = None
        self.chips = QWidget(); chip_box = QHBoxLayout(self.chips); chip_box.setContentsMargins(0, 0, 0, 0); chip_box.setSpacing(4)
        self.chip_group = QButtonGroup(self); self.chip_group.setExclusive(True)
        self.category_box = QComboBox(); self.category_box.setAccessibleName('Kategori')
        self.category_box.addItem('Tüm kategoriler', None)
        for category in dict.fromkeys(s['category'] for s in self.shapes):
            self.category_box.addItem(category, category)
        self.category_box.currentIndexChanged.connect(lambda *_: self.fill_shapes())
        self.shape_tree = QListWidget(); self.shape_tree.setViewMode(QListView.IconMode); self.shape_tree.setIconSize(QSize(64, 64))
        self.shape_tree.setGridSize(QSize(116, 148)); self.shape_tree.setTextElideMode(Qt.ElideNone); self.shape_tree.setResizeMode(QListView.Adjust)
        self.shape_tree.setMovement(QListView.Static); self.shape_tree.setWordWrap(True); self.shape_tree.setSpacing(4)
        self.shape_tree.setUniformItemSizes(True)
        self.shape_tree.setAccessibleName('Şekiller'); self.shape_tree.itemSelectionChanged.connect(self.shape_selected)
        self.shape_tree.itemClicked.connect(lambda *_:self.shape_selected())
        self.shape_tree.itemActivated.connect(lambda *_:self.shape_selected())
        self.variant = QComboBox(); self.variant.setAccessibleName('Varyant'); self.variant.currentIndexChanged.connect(self.variant_changed)
        self.recent = QComboBox(); self.recent.setAccessibleName('Son kullanılanlar'); self.recent.activated.connect(self.recent_chosen)
        host = QWidget(); box = QVBoxLayout(host); box.setContentsMargins(0, 0, 4, 0); box.setSpacing(6)
        box.addWidget(label('1 · Şekil', 'section')); box.addWidget(self.shape_search); box.addWidget(self.category_box)
        box.addWidget(self.shape_tree, 1)
        box.addWidget(label('Varyant', 'muted')); box.addWidget(self.variant)
        box.addWidget(label('Son kullanılanlar', 'muted')); box.addWidget(self.recent)
        host.setMinimumWidth(250)
        self.fill_shapes(); self.fill_recent()
        return host

    def visible_shapes(self):
        needle = search_text(self.shape_search.text().strip())
        category = self.category_box.currentData() if hasattr(self, 'category_box') else None
        for shape in self.shapes:
            text = search_text(' '.join([shape['title'], shape['category'], *shape.get('keywords', ())]))
            if (not needle or needle in text) and (category is None or shape['category'] == category):
                yield shape

    def fill_shapes(self, *args):
        colors = COLORS[self.context.appearance]
        self.shape_tree.blockSignals(True); self.shape_tree.clear()
        # Implemented shapes first; planned ones follow, visibly marked and not selectable.
        for shape in sorted(self.visible_shapes(), key=lambda s: s['status'] != 'implemented'):
            planned = shape['status'] != 'implemented'
            count=len(shape['variants'])
            suffix='\nPlanlanan' if planned else f'\n{count} varyant' if count>1 else ''
            item = QListWidgetItem(shape['title'] + suffix)
            item.setSizeHint(self.shape_tree.gridSize())
            item.setData(Qt.UserRole, shape['shape_id']); item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setIcon(preview_icon(shape.get('preview'), colors['muted' if planned else 'accent'], fill=None if planned else colors['accent']))
            item.setToolTip(f'{shape["title"]}\n{shape["category"]} · ' + ('Henüz uygulanmadı; seçilemez.' if planned else ', '.join(shape.get('keywords', ()))))
            if planned:
                item.setFlags(item.flags() & ~(Qt.ItemIsSelectable | Qt.ItemIsEnabled))
            self.shape_tree.addItem(item)
            if shape['shape_id'] == self.shape_id:
                item.setSelected(True)
        self.shape_tree.blockSignals(False)

    def shape_by_id(self, shape_id):
        return next(s for s in self.shapes if s['shape_id'] == shape_id)

    def shape_selected(self):
        items = self.shape_tree.selectedItems()
        if not items or items[0].data(Qt.UserRole) is None:
            return
        shape = self.shape_by_id(items[0].data(Qt.UserRole))
        variants=[v for v in shape['variants'] if v['status']=='implemented']
        needle=search_text(self.shape_search.text().strip())
        match=next((v for v in variants if needle and any(needle in search_text(text) for text in
                   (v['variant_id'],v['title'],v.get('search_name',''),f'{shape["title"]}, {v["title"]}'))),None)
        variant=(match or next(iter(variants),{})).get('variant_id')
        if variant and (shape['shape_id'] != self.shape_id or match and variant != self.variant_id):
            self.choose_shape(shape['shape_id'], variant)

    def choose_shape(self, shape_id, variant_id, keep=True):
        shape = self.shape_by_id(shape_id)
        self.variant.blockSignals(True); self.variant.clear()
        for v in shape['variants']:
            planned = v['status'] != 'implemented'
            self.variant.addItem(v['title'] + (' · Planlanan' if planned else ''), v['variant_id'])
            if planned:
                self.variant.model().item(self.variant.count() - 1).setEnabled(False)
        self.variant.setCurrentIndex(max(self.variant.findData(variant_id), 0)); self.variant.blockSignals(False)
        same_shape = shape_id == self.shape_id
        self.shape_id = shape_id
        self.load_schema(variant_id, keep=keep and same_shape)
        self.remember_recent(shape_id, variant_id)
        self.fill_shapes()

    def variant_changed(self, *args):
        variant = self.variant.currentData()
        if variant and variant != self.variant_id:
            self.load_schema(variant, keep=True)
            self.remember_recent(self.shape_id, variant)

    def fill_recent(self):
        recent = self.settings.get('unfold_recent', []) or []
        self.recent.blockSignals(True); self.recent.clear(); self.recent.addItem('—', None)
        titles = {(s['shape_id'], v['variant_id']): f'{s["title"]} · {v["title"]}' for s in self.shapes for v in s['variants']}
        for entry in recent if isinstance(recent, list) else []:
            key = tuple(entry) if isinstance(entry, list) and len(entry) == 2 else None
            if key in titles:
                self.recent.addItem(titles[key], list(key))
        self.recent.blockSignals(False)

    def remember_recent(self, shape_id, variant_id):
        recent = [e for e in (self.settings.get('unfold_recent', []) or []) if isinstance(e, list) and e != [shape_id, variant_id]]
        self.settings.set('unfold_recent', ([[shape_id, variant_id]] + recent)[:6]); self.fill_recent()

    def recent_chosen(self, index):
        data = self.recent.itemData(index)
        if data:
            self.choose_shape(data[0], data[1])

    # ==================================================================================
    # Middle: parameters from the service schema
    # ==================================================================================
    def build_parameters(self):
        self.sketch = SchemaSketch(); self.sketch.annotationClicked.connect(self.focus_field)
        self.sketch.inlineEdited.connect(self.inline_edited); self.sketch.inlineCommitted.connect(lambda *_: self.calculate_now())
        # One form per shape/variant, built once and kept: switching shows another form instead of
        # deleting widgets (focus, typed text and accessibility objects stay valid).
        self.schema_forms = {}; self.advanced = None
        self.param_host = QWidget(); self.param_box = QVBoxLayout(self.param_host)
        self.param_box.setContentsMargins(0, 0, 0, 0); self.param_box.setSpacing(0)
        prod = QWidget(); self.prod_form = QFormLayout(prod); self.prod_form.setContentsMargins(0, 0, 0, 0)
        self.prod_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.unit = QComboBox(); self.unit.addItem('mm', 'mm'); self.unit.addItem('inch', 'inch'); self.unit.setAccessibleName('Giriş birimi')
        self.unit.currentIndexChanged.connect(self.unit_changed); self._unit = 'mm'
        self.thickness = self._field('thickness', 'Sac kalınlığı', 't', 'length', 2.)
        self.reference = QComboBox(); self.reference.setAccessibleName('Ölçü yüzeyi')
        self.reference.currentIndexChanged.connect(self.reference_changed)
        self.reference_sketch = ReferenceSketch()
        self.material = QComboBox(); self.material.setAccessibleName('Malzeme')
        for m in self.materials:
            self.material.addItem(self.material_caption(m), m['id'])
        self.material.setCurrentIndex(max(self.material.findData('Demir / Çelik'), 0))
        self.material.currentIndexChanged.connect(self.material_changed)
        self.joint_kind = QComboBox(); self.joint_kind.setAccessibleName('Birleşim türü')
        self.joint_kind.currentIndexChanged.connect(self.joint_changed)
        self.seam_angle = self._field('seam_angle', 'Dikiş başlangıç açısı', 'θ', 'angle', 0.)
        self.split_count = self._field('split_count', 'Çevresel bölme', 'n', 'count', 1)
        self.joint = self._field('joint', 'Bindirme payı', 'b', 'length', 0.)
        self.price = self._field('price', 'Fiyat', '₺/kg', 'price', None)
        for title, widget in (('Giriş birimi', self.unit), ('Ölçü yüzeyi', self.reference), ('', self.reference_sketch),
                              ('Malzeme', self.material), ('Birleşim', self.joint_kind)):
            self.prod_form.addRow(title, widget)
        for key in ('thickness', 'joint', 'seam_angle', 'split_count', 'price'):
            self._add_field_row(self.prod_form, key)
        self.calculate_button = button('Hesapla', self.calculate_now, primary=True)
        from .forming import FormingPanel
        self.forming=FormingPanel();self.forming.changed.connect(self.input_changed)
        self.calculate_button.setToolTip('Değişiklikler kısa bir bekleme sonrası kendiliğinden hesaplanır; Enter hemen hesaplar.')
        host = QWidget(); box = QVBoxLayout(host); box.setContentsMargins(4, 0, 4, 0); box.setSpacing(6)
        self.shape_title = label('', 'section')
        box.addWidget(self.shape_title); box.addWidget(self.sketch); box.addWidget(label('2 · Ölçüler', 'section'))
        box.addWidget(self.param_host)
        box.addWidget(label('3 · Malzeme ve üretim', 'section')); box.addWidget(prod)
        box.addWidget(Disclosure('Açınım ve üretim telafisi',self.forming));box.addWidget(self.calculate_button)
        self.validation_note = label('', 'muted'); box.addWidget(self.validation_note); box.addStretch(1)
        self.sketch.setMinimumHeight(230)
        area = scroll(host); area.setMinimumWidth(300); area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls.append(self.calculate_button)
        return area

    def _field(self, key, title, symbol, kind, default):
        edit = QLineEdit(); edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter); edit.setAccessibleName(title)
        error = label('', 'muted'); error.setVisible(False); error.setObjectName('fieldError')
        self.fields[key] = dict(edit=edit, error=error, title=title, symbol=symbol, kind=kind, label=None)
        self.values[key] = default
        edit.setText(self.display_value(key, default)); self.applied_text[key] = edit.text()
        edit.textEdited.connect(lambda *_, k=key: self.field_edited(k))
        edit.returnPressed.connect(self.calculate_now)
        edit.installEventFilter(self)
        return edit

    def _add_field_row(self, form, key, choices=None, hint=''):
        """Number field; with discrete ``choices`` [(value, title)] a list replaces the text box (same value path)."""
        info = self.fields[key]
        caption = label(self.caption(key), wrap=True); info['label'] = caption
        column = QWidget(); column_box = QVBoxLayout(column); column_box.setContentsMargins(0, 0, 0, 0); column_box.setSpacing(1)
        column_box.addWidget(info['edit'])
        if choices:
            combo = QComboBox(); combo.setAccessibleName(info['title']); info['combo'] = combo; info['choices'] = True
            for value, title in choices:
                combo.addItem(str(title), value)
            info['edit'].hide(); column_box.addWidget(combo); caption.setText(self.caption(key))
            def chosen(*_, k=key, box=combo):
                if box.currentData() is not None and self.fields.get(k) is info:
                    info['edit'].setText(str(box.currentData())); self.field_edited(k)
            def typed(text, box=combo):
                index = box.findData(int(text)) if text.strip().lstrip('-').isdigit() else -1
                box.blockSignals(True); box.setCurrentIndex(index); box.blockSignals(False)
            combo.currentIndexChanged.connect(chosen); info['edit'].textChanged.connect(typed); typed(info['edit'].text())
        if hint:
            caption.setToolTip(hint); info['edit'].setToolTip(hint)
        column_box.addWidget(info['error'])
        form.addRow(caption, column)

    def caption(self, key):
        info = self.fields[key]
        unit = '' if info.get('choices') else {'length': self._unit, 'angle': '°', 'count': 'adet', 'price': ''}.get(info['kind'], '')
        return f'{info["title"]} {info["symbol"]}' + (f' · {unit}' if unit else '')

    def display_value(self, key, value):
        info = self.fields[key]
        if value is None:
            return ''
        shown = to_display(value, self._unit) if info['kind'] == 'length' else value
        return fmt(float(shown), 6) if info['kind'] != 'count' else str(int(value))

    def load_schema(self, variant_id, keep=True):
        try:
            schema = self.service.get_schema(self.shape_id, variant_id)
        except (ValueError, KeyError) as error:
            self.set_status(f'Şema alınamadı: {error}', True); return
        previous = self.schema; old_values = {k: v for k, v in self.values.items()}
        old_key = (self.schema['shape_id'], self.schema['variant_id']) if previous else None
        if old_key in self.schema_forms:                   # remember this form's values for a later return
            self.schema_forms[old_key]['values'] = {k: self.values.get(k) for k in self.schema_forms[old_key]['fields']}
            self.schema_forms[old_key]['host'].hide()
        self.schema, self.variant_id = schema, variant_id
        for key in [k for k in self.fields if k not in PRODUCTION_FIELDS]:
            self.fields.pop(key); self.values.pop(key, None); self.errors.pop(key, None); self.applied_text.pop(key, None)
        key = (self.shape_id, variant_id)
        entry = self.schema_forms.get(key)
        if entry is None:
            host = QWidget(); column = QVBoxLayout(host); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(4)
            common = QWidget(); common_form = QFormLayout(common); common_form.setContentsMargins(0, 0, 0, 0)
            common_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            advanced_host = QWidget(); advanced_form = QFormLayout(advanced_host); advanced_form.setContentsMargins(0, 0, 0, 0)
            advanced = Disclosure('Gelişmiş şekil seçenekleri', advanced_host)
            labels = (schema['options'].get('model_options') or {}).get('parameter_options') or {}
            for p in schema['parameters']:
                self._field(p['id'], p['label'], p['symbol'], p['kind'], p['default'])
                choices = [tuple(c) for c in labels.get(p['id'], ())] or [(c, c) for c in p.get('choices') or ()]
                self._add_field_row(common_form if p.get('group') == 'common' else advanced_form, p['id'], choices=choices)
            column.addWidget(common); column.addWidget(advanced)
            model = self.build_model_options(schema, column) if schema.get('source_id') else None
            self.param_box.addWidget(host)
            advanced.setVisible(advanced_form.rowCount() > 0)
            defaults = {p['id']: p['default'] for p in schema['parameters']}
            defaults.update({k: 0. for k in (model or {}).get('laps', {})})
            entry = self.schema_forms[key] = dict(host=host, advanced=advanced, values={}, model=model, defaults=defaults,
                                                  fields={k: self.fields[k] for k in defaults})
        else:
            for pid, info in entry['fields'].items():
                self.fields[pid] = info
                self.values[pid] = entry['values'].get(pid, entry['defaults'][pid])
                info['edit'].setText(self.display_value(pid, self.values[pid])); info['label'].setText(self.caption(pid))
                self.applied_text[pid] = info['edit'].text(); self.show_field_error(pid, None)
        self.advanced = entry['advanced']; self.model = entry['model']; entry['host'].show()
        dropped = []
        old_kinds = {p['id']: p['kind'] for p in (previous or {}).get('parameters', [])}
        for p in schema['parameters']:
            if keep and p['id'] in old_values and old_kinds.get(p['id']) == p['kind'] and old_values[p['id']] is not None:
                self.values[p['id']] = old_values[p['id']]
                self.fields[p['id']]['edit'].setText(self.display_value(p['id'], old_values[p['id']]))
                self.applied_text[p['id']] = self.fields[p['id']]['edit'].text()
        if keep and previous:
            new_ids = {p['id'] for p in schema['parameters']}
            dropped = [p['label'] for p in previous['parameters'] if p['id'] not in new_ids and old_values.get(p['id']) is not None]
        options = schema.get('options', {})
        self._fill_options(self.reference, options.get('dimension_reference', ['mid']), REFERENCE_TITLES,
                           prefer=options.get('default_reference', 'mid'))
        self._fill_options(self.joint_kind, options.get('joint_kinds', ['butt']), JOINT_TITLES, prefer='butt')
        for key, supported, reason in (('seam_angle', options.get('seam'), 'Bu şekilde dikiş yeri seçilemez.'),
                                       ('split_count', options.get('split'), 'Bu şekil çevresel bölmeyi desteklemiyor.')):
            self.fields[key]['edit'].setEnabled(bool(supported))
            self.fields[key]['edit'].setToolTip('' if supported else reason)
        self.joint_changed(recalculate=False)
        self.sketch.set_schema(schema); self.sync_inline()
        self.sketch.setVisible(bool(schema.get('sketch')))     # source models: no dimensioned sketch yet, the form has the symbols
        self.reference_sketch.set_reference(self.reference.currentData())
        shape = self.shape_by_id(self.shape_id)
        self.shape_title.setText(f'{shape["title"]} · {self.variant.currentText()}')
        if dropped:
            self.set_status('Varyant değişti; bu değerler yeni varyantta yok: ' + ', '.join(dropped), tone='warning')
        self.input_changed()

    # ---- source-model options (engine 1.1.0: cut choice, edge laps, helper lines, numbering) ----
    def build_model_options(self, schema, column):
        """Controls for ``schema.options.model_options``, built once per schema and kept with its form."""
        options = schema['options'].get('model_options') or {}
        support = options.get('option_support') or {}; features = options.get('source_features') or {}
        model = dict(laps={})
        cut_host = QWidget(); cut_form = QFormLayout(cut_host); cut_form.setContentsMargins(0, 0, 0, 0)
        cut_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        cut = QComboBox(); cut.setAccessibleName('Kesim / dikiş seçimi')
        for item in options.get('cut_options') or ():
            cut.addItem(item['label'], item['value'])
        cut.setEnabled(cut.count() > 1)
        cut.setToolTip('Parçanın kaç parçadan ve nereden dikişle kesileceği.' if cut.count() > 1 else 'Bu modelde tek kesim düzeni var.')
        cut.currentIndexChanged.connect(self.input_changed); model['cut'] = cut
        cut_form.addRow('Kesim düzeni', cut); column.addWidget(cut_host)

        extra = QWidget(); extra_form = QFormLayout(extra); extra_form.setContentsMargins(0, 0, 0, 0)
        extra_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        laps = []
        if support.get('edge_allowances'):
            if features.get('lapFields'):           # ducts: flange on the long wall edges and lap at the wall ends only
                laps = [DUCT_LAP_TITLES[f['key']] for f in features['lapFields'] if f.get('key') in DUCT_LAP_TITLES]
            else:
                laps = [(k, LAP_TITLES[k], 'Açınımın bu kenarına eklenen kaynak/bindirme payı. 0 = yok.')
                        for k in ('lap_top', 'lap_bottom', 'lap_left', 'lap_right')]
        if support.get('strip_lap'):
            laps.append(('strip_lap', LAP_TITLES['strip_lap'], 'Parçalar arası birleşim şeridinin payı. 0 = yok.'))
        for name, title, hint in laps:
            key = 'opt.' + name
            self._field(key, title, '', 'length', 0.)
            self._add_field_row(extra_form, key, hint=hint); model['laps'][key] = name
        divisions = QComboBox(); divisions.setAccessibleName('Yardımcı çizgi bölmesi')
        for n in options.get('helper_divisions') or (24,):
            divisions.addItem(f'{n} bölme', n)
        divisions.setCurrentIndex(max(divisions.findData(24), 0))
        divisions.setToolTip('Açınımdaki yardımcı (G) çizgilerinin sayısı. Eğri hassasiyetini değiştirmez.')
        divisions.currentIndexChanged.connect(self.input_changed); model['divisions'] = divisions
        extra_form.addRow('Yardımcı çizgiler', divisions)
        numbering = QCheckBox('Yardımcı çizgileri numarala'); numbering.setAccessibleName('Numaralama')
        allowed = not features.get('noNumbers')
        numbering.setChecked(allowed); numbering.setEnabled(allowed)
        numbering.setToolTip('' if allowed else 'Bu modelde numaralama yok.')
        numbering.toggled.connect(self.input_changed); model['numbering'] = numbering
        extra_form.addRow('', numbering)
        column.addWidget(Disclosure('Kenar payları ve yardımcı çizgiler', extra))

        source = schema.get('source') or {}
        info = QWidget(); info_box = QVBoxLayout(info); info_box.setContentsMargins(0, 0, 0, 0); info_box.setSpacing(4)
        text = label(self.source_text(schema), 'muted', wrap=True); text.setTextFormat(Qt.RichText)
        text.setOpenExternalLinks(True); text.setTextInteractionFlags(Qt.TextBrowserInteraction); info_box.addWidget(text)
        example = button('Çalışan örneği yükle', lambda: self.load_example(schema.get('source_id')))
        example.setToolTip('Bu model için doğrulanmış bir örnek ölçü setini yükler (kalınlık, malzeme ve birim aynı kalır).')
        example.setEnabled(bool(source.get('has_example'))); info_box.addWidget(example, alignment=Qt.AlignLeft)
        model['info'] = text; model['example'] = example
        column.addWidget(Disclosure('Model bilgisi ve sınırlar', info))
        return model

    def source_text(self, schema):
        source = schema.get('source') or {}
        if not source:
            return ''
        method = METHOD_TITLES.get(source.get('method'), source.get('method') or '—')
        stages = ''.join(f'<br>{"✔" if done else "✖"} {title}' for title, done in source.get('stages', ()))
        limits = ''.join(f'<li>{text}</li>' for text in source.get('restrictions', ()))
        url = source.get('url')
        return (f'<b>Yöntem:</b> {method}<br><b>Durum:</b> {source.get("status", "—")}{stages}'
                f'<br><b>Doğrulanmış çıktılar:</b> {", ".join(source.get("outputs") or ()) or "—"}'
                + (f'<ul style="margin-left:-20px">{limits}</ul>' if limits else '')
                + (f'Kaynak model: <a href="{url}">{url}</a>' if url else ''))

    def model_options(self):
        """Request ``model_options`` from the visible controls; lengths in the current input unit."""
        model = getattr(self, 'model', None)
        if not model:
            return {}
        # Only choices that differ from the engine defaults are sent (same request as a saved project).
        options = {}
        if model['cut'].currentIndex() > 0:
            options['cut_type'] = model['cut'].currentData()
        if model['divisions'].currentData() != 24:
            options['helper_divisions'] = model['divisions'].currentData()
        if model['numbering'].isChecked() != model['numbering'].isEnabled():
            options['numbering'] = model['numbering'].isChecked()
        for key, name in model['laps'].items():
            value = self.values.get(key)
            if value:
                options[name] = to_display(value, self._unit)
        return {k: v for k, v in options.items() if v is not None}

    def apply_model_options(self, options, unit):
        """Restore saved model options (project / example); unknown keys stay with the engine's defaults."""
        model = getattr(self, 'model', None)
        if not model:
            return
        allowed = model['numbering'].isEnabled()
        for box, value in ((model['cut'], options.get('cut_type')), (model['divisions'], options.get('helper_divisions', 24))):
            index = box.findData(value) if value is not None else 0
            box.blockSignals(True); box.setCurrentIndex(max(index, 0)); box.blockSignals(False)
        model['numbering'].blockSignals(True); model['numbering'].setChecked(bool(options.get('numbering', allowed)) and allowed)
        model['numbering'].blockSignals(False)
        for key, name in model['laps'].items():
            value = options.get(name) or 0.
            self.values[key] = to_mm(value, unit) if value else 0.
            self.fields[key]['edit'].setText(self.display_value(key, self.values[key])); self.applied_text[key] = self.fields[key]['edit'].text()
            self.errors.pop(key, None); self.show_field_error(key, None)

    def load_example(self, source_id):
        """Shape dimensions, seam position and model options change; thickness, material and unit are the user's."""
        example = self.service.example_request(source_id) if source_id else None
        if example is None or example['shape_id'] != self.shape_id or example['variant_id'] != self.variant_id:
            self.set_status('Bu model için örnek bulunamadı.', True); return
        unit = example.get('input_units', 'mm')
        for key, value in example['parameters'].items():
            if key in self.fields:
                self.values[key] = to_mm(value, unit) if self.fields[key]['kind'] == 'length' else value
                self.fields[key]['edit'].setText(self.display_value(key, self.values[key]))
                self.applied_text[key] = self.fields[key]['edit'].text(); self.errors.pop(key, None); self.show_field_error(key, None)
        seam = (example.get('seam_options') or {}).get('start_angle_deg')
        if seam is not None and self.fields['seam_angle']['edit'].isEnabled():      # the seam position belongs to the example
            self.values['seam_angle'] = seam; self.fields['seam_angle']['edit'].setText(self.display_value('seam_angle', seam))
            self.applied_text['seam_angle'] = self.fields['seam_angle']['edit'].text()
        self.apply_model_options(example.get('model_options') or {}, unit)
        self.sync_inline(); self.set_status('Doğrulanmış örnek ölçüler yüklendi.', tone='success')
        self.calculate_now() if self.build_request() is not None else self.input_changed()

    @staticmethod
    def _fill_options(box, values, titles, prefer=None):
        current = box.currentData()
        box.blockSignals(True); box.clear()
        for value in values:
            box.addItem(str(titles.get(value, value)), value)
        index = box.findData(current)
        box.setCurrentIndex(index if index >= 0 else max(box.findData(prefer), 0)); box.setEnabled(len(values) > 1)
        if not box.isEnabled():
            box.setToolTip('Bu şekil yalnız bu seçeneği destekliyor.')
        box.blockSignals(False)

    def joint_changed(self, *args, recalculate=True):
        lap = self.joint_kind.currentData() == 'lap'
        self.fields['joint']['edit'].setEnabled(lap)
        self.fields['joint']['edit'].setToolTip('' if lap else 'Bindirme payı yalnız bindirmeli birleşimde kullanılır.')
        if recalculate:
            self.input_changed()

    def material_changed(self, *args):
        self.restore_material_caption()
        self.loaded_material = None
        if self.price_unit!='kg' or self.price_currency not in ('','TL'):
            self.values['price']=None;self.fields['price']['edit'].clear();self.applied_text['price']=''
        self.price_unit = 'kg'; self.price_currency = 'TL'
        self.update_price_caption()
        self.input_changed()

    @staticmethod
    def material_caption(material):
        density=material.get('density_kg_m3')
        return material['title']+(f' · {fmt(density,0)} kg/m³' if density is not None else '')

    def restore_material_caption(self):
        if self.loaded_material is None:return
        name=self.loaded_material.get('name','')
        entry=next((m for m in self.materials if m['id']==name),None)
        if entry is not None:self.material.setItemText(self.material.findData(name),self.material_caption(entry))

    def update_price_caption(self):
        currency = '₺' if self.price_currency == 'TL' else self.price_currency
        unit = 'm²' if self.price_unit == 'm2' else self.price_unit
        self.fields['price']['symbol'] = f'{currency}/{unit}'
        self.fields['price']['label'].setText(self.caption('price'))

    def eventFilter(self, watched, event):
        for key, info in self.fields.items():
            if info['edit'] is watched:
                if event.type() == QEvent.FocusIn:
                    self.sketch.highlight(key)
                elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                    info['edit'].setText(self.applied_text.get(key, '')); self.field_edited(key)
                    return True
        return super().eventFilter(watched, event)

    def focus_field(self, parameter_id):
        info = self.fields.get(parameter_id)
        if info:
            if not info['edit'].isVisible() and self.advanced is not None and self.advanced.isVisible():
                self.advanced.set_expanded(True)
            target = info.get('combo') or info['edit']
            target.setFocus()
            if target is info['edit']:
                info['edit'].selectAll()
            self.sketch.highlight(parameter_id)

    def field_edited(self, key):
        info = self.fields[key]; text = info['edit'].text()
        try:
            if not text.strip():
                value = None
            else:
                number = parse(text, info['title'])
                if info['kind'] == 'count':
                    if number != int(number):
                        raise ValueError(f'{info["title"]} tam sayı olmalı.')
                    number = int(number)
                value = to_mm(number, self._unit) if info['kind'] == 'length' else number
            self.values[key] = value; self.errors.pop(key, None)
        except ValueError as error:
            self.values[key] = None; self.errors[key] = str(error)
        self.show_field_error(key, self.errors.get(key))
        self.sketch.set_text(key, info['edit'].text())
        self.input_changed()

    def inline_edited(self, key, text):
        """Typing on the drawing is the same as typing in the form field."""
        if key in self.fields:
            self.fields[key]['edit'].setText(text); self.field_edited(key)

    def sync_inline(self):
        for key in self.fields:
            self.sketch.set_text(key, self.fields[key]['edit'].text())

    def show_field_error(self, key, message, severity='error'):
        self.sketch.set_invalid(key, bool(message) and severity == 'error')
        info = self.fields[key]
        info['error'].setText(message or ''); info['error'].setVisible(bool(message))
        colour = COLORS[self.context.appearance]['danger' if severity == 'error' else 'warning']
        info['error'].setStyleSheet(f'color: {colour};' if message else '')
        info['edit'].setProperty('invalid', bool(message)); info['edit'].setToolTip(message or '')

    def unit_changed(self, *args):
        """Same physical part: lengths are converted for display, the stored mm stay as they are."""
        self._unit = self.unit.currentData()
        for key, info in self.fields.items():
            if info['kind'] == 'length' and key not in self.errors:
                info['edit'].setText(self.display_value(key, self.values.get(key))); self.applied_text[key] = info['edit'].text()
            if info['label'] is not None:
                info['label'].setText(self.caption(key))
        self.sync_inline()
        self.input_changed()

    def reference_changed(self, *args):
        if self.reference.currentData():
            self.reference_sketch.set_reference(self.reference.currentData())
        self.input_changed()

    # ==================================================================================
    # Requests and calculation
    # ==================================================================================
    def build_request(self):
        """None while any required value is missing or invalid (no request with guessed data)."""
        if self.schema is None:
            return None
        missing = [p['label'] for p in self.schema['parameters'] if p.get('required') and self.values.get(p['id']) is None]
        if missing or self.errors:
            return None
        def given(key):
            value = self.values.get(key)
            return to_display(value, self._unit) if value is not None and self.fields[key]['kind'] == 'length' else value
        parameters = {p['id']: given(p['id']) for p in self.schema['parameters'] if self.values.get(p['id']) is not None}
        material = next((m for m in self.materials if m['id'] == self.material.currentData()), None)
        material_data = dict(self.loaded_material) if self.loaded_material is not None else (
            dict(name=material['id'],density_kg_m3=material.get('density_kg_m3')) if material else {})
        material_data.update(unit_price=self.values.get('price'),price_unit=self.price_unit,currency=self.price_currency)
        model_options = self.model_options()
        enabled = lambda key: self.fields[key]['edit'].isEnabled()
        try:forming_options=self.forming.options()
        except ValueError:return None
        return dict(schema_version=1, request_id=str(uuid.uuid4()), revision=self.revision, shape_id=self.shape_id,
                    variant_id=self.variant_id, parameters=parameters, input_units=self._unit,
                    thickness=given('thickness') or None, dimension_reference=self.reference.currentData(),
                    material=material_data,
                    seam_options=dict(start_angle_deg=self.values.get('seam_angle') or 0.) if enabled('seam_angle') else {},
                    split_options=dict(count=int(self.values.get('split_count') or 1)) if enabled('split_count') else {},
                    joint_options=dict(kind=self.joint_kind.currentData() or 'butt',
                                       overlap=(given('joint') or 0.) if self.joint_kind.currentData() == 'lap' else 0.),
                    development_options=dict(self.development_options), model_options=model_options,forming_options=forming_options)

    def input_changed(self, *args):
        self.revision += 1
        if self.result is not None and self.state not in ('stale', 'invalid_stale'):
            self.set_state('stale')        # keep the last drawing, clearly marked; exports are blocked
        self.refresh_actions()
        if self.build_request() is None:
            self.calc_timer.stop()
            self.set_state('invalid_stale' if self.result is not None else 'missing')
            return
        self.calc_timer.start()

    def calculate_now(self):
        self.calc_timer.stop(); self.calculate()

    def calculate(self):
        if not self.isVisible() or getattr(self.context, 'closing', False):
            # A hidden page never starts background work; it calculates when shown.
            self.pending_show = True; return
        self.pending_show = False
        request = self.build_request()
        if request is None:
            self.set_state('missing'); return
        if self.jobs.busy:
            # One job at a time: stop the old one; the newest request starts when it ends.
            self.queued = True; self.jobs.cancel(); return
        self.running_request = request
        self.set_state('running')
        service = self.service

        def run(events, stop):
            report = service.validate(request)
            if not report.get('ok', False):
                events.put(('unfold_validation', (request, report))); return
            result = service.calculate(request, cancel_token=stop)
            events.put(('unfold_result', (request, report, result)))
        self.jobs.start(self, run)

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'unfold_validation':
                self.accept_validation(*value)
            elif kind == 'unfold_result':
                self.accept_result(*value)
            elif kind == 'unfold_files':
                self.files_finished(value)
            elif kind == 'job_error':
                text = value.get('error', '')
                self.set_state('cancelled' if 'İptal' in text or 'Interrupted' in text else 'error')
        super().handle_events([e for e in events if not (e[0] == 'job_error' and 'İptal' in e[1].get('error', ''))])

    def _current(self, request):
        return request['revision'] == self.revision

    def accept_validation(self, request, report):
        if not self._current(request):
            return
        for key in self.fields:
            if key not in self.errors:
                self.show_field_error(key, None)
        general = []
        for issue in report.get('issues', []):
            ids = [i for i in issue.get('field_ids', []) if i in self.fields]
            for key in ids:
                self.show_field_error(key, issue['message'], issue.get('severity', 'error'))
            if not ids:
                general.append(issue['message'])
        self.validation_note.setText('\n'.join(general) + ('\n' if general else '') + report.get('note', ''))
        self.set_state('error'); self.set_status('Ölçüler geçerli değil; işaretli alanları düzeltin.', True)

    def accept_result(self, request, report, result):
        # Reject late answers: the result must belong to the request of the current revision.
        if not self._current(request) or result.get('request_id') != request['request_id'] or result.get('revision') != request['revision']:
            return
        for key in self.fields:
            if key not in self.errors:
                self.show_field_error(key, None)
        for issue in report.get('issues', []):
            for key in issue.get('field_ids', []):
                if key in self.fields:
                    self.show_field_error(key, issue['message'], issue.get('severity', 'warning'))
        self.validation_note.setText(report.get('note', ''))
        self.result, self.result_revision, self.result_request = result, request['revision'], request
        status = result.get('status')
        self.set_state({'ok': 'ok', 'warning': 'warning', 'example': 'example'}.get(status, 'error'))
        self.show_result(result)

    def job_finished(self):
        self.running_request = None
        self.file_done = None; self.quiet_cancel_on_close = True
        if self.queued:
            self.queued = False; self.calculate()
        elif self.state == 'running':
            self.set_state('cancelled')

    def set_state(self, state):
        self.state = state
        text, token = STATES[state]
        colour = COLORS[self.context.appearance][token]
        self.state_label.setText(('● ' if state in ('ok', 'example', 'warning') else '◆ ' if state == 'error' else '○ ') + text)
        self.state_label.setStyleSheet(f'color: {colour}; font-weight: 600;')
        self.refresh_actions()

    def is_current(self):
        return self.result is not None and self.result_revision == self.revision and self.state in ('ok', 'warning', 'example')

    def refresh_actions(self):
        if not hasattr(self, 'export_buttons'):
            return
        current = self.is_current()
        capabilities = (self.result or {}).get('capabilities', {}) if current else {}
        exports = set(capabilities.get('exports', ()))
        many = len((self.result or {}).get('parts', ())) > 1
        for key, widget in self.export_buttons.items():
            enabled = key in exports and not self.busy and not (key in ('dxf','dwg') and many)
            if hasattr(self,'export_development') and self.export_development.currentData() in ('compensated','comparison'):
                enabled=enabled and bool((self.result or {}).get('forming_report',{}).get('all_compensated')) and key!='step'
            widget.setEnabled(enabled)
            widget.setToolTip('' if enabled else 'Güncel bir sonuç yok.' if not current else
                              'Çok parçalı sonuçta her parça ayrı çıktı olur: Toplu ZIP kullanın.' if key in ('dxf','dwg') and many else
                              'DWG için kurulu yerel ODA File Converter gerekli.' if key=='dwg' else
                              capabilities.get('step_reason') or 'Katı STEP için pozitif sac kalınlığı ve desteklenen nominal CAD geometrisi gerekli.'
                              if key == 'step' else 'Bu sonuç için servis bu çıktıyı sağlamıyor.')
        nesting = bool(capabilities.get('nesting')) and not self.busy and 'nesting' in self.context.pages
        self.nesting_button.setEnabled(nesting)
        self.nesting_button.setToolTip('Kontur, delik, kalınlık, malzeme ve adet Nesting projesine aktarılır.' if nesting else
                                       'Güncel ve başarılı bir sonuç gerekli.')
        for widget in (self.open_button, self.save_button):
            widget.setEnabled(not self.busy)
        self.add_part_button.setEnabled(current and not self.busy)
        if hasattr(self, 'project_zip_button'):
            self.project_zip_button.setEnabled(bool(self.project_parts) and not self.busy)

    # ==================================================================================
    # Right: views and results
    # ==================================================================================
    def build_workspace(self):
        from modules.dxf_dwg.preview.viewer import MeshView
        self.mesh_view = MeshView(); self.mesh_view.setAccessibleName('Sac parçası 3D görünüm')
        views = QHBoxLayout(); views.setSpacing(2)
        for name in ('İzometrik', 'Ön', 'Üst', 'Sağ'):
            views.addWidget(button(name, lambda *_, n=name: self.mesh_view.view(n), flat=True))
        views.addWidget(button('Sığdır', lambda: self.mesh_view.fit(), flat=True)); views.addStretch(1)
        self.view_choice = QComboBox(); self.view_choice.setAccessibleName('Görünüm seçimi')
        self.view_choice.setSizeAdjustPolicy(QComboBox.AdjustToContents); self.view_choice.setMinimumWidth(130)
        self.view_choice.currentIndexChanged.connect(self.show_view)
        self.drawing_view = DevelopmentView(); self.drawing_view.setAccessibleName('Teknik görünüş')
        self.mesh_stack = QStackedWidget(); self.mesh_stack.addWidget(self.mesh_view); self.mesh_stack.addWidget(self.drawing_view)
        self.mesh_caption = label('', 'muted')
        mesh_panel = QWidget(); mesh_box = QVBoxLayout(mesh_panel); mesh_box.setContentsMargins(0, 0, 0, 0)
        mesh_box.addWidget(section_header('3D / Teknik görünüş', self.view_choice)); mesh_box.addLayout(views)
        mesh_box.addWidget(self.mesh_stack, 1)
        mesh_box.addWidget(self.mesh_caption)

        self.flat_view = DevelopmentView(); self.flat_view.measured.connect(self.show_measure)
        self.flat_view.partClicked.connect(self.select_part)
        tools = QHBoxLayout(); tools.setSpacing(2)
        tools.addWidget(button('Sığdır', self.flat_view.fit, flat=True)); tools.addWidget(button('1:1', self.flat_view.one_to_one, flat=True))
        self.measure_button = button('Ölçüm', flat=True); self.measure_button.setCheckable(True)
        self.measure_button.toggled.connect(self.flat_view.set_measuring)
        self.measure_button.setToolTip('İki köşe/uç noktaya tıklayın; uzaklık servis geometrisinden hesaplanır.')
        self.focus_button = button('Yalnız seçili parça', flat=True); self.focus_button.setCheckable(True)
        self.focus_button.toggled.connect(self.flat_view.set_focus_selected)
        tools.addWidget(self.measure_button); tools.addWidget(self.focus_button); tools.addStretch(1)
        layers = QVBoxLayout(); layers.setSpacing(2); self.layer_boxes = {}
        for key, title, token, style, width in LAYERS:
            box = QCheckBox(f'{title} {"━" if style == Qt.SolidLine else "╍" if style == Qt.DashLine else "┄" if style == Qt.DotLine else "─·"}')
            box.setChecked(True); box.toggled.connect(lambda on, k=key: self.flat_view.set_layer(k, on))
            box.setToolTip({'construction': 'Yardımcı doğrular (ana doğrular); abkant büküm sayısı değildir.',
                            'bend': 'Gerçek büküm çizgileri (servis bend katmanı).'}.get(key, title))
            self.layer_boxes[key] = box
        boxes = list(self.layer_boxes.values())
        for start in range(0, len(boxes), 4):
            layers.addWidget(AdaptiveRow(*boxes[start:start+4], spacing=8))
        self.measure_label = label('', 'muted')
        flat_panel = QWidget(); flat_box = QVBoxLayout(flat_panel); flat_box.setContentsMargins(0, 0, 0, 0)
        flat_box.addWidget(section_header('Açınım')); flat_box.addLayout(tools); flat_box.addLayout(layers)
        flat_box.addWidget(self.flat_view, 1); flat_box.addWidget(self.measure_label)

        self.view_split = QSplitter(Qt.Horizontal); self.view_split.addWidget(mesh_panel); self.view_split.addWidget(flat_panel)
        self.view_split.setStretchFactor(0, 4); self.view_split.setStretchFactor(1, 5)
        self.view_split.setSizes([4000, 5000]); self.view_tabs = QTabWidget()
        self.view_stack = QStackedWidget(); self.view_stack.addWidget(self.view_split); self.view_stack.addWidget(self.view_tabs)
        self.view_panels = (mesh_panel, flat_panel)

        results = self.build_results()
        self.metrics = MetricStrip((('size', 'Açınım ölçüsü'), ('area', 'Net alan'), ('cut', 'Kesim boyu'),
                                    ('mass', 'Kütle'), ('parts', 'Parça')))
        header = QWidget(); header_box = QVBoxLayout(header); header_box.setContentsMargins(0, 0, 0, 4); header_box.setSpacing(2)
        header_box.addWidget(self.state_label); header_box.addWidget(self.metrics)
        top = QWidget(); top_box = QVBoxLayout(top); top_box.setContentsMargins(0, 0, 0, 0); top_box.setSpacing(2)
        top_box.addWidget(header); top_box.addWidget(self.view_stack, 1)
        right = QSplitter(Qt.Vertical); right.addWidget(top); right.addWidget(results)
        right.setChildrenCollapsible(False); right.setStretchFactor(0, 7); right.setStretchFactor(1, 3)
        right.setSizes([7000, 3000]); self.right_split = right
        return right

    def apply_view_layout(self, *args):
        tabs = self.layout_mode.currentData() == 'tabs' or self.width() < 1250
        current = self.view_stack.currentWidget() is self.view_tabs
        if tabs == current:
            return
        if tabs:
            for panel, title in zip(self.view_panels, ('3D / Teknik görünüş', 'Açınım')):
                self.view_tabs.addTab(panel, title)
            self.view_tabs.setCurrentIndex(1); self.view_stack.setCurrentWidget(self.view_tabs)
        else:
            while self.view_tabs.count():
                self.view_tabs.removeTab(0)
            for panel in self.view_panels:
                self.view_split.addWidget(panel); panel.show()
            self.view_stack.setCurrentWidget(self.view_split); self.view_split.setSizes([4000, 5000])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'view_stack'):
            self.apply_view_layout()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, 'pending_show', False) and self.build_request() is not None:
            self.calc_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.calc_timer.isActive():
            self.calc_timer.stop(); self.pending_show = True

    def build_results(self):
        self.state_label = label('', wrap=False)
        self.method_label = label('', 'muted')
        self.part_table = _table(['Parça', 'Adet', 'Net alan · mm²', 'Paylı alan · mm²', 'Çevreleyen · mm',
                                  'Kesim boyu · mm', 'Kütle · kg', 'Maliyet · ₺'], stretch=0)
        self.part_table.itemSelectionChanged.connect(self.part_row_selected); self.part_table.setMinimumHeight(70)
        self.messages = QTextBrowser()
        self.export_buttons = {key: button(title, lambda *_, k=key: self.export_current(k)) for key, title in EXPORTS}
        self.nesting_button = button("Nesting'e gönder", self.send_to_nesting)
        exports = QWidget(); ebox = QHBoxLayout(exports); ebox.setContentsMargins(0, 0, 0, 0); ebox.setSpacing(4)
        ebox.addWidget(label('Çıktı', 'muted'))
        self.export_development=QComboBox();self.export_development.setAccessibleName('Açınım çıktı türü')
        for title,value in (('Güncel açınım','current'),('Nominal açınım','nominal'),('Telafili açınım','compensated'),('Nominal / telafili karşılaştırma','comparison')):
            self.export_development.addItem(title,value)
        self.export_development.currentIndexChanged.connect(self.refresh_actions)
        for widget in (*self.export_buttons.values(), self.nesting_button):
            ebox.addWidget(widget)
        result_tab = QWidget(); rbox = QVBoxLayout(result_tab); rbox.setContentsMargins(0, 4, 0, 0)
        rbox.addWidget(self.part_table, 1); rbox.addWidget(self.method_label)
        selection=QHBoxLayout();selection.addWidget(label('Açınım seçimi','muted'));selection.addWidget(self.export_development);selection.addStretch(1)
        rbox.addLayout(selection)
        out = QHBoxLayout(); out.addStretch(1); out.addWidget(exports); rbox.addLayout(out)
        messages_tab = QWidget(); mbox = QVBoxLayout(messages_tab); mbox.setContentsMargins(0, 4, 0, 0); mbox.addWidget(self.messages)

        self.project_table = _table(['Kod', 'Ad', 'Şekil / varyant', 'Rev.', 'Kalınlık', 'Malzeme', 'Adet', 'Durum'], stretch=1)
        self.project_table.itemSelectionChanged.connect(self.project_row_selected)
        self.add_part_button = button('Projeye ekle', self.add_to_project)
        self.add_part_button.setToolTip('Güncel sonucu proje parçası olarak ekler.')
        self.duplicate_button = button('Çoğalt', self.duplicate_part); self.remove_button = button('Kaldır', self.remove_part)
        project_tab = QWidget(); pbox = QVBoxLayout(project_tab); pbox.setContentsMargins(0, 4, 0, 0)
        self.project_zip_button = button("Projeyi ZIP'e aktar", self.export_project_zip)
        self.project_zip_button.setToolTip('Her parçayı motor yeniden hesaplar; ayrı DXF/PDF ve proje manifesti üretir.')
        from PySide6.QtWidgets import QSpinBox
        self.part_quantity = QSpinBox(); self.part_quantity.setRange(1, 1000000); self.part_quantity.setAccessibleName('Seçili parça adedi')
        self.part_quantity.valueChanged.connect(self.quantity_changed)
        prow = QHBoxLayout(); prow.addWidget(self.add_part_button); prow.addWidget(self.duplicate_button)
        prow.addWidget(self.remove_button); prow.addWidget(label('Adet', 'muted')); prow.addWidget(self.part_quantity)
        prow.addStretch(1); prow.addWidget(self.project_zip_button)
        pbox.addLayout(prow); pbox.addWidget(self.project_table, 1)
        self.result_tabs = QTabWidget(); self.result_tabs.setDocumentMode(True)
        self.result_tabs.addTab(result_tab, 'Parçalar'); self.result_tabs.addTab(messages_tab, 'Uyarılar')
        self.result_tabs.addTab(project_tab, 'Proje')
        self.forming_results=QTextBrowser();self.forming_results.setAccessibleName('Şekillendirme hesap sonuçları')
        self.result_tabs.addTab(self.forming_results,'Telafi / yaylanma')
        self.controls += [self.duplicate_button, self.remove_button]
        return self.result_tabs

    def show_result(self, result):
        parts = result.get('parts', [])
        message = '; '.join(e['message'] for e in result.get('errors', [])) or 'Açınım yok.'
        self.flat_view.set_parts(parts, message)
        from core.unfolding.forming.reporting import report_lines
        self.forming_results.setPlainText('\n'.join(report_lines(result.get('forming_report') or {})))
        material = (self.result_request or {}).get('material') or {}
        currency=material.get('currency','')
        self.part_table.horizontalHeaderItem(7).setText('Maliyet'+(' · '+('₺' if currency=='TL' else currency) if currency else ''))
        rows = []
        for part in parts:
            m = part.get('metrics', {})
            mass = m.get('mass_kg')
            if mass is None:
                reason = ('kalınlık yok' if not self.result_request.get('thickness') else
                          'malzeme yoğunluğu yok' if not material.get('density_kg_m3') else 'servis kütle vermedi')
                mass_text = f'Hesaplanamadı ({reason})'
            else:
                mass_text = fmt(mass, 3)
            cost = m.get('cost')
            cost = fmt(cost, 2) if cost is not None else ('Fiyat girilmedi' if mass is not None else 'Hesaplanamadı')
            bbox = m.get('bbox_mm')
            rows.append((part.get('name', part['part_id']), part.get('quantity', 1), fmt(m.get('net_area_mm2'), 1),
                         fmt(m.get('gross_area_mm2'), 1), f'{fmt(bbox[0], 1)} × {fmt(bbox[1], 1)}' if bbox else '—',
                         fmt(m.get('cut_length_mm'), 1), mass_text, cost))
        _fill(self.part_table, rows, align_right=(1, 2, 3, 5))
        if parts:
            self.part_table.selectRow(0)
        method = METHOD_TITLES.get(result.get('calculation_method'), result.get('calculation_method') or '—')
        quality = result.get('quality_metrics') or {}
        metrics = [(key, title) for key, title in (('chord_error_bound_mm', 'kord hatası ≤'), ('contour_closure_error_mm', 'kontur kapanma'),
                                                    ('seam_closure_error_mm', 'dikiş kapanma')) if quality.get(key) is not None]
        figures = ' · '.join(f'{title} {fmt(float(quality[key]), 6)} mm' for key, title in metrics)
        self.method_label.setText(f'Yöntem: {method}' + (f' · {figures} (yazılım ölçütleri; imalat toleransı değildir)' if figures else '')
                                  + f' · {result.get("engine_version", "")}')
        lines = [f'⚠ {w["message"]}' for w in result.get('warnings', [])] + [f'✖ {e["message"]}' for e in result.get('errors', [])]
        self.messages.setPlainText('\n'.join(lines) or 'Uyarı yok.')
        self.result_tabs.setTabText(1, f'Uyarılar ({len(lines)})' if lines else 'Uyarılar')
        total = lambda key: sum((p.get('metrics') or {}).get(key) or 0 for p in parts) if parts else None
        first = (parts[0].get('metrics') or {}) if parts else {}
        bbox = first.get('bbox_mm')
        u = self._unit
        self.metrics.set('size', f'{fmt(to_display(bbox[0], u), 1)} × {fmt(to_display(bbox[1], u), 1)} {u}' if bbox and len(parts) == 1 else
                         ('çok parçalı' if parts else '—'))
        self.metrics.set('area', f'{fmt(total("net_area_mm2") / 1e6, 4)} m²' if parts else '—')
        self.metrics.set('cut', f'{fmt(to_display(total("cut_length_mm"), u), 1)} {u}' if parts else '—')
        masses = [(p.get('metrics') or {}).get('mass_kg') for p in parts]
        self.metrics.set('mass', f'{fmt(sum(masses), 3)} kg' if parts and None not in masses else 'Hesaplanamadı' if parts else '—')
        self.metrics.set('parts', str(sum(p.get('quantity', 1) for p in parts)) if parts else '—')
        self.show_mesh()
        self.refresh_actions()

    def show_view(self, *args):
        """3D preview mesh, or one of the service's technical views (front / top wireframes)."""
        part = self.selected_part(); index = self.view_choice.currentData()
        if index is None or part is None:
            self.mesh_stack.setCurrentIndex(0); return
        view = part.get('drawing_views', [])[index]
        self.drawing_view.set_parts([dict(part_id=part['part_id'], geometry_2d=dict(entities=view['entities']))])
        self.mesh_stack.setCurrentIndex(1)
        self.mesh_caption.setText(f'{view["label"]} · servis tel görünüşü')

    def show_mesh(self):
        part = self.selected_part()
        current = self.view_choice.currentData()
        self.view_choice.blockSignals(True); self.view_choice.clear(); self.view_choice.addItem('3D önizleme', None)
        for i, view in enumerate((part or {}).get('drawing_views', [])):
            self.view_choice.addItem(view['label'], i)
        self.view_choice.setCurrentIndex(max(self.view_choice.findData(current), 0)); self.view_choice.blockSignals(False)
        triangles = (part or {}).get('mesh_3d', {}).get('triangles_mm') if part else None
        if not triangles:
            self.mesh_view.set_mesh(None)
            self.mesh_caption.setText('Bu sonuç için 3D ağ yok.'); return
        from modules.dxf_dwg.preview.geometry import make_mesh
        try:
            self.mesh_view.set_mesh(make_mesh([c / 1000. for c in triangles]))   # viewer takes metres
            self.mesh_caption.setText(f'{part.get("name", part["part_id"])} · servis önizleme ağı (STEP veya katı değildir)')
            self.show_view()
        except ValueError as error:
            self.mesh_view.set_mesh(None); self.mesh_caption.setText(f'3D ağ gösterilemedi: {error}')

    def selected_part(self):
        parts = (self.result or {}).get('parts', [])
        rows = self.part_table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(parts):
            return parts[rows[0].row()]
        return parts[0] if parts else None

    def part_row_selected(self):
        part = self.selected_part()
        if part:
            self.flat_view.select(part['part_id']); self.show_mesh()

    def select_part(self, part_id):
        for row, part in enumerate((self.result or {}).get('parts', [])):
            if part['part_id'] == part_id:
                self.part_table.selectRow(row); break

    def show_measure(self, distance_mm):
        self.measure_label.setText(f'Ölçülen: {fmt(to_display(distance_mm, self._unit), 3)} {self._unit} '
                                   '(servis geometrisinin köşe/uç noktaları arasında)')

    # ==================================================================================
    # Project parts
    # ==================================================================================
    def mark_dirty(self, dirty=True):
        self.dirty = dirty
        self.title_label.setText('Sac Açınımı' + (' · kaydedilmemiş değişiklik' if dirty else ''))

    def add_to_project(self):
        if not self.is_current():
            self.set_status('Projeye eklemek için güncel bir sonuç gerekli.', True); return
        request = dict(self.result_request,request_id=uuid.uuid4().hex)
        material = next((m['title'] for m in self.materials if m['id'] == self.material.currentData()), '—')
        code = f'P{len(self.project_parts) + 1:03d}'
        self.project_parts.append(dict(code=code, name=self.shape_title.text(), request=request, revision=1, material=material,
                                       quantity=1, status=STATES[self.state][0]))
        self.refresh_project(); self.mark_dirty(); self.result_tabs.setCurrentIndex(2)

    def duplicate_part(self):
        row = self._project_row()
        if row is None:
            return
        part = dict(self.project_parts[row]); part['code'] = f'P{len(self.project_parts) + 1:03d}'; part['revision'] = 1
        from copy import deepcopy
        part['request']=dict(deepcopy(part['request']),request_id=uuid.uuid4().hex)
        self.project_parts.append(part); self.refresh_project(); self.mark_dirty()

    def remove_part(self):
        row = self._project_row()
        if row is not None:
            del self.project_parts[row]; self.refresh_project(); self.mark_dirty()

    def _project_row(self):
        rows = self.project_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def refresh_project(self):
        rows = []
        for p in self.project_parts:
            r = p['request']
            thickness = fmt(r.get('thickness'), 3, r.get('input_units', 'mm')) if r.get('thickness') else 'verilmedi'
            rows.append((p['code'], p['name'], f'{r["shape_id"]} / {r["variant_id"]}', p['revision'], thickness, p['material'],
                         p.get('quantity', 1), p['status']))
        _fill(self.project_table, rows)
        self.refresh_actions()

    def project_row_selected(self):
        row = self._project_row()
        if row is None:
            return
        part = self.project_parts[row]
        self.part_quantity.blockSignals(True); self.part_quantity.setValue(part.get('quantity', 1)); self.part_quantity.blockSignals(False)
        self.load_request(part['request'])

    def quantity_changed(self, value):
        row = self._project_row()
        if row is not None and self.project_parts[row].get('quantity') != value:
            self.project_parts[row]['quantity'] = value; self.mark_dirty()
            self.project_table.item(row, 6).setText(str(value))

    def load_request(self, request):
        """Edit a project part: same shape/variant/unit/values; results are recalculated."""
        self.unit.blockSignals(True); self.unit.setCurrentIndex(max(self.unit.findData(request['input_units']), 0)); self.unit.blockSignals(False)
        self._unit = request['input_units']
        self.choose_shape(request['shape_id'], request['variant_id'], keep=False)
        self.apply_model_options(request.get('model_options') or {}, request['input_units'])
        self.development_options = dict(request.get('development_options') or {})
        self.forming.set_options(request.get('forming_options') or {})
        for key, value in request['parameters'].items():
            if key in self.fields:
                kind = self.fields[key]['kind']
                self.values[key] = to_mm(value, self._unit) if kind == 'length' else value
                self.fields[key]['edit'].setText(self.display_value(key, self.values[key]))
        joint = request.get('joint_options') or {}
        for key, value, length in (('thickness', request.get('thickness'), True), ('joint', joint.get('overlap',0.), True),
                                   ('seam_angle', (request.get('seam_options') or {}).get('start_angle_deg',0.), False),
                                   ('split_count', (request.get('split_options') or {}).get('count',1), False),
                                   ('price', (request.get('material') or {}).get('unit_price'), False)):
            self.values[key] = to_mm(value, self._unit) if length and value is not None else value
            self.fields[key]['edit'].setText(self.display_value(key, self.values[key]))
        for key,info in self.fields.items():
            self.errors.pop(key,None);self.applied_text[key]=info['edit'].text();self.show_field_error(key,None)
        for key, info in self.fields.items():
            if info['label'] is not None:
                info['label'].setText(self.caption(key))
        for box, value in ((self.reference, request.get('dimension_reference')), (self.joint_kind, joint.get('kind'))):
            index = box.findData(value)
            if index >= 0:
                box.blockSignals(True); box.setCurrentIndex(index); box.blockSignals(False)
        self.reference_sketch.set_reference(self.reference.currentData()); self.joint_changed(recalculate=False)
        material_data = dict(request.get('material') or {})
        material = material_data.get('name','')
        self.material.blockSignals(True)
        self.restore_material_caption()
        if self.material.findData(material)<0:
            self.materials.append(dict(id=material,title=material,density_kg_m3=material_data.get('density_kg_m3')))
            self.material.addItem(material,material)
        self.material.setCurrentIndex(self.material.findData(material))
        self.material.setItemText(self.material.currentIndex(),self.material_caption(
            dict(title=material or 'Malzeme seçilmedi',density_kg_m3=material_data.get('density_kg_m3'))))
        self.material.blockSignals(False)
        self.loaded_material = material_data
        self.price_unit = material_data.get('price_unit','kg');self.price_currency = material_data.get('currency','')
        self.update_price_caption()
        self.sync_inline()
        self.input_changed()

    # ---- files: projects, outputs, nesting (all produced by the service) ----------------
    def _start_file_job(self, title, operation, done):
        if not self.can_start():
            return
        self.quiet_cancel_on_close = False            # a file being written is worth a confirmation
        self.file_done = done
        self.set_status(title + '…')
        def run(events, stop):
            events.put(('unfold_files', operation(stop)))
        self.jobs.start(self, run)

    def files_finished(self, outcome):
        self.quiet_cancel_on_close = True
        done, self.file_done = getattr(self, 'file_done', None), None
        if done is not None:
            done(outcome)

    def _report_files(self, outcome, what):
        files = outcome.get('files', [])
        errors = [e['message'] for e in outcome.get('errors', [])]
        names = ', '.join(Path(f['path']).name for f in files[:6]) + (' …' if len(files) > 6 else '')
        if outcome.get('status') == 'complete':
            self.last_output = files[0]['path'] if files else None
            self.set_status(f'{what} oluşturuldu: {names}')
        elif outcome.get('status') == 'partial':
            self.set_status(f'{what} kısmen oluşturuldu ({names}); hatalar: ' + '; '.join(errors), tone='warning')
        else:
            self.set_status(f'{what} oluşturulamadı: ' + ('; '.join(errors) or 'bilinmeyen hata'), True)
        self.messages.setPlainText('\n'.join([f'✔ {f["path"]}' for f in files] + [f'✖ {e}' for e in errors]) or 'Çıktı yok.')

    def export_current(self, kind):
        if not self.is_current():
            self.set_status('Çıktı için güncel bir sonuç gerekli.', True); return
        from core.unfolding.exporting import safe_name
        name = safe_name(self.project_name.text().strip() or 'acinim')
        suffix = {'step': 'step', 'zip': 'zip'}.get(kind, kind)
        path, _ = QFileDialog.getSaveFileName(self, 'Çıktıyı kaydet', f'{name}_{safe_name(self.shape_id)}.{suffix}', EXPORT_FILTERS[kind])
        if not path:
            return
        result, service = self.result, self.service
        options = dict(path=path, format=kind, project_name=self.project_name.text().strip(),
                       development=self.export_development.currentData(),
                       include_step='step' in result['capabilities'].get('exports', ()))
        self._start_file_job('Çıktı hazırlanıyor', lambda stop: service.export(result, options, cancel_token=stop),
                             lambda outcome: self._report_files(outcome, EXPORT_FILTERS[kind].split()[0]))

    def project_object(self):
        from dataclasses import replace
        return replace(self.service.project(self.project_parts, self.project_name.text().strip()),**self.project_metadata)

    def save_project(self):
        if not self.project_parts:
            self.set_status('Kaydetmek için önce "Projeye ekle" ile parça ekleyin.', True); return
        from core.unfolding.exporting import safe_name
        path, _ = QFileDialog.getSaveFileName(self, 'Projeyi kaydet', f'{safe_name(self.project_name.text().strip() or "proje")}.gokunfold.json',
                                              'Sac açınımı projesi (*.json)')
        if not path:
            return
        try:
            self.service.save_project(self.project_object(), path)
        except (OSError, ValueError) as error:
            self.set_status(f'Proje kaydedilemedi: {error}', True); return
        self.mark_dirty(False); self.set_status(f'Proje kaydedildi: {Path(path).name}')

    def open_project(self):
        if self.dirty and self.project_parts:
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(self, 'Kaydedilmemiş değişiklik', 'Proje değişiklikleri kaydedilmedi. Yine de başka proje açılsın mı?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        path, _ = QFileDialog.getOpenFileName(self, 'Proje aç', '', 'Sac açınımı projesi (*.json)')
        if not path:
            return
        try:
            project = self.service.load_project(path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.set_status(f'Proje açılamadı: {error}', True); return
        self.project_metadata=dict(code=project.code,revision=project.revision,quantity=project.quantity)
        self.project_parts = [dict(code=item.code, name=item.code, request=self.service.page_request(item.request), revision=1,
                                   quantity=item.quantity, material=item.request.material.name or '—', status='Yeniden hesaplanacak')
                              for item in project.items]
        self.project_name.setText(project.name); self.refresh_project(); self.mark_dirty(False)
        note = ' Proje eski motor sürümüyle kaydedilmiş; sonuçlar yeniden hesaplanıyor.' if project.needs_recalculation else ''
        if self.project_parts:
            self.project_table.selectRow(0)            # loads the first part into the form and recalculates
        self.result_tabs.setCurrentIndex(2)
        self.set_status(f'Proje açıldı: {Path(path).name} · {len(self.project_parts)} parça.' + note)

    def export_project_zip(self):
        if not self.project_parts:
            return
        from core.unfolding.exporting import safe_name
        path, _ = QFileDialog.getSaveFileName(self, "Projeyi ZIP'e aktar", f'{safe_name(self.project_name.text().strip() or "proje")}.zip', 'ZIP (*.zip)')
        if not path:
            return
        project, service = self.project_object(), self.service
        self._start_file_job('Proje çıktıları hazırlanıyor', lambda stop: service.export_project(project, path, cancel_token=stop),
                             lambda outcome: self._report_files(outcome, 'Proje ZIP'))

    def send_to_nesting(self):
        """Transfer the current development to the Nesting project (contour, holes, thickness, material, quantity)."""
        if not self.is_current():
            self.set_status('Nesting için güncel bir sonuç gerekli.', True); return
        nesting = self.context.pages['nesting']
        materials = list(nesting.project.materials)
        if not materials:
            self.set_status('Nesting projesinde malzeme yok; önce Nesting modülünde malzeme tanımlayın.', True); return
        from PySide6.QtWidgets import QInputDialog
        titles = [f'{m.name} · {m.density:g} kg/m³' for m in materials]
        guess = next((i for i, m in enumerate(materials) if m.name.casefold() == (self.material.currentData() or '').casefold()), 0)
        choice, ok = QInputDialog.getItem(self, "Nesting'e gönder", 'Nesting projesindeki malzeme:', titles, guess, False)
        if not ok:
            return
        material = materials[titles.index(choice)]
        try:
            from dataclasses import replace as dc_replace
            parts = [dc_replace(part, material=material.id) for part in self.service.nesting_parts(self.result)]
        except (ValueError, ImportError) as error:
            self.set_status(f"Nesting'e aktarılamadı: {error}", True); return
        existing = {p.id for p in nesting.project.parts}
        fresh = [p for p in parts if p.id not in existing]
        if not fresh:
            self.set_status('Bu sonuç Nesting projesinde zaten var.', tone='warning'); return
        nesting.project.parts.extend(fresh); nesting.invalidate(); nesting.refresh()
        count = sum(p.quantity for p in fresh)
        self.set_status(f"Nesting'e aktarıldı: {len(fresh)} parça tipi, {count} adet · {material.name} · "
                        f"{fmt(fresh[0].thickness, 3)} mm.")

    # ---- page hooks --------------------------------------------------------------------
    def set_busy(self, busy):
        super().set_busy(busy)
        self.refresh_actions()

    def theme_changed(self):
        appearance = self.context.appearance
        for view in (self.flat_view, self.sketch, self.reference_sketch):
            view.appearance = appearance
        self.flat_view.set_appearance(appearance); self.drawing_view.set_appearance(appearance)
        self.sketch.update(); self.reference_sketch.update()
        self.mesh_view.set_background(COLORS[appearance]['canvas'])
        self.banner.setStyleSheet(f'color: {COLORS[appearance]["warning"]}; font-weight: 600;')
        self.fill_shapes(); self.set_state(self.state)
