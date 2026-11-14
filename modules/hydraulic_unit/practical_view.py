"""A single form for a novice's out-and-back cylinder calculation."""
from dataclasses import replace
import math

from PySide6.QtCore import Qt, QPoint, QRectF, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QSizePolicy,
                               QVBoxLayout, QWidget)

from gui_qt.components import Disclosure, button, label, scroll
from gui_qt.theme import COLORS
from .beginner import FORCE_FACTORS
from .beginner_view import CylinderDiagram, IssueRow, PLAIN_ISSUES, Responsive, ResultCard, panel, polish, show, text_number
from .core.validation import InputError
from .practical import PracticalInputs, TITLES, practical_project, practical_values
from .presentation import result_rows
from .schematic import UnitSchematic


class Reflow(QWidget):
    """Children in as many equal columns as fit (``min_width`` each), re-laid out on resize."""

    def __init__(self, min_width, spacing=10, max_columns=4, allowed=None):
        super().__init__(); self.min_width, self.max_columns = min_width, max_columns
        self.allowed = allowed or tuple(range(max_columns, 0, -1))   # e.g. (4, 2, 1): never a 3 + 1 layout
        self.grid = QGridLayout(self); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(spacing); self.grid.setVerticalSpacing(spacing)
        self.items = []; self.columns = 0

    def add(self, widget):
        self.items.append(widget); self.columns = 0; self.reflow()

    def reflow(self):
        fit = max(1, min(self.max_columns, len(self.items) or 1, self.width() // self.min_width if self.width() else 1))
        columns = next((n for n in self.allowed if n <= fit), 1)
        if columns == self.columns:
            return
        self.columns = columns
        for widget in self.items:
            self.grid.removeWidget(widget)
        for i, widget in enumerate(self.items):
            self.grid.addWidget(widget, i // columns, i % columns)
        for col in range(self.max_columns):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event); self.reflow()


class CycleStrip(QWidget):
    """İleri / uçta bekle / geri, sürelerine oranlı; toplam süre ve tekrar eden çevrim işareti."""

    def __init__(self, appearance):
        super().__init__(); self.appearance = appearance; self.parts = []
        self.setMinimumHeight(54); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName('Çevrim süreleri')

    def sizeHint(self):
        return QSize(400, 54)

    def set_parts(self, parts):
        """``parts``: (name, seconds or None) in order; None draws a hatched 'unknown' segment."""
        self.parts = parts
        known = [s for _, s in parts if s]
        total = sum(known)
        self.setAccessibleDescription(' → '.join(f'{n} {s:g} s' if s else f'{n} ?' for n, s in parts)
                                      + (f' · toplam {total:g} s' if known else ''))
        self.update()

    def paintEvent(self, event):
        c = COLORS[self.appearance]; p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        colours = {'İleri': QColor(c['accent']), 'Bekle': QColor(c['warning']), 'Geri': QColor(c['success'])}
        widths = [s if s and s > 0 else 0 for _, s in self.parts]
        total = sum(widths); bar = QRectF(0, 20, self.width(), 14)
        small = QFont(self.font()); small.setPixelSize(11)
        if not self.parts or total <= 0:
            p.setPen(Qt.NoPen); p.setBrush(QColor(c['input'])); p.drawRoundedRect(bar, 7, 7); p.end(); return
        x = 0.
        for (name, seconds), width in zip(self.parts, widths):
            if width <= 0:
                continue
            span = bar.width() * width / total; part = QRectF(x, bar.top(), span, bar.height())
            colour = colours.get(name, QColor(c['muted']))
            p.setPen(Qt.NoPen); p.setBrush(colour); p.drawRoundedRect(part.adjusted(1, 0, -1, 0), 4, 4)
            p.setFont(small); p.setPen(QColor(c['text']))
            text = f'{name} · {seconds:g} s'.replace('.', ',')
            if p.fontMetrics().horizontalAdvance(text) + 8 > span:
                text = f'{seconds:g} s'.replace('.', ',')
            p.drawText(QRectF(x, 0, span, 18), Qt.AlignHCenter | Qt.AlignBottom, text)
            x += span
        p.setPen(QColor(c['muted']))
        p.drawText(QRectF(0, 36, self.width(), 18), Qt.AlignRight | Qt.AlignVCenter,
                   f'toplam {total:g} s · başlangıca döner'.replace('.', ','))
        p.end()


class Metric(ResultCard):
    """Compact KPI tile: small caps title, large value, one-line note; accent bar shows the state."""

    def __init__(self, title):
        super().__init__(title)
        self.setProperty('metric', True)
        self.title.setProperty('role', 'muted'); self.title.setProperty('kicker', True)
        self.value.setProperty('metricValue', True); self.lines.hide()
        self.note.setWordWrap(True)
        # Tag on its own line under the value: the title keeps the full width.
        box = self.layout(); box.removeWidget(self.tag); self.tag.setParent(self)
        box.insertWidget(box.indexOf(self.value)+1, self.tag)
        self.setMinimumWidth(150)

    def fill(self, tag, value, lines, note, tip='', state=None):
        super().fill(tag, value, lines, note, tip, None)
        self.setProperty('state', state or ''); polish(self)


class PracticalView(QWidget):
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.inputs = {}; self.pending = False; self.ready = False
        self.allowed = False; self._force_unit = 'tonf'
        self.reveal_timer = QTimer(self); self.reveal_timer.setSingleShot(True)
        self.reveal_timer.timeout.connect(self.reveal_result)
        self.fresh = not owner.settings.get('hydraulic_unit_project')
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(8)
        head = QHBoxLayout(); head.setSpacing(12)
        words = QVBoxLayout(); words.setSpacing(1)
        words.addWidget(label('Ölçüleri girin. Hareketi tarif edin. Ünite ihtiyacını görün.', 'section'))
        words.addWidget(label('Tek silindir: mil dışarı çıkar, isterseniz uçta bekler ve aynı mesafeyi geri döner.', 'muted'))
        head.addLayout(words, 1)
        self.chip = label('Taslak', 'muted', wrap=False); self.chip.setProperty('chip', True)
        self.chip.setAccessibleName('Hesap durumu'); head.addWidget(self.chip, 0, Qt.AlignTop)
        outer.addLayout(head)
        body = QWidget(); box = QVBoxLayout(body); box.setContentsMargins(2, 2, 8, 4)
        self.existing, existing = panel()
        self.existing_note = label('', 'muted'); existing.addWidget(self.existing_note)
        actions = QHBoxLayout()
        actions.addWidget(button('Mevcut hareket planını aç', self.open_plan))
        self.new_button = button('Yeni basit çevrim oluştur', self.start_new)
        actions.addWidget(self.new_button); actions.addStretch(1); existing.addLayout(actions)
        box.addWidget(self.existing)
        split = Responsive(1040, 16)   # side by side from a 1366 px window (page ~1130 px)
        self.form = QWidget(); form = QVBoxLayout(self.form); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(12)
        self.form.setMinimumWidth(330)
        sizes, contents = panel(); contents.setSpacing(10)
        contents.addLayout(self.card_head('1', 'Silindirin ölçüleri', 'Etiketten veya teknik resimden; milimetre.'))
        grid = Reflow(170, 12, 3)
        for key, title, hint, example in (
                ('bore', 'Silindirin iç çapı', 'Etiketteki piston çapı (ØD); gövdenin dışı değil.', '63'),
                ('rod', 'Parlak milin çapı', 'Dışarı çıkan mil; kumpasla ölçülebilir.', '36'),
                ('stroke', 'Gideceği yol (strok)', 'Tamamen içeriden tamamen dışarıya.', '300')):
            grid.add(self.field(key, title, 'mm', hint, example))
        contents.addWidget(grid)
        self.diagram = CylinderDiagram(owner.context)
        contents.addWidget(Disclosure('Bu ölçüler silindirin neresinde?', self.diagram))
        form.addWidget(sizes)
        motions, contents = panel(); contents.setSpacing(10)
        top = self.card_head('2', 'Nasıl çalışsın?', 'İleri gider, isterseniz bekler, aynı yoldan döner.')
        self.force_unit = QComboBox(); self.force_unit.addItem('Ton-kuvvet', 'tonf'); self.force_unit.addItem('kN', 'kN')
        self.force_unit.setAccessibleName('Pratik hesap kuvvet birimi')
        self.force_unit.setToolTip('İtme kuvvetini hangi birimle biliyorsunuz?')
        top.addWidget(self.force_unit, 0, Qt.AlignTop); contents.addLayout(top)
        grid = Reflow(170, 12, 2)
        grid.add(self.field('force', 'İleri ne kadar kuvvet uygulasın?', 'tonf', 'Presin / silindirin itme kuvveti.', '3'))
        grid.add(self.field('extend_time', 'İleri kaç saniyede gitsin?', 's', 'Tam stroku tamamlama süresi.', '5'))
        grid.add(self.field('return_time', 'Geri kaç saniyede dönsün?', 's', 'Aynı yoldan başlangıca döner.', '5'))
        grid.add(self.field('hold_time', 'Uçta kaç saniye beklesin?', 's', 'Yoksa 0; beklerken itme sürer.', '0'))
        contents.addWidget(grid)
        self.strip = CycleStrip(owner.context.appearance); contents.addWidget(self.strip)
        extra = QWidget(); e = QVBoxLayout(extra); e.setContentsMargins(0, 4, 0, 0)
        e.addWidget(self.field('return_force', 'Geri dönüşte gereken çekme kuvveti', 'tonf',
                               'Yüksüz dönüş için 0. Dönüşte direnç varsa gereken kuvveti girin.', '0'))
        e.addWidget(label('Ton-kuvvet bir kuvvettir; yükün ton cinsinden kütlesiyle her mekanizmada aynı değildir. '
                          'Sürtünme, eğim ve mekanizma oranı gereken kuvveti değiştirir.', 'muted'))
        self.return_section = Disclosure('Geri dönüşte yük varsa / kuvvet birimi hakkında', extra)
        contents.addWidget(self.return_section)
        self.return_note = label('', 'muted'); contents.addWidget(self.return_note)
        self.auto_pump = QCheckBox('Pompayı bu harekete göre boyutlandır')
        self.auto_pump.setToolTip('Önerilen pompa hacmini projeye uygular. Basınç sınırı, verimler ve diğer teknik ayarlar korunur.')
        contents.addWidget(self.auto_pump)
        form.addWidget(motions)
        self.error = label('', 'error'); self.error.setTextFormat(Qt.PlainText); self.error.hide(); form.addWidget(self.error)
        self.calculate_button = button('Ünite ihtiyacını hesapla', self.calculate, primary=True)
        self.calculate_button.setMinimumHeight(38)
        self.draft_note = label('', 'muted'); form.addStretch(1)
        split.box.addWidget(self.form, 3)
        result, output = panel(); output.setSpacing(10)
        self.output_panel = result
        head = QHBoxLayout(); head.setSpacing(8)
        head.addWidget(label('Hangi ünite gerekir?', 'section'), 1)
        self.report_row = QWidget(); reports = QHBoxLayout(self.report_row); reports.setContentsMargins(0, 0, 0, 0); reports.setSpacing(6)
        self.pdf_button = button('PDF raporu…', owner.export_pdf)
        self.excel_button = button('Excel…', lambda: owner.export('excel'))
        self.cancel_pdf_button = button('Raporu durdur', owner.cancel_pdf, destructive=True); self.cancel_pdf_button.hide()
        reports.addWidget(self.pdf_button); reports.addWidget(self.excel_button); reports.addWidget(self.cancel_pdf_button)
        head.addWidget(self.report_row, 0, Qt.AlignTop); output.addLayout(head)
        self.state = label('Ölçüleri ve hareket sürelerini girip hesaplayın.', 'muted'); output.addWidget(self.state)
        self.cycle = label('', 'muted'); output.addWidget(self.cycle)
        self.metrics = Reflow(176, 10, 4, (4, 2, 1)); self.cards = {}
        for key, title in (('motor', 'ELEKTRİK MOTORU'), ('pump', 'YAĞ POMPASI'), ('pressure', 'ÇALIŞMA BASINCI'), ('tank', 'YAĞ TANKI')):
            card = Metric(title); self.metrics.add(card); self.cards[key] = card
        output.addWidget(self.metrics)
        self.issue_box = QVBoxLayout(); self.issue_box.setSpacing(6); output.addLayout(self.issue_box)
        output.addWidget(label('Ünite şeması', 'section'))
        output.addWidget(label('Elemana tıklayınca ölçüsü veya ayarı açılır. ✓ uygun · ! kontrol · ✕ kritik.', 'muted'))
        self.schematic = UnitSchematic(owner.context.appearance)
        self.schematic.nodeClicked.connect(self.open_node); output.addWidget(self.schematic)
        self.technical = label('', 'muted'); self.technical.setTextFormat(Qt.PlainText)
        output.addWidget(Disclosure('Basınç, soğutma ve diğer hesap ayrıntıları', self.technical))
        self.status = label('', 'muted'); self.status.setTextFormat(Qt.PlainText); output.addWidget(self.status)
        output.addWidget(button('Hareket planı ve tüm sonuçlar →', self.open_plan, flat=True))
        output.addStretch(1); split.box.addWidget(result, 5)
        box.addWidget(split); self.workspace = scroll(body); outer.addWidget(self.workspace, 1)
        footer = QHBoxLayout(); footer.setSpacing(16); footer.addWidget(self.draft_note,1)
        footer.addWidget(self.calculate_button); outer.addLayout(footer)
        for key in self.inputs:
            self.inputs[key].textEdited.connect(self.mark_pending)
            self.inputs[key].returnPressed.connect(self.calculate)
        self.auto_pump.toggled.connect(self.mark_pending)
        self.force_unit.currentIndexChanged.connect(self.change_force_unit)
        self.clear_result()

    def card_head(self, number, title, hint):
        row = QHBoxLayout(); row.setSpacing(10)
        badge = label(number, None, wrap=False); badge.setProperty('stepBadge', True); badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(26, 26); row.addWidget(badge, 0, Qt.AlignTop)
        words = QVBoxLayout(); words.setSpacing(0)
        words.addWidget(label(title, 'section')); words.addWidget(label(hint, 'muted')); row.addLayout(words, 1)
        return row

    def field(self, key, title, unit, hint, example):
        """Title (buddy of the input), the input with its unit inside one frame, and a short hint."""
        tile = QWidget(); box = QVBoxLayout(tile); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(4)
        heading = label(title); heading.setProperty('fieldTitle', True); box.addWidget(heading)
        frame = QFrame(); frame.setProperty('unitField', True)
        inner = QHBoxLayout(frame); inner.setContentsMargins(0, 0, 10, 0); inner.setSpacing(4)
        edit = QLineEdit(); edit.setMinimumHeight(34); edit.setMinimumWidth(70); edit.setFrame(False)
        edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter); edit.setPlaceholderText(example); edit.setAccessibleName(title)
        edit.setProperty('inUnitField', True)
        unit_label = label(unit, 'muted', wrap=False); edit._unit_label = unit_label
        inner.addWidget(edit, 1); inner.addWidget(unit_label)
        box.addWidget(frame)
        tip = label(hint, 'muted'); tip.setProperty('hint', True); box.addWidget(tip)
        heading.setBuddy(edit); self.inputs[key] = edit
        return tile

    def set_number(self, key, value):
        edit = self.inputs[key]; edit.setText(text_number(value)); edit._shown = (edit.text(), value)

    def number(self, key):
        edit = self.inputs[key]
        if getattr(edit, '_shown', (None,))[0] == edit.text():
            return edit._shown[1]
        try:
            value = float(edit.text().strip().replace(',', '.'))
            if not math.isfinite(value):raise ValueError
            return value
        except ValueError:
            raise InputError('practical.' + key, TITLES[key] + ': bir sayı girin; örneğin 63 veya 2,5.') from None

    def populate(self, project):
        values = practical_values(project)
        canonical = values is not None
        self.allowed = values is not None or (self.fresh and len(project.cylinders) == 1)
        self.existing.setVisible(not self.allowed)
        self.new_button.setVisible(len(project.cylinders) == 1)
        self.existing_note.setText('Bu projenin özel bir hareket planı var. Basit forma indirgenmedi; verileriniz korunuyor. '
                                   'Mevcut planı açabilir veya yeni bir ileri–geri çevrim oluşturabilirsiniz.')
        if len(project.cylinders) > 1:
            self.existing_note.setText('Bu projede birden fazla silindir var. Verileriniz korunuyor; mevcut hareket planını açın.')
        if values is None:
            c = project.cylinders[0]
            values = replace(PracticalInputs(), bore=c.bore * 1000, rod=c.rod * 1000, stroke=c.stroke * 1000)
        factor = FORCE_FACTORS['tonf'] / FORCE_FACTORS[self._force_unit]
        for key in TITLES:
            value = getattr(values, key) * (factor if key in ('force', 'return_force') else 1.)
            self.set_number(key, value)
            if key in ('force','return_force'):
                phase = project.phases[0 if key=='force' else -1] if canonical else None
                self.inputs[key]._si_force = phase.force if phase is not None else value * FORCE_FACTORS[self._force_unit]
        self.form.setEnabled(self.allowed); self.pending = False; self.ready = False
        self.auto_pump.blockSignals(True); self.auto_pump.setChecked(self.fresh); self.auto_pump.blockSignals(False)
        self.draft_note.setText('Örnek başlangıç değerleri; kendi ölçü ve sürelerinizle değiştirin. '
                                'Hesapla düğmesi basit ileri–geri çevrimi oluşturur.' if values and self.fresh else
                                'Ölçü değişirse ileri ve geri hareket de yeni strokun tamamını kullanır.')
        self.update_diagram(); self.clear_result()
        self.state.setText('Ölçüleri ve hareket sürelerini girip hesaplayın.' if self.allowed else
                           'Mevcut özel planınız korunuyor; basit hesap henüz oluşturulmadı.')
        self.state.setProperty('role','muted'); polish(self.state)
        self.set_chip('muted', 'Örnek değerler' if self.fresh else 'Hesaplanmadı')

    def start_new(self):
        self.allowed = True; self.form.setEnabled(True); self.existing.hide(); self.fresh = False
        self.auto_pump.setChecked(True)
        self.draft_note.setText('Hesapla dediğinizde mevcut hareketlerin yerine bu ileri–geri çevrim yazılır. '
                                'Diğer teknik ayarlar korunur.')
        self.mark_pending()

    def read_project(self, base):
        if not self.pending or not self.allowed:
            return base
        values = PracticalInputs(**{key: self.number(key) for key in TITLES}, force_unit=self._force_unit)
        project = practical_project(base, values)
        exact_sizes = {key:getattr(base.cylinders[0],key) for key in ('bore','rod','stroke')
                       if getattr(self.inputs[key],'_shown',(None,))[0] == self.inputs[key].text()}
        cylinder = replace(project.cylinders[0],**exact_sizes)
        loads = {}
        for key, kinds in (('force',('extend','hold')),('return_force',('retract',))):
            edit = self.inputs[key]
            if getattr(edit,'_shown',(None,))[0] == edit.text():
                loads.update({kind:edit._si_force for kind in kinds})
        return replace(project,cylinders=(cylinder,),phases=tuple(
            replace(p,stroke=cylinder.stroke,force=loads.get(p.kind,p.force)) for p in project.phases))

    def mark_pending(self, *args):
        self.pending = True; self.ready = False; self.error.hide()
        for edit in self.inputs.values():edit.setProperty('invalid', False); polish(edit)
        self.clear_result(); self.state.setText('Bilgiler değişti. Sonucu görmek için hesaplayın.'); self.set_chip('muted', 'Değişti · hesaplayın')
        self.state.setProperty('role','muted'); polish(self.state); self.status.clear()
        self.owner.result = None; self.owner.timer.stop(); self.owner.refresh_actions(); self.update_diagram()

    def calculate(self):
        if not self.allowed or self.owner.busy or self.owner.pdf_job is not None:return
        self.pending = True
        self.owner.recalculate()
        if self.ready:self.reveal_timer.start(0)

    def reveal_result(self):
        if self.ready and self.isVisible():
            top = self.output_panel.mapTo(self.workspace.widget(),QPoint()).y()
            self.workspace.verticalScrollBar().setValue(top)

    def change_force_unit(self):
        new = self.force_unit.currentData(); old = self._force_unit
        try:
            forces = {key: self.inputs[key]._si_force if getattr(self.inputs[key],'_shown',(None,))[0] == self.inputs[key].text()
                      else self.number(key) * FORCE_FACTORS[old] for key in ('force','return_force')}
            values = {key: force / FORCE_FACTORS[new] for key,force in forces.items()}
            if not all(math.isfinite(v) for v in values.values()):raise InputError('practical.force', 'Kuvvet çok büyük.')
        except InputError as error:
            self.force_unit.blockSignals(True); self.force_unit.setCurrentIndex(self.force_unit.findData(old)); self.force_unit.blockSignals(False)
            self.show_error(error); return
        self._force_unit = new
        for key, value in values.items():
            self.set_number(key, value); self.inputs[key]._unit_label.setText(new); self.inputs[key]._si_force=forces[key]
        self.update_diagram()

    def update_diagram(self):
        values = {}
        for key in ('bore', 'rod', 'stroke'):
            try:values[key] = self.number(key)
            except InputError:pass
        self.diagram.set_values(values)
        seconds = {}
        for key in ('extend_time', 'hold_time', 'return_time'):
            try:
                value = self.number(key); seconds[key] = value if value >= 0 else None
            except InputError:
                seconds[key] = None
        parts = [('İleri', seconds['extend_time'])]
        if seconds['hold_time']:
            parts.append(('Bekle', seconds['hold_time']))
        self.strip.set_parts(parts + [('Geri', seconds['return_time'])])
        self.return_note.setText(f'Geri dönüş yükü: {self.inputs["return_force"].text()} {self._force_unit} · '
                                 'değiştirmek için üstteki bölümü açın.')

    def clear_result(self):
        self.schematic.clear('Güncel değerleri görmek için hesaplayın.')
        for card in self.cards.values():card.hide()
        while self.issue_box.count():
            item = self.issue_box.takeAt(0); widget = item.widget()
            if widget is not None:widget.hide(); widget.deleteLater()
        self.cycle.clear(); self.technical.clear(); self.report_row.hide()
        self.pdf_button.setEnabled(False); self.excel_button.setEnabled(False)

    def show_error(self, error):
        self.ready = False; self.clear_result(); self.error.setText(str(error)); self.error.show()
        self.state.setText('Hesap yapılmadı; işaretli bilgiyi düzeltin.'); self.set_chip('error', 'Girdi hatası')
        key = error.field.removeprefix('practical.')
        if key in self.inputs:
            if key == 'return_force':self.return_section.set_expanded(True)
            edit = self.inputs[key]; edit.setProperty('invalid', True); polish(edit); edit.setFocus()
            self.workspace.ensureWidgetVisible(edit)
        else:self.workspace.ensureWidgetVisible(self.error)

    def show_result(self, project, result):
        if practical_values(project) is None or not self.allowed:
            self.ready = False; self.clear_result()
            if not self.fresh and not self.pending:
                self.schematic.set_nodes(self.owner.simple.schematic.nodes)
            return
        self.pending = False; self.ready = True; self.fresh = False; self.error.hide(); self.clear_result()
        self.schematic.set_nodes(self.owner.simple.schematic.nodes)
        self.draft_note.setText('Sonuç, girdiğiniz ölçü ve süreler içindir. Bir değeri değiştirirseniz yeniden hesaplayın.')
        for edit in self.inputs.values():edit.setProperty('invalid', False); polish(edit)
        rows = {name: show(value, unit) for name, value, unit, _ in result_rows(project, result)}
        cycle = result.cycle
        critical = [i for i in result.issues if i.severity == 'critical']
        self.state.setText('Ön seçim hazır · aşağıdaki kritik konular çözülmeli' if critical else 'Ön seçim hazır')
        self.state.setProperty('role', 'error' if critical else 'success'); polish(self.state)
        warning = [i for i in result.issues if i.severity == 'warning']
        self.set_chip('error' if critical else 'warning' if warning else 'success',
                      f'{len(critical)} kritik' if critical else f'{len(warning)} kontrol' if warning else 'Uygun')
        self.cycle.setText('İleri → ' + ('uçta bekle → ' if len(project.phases) == 3 else '') +
                           f'geri · toplam {show(cycle["duration"], "s")} · başlangıç konumuna döner')
        nodes = self.owner.simple.schematic.nodes
        self.cards['motor'].fill('ÖNERİ' if project.selected_motor is None else 'MEVCUT', rows['Seçilen motor'], [],
                                 'Etiket gücü; görev sınıfını üreticiyle doğrulayın.',
                                 'Motorun etiket gücü. Üretici görev sınıfı ayrıca doğrulanır.', nodes['motor'].state)
        self.cards['pump'].fill('GEREKEN', rows['Maksimum gerekli debi'],
                                ['Yağı, istediğiniz hareket süresine yetiştirecek debi.'],
                                'Süreye yetişecek debi; basınç sınırı ayrıca karşılanmalı.',
                                'Debi yeterli olsa da pompanın basınç sınırı ayrıca karşılanmalı.', nodes['pump'].state)
        self.cards['pressure'].fill('GEREKEN', rows['Maksimum gerekli basınç'], [],
                                    f'Emniyet valfi: {rows["Emniyet valfi ayarı"]}',
                                    'Yükü hareket ettirmek için hattaki en yüksek basınç (hat kayıpları dahil).', nodes['relief'].state)
        self.cards['tank'].fill('GEREKEN', rows['Gerekli kullanılabilir tank'], [],
                                'Kullanılabilir yağ; tankın dış hacmi değildir.',
                                'Tankta bulunması gereken kullanılabilir yağ; tankın dış hacmi değildir.', nodes['tank'].state)
        for card in self.cards.values():card.show()
        self.technical.setText('\n'.join(f'{name}: {rows[name]}' for name in (
            'Maksimum gerekli basınç', 'Emniyet valfi ayarı', 'Nominal deplasman adayı',
            'Boru/hortum iç çapı', 'Gerekli soğutucu', 'Mevcut kullanılabilir tank')) +
            '\n\nPompa, yağ, hat ve tank ayarları ayrıntılı görünümdeki değerlerdir. '
            'Isı ve soğutma sonucu, hareketler karşılanmıyorsa yalnız senaryodur. Ön boyutlandırmadır.')
        warnings = QWidget(); wb = QVBoxLayout(warnings); wb.setContentsMargins(0, 0, 0, 0)
        other = 0
        for issue in result.issues:
            if issue.severity not in ('critical', 'warning'):continue
            problem, action = PLAIN_ISSUES.get(issue.code, (issue.message, 'Ayrıntılı ayarlarda bu değeri kontrol edin.'))
            if issue.code in ('COOLER', 'HOT_OIL'):
                action = f'Gereken soğutma gücü: {rows["Gerekli soğutucu"]}. Göster ile tank ve ısı ayarlarını inceleyin.'
                if result.thermal.get('status') == 'scenario_only':action += ' Bu değer yalnız senaryodur.'
            elif issue.code == 'CAPACITY':
                action = ('Soldaki pompa boyutlandırma seçeneğini açıp yeniden hesaplayın; basınç sınırını da kontrol edin.'
                          if not self.auto_pump.isChecked() else
                          'Debi adayı uygulandı. Basınç sınırı ve diğer pompa ayarlarını Göster ile kontrol edin.')
            target = (lambda:self.owner.open_detailed(0)) if issue.code=='BUCKLING' else (
                lambda f=issue.field:self.owner.navigate_to_field(f))
            row = IssueRow(issue.severity, problem, action, target)
            if issue.severity == 'critical':self.issue_box.addWidget(row)
            else:wb.addWidget(row); other += 1
        if other:self.issue_box.addWidget(Disclosure(f'Diğer kontroller ({other})', warnings))
        else:warnings.deleteLater()
        self.report_row.show(); self.update_actions(result, self.owner.busy, self.owner.pdf_job is not None)

    def update_actions(self, result, busy, reporting):
        ready = self.ready and not self.pending and result is not None and not busy and not reporting
        self.pdf_button.setEnabled(ready); self.excel_button.setEnabled(ready)
        self.cancel_pdf_button.setVisible(reporting)
        self.report_row.setVisible(self.ready or reporting)
        self.calculate_button.setEnabled(self.allowed and not busy and not reporting)

    def open_plan(self):
        self.owner.view_mode.setCurrentIndex(0)

    def open_node(self, node):
        if node == 'cylinder':
            if self.allowed:
                edit = self.inputs['bore']; self.workspace.ensureWidgetVisible(edit); edit.setFocus()
            else:
                self.owner.open_detailed(0)
        else:
            self.owner.simple.open_node(node)

    def set_chip(self, role, text):
        self.chip.setText(text); self.chip.setProperty('role', role); polish(self.chip)

    def apply_theme(self):
        appearance = self.owner.context.appearance; c = COLORS[appearance]
        self.diagram.update(); self.strip.appearance = appearance; self.strip.update()
        self.schematic.appearance = appearance; self.schematic.update()
        self.setStyleSheet(f'''
            QLabel[chip="true"] {{ border: 1px solid {c['border']}; border-radius: 11px; padding: 3px 12px; font-weight: 600; }}
            QLabel[chip="true"][role="success"] {{ border-color: {c['success']}; }}
            QLabel[chip="true"][role="warning"] {{ border-color: {c['warning']}; }}
            QLabel[chip="true"][role="error"] {{ border-color: {c['danger']}; }}
            QLabel[stepBadge="true"] {{ background: {c['accent']}; color: {c['on_accent']}; border-radius: 13px; font-weight: 700; }}
            QLabel[fieldTitle="true"] {{ font-weight: 600; }}
            QLabel[hint="true"] {{ font-size: 11px; }}
            QFrame[unitField="true"] {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; }}
            QFrame[unitField="true"]:hover {{ border-color: {c['border_strong']}; }}
            QLineEdit[inUnitField="true"] {{ background: transparent; border: none; font-size: 15px; font-weight: 600; padding: 0 2px 0 8px; }}
            QLineEdit[inUnitField="true"][invalid="true"] {{ color: {c['danger']}; }}
            QFrame[metric="true"] {{ border-left: 4px solid {c['border_strong']}; }}
            QFrame[metric="true"][state="success"] {{ border-left-color: {c['success']}; }}
            QFrame[metric="true"][state="warning"] {{ border-left-color: {c['warning']}; }}
            QFrame[metric="true"][state="error"] {{ border-left-color: {c['danger']}; }}
            QLabel[kicker="true"] {{ font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }}
            QLabel[metricValue="true"] {{ font-size: 22px; font-weight: 700; }}
        ''')
