"""Normal GOKWORKS entry: manual sequence → native 3D sweep → operator PDF."""
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QSize
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                              QListWidget, QScrollArea, QSlider, QSplitter, QTextBrowser, QVBoxLayout, QWidget)
from gui_qt.components import BasePage, button, label
from gui_qt.theme import COLORS
from .dialogs import ToolDialog, format_segments, segments
from .models import Plan, Step
from .service import PHASES, STATUS
from .viewer import SceneView
from .tool_picker import ToolPicker, profile_icon


class PressBrakePage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Abkant Simülasyonu', 'Hava bükümü · manuel sıra ve takım planı · geometrik hareket kontrolü')
        self.plan = self.result = None
        self.flat_mesh = self.formed_mesh = None
        self.loading = False; self.generation = 0; self.frame_index = 0
        self.preview_pending = False; self.preview_key = None; self.view_mode = 'step'
        self.library_path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))/'press-brake-tools-v1.json'
        self.library = ()
        self.check_button = self.action('Hareketi kontrol et', self.calculate, primary=True)
        self.pdf_button = self.action('Büküm Föyü PDF', self.pdf_dialog)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        row = QHBoxLayout()
        self.sw_button = button('Aktif SolidWorks Parçasını Al', self.read_sw); row.addWidget(self.sw_button)
        self.demo_picker = QComboBox(); self.demo_picker.addItem('DEMO · Delikli kutu / 2 mm', 'box')
        self.demo_picker.addItem('DEMO · U / 2 mm', 'U'); self.demo_picker.addItem('DEMO · L / 120°', 'L120')
        self.demo_picker.setMinimumContentsLength(14); self.demo_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.demo_picker.setAccessibleName('Özgün demo parçası'); row.addWidget(self.demo_picker, 1)
        self.demo_button = button('Demoyu aç', lambda: self.load_demo(self.demo_picker.currentData())); row.addWidget(self.demo_button)
        self.layout.addLayout(row)
        self.part_label = label('Bir SolidWorks sac parçasını alın veya özgün demo açın.', 'muted'); self.part_label.setWordWrap(True); self.layout.addWidget(self.part_label)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        left = QWidget(); left.setMinimumWidth(130); left_body = QVBoxLayout(left); left_body.setContentsMargins(0, 0, 0, 0)
        left_body.addWidget(label('BÜKÜM SIRASI', 'muted')); self.bends = QListWidget(); self.bends.setAccessibleName('Büküm sırası')
        self.bends.setWordWrap(True); self.bends.setTextElideMode(Qt.ElideNone); self.bends.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_body.addWidget(self.bends, 1)
        order = QHBoxLayout(); self.up = button('↑', lambda: self.reorder(-1)); self.down = button('↓', lambda: self.reorder(1))
        self.up.setAccessibleName('Bükümü yukarı taşı'); self.down.setAccessibleName('Bükümü aşağı taşı')
        order.addWidget(self.up); order.addWidget(self.down); left_body.addLayout(order)
        self.import_tool = button('DXF takım ekle…', self.tool_dialog); left_body.addWidget(self.import_tool)
        self.unitless = QCheckBox('Birimsiz DXF = mm'); self.unitless.setToolTip('1 çizim birimi = 1 mm. Yalnız çizimin mm ölçekte olduğunu biliyorsanız seçin.'); left_body.addWidget(self.unitless)
        self.splitter.addWidget(left)
        center = QWidget(); center.setMinimumWidth(140); center_body = QVBoxLayout(center); center_body.setContentsMargins(0, 0, 0, 0)
        self.viewer = SceneView(); center_body.addWidget(self.viewer, 1)
        views = QHBoxLayout()
        self.flat_button = button('Açınım', lambda: self.show_shape(False)); self.formed_button = button('Bitmiş form', lambda: self.show_shape(True))
        self.fit_button = button('Sığdır', self.viewer.fit)
        for w in (self.flat_button, self.formed_button, self.fit_button):
            views.addWidget(w)
        center_body.addLayout(views)
        legend = label('Sarı: aktif eksen · Mavi: üst · Yeşil: alt · Kırmızı: çarpışma', 'muted'); legend.setWordWrap(True); center_body.addWidget(legend)
        self.splitter.addWidget(center)
        right = QWidget(); right.setMinimumWidth(200); form = QFormLayout(right); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.bend_label = QLabel('Adım seçin'); self.bend_label.setWordWrap(True); form.addRow(self.bend_label)
        self.punch = QComboBox(); self.die = QComboBox(); self.channel = QComboBox()
        self.punch_button = button('Üst bıçak seç…', lambda: self.choose_tool('punch'))
        self.die_button = button('Alt kalıp seç…', lambda: self.choose_tool('die'))
        for title, field in (('Üst bıçak · görsel kütüphane', self.punch_button), ('Alt kalıp · görsel kütüphane', self.die_button)):
            field.setMinimumHeight(60); field.setIconSize(QSize(42, 46)); form.addRow(title, field)
        # Keep the selection models/API for existing tests and saved page state;
        # the operator selects from section cards, not these hidden widgets.
        for picker in (self.punch, self.die):
            picker.setParent(self); picker.hide()
        for title, field in (('V kanalı', self.channel),):
            field.setMinimumContentsLength(10); field.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            field.setAccessibleName(title); form.addRow(title, field)
        self.fixed = QComboBox(); self.fixed.addItem('Ana flanş sabit', 'parent'); self.fixed.addItem('Karşı taraf sabit', 'child'); form.addRow('Tutuş', self.fixed)
        self.orientation = QComboBox(); self.orientation.addItem('0°', 0); self.orientation.addItem('180° · yeniden konumlandır', 180); form.addRow('Parça yönü', self.orientation)
        self.direction = QComboBox(); self.direction.addItem('CAD büküm yönü', False); self.direction.addItem('Büküm yönünü ters çevir', True); form.addRow('Yön', self.direction)
        self.punch_segments = QLineEdit(); self.die_segments = QLineEdit()
        for title, field in (('Üst segmentler · x:L (mm)', self.punch_segments), ('Alt segmentler · x:L (mm)', self.die_segments)):
            field.setAccessibleName(title); form.addRow(title, field)
        self.apply_segments = button('Segment yerleşimini uygula', self.update_segments); form.addRow(self.apply_segments)
        self.tool_info = QLabel(); self.tool_info.setWordWrap(True); form.addRow(self.tool_info)
        self.details = QTextBrowser(); self.details.setMinimumHeight(100); self.details.setOpenExternalLinks(False); form.addRow(self.details)
        self.right_scroll = QScrollArea(); self.right_scroll.setWidgetResizable(True); self.right_scroll.setWidget(right); self.right_scroll.setMinimumWidth(200)
        self.splitter.addWidget(self.right_scroll); self.splitter.setStretchFactor(1, 1); self.splitter.setSizes([180, 700, 280]); self.layout.addWidget(self.splitter, 1)
        playback = QHBoxLayout(); self.previous = button('◀ Adım', lambda: self.select_step(-1)); self.play = button('Oynat', self.toggle_play); self.next = button('Adım ▶', lambda: self.select_step(1))
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(0, 0); self.slider.setAccessibleName('Hareket konumu')
        self.speed = QComboBox(); self.speed.addItem('5 kare/s', 200); self.speed.addItem('12 kare/s', 83); self.speed.addItem('24 kare/s', 42); self.speed.setCurrentIndex(1); self.speed.setAccessibleName('Oynatma hızı; kontrol çözünürlüğünü değiştirmez')
        for w in (self.previous, self.play, self.next, self.slider, self.speed):
            playback.addWidget(w, 1 if w is self.slider else 0)
        self.layout.addLayout(playback)
        self.frame_label = label('Hareket kontrolü henüz çalıştırılmadı.', 'muted'); self.frame_label.setWordWrap(True); self.layout.addWidget(self.frame_label)
        scope = label('Kapsam: sac / atanmış takım katıları / varsa tutucular. Tezgâh, arka dayama, adımlar arası tutuş ve çıkarma rotası kapsam dışı. CNC strok hesabı değildir.', 'muted'); scope.setWordWrap(True); self.layout.addWidget(scope)
        self.finish_layout()
        self.timer = QTimer(self); self.timer.timeout.connect(self.advance)
        self.bends.currentRowChanged.connect(self.select)
        for field in (self.punch, self.die, self.channel, self.fixed, self.orientation, self.direction):
            field.currentIndexChanged.connect(self.assignment_changed)
        self.slider.valueChanged.connect(self.show_frame)
        self.controls += [self.sw_button, self.demo_button, self.demo_picker, self.bends, self.up, self.down, self.import_tool,
                          self.punch, self.die, self.punch_button, self.die_button, self.channel, self.fixed, self.orientation, self.direction, self.punch_segments, self.die_segments, self.apply_segments]
        self.theme_changed(); self.refresh_actions()

    def theme_changed(self):
        if hasattr(self, 'viewer'):
            self.viewer.set_background(COLORS[self.context.appearance]['canvas'])
        if getattr(self, 'plan', None):
            self.refresh_tool_buttons()

    def refresh_actions(self):
        ready = self.plan is not None and not self.busy
        self.check_button.setEnabled(ready); self.pdf_button.setEnabled(ready and self.result is not None)
        for control in (self.play, self.slider, self.previous, self.next):
            control.setEnabled(ready and bool(self.result and self.result.frames))
        self.flat_button.setEnabled(ready and self.flat_mesh is not None); self.formed_button.setEnabled(ready and self.formed_mesh is not None)
        self.punch_button.setEnabled(ready); self.die_button.setEnabled(ready)

    def set_busy(self, busy):
        super().set_busy(busy)
        if busy:
            self.pause()
        self.refresh_actions()

    def job_finished(self):
        self.refresh_actions()
        if self.preview_pending:
            self.preview()

    def pause(self):
        self.timer.stop(); self.play.setText('Oynat')

    def start(self, operation):
        if not self.can_start():
            return False
        self.pause()
        def guarded(sink, stop):
            from modules.cad_converter.models import Cancelled
            from modules.tolerance_stack.calculator import Cancelled as FileCancelled
            try:
                operation(sink, stop)
            except (Cancelled, FileCancelled):
                sink.put(('press_cancelled', 'İşlem durduruldu; tamamlanmamış kontrol sonucu yayımlanmadı.'))
        return self.jobs.start(self, guarded)

    def load_demo(self, kind='box'):
        from .demo import load_demo
        self.load_plan(lambda stop: load_demo(kind))

    def read_sw(self):
        from .solidworks import read_active
        from .demo import tools
        self.load_plan(lambda stop: (lambda part: Plan(part, tuple(Step(b.id) for b in part.bends), tools()))(read_active(stop)))

    def load_plan(self, factory):
        def operation(sink, stop):
            from .geometry import Geometry, mesh
            from .kinematics import step_angles
            from .tooling import load_catalog
            from modules.cad_converter.models import checkpoint
            plan = factory(stop); checkpoint(stop)
            library = load_catalog(self.library_path)
            plan = replace(plan, tools=plan.tools+library)
            plan.validate(); geometry = Geometry(plan)
            flat = mesh(geometry.part_bodies({}), stop); formed = mesh(geometry.part_bodies(step_angles(plan, len(plan.steps)-1, 1)), stop)
            sink.put(('press_plan', (plan, flat, formed, library)))
        self.start(operation)

    def accept_plan(self, plan, flat, formed, library):
        self.generation += 1; self.plan, self.result = plan, None
        self.flat_mesh, self.formed_mesh, self.library = flat, formed, library
        self.loading = True
        self.bends.clear(); self.bends.addItems([s.bend for s in plan.steps])
        for picker, kind in ((self.punch, 'punch'), (self.die, 'die')):
            picker.clear()
            for tool in plan.tools:
                if tool.kind == kind:
                    picker.addItem(tool.code+(' · DEMO' if tool.demo else ''), tool.id)
        self.loading = False; self.bends.setCurrentRow(0)
        self.refresh_steps()
        p = plan.part
        self.part_label.setText(f'{"DEMO · " if p.demo else ""}{p.name} · {p.configuration} · {p.thickness:g} mm · {p.material} · {len(p.bends)} büküm')
        self.viewer.frame = None; self.viewer.set_mesh(flat)
        self.frame_label.setText('Açınım yüklendi. Sırayı ve takımları atayıp hareketi kontrol edin.')
        self.set_status('Parça okundu; hareket kontrolü bekleniyor.'); self.refresh_actions()

    def select(self, index, seek=True):
        if self.loading or self.plan is None or not 0 <= index < len(self.plan.steps):
            return
        if seek:
            self.pause()
        self.loading = True
        step = self.plan.steps[index]; bend = next(b for b in self.plan.part.bends if b.id == step.bend)
        self.bend_label.setText(f'Adım {index+1} · {bend.title}\nİç açı {bend.inside_angle:g}° / dönüş {bend.turn:g}°\nİç R {bend.radius:g} mm · etkin boy {bend.length:.2f} mm')
        for picker, value in ((self.punch, step.punch), (self.die, step.die), (self.fixed, step.fixed_side), (self.orientation, step.orientation), (self.direction, step.reverse)):
            picker.setCurrentIndex(picker.findData(value))
        die = self.plan.tool(step.die); self.channel.clear()
        for channel in die.channels:
            self.channel.addItem(f'{channel.id} · V{channel.opening:g} / {channel.angle:g}°', channel.id)
        self.channel.setCurrentIndex(self.channel.findData(step.channel))
        punch = self.plan.tool(step.punch)
        self.punch_segments.setText(format_segments(step.punch_segments if step.punch_segments is not None else punch.segments))
        self.die_segments.setText(format_segments(step.die_segments if step.die_segments is not None else die.segments))
        self.tool_info.setText(f'{punch.code}: {punch.maker}\n{die.code}: {die.maker}\nHat yükü: '+(' / '.join(f'{t.line_load} {t.line_load_unit}' if t.line_load is not None else 'bilinmiyor' for t in (punch, die)))+'\nProses iç R tahmini: bilinmiyor')
        self.loading = False; self.show_details(index)
        self.refresh_tool_buttons()
        self.view_mode = 'step'
        if self.result and seek:
            first = next((i for i, f in enumerate(self.result.frames) if f.step == index), None)
            if first is not None:
                self.slider.setValue(first); self.show_frame(first)
        elif not self.result:
            self.preview_pending = True
            self.preview()

    def refresh_tool_buttons(self):
        if not self.plan or self.bends.currentRow() < 0:
            return
        step = self.plan.steps[self.bends.currentRow()]
        for widget, id in ((self.punch_button, step.punch), (self.die_button, step.die)):
            tool = self.plan.tool(id)
            widget.setText(tool.code+'\nDeğiştir…')
            widget.setIcon(profile_icon(tool, self.context.appearance, QSize(42, 46)))
            widget.setToolTip(f'{tool.maker} / {tool.code}\nKesit kartlarından seçmek için tıklayın.')

    def choose_tool(self, kind):
        if not self.plan or self.busy or self.bends.currentRow() < 0:
            return
        index = self.bends.currentRow(); old = self.plan.steps[index]
        current = old.punch if kind == 'punch' else old.die
        chosen_segments = old.punch_segments if kind == 'punch' else old.die_segments
        picker = ToolPicker(self.plan.tools, kind, current, channel=old.channel,
                            assigned_segments=chosen_segments, appearance=self.context.appearance,
                            settings=self.settings, parent=self)
        accepted = picker.exec()
        if picker.import_requested:
            self.tool_dialog()
        elif accepted and picker.selection:
            selected = picker.selection
            if kind == 'punch':
                step = replace(old, punch=selected.tool, punch_segments=selected.segments)
            else:
                step = replace(old, die=selected.tool, channel=selected.channel, die_segments=selected.segments)
            rows = list(self.plan.steps); rows[index] = step
            self.invalidate(self.plan.changed(steps=tuple(rows)))

    def refresh_steps(self):
        if not self.plan:
            return
        for i, step in enumerate(self.plan.steps):
            bend = next(b for b in self.plan.part.bends if b.id == step.bend)
            previous = self.plan.steps[i-1] if i else None
            change = previous and (step.punch, step.die, step.channel) != (previous.punch, previous.die, previous.channel)
            status = '\n'+STATUS[self.result.steps[i].status] if self.result else ''
            self.bends.item(i).setText(f'{i+1}. {bend.title}'+status+('\nTakım değişimi' if change else '')+('\nYeniden tutuş' if i else '')+(' · Çevir 180°' if step.orientation else ''))

    def preview(self):
        if not self.preview_pending or not self.plan or self.result or self.view_mode != 'step':
            self.preview_pending = False
            return
        if self.jobs.busy:
            return
        index = self.bends.currentRow(); key = (self.generation, index)
        self.preview_pending = False
        if index < 0 or self.preview_key == key:
            return
        self.preview_key = key; plan = self.plan
        def operation(sink, stop):
            from .geometry import Geometry, mesh
            from .kinematics import step_angles
            from .service import Frame
            geometry = Geometry(plan)
            bodies, _ = geometry.scene(index, step_angles(plan, index, 0))
            bend = next(b for b in plan.part.bends if b.id == plan.steps[index].bend)
            frame = Frame(index, 'approach', 0, mesh(bodies, stop),
                          ((-bend.length/2, 0, 0), (bend.length/2, 0, 0)), (),
                          tuple((b.id, b.bounds) for b in bodies if b.kind != 'sheet'))
            sink.put(('press_preview', (key, frame)))
        self.start(operation)

    def show_details(self, index):
        if self.result is None:
            self.details.setPlainText('Kontrol bekleniyor. Takım değişimleri ve adımlar arası parça çevirme hareketleri ayrıca kurulumda doğrulanır.')
            return
        status = self.result.steps[index]
        text = STATUS[status.status]+'\n'+f'{status.samples} katı poz kontrolü\n'+'\n'.join(status.notes)
        if status.first_hit:
            f = status.first_hit
            text += f'\nİlk çarpışma: {PHASES[f.phase]} / {f.angle:.2f}°\n'+'\n'.join(' ↔ '.join(h.pair)+f' @ {tuple(round(v, 2) for v in h.location)} mm' for h in f.hits)
        self.details.setPlainText(text)

    def invalidate(self, plan):
        self.pause(); self.plan = plan; self.result = None; self.generation += 1
        self.formed_mesh = None
        self.viewer.frame = None; self.viewer.set_mesh(self.flat_mesh); self.viewer.overlay.update()
        self.frame_label.setText('Plan değişti · önceki hareket kontrolü geçersiz. Yeniden kontrol edin.')
        self.refresh_steps(); self.select(self.bends.currentRow()); self.refresh_actions()

    def assignment_changed(self):
        if self.loading or not self.plan:
            return
        index = self.bends.currentRow()
        if index < 0:
            return
        old = self.plan.steps[index]
        die = self.plan.tool(self.die.currentData())
        channel = self.channel.currentData() if old.die == die.id else (die.channels[0].id if die.channels else '')
        step = replace(old, punch=self.punch.currentData(), die=die.id, channel=channel,
                       fixed_side=self.fixed.currentData(), orientation=self.orientation.currentData(), reverse=self.direction.currentData(),
                       punch_segments=old.punch_segments if old.punch == self.punch.currentData() else None,
                       die_segments=old.die_segments if old.die == die.id else None)
        steps = list(self.plan.steps); steps[index] = step
        self.invalidate(self.plan.changed(steps=tuple(steps)))

    def update_segments(self):
        if not self.plan:
            return
        try:
            index = self.bends.currentRow(); step = self.plan.steps[index]
            step = replace(step, punch_segments=segments(self.punch_segments.text()), die_segments=segments(self.die_segments.text()))
            rows = list(self.plan.steps); rows[index] = step; self.invalidate(self.plan.changed(steps=tuple(rows)))
        except ValueError as error:
            self.set_status(str(error), True)

    def reorder(self, offset):
        if not self.plan:
            return
        i = self.bends.currentRow(); j = i+offset
        if i < 0 or not 0 <= j < len(self.plan.steps):
            return
        steps = list(self.plan.steps); steps[i], steps[j] = steps[j], steps[i]
        self.loading = True; self.bends.clear(); self.bends.addItems([s.bend for s in steps]); self.bends.setCurrentRow(j); self.loading = False
        self.invalidate(self.plan.changed(steps=tuple(steps)))

    def calculate(self):
        if not self.plan:
            return
        plan, token = self.plan, self.generation
        self.set_status('Yaklaşma, büküm ve geri çekilme katıları kontrol ediliyor…')
        def operation(sink, stop):
            from .service import run
            last = [None]
            def progress(index, phase, value):
                mark = index, phase
                if mark != last[0]:
                    sink.put(('press_progress', f'Adım {index+1} · {PHASES[phase]}')); last[0] = mark
            result = run(plan, stop, progress)
            sink.put(('press_result', (token, result)))
        self.start(operation)

    def accept_result(self, token, result):
        if token != self.generation or not self.plan or result.revision != self.plan.revision:
            return
        self.result = result; self.flat_mesh, self.formed_mesh = result.flat_mesh, result.formed_mesh
        self.loading = True; self.preview_pending = False
        self.refresh_steps()
        self.loading = False; self.slider.setRange(0, max(0, len(result.frames)-1)); self.slider.setValue(0)
        self.select(max(0, self.bends.currentRow())); self.set_status(STATUS[result.status]); self.refresh_actions()

    def show_frame(self, index):
        if not self.result or not 0 <= index < len(self.result.frames):
            return
        self.frame_index = index; frame = self.result.frames[index]
        if self.bends.currentRow() != frame.step:
            self.loading = True; self.bends.setCurrentRow(frame.step); self.loading = False
            self.select(frame.step, seek=False)
        self.viewer.set_frame(frame)
        self.frame_label.setText(f'Adım {frame.step+1} · {PHASES[frame.phase]} · dönüş {frame.angle:.2f}°'+(' · ÇARPIŞMA: '+'; '.join(' ↔ '.join(h.pair) for h in frame.hits) if frame.hits else ''))
        if frame.hits:
            self.pause()

    def toggle_play(self):
        if self.timer.isActive():
            self.pause()
        elif self.result and self.result.frames:
            if self.result.frames[self.frame_index].hits:
                self.set_status('Bu karede çarpışma var. Takımı/sırayı değiştirin veya incelemek için sürgüyü taşıyın.')
                return
            if self.frame_index >= len(self.result.frames)-1:
                self.slider.setValue(0)
            self.timer.start(self.speed.currentData()); self.play.setText('Duraklat')

    def advance(self):
        if not self.result or self.frame_index >= len(self.result.frames)-1:
            self.pause(); return
        self.slider.setValue(self.frame_index+1)

    def select_step(self, offset):
        if self.plan:
            self.bends.setCurrentRow(min(len(self.plan.steps)-1, max(0, self.bends.currentRow()+offset)))

    def show_shape(self, formed):
        self.view_mode = 'formed' if formed else 'flat'; self.preview_pending = False
        self.pause(); self.viewer.frame = None; self.viewer.set_mesh(self.formed_mesh if formed else self.flat_mesh); self.viewer.overlay.update()
        self.frame_label.setText('Nominal bitmiş form · takım/konumlandırma hareketi içermez' if formed else 'Gerçek açınım · delikler ve rahatlatmalar korunur')

    def pdf_dialog(self):
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Büküm Föyü PDF', 'Bukum-Foyu.pdf', 'PDF (*.pdf)')
        if path:
            self.export_pdf(path, overwrite=True)

    def export_pdf(self, path, overwrite=False):
        if not self.plan or not self.result:
            return
        plan, result = self.plan, self.result
        def operation(sink, stop):
            from .report import export_pdf
            output = export_pdf(plan, result, path, overwrite=overwrite, stop=stop)
            sink.put(('press_pdf', str(output)))
        self.start(operation)

    def tool_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Takım kesiti · gerçek ölçüde mm DXF', '', 'DXF (*.dxf)')
        if path:
            self.load_tool_dxf(path, self.unitless.isChecked())

    def load_tool_dxf(self, path, accept_unitless=False):
        def operation(sink, stop):
            from .tooling import read_sections
            text, contours = read_sections(path, accept_unitless=accept_unitless)
            sink.put(('press_tool_sections', (str(path), text, contours)))
        self.start(operation)

    def edit_tool(self, payload):
        # The previous job must finish before starting a new worker on accept.
        if self.jobs.busy:
            QTimer.singleShot(25, lambda: self.edit_tool(payload)); return
        dialog = ToolDialog(*payload, self)
        if dialog.exec() and dialog.tool:
            tool, holder_path = dialog.tool, dialog.fields['holder_path'].text().strip()
            holder_positions = dialog.fields['holder_segments'].text().strip()
            def operation(sink, stop):
                from .tooling import read_sections, save_catalog, load_catalog
                from .geometry import Geometry
                if holder_path:
                    holder_text, contours = read_sections(holder_path)
                    if len(contours) != 1:
                        raise ValueError('Tutucu DXF tek bir kapalı kesit içermeli.')
                    # Original holder coordinates must share the same mounting
                    # datum as the tool drawing, explicit in the metadata UI.
                    tool_with_holder = replace(tool, holder_section=contours[0][0], holder_source=holder_path,
                                               holder_segments=segments(holder_positions), holder_dxf=holder_text)
                else:
                    tool_with_holder = tool
                tool_with_holder.validate(); g = Geometry()
                for segment in tool_with_holder.segments:
                    g.tool_shape(tool_with_holder, segment)
                if tool_with_holder.holder_section is not None:
                    holder = replace(tool_with_holder, id=tool_with_holder.id+':holder', section=tool_with_holder.holder_section,
                                     section_dxf=tool_with_holder.holder_dxf, contour_index=0)
                    for segment in holder.holder_segments:
                        g.tool_shape(holder, segment)
                # Read the actual user library even when no part was opened.
                # Adding the first tool in a session must not erase old cards.
                existing = load_catalog(self.library_path)
                library = tuple(t for t in existing if t.id != tool_with_holder.id)+(tool_with_holder,)
                save_catalog(library, self.library_path)
                sink.put(('press_tool_added', (tool_with_holder, library)))
            self.start(operation)

    def handle_events(self, events):
        super().handle_events(events)
        for kind, value in events:
            if kind == 'press_plan':
                self.accept_plan(*value)
            elif kind == 'press_result':
                self.accept_result(*value)
            elif kind == 'press_progress':
                self.set_status(value+' · katı kontrolü sürüyor')
            elif kind == 'press_preview':
                key, frame = value
                if self.plan and key == (self.generation, self.bends.currentRow()) and self.view_mode == 'step' and not self.result:
                    self.viewer.set_frame(frame)
                    self.frame_label.setText(f'Adım {frame.step+1} · atanmış takımlar ve aktif eksen · KONTROL BEKLİYOR')
            elif kind == 'press_pdf':
                self.set_status('Büküm föyü oluşturuldu: '+value)
            elif kind == 'press_cancelled':
                self.preview_pending = False
                self.set_status(value)
            elif kind == 'press_tool_sections':
                QTimer.singleShot(0, lambda value=value: self.edit_tool(value))
            elif kind == 'press_tool_added':
                tool, self.library = value
                if self.plan:
                    present = {t.id for t in self.plan.tools}
                    added = tuple(t for t in self.library if t.id not in present)
                    self.invalidate(self.plan.changed(tools=self.plan.tools+added))
                    self.loading = True
                    for item in added:
                        picker = self.punch if item.kind == 'punch' else self.die
                        picker.addItem(item.code, item.id)
                    self.loading = False
                self.set_status('Takım kütüphaneye eklendi: '+tool.code)

    def hideEvent(self, event):
        self.pause(); super().hideEvent(event)
