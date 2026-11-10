"""Normal GOKWORKS entry: manual sequence → native 3D sweep → operator PDF."""
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QSize, QLocale
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                              QAbstractItemView, QDoubleSpinBox, QListView, QListWidget, QListWidgetItem, QScrollArea, QSlider, QSplitter, QTextBrowser, QVBoxLayout, QWidget)
from gui_qt.components import AdaptiveRow, BasePage, Disclosure, ElidedLabel, button, card, label, separator
from gui_qt.theme import COLORS
from .dialogs import ToolDialog, format_segments, segments
from .models import Plan, Step
from .service import PHASES, STATUS
from .viewer import SceneView
from .tool_picker import ToolPicker, profile_icon
from .flat_plan import FlatPlan
from .cards import CARD, PROGRESS, STATES, StepCardDelegate

SCOPE = ('Kapsam: sac / atanmış takım katıları / varsa tutucular. Tezgâh (sahnedeki üst kiriş ve alt ray yalnız görsel), '
         'arka dayama, adımlar arası tutuş ve çıkarma rotası kapsam dışı. CNC strok hesabı ve üretim uygunluğu onayı değildir.')


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
        self.video_button = self.action('Video MP4', self.video_dialog)
        self.video_button.setToolTip('Kontrol edilen hareketi, sahnedeki bakış açısıyla MP4 video olarak kaydeder (oynatma hızı kare hızıdır).')
        self.video_writer = None
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        # Source bar: where the part comes from, and a one-line part summary.
        row = QHBoxLayout(); row.setSpacing(8)
        self.sw_button = button('Aktif SolidWorks Parçasını Al', self.read_sw); row.addWidget(self.sw_button)
        self.demo_picker = QComboBox(); self.demo_picker.addItem('DEMO · Delikli kutu / 2 mm', 'box')
        self.demo_picker.addItem('DEMO · U / 2 mm', 'U'); self.demo_picker.addItem('DEMO · L / 120°', 'L120')
        self.demo_picker.setMinimumContentsLength(22); self.demo_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.demo_picker.setAccessibleName('Özgün demo parçası'); row.addWidget(self.demo_picker)
        self.demo_button = button('Demoyu aç', lambda: self.load_demo(self.demo_picker.currentData())); row.addWidget(self.demo_button)
        self.part_label = ElidedLabel('Bir SolidWorks sac parçasını alın veya özgün demo açın.'); self.part_label.setProperty('role', 'muted')
        row.addWidget(self.part_label, 1)
        self.layout.addLayout(row)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)

        # Left: bend sequence as step cards.
        left = QWidget(); left.setMinimumWidth(150); left_body = QVBoxLayout(left); left_body.setContentsMargins(0, 0, 0, 0); left_body.setSpacing(6)
        self.sequence_title = label('BÜKÜM SIRASI', 'section', wrap=False); left_body.addWidget(self.sequence_title)
        self.bends = QListWidget(); self.bends.setAccessibleName('Büküm sırası')
        self.bends.setWordWrap(True); self.bends.setTextElideMode(Qt.ElideNone); self.bends.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bends.setResizeMode(QListView.Adjust); self.bends.setSpacing(0); self.bends.setUniformItemSizes(False)
        self.step_cards = StepCardDelegate(self.bends, context.appearance); self.bends.setItemDelegate(self.step_cards)
        self.step_cards.toggled.connect(self.toggle_step)
        # Drag a card to reorder (↑/↓ stay for keyboard use); the plan follows the list order.
        self.bends.setDragDropMode(QAbstractItemView.InternalMove); self.bends.setDefaultDropAction(Qt.MoveAction)
        self.bends.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self.dropped))
        left_body.addWidget(self.bends, 1)
        order = QHBoxLayout(); order.setSpacing(8)
        self.up = button('↑ Yukarı', lambda: self.reorder(-1)); self.down = button('↓ Aşağı', lambda: self.reorder(1))
        self.up.setAccessibleName('Bükümü yukarı taşı'); self.down.setAccessibleName('Bükümü aşağı taşı')
        self.up.setToolTip('Seçili bükümü sırada bir önceye alır (kartı sürükleyerek de taşıyabilirsiniz); önceki kontrol sonucu geçersiz olur.')
        self.down.setToolTip('Seçili bükümü sırada bir sonraya alır; önceki kontrol sonucu geçersiz olur.')
        order.addWidget(self.up); order.addWidget(self.down); left_body.addLayout(order)
        self.catalog_button = button('Takım kataloğu indir', self.download_catalog)
        self.catalog_button.setToolTip('Kaynak depodaki 7 gerçek DXF profilini ve WILA/Rolleri ürün kartlarını kişisel kütüphaneye indirir. Mevcut takımlar korunur.')
        # Library actions are occasional: they share one collapsed section so the bend
        # cards keep their height in small windows.
        dxf = QWidget(); dxf_body = QVBoxLayout(dxf); dxf_body.setContentsMargins(0, 0, 0, 0); dxf_body.setSpacing(6)
        dxf_body.addWidget(self.catalog_button)
        self.import_tool = button('DXF takım ekle…', self.tool_dialog); dxf_body.addWidget(self.import_tool)
        self.unitless = QCheckBox('Birimsiz DXF = mm'); self.unitless.setToolTip('1 çizim birimi = 1 mm. Yalnız çizimin mm ölçekte olduğunu biliyorsanız seçin.'); dxf_body.addWidget(self.unitless)
        self.dxf_section = Disclosure('Takım kütüphanesi', dxf); left_body.addWidget(self.dxf_section)
        self.splitter.addWidget(left)

        # Center: the 3D scene takes all remaining room; step/phase/angle and the legend live inside it.
        center = QWidget(); center.setMinimumWidth(180); center_body = QVBoxLayout(center); center_body.setContentsMargins(0, 0, 0, 0); center_body.setSpacing(6)
        self.viewer = SceneView(); center_body.addWidget(self.viewer, 1)
        self.splitter.addWidget(center)

        # Right: selected step → tools → positioning; optional details collapse.
        right = QWidget(); right.setMinimumWidth(210); side = QVBoxLayout(right); side.setContentsMargins(0, 0, 6, 0); side.setSpacing(10)
        side.addWidget(label('AÇINIM PLANI', 'section', wrap=False))
        self.flat_plan = FlatPlan(context.appearance); side.addWidget(self.flat_plan)
        self.flat_plan.stepClicked.connect(self.bends.setCurrentRow)
        side.addWidget(label('SEÇİLİ ADIM', 'section', wrap=False))
        self.bend_label = QLabel('Adım seçin'); self.bend_label.setProperty('role', 'title'); self.bend_label.setWordWrap(True); side.addWidget(self.bend_label)
        values = QGridLayout(); values.setHorizontalSpacing(8); values.setVerticalSpacing(6); self.values = {}
        for i, (key, title) in enumerate((('inside', 'İç açı'), ('turn', 'Dönüş'), ('radius', 'İç R'), ('length', 'Etkin boy'))):
            tile, tile_body = card(); tile_body.setContentsMargins(8, 5, 8, 5); tile_body.setSpacing(0)
            tile_body.addWidget(label(title, 'muted', wrap=False)); value = label('—', 'result', wrap=False); tile_body.addWidget(value)
            self.values[key] = value; values.addWidget(tile, i//2, i % 2)
        self.value_grid = values; self.value_tiles = [values.itemAt(i).widget() for i in range(values.count())]
        side.addLayout(values)
        # Target inside angle (− value +): geometry, check and PDF follow; CAD value stays one click away.
        target = QHBoxLayout(); target.setSpacing(6)
        target_title = label('Hedef iç açı', 'muted', wrap=False); side.addWidget(target_title)
        self.target_minus = button('−', lambda: self.nudge_target(-1)); self.target_plus = button('+', lambda: self.nudge_target(1))
        self.target = QDoubleSpinBox(); self.target.setRange(1, 179); self.target.setDecimals(1); self.target.setSingleStep(1)
        self.target.setSuffix('°'); self.target.setKeyboardTracking(False); self.target.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.target.setLocale(QLocale(QLocale.Turkish, QLocale.Turkey)); self.target.setAlignment(Qt.AlignCenter)
        self.target.setAccessibleName('Hedef iç açı'); self.target_minus.setAccessibleName('Hedef açıyı 1° azalt'); self.target_plus.setAccessibleName('Hedef açıyı 1° artır')
        self.target.setToolTip('Bu adımın bükülecek iç açısı. CAD büküm bölgesi korunur; sahne, çarpışma kontrolü ve PDF bu açıyı kullanır. Geri yaylanma hesabı değildir.')
        self.target_cad = button('CAD', self.reset_target); self.target_cad.setToolTip('Hedefi CAD iç açısına döndürür.')
        for w in (self.target_minus, self.target_plus):
            w.setFixedWidth(34)
        target.addWidget(self.target_minus); target.addWidget(self.target, 1); target.addWidget(self.target_plus); target.addWidget(self.target_cad)
        self.target.valueChanged.connect(self.set_target)
        side.addLayout(target)
        side.addWidget(separator()); side.addWidget(label('TAKIMLAR', 'section', wrap=False))
        tools = QFormLayout(); tools.setRowWrapPolicy(QFormLayout.WrapAllRows); tools.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.punch = QComboBox(); self.die = QComboBox(); self.channel = QComboBox()
        self.punch_button = button('Üst bıçak seç…', lambda: self.choose_tool('punch'))
        self.die_button = button('Alt kalıp seç…', lambda: self.choose_tool('die'))
        for title, field in (('Üst bıçak', self.punch_button), ('Alt kalıp', self.die_button)):
            field.setMinimumHeight(64); field.setIconSize(QSize(48, 52)); field.setStyleSheet('text-align: left; padding-left: 8px;')
            tools.addRow(title, field)
        # Keep the selection models/API for existing tests and saved page state;
        # the operator selects from section cards, not these hidden widgets.
        for picker in (self.punch, self.die):
            picker.setParent(self); picker.hide()
        self.channel.setMinimumContentsLength(10); self.channel.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.channel.setAccessibleName('V kanalı'); tools.addRow('V kanalı', self.channel)
        side.addLayout(tools)
        side.addWidget(separator()); side.addWidget(label('KONUMLANDIRMA', 'section', wrap=False))
        form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapAllRows); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fixed = QComboBox(); self.fixed.addItem('Ana flanş sabit', 'parent'); self.fixed.addItem('Karşı taraf sabit', 'child'); form.addRow('Tutuş', self.fixed)
        self.orientation = QComboBox(); self.orientation.addItem('0°', 0); self.orientation.addItem('180° · yeniden konumlandır', 180); form.addRow('Parça yönü', self.orientation)
        self.direction = QComboBox(); self.direction.addItem('CAD büküm yönü', False); self.direction.addItem('Büküm yönünü ters çevir', True); form.addRow('Büküm yönü', self.direction)
        side.addLayout(form)
        side.addWidget(separator())
        segment_box = QWidget(); segment_form = QFormLayout(segment_box); segment_form.setContentsMargins(0, 0, 0, 0)
        segment_form.setRowWrapPolicy(QFormLayout.WrapAllRows); segment_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.punch_segments = QLineEdit(); self.die_segments = QLineEdit()
        for title, field in (('Üst segmentler · x:L (mm)', self.punch_segments), ('Alt segmentler · x:L (mm)', self.die_segments)):
            field.setAccessibleName(title); field.setPlaceholderText('ör. -40:30; 5:35'); segment_form.addRow(title, field)
        self.apply_segments = button('Segment yerleşimini uygula', self.update_segments); segment_form.addRow(self.apply_segments)
        self.segment_section = Disclosure('Segment yerleşimi', segment_box); side.addWidget(self.segment_section)
        self.tool_info = QLabel(); self.tool_info.setWordWrap(True); self.tool_info.setTextFormat(Qt.PlainText)
        self.tool_section = Disclosure('Takım verisi', self.tool_info); side.addWidget(self.tool_section)
        details = QWidget(); details_body = QVBoxLayout(details); details_body.setContentsMargins(0, 0, 0, 0)
        self.details = QTextBrowser(); self.details.setMinimumHeight(110); self.details.setOpenExternalLinks(False); details_body.addWidget(self.details)
        scope = label(SCOPE, 'muted'); details_body.addWidget(scope)
        self.details_section = Disclosure('Kontrol ayrıntıları ve kapsam', details); side.addWidget(self.details_section)
        side.addStretch(1)
        self.right_scroll = QScrollArea(); self.right_scroll.setWidgetResizable(True); self.right_scroll.setWidget(right); self.right_scroll.setMinimumWidth(220)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.right_scroll.setFrameShape(QScrollArea.NoFrame)
        self.splitter.addWidget(self.right_scroll); self.splitter.setStretchFactor(1, 1); self.splitter.setSizes([210, 760, 290]); self.layout.addWidget(self.splitter, 1)
        self.splitter.splitterMoved.connect(self.reflow_values)

        # Transport: playback on the left, view shortcuts on the right; stacks on narrow windows.
        transport = QWidget(); playback = QHBoxLayout(transport); playback.setContentsMargins(0, 0, 0, 0); playback.setSpacing(8)
        self.previous = button('◀ Önceki', lambda: self.select_step(-1)); self.play = button('▶ Oynat', self.toggle_play, primary=True)
        self.next = button('Sonraki ▶', lambda: self.select_step(1))
        self.previous.setToolTip('Önceki büküm adımı'); self.next.setToolTip('Sonraki büküm adımı')
        self.play.setToolTip('Kontrol edilen hareketi oynatır; çarpışan karede durur.')
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(0, 0); self.slider.setAccessibleName('Hareket konumu'); self.slider.setMinimumWidth(80)
        self.speed = QComboBox(); self.speed.addItem('5 kare/s', 200); self.speed.addItem('12 kare/s', 83); self.speed.addItem('24 kare/s', 42); self.speed.setCurrentIndex(1); self.speed.setAccessibleName('Oynatma hızı; kontrol çözünürlüğünü değiştirmez')
        self.speed.setToolTip('Yalnız oynatma hızı; kontrol çözünürlüğünü değiştirmez.')
        for w in (self.previous, self.play, self.next, self.slider, self.speed):
            playback.addWidget(w, 1 if w is self.slider else 0)
        views = QWidget(); view_row = QHBoxLayout(views); view_row.setContentsMargins(0, 0, 0, 0); view_row.setSpacing(8)
        self.flat_button = button('Açınım', lambda: self.show_shape(False)); self.formed_button = button('Bitmiş form', lambda: self.show_shape(True))
        self.fit_button = button('Sığdır', self.viewer.fit)
        self.flat_button.setToolTip('Gerçek açınım; delikler ve rahatlatmalar korunur.')
        self.formed_button.setToolTip('Nominal bitmiş form; takım ve konumlandırma hareketi içermez.')
        self.fit_button.setToolTip('Sahneyi pencereye sığdırır.')
        for w in (self.flat_button, self.formed_button, self.fit_button):
            view_row.addWidget(w)
        self.transport = AdaptiveRow(transport, views, stretch=0); self.layout.addWidget(self.transport)
        status = QHBoxLayout(); status.setSpacing(10)
        self.result_badge = label('○ Kontrol bekliyor', 'muted', wrap=False); status.addWidget(self.result_badge)
        self.frame_label = ElidedLabel('Hareket kontrolü henüz çalıştırılmadı.'); self.frame_label.setProperty('role', 'muted')
        self.frame_label.setToolTip(SCOPE); status.addWidget(self.frame_label, 1)
        self.layout.addLayout(status)
        self.finish_layout()
        self.timer = QTimer(self); self.timer.timeout.connect(self.advance)
        self.bends.currentRowChanged.connect(self.select)
        for field in (self.punch, self.die, self.channel, self.fixed, self.orientation, self.direction):
            field.currentIndexChanged.connect(self.assignment_changed)
        self.slider.valueChanged.connect(self.show_frame)
        self.controls += [self.sw_button, self.demo_button, self.demo_picker, self.bends, self.up, self.down, self.import_tool,
                          self.punch, self.die, self.punch_button, self.die_button, self.target, self.target_minus, self.target_plus, self.flat_plan, self.channel, self.fixed, self.orientation, self.direction, self.punch_segments, self.die_segments, self.apply_segments]
        self.theme_changed(); self.refresh_actions()

    def resizeEvent(self, event):
        super().resizeEvent(event); self.reflow_values()

    def reflow_values(self, *_):
        if hasattr(self, 'value_grid'):
            # Two value tiles per row while they fit, one per row in a narrow side panel.
            columns = 2 if self.right_scroll.viewport().width() >= 250 else 1
            for i, tile in enumerate(self.value_tiles):
                position = (i//columns, i % columns)
                if self.value_grid.getItemPosition(self.value_grid.indexOf(tile))[:2] != position:
                    self.value_grid.addWidget(tile, *position)

    def theme_changed(self):
        if hasattr(self, 'viewer'):
            self.viewer.set_background(COLORS[self.context.appearance]['canvas'])
            self.step_cards.appearance = self.context.appearance; self.bends.viewport().update()
            self.flat_plan.appearance = self.context.appearance; self.flat_plan.update()
        if getattr(self, 'plan', None):
            self.refresh_tool_buttons()

    def refresh_actions(self):
        ready = self.plan is not None and not self.busy
        self.check_button.setEnabled(ready); self.pdf_button.setEnabled(ready and self.result is not None)
        self.video_button.setEnabled(ready and bool(self.result and self.result.frames) and self.video_writer is None)
        for control in (self.play, self.slider, self.previous, self.next):
            control.setEnabled(ready and bool(self.result and self.result.frames))
        self.flat_button.setEnabled(ready and self.flat_mesh is not None); self.formed_button.setEnabled(ready and self.formed_mesh is not None)
        self.punch_button.setEnabled(ready); self.die_button.setEnabled(ready)
        self.catalog_button.setEnabled(not self.busy)
        row = self.bends.currentRow()
        self.target_cad.setEnabled(ready and 0 <= row < len(self.plan.steps) and self.plan.steps[row].target is not None)

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
        self.timer.stop(); self.play.setText('▶ Oynat')

    def show_state(self, text, hud=None):
        """One read-out below the scene and a compact one inside it (step · phase · angle)."""
        self.frame_label.setText(text)
        state = self.result.status if self.result else None
        self.viewer.set_hud(hud if hud is not None else text, state)

    def show_result_badge(self):
        status = self.result.status if self.result else None
        symbol, text, tone = STATES[status]
        self.result_badge.setText(f'{symbol} {text}')
        self.result_badge.setProperty('role', {'danger': 'error', 'muted': 'muted'}.get(tone, tone))
        self.result_badge.style().unpolish(self.result_badge); self.result_badge.style().polish(self.result_badge)

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
        from .standard import recommended_v, standard_tools, straight_punch, single_v_die
        def plan(part):
            # A real part starts on generic market-standard tools: 88° punch, V from the 8 × t rule.
            punch, die = straight_punch(), single_v_die(recommended_v(part.thickness))
            return Plan(part, tuple(Step(b.id, punch.id, die.id, die.channels[0].id) for b in part.bends), tools()+standard_tools())
        self.load_plan(lambda stop: plan(read_active(stop)))

    def load_plan(self, factory):
        def operation(sink, stop):
            from .geometry import Geometry, mesh
            from .kinematics import step_angles
            from .tooling import load_catalog
            from .sources import manufacturer_tools, merged_catalog
            from .standard import standard_tools
            from modules.cad_converter.models import checkpoint
            plan = factory(stop); checkpoint(stop)
            library = load_catalog(self.library_path)
            plan = replace(plan, tools=merged_catalog(plan.tools, merged_catalog(standard_tools(), merged_catalog(library, manufacturer_tools()))))
            plan.validate(); geometry = Geometry(plan)
            flat = mesh(geometry.part_bodies({}), stop); formed = mesh(geometry.part_bodies(step_angles(plan, len(plan.steps)-1, 1)), stop)
            sink.put(('press_plan', (plan, flat, formed, library)))
        self.start(operation)

    def accept_plan(self, plan, flat, formed, library):
        self.generation += 1; self.plan, self.result = plan, None
        self.flat_mesh, self.formed_mesh, self.library = flat, formed, library
        self.loading = True
        self.fill_steps(plan.steps)
        for picker, kind in ((self.punch, 'punch'), (self.die, 'die')):
            picker.clear()
            for tool in plan.tools:
                if tool.kind == kind:
                    picker.addItem(tool.code+(' · DEMO' if tool.demo else ''), tool.id)
        self.loading = False; self.bends.setCurrentRow(0)
        self.refresh_steps()
        p = plan.part
        fields = [p.name, p.configuration, f'{p.thickness:g} mm', p.material, f'{len(p.bends)} büküm']
        text = ' · '.join(dict.fromkeys(f for f in fields if f))
        self.part_label.setText(('DEMO · ' if p.demo and 'DEMO' not in text else '')+text); self.part_label.setToolTip(self.part_label.text())
        self.viewer.frame = None; self.viewer.set_mesh(flat); self.show_result_badge()
        self.show_state('Açınım yüklendi. Sırayı ve takımları atayıp hareketi kontrol edin.', 'Açınım')
        self.set_status('Parça okundu; hareket kontrolü bekleniyor.'); self.refresh_actions()

    def select(self, index, seek=True):
        if self.loading or self.plan is None or not 0 <= index < len(self.plan.steps):
            return
        if seek:
            self.pause()
        self.loading = True
        step = self.plan.steps[index]; bend = next(b for b in self.plan.part.bends if b.id == step.bend)
        self.bend_label.setText(f'Adım {index+1} / {len(self.plan.steps)} · {bend.title}'); self.flat_plan.set_current(index)
        self.target.blockSignals(True); self.target.setValue(self.plan.inside(step)); self.target.blockSignals(False)
        self.target_cad.setText(f'CAD {bend.inside_angle:g}°'.replace('.', ',')); self.refresh_actions()
        for key, text in (('inside', f'{self.plan.inside(step):g}°'), ('turn', f'{self.plan.turn(step):g}°'), ('radius', f'{bend.radius:g} mm'),
                          ('length', f'{bend.length:.2f} mm')):
            self.values[key].setText(text.replace('.', ','))
        for picker, value in ((self.punch, step.punch), (self.die, step.die), (self.fixed, step.fixed_side), (self.orientation, step.orientation), (self.direction, step.reverse)):
            picker.setCurrentIndex(picker.findData(value))
        die = self.plan.tool(step.die); self.channel.clear()
        for channel in die.channels:
            self.channel.addItem(f'{channel.id} · V{channel.opening:g} / {channel.angle:g}°'.replace('.', ','), channel.id)
        self.channel.setCurrentIndex(self.channel.findData(step.channel))
        punch = self.plan.tool(step.punch)
        from .standard import default_segments
        self.punch_segments.setText(format_segments(step.punch_segments if step.punch_segments is not None else default_segments(punch, bend)))
        self.die_segments.setText(format_segments(step.die_segments if step.die_segments is not None else default_segments(die, bend)))
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
            widget.setText(tool.code+'\n'+('DEMO · ' if tool.demo else '')+'Değiştir…')
            widget.setIcon(profile_icon(tool, self.context.appearance, QSize(48, 52)))
            widget.setToolTip(f'{tool.maker} / {tool.code}\nKesit kartlarından seçmek için tıklayın.')

    def choose_tool(self, kind):
        if not self.plan or self.busy or self.bends.currentRow() < 0:
            return
        index = self.bends.currentRow(); old = self.plan.steps[index]
        current = old.punch if kind == 'punch' else old.die
        chosen_segments = old.punch_segments if kind == 'punch' else old.die_segments
        picker = ToolPicker(self.plan.tools, kind, current, channel=old.channel,
                            assigned_segments=chosen_segments, appearance=self.context.appearance,
                            settings=self.settings, parent=self, bend_length=self.plan.bend(old.bend).length)
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
            status = self.result.steps[i].status if self.result else None
            playing = self.result.frames[min(self.frame_index, len(self.result.frames)-1)].step if self.result and self.result.frames else None
            progress = None if playing is None else 'done' if i < playing else 'current' if i == playing else 'todo'
            item = self.bends.item(i)
            # Plain text stays for search, tests and assistive technology; the card paints the same facts.
            item.setText(f'{i+1}. {bend.title}'+('\n'+STATUS[status] if status else '')+('\nTakım değişimi' if change else '')
                         +('\nYeniden tutuş' if i else '')+(' · Çevir 180°' if step.orientation else '')
                         +(' · Yön ters' if step.reverse else '')+(f' · {PROGRESS[progress]}' if progress else ''))
            item.setData(CARD, dict(number=i+1, title=bend.title,
                                    detail=(f'{self.plan.inside(step):g}° iç' + (f' (CAD {bend.inside_angle:g}°)' if self.plan.inside(step) != bend.inside_angle else '')
                                            + f' · R {bend.radius:g} · {bend.length:.1f} mm').replace('.', ','),
                                    status=status, change=bool(change), regrip=bool(i), flip=bool(step.orientation),
                                    reverse=bool(step.reverse), progress=progress))
            item.setToolTip(item.text())
        self.sequence_title.setText(f'BÜKÜM SIRASI · {len(self.plan.steps)}')
        self.flat_plan.set_plan(self.plan, self.bends.currentRow())

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
            from .geometry import Geometry, scene_mesh
            from .kinematics import step_angles
            from .service import Frame
            geometry = Geometry(plan)
            bodies, _ = geometry.scene(index, step_angles(plan, index, 0))
            bend = next(b for b in plan.part.bends if b.id == plan.steps[index].bend)
            frame = Frame(index, 'approach', 0, scene_mesh(bodies, stop),
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
        self.viewer.frame = None; self.viewer.set_mesh(self.flat_mesh); self.viewer.bend_annotations.update(); self.show_result_badge()
        self.show_state('Plan değişti · önceki hareket kontrolü geçersiz. Yeniden kontrol edin.', 'Plan değişti · kontrol bekliyor')
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

    def nudge_target(self, delta):
        self.target.setValue(round(self.target.value())+delta)

    def reset_target(self):
        if self.plan and self.bends.currentRow() >= 0:
            self.set_target(None)

    def set_target(self, value):
        """Planned inside angle of the selected step; the CAD angle means 'no target'."""
        if self.loading or not self.plan:
            return
        index = self.bends.currentRow()
        if index < 0:
            return
        old = self.plan.steps[index]; bend = self.plan.bend(old.bend)
        target = None if value is None or abs(value-bend.inside_angle) < 1e-9 else round(float(value), 1)
        if target == old.target:
            return
        steps = list(self.plan.steps); steps[index] = replace(old, target=target)
        plan = self.plan.changed(steps=tuple(steps))
        try:
            plan.validate()
        except ValueError as error:
            self.set_status(str(error), True)
            self.target.blockSignals(True); self.target.setValue(self.plan.inside(old)); self.target.blockSignals(False)
            return
        self.invalidate(plan)

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
        self.apply_order(steps, j)

    def fill_steps(self, steps, current=None):
        self.bends.clear()
        for step in steps:
            item = QListWidgetItem(step.bend); item.setData(Qt.UserRole, step.bend)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled); self.bends.addItem(item)
        if current is not None:
            self.bends.setCurrentRow(current)

    def apply_order(self, steps, current):
        self.loading = True; self.fill_steps(steps, current); self.loading = False
        self.invalidate(self.plan.changed(steps=tuple(steps)))

    def dropped(self):
        """A card was dragged to a new place: same steps, new order."""
        if not self.plan:
            return
        order = [self.bends.item(i).data(Qt.UserRole) for i in range(self.bends.count())]
        if order == [s.bend for s in self.plan.steps] or sorted(order) != sorted(s.bend for s in self.plan.steps):
            return
        by_bend = {s.bend: s for s in self.plan.steps}; moved = self.bends.currentItem()
        current = self.bends.row(moved) if moved else 0
        self.apply_order([by_bend[b] for b in order], current)

    def toggle_step(self, row, field):
        """In-card ⇄ Yön / ↻ 180° buttons: same plan fields as the right panel's combos."""
        if self.loading or not self.plan or not 0 <= row < len(self.plan.steps):
            return
        old = self.plan.steps[row]
        step = replace(old, reverse=not old.reverse) if field == 'reverse' else replace(old, orientation=0 if old.orientation else 180)
        steps = list(self.plan.steps); steps[row] = step
        if self.bends.currentRow() != row:
            self.loading = True; self.bends.setCurrentRow(row); self.loading = False
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
        self.show_result_badge()
        self.select(max(0, self.bends.currentRow())); self.set_status(STATUS[result.status]); self.refresh_actions()

    def show_frame(self, index):
        if not self.result or not 0 <= index < len(self.result.frames):
            return
        self.frame_index = index; frame = self.result.frames[index]
        if self.bends.currentRow() != frame.step:
            self.loading = True; self.bends.setCurrentRow(frame.step); self.loading = False
            self.select(frame.step, seek=False)
        if any(self.bends.item(i).data(CARD).get('progress') != ('done' if i < frame.step else 'current' if i == frame.step else 'todo')
               for i in range(self.bends.count()) if self.bends.item(i).data(CARD)):
            self.loading = True; self.refresh_steps(); self.loading = False
        self.viewer.set_frame(frame)
        where = f'Adım {frame.step+1}/{len(self.plan.steps)} · {PHASES[frame.phase]} · dönüş {frame.angle:.2f}°'.replace('.', ',')
        self.show_state(where+(' · ÇARPIŞMA: '+'; '.join(' ↔ '.join(h.pair) for h in frame.hits) if frame.hits else ''),
                        where+(' · ✕ çarpışma' if frame.hits else ''))
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
            self.timer.start(self.speed.currentData()); self.play.setText('❚❚ Duraklat')

    def advance(self):
        if not self.result or self.frame_index >= len(self.result.frames)-1:
            self.pause(); return
        self.slider.setValue(self.frame_index+1)

    def select_step(self, offset):
        if self.plan:
            self.bends.setCurrentRow(min(len(self.plan.steps)-1, max(0, self.bends.currentRow()+offset)))

    def show_shape(self, formed):
        self.view_mode = 'formed' if formed else 'flat'; self.preview_pending = False
        self.pause(); self.viewer.frame = None; self.viewer.set_mesh(self.formed_mesh if formed else self.flat_mesh); self.viewer.bend_annotations.update()
        self.show_state('Nominal bitmiş form · takım/konumlandırma hareketi içermez' if formed else 'Gerçek açınım · delikler ve rahatlatmalar korunur',
                        'Bitmiş form · nominal' if formed else 'Açınım')

    def pdf_dialog(self):
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Büküm Föyü PDF', 'Bukum-Foyu.pdf', 'PDF (*.pdf)')
        if path:
            self.export_pdf(path, overwrite=True)

    def video_dialog(self):
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Büküm animasyonu', 'Bukum-Animasyonu.mp4', 'MP4 video (*.mp4)')
        if path:
            self.export_video(path if path.lower().endswith('.mp4') else path+'.mp4')

    def export_video(self, path):
        """Render the checked frames in the worker, then encode them here (Qt Multimedia lives on the GUI thread)."""
        if not self.plan or not self.result or self.video_writer is not None:
            return
        try:
            from .video import video_codec
            available = video_codec() is not None
        except ImportError:
            available = False
        if not available:   # say so before spending time on frames
            self.set_status('Bu kurulumda MP4 video kodlayıcısı yok (Qt Multimedia); video kaydedilemiyor.', True); return
        plan, result, state = self.plan, self.result, self.viewer.camera.state()
        fps = max(1, round(1000/(self.speed.currentData() or 83)))
        def operation(sink, stop):
            from .video import render_frames
            last = [0]
            def progress(done, total):
                if done == total or done-last[0] >= max(1, total//20):
                    last[0] = done; sink.put(('press_video_progress', f'Video kareleri çiziliyor · {done}/{total}'))
            sink.put(('press_video_frames', (plan.revision, path, fps, render_frames(plan, result, state, stop, progress))))
        self.start(operation)

    def encode_video(self, revision, path, fps, frames):
        from .video import VideoWriter
        if not self.plan or revision != self.plan.revision:
            self.set_status('Plan değiştiği için video kaydı iptal edildi; yeniden kontrol edip tekrar deneyin.', True); return
        try:
            writer = VideoWriter(frames, path, fps, self)
        except (ValueError, ImportError) as error:
            self.set_status(str(error), True); return
        def done(message, error=False):
            self.video_writer = None; writer.deleteLater(); self.set_status(message, error); self.refresh_actions()
        writer.finished.connect(lambda output: done(f'Video kaydedildi: {output} · {len(frames)} kare · {fps} kare/s'))
        writer.failed.connect(lambda message: done('Video kaydedilemedi: '+message, True))
        self.video_writer = writer; self.refresh_actions(); self.set_status(f'Video yazılıyor… {len(frames)} kare')
        writer.start()

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

    def download_catalog(self):
        def operation(sink, stop):
            from .sources import download_starter, manufacturer_tools, merged_catalog
            from .tooling import load_catalog, save_catalog
            from modules.cad_converter.models import checkpoint
            existing = load_catalog(self.library_path)
            incoming = download_starter(stop)+manufacturer_tools()
            library = merged_catalog(existing, incoming)
            checkpoint(stop); save_catalog(library, self.library_path)
            sink.put(('press_catalog', library))
        if self.start(operation):
            self.set_status('Kaynak takım profilleri indiriliyor…')

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
                    self.show_state(f'Adım {frame.step+1} · atanmış takımlar ve aktif eksen · KONTROL BEKLİYOR',
                                    f'Adım {frame.step+1}/{len(self.plan.steps)} · kontrol bekliyor')
            elif kind == 'press_video_progress':
                self.set_status(value)
            elif kind == 'press_video_frames':
                self.encode_video(*value)
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
            elif kind == 'press_catalog':
                from .sources import merged_catalog
                self.library = value
                if self.plan:
                    present = {t.id for t in self.plan.tools}
                    added = tuple(t for t in value if t.id not in present)
                    # Adding unassigned profiles does not invalidate a solved
                    # bend plan or trigger another expensive movement check.
                    self.plan = replace(self.plan, tools=merged_catalog(self.plan.tools, value))
                    self.loading = True
                    for tool in added:
                        picker = self.punch if tool.kind == 'punch' else self.die
                        picker.addItem(tool.code, tool.id)
                    self.loading = False
                self.set_status(f'Kütüphane hazır: {sum(t.section is not None for t in value)} gerçek kesit, '
                                f'{sum(t.section is None for t in value)} üretici bilgi kartı. Takımları kesit kartlarından seçin.')

    def hideEvent(self, event):
        self.pause(); super().hideEvent(event)
