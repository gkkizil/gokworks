"""Shared Qt Widgets: forms, persistent workspaces and model-backed results."""

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QComboBox, QCheckBox, QPushButton, QScrollArea,
    QFileDialog, QTableView, QTreeView, QHeaderView, QAbstractItemView,
    QTabWidget, QPlainTextEdit, QDialog, QDialogButtonBox, QApplication)

from .models import Column, TableModel, FilterProxy, LABELS


def label(text='', role=None, *, wrap=True):
    widget = QLabel(text)
    widget.setWordWrap(wrap)
    widget.setMinimumWidth(0)
    if role:
        widget.setProperty('role', role)
    return widget


def button(text, callback=None, *, primary=False):
    widget = QPushButton(text)
    if callback:
        widget.clicked.connect(callback)
    widget.setProperty('primary', primary)
    return widget


def card(title=None):
    widget = QFrame()
    widget.setProperty('card', True)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    if title:
        layout.addWidget(label(title, 'section'))
    return widget, layout


def scroll(widget):
    area = QScrollArea()
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
    view.header().setStretchLastSection(True) if isinstance(view, QTreeView) else view.horizontalHeader().setStretchLastSection(True)
    header = view.header() if isinstance(view, QTreeView) else view.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setDefaultSectionSize(180)
    header.setMinimumSectionSize(60)
    if isinstance(view, QTableView):
        view.verticalHeader().setDefaultSectionSize(38)
    view.setMinimumWidth(0)
    return view


class PathPicker(QWidget):
    changed = Signal(str)

    def __init__(self, text='', *, folder=True, title='Klasör seç', parent=None):
        super().__init__(parent)
        self.folder, self.dialog_title = folder, title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.entry = QLineEdit(str(text))
        self.entry.setPlaceholderText(title)
        self.entry.setClearButtonEnabled(True)
        self.choose = button('Klasör seç' if folder else 'Dosya seç', self.browse)
        self.choose.setAccessibleName(title)
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
        self.form.setSpacing(12)
        self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    def _bind(self, key, widget, default, signal):
        self.fields[key] = widget
        widget.setObjectName(f'{self.prefix}{key}')
        widget.setAccessibleName(key)
        signal.connect(lambda *args, key=key: self._changed(key))
        return widget

    def _changed(self, key):
        self.settings.set(self.prefix + key, self.value(key))
        self.changed.emit(key)

    def text(self, key, title, default=''):
        widget = QLineEdit(str(self.settings.get(self.prefix + key, default)))
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


class BasePage(QWidget):
    statusChanged = Signal(str, bool)
    progressChanged = Signal(int, int)

    def __init__(self, context, title, description):
        super().__init__()
        self.context, self.settings, self.jobs = context, context.settings, context.jobs
        self.busy = False
        self.controls = []
        self.status_text = ''
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 16)
        self.layout.setSpacing(14)
        heading = QHBoxLayout()
        captions = QVBoxLayout()
        captions.setSpacing(5)
        captions.addWidget(label(title, 'title'))
        captions.addWidget(label(description, 'subtitle'))
        heading.addLayout(captions, 1)
        self.actions = QHBoxLayout()
        heading.addLayout(self.actions)
        self.layout.addLayout(heading)
        self.status = label('Hazır', 'muted')

    def action(self, title, callback, *, primary=False, locked=True):
        widget = button(title, callback, primary=primary)
        self.actions.addWidget(widget)
        if locked:
            self.controls.append(widget)
        return widget

    def finish_layout(self):
        row = QHBoxLayout()
        self.status.setMaximumHeight(54)
        row.addWidget(self.status, 1)
        self.status_details = button('Ayrıntı', lambda: show_details(self, 'İşlem ayrıntısı', self.status_text))
        self.status_details.setVisible(False)
        row.addWidget(self.status_details)
        self.layout.addLayout(row)

    def set_status(self, text, error=False):
        self.status_text = str(text)
        self.status.setText(self.status_text)
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

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'job_error':
                self.set_status(value['error'], True)

    def job_finished(self):
        pass

    def theme_changed(self):
        pass


class ResultsPanel(QWidget):
    def __init__(self, parent=None, *, success_label='Başarılı'):
        super().__init__(parent)
        self.results = []
        self.success_label = success_label
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Dosya adı, yol veya açıklama ara…')
        self.search.setClearButtonEnabled(True)
        self.filter = QComboBox()
        self.filter.addItem('Tüm durumlar', None)
        for value in ('pending', 'running', 'success', 'partial', 'skipped', 'error'):
            self.filter.addItem(LABELS[value], value)
        self.copy_log = button('Günlüğü kopyala', self.copy_log_text)
        self.save = button('Rapor kaydet', self.save_dialog)
        self.clear_button = button('Temizle', self.clear_filters)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.filter)
        toolbar.addWidget(self.save)
        toolbar.addWidget(self.copy_log)
        toolbar.addWidget(self.clear_button)
        self.layout.addLayout(toolbar)
        self.tabs = QTabWidget()
        self.table = configure_view(QTableView())
        self.model = TableModel((Column('Dosya / parça', 'source'),
                                 Column('Durum', 'status', lambda x: LABELS.get(x, x)),
                                 Column('Açıklama', 'detail')))
        self.proxy = FilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setColumnWidth(0, 360)
        self.table.setColumnWidth(1, 120)
        self.table.doubleClicked.connect(self.show_details)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.table, 'Dosyalar')
        self.tabs.addTab(self.log, 'Günlük')
        self.layout.addWidget(self.tabs, 1)
        self.counter = label('Henüz sonuç yok. Kaynağı seçip tarama veya aktarım başlatın.', 'muted')
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
        QShortcut(QKeySequence('Return'), self.table, activated=lambda: self.show_details(self.table.currentIndex()))

    def reset(self):
        self.clear_filters()
        self.results.clear()
        self.model.replace([])
        self.log.clear()

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

    def copy_log_text(self):
        QApplication.clipboard().setText(self.log.toPlainText())

    def show_details(self, index):
        if not index.isValid():
            return
        row = index.data(Qt.UserRole)
        show_details(self, 'Dosya ayrıntıları', '\n\n'.join(f'{key}: {value}' for key, value in row.items()))

    def save_csv(self, path):
        with Path(path).open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream, delimiter=';')
            writer.writerow(('Kaynak', 'Çıktı', 'Durum', 'Açıklama'))
            writer.writerows((row['source'], row.get('output', ''), row.get('_status_label', LABELS.get(row['status'], row['status'])),
                              row.get('detail', '')) for row in self.results)

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
    copy = actions.addButton('Kopyala', QDialogButtonBox.ActionRole)
    copy.clicked.connect(lambda: QApplication.clipboard().setText(str(text)))
    actions.rejected.connect(dialog.reject)
    layout.addWidget(actions)
    dialog.exec()


def open_folder(path):
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).absolute())))
