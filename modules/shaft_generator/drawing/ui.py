"""'Teknik resim ve toleranslar' panel of the parametric shaft page.

All requirements are stored on ``project.drawing`` and bound to stable stage /
operation ids. Nothing is filled in automatically: a tolerance, Ra value,
datum or frame exists only after the user adds it here.
"""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QVBoxLayout, QWidget)

from gui_qt.components import AdaptiveRow, Disclosure, NumberSpinBox, button, label, pane, separator
from modules.iso_fits import rules as iso
from .models import (CHARACTERISTICS, DATUM_LABELS, LAYS, SHEET_SIZES, Datum, DrawingSettings, FinishSpec,
                     GeometricTolerance, ToleranceSpec)
from .planner import plan as build_plan, summary
from .targets import dimension_targets, surface_targets
from .tolerances import resolve

TOLERANCE_TITLES = (('none', 'Tolerans yok'), ('symmetric', 'Simetrik ±'), ('bilateral', 'Çift yönlü (üst / alt)'),
                    ('limit', 'Limit ölçü'), ('iso_fit', 'ISO 286 geçme'))
PROCESS_TITLES = (('removal_required', 'Talaş kaldırma gerekli'), ('removal_prohibited', 'Talaş kaldırma yasak'),
                  ('basic', 'Genel yüzey sembolü'))
RA_VALUES = ('0,4', '0,8', '1,6', '3,2', '6,3', '12,5')
SCALES = (('auto', 'Otomatik (ISO 5455)'), ((2, 1), '2:1'), ((1, 1), '1:1'), ((1, 2), '1:2'), ((1, 5), '1:5'), ((1, 10), '1:10'))


def _float(text):
    try:
        return float(str(text).replace(',', '.'))
    except ValueError:
        return None


class DrawingPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self._loading = False
        body = QVBoxLayout(self); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(8)
        self.enabled = QCheckBox('Otomatik teknik resim oluştur')
        self.enabled.setToolTip('SLDPRT oluştur ve kaydet komutundan sonra aynı SOLIDWORKS oturumunda yeni bir .SLDDRW hazırlanır.')
        body.addWidget(self.enabled)
        body.addWidget(label('Yeni teknik resim kayıtlı SLDPRT dosyasına bağlanır. Ölçüler referans ölçüdür; '
                             'parçanın sürücü ölçüleri değiştirilmez.', 'muted'))

        # --- sheet ------------------------------------------------------
        sheet, sheet_box = pane('Sayfa ve görünüşler')
        form = QFormLayout(); form.setContentsMargins(0, 0, 0, 0)
        self.template = QLineEdit(); self.template.setPlaceholderText('SOLIDWORKS varsayılan şablonu')
        self.template.setClearButtonEnabled(True)
        form.addRow('Şablon (.drwdot)', AdaptiveRow(self.template, button('Seç…', lambda: self.pick(self.template, 'Teknik resim şablonu (*.drwdot)')), stretch=0))
        self.sheet_format = QLineEdit(); self.sheet_format.setPlaceholderText('Şablondaki antet kullanılır')
        self.sheet_format.setClearButtonEnabled(True)
        form.addRow('Sayfa formatı (.slddrt)', AdaptiveRow(self.sheet_format, button('Seç…', lambda: self.pick(self.sheet_format, 'Sayfa formatı (*.slddrt)')), stretch=0))
        self.size = QComboBox(); self.size.addItem('Otomatik', 'auto')
        for name in SHEET_SIZES: self.size.addItem(name, name)
        form.addRow('Sayfa boyutu', self.size)
        self.projection = QComboBox(); self.projection.addItem('ISO birinci açı (E)', 'first'); self.projection.addItem('Üçüncü açı (A)', 'third')
        form.addRow('İzdüşüm', self.projection)
        self.scale = QComboBox()
        for value, title in SCALES: self.scale.addItem(title, value)
        form.addRow('Ölçek', self.scale)
        self.scheme = QComboBox()
        for value, title in (('baseline', 'Ortak referans (sol uç)'), ('chain', 'Zincir'), ('mixed', 'Karma (toplam + zincir)')):
            self.scheme.addItem(title, value)
        form.addRow('Boy ölçülendirme', self.scheme)
        sheet_box.addLayout(form)
        self.total_reference = QCheckBox('Toplam boyu göster (zincirde referans ölçü)')
        self.isometric = QCheckBox('İzometrik görünüş'); self.detail = QCheckBox('Küçük kanallar için detay görünüşü')
        self.section = QCheckBox('Kama kanalı için kesit'); self.centerlines = QCheckBox('Merkez çizgileri')
        for box in (self.total_reference, self.isometric, self.detail, self.section, self.centerlines):
            sheet_box.addWidget(box)
        body.addWidget(sheet)

        # --- dimension tolerances ----------------------------------------
        tolerances, tol_box = pane('Ölçü toleransları', rule=True)
        self.dimension = QComboBox(); self.dimension.setAccessibleName('Toleranslanacak ölçü')
        tol_box.addWidget(self.dimension)
        tol_form = QFormLayout(); tol_form.setContentsMargins(0, 0, 0, 0)
        self.tol_kind = QComboBox()
        for value, title in TOLERANCE_TITLES: self.tol_kind.addItem(title, value)
        tol_form.addRow('Tolerans türü', self.tol_kind)
        self.fit = QComboBox(); tol_form.addRow('ISO sınıfı', self.fit)
        self.fit_display = QComboBox()
        for value, title in (('class', 'Yalnız sınıf (h6)'), ('deviations', 'Yalnız sapmalar'), ('class_and_deviations', 'Sınıf ve sapmalar')):
            self.fit_display.addItem(title, value)
        tol_form.addRow('Gösterim', self.fit_display)
        self.upper = NumberSpinBox(4); self.upper.setRange(-100, 100); tol_form.addRow('Üst sapma · mm', self.upper)
        self.lower = NumberSpinBox(4); self.lower.setRange(-100, 100); tol_form.addRow('Alt sapma · mm', self.lower)
        tol_box.addLayout(tol_form)
        self.tol_preview = label('', 'muted'); tol_box.addWidget(self.tol_preview)
        body.addWidget(tolerances)

        # --- surface texture ---------------------------------------------
        finishes, fin_box = pane('Yüzey pürüzlülüğü (ISO 21920-1 · Ra)', rule=True)
        self.surface = QComboBox(); self.surface.setAccessibleName('Yüzey'); fin_box.addWidget(self.surface)
        fin_form = QFormLayout(); fin_form.setContentsMargins(0, 0, 0, 0)
        self.finish_on = QCheckBox('Bu yüzeye gereksinim ata'); fin_form.addRow(self.finish_on)
        self.ra = QComboBox(); self.ra.setEditable(True); self.ra.addItems(RA_VALUES); fin_form.addRow('Ra · µm', self.ra)
        self.process = QComboBox()
        for value, title in PROCESS_TITLES: self.process.addItem(title, value)
        fin_form.addRow('Sembol', self.process)
        self.method = QLineEdit(); self.method.setPlaceholderText('isteğe bağlı, ör. taşlama'); fin_form.addRow('İşleme yöntemi', self.method)
        self.lay = QComboBox()
        for value in LAYS: self.lay.addItem(value or 'Belirtilmemiş', value)
        fin_form.addRow('İz yönü', self.lay)
        fin_box.addLayout(fin_form)
        bulk = QHBoxLayout()
        self.bulk_ra = QComboBox(); self.bulk_ra.setEditable(True); self.bulk_ra.addItems(RA_VALUES)
        bulk.addWidget(label('Tüm silindirlere', 'muted')); bulk.addWidget(self.bulk_ra)
        self.bulk_apply = button('Uygula', self.apply_bulk, flat=True); self.bulk_clear = button('Kaldır', self.clear_bulk, flat=True)
        bulk.addWidget(self.bulk_apply); bulk.addWidget(self.bulk_clear); fin_box.addLayout(bulk)
        self.bulk_info = label('', 'muted'); fin_box.addWidget(self.bulk_info)
        body.addWidget(finishes)

        # --- datums and geometric tolerances ------------------------------
        gdt, gdt_box = pane('Datum ve geometrik toleranslar (ISO 1101 / ISO 5459)', rule=True)
        datum_row = QHBoxLayout()
        self.datum_label = QComboBox(); self.datum_label.addItems(DATUM_LABELS)
        self.datum_surface = QComboBox(); self.datum_surface.setMinimumContentsLength(10)
        datum_row.addWidget(self.datum_label); datum_row.addWidget(self.datum_surface, 1)
        datum_row.addWidget(button('Datum ekle', self.add_datum, flat=True)); gdt_box.addLayout(datum_row)
        frame_form = QFormLayout(); frame_form.setContentsMargins(0, 0, 0, 0)
        self.characteristic = QComboBox()
        for key, (title, _) in CHARACTERISTICS.items(): self.characteristic.addItem(title, key)
        frame_form.addRow('Tolerans', self.characteristic)
        self.frame_value = NumberSpinBox(4); self.frame_value.setRange(.0001, 10); self.frame_value.setValue(.02)
        frame_form.addRow('Değer · mm', self.frame_value)
        self.frame_surface = QComboBox(); frame_form.addRow('Hedef yüzey', self.frame_surface)
        self.frame_datums = QLineEdit(); self.frame_datums.setPlaceholderText('ör. A veya A B')
        frame_form.addRow('Datumlar', self.frame_datums)
        gdt_box.addLayout(frame_form)
        gdt_box.addWidget(button('Geometrik tolerans ekle', self.add_frame, flat=True), alignment=Qt.AlignLeft)
        self.gdt_list = QListWidget(); self.gdt_list.setMaximumHeight(110); gdt_box.addWidget(self.gdt_list)
        gdt_box.addWidget(button('Seçileni kaldır', self.remove_gdt, flat=True), alignment=Qt.AlignLeft)
        body.addWidget(gdt)

        # --- title block and outputs --------------------------------------
        title_widget = QWidget(); title_form = QFormLayout(title_widget); title_form.setContentsMargins(0, 0, 0, 0)
        self.title_fields = {}
        for key, caption in (('drawing_number', 'Resim no'), ('revision', 'Revizyon'), ('material', 'Malzeme (boş: parçadan)'),
                             ('general_tolerance', 'Genel tolerans'), ('drawn_by', 'Çizen'), ('notes', 'Açıklama')):
            edit = QLineEdit(); edit.setClearButtonEnabled(True); self.title_fields[key] = edit; title_form.addRow(caption, edit)
        body.addWidget(Disclosure('Antet bilgileri', title_widget))
        outputs = QHBoxLayout(); self.pdf = QCheckBox('PDF'); self.dwg = QCheckBox('DWG')
        outputs.addWidget(label('Ek çıktılar', 'muted')); outputs.addWidget(self.pdf); outputs.addWidget(self.dwg); outputs.addStretch()
        body.addLayout(outputs)

        body.addWidget(separator())
        self.plan_summary = label('', 'section'); body.addWidget(self.plan_summary)
        self.plan_issues = label('', 'muted'); self.plan_issues.setTextInteractionFlags(Qt.TextSelectableByMouse); body.addWidget(self.plan_issues)
        self.from_part = button('Kayıtlı SLDPRT’den teknik resim…', self.page.drawing_from_part)
        self.from_part.setToolTip('Daha önce GOKWORKS ile oluşturulup kaydedilmiş mil parçası için yeni .SLDDRW oluştur')
        body.addWidget(self.from_part, alignment=Qt.AlignLeft)
        body.addStretch()
        self.connect_signals()

    # ---- state ------------------------------------------------------------
    @property
    def settings(self):
        if self.page.project.drawing is None:
            self.page.project.drawing = DrawingSettings()
        return self.page.project.drawing

    def connect_signals(self):
        for widget in (self.enabled, self.total_reference, self.isometric, self.detail, self.section, self.centerlines, self.pdf, self.dwg):
            widget.toggled.connect(self.store)
        for widget in (self.size, self.projection, self.scale, self.scheme):
            widget.currentIndexChanged.connect(self.store)
        for widget in (self.template, self.sheet_format, *self.title_fields.values()):
            widget.editingFinished.connect(self.store)
        self.dimension.currentIndexChanged.connect(self.load_tolerance)
        for widget in (self.tol_kind, self.fit, self.fit_display):
            widget.currentIndexChanged.connect(self.store_tolerance)
        for widget in (self.upper, self.lower):
            widget.valueChanged.connect(self.store_tolerance)
        self.surface.currentIndexChanged.connect(self.load_finish)
        self.finish_on.toggled.connect(self.store_finish)
        for widget in (self.process, self.lay):
            widget.currentIndexChanged.connect(self.store_finish)
        self.ra.currentTextChanged.connect(self.store_finish)
        self.method.editingFinished.connect(self.store_finish)

    def pick(self, target, pattern):
        path, _ = QFileDialog.getOpenFileName(self, 'Dosya seç', target.text(), pattern)
        if path:
            target.setText(path); self.store()

    def populate(self):
        """Refill from the project (open, stage edits, deletions)."""
        self._loading = True
        try:
            s = self.page.project.drawing or DrawingSettings()
            blockers = [QSignalBlocker(w) for w in self.findChildren(QWidget)]
            self.enabled.setChecked(s.enabled); self.template.setText(s.template); self.sheet_format.setText(s.sheet_format)
            self.size.setCurrentIndex(max(0, self.size.findData(s.sheet_size)))
            self.projection.setCurrentIndex(max(0, self.projection.findData(s.projection)))
            scale = 'auto' if s.scale_mode == 'auto' else tuple(s.scale)
            self.scale.setCurrentIndex(max(0, next((i for i in range(self.scale.count()) if self.scale.itemData(i) == scale), 0)))
            self.scheme.setCurrentIndex(max(0, self.scheme.findData(s.scheme)))
            for box, value in ((self.total_reference, s.total_length_reference), (self.isometric, s.isometric), (self.detail, s.detail_views),
                               (self.section, s.keyway_section), (self.centerlines, s.centerlines), (self.pdf, s.pdf), (self.dwg, s.dwg)):
                box.setChecked(value)
            for key, edit in self.title_fields.items():
                edit.setText(s.title.get(key, ''))
            current = self.dimension.currentData()
            self.dimension.clear()
            for key, title, nominal, feature in dimension_targets(self.page.project):
                self.dimension.addItem(title, (key, nominal, feature))
            index = next((i for i in range(self.dimension.count()) if current and self.dimension.itemData(i)[0] == current[0]), 0)
            self.dimension.setCurrentIndex(index)
            surface_rows = surface_targets(self.page.project)
            for combo in (self.surface, self.datum_surface, self.frame_surface):
                selected = combo.currentData(); combo.clear()
                for key, title, _ in surface_rows:
                    combo.addItem(title, key)
                combo.setCurrentIndex(max(0, combo.findData(selected)))
            del blockers
        finally:
            self._loading = False
        self.load_tolerance(); self.load_finish(); self.refresh_lists(); self.refresh_plan()

    def store(self, *args):
        if self._loading:
            return
        s = self.settings
        s.enabled = self.enabled.isChecked(); s.template = self.template.text().strip(); s.sheet_format = self.sheet_format.text().strip()
        s.sheet_size = self.size.currentData(); s.projection = self.projection.currentData(); s.scheme = self.scheme.currentData()
        scale = self.scale.currentData()
        s.scale_mode, s.scale = ('auto', [1, 1]) if scale == 'auto' else ('fixed', list(scale))
        s.total_length_reference = self.total_reference.isChecked(); s.isometric = self.isometric.isChecked()
        s.detail_views = self.detail.isChecked(); s.keyway_section = self.section.isChecked(); s.centerlines = self.centerlines.isChecked()
        s.pdf = self.pdf.isChecked(); s.dwg = self.dwg.isChecked()
        s.title = {k: e.text().strip() for k, e in self.title_fields.items() if e.text().strip()}
        self.changed()

    def changed(self):
        self.refresh_plan()
        self.page.drawing_changed()

    # ---- tolerances ---------------------------------------------------------
    def load_tolerance(self, *args):
        data = self.dimension.currentData()
        if not data:
            return
        key, nominal, feature = data
        self._loading = True
        try:
            spec = (self.page.project.drawing.tolerances.get(key) if self.page.project.drawing else None) or ToleranceSpec()
            with QSignalBlocker(self.tol_kind), QSignalBlocker(self.fit), QSignalBlocker(self.fit_display), \
                    QSignalBlocker(self.upper), QSignalBlocker(self.lower):
                self.tol_kind.setCurrentIndex(self.tol_kind.findData(spec.kind))
                self.fit.clear()
                if feature:
                    self.fit.addItems(iso.classes(feature))
                self.fit.setCurrentText(spec.fit)
                self.fit_display.setCurrentIndex(self.fit_display.findData(spec.display))
                self.upper.setValue(spec.upper); self.lower.setValue(spec.lower)
        finally:
            self._loading = False
        self.update_tolerance_controls()

    def update_tolerance_controls(self):
        data = self.dimension.currentData() or ('', 0, '')
        kind = self.tol_kind.currentData()
        iso_ok = bool(data[2])
        self.tol_kind.model().item(self.tol_kind.findData('iso_fit')).setEnabled(iso_ok)
        for widget in (self.fit, self.fit_display):
            widget.setEnabled(kind == 'iso_fit')
        self.upper.setEnabled(kind in ('symmetric', 'bilateral', 'limit'))
        self.lower.setEnabled(kind in ('bilateral', 'limit'))
        self.tol_preview.setText(self.tolerance_text())

    def tolerance_text(self):
        data = self.dimension.currentData()
        if not data:
            return ''
        key, nominal, feature = data
        spec = self.current_spec()
        if spec.kind == 'none':
            return 'Tolerans tanımlanmadı; ölçü nominal gösterilir.'
        errors = spec.errors('Tolerans')
        if errors:
            return errors[0]
        try:
            result = resolve(spec, nominal, feature)
        except ValueError as error:
            return str(error)
        from .tolerances import _fmt
        deviations = f'üst {_fmt(result.upper, places=4)} · alt {_fmt(result.lower, places=4)} mm'
        return f'Gösterim: {result.text}  ·  {deviations}'

    def current_spec(self):
        kind = self.tol_kind.currentData()
        upper, lower = self.upper.value(), self.lower.value()
        return ToleranceSpec(kind=kind, upper=upper, lower=(-upper if kind == 'symmetric' else lower),
                             fit=self.fit.currentText() if kind == 'iso_fit' else '', display=self.fit_display.currentData())

    def store_tolerance(self, *args):
        if self._loading:
            return
        data = self.dimension.currentData()
        if not data:
            return
        spec = self.current_spec()
        if spec.kind == 'none':
            self.settings.tolerances.pop(data[0], None)
        else:
            self.settings.tolerances[data[0]] = spec
        self.update_tolerance_controls()
        self.changed()

    # ---- surface texture --------------------------------------------------
    def load_finish(self, *args):
        key = self.surface.currentData()
        drawing = self.page.project.drawing
        spec = drawing.finishes.get(key) if drawing and key else None
        self._loading = True
        try:
            with QSignalBlocker(self.finish_on), QSignalBlocker(self.ra), QSignalBlocker(self.process), \
                    QSignalBlocker(self.method), QSignalBlocker(self.lay):
                self.finish_on.setChecked(spec is not None)
                shown = spec or FinishSpec()
                self.ra.setCurrentText(f'{shown.ra:g}'.replace('.', ','))
                self.process.setCurrentIndex(self.process.findData(shown.process))
                self.method.setText(shown.method); self.lay.setCurrentIndex(self.lay.findData(shown.lay))
        finally:
            self._loading = False
        for widget in (self.ra, self.process, self.method, self.lay):
            widget.setEnabled(spec is not None)
        self.refresh_bulk_info()

    def store_finish(self, *args):
        if self._loading:
            return
        key = self.surface.currentData()
        if not key:
            return
        for widget in (self.ra, self.process, self.method, self.lay):
            widget.setEnabled(self.finish_on.isChecked())
        if not self.finish_on.isChecked():
            self.settings.finishes.pop(key, None)
        else:
            ra = _float(self.ra.currentText())
            spec = FinishSpec(ra=ra if ra is not None else float('nan'), process=self.process.currentData(),
                              method=self.method.text().strip(), lay=self.lay.currentData())
            self.settings.finishes[key] = spec
        self.changed()

    def apply_bulk(self):
        ra = _float(self.bulk_ra.currentText())
        spec = FinishSpec(ra=ra if ra is not None else float('nan'))
        errors = spec.errors('Toplu Ra')
        if errors:
            self.page.set_status(errors[0], True); return
        self.settings.default_finish = spec
        self.refresh_bulk_info(); self.changed()

    def clear_bulk(self):
        self.settings.default_finish = None
        self.refresh_bulk_info(); self.changed()

    def refresh_bulk_info(self):
        drawing = self.page.project.drawing
        default = drawing.default_finish if drawing else None
        self.bulk_info.setText('Toplu değer yok · yalnız seçilen yüzeylere işaret konur.' if default is None else
                               f'Tüm silindirik dış yüzeylere Ra {default.ra:g}; yukarıdaki yüzeye özel değer önceliklidir.'.replace('.', ','))

    # ---- datums and frames ----------------------------------------------------
    def add_datum(self):
        label_text, target = self.datum_label.currentText(), self.datum_surface.currentData()
        if not target:
            return
        if any(d.label == label_text for d in self.settings.datums):
            self.page.set_status(f'Datum {label_text} zaten tanımlı.', True); return
        self.settings.datums.append(Datum(label_text, target))
        self.refresh_lists(); self.changed()

    def add_frame(self):
        datums = self.frame_datums.text().upper().split()
        frame = GeometricTolerance(self.characteristic.currentData(), self.frame_value.value(), self.frame_surface.currentData(),
                                   datums, id=f'g{len(self.settings.geometric)+1}')
        test = DrawingSettings(datums=list(self.settings.datums), geometric=[frame])
        errors = [e for e in test.basic_errors() if 'Geometrik' in e or ':' in e]
        if errors:
            self.page.set_status(errors[0], True); return
        self.settings.geometric.append(frame)
        self.refresh_lists(); self.changed()

    def remove_gdt(self):
        item = self.gdt_list.currentItem()
        if item is None:
            return
        kind, index = item.data(Qt.UserRole)
        if kind == 'datum':
            removed = self.settings.datums.pop(index)
            used = [g for g in self.settings.geometric if removed.label in g.datums]
            if used:
                self.page.set_status(f'Datum {removed.label} {len(used)} geometrik toleransta kullanılıyor; önce onları kaldırın.', True)
                self.settings.datums.insert(index, removed); return
        else:
            self.settings.geometric.pop(index)
        self.refresh_lists(); self.changed()

    def refresh_lists(self):
        self.gdt_list.clear()
        drawing = self.page.project.drawing
        if drawing is None:
            return
        titles = {key: title for key, title, _ in surface_targets(self.page.project)}
        for i, datum in enumerate(drawing.datums):
            item = QListWidgetItem(f'Datum {datum.label} · {titles.get(datum.target, "kaldırılmış yüzey")}')
            item.setData(Qt.UserRole, ('datum', i)); self.gdt_list.addItem(item)
        for i, frame in enumerate(drawing.geometric):
            text = f'{CHARACTERISTICS[frame.characteristic][0]} {frame.value:g} {" ".join(frame.datums)} · {titles.get(frame.target, "kaldırılmış yüzey")}'
            item = QListWidgetItem(text.replace('.', ',')); item.setData(Qt.UserRole, ('frame', i)); self.gdt_list.addItem(item)

    # ---- plan feedback -----------------------------------------------------
    def refresh_plan(self):
        result = build_plan(self.page.project, self.page.project.drawing or DrawingSettings())
        self.last_plan = result
        self.plan_summary.setText(summary(result))
        lines = [f'Hata: {e}' for e in result['errors']] + [f'Uyarı: {w}' for w in result['warnings']]
        self.plan_issues.setText('\n'.join(lines) if lines else 'Plan hazır: bütün ölçü ve işaretler gerçek geometriye bağlanabilir.')
        self.plan_issues.setProperty('role', 'error' if result['errors'] else 'muted')
        self.plan_issues.style().unpolish(self.plan_issues); self.plan_issues.style().polish(self.plan_issues)
        return result
