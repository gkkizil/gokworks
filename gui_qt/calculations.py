"""Shared engineering workspace with Qt vector scenes and exportable reports."""

import csv
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, QTabWidget,
    QTableView, QFileDialog, QApplication, QStackedWidget, QMenu, QSizePolicy)
from gui_qt.components import BasePage, ValueForm, card, label, scroll, configure_view, show_details
from gui_qt.components import Disclosure
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
            self.wide.setSizes([max(300, round(width * .36)), max(320, round(width * .64))])
        self.inputs.show()
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
        left, left_layout = card('Hesap değerleri')
        self.input_card = left
        self.form = ValueForm(self.settings, prefix)
        left_layout.addWidget(self.form)
        self.extra_layout = QVBoxLayout()
        left_layout.addLayout(self.extra_layout)
        left_layout.addStretch()
        right = QWidget()
        self.right = QVBoxLayout(right)
        self.right.setContentsMargins(0, 0, 0, 0)
        self.right.setSpacing(8)
        self.headline = label('—', 'result')
        self.right.addWidget(self.headline)
        self.summary = label('', 'subtitle')
        self.right.addWidget(self.summary)
        self.diagram_tabs = QTabWidget()
        self.diagrams = {}
        self.right.addWidget(self.diagram_tabs)
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
        self.left_scroll, self.right_scroll = self.workspace.left_scroll, self.workspace.right_scroll
        self.layout.addWidget(self.workspace, 1)
        self.finish_layout()
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
        diagram.setMaximumHeight(max(260, height))
        self.diagrams[key] = diagram
        self.diagram_tabs.addTab(diagram, title)
        return diagram

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
