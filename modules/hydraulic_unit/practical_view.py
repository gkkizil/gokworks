"""A single form for a novice's out-and-back cylinder calculation."""
from dataclasses import replace
import math

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from gui_qt.components import Disclosure, button, label, scroll
from .beginner import FORCE_FACTORS
from .beginner_view import CylinderDiagram, IssueRow, PLAIN_ISSUES, Responsive, ResultCard, panel, polish, show, text_number
from .core.validation import InputError
from .practical import PracticalInputs, TITLES, practical_project, practical_values
from .presentation import result_rows


class PracticalView(QWidget):
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.inputs = {}; self.pending = False; self.ready = False
        self.allowed = False; self._force_unit = 'tonf'
        self.reveal_timer = QTimer(self); self.reveal_timer.setSingleShot(True)
        self.reveal_timer.timeout.connect(self.reveal_result)
        self.fresh = not owner.settings.get('hydraulic_unit_project')
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(8)
        outer.addWidget(label('Ölçüleri girin. Hareketi tarif edin. Ünite ihtiyacını görün.', 'section'))
        outer.addWidget(label('Tek silindir için: mil dışarı çıkar, isterseniz uçta bekler ve aynı mesafeyi geri döner.', 'muted'))
        body = QWidget(); box = QVBoxLayout(body); box.setContentsMargins(2, 2, 8, 4)
        self.existing, existing = panel()
        self.existing_note = label('', 'muted'); existing.addWidget(self.existing_note)
        actions = QHBoxLayout()
        actions.addWidget(button('Mevcut hareket planını aç', self.open_plan))
        self.new_button = button('Yeni basit çevrim oluştur', self.start_new)
        actions.addWidget(self.new_button); actions.addStretch(1); existing.addLayout(actions)
        box.addWidget(self.existing)
        split = Responsive(980, 16)
        self.form = QWidget(); form = QVBoxLayout(self.form); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(12)
        sizes, contents = panel(); contents.addWidget(label('1  Silindirin ölçüleri', 'section'))
        grid = QGridLayout(); grid.setColumnStretch(0, 1); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)
        for row, (key, title, hint, example) in enumerate((
                ('bore', 'Silindirin iç çapı', 'Gövdenin dışı değil; etiketteki piston çapı (ØD).', '63'),
                ('rod', 'Parlak milin çapı', 'Dışarı çıkan mil; kumpasla bu kısmı ölçebilirsiniz.', '36'),
                ('stroke', 'Gideceği yol (strok)', 'Milin tamamen içeriden tamamen dışarıya gideceği mesafe.', '300'))):
            self.field(grid, row, key, title, 'mm', hint, example)
        contents.addLayout(grid)
        self.diagram = CylinderDiagram(owner.context)
        contents.addWidget(Disclosure('Bu ölçüler silindirin neresinde?', self.diagram))
        form.addWidget(sizes)
        motions, contents = panel(); contents.addWidget(label('2  Nasıl çalışsın?', 'section'))
        unit = QHBoxLayout(); unit.addWidget(label('İtme kuvvetini hangi birimle biliyorsunuz?', 'muted'), 1)
        self.force_unit = QComboBox(); self.force_unit.addItem('Ton-kuvvet', 'tonf'); self.force_unit.addItem('kN', 'kN')
        self.force_unit.setAccessibleName('Pratik hesap kuvvet birimi'); unit.addWidget(self.force_unit); contents.addLayout(unit)
        grid = QGridLayout(); grid.setColumnStretch(0, 1); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)
        self.field(grid, 0, 'force', 'İleri ne kadar kuvvet uygulasın?', 'tonf', 'Presin / silindirin uygulayacağı itme kuvveti.', '3')
        self.field(grid, 1, 'extend_time', 'İleri kaç saniyede gitsin?', 's', 'Tam stroku tamamlayacağı süre.', '5')
        self.field(grid, 2, 'return_time', 'Geri kaç saniyede dönsün?', 's', 'Aynı mesafeyi başlangıca geri gelir.', '5')
        self.field(grid, 3, 'hold_time', 'Uçta kaç saniye beklesin?', 's', 'Bekleme yoksa 0 yazın; varsa itme kuvveti korunur.', '0')
        contents.addLayout(grid)
        extra = QWidget(); e = QVBoxLayout(extra); e.setContentsMargins(0, 4, 0, 0)
        grid = QGridLayout(); grid.setColumnStretch(0, 1)
        self.field(grid, 0, 'return_force', 'Geri dönüşte gereken çekme kuvveti', 'tonf',
                   'Yüksüz dönüş için 0. Dönüşte direnç varsa gereken kuvveti girin.', '0')
        e.addLayout(grid)
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
        split.box.addWidget(self.form, 1)
        result, output = panel(); output.addWidget(label('Hangi ünite gerekir?', 'section'))
        self.output_panel = result
        self.state = label('Ölçüleri ve hareket sürelerini girip hesaplayın.', 'muted'); output.addWidget(self.state)
        self.cycle = label('', 'muted'); output.addWidget(self.cycle)
        self.cards = {}
        for key, title in (('motor', 'Elektrik motoru'), ('pump', 'Yağ pompası'), ('tank', 'Yağ tankı')):
            card = ResultCard(title); output.addWidget(card); self.cards[key] = card
        self.technical = label('', 'muted'); self.technical.setTextFormat(Qt.PlainText)
        output.addWidget(Disclosure('Basınç, soğutma ve diğer hesap ayrıntıları', self.technical))
        self.issue_box = QVBoxLayout(); output.addLayout(self.issue_box)
        self.report_row = QWidget(); reports = QHBoxLayout(self.report_row); reports.setContentsMargins(0, 4, 0, 0)
        self.pdf_button = button('PDF raporu al…', owner.export_pdf)
        self.excel_button = button('Excel al…', lambda: owner.export('excel'))
        self.cancel_pdf_button = button('Raporu durdur', owner.cancel_pdf, destructive=True); self.cancel_pdf_button.hide()
        reports.addWidget(self.pdf_button); reports.addWidget(self.excel_button); reports.addWidget(self.cancel_pdf_button); reports.addStretch(1)
        output.addWidget(self.report_row)
        self.status = label('', 'muted'); self.status.setTextFormat(Qt.PlainText); output.addWidget(self.status)
        output.addWidget(button('Hareket planı ve tüm sonuçlar →', self.open_plan, flat=True))
        output.addStretch(1); split.box.addWidget(result, 1)
        box.addWidget(split); self.workspace = scroll(body); outer.addWidget(self.workspace, 1)
        footer = QHBoxLayout(); footer.setSpacing(16); footer.addWidget(self.draft_note,1)
        footer.addWidget(self.calculate_button); outer.addLayout(footer)
        for key in self.inputs:
            self.inputs[key].textEdited.connect(self.mark_pending)
            self.inputs[key].returnPressed.connect(self.calculate)
        self.auto_pump.toggled.connect(self.mark_pending)
        self.force_unit.currentIndexChanged.connect(self.change_force_unit)
        self.clear_result()

    def field(self, grid, row, key, title, unit, hint, example):
        text = QWidget(); box = QVBoxLayout(text); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(2)
        heading = label(title); box.addWidget(heading); box.addWidget(label(hint, 'muted'))
        edit = QLineEdit(); edit.setFixedWidth(100); edit.setMinimumHeight(30)
        edit.setAlignment(Qt.AlignRight); edit.setPlaceholderText(example); edit.setAccessibleName(title)
        heading.setBuddy(edit); self.inputs[key] = edit
        unit_label = label(unit, 'muted', wrap=False); edit._unit_label = unit_label
        grid.addWidget(text, row, 0); grid.addWidget(edit, row, 1); grid.addWidget(unit_label, row, 2)

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
        self.clear_result(); self.state.setText('Bilgiler değişti. Sonucu görmek için hesaplayın.')
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
        self.return_note.setText(f'Geri dönüş yükü: {self.inputs["return_force"].text()} {self._force_unit} · '
                                 'değiştirmek için üstteki bölümü açın.')

    def clear_result(self):
        for card in self.cards.values():card.hide()
        while self.issue_box.count():
            item = self.issue_box.takeAt(0); widget = item.widget()
            if widget is not None:widget.hide(); widget.deleteLater()
        self.cycle.clear(); self.technical.clear(); self.report_row.hide()
        self.pdf_button.setEnabled(False); self.excel_button.setEnabled(False)

    def show_error(self, error):
        self.ready = False; self.clear_result(); self.error.setText(str(error)); self.error.show()
        self.state.setText('Hesap yapılmadı; işaretli bilgiyi düzeltin.')
        key = error.field.removeprefix('practical.')
        if key in self.inputs:
            if key == 'return_force':self.return_section.set_expanded(True)
            edit = self.inputs[key]; edit.setProperty('invalid', True); polish(edit); edit.setFocus()
            self.workspace.ensureWidgetVisible(edit)
        else:self.workspace.ensureWidgetVisible(self.error)

    def show_result(self, project, result):
        if practical_values(project) is None or not self.allowed:
            self.ready = False; self.clear_result(); return
        self.pending = False; self.ready = True; self.fresh = False; self.error.hide(); self.clear_result()
        self.draft_note.setText('Sonuç, girdiğiniz ölçü ve süreler içindir. Bir değeri değiştirirseniz yeniden hesaplayın.')
        for edit in self.inputs.values():edit.setProperty('invalid', False); polish(edit)
        rows = {name: show(value, unit) for name, value, unit, _ in result_rows(project, result)}
        cycle = result.cycle
        critical = [i for i in result.issues if i.severity == 'critical']
        self.state.setText('Ön seçim hazır · aşağıdaki kritik konular çözülmeli' if critical else 'Ön seçim hazır')
        self.state.setProperty('role', 'error' if critical else 'success'); polish(self.state)
        self.cycle.setText('İleri → ' + ('uçta bekle → ' if len(project.phases) == 3 else '') +
                           f'geri · toplam {show(cycle["duration"], "s")} · başlangıç konumuna döner')
        self.cards['motor'].fill('ÖNERİ' if project.selected_motor is None else 'MEVCUT', rows['Seçilen motor'], [],
                                 'Motorun etiket gücü. Üretici görev sınıfı ayrıca doğrulanır.')
        self.cards['pump'].fill('GEREKEN', rows['Maksimum gerekli debi'],
                                ['Yağı, istediğiniz hareket süresine yetiştirecek debi.'],
                                'Debi yeterli olsa da pompanın basınç sınırı ayrıca karşılanmalı.')
        self.cards['tank'].fill('GEREKEN', rows['Gerekli kullanılabilir tank'], [],
                                'Tankta bulunması gereken kullanılabilir yağ; tankın dış hacmi değildir.')
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

    def apply_theme(self):
        self.diagram.update()
