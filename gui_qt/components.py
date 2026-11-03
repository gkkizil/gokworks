"""Shared Qt Widgets: forms, persistent workspaces and model-backed results."""

from shared.files import write_csv_atomic
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import Qt, QTimer, Signal, QUrl, QSize, QEvent, QObject, QPointF
from PySide6.QtGui import QCursor, QDesktopServices, QKeySequence, QShortcut, QPainter, QPalette, QColor
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QComboBox, QCheckBox, QPushButton, QScrollArea,
    QFileDialog, QTableView, QTreeView, QHeaderView, QAbstractItemView,
    QTabWidget, QPlainTextEdit, QDialog, QDialogButtonBox, QApplication, QToolTip,
    QToolButton, QToolBar, QBoxLayout, QMenu, QSplitter, QSizePolicy, QListView,
    QDoubleSpinBox, QStyledItemDelegate)

from .models import Column, TableModel, FilterProxy, LABELS
from .theme import COLORS, SPACING


def label(text='', role=None, *, wrap=True):
    widget = QLabel(text)
    widget.setWordWrap(wrap)
    widget.setMinimumWidth(0)
    if role:
        widget.setProperty('role', role)
    return widget


class ElidedLabel(QLabel):
    """Single-line shell text that yields space to controls, retaining its full text."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.setFont(self.font())
        painter.drawText(self.contentsRect(), self.alignment(),
                         self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.contentsRect().width()))


class ViewEmptyState(QWidget):
    """One lightweight overlay; the underlying model/view remains intact."""
    def __init__(self, view, reset, hint):
        super().__init__(view.viewport())
        self.view, self.hint = view, hint
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10); layout.addStretch()
        self.title = label('', 'section'); self.detail = label('', 'muted')
        for caption in (self.title, self.detail):
            caption.setAlignment(Qt.AlignCenter)
            caption.setTextFormat(Qt.PlainText)
            layout.addWidget(caption)
        self.reset = button('Filtreleri temizle', reset)
        layout.addWidget(self.reset, alignment=Qt.AlignHCenter); layout.addStretch()
        view.viewport().installEventFilter(self)
        self.setGeometry(view.viewport().rect())

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.setGeometry(self.view.viewport().rect())
        return super().eventFilter(watched, event)

    def show_state(self, *, empty, filtered, busy):
        self.title.setText('Eşleşen dosya yok' if filtered else 'İşlem sürüyor…' if busy else 'Dosyalar burada görünecek')
        self.detail.setText('Arama veya durum filtresini temizleyerek tüm dosyaları gösterin.' if filtered
                            else 'Dosyalar hazırlanıyor. İşlem durumu alt çubukta gösterilir.' if busy
                            else self.hint)
        self.reset.setVisible(filtered)
        self.setVisible(empty)


def button(text, callback=None, *, primary=False, destructive=False, flat=False):
    """Design-system button: secondary by default; primary, destructive or flat."""
    widget = QPushButton(text)
    if callback:
        widget.clicked.connect(callback)
    widget.setProperty('primary', primary)
    if destructive:
        widget.setProperty('destructive', True)
    if flat:
        widget.setProperty('flat', True)
    return widget


def toggle_icon(appearance):
    """Check-box icon for an on/off option button: empty when off, ticked when on."""
    from PySide6.QtGui import QIcon, QPixmap, QPen
    from .theme import COLORS
    colors = COLORS.get(appearance, next(iter(COLORS.values())))
    icon = QIcon()
    for state, checked in ((QIcon.Off, False), (QIcon.On, True)):
        for scale in (1, 2):
            size = 16 * scale
            pixmap = QPixmap(size, size); pixmap.setDevicePixelRatio(scale); pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
            if checked:
                painter.setPen(Qt.NoPen); painter.setBrush(QColor(colors['accent']))
                painter.drawRoundedRect(1.5, 1.5, 13, 13, 3, 3)
                pen = QPen(QColor(colors['on_accent']), 2); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen); painter.drawPolyline([QPointF(4.5, 8.2), QPointF(7, 10.7), QPointF(11.6, 5.4)])
            else:
                painter.setPen(QPen(QColor(colors['muted']), 1.4)); painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(2, 2, 12, 12, 3, 3)
            painter.end()
            icon.addPixmap(pixmap, QIcon.Normal, state)
    return icon


def toggle_button(text, appearance='dark', *, checked=False):
    """Design-system on/off option shown as a button: clearer than a bare check box
    when it changes what the neighbouring action buttons do."""
    widget = QPushButton(text)
    widget.setCheckable(True); widget.setChecked(checked)
    widget.setProperty('toggle', True)
    widget.setIcon(toggle_icon(appearance))
    return widget


def separator(vertical=False):
    """A 1 px rule that separates regions instead of nesting another card."""
    line = QFrame()
    line.setProperty('separator', True)
    line.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


def section_header(title, *trailing):
    """Pane heading: semibold title on the left, optional compact controls right."""
    row = QWidget(); layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(4)
    caption = label(title, 'section', wrap=False)
    layout.addWidget(caption, 1)
    for widget in trailing:
        layout.addWidget(widget)
    row.caption = caption
    return row


def card(title=None):
    widget = QFrame()
    widget.setProperty('card', True)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)
    if title:
        layout.addWidget(label(title, 'section'))
    return widget, layout


class Disclosure(QWidget):
    """Optional controls stay alive and retain values when their section closes."""
    expandedChanged = Signal(bool)

    def __init__(self, title, content, parent=None, *, expanded=False):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(8)
        self.toggle = QToolButton(); self.toggle.setText(title)
        self.toggle.setCheckable(True); self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setProperty('disclosure', True)
        self.content = content
        layout.addWidget(self.toggle, alignment=Qt.AlignLeft); layout.addWidget(content)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(expanded)

    def is_expanded(self):
        return self.toggle.isChecked()

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        changed = self.toggle.isChecked() != expanded
        blocked = self.toggle.blockSignals(True); self.toggle.setChecked(expanded); self.toggle.blockSignals(blocked)
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setAccessibleDescription('Açık' if expanded else 'Kapalı')
        # Button toggles and programmatic changes share one notification.
        if changed or self.sender() is self.toggle: self.expandedChanged.emit(expanded)


class StableScrollArea(QScrollArea):
    """QScrollArea that cannot recurse on its own content resize.

    Word-wrapped labels make content height depend on width. When the vertical
    scroll bar appears it narrows the viewport, which changes the height again;
    at some window widths Qt re-enters its resize handling until the native
    stack overflows. Nested passes are skipped; the outer pass and the next
    resize/layout event settle the geometry.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._resizing = False

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Resize:
            return super().eventFilter(watched, event)
        if self._resizing:
            return False
        self._resizing = True
        try:
            return super().eventFilter(watched, event)
        finally:
            self._resizing = False


def scroll(widget):
    area = StableScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setMinimumWidth(0)
    return area


def configure_view(view):
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setSelectionMode(QAbstractItemView.SingleSelection)
    view.setSortingEnabled(True)
    view.setUniformRowHeights(True) if isinstance(view, QTreeView) else view.verticalHeader().setVisible(False)
    view.setTextElideMode(Qt.ElideMiddle)
    header = view.header() if isinstance(view, QTreeView) else view.horizontalHeader()
    header.setDefaultSectionSize(140)
    header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.setHighlightSections(False)
    if isinstance(view, QTableView):
        from .theme import ROW_HEIGHT
        view.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        view.setShowGrid(False)
        view.setWordWrap(False)
    view.setMinimumWidth(0)
    fit_columns(view, minimum=80)
    return view


class PathPicker(QWidget):
    changed = Signal(str)

    def __init__(self, text='', *, folder=True, title='Klasör seç', parent=None):
        super().__init__(parent)
        self.folder, self.dialog_title = folder, title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.entry = QLineEdit(str(text))
        self.entry.setAccessibleName(title)
        self.entry.setPlaceholderText(title)
        self.entry.setClearButtonEnabled(True)
        self.choose = button('Klasör seç' if folder else 'Dosya seç', self.browse)
        self.choose.setAccessibleName(title)
        self.choose.setToolTip(title)
        layout.addWidget(self.entry, 1)
        layout.addWidget(self.choose)
        self.entry.textChanged.connect(self.changed)

    def text(self):
        return self.entry.text().strip()

    def setText(self, value):
        self.entry.setText(str(value))

    def browse(self):
        if self.folder:
            path = QFileDialog.getExistingDirectory(self, self.dialog_title, self.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, self.dialog_title, self.text(),
                                                 'SolidWorks (*.SLDASM *.sldasm *.SLDPRT *.sldprt *.SLDDRW *.slddrw)')
        if path:
            self.setText(path)


class ValueForm(QWidget):
    changed = Signal(str)

    def __init__(self, settings, prefix, parent=None):
        super().__init__(parent)
        self.settings, self.prefix = settings, prefix
        self.fields = {}
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(8)
        self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    def _bind(self, key, widget, default, signal):
        self.fields[key] = widget
        widget.setObjectName(f'{self.prefix}{key}')
        if isinstance(widget,(QLineEdit,QComboBox)): widget.setMinimumWidth(112)
        caption = self.form.labelForField(widget)
        widget.setAccessibleName(caption.text() if caption is not None else widget.text() if isinstance(widget,QCheckBox) else key)
        signal.connect(lambda *args, key=key: self._changed(key))
        return widget

    def _changed(self, key):
        self.settings.set(self.prefix + key, self.value(key))
        self.changed.emit(key)

    def text(self, key, title, default=''):
        widget = QLineEdit(str(self.settings.get(self.prefix + key, default)))
        try:
            float(str(default).replace(',','.'))
            # Numbers align right like a technical table; a clear icon would
            # only add noise beside a short numeric value.
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        except (ValueError,TypeError):
            widget.setClearButtonEnabled(True)
        self.form.addRow(label(title), widget)
        return self._bind(key, widget, default, widget.textChanged)

    def combo(self, key, title, choices, default=None, *, editable=False):
        choices = list(choices)
        default = choices[0] if default is None else default
        value = str(self.settings.get(self.prefix + key, default))
        widget = QComboBox()
        widget.setEditable(editable)
        widget.addItems([str(item) for item in choices])
        widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        widget.setMinimumContentsLength(8)
        widget.setCurrentText(value if editable or value in choices else str(default))
        self.form.addRow(label(title), widget)
        return self._bind(key, widget, default, widget.currentTextChanged)

    def check(self, key, title, default=False, *, persist=True):
        widget = QCheckBox(title)
        widget.setChecked(self.settings.get(self.prefix + key, default) is True if persist else default)
        self.form.addRow(widget)
        if persist:
            return self._bind(key, widget, default, widget.toggled)
        self.fields[key] = widget
        widget.toggled.connect(lambda: self.changed.emit(key))
        return widget

    def path(self, key, title, default='', *, folder=True):
        widget = PathPicker(self.settings.get(self.prefix + key, default), folder=folder, title=title)
        self.form.addRow(label(title), widget)
        return self._bind(key, widget, default, widget.changed)

    def value(self, key):
        widget = self.fields[key]
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text()

    def values(self):
        return {key: self.value(key) for key in self.fields}

    def set_value(self, key, value):
        widget = self.fields[key]
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        else:
            widget.setText(str(value))

    def show_field(self, key, visible):
        self.form.setRowVisible(self.fields[key], visible)

    def stack_fields(self):
        """Labels above inputs keep the narrow transfer column readable."""
        self.form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        for widget in self.fields.values():
            if isinstance(widget, PathPicker):
                widget.choose.setText('Seç…')
                widget.choose.setToolTip(widget.dialog_title)


class TransferWorkspace(QSplitter):
    """Two persistent vertical columns: source/commands and full-height results."""
    def __init__(self, page, source, results):
        super().__init__(Qt.Horizontal)
        self.setObjectName('transferWorkspace')
        self.setChildrenCollapsible(False); self.setHandleWidth(6)
        self.source_column = QWidget()
        self.source_column.setMinimumWidth(220); self.source_column.setMaximumWidth(400)
        body = QVBoxLayout(self.source_column); body.setContentsMargins(0,0,0,0); body.setSpacing(8)
        self.source_scroll = scroll(source)
        self.source_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.addWidget(self.source_scroll,1)
        # Commands stay in the contextual strip at the top, independent of
        # source scrolling and consistent across all transfer workbenches.
        results.setMinimumWidth(0)
        self.addWidget(self.source_column); self.addWidget(results)
        self.setStretchFactor(0,0); self.setStretchFactor(1,1)
        self._preferred_source_width = 330
        self._fitting_columns = False
        self.setSizes([330,850])
        self.splitterMoved.connect(self._remember_width)

    def _remember_width(self,position,index):
        if not self._fitting_columns:
            self._preferred_source_width = self.sizes()[0]

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # Keep the result tools usable at the application's minimum window size.
        # Remember the user's divider position so widening restores their layout.
        self._fitting_columns = True
        try:
            maximum = min(400,max(220,self.width()-self.handleWidth()-320))
            self.source_column.setMaximumWidth(maximum)
            width = min(maximum,self._preferred_source_width)
            self.setSizes([width,max(0,self.width()-self.handleWidth()-width)])
        finally:
            self._fitting_columns = False


class SearchToolbar(QWidget):
    """Search above commands when the results column is narrow."""
    def __init__(self, search, commands):
        super().__init__()
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.box = QBoxLayout(QBoxLayout.TopToBottom,self)
        self.box.setContentsMargins(0,0,0,0); self.box.setSpacing(6)
        self.box.addWidget(search,1)
        tools = QWidget(); row = QHBoxLayout(tools)
        row.setContentsMargins(0,0,0,0); row.setSpacing(6)
        for command in commands: row.addWidget(command)
        self.box.addWidget(tools)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.box.setDirection(QBoxLayout.TopToBottom if self.width()<600 else QBoxLayout.LeftToRight)


class SourceFileProxy(FilterProxy):
    def data(self,index,role=Qt.DisplayRole):
        if role==Qt.DisplayRole:
            row = super().data(index,Qt.UserRole)
            if row: return row.get('source_label') or PureWindowsPath(str(row.get('source',''))).name
        return super().data(index,role)


class SourceFiles(QWidget):
    """A virtual source inventory backed by the existing export model."""
    def __init__(self,results):
        super().__init__()
        body=QVBoxLayout(self); body.setContentsMargins(0,0,0,0); body.setSpacing(6)
        self.counter=label('Kaynak dosyalar · 0','section'); body.addWidget(self.counter)
        self.search=QLineEdit(); self.search.setPlaceholderText('Kaynak dosya ara…')
        self.search.setClearButtonEnabled(True); self.search.setAccessibleName('Kaynak dosyalarda ara')
        body.addWidget(self.search)
        self.proxy=SourceFileProxy(self); self.proxy.setSourceModel(results.model)
        self.view=QListView(); self.view.setModel(self.proxy); self.view.setUniformItemSizes(True)
        self.view.setMinimumWidth(0); self.view.setMinimumHeight(96)
        self.view.setTextElideMode(Qt.ElideMiddle); self.view.setAlternatingRowColors(True)
        self.view.setAccessibleName('Kaynak klasörde bulunan dosyalar')
        self.view.setToolTip('Kaynak klasördeki uygun dosyalar aktarılır. Bir dosyaya tıklayarak sağdaki durumunu görebilirsiniz.')
        body.addWidget(self.view,1)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(100)
        self.search.textChanged.connect(lambda:self.timer.start())
        self.timer.timeout.connect(lambda:self.proxy.set_query(self.search.text()))
        def select(index):
            source_index=self.proxy.mapToSource(index)
            target=results.proxy.mapFromSource(source_index)
            if source_index.isValid() and not target.isValid():
                results.clear_filters()
                target=results.proxy.mapFromSource(source_index)
            if target.isValid():
                results.tabs.setCurrentIndex(0); results.table.setCurrentIndex(target); results.table.scrollTo(target)
        self.view.clicked.connect(select)
        def count(*args):
            total=results.model.rowCount(); self.counter.setText(f'Kaynak dosyalar · {total}')
            if not total:
                self.search.clear(); self.timer.stop(); self.proxy.set_query('')
        for signal in (results.model.modelReset,results.model.rowsInserted,results.model.rowsRemoved): signal.connect(count)


class BasePage(QWidget):
    statusChanged = Signal(str, bool)
    progressChanged = Signal(int, int)

    def __init__(self, context, title, description):
        super().__init__()
        self.context, self.settings, self.jobs = context, context.settings, context.jobs
        self.busy = False
        self.controls = []
        self.command_controls = []
        self.status_text = ''
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 8, 12, 8)
        self.layout.setSpacing(8)
        heading = QBoxLayout(QBoxLayout.LeftToRight)
        self.heading = heading
        captions = QVBoxLayout()
        captions.setSpacing(1)
        self.title_label = label(title, 'title'); self.description_label = label(description, 'subtitle')
        self.title_label.setToolTip(description)
        captions.addWidget(self.title_label); captions.addWidget(self.description_label)
        heading.addLayout(captions, 1)
        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0,0,0,0); self.actions.setSpacing(4)
        self.actions.setAlignment(Qt.AlignRight)
        self.command_bar = QToolBar(); self.command_bar.setObjectName('moduleCommands')
        self.command_bar.setMovable(False); self.command_bar.setFloatable(False)
        self.command_bar.setAccessibleName(title+' komutları')
        self.action_host = QWidget(); self.action_host.setLayout(self.actions)
        self.command_bar.addWidget(self.action_host)
        heading.addWidget(self.command_bar)
        self.layout.addLayout(heading)
        # One hairline separates the module header from its workspace.
        self.header_rule = separator(); self.layout.addWidget(self.header_rule)
        self.status = label('Hazır', 'muted'); self.status.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep command labels readable instead of squeezing a long heading and
        # several actions into the same narrow row. Nesting adds an inline
        # project field to its header and deliberately manages that layout.
        if self.heading.count() == 2:
            required = self.title_label.fontMetrics().horizontalAdvance(self.title_label.text())+self.actions.sizeHint().width()+40
            self.heading.setDirection(QBoxLayout.TopToBottom if self.width()-32 < required else QBoxLayout.LeftToRight)

    def action(self, title, callback, *, primary=False, locked=True):
        widget = button(title, callback, primary=primary)
        key=title.casefold()
        name=('stop' if 'durdur' in key else 'copy' if 'kopyala' in key else
              'search' if 'tara' in key or 'oku' in key else
              'play' if primary else 'export' if 'rapor' in key or 'kaydet' in key else
              'info' if 'yardım' in key else 'folder' if 'proje' in key else '')
        widget.setProperty('commandIcon',name);widget.setIconSize(QSize(16,16))
        self.command_controls.append(widget)
        self.refresh_command_icons()
        if title == 'Durdur': widget.hide()
        self.actions.addWidget(widget)
        if locked:
            self.controls.append(widget)
        return widget

    def refresh_command_icons(self):
        from .icons import icon
        from .theme import COLORS
        colors=COLORS[self.context.appearance]
        for widget in self.command_controls:
            name=widget.property('commandIcon')
            if name:widget.setIcon(icon(name,colors['on_accent' if widget.property('primary') else 'muted']))

    def finish_layout(self):
        row = QHBoxLayout()
        self.status.setMaximumHeight(54)
        row.addWidget(self.status, 1)
        self.status_details = button('Ayrıntı', lambda: show_details(self, 'İşlem ayrıntısı', self.status_text))
        self.status_details.setVisible(False)
        row.addWidget(self.status_details)
        self.layout.addLayout(row)

    SUCCESS_WORDS = ('kaydedildi', 'oluşturuldu', 'tamamlandı', 'dışa aktarıldı', 'aktarıldı', 'okundu',
                     'eklendi', 'kopyalandı', 'güncellendi', 'doğrulandı')
    WARNING_WORDS = ('kısmen', 'uyarı', 'eksik', 'atlandı', 'durduruldu')

    @classmethod
    def status_tone(cls, text, error=False, tone=None):
        """error / warning / success / muted for the status bar; ``tone`` overrides the inference."""
        if error:
            return 'error'
        if tone in ('success', 'warning', 'muted'):
            return tone
        first = str(text).splitlines()[0].casefold() if str(text).strip() else ''
        if any(word in first for word in cls.WARNING_WORDS):
            return 'warning'
        if any(word in first for word in cls.SUCCESS_WORDS):
            return 'success'
        return 'muted'

    def set_status(self, text, error=False, tone=None):
        self.status_kind = self.status_tone(text, error, tone)
        self.status_text = str(text)
        self.status.setText(self.status_text)
        self.status.setVisible(bool(error))
        self.status.setToolTip(self.status_text)
        if hasattr(self, 'status_details'):
            self.status_details.setVisible(error)
        self.status.setProperty('role', 'error' if error else 'muted')
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.statusChanged.emit(self.status_text, error)

    def can_start(self):
        if self.jobs.busy:
            self.set_status('Başka bir işlem sürüyor. Önce tamamlayın veya durdurun.', True)
            return False
        return True

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            control.setEnabled(not busy)
        if hasattr(self, 'stop_button'):
            self.stop_button.setEnabled(busy)
            self.stop_button.setVisible(busy)

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'job_error':
                self.set_status(value['error'], True)

    def job_finished(self):
        pass

    def theme_changed(self):
        pass


class ResultsPanel(QWidget):
    cleared = Signal()

    def __init__(self, parent=None, *, success_label='Başarılı',
                 empty_hint='Bu ekranın kaynak seçeneklerinden dosyaları ekleyin veya okuyun.'):
        super().__init__(parent)
        self.results = []
        self.busy = False
        self.success_label = success_label
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Dosya adı, yol veya açıklama ara…')
        self.search.setClearButtonEnabled(True)
        self.filter = QComboBox()
        self.filter.addItem('Tüm durumlar', None)
        for value in ('pending', 'running', 'success', 'partial', 'skipped', 'error'):
            self.filter.addItem(LABELS[value], value)
        self.copy_log = button('Günlüğü kopyala', self.copy_log_text)
        self.save = button('Rapor kaydet', self.save_dialog)
        self.report_menu = button('Rapor')
        report_menu = QMenu(self.report_menu)
        report_menu.addAction('Raporu CSV kaydet…', self.save_dialog)
        report_menu.addAction('Günlüğü kopyala', self.copy_log_text)
        self.report_menu.setMenu(report_menu)
        self.save.hide(); self.copy_log.hide()
        self.clear_button = button('Temizle', self.clear)
        self.clear_button.setToolTip('Dosya listesini, işlem sonuçlarını ve günlüğü temizle')
        self.toolbar=SearchToolbar(self.search,(self.filter,self.save,self.copy_log,self.report_menu,self.clear_button))
        self.layout.addWidget(self.toolbar)
        self.tabs = QTabWidget()
        self.table = configure_view(QTableView())
        self.model = TableModel((Column('Dosya / parça', 'source'),
                                 Column('Durum', 'status', lambda x: LABELS.get(x, x)),
                                 Column('Açıklama', 'detail')))
        self.proxy = FilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.empty_state = ViewEmptyState(self.table, self.clear_filters, empty_hint)
        self.empty_state.show_state(empty=True, filtered=False, busy=False)
        # Description takes the free width; the file name follows its contents
        # until dragged; every edge stays draggable.
        fit_columns(self.table, elastic=2, minimum=160, defaults={1: 110}, autofit=(0,))
        self.table.doubleClicked.connect(self.show_details)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.table, 'Dosyalar')
        self.tabs.addTab(self.log, 'Günlük')
        self.layout.addWidget(self.tabs, 1)
        self.counter = label('0 / 0 dosya · 0 sonuç', 'muted', wrap=False)
        self.layout.addWidget(self.counter)
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(100)
        self.search_timer.setSingleShot(True)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(lambda: self.proxy.set_query(self.search.text()))
        self.filter.currentIndexChanged.connect(lambda: self.proxy.set_status(self.filter.currentData()))
        self.proxy.rowsInserted.connect(self.refresh_count)
        self.proxy.modelReset.connect(self.refresh_count)
        self.proxy.rowsRemoved.connect(self.refresh_count)
        QShortcut(QKeySequence.Find, self, activated=self.search.setFocus)
        details_shortcut = QShortcut(QKeySequence('Return'), self.table,
                                    activated=lambda: self.show_details(self.table.currentIndex()))
        details_shortcut.setContext(Qt.WidgetShortcut)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        compact = event.size().width() < 820
        self.save.setVisible(not compact); self.copy_log.setVisible(not compact)
        self.report_menu.setVisible(compact)

    def reset(self):
        self.clear_filters()
        self.results.clear()
        self.model.replace([])
        self.log.clear()
        self.tabs.setCurrentIndex(0)
        self.refresh_count()

    def clear(self):
        if self.busy:
            return False
        self.reset()
        self.cleared.emit()
        return True

    def set_busy(self, busy):
        self.busy = busy
        self.clear_button.setEnabled(not busy)
        self.refresh_count()

    def clear_filters(self):
        self.search.clear()
        self.filter.setCurrentIndex(0)
        self.search_timer.stop()
        self.proxy.set_query('')
        self.proxy.set_status(None)

    def files(self, sources):
        self.model.replace([dict(source=str(path), status='pending', detail='') for path in sources])
        self.refresh_count()

    def result(self, result):
        result = dict(result)
        if result['status'] == 'success':
            result['_status_label'] = 'Uygulamaya hazır' if result.get('preview') else self.success_label
        self.results.append(result)
        self.model.upsert(result)
        self.append_log(f"{LABELS.get(result['status'], result['status'])} · {result['source']} · {result.get('detail', '')}")
        self.refresh_count()

    def append_log(self, text):
        self.log.appendPlainText(str(text))

    def refresh_count(self, *args):
        self.counter.setText(f'{self.proxy.rowCount()} / {self.model.rowCount()} dosya · {len(self.results)} sonuç')
        self.empty_state.show_state(empty=self.proxy.rowCount() == 0,
                                    filtered=self.model.rowCount() > 0, busy=self.busy)

    def copy_log_text(self):
        QApplication.clipboard().setText(self.log.toPlainText())

    def show_details(self, index):
        if not index.isValid():
            return
        row = index.data(Qt.UserRole)
        show_details(self, 'Dosya ayrıntıları', '\n\n'.join(f'{key}: {value}' for key, value in row.items()))

    def save_csv(self, path):
        write_csv_atomic(path, ('Kaynak', 'Çıktı', 'Durum', 'Açıklama'),
                         [(row['source'], row.get('output', ''), row.get('_status_label', LABELS.get(row['status'], row['status'])),
                           row.get('detail', '')) for row in self.results])

    def save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Rapor kaydet', 'GOKWORKS_rapor.csv', 'CSV (*.csv)')
        if path:
            try:
                self.save_csv(path)
                self.append_log(f'Rapor kaydedildi: {path}')
            except OSError as error:
                show_details(self, 'Rapor kaydedilemedi', str(error))


def show_details(parent, title, text):
    dialog = QDialog(parent)
    dialog.setWindowTitle('GOKWORKS · ' + title)
    dialog.resize(650, 430)
    layout = QVBoxLayout(dialog)
    content = QPlainTextEdit()
    content.setReadOnly(True)
    content.setPlainText(str(text))
    layout.addWidget(content)
    actions = QDialogButtonBox(QDialogButtonBox.Close)
    actions.button(QDialogButtonBox.Close).setText('Kapat')
    copy = actions.addButton('Kopyala', QDialogButtonBox.ActionRole)
    copy.clicked.connect(lambda: QApplication.clipboard().setText(str(text)))
    actions.rejected.connect(dialog.reject)
    layout.addWidget(actions)
    dialog.exec()


def open_folder(path):
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).absolute())))


# ---------------------------------------------------------------------------
# Design-system widgets shared by several workbenches (docs/UI_DESIGN_SYSTEM.md)
# ---------------------------------------------------------------------------

def turkish_locale():
    """tr_TR number format (decimal comma) without the ambiguous '1.500' grouping."""
    from PySide6.QtCore import QLocale
    locale = QLocale(QLocale.Turkish, QLocale.Turkey)
    locale.setNumberOptions(QLocale.OmitGroupSeparator | QLocale.RejectGroupSeparator)
    return locale


class NumberSpinBox(QDoubleSpinBox):
    """Engineering number field: decimal comma, right aligned, no trailing zeros.

    The value still rounds to ``decimals()`` places, so precision is unchanged:
    2.0000 is shown as 2 and 0.0125 as 0,0125.
    """
    def __init__(self, decimals=4, parent=None):
        super().__init__(parent)
        self.setLocale(turkish_locale()); self.setDecimals(decimals)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def textFromValue(self, value):
        text = self.locale().toString(float(value), 'f', self.decimals())
        point = self.locale().decimalPoint()
        if point in text:
            text = text.rstrip('0').rstrip(point)
        return '0' if text in ('-0', '') else text


def pane(title=None, *, rule=False):
    """Flat parameter/result group: semibold heading over content, no frame.

    Calculation pages separate groups with spacing and optional 1 px rules
    instead of nested cards (docs/UI_DESIGN_SYSTEM.md, "Düz yüzeyler").
    """
    widget = QFrame()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    if rule:
        layout.addWidget(separator())
    if title:
        heading = label(title, 'section')
        layout.addWidget(heading)
        widget.heading = heading
    return widget, layout


# Status → semantic token. Colour is used only where the state carries meaning.
STATUS_TOKENS = {'success': 'success', 'partial': 'warning', 'skipped': 'warning', 'error': 'danger'}


class StatusDelegate(QStyledItemDelegate):
    """Colours only the status cell of a result row with its semantic token.

    ``appearance`` is a callable so the colours follow live theme switches
    without rebuilding the view.
    """
    def __init__(self, appearance, parent=None):
        super().__init__(parent)
        self.appearance = appearance

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        row = index.data(Qt.UserRole) or {}
        token = STATUS_TOKENS.get(row.get('status')) if isinstance(row, dict) else None
        if token:
            color = QColor(COLORS[self.appearance()][token])
            for group in (QPalette.Active, QPalette.Inactive):
                option.palette.setColor(group, QPalette.Text, color)
                option.palette.setColor(group, QPalette.HighlightedText, color)


class AdaptiveRow(QWidget):
    """Compact command row that stacks only when its column is too narrow.

    Its minimum width is the widest single control, so a narrow source column
    never grows a horizontal scroll bar.
    """
    def __init__(self, *widgets, spacing=SPACING['s'], stretch=None):
        super().__init__()
        self.widgets = widgets
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0); self.box.setSpacing(spacing)
        for index, widget in enumerate(widgets):
            self.box.addWidget(widget, 1 if index == stretch else 0)
        if stretch is None:
            self.box.addStretch()
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def _row_width(self):
        return sum(w.sizeHint().width() for w in self.widgets) + self.box.spacing() * (len(self.widgets) - 1)

    def minimumSizeHint(self):
        return QSize(max(w.minimumSizeHint().width() for w in self.widgets), super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = QBoxLayout.LeftToRight if self.width() >= self._row_width() else QBoxLayout.TopToBottom
        if self.box.direction() != direction:
            self.box.setDirection(direction)


class ColumnFitter(QObject):
    """One consistent, spreadsheet-like column behaviour for every table and tree.

    Automatic layout (until the user touches a column):
    * one *elastic* column takes the free width (never below ``minimum``;
      a narrow view scrolls instead of clipping), other columns follow their
      contents (``autofit``) or use ``defaults``.

    Manual layout (as in Excel, from the first drag on):
    * dragging an edge changes only that column; no other column moves.
      Growing shows a horizontal scroll bar, shrinking leaves empty space;
    * the width is shown next to the cursor while dragging;
    * double-clicking an edge fits that column to its contents;
    * widths are remembered per view (``settings``/``key``);
    * header menu: fit all columns to contents / back to automatic layout.
    """

    MAX_AUTOFIT = 420

    def __init__(self, view, *, elastic=None, minimum=120, defaults=None, autofit='auto', fixed=(),
                 settings=None, key=None):
        super().__init__(view)
        self.view = view
        self.header = view.header() if isinstance(view, QTreeView) else view.horizontalHeader()
        self.elastic, self.minimum = elastic, minimum
        self.defaults = dict(defaults or {})
        self.autofit = autofit if autofit == 'auto' else set(autofit)
        self.fixed = set(fixed)
        self.settings, self.key = settings, key
        self.user = set()
        self.manual = False
        self._guard = False
        self.header.setStretchLastSection(False)
        self.header.setCascadingSectionResizes(False)
        self.header.setMinimumSectionSize(28)
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        for column in self.fixed:
            self.header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.header.sectionResized.connect(self._resized)
        self.header.sectionHandleDoubleClicked.connect(self.fit_to_contents)
        self.header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self._menu)
        self.header.sectionCountChanged.connect(self._count_changed)
        self._viewport = view.viewport()
        self._viewport.installEventFilter(self)
        view.destroyed.connect(self._view_destroyed)
        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save)
        self._autofit_timer = QTimer(self); self._autofit_timer.setSingleShot(True); self._autofit_timer.setInterval(0)
        self._autofit_timer.timeout.connect(self._autofit)
        self.alive = True
        self._model = None
        self.attach_model()
        self.apply_defaults()
        self._restore()
        self._autofit_timer.start()

    # -- model hooks -------------------------------------------------------
    def attach_model(self):
        model = self.view.model()
        if model is None or model is self._model:
            return
        self._model = model
        for signal in (model.modelReset, model.rowsInserted, model.layoutChanged):
            signal.connect(self._contents_changed)

    def _count_changed(self, old, new):
        """A model was set or columns were added later: size the new columns."""
        self.attach_model()
        self._guard = True
        try:
            for column in self.fixed:
                if column < new:
                    self.header.setSectionResizeMode(column, QHeaderView.Fixed)
        finally:
            self._guard = False
        if new > old:
            self.apply_defaults(range(old, new))
            self._restore()
        self._contents_changed()

    def _contents_changed(self, *args):
        self._autofit_timer.start()

    def _auto_columns(self):
        """Columns that follow their contents until the user resizes them."""
        elastic = self.elastic_column()
        if self.autofit == 'auto':
            columns = {c for c in range(self.header.count()) if c not in self.defaults}
        else:
            columns = set(self.autofit)
        return {c for c in columns - self.user - self.fixed
                if c != elastic and c < self.header.count() and not self.header.isSectionHidden(c)}

    def _autofit(self):
        if not self.alive or self.manual:
            return
        columns = self._auto_columns() if self.autofit else set()
        if not columns:
            self.fit(); return
        wanted = {}
        for column in columns:
            content = self.view.sizeHintForColumn(column)
            wanted[column] = min(max(content + 12, self._header_width(column), 60), self.MAX_AUTOFIT)
        # Never push the elastic column below its minimum just to show long text:
        # shrink the auto columns toward their header width instead.
        elastic = self.elastic_column()
        fixed_width = sum(self.header.sectionSize(c) for c in range(self.header.count())
                          if c not in columns and c != elastic and not self.header.isSectionHidden(c))
        room = self.view.viewport().width() - fixed_width - self.minimum
        total = sum(wanted.values())
        if room > 0 and total > room:
            floors = {c: max(self._header_width(c), 60) for c in columns}
            spare = sum(wanted[c] - floors[c] for c in columns)
            excess = total - room
            if spare > 0:
                for c in columns:
                    wanted[c] = int(wanted[c] - (wanted[c] - floors[c]) * min(1.0, excess / spare))
        self._guard = True
        try:
            for column, width in wanted.items():
                self.header.resizeSection(column, width)
        finally:
            self._guard = False
        self.fit()

    # -- geometry ------------------------------------------------------------
    def _header_width(self, column):
        model = self.view.model()
        title = str(model.headerData(column, Qt.Horizontal)) if model is not None else ''
        font = self.header.font(); font.setBold(True)
        from PySide6.QtGui import QFontMetrics
        return QFontMetrics(font).horizontalAdvance(title) + 22

    def elastic_column(self):
        if self.elastic is not None:
            return self.elastic
        visible = [self.header.logicalIndex(v) for v in range(self.header.count())
                   if not self.header.isSectionHidden(self.header.logicalIndex(v))]
        return visible[-1] if visible else None

    def apply_defaults(self, columns=None):
        self._guard = True
        try:
            for column in (range(self.header.count()) if columns is None else columns):
                width = self.defaults.get(column)
                if width is None and column != self.elastic_column() and column not in self.fixed:
                    width = max(self._header_width(column), 90)
                if width is not None:
                    self.header.resizeSection(column, int(width))
        finally:
            self._guard = False

    def fit(self):
        """Give the elastic column exactly the free width (or its minimum)."""
        if not self.alive or self.manual:
            return
        elastic = self.elastic_column()
        if elastic is None or elastic >= self.header.count() or self.header.isSectionHidden(elastic):
            return
        others = sum(self.header.sectionSize(c) for c in range(self.header.count())
                     if c != elastic and not self.header.isSectionHidden(c))
        width = max(self.minimum, self.view.viewport().width() - others)
        if self.header.sectionSize(elastic) != width:
            self._guard = True
            try:
                self.header.resizeSection(elastic, width)
            finally:
                self._guard = False

    def _resized(self, column, old, new):
        if self._guard:
            return
        if new == 0 or old == 0:          # shown / hidden
            if not self.manual:
                self._autofit_timer.start()
            return
        if not QApplication.mouseButtons() & Qt.LeftButton:
            # Programmatic setColumnWidth(): a default width for the automatic
            # layout, not a user drag (must not switch to manual mode).
            if not self.manual:
                self.defaults[column] = new
                if self.autofit != 'auto' and column in self.autofit:
                    self.autofit = set(self.autofit) - {column}
                self._autofit_timer.start()
            return
        # Spreadsheet behaviour: only the dragged column changes.
        self.manual = True
        self.user.add(column)
        QToolTip.showText(QCursor.pos(), f'Genişlik: {new} piksel', self.header)
        self._save_timer.start()

    def detach(self):
        self.alive = False
        self._autofit_timer.stop(); self._save_timer.stop()
        self._viewport.removeEventFilter(self)
        connections = [(self.header.sectionResized, self._resized),
                       (self.header.sectionHandleDoubleClicked, self.fit_to_contents),
                       (self.header.customContextMenuRequested, self._menu),
                       (self.header.sectionCountChanged, self._count_changed)]
        if self._model is not None:
            connections += [(signal, self._contents_changed) for signal in
                            (self._model.modelReset, self._model.rowsInserted, self._model.layoutChanged)]
        for signal, slot in connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def _view_destroyed(self, *args):
        self.alive = False

    def eventFilter(self, watched, event):
        if self.alive and watched is self._viewport and event.type() == QEvent.Resize:
            try:
                self.attach_model()
                self.fit()
            except RuntimeError:      # view is being destroyed
                self.alive = False
        return False

    # -- commands ---------------------------------------------------------------
    def fit_to_contents(self, column=None):
        """Excel double-click: fit to contents (all columns from the menu)."""
        columns = [column] if isinstance(column, int) else [c for c in range(self.header.count()) if c not in self.fixed]
        self.manual = True
        self._guard = True
        try:
            for c in columns:
                if self.header.isSectionHidden(c) or c in self.fixed:
                    continue
                self.view.resizeColumnToContents(c)
                width = max(self.header.sectionSize(c), self._header_width(c))
                self.header.resizeSection(c, min(width, self.MAX_AUTOFIT))
                self.user.add(c)
        finally:
            self._guard = False
        self._save_timer.start()

    def reset(self):
        """Back to the automatic layout and forget saved widths."""
        self.user.clear(); self.manual = False
        if self.settings is not None and self.key:
            self.settings.set(self._settings_key(), {})
        self.apply_defaults()
        self._autofit() if self.autofit else self.fit()
        self._save_timer.stop()

    def _menu(self, point):
        menu = QMenu(self.header)
        menu.addAction('Sütunları içeriğe sığdır', self.fit_to_contents)
        menu.addAction('Otomatik sütun genişlikleri', self.reset)
        menu.exec(self.header.mapToGlobal(point))

    # -- persistence ----------------------------------------------------------
    def _settings_key(self):
        return 'columns/' + self.key

    def _save(self):
        if self.settings is None or not self.key:
            return
        if not self.manual:
            self.settings.set(self._settings_key(), {}); return
        widths = {str(c): self.header.sectionSize(c) for c in range(self.header.count())
                  if c not in self.fixed and not self.header.isSectionHidden(c) and self.header.sectionSize(c) > 0}
        self.settings.set(self._settings_key(), widths)

    def _restore(self):
        if self.settings is None or not self.key:
            return
        saved = self.settings.get(self._settings_key(), {})
        if not isinstance(saved, dict):
            return
        self._guard = True
        try:
            for text, width in saved.items():
                if not str(text).isdigit() or type(width) is not int or not 28 <= width <= 1200:
                    continue
                column = int(text)
                if column < self.header.count() and column not in self.fixed:
                    self.header.resizeSection(column, width); self.user.add(column); self.manual = True
        finally:
            self._guard = False


def fit_columns(view, **options):
    """Install (or replace) the shared column behaviour on a table or tree."""
    previous = getattr(view, 'column_fitter', None)
    if previous is not None:
        previous.detach()
        previous.deleteLater()
    view.column_fitter = ColumnFitter(view, **options)
    return view.column_fitter
