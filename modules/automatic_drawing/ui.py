"""One drawing workbench and one editable file/configuration/assembly tree."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QPushButton, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget,
    QStyledItemDelegate, QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget)

from gui_qt.components import set_style_sheet
from gui_qt.components import (BasePage, AdaptiveRow, Disclosure, NumberSpinBox, button,
    configure_view, fit_columns, label, scroll)
from gui_qt.theme import COLORS
from .models import Options, PAPERS, STAGES, Source
from .pipeline import worker
from .outputs import write_batch_report
from .rules import CLASS_TITLES
from .preview import SheetPreview
from .coverage import COVERAGE, PASS_MEANING
from gui_qt.coverage import CoverageList


class _WheelGuard(QObject):
    """A wheel over an unfocused combo / number box scrolls the page instead of changing the value.

    Seen in the SolidWorks add-in dialog: scrolling the settings changed the projection from
    ISO first angle to third angle without any click.
    """
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel and not watched.hasFocus():
            parent = watched.parentWidget()
            if parent is not None:      # the page scrolls; the value stays
                QCoreApplication.sendEvent(parent, event)
            return True
        return False


WHEEL_GUARD = _WheelGuard()


def guard_wheel(widget):
    widget.setFocusPolicy(Qt.StrongFocus)
    widget.installEventFilter(WHEEL_GUARD)
    return widget


SOURCE_SUFFIXES = ('.sldprt', '.sldasm')
STATUS_TEXT = {'PASS': 'Başarılı', 'WARNING': 'Uyarılı', 'FAIL': 'Hatalı', 'CANCELLED': 'İptal', 'SKIPPED': 'Atlandı'}
STATUS_TONE = {'PASS': 'success', 'WARNING': 'warning', 'FAIL': 'danger', 'Hazır': 'success',
               'Analiz edildi': 'accent', 'Bekliyor': 'muted', 'Bastırılmış': 'muted'}
# The 18 pipeline stages read as three phases on the progress strip.
PHASES = (('Hazırlık', 0, 6), ('Resim', 6, 13), ('Doğrulama ve kayıt', 13, len(STAGES)))


def parse_scales(text):
    result = []
    for token in text.split(';'):
        pieces = token.strip().replace(',', '.').split(':')
        if len(pieces) != 2:
            raise ValueError('Ölçekleri 1:1;1:2;1:2,5 biçiminde girin.')
        numerator, denominator = map(float, pieces)
        if denominator <= 0 or numerator <= 0:
            raise ValueError('Ölçek payı ve paydası pozitif olmalı.')
        result.append(numerator/denominator)
    return tuple(result)


def polish(widget):
    widget.style().unpolish(widget); widget.style().polish(widget)


class ConfigurationDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return super().createEditor(parent, option, index) if index.column() == 1 else None


class Overlay(QWidget):
    """Centred empty-state message over a view's viewport; the view itself stays in place."""

    def __init__(self, view, title, detail, *actions, glyph=None):
        super().__init__(view.viewport()); self.view = view
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 16, 20, 16); layout.setSpacing(8)
        layout.addStretch()
        if glyph is not None:
            self.glyph = QLabel(); self.glyph.setAlignment(Qt.AlignCenter); layout.addWidget(self.glyph)
        self.title = label(title, 'section'); self.detail = label(detail, 'muted')
        for caption in (self.title, self.detail):
            caption.setAlignment(Qt.AlignCenter); layout.addWidget(caption)
        if actions:
            row = QHBoxLayout(); row.addStretch()
            for action in actions:
                row.addWidget(action)
            row.addStretch(); layout.addLayout(row)
        layout.addStretch()
        self.icon_name = glyph
        view.viewport().installEventFilter(self); self.setGeometry(view.viewport().rect())

    def set_colour(self, colour):
        if self.icon_name:
            from gui_qt.icons import icon
            self.glyph.setPixmap(icon(self.icon_name, colour).pixmap(QSize(44, 44)))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.setGeometry(self.view.viewport().rect())
        return super().eventFilter(watched, event)


class FlowRow(QWidget):
    """Chips left to right, wrapping onto new lines instead of clipping."""

    def __init__(self, spacing=6):
        super().__init__(); self.spacing = spacing; self.chips = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def add(self, widget):
        widget.setParent(self); self.chips.append(widget); self.relayout()

    def _place(self, width, apply=False):
        x = y = line = 0
        for chip in self.chips:
            if chip.isHidden():
                continue
            size = chip.sizeHint()
            if x and x+size.width() > width:
                x, y, line = 0, y+line+self.spacing, 0
            if apply:
                chip.setGeometry(x, y, size.width(), size.height())
            x += size.width()+self.spacing; line = max(line, size.height())
        return y+line

    def relayout(self):
        self.updateGeometry(); self._place(self.width(), True)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(width)

    def sizeHint(self):
        return QSize(400, self._place(max(self.width(), 400)))

    def resizeEvent(self, event):
        super().resizeEvent(event); self._place(self.width(), True)


class Reflow(QWidget):
    """Cards in as many equal columns as fit (``min_width`` each); ``wide`` cards span the row."""

    def __init__(self, min_width, max_columns=2, spacing=12):
        super().__init__(); self.min_width, self.max_columns = min_width, max_columns
        self.grid = QGridLayout(self); self.grid.setContentsMargins(0, 0, 0, 0); self.grid.setSpacing(spacing)
        self.items = []; self.columns = 0

    def add(self, widget, wide=False):
        self.items.append((widget, wide)); self.columns = 0; self.reflow()

    def reflow(self):
        columns = max(1, min(self.max_columns, self.width()//self.min_width if self.width() else 1))
        if columns == self.columns:
            return
        self.columns = columns
        for widget, _ in self.items:
            self.grid.removeWidget(widget)
        row = col = 0
        for widget, wide in self.items:
            if wide and col:
                row, col = row+1, 0
            self.grid.addWidget(widget, row, col, 1, columns if wide else 1, Qt.AlignTop)
            col = 0 if wide else col+1
            if wide or col >= columns:
                row, col = row+1, 0
        for c in range(self.max_columns):
            self.grid.setColumnStretch(c, 1 if c < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event); self.reflow()


class PhaseStrip(QWidget):
    """Three phase segments (Hazırlık · Resim · Doğrulama ve kayıt) filled from the stage count."""

    def __init__(self):
        super().__init__(); self.completed = 0; self.active = False; self.colours = COLORS['dark']
        self.setMinimumHeight(30); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName('Teknik resim aşamaları')

    def sizeHint(self):
        return QSize(400, 30)

    def set_state(self, completed, active):
        self.completed, self.active = completed, active; self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        c = self.colours; gap = 6; width = (self.width()-gap*(len(PHASES)-1))/len(PHASES)
        for i, (title, first, last) in enumerate(PHASES):
            x = i*(width+gap); done = max(0, min(last, self.completed)-first)/(last-first)
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(c['border']))
            painter.drawRoundedRect(x, 0, width, 5, 2.5, 2.5)
            if done:
                painter.setBrush(QColor(c['success'] if done >= 1 else c['accent']))
                painter.drawRoundedRect(x, 0, width*done, 5, 2.5, 2.5)
            current = self.active and first <= self.completed < last
            painter.setPen(QColor(c['text'] if current or done >= 1 else c['muted']))
            font = painter.font(); font.setBold(current); painter.setFont(font)
            painter.drawText(int(x), 9, int(width), self.height()-9, Qt.AlignLeft | Qt.AlignVCenter,
                             ('✓ ' if done >= 1 else '')+title)


class AutoDrawingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Otomatik teknik resim',
                         'SolidWorks parça ve montajlarından modele bağlı, düzenlenebilir teknik resimler oluşturun.')
        self.results = []
        self.batch_notice = ''
        self.source_items = {}
        self.browse = {}
        self.option_rows = {}
        self.saved = self.settings.get('automatic_drawing', {})
        if not isinstance(self.saved, dict):
            self.saved = {}
        self.analyze_button = self.action('Kontrol et', self.analyze)
        self.analyze_button.setToolTip('Seçili modeli SolidWorks’ten okur; resim oluşturmaz, modeli değiştirmez.')
        self.start_button = self.action('Resimleri oluştur', self.start, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.report_button = self.action('Rapor kaydet', self.save_report)
        self.controls.remove(self.report_button)
        self.report_button.setEnabled(False)
        self.setAcceptDrops(True)

        # ------------------------------------------------------------- sources
        left = QFrame(); left.setObjectName('drawingSources'); left.setProperty('card', True); left.setMinimumWidth(0)
        ll = QVBoxLayout(left); ll.setContentsMargins(12, 10, 12, 10); ll.setSpacing(8)
        head = QHBoxLayout(); head.setSpacing(8)
        head.addWidget(label('1 · Modeller', 'section', wrap=False)); head.addStretch()
        self.source_count = label('', 'muted', wrap=False); self.source_count.setProperty('chip', True)
        head.addWidget(self.source_count); ll.addLayout(head)
        self.add_file_button = button('Dosya ekle…', self.choose_files)
        self.add_folder_button = button('Klasör ekle…', self.choose_folder)
        self.active_button = button('Aktif dosyayı al', self.use_active)
        self.remove_button = button('Seçilileri kaldır', self.remove_sources, flat=True)
        ll.addWidget(AdaptiveRow(self.add_file_button, self.add_folder_button, self.active_button))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Dosya / bileşen', 'Konfigürasyon', 'Durum'])
        self.tree.setAccessibleName('Teknik resim kaynakları ve montaj hiyerarşisi')
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setItemDelegate(ConfigurationDelegate(self.tree))
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.setMinimumWidth(0); self.tree.setUniformRowHeights(True); self.tree.setIndentation(16)
        self.tree.setFrameShape(QFrame.NoFrame)
        fit_columns(self.tree, elastic=0, minimum=120, autofit=(1, 2),
                    settings=self.settings, key='automatic_drawing_sources')
        self.tree.itemSelectionChanged.connect(self.show_analysis)
        self.tree.itemChanged.connect(lambda *_: self.refresh_sources())
        self.empty_add = button('Dosya ekle…', self.choose_files, primary=True)
        self.empty_active = button('Aktif dosyayı al', self.use_active)
        self.tree_empty = Overlay(self.tree, 'Parça veya montaj ekleyin',
                                  'SLDPRT / SLDASM dosyalarını buraya sürükleyin ya da SolidWorks’te açık modeli alın.',
                                  self.empty_add, self.empty_active, glyph='automatic_drawing')
        ll.addWidget(self.tree, 1)
        foot = QHBoxLayout(); foot.setSpacing(8)
        self.tree_hint = label('İşaretli modellerin resmi çıkar · konfigürasyonu değiştirmek için çift tıklayın', 'muted')
        foot.addWidget(self.tree_hint, 1); foot.addWidget(self.remove_button, 0, Qt.AlignTop)
        ll.addLayout(foot)
        self.controls += [self.add_file_button, self.add_folder_button, self.active_button,
                          self.remove_button, self.tree, self.empty_add, self.empty_active]
        self.source_card = left

        # ------------------------------------------------------------- steps
        # Left: 1 · Modeller. Right: 2 · Kontrol → 3 · Ayarlar → 4 · Sonuçlar, one at a time,
        # with a "next step" box that always says what to do now and offers that button.
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(8)
        steps_row = QHBoxLayout(); steps_row.setSpacing(6)
        self.step_group = QButtonGroup(self); self.step_buttons = []
        for index, (title, tip) in enumerate((
                ('2 · Kontrol', 'Model SolidWorks’ten okunur; parça bilgisi ve pafta taslağı görünür.'),
                ('3 · Ayarlar', 'Pafta, görünüşler ve çıktılar. Ayrıntılı ayarlar “Gelişmiş” altında.'),
                ('4 · Sonuçlar', 'Oluşturulan resimler, bulgular ve SolidWorks PDF’i.'))):
            step = QPushButton(title); step.setCheckable(True); step.setProperty('step', True)
            step.setToolTip(tip); step.setAccessibleName('Adım '+title)
            self.step_group.addButton(step, index); steps_row.addWidget(step); self.step_buttons.append(step)
        steps_row.addStretch()
        self.help_button = button('Bu araç neyi yapar?', self.show_coverage, flat=True)
        steps_row.addWidget(self.help_button)
        rl.addLayout(steps_row)
        guide = QFrame(); guide.setProperty('card', True); guide.setObjectName('drawingGuide')
        gl = QHBoxLayout(guide); gl.setContentsMargins(12, 8, 12, 8); gl.setSpacing(10)
        self.guide_text = label('', None); self.guide_text.setProperty('guide', True)
        self.guide_button = button('', self._guide_action, primary=True)
        gl.addWidget(self.guide_text, 1); gl.addWidget(self.guide_button, 0, Qt.AlignVCenter)
        rl.addWidget(guide)
        self.tabs = QTabWidget(); self.tabs.setMinimumWidth(0); self.tabs.setDocumentMode(True)
        self.tabs.tabBar().hide()                      # the numbered steps above replace the tab bar
        self.step_group.idClicked.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(lambda index: self.step_buttons[index].setChecked(True))
        self.tabs.currentChanged.connect(lambda *_: self.refresh_guide())
        rl.addWidget(self.tabs, 1)

        # 2 · Kontrol: what was read and how the sheet will look, before anything is created.
        check = QWidget(); cv = QVBoxLayout(check); cv.setContentsMargins(0, 4, 0, 0); cv.setSpacing(8)
        self.facts = {}
        facts = QHBoxLayout(); facts.setSpacing(8)
        for key, title in (('class', 'Parça türü'), ('size', 'Dış ölçüler · mm'),
                           ('bodies', 'Gövdeler'), ('config', 'Konfigürasyon')):
            tile = QFrame(); tile.setProperty('card', True); tile.setProperty('fact', True)
            tl = QVBoxLayout(tile); tl.setContentsMargins(12, 6, 12, 6); tl.setSpacing(1)
            kicker = label(title.upper(), 'muted', wrap=False); kicker.setProperty('kicker', True)
            value = label('—', None); value.setProperty('factValue', True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            tl.addWidget(kicker); tl.addWidget(value); self.facts[key] = value
            facts.addWidget(tile, 1)
        cv.addLayout(facts)
        self.preview_caption = label('Taslak için önce modeli kontrol edin.', 'muted')
        cv.addWidget(self.preview_caption)
        self.sheet_preview = SheetPreview()
        self.sheet_preview.show_message('Soldan bir model seçip “Kontrol et”e basın. Pafta, ölçek ve görünüşlerin '
                                        'yeri burada, resim oluşturulmadan önce görünür.')
        cv.addWidget(self.sheet_preview, 1)
        self.draft_note = label('Taslak: kutular görünüşlerin yeri ve boyudur. Çizgiler, ölçüler, açınım ve BOM, '
                                'resim oluşturulunca gelir. Ayar değişikliği taslağa anında yansır.', 'muted')
        cv.addWidget(self.draft_note)
        self.analysis_text = QPlainTextEdit(); self.analysis_text.setReadOnly(True)
        self.analysis_text.setPlainText('Soldan bir model seçip “Kontrol et”e basın.')
        self.analysis_text.setMinimumHeight(110)
        cv.addWidget(Disclosure('Okunan model bilgilerinin tamamı', self.analysis_text))
        self.tabs.addTab(check, 'Kontrol')

        # 3 · Ayarlar: the few that matter first, the rest under "Gelişmiş".
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget); settings_layout.setContentsMargins(0, 4, 8, 10)
        settings_layout.setSpacing(10)
        self.summary = FlowRow(); self.summary_chips = []
        settings_layout.addWidget(self.summary)
        self.fields = {}
        self.cards = Reflow(360, max_columns=3)
        self.advanced_cards = Reflow(430)
        self._build_options()
        settings_layout.addWidget(self.cards)
        self.advanced = Disclosure('Gelişmiş ayarlar · şablonlar, ölçüler, montaj / BOM, dosya adı, antet',
                                   self.advanced_cards)
        settings_layout.addWidget(self.advanced)
        settings_layout.addStretch()
        settings_scroll = scroll(settings_widget)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        self.tabs.addTab(settings_scroll, 'Ayarlar')

        # 4 · Sonuçlar: counts, the list, and the real PDF exported by SolidWorks below it.
        results = QWidget(); rv = QVBoxLayout(results); rv.setContentsMargins(0, 4, 0, 0); rv.setSpacing(8)
        tiles = QHBoxLayout(); tiles.setSpacing(8); self.tiles = {}
        for key, title in (('PASS', 'Başarılı'), ('WARNING', 'Uyarılı'), ('FAIL', 'Hatalı'), ('sheets', 'Pafta')):
            tile = QFrame(); tile.setProperty('card', True); tile.setProperty('tile', key)
            tl = QVBoxLayout(tile); tl.setContentsMargins(12, 6, 12, 6); tl.setSpacing(0)
            kicker = label(title.upper(), 'muted', wrap=False); kicker.setProperty('kicker', True)
            value = label('0', None, wrap=False); value.setProperty('tileValue', True)
            tl.addWidget(kicker); tl.addWidget(value); self.tiles[key] = value; tiles.addWidget(tile, 1)
            if key == 'PASS':
                tile.setToolTip(PASS_MEANING)
        rv.addLayout(tiles)
        self.pass_meaning = label(PASS_MEANING, 'muted'); rv.addWidget(self.pass_meaning)
        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(['Dosya', 'Konfigürasyon', 'Durum', 'Pafta', 'Açıklama'])
        configure_view(self.result_table)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.itemSelectionChanged.connect(self.select_result)
        fit_columns(self.result_table, elastic=4, minimum=160, autofit=(0, 1, 2, 3),
                    settings=self.settings, key='automatic_drawing_results')
        self.results_empty = Overlay(self.result_table, 'Henüz sonuç yok',
                                     'Modelleri işaretleyip “Resimleri oluştur”a basın. '
                                     'Her dosya için SLDDRW, PDF ve doğrulama bulguları burada listelenir.')
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        pdf = QWidget(); pdv = QVBoxLayout(pdf); pdv.setContentsMargins(0, 0, 0, 0); pdv.setSpacing(4)
        self.pdf_caption = label('Listeden bir sonuç seçin; SolidWorks’ün dışa aktardığı gerçek PDF burada açılır.',
                                 'muted')
        pdv.addWidget(self.pdf_caption); pdv.addWidget(self.pdf_view, 1)
        self.preview_empty = Overlay(self.pdf_view, 'PDF önizleme',
                                     'Yukarıdaki listeden bir resim seçin.', glyph='pdf')
        result_split = QSplitter(Qt.Vertical); result_split.setChildrenCollapsible(False)
        result_split.addWidget(self.result_table); result_split.addWidget(pdf)
        result_split.setSizes([200, 400])
        rv.addWidget(result_split, 1)
        self.tabs.addTab(results, 'Sonuçlar')

        self.coverage = CoverageList(COVERAGE, 'Bu araç neyi otomatik yapar? Kısmi ve desteklenmeyen konular '
                                     'resimde sessizce atlanmış sayılmaz; elle tamamlanmalıdır.')

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False); self.splitter.setHandleWidth(10)
        self.layout.addWidget(self.splitter, 1)    # placed before filling: a moved filled tree is restyled again
        self.splitter.addWidget(left); self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1); self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([380, 900])

        # ------------------------------------------------------------- progress
        progress = QFrame(); progress.setProperty('card', True); progress.setObjectName('drawingProgress')
        pl = QVBoxLayout(progress); pl.setContentsMargins(12, 8, 12, 8); pl.setSpacing(6)
        top = QHBoxLayout()
        self.progress_label = label('SolidWorks bağlantısı kontrol / oluşturma sırasında denetlenir.', 'muted')
        top.addWidget(self.progress_label, 1)
        self.stage_count = label('', 'muted', wrap=False); top.addWidget(self.stage_count)
        pl.addLayout(top)
        self.phases = PhaseStrip(); pl.addWidget(self.phases)
        self.stage_progress = QProgressBar()
        self.stage_progress.setRange(0, len(STAGES)); self.stage_progress.setValue(0)
        self.stage_progress.setTextVisible(False); self.stage_progress.hide()   # the phase strip draws it
        pl.addWidget(self.stage_progress)
        self.layout.addWidget(progress)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(2000)
        self.log.setMaximumHeight(120)
        self.layout.addWidget(Disclosure('İşlem günlüğü', self.log))
        self.finish_layout()
        for field in self.fields.values():
            signal = (field.toggled if isinstance(field, QCheckBox) else field.currentIndexChanged
                      if isinstance(field, QComboBox) else field.valueChanged if isinstance(field, NumberSpinBox)
                      else field.textChanged)
            signal.connect(self.refresh_options)
        self.refresh_options(); self.refresh_sources(); self.refresh_results(); self.theme_changed()
        self.tabs.setCurrentIndex(0); self.step_buttons[0].setChecked(True)
        self.tree.itemChanged.connect(lambda *_: self.refresh_guide())
        self.refresh_guide()

    # ------------------------------------------------------------------ options
    def _saved(self, key, default):
        value = self.saved.get(key, default)
        if isinstance(default, bool):
            return value if isinstance(value, bool) else default
        return value if isinstance(value, type(default)) and not isinstance(value, bool) else default

    def _line(self, form, key, title, default='', placeholder=''):
        widget = QLineEdit(self._saved(key, default)); widget.setClearButtonEnabled(True)
        widget.setMinimumWidth(0); widget.setAccessibleName(title); widget.setPlaceholderText(placeholder)
        form.addRow(title, widget); self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _combo(self, form, key, title, items, default):
        widget = guard_wheel(QComboBox()); widget.setMinimumContentsLength(4)
        widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for text, value in items: widget.addItem(text, value)
        index = widget.findData(self._saved(key, default)); widget.setCurrentIndex(max(0, index))
        form.addRow(title, widget); self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _check(self, form, key, title, default, hint=''):
        widget = QCheckBox(title); widget.setChecked(self._saved(key, default))
        if hint:
            row = QWidget(); box = QVBoxLayout(row); box.setContentsMargins(0, 0, 0, 2); box.setSpacing(0)
            box.addWidget(widget)
            note = label(hint, 'muted'); note.setProperty('optionHint', True); box.addWidget(note)
            widget.setToolTip(hint); form.addRow(row); self.option_rows[key] = row
        else:
            form.addRow(widget)
        self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _path(self, form, key, title, file_filter=None, placeholder=''):
        widget = QLineEdit(self._saved(key, '')); widget.setClearButtonEnabled(True)
        widget.setMinimumWidth(0); widget.setAccessibleName(title); widget.setPlaceholderText(placeholder)
        self.fields[key] = widget; self.controls.append(widget)
        browse = button('Seç…', lambda: self.choose_path(widget, title, file_filter))
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        layout.addWidget(widget, 1); layout.addWidget(browse)
        form.addRow(title, row); self.controls.append(browse); self.browse[key] = browse

    def _form(self, title, detail, wide=False, advanced=False):
        section = QFrame(); section.setProperty('card', True); section.setProperty('settingsCard', True)
        body = QVBoxLayout(section); body.setContentsMargins(14, 12, 14, 12); body.setSpacing(8)
        body.addWidget(label(title, 'section'))
        if detail:
            body.addWidget(label(detail, 'muted'))
        form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(8); form.setContentsMargins(0, 4, 0, 0)
        body.addLayout(form); (self.advanced_cards if advanced else self.cards).add(section, wide)
        return form

    def _build_options(self):
        # ---- basic: what most drawings need
        general = self._form('Pafta', 'Kâğıt boyu, izdüşüm yöntemi ve ölçek.')
        self._combo(general, 'paper', 'Pafta boyutu', [('A3 yatay', 'A3'), ('Otomatik (parçaya göre)', 'auto'),
                    *[(p+' yatay', p) for p in PAPERS if p != 'A3'], ('Özel ölçü', 'custom')], 'A3')
        for key, title, default in (('custom_width_mm', 'Özel en · mm', 420.),
                                    ('custom_height_mm', 'Özel boy · mm', 297.)):
            spin = guard_wheel(NumberSpinBox(2)); spin.setRange(100, 5000)
            value = self.saved.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 100 <= value <= 5000:
                value = default
            spin.setValue(value); general.addRow(title, spin); self.fields[key] = spin; self.controls.append(spin)
        def custom_paper():
            custom = self.fields['paper'].currentData() == 'custom'
            for key in ('custom_width_mm', 'custom_height_mm'):
                general.setRowVisible(self.fields[key], custom)
        self.fields['paper'].currentIndexChanged.connect(custom_paper)
        custom_paper()
        self._combo(general, 'projection', 'İzdüşüm yöntemi', [('Avrupa · ISO 1. açı', 'first'),
                                                             ('Amerikan · 3. açı', 'third')], 'first')
        self._line(general, 'manual_scale_text', 'Ölçek', placeholder='Boş: otomatik · sabit için ör. 1:2')

        views = self._form('Görünüşler', 'Ön görünüş her zaman çizilir. Yanına eklenecekleri seçin.')
        for key, title, default in (('top', 'Üstten görünüş', True), ('side', 'Yandan görünüş', True),
                                    ('isometric', 'İzometrik (3B) görünüş', True)):
            self._check(views, key, title, default)
        self._check(views, 'flat_pattern', 'Sac parçada açınım', True, 'Modelde açınım varsa ayrı görünüş olarak.')
        self._check(views, 'bom', 'Montajda malzeme listesi (BOM)', True)

        output = self._form('Çıktı', 'SolidWorks resmi (SLDDRW) her zaman kaydedilir.')
        self._path(output, 'output_dir', 'Kayıt klasörü', placeholder='Boş: modelin kendi klasörü')
        self._check(output, 'pdf', 'PDF de kaydet (önizleme için gerekli)', True)
        self._check(output, 'dxf', 'DXF de kaydet (tek paftalı resimlerde)', False)
        self._combo(output, 'existing', 'Aynı adla dosya varsa', [('Yeni ad ver', 'unique'), ('Atla', 'skip')],
                    'unique')

        # ---- advanced
        templates = self._form('Şablonlar', 'Boş bırakılırsa SolidWorks’ün kendi şablonları kullanılır.', advanced=True)
        self._path(templates, 'template', 'Resim şablonu (.drwdot)', 'SolidWorks resim şablonu (*.drwdot *.DRWDOT)',
                   'SolidWorks varsayılanı')
        self._path(templates, 'sheet_format', 'Firma anteti / pafta çerçevesi (.slddrt)',
                   'SolidWorks sayfa biçimi (*.slddrt *.SLDDRT)', 'Şablondaki antet')
        self._path(templates, 'hole_table_template', 'Delik tablosu şablonu (.sldholtbt)',
                   'SolidWorks delik tablosu (*.sldholtbt *.SLDHOLTBT)', 'SolidWorks standart şablonu')
        self._path(templates, 'bom_template', 'BOM şablonu (.sldbomtbt)',
                   'SolidWorks BOM şablonu (*.sldbomtbt *.SLDBOMTBT)', 'SolidWorks varsayılanı')

        layout = self._form('Görünüş yerleşimi', 'Hangi yüzün ön görünüş olacağı ve ölçek seçenekleri.', advanced=True)
        self._combo(layout, 'main_view', 'Ön görünüş olarak', [('Otomatik seç', 'auto'), ('Ön', 'front'),
                    ('Arka', 'back'), ('Üst', 'top'), ('Alt', 'bottom'), ('Sağ', 'right'), ('Sol', 'left')], 'auto')
        self._combo(layout, 'classification', 'Parça türü', [('Otomatik', 'auto')]+[
            (title, key) for key, title in CLASS_TITLES.items() if key != 'assembly'], 'auto')
        self._line(layout, 'scales_text', 'Otomatik ölçekte denenecekler',
                   '5:1;2:1;1:1;1:2;1:2,5;1:5;1:10;1:20;1:50;1:100')

        dims = self._form('Ölçüler', 'Modelden aktarılan ölçüler ve işaretler.', advanced=True)
        for key, title, default, hint in (
            ('model_dimensions', 'Modelde “resme aktar” işaretli ölçüler', True, ''),
            ('include_unmarked', 'İşaretsiz model ölçüleri de', False, 'Kalabalık resim üretebilir.'),
            ('geometry_dimensions', 'Geometriden referans ölçüler', False, 'Dış ölçüler ve delik konumları; referans olarak.'),
            ('arrange_dimensions', 'Ölçüleri düzenle ve denetle', True, 'Çakışan ve görünüş dışına taşan ölçüler raporlanır.'),
            ('center_marks', 'Delik merkez işaretleri', True, ''),
            ('bend_lines', 'Açınımda büküm çizgileri', True, '')):
            self._check(dims, key, title, default, hint)

        assembly = self._form('Montaj ve BOM', 'Montajda hangi resimler çıkar, BOM nasıl olur.', advanced=True)
        self._combo(assembly, 'assembly_scope', 'Oluşturulacak resimler',
                    [('Yalnız seçili dosyalar / montaj', 'assembly'),
                     ('Montaj ve içindeki parçalar', 'parts'),
                     ('Montaj, alt montajlar ve parçalar', 'all')], 'assembly')
        self._combo(assembly, 'bom_type', 'BOM içeriği', [('Yalnız parçalar', 'parts'),
                    ('Üst seviye', 'top'), ('Girintili', 'indented')], 'parts')
        self._check(assembly, 'balloons', 'BOM’a bağlı balonlar', False)

        naming = self._form('Dosya adı', '{name} model adı, {configuration} konfigürasyon.', advanced=True)
        self._line(naming, 'naming', 'Dosya adı şablonu', '{name}-{configuration}')

        mapping = self._form('Antet eşlemesi', 'Model özelliği → resim özelliği. Antetteki alanlar bu eşlemeyle dolar.',
                             advanced=True)
        raw_map = self.saved.get('property_map')
        saved_map = raw_map if isinstance(raw_map, list) and 0 < len(raw_map) <= 50 and all(
            isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(s, str) for s in p)
            for p in raw_map) else Options().property_map
        self.mapping_fields = []
        for index, (source, target) in enumerate(saved_map):
            left, right = QLineEdit(source), QLineEdit(target)
            left.setPlaceholderText('Model özelliği'); right.setPlaceholderText('Resim özelliği')
            left.setAccessibleName(f'Antet {index+1} kaynak model özelliği')
            right.setAccessibleName(f'Antet {index+1} hedef resim özelliği')
            row = QWidget(); fields = QHBoxLayout(row); fields.setContentsMargins(0, 0, 0, 0); fields.setSpacing(6)
            arrow = label('→', 'muted', wrap=False)
            fields.addWidget(left, 1); fields.addWidget(arrow); fields.addWidget(right, 1)
            mapping.addRow(row); self.mapping_fields.append((left, right)); self.controls += [left, right]

    DEPENDENT = {'include_unmarked': 'model_dimensions', 'bend_lines': 'flat_pattern',
                 'bom_type': 'bom', 'bom_template': 'bom', 'balloons': 'bom'}

    def refresh_options(self, *_):
        """Dependent options follow their parent; the summary chips follow every change."""
        for key, parent in self.DEPENDENT.items():
            on = self.fields[parent].isChecked() and not self.busy
            self.fields[key].setEnabled(on)
            if key in self.browse:
                self.browse[key].setEnabled(on)
        f = self.fields
        paper = f['paper'].currentText() if f['paper'].currentData() != 'custom' else \
            f"{f['custom_width_mm'].value():g} × {f['custom_height_mm'].value():g} mm"
        scale = f['manual_scale_text'].text().strip()
        outputs = ['SLDDRW']+(['PDF'] if f['pdf'].isChecked() else [])+(['DXF'] if f['dxf'].isChecked() else [])
        views = [n for k, n in (('top', 'üst'), ('side', 'yan'), ('isometric', 'izometrik')) if f[k].isChecked()]
        chips = [paper, f['projection'].currentText(), 'Ölçek '+(scale if scale else 'otomatik'),
                 'Görünüş: ön'+(', '+', '.join(views) if views else ''), ' + '.join(outputs)]
        if f['bom'].isChecked():
            chips.append('BOM · '+f['bom_type'].currentText().lower())
        while len(self.summary_chips) < len(chips):
            chip = label('', None, wrap=False); chip.setProperty('chip', True)
            self.summary.add(chip); self.summary_chips.append(chip)
        for i, chip in enumerate(self.summary_chips):
            chip.setVisible(i < len(chips))
            if i < len(chips):
                chip.setText(chips[i])
        self.summary.relayout()
        self.refresh_draft()

    # ------------------------------------------------------------------ draft preview
    def current_info(self):
        item = self.tree.currentItem()
        while item is not None and item.data(0, Qt.UserRole+1) is None:
            item = item.parent()
        if item is not None:
            return item.data(0, Qt.UserRole+1)
        return next((i.data(0, Qt.UserRole+1) for i in self._all_items() if i.data(0, Qt.UserRole+1) is not None), None)

    def refresh_draft(self):
        if not hasattr(self, 'sheet_preview'):
            return
        info = self.current_info()
        if info is None:
            self.sheet_preview.show_message('Soldan bir model seçip “Kontrol et”e basın. Pafta, ölçek ve görünüşlerin '
                                            'yeri burada, resim oluşturulmadan önce görünür.')
            caption = 'Taslak için önce modeli kontrol edin (SolidWorks yalnız okunur, resim oluşturulmaz).'
        else:
            try:
                options = self.collect_options(save=False)
            except (ValueError, TypeError) as error:
                self.sheet_preview.show_message('Ayarlar geçersiz: '+str(error)); caption = 'Ayarları düzeltin.'
            else:
                self.sheet_preview.show_plan(info, options)
                caption = (Path(info.source.path).name+' · '+info.source.configuration+' · '
                           + (self.sheet_preview.summary() if self.sheet_preview.plans else 'sığmıyor'))
        self.preview_caption.setText(caption)

    def set_busy(self, busy):
        super().set_busy(busy)
        self.refresh_options()
        if hasattr(self, 'guide_button'):
            self.refresh_guide()

    # ------------------------------------------------------------------ guide
    def refresh_guide(self):
        """One sentence on what to do now, and the button that does it."""
        if not hasattr(self, 'guide_button'):
            return
        files = self.tree.topLevelItemCount()
        checked = len(self.selected_sources()) if files else 0
        analysed = self.current_info() is not None
        if self.busy:
            text, action = 'Çalışıyor… İlerleme aşağıda. İsterseniz “Durdur” ile kesebilirsiniz.', None
        elif not files:
            text, action = ('1. Resmi çıkarılacak parça veya montajı ekleyin: dosya seçin, sürükleyip bırakın '
                            'ya da SolidWorks’te açık modeli alın.'), ('Dosya ekle…', 'add')
        elif not checked:
            text, action = '1. Soldaki listede resmi çıkarılacak modelleri işaretleyin.', None
        elif self.results:
            text, action = (f'Bitti: {len(self.results)} sonuç. Listeden bir satır seçin, PDF aşağıda açılır. '
                            'Klasörde SLDDRW ve PDF dosyaları hazır.'), ('Sonuçlara git', 'results')
        elif not analysed:
            text, action = ('2. Modeli kontrol edin: SolidWorks’ten okunur, pafta taslağı gösterilir. Model değişmez.'),\
                ('Kontrol et', 'analyze')
        else:
            text, action = ('3. Taslak uygunsa ayarlara bir göz atın ve resimleri oluşturun. '
                            f'{checked} model işaretli.'), ('Resimleri oluştur', 'start')
        self.guide_text.setText(text)
        if action and action[1] == 'results' and self.tabs.currentIndex() == 2:
            action = None                              # already there
        self.guide_button.setVisible(action is not None)
        if action:
            self.guide_button.setText(action[0]); self.guide_button.setProperty('guideAction', action[1])
            self.guide_button.setEnabled(not self.busy)

    def _guide_action(self):
        action = self.guide_button.property('guideAction')
        if action == 'add': self.choose_files()
        elif action == 'analyze': self.analyze()
        elif action == 'start': self.start()
        elif action == 'results': self.tabs.setCurrentIndex(2)

    def show_coverage(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dialog = QDialog(self); dialog.setWindowTitle('Otomatik teknik resim neyi yapar?')
        layout = QVBoxLayout(dialog)
        area = QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QFrame.NoFrame)
        self.coverage.setParent(None); area.setWidget(self.coverage); layout.addWidget(area, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons); dialog.resize(720, 560)
        dialog.finished.connect(lambda *_: (area.takeWidget(), self.coverage.setParent(self)))
        dialog.exec()

    # ------------------------------------------------------------------ sources
    def refresh_sources(self):
        files = self.tree.topLevelItemCount()
        checked = len(self.selected_sources()) if files else 0
        self.source_count.setText(f'{files} dosya · {checked} seçili' if files else 'Boş')
        self.tree_empty.setVisible(files == 0)
        self.tree.header().setVisible(files > 0)
        self.refresh_guide()

    def _tint(self, item):
        status = item.text(2)
        colour = COLORS[self.context.appearance].get(STATUS_TONE.get(status, 'muted'))
        if colour:
            item.setForeground(2, QColor(colour))

    def dragEnterEvent(self, event):
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not self.busy and any(Path(u).suffix.lower() in SOURCE_SUFFIXES or Path(u).is_dir() for u in urls):
            event.acceptProposedAction(); self._set_dropping(True)

    def dragLeaveEvent(self, event):
        self._set_dropping(False)

    def dropEvent(self, event):
        self._set_dropping(False)
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        files = [p for p in paths if p.suffix.lower() in SOURCE_SUFFIXES and p.is_file()]
        self.add_sources(Source(str(p.resolve())) for p in files)
        folders = [p for p in paths if p.is_dir()]
        if folders and self.can_start():
            self.jobs.start(self, worker('folder', folder=str(folders[0])))
        event.acceptProposedAction()

    def _set_dropping(self, on):
        self.source_card.setProperty('dropping', on); polish(self.source_card)

    # ------------------------------------------------------------------ theme
    def theme_changed(self):
        c = COLORS[self.context.appearance]
        for overlay in (self.tree_empty, self.preview_empty):
            overlay.set_colour(c['muted'])
        self.phases.colours = c; self.phases.update()
        self.sheet_preview.colours = c; self.sheet_preview.update()
        for item in self._all_items():
            self._tint(item)
        self.refresh_results()
        set_style_sheet(self, f"""
            QFrame#drawingSources[dropping="true"] {{ border: 2px dashed {c['accent']}; }}
            QLabel[chip="true"] {{ border: 1px solid {c['border']}; border-radius: 11px; padding: 2px 10px;
                                   background: {c['input']}; }}
            QLabel[kicker="true"] {{ font-size: 10px; font-weight: 700; letter-spacing: 0.6px; }}
            QLabel[factValue="true"] {{ font-size: 15px; font-weight: 600; }}
            QLabel[tileValue="true"] {{ font-size: 22px; font-weight: 700; }}
            QFrame[tile] {{ border-left: 4px solid {c['border_strong']}; }}
            QFrame[tile="PASS"] {{ border-left-color: {c['success']}; }}
            QFrame[tile="WARNING"] {{ border-left-color: {c['warning']}; }}
            QFrame[tile="FAIL"] {{ border-left-color: {c['danger']}; }}
            QFrame[tile="sheets"] {{ border-left-color: {c['accent']}; }}
            QPushButton[segment="true"] {{ padding: 4px 12px; }}
            QPushButton[step="true"] {{ padding: 6px 16px; font-weight: 600; border-radius: 15px; }}
            QPushButton[step="true"]:checked {{ background: {c['accent']}; border-color: {c['accent']};
                                                color: {c['on_accent']}; }}
            QFrame#drawingGuide {{ border-left: 4px solid {c['accent']}; }}
            QLabel[guide="true"] {{ font-size: 13px; }}
            QPushButton[segment="true"]:checked {{ background: {c['selected']}; border-color: {c['accent']}; color: {c['text']}; }}
            QLabel[optionHint="true"] {{ font-size: 11px; padding-left: 24px; }}
            QFrame[settingsCard="true"] QLineEdit, QFrame[settingsCard="true"] QComboBox {{ min-height: 24px; }}
        """)

    def _all_items(self):
        pending = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop()
            pending.extend(item.child(i) for i in range(item.childCount()))
            yield item

    # ------------------------------------------------------------------ results
    def refresh_results(self):
        counts = {key: sum(r.status == key for r in self.results) for key in ('PASS', 'WARNING', 'FAIL')}
        for key, value in counts.items():
            self.tiles[key].setText(str(value))
        self.tiles['sheets'].setText(str(sum(len(r.sheets) for r in self.results)))
        self.results_empty.setVisible(not self.results)
        self.result_table.horizontalHeader().setVisible(bool(self.results))
        self.tabs.setTabText(2, f'Sonuçlar · {len(self.results)}' if self.results else 'Sonuçlar')
        self.step_buttons[2].setText(f'4 · Sonuçlar · {len(self.results)}' if self.results else '4 · Sonuçlar')
        self.preview_empty.setVisible(self.pdf_document.pageCount() == 0)
        self.refresh_guide()

    def choose_path(self, field, title, file_filter):
        if file_filter:
            path, _ = QFileDialog.getOpenFileName(self, title, field.text(), file_filter)
        else:
            path = QFileDialog.getExistingDirectory(self, title, field.text())
        if path: field.setText(path)

    def options(self):
        return self.collect_options(save=True)

    def collect_options(self, save=True):
        data, saved = {}, {}
        for key, field in self.fields.items():
            value = (field.isChecked() if isinstance(field, QCheckBox) else field.currentData()
                     if isinstance(field, QComboBox) else field.value()
                     if isinstance(field, NumberSpinBox) else field.text().strip())
            saved[key] = value
            if not key.endswith('_text'):
                data[key] = value
        data['scales'] = parse_scales(saved['scales_text'])
        text = saved['manual_scale_text']
        data['manual_scale'] = parse_scales(text)[0] if text else None
        if text and len(parse_scales(text)) != 1:
            raise ValueError('Manuel ölçek için yalnız bir oran girin.')
        data['property_map'] = tuple((left.text().strip(), right.text().strip()) for left, right in self.mapping_fields)
        saved['property_map'] = list(data['property_map'])
        options = Options(**data).validate()
        if save:
            self.settings.set('automatic_drawing', saved)
        return options

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'SolidWorks kaynakları', '',
            'SolidWorks (*.sldprt *.SLDPRT *.sldasm *.SLDASM)')
        self.add_sources(Source(str(Path(path).resolve())) for path in paths)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Kaynak klasör')
        if path and self.can_start():
            self.jobs.start(self, worker('folder', folder=path))

    def use_active(self):
        if self.can_start():
            self.jobs.start(self, worker('analyze'))

    def add_sources(self, sources):
        if self.busy: return
        self.tree.blockSignals(True)
        try:
            for source in sources:
                if source.key in self.source_items:
                    continue
                item = QTreeWidgetItem([Path(source.path).name, source.configuration, 'Bekliyor'])
                item.setData(0, Qt.UserRole, source); item.setToolTip(0, source.path)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
                item.setCheckState(0, Qt.Checked); self._tint(item)
                self.tree.addTopLevelItem(item); self.source_items[source.key] = item
        finally:
            self.tree.blockSignals(False)
        self.refresh_sources()

    def selected_sources(self):
        sources = {}
        pending = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop(0)
            pending.extend(item.child(i) for i in range(item.childCount()))
            original = item.data(0, Qt.UserRole)
            if item.checkState(0) == Qt.Checked and isinstance(original, Source) and original.path:
                source = Source(original.path, item.text(1).strip())
                sources.setdefault(source.key, source)
        return tuple(sources.values())

    def remove_sources(self):
        if self.busy: return
        for item in self.tree.selectedItems():
            if item.parent() is not None:
                item.setCheckState(0, Qt.Unchecked)
                continue
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self.source_items = {key: item for key, item in self.source_items.items()
                             if item.treeWidget() is self.tree}
        self.refresh_sources()

    def analyze(self):
        if not self.can_start(): return
        sources = self.selected_sources()
        if not sources:
            self.set_status('Analiz edilecek dosyaları işaretleyin veya aktif dosyayı alın.', True)
            return
        self.jobs.start(self, worker('analyze', sources))

    def start(self):
        if not self.can_start(): return
        try:
            sources, options = self.selected_sources(), self.options()
            if not sources:
                raise ValueError('Teknik resmi oluşturulacak dosyaları işaretleyin.')
            self.pdf_document.close()
            self.results.clear(); self.result_table.setRowCount(0); self.refresh_results()
            self.report_button.setEnabled(False)
            self.stage_progress.setValue(0); self.log.clear()
            self.batch_notice = ''
            self.jobs.start(self, worker('generate', sources, options))
        except (ValueError, OSError, TypeError) as error:
            self.set_status(str(error), True)

    def _analysis_item(self, info):
        self.tree.blockSignals(True)
        try:
            self._fill_analysis_item(info)
        finally:
            self.tree.blockSignals(False)
        self.refresh_sources(); self.show_analysis()

    def _fill_analysis_item(self, info):
        item = self.source_items.get(info.source.key) or self.source_items.pop((info.source.key[0], ''), None)
        if item is None:
            item = next((candidate for candidate in self.source_items.values()
                         if candidate.data(0, Qt.UserRole).key[0] == info.source.key[0] and
                         candidate.text(1) == info.source.configuration), None)
        if item is not None:
            self.source_items = {key: value for key, value in self.source_items.items() if value is not item}
        if item is None:
            item = QTreeWidgetItem()
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            item.setCheckState(0, Qt.Checked); self.tree.addTopLevelItem(item)
        self.source_items[info.source.key] = item
        item.setText(0, Path(info.source.path).name); item.setText(1, info.source.configuration)
        item.setText(2, 'Analiz edildi'); item.setToolTip(0, info.source.path); self._tint(item)
        item.setData(0, Qt.UserRole, info.source); item.setData(0, Qt.UserRole+1, info)
        item.takeChildren()
        pending = [(item, info.tree.children if info.tree else ())]
        while pending:
            parent, children = pending.pop()
            for node in children:
                child = QTreeWidgetItem([node.name, node.source.configuration,
                                        {'ready': 'Hazır', 'suppressed': 'Bastırılmış'}.get(node.state, node.state)])
                child.setData(0, Qt.UserRole, node.source); child.setToolTip(0, node.source.path+'\n'+node.detail)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                if node.state not in ('ready', 'hidden'):
                    child.setFlags(child.flags() & ~Qt.ItemIsEnabled)
                self._tint(child)
                parent.addChild(child); pending.append((child, node.children))
        item.setExpanded(True)
        self.tree.setCurrentItem(item)

    def show_analysis(self):
        item = self.tree.currentItem()
        info = item.data(0, Qt.UserRole+1) if item is not None else None
        if info is None:
            self.refresh_draft(); return
        lines = [info.title, info.source.path, 'Konfigürasyon: '+info.source.configuration,
                 'SolidWorks API: '+info.revision, 'Sınıf: '+CLASS_TITLES.get(info.classification, info.classification),
                 info.classification_reason, 'Dış ölçüler · mm: '+' × '.join(f'{v:g}' for v in info.size_mm),
                 f'Katı gövde: {info.body_count} · Sac gövde: {info.sheet_body_count}',
                 'Kaynak birim: '+info.source_unit, '', 'Model özellikleri:']
        lines += [f'{key}: {value}' for key, value in info.properties.items()]
        lines += ['', 'Unsur türleri:']+[f'{key}: {value}' for key, value in info.feature_types.items()]
        if info.sheet_bodies:
            lines += ['', 'Sac gövdeleri / açınım eşleşmeleri:']
            for row in info.sheet_bodies:
                thickness = f'{row.thickness_mm:g} mm' if row.thickness_mm is not None else 'Kalınlık okunamadı'
                lines.append(f'{row.label} · {row.name} · {thickness} · {row.material or "Malzeme okunamadı"}')
                lines.append('  Cut List: '+(row.cut_list or 'Doğrulanamadı')+
                             ' · Açınım: '+(', '.join(row.configurations) if row.ready else 'Doğrulanamadı'))
        lines += ['', *info.warnings]
        self.analysis_text.setPlainText('\n'.join(lines))
        self.facts['class'].setText(CLASS_TITLES.get(info.classification, info.classification))
        self.facts['size'].setText(' × '.join(f'{v:g}' for v in info.size_mm) or '—')
        self.facts['bodies'].setText(f'{info.body_count} katı · {info.sheet_body_count} sac')
        self.facts['config'].setText(info.source.configuration or '—')
        for value in self.facts.values():
            value.setToolTip(value.text())
        self.refresh_draft()

    def show_result(self, result):
        self.results = [r for r in self.results if r.source.key != result.source.key]+[result]
        sorting = self.result_table.isSortingEnabled()
        self.result_table.setSortingEnabled(False)     # rows must not move while they are filled
        self.result_table.setRowCount(len(self.results))
        for row, value in enumerate(self.results):
            detail = '\n'.join(f.text for f in value.findings) or 'Temel yapısal doğrulamalar geçti.'
            for col, text in enumerate((Path(value.source.path).name, value.source.configuration,
                                        STATUS_TEXT.get(value.status, value.status), str(len(value.sheets)), detail)):
                cell = QTableWidgetItem(text); cell.setToolTip(text)
                if col == 2:
                    colour = COLORS[self.context.appearance].get(STATUS_TONE.get(value.status, ''))
                    if colour:
                        cell.setForeground(QColor(colour))
                cell.setData(Qt.UserRole, row)
                self.result_table.setItem(row, col, cell)
        self.result_table.setSortingEnabled(sorting)
        self.refresh_results()
        if result.analysis:
            self._analysis_item(result.analysis)
        self.log.appendPlainText(f'{result.status} · {result.source.path} · {result.stage}')
        for finding in result.findings: self.log.appendPlainText(f'{finding.severity}: {finding.text}')

    def select_result(self):
        cell = self.result_table.item(self.result_table.currentRow(), 0)
        row = cell.data(Qt.UserRole) if cell is not None else None
        if not isinstance(row, int) or not 0 <= row < len(self.results): return
        result = self.results[row]
        self.pdf_document.close()
        path = result.outputs.get('pdf')
        if path and Path(path).is_file():
            self.pdf_document.load(path)
            self.pdf_caption.setText(Path(path).name+' · SolidWorks’ten alınan PDF')
        else:
            self.pdf_caption.setText('Bu sonuç için PDF oluşturulmadı. SLDDRW / rapor ayrıntılarını kontrol edin.')
        self.refresh_results()

    def save_report(self):
        if not self.results: return
        path, _ = QFileDialog.getSaveFileName(self, 'Teknik resim işlem raporu', 'GOKWORKS-teknik-resim.json',
                                             'JSON (*.json)')
        if path:
            try:
                write_batch_report(path, self.results); self.set_status('İşlem raporu kaydedildi.')
            except (OSError, ValueError) as error:
                self.set_status(str(error), True)

    def handle_events(self, events):
        super().handle_events(events)
        for kind, value in events:
            if kind == 'drawing_sources':
                # The worker is still finishing; this is an inventory update, not user input.
                busy, self.busy = self.busy, False
                try: self.add_sources(value)
                finally: self.busy = busy
            elif kind == 'drawing_analysis':
                self._analysis_item(value); self.tabs.setCurrentIndex(0); self.refresh_guide()
                self.set_status('Model analizi tamamlandı.')
            elif kind == 'drawing_analysis_error':
                self.set_status(value['error'], True); self.log.appendPlainText(value['error'])
            elif kind == 'drawing_progress':
                self.stage_progress.setValue(value['completed'])
                self.phases.set_state(value['completed'], True)
                self.stage_count.setText(f"{value['completed']} / {value['total']} aşama")
                self.progress_label.setText(Path(value['source'].path).name+' · '+value['stage'])
                self.progressChanged.emit(value['completed'], value['total'])
            elif kind == 'drawing_result':
                self.show_result(value)
            elif kind == 'drawing_notice':
                self.batch_notice = value
                self.log.appendPlainText(value); self.set_status(value, True)
            elif kind == 'drawing_done':
                self.report_button.setEnabled(bool(self.results))
                counts = {status: sum(r.status == status for r in value)
                          for status in ('PASS', 'WARNING', 'FAIL', 'CANCELLED', 'SKIPPED')}
                summary = ' · '.join(f'{count} {name}' for name, count in counts.items())
                self.phases.set_state(self.stage_progress.value(), False)
                self.set_status(summary+('\n'+self.batch_notice if self.batch_notice else ''),
                                error=bool(counts['FAIL'] or self.batch_notice))
                self.tabs.setCurrentIndex(2)

    def job_finished(self):
        self.report_button.setEnabled(bool(self.results))
