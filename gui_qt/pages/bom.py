"""Virtualized hierarchical BOM, instance weights and complete Excel export."""

from dataclasses import asdict
from pathlib import PureWindowsPath

from PySide6.QtCore import Qt, QTimer, QPersistentModelIndex
from PySide6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLineEdit, QTabWidget,
    QTableView, QTreeView, QSplitter, QFileDialog, QApplication)

from bom.exporter import scan_worker
from .. import services
from ..models import Column, TableModel, TreeModel, FilterProxy
from ..components import BasePage, ValueForm, card, label, button, configure_view, show_details


def mass(value):
    return 'Okunamadı' if value is None else f'{value:,.6f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class BomPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'BOM · Ürün ağacı', 'Montaj hiyerarşisi, parça adetleri ve canlı ağırlık bilgileri.')
        self.result = None
        self.scan_button = self.action('Montajı oku', self.scan, primary=True)
        self.export_button = self.action('Excel kaydet', self.export)
        self.export_button.setEnabled(False)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.stop_button.setEnabled(False)
        self.form = ValueForm(self.settings, 'bom_')
        self.form.check('include_excluded', 'BOM dışında bırakılan bileşenleri dahil et', False)
        self.layout.addWidget(self.form)
        self.controls.append(self.form)
        self.summary = label('SolidWorks’te ana montajı etkinleştirip Montajı oku düğmesine basın.', 'muted')
        self.layout.addWidget(self.summary)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Parça, montaj, konfigürasyon veya dosya yolu ara…')
        self.search.setClearButtonEnabled(True)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(button('Tümünü aç', self.expand_all))
        toolbar.addWidget(button('Daralt', lambda: self.tree.collapseAll()))
        toolbar.addWidget(button('Temizle', self.clear))
        toolbar.addWidget(button('Dosya yolunu kopyala', self.copy_path))
        self.layout.addLayout(toolbar)
        self.tabs = QTabWidget()
        self.parts = configure_view(QTableView())
        self.parts_model = TableModel((Column('Parça adı', 'name'), Column('Adet', 'quantity'),
            Column('Birim ağırlık (kg)', 'mass_kg', mass), Column('Toplam (kg)', 'total_mass_kg', mass),
            Column('Konfigürasyon', 'configuration'), Column('Dosya yolu', 'path'), Column('Ağırlık durumu', 'mass_note')))
        self.parts_proxy = FilterProxy(self)
        self.parts_proxy.setSourceModel(self.parts_model)
        self.parts.setModel(self.parts_proxy)
        self.tree = configure_view(QTreeView())
        self.tree_model = TreeModel((Column('Montaj / parça', 'name'), Column('Pozisyon', 'number'),
            Column('Tür', 'kind'), Column('Ağırlık (kg)', 'mass_kg', mass),
            Column('Konfigürasyon', 'configuration'), Column('Dosya yolu', 'path')))
        self.tree_proxy = FilterProxy(self, tree=True)
        self.tree_proxy.setSourceModel(self.tree_model)
        self.tree.setModel(self.tree_proxy)
        self.tree.setColumnWidth(0, 330)
        self.tabs.addTab(self.parts, 'Parça listesi')
        self.tabs.addTab(self.tree, 'Ürün ağacı')
        self.parts.doubleClicked.connect(self.details)
        self.tree.doubleClicked.connect(self.details)
        self.layout.addWidget(self.tabs, 1)
        self.selection = label('Bir satır seçerek ayrıntıları görün. Excel’e tüm montaj aktarılır.', 'muted')
        self.layout.addWidget(self.selection)
        for view in (self.parts, self.tree):
            view.selectionModel().currentChanged.connect(self.select_row)
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(120)
        self.search_timer.setSingleShot(True)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self.filter)
        self.expand_timer = QTimer(self)
        self.expand_timer.setInterval(0)
        self.expand_timer.timeout.connect(self.expand_batch)
        self.expand_pending = []
        self.finish_layout()

    def set_busy(self, busy):
        super().set_busy(busy)
        self.export_button.setEnabled(not busy and self.result is not None)

    def clear(self):
        if self.busy:
            return
        self.expand_timer.stop()
        self.expand_pending.clear()
        self.result = None
        self.parts_model.replace([])
        self.tree_model.replace([])
        self.export_button.setEnabled(False)
        self.selection.setText('Bir satır seçerek ayrıntıları görün. Excel’e tüm montaj aktarılır.')
        self.summary.setText('Henüz montaj okunmadı.')

    def scan(self):
        if not self.can_start():
            return
        self.clear()
        include = self.form.value('include_excluded')
        self.jobs.start(self, lambda sink, stop: scan_worker(sink, stop, include_excluded=include))
        self.set_status('Montaj, alt parçalar ve ağırlıkları okunuyor…')

    def load_result(self, result):
        self.result = result
        self.parts_model.replace([asdict(part) for part in result.parts])
        self.tree_model.replace([dict(asdict(node), id=node.number) for node in result.tree])
        self.tree.expandToDepth(0)
        self.summary.setText(f'{PureWindowsPath(result.assembly).name} · {result.configuration}\n'
            f'{len(result.parts)} farklı parça · {result.total_parts} adet · Toplam: {mass(result.total_mass_kg)} kg · '
            f'Bastırılmış: {result.suppressed} · BOM dışı: {result.excluded}')
        self.export_button.setEnabled(not self.busy)

    def filter(self):
        query = self.search.text()
        self.parts_proxy.set_query(query)
        self.tree_proxy.set_query(query)
        if query:
            self.expand_all()

    def expand_all(self):
        self.expand_pending = [QPersistentModelIndex(self.tree_proxy.index(row, 0))
                               for row in range(self.tree_proxy.rowCount())]
        self.expand_timer.start()

    def expand_batch(self):
        for _ in range(min(100, len(self.expand_pending))):
            index = self.expand_pending.pop()
            if not index.isValid():
                continue
            self.tree.expand(index)
            self.expand_pending.extend(QPersistentModelIndex(self.tree_proxy.index(row, 0, index))
                                       for row in range(self.tree_proxy.rowCount(index)))
        if not self.expand_pending:
            self.expand_timer.stop()

    def select_row(self, index, previous=None):
        if not index.isValid():
            return
        row = index.data(Qt.UserRole) or {}
        self.selection.setText(f"{row.get('name', '')} · {row.get('configuration', '')}\n{row.get('path', '')}")

    def details(self, index):
        if index.isValid():
            row = index.data(Qt.UserRole) or {}
            show_details(self, row.get('name', 'BOM satırı'), '\n'.join(f'{key}: {value}' for key, value in row.items()))

    def copy_path(self):
        view = self.tree if self.tabs.currentIndex() == 1 else self.parts
        row = view.currentIndex().data(Qt.UserRole)
        if row:
            QApplication.clipboard().setText(row.get('path', ''))
            self.set_status('Dosya yolu panoya kopyalandı.')

    def export(self):
        if self.result is None or not self.can_start():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Ürün ağacını Excel dosyasına kaydet',
            PureWindowsPath(self.result.assembly).stem + '_BOM.xlsx', 'Excel (*.xlsx)')
        if path:
            result = self.result
            self.jobs.start(self, lambda sink, stop: services.write_bom(result, path, sink, stop))
            self.set_status('Excel dosyası hazırlanıyor…')

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'bom_phase':
                self.set_status(value)
            elif kind == 'bom_done':
                state = value.get('state')
                if state == 'completed':
                    self.load_result(value['result'])
                    self.set_status('Montaj ve ağırlık bilgileri okundu. Excel’e aktarabilirsiniz.')
                elif state == 'exported':
                    self.set_status('Excel kaydedildi: ' + value['path'])
                elif state == 'cancelled':
                    self.set_status('İşlem durduruldu; mevcut sonuçlar korundu.')
                else:
                    self.set_status(value.get('error', 'BOM işlemi tamamlanamadı.'), True)
            elif kind == 'job_error':
                self.set_status(value['error'], True)
