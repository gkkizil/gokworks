"""Shared engineering workspace with Qt vector scenes and exportable reports."""

import csv
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, QTabWidget,
    QTableView, QFileDialog, QApplication)
from ..components import BasePage, ValueForm, card, label, scroll, configure_view, show_details
from ..diagrams import EngineeringDiagram
from ..models import Column, TableModel


class CalculationPage(BasePage):
    def __init__(self, context, title, description, prefix):
        super().__init__(context, title, description)
        self.result = None
        self.report = []
        self.loading = False
        self.action('Sonucu kopyala', self.copy_report)
        self.action('CSV kaydet', self.save_report)
        self.splitter = QSplitter(Qt.Horizontal)
        left, left_layout = card('PARAMETRELER')
        self.form = ValueForm(self.settings, prefix)
        left_layout.addWidget(self.form)
        self.extra_layout = QVBoxLayout()
        left_layout.addLayout(self.extra_layout)
        left_layout.addStretch()
        self.left_scroll = scroll(left)
        self.left_scroll.setMinimumWidth(240)
        self.splitter.addWidget(self.left_scroll)
        right = QWidget()
        self.right = QVBoxLayout(right)
        self.right.setContentsMargins(0, 0, 0, 0)
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
        self.metrics.setMinimumHeight(190)
        self.right.addWidget(self.metrics)
        self.right.addStretch()
        self.splitter.addWidget(scroll(right))
        self.splitter.setSizes([360, 700])
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(60)
        self.update_timer.timeout.connect(self.update_result)
        self.form.changed.connect(self.changed)

    def add_diagram(self, key, title, width=650, height=300):
        diagram = EngineeringDiagram(width=width, height=height)
        diagram.setMinimumHeight(height)
        self.diagrams[key] = diagram
        self.diagram_tabs.addTab(diagram, title)
        return diagram

    @property
    def appearance(self):
        return 'Dark' if self.context.appearance == 'dark' else 'Light'

    def changed(self, key):
        if not self.loading:
            self.update_timer.start()

    def update_result(self):
        raise NotImplementedError

    def present(self, rows):
        self.report = list(rows)
        self.metric_model.replace([dict(key=key, value=str(value)) for key, value in rows])
        self.metrics.setColumnWidth(0, 230)

    def invalid(self, error):
        self.result = None
        self.report = []
        self.headline.setText('Değerleri kontrol edin')
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
