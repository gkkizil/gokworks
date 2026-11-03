"""Shared engineering workspace with Qt vector scenes and exportable reports."""

import csv
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QSplitter, QTabWidget,
    QTableView, QFileDialog, QApplication, QStackedWidget, QMenu, QSizePolicy, QToolButton)
from gui_qt.components import BasePage, ValueForm, label, scroll, separator, configure_view, show_details
from gui_qt.components import Disclosure, pane  # noqa: F401  (pane re-exported)
from gui_qt.diagrams import EngineeringDiagram
from gui_qt.models import Column, TableModel


class CalculationWorkspace(QStackedWidget):
    """Keep usable form widths and use one scroll area on narrow screens."""

    def __init__(self, inputs, result):
        super().__init__()
        self.inputs, self.result = inputs, result
        inputs.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        self.left_scroll, self.right_scroll = scroll(inputs), scroll(result)
        self.wide = QSplitter(Qt.Horizontal)
        self.wide.addWidget(self.left_scroll)
        self.wide.addWidget(self.right_scroll)
        self.wide.setChildrenCollapsible(False)
        self.wide.setStretchFactor(0, 4)
        self.wide.setStretchFactor(1, 7)
        self.column = QWidget()
        self.column_layout = QVBoxLayout(self.column)
        self.column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_layout.setSpacing(10)
        self.column_scroll = scroll(self.column)
        self.addWidget(self.wide)
        self.addWidget(self.column_scroll)
        self.compact = None
        self.saved_sizes = None   # user-dragged splitter sizes, restored in the wide layout
        self.inputs_hidden = False  # the user hid the parameter panel; layout changes must respect it

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = event.size().width() < 720
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.left_scroll.takeWidget()
            self.right_scroll.takeWidget()
            self.column_layout.addWidget(self.inputs)
            self.column_layout.addWidget(self.result)
            self.column_layout.addStretch()
            self.setCurrentWidget(self.column_scroll)
        else:
            self.column_layout.removeWidget(self.inputs)
            self.column_layout.removeWidget(self.result)
            if self.column_layout.count():
                self.column_layout.takeAt(0)
            self.left_scroll.setWidget(self.inputs)
            self.right_scroll.setWidget(self.result)
            self.setCurrentWidget(self.wide)
            width = event.size().width()
            if self.saved_sizes and sum(self.saved_sizes) > 0:
                share = self.saved_sizes[0] / sum(self.saved_sizes)
                left = min(max(300, round(width * share)), max(300, width - 320))
                self.wide.setSizes([left, max(320, width - left)])
            else:
                self.wide.setSizes([max(300, round(width * .36)), max(320, round(width * .64))])
        self.inputs.setVisible(not self.inputs_hidden)
        self.left_scroll.setVisible(not (self.inputs_hidden and not compact))
        self.result.show()


class CalculationPage(BasePage):
    def __init__(self, context, title, description, prefix):
        super().__init__(context, title, description)
        self.result = None
        self.report = []
        self.loading = False
        self.action('Sonucu kopyala', self.copy_report)
        self.report_menu=QMenu(self)
        self.report_menu.addAction('CSV kaydet…',self.save_report)
        self.action('Rapor / yardım',None).setMenu(self.report_menu)
        left, left_layout = pane('Hesap değerleri')
        left_layout.setContentsMargins(0, 0, 8, 0)
        self.input_card = left
        self.form = ValueForm(self.settings, prefix)
        left_layout.addWidget(self.form)
        self.extra_layout = QVBoxLayout()
        left_layout.addLayout(self.extra_layout)
        left_layout.addStretch()
        right = QWidget()
        self.right = QVBoxLayout(right)
        self.right.setContentsMargins(8, 0, 0, 0)
        self.right.setSpacing(6)
        # Hierarchy: 20 px result headline, one muted summary line, a rule,
        # then the drawing and supporting text.
        self.headline = label('—', 'result')
        self.headline.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.headline.setAccessibleName('Hesap sonucu')
        self.right.addWidget(self.headline)
        self.summary = label('', 'muted')
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.right.addWidget(self.summary)
        self.result_rule = separator()
        self.right.addWidget(self.result_rule)
        self.diagram_tabs = QTabWidget()
        self.diagram_tabs.setDocumentMode(True)
        self.diagrams = {}
        # One view command for every technical sketch (Ctrl+wheel zoom, drag pan are on the view).
        self.fit_button = QToolButton()
        self.fit_button.setText('Sığdır')
        self.fit_button.setAutoRaise(True)
        self.fit_button.setToolTip('Görünümü sığdır · ' + EngineeringDiagram.HINT)
        self.fit_button.clicked.connect(self.fit_diagram)
        self.diagram_tabs.setCornerWidget(self.fit_button, Qt.TopRightCorner)
        self.right.addWidget(self.diagram_tabs, 1)
        self.details = label()
        self.right.addWidget(self.details)
        self.metric_model = TableModel((Column('Özellik', 'key'), Column('Değer', 'value')))
        self.metrics = configure_view(QTableView())
        self.metrics.setModel(self.metric_model)
        self.metrics.setMinimumHeight(160)
        self.metrics.setMaximumHeight(260)
        self.report_disclosure = Disclosure('Hesap ayrıntıları ve rapor', self.metrics)
        self.right.addWidget(self.report_disclosure)
        self.right.addStretch()
        self.workspace = CalculationWorkspace(left, right)
        self.compact_headline = label('—','section');self.compact_headline.hide()
        self.compact_headline.setAccessibleName('Güncel hesap sonucu')
        self.layout.addWidget(self.compact_headline)
        self.splitter = self.workspace.wide
        self.layout_key = 'layout/' + prefix
        saved = self.settings.get(self.layout_key + 'split')
        if isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, int) and v > 0 for v in saved):
            self.workspace.saved_sizes = saved
        self.splitter.splitterMoved.connect(self.remember_split)
        self.inputs_button = self.action('Parametreleri gizle', self.toggle_inputs, locked=False)
        self.inputs_button.setToolTip('Parametre panelini gizle / göster (Ctrl+Shift+P)')
        QShortcut(QKeySequence('Ctrl+Shift+P'), self, activated=self.toggle_inputs)
        self.left_scroll, self.right_scroll = self.workspace.left_scroll, self.workspace.right_scroll
        self.layout.addWidget(self.workspace, 1)
        self.finish_layout()
        if self.settings.get(self.layout_key + 'inputs_hidden') is True:
            self.set_inputs_visible(False)
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(60)
        self.update_timer.timeout.connect(self.update_result)
        self.form.changed.connect(self.changed)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'compact_headline'):
            self.compact_headline.setVisible(event.size().width()-32 < 720)

    def add_diagram(self, key, title, width=650, height=300):
        diagram = EngineeringDiagram(width=width, height=height)
        # Keep the full engineering scene, while avoiding a mandatory tall
        # viewport that pushes the result and report below smaller windows.
        diagram.setMinimumHeight(min(height, 220))
        # Wide windows may give the drawing more room (it scales to fit),
        # instead of leaving an empty band below the result.
        diagram.setMaximumHeight(max(300, round(height * 1.35)))
        self.diagrams[key] = diagram
        self.diagram_tabs.addTab(diagram, title)
        # The tab widget may grow with the window, but never beyond its tallest
        # drawing; otherwise an empty band opens below the scene.
        self.diagram_tabs.setMaximumHeight(max(d.maximumHeight() for d in self.diagrams.values())
                                           + self.diagram_tabs.tabBar().sizeHint().height() + 2)
        return diagram

    def remember_split(self, *args):
        sizes = self.splitter.sizes()
        if len(sizes) == 2 and all(sizes):
            self.workspace.saved_sizes = sizes
            self.settings.set(self.layout_key + 'split', sizes)

    def set_inputs_visible(self, visible):
        self.workspace.inputs_hidden = not visible
        self.input_card.setVisible(visible)
        self.workspace.left_scroll.setVisible(visible or self.workspace.compact is True)
        self.inputs_button.setText('Parametreleri gizle' if visible else 'Parametreleri göster')
        self.settings.set(self.layout_key + 'inputs_hidden', not visible)

    def toggle_inputs(self):
        self.set_inputs_visible(self.input_card.isHidden())

    def fit_diagram(self):
        diagram = self.diagram_tabs.currentWidget()
        if isinstance(diagram, EngineeringDiagram):
            diagram.fit_view()

    def info_action(self,title,callback):
        return self.report_menu.addAction(title,callback)

    @property
    def appearance(self):
        return 'Dark' if self.context.appearance == 'dark' else 'Light'

    def changed(self, key):
        if not self.loading:
            self.update_timer.start()

    def update_result(self):
        raise NotImplementedError

    def present(self, rows):
        self.compact_headline.setText(self.headline.text())
        self.report = list(rows)
        self.metric_model.replace([dict(key=key, value=str(value)) for key, value in rows])
        self.metrics.setColumnWidth(0, 230)

    def invalid(self, error):
        self.result = None
        self.report = []
        self.headline.setText('Değerleri kontrol edin')
        self.compact_headline.setText('Değerleri kontrol edin')
        self.summary.clear()
        self.metric_model.replace([])
        self.set_status(str(error), True)
        for diagram in self.diagrams.values():
            diagram.vector.delete('all')

    def copy_report(self):
        if self.report:
            QApplication.clipboard().setText('\n'.join(f'{key}: {value}' for key, value in self.report))
            self.set_status('Sonuç ve hesap kapsamı panoya kopyalandı.')

    def save_report(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Hesabı kaydet', 'GOKWORKS_hesap.csv', 'CSV (*.csv)')
        if path:
            try:
                with open(path, 'w', encoding='utf-8-sig', newline='') as stream:
                    writer = csv.writer(stream, delimiter=';')
                    writer.writerow(('Alan', 'Değer'))
                    writer.writerows(self.report)
                self.set_status('CSV raporu kaydedildi.')
            except OSError as error:
                self.set_status(str(error), True)

    def theme_changed(self):
        self.update_result()
