"""PDF workspace presentation only; existing result models and commands remain in use."""
from collections import Counter
from pathlib import PureWindowsPath

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QSizePolicy

from gui_qt.components import ResultsPanel, button, label, separator
from gui_qt.icons import icon
from gui_qt.models import Column
from gui_qt.theme import COLORS


class PdfResultsPanel(ResultsPanel):
    def __init__(self, appearance):
        self.appearance = appearance
        super().__init__(empty_hint='Kaynak klasörünü seçin ve teknik resimlerinizi tarayın.')
        self.setObjectName('pdfResults')
        self.model.columns = (Column('Teknik resim','source',lambda value:PureWindowsPath(str(value)).name),
                              *self.model.columns[1:])
        self.model.headerDataChanged.emit(Qt.Horizontal,0,0)
        self.summary = QFrame(); self.summary.setObjectName('pdfSummary')
        summary = QVBoxLayout(self.summary)
        summary.setContentsMargins(12,10,12,10); summary.setSpacing(8)
        metrics = QHBoxLayout(); metrics.setContentsMargins(0,0,0,0); metrics.setSpacing(12)
        self.metrics = {}
        for key,title in (('total','Teknik resim'),('success','Aktarılan'),('skipped','Atlanan'),('error','Hatalı')):
            cell = QVBoxLayout(); cell.setSpacing(1)
            caption = label(title,'muted',wrap=False)
            value = label('0','result',wrap=False)
            value.setProperty('metricTitle',title)
            value.setAccessibleName(title+' sayısı')
            self.metrics[key] = value
            cell.addWidget(caption); cell.addWidget(value)
            metrics.addLayout(cell,1)
        summary.addLayout(metrics)
        summary.addWidget(separator())
        state = QHBoxLayout(); state.setSpacing(8)
        self.stage = label('Kaynak klasörünü seçerek başlayın.','muted',wrap=False)
        self.stage.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.stage.setAccessibleName('PDF aktarım durumu')
        self.format_label = label('SLDDRW / PDF','muted',wrap=False)
        self.format_label.setProperty('pdfFormat',True)
        state.addWidget(self.stage,1); state.addWidget(self.format_label)
        summary.addLayout(state)
        self.transfer_progress = QProgressBar(); self.transfer_progress.setTextVisible(False)
        self.transfer_progress.setAccessibleName('PDF aktarım ilerlemesi')
        self.transfer_progress.hide(); summary.addWidget(self.transfer_progress)
        self.layout.insertWidget(0,self.summary)
        self.layout.setSpacing(10)

        empty = self.empty_state
        self.document_icon = QLabel(); self.document_icon.setAlignment(Qt.AlignCenter)
        empty.layout().insertWidget(1,self.document_icon)
        empty.title.setProperty('role','title')
        empty.detail.setMaximumWidth(420)
        empty.layout().setAlignment(empty.detail,Qt.AlignHCenter)
        self.choose_source = button('Kaynak klasörü seç')
        self.choose_source.setAccessibleName('PDF aktarımı için kaynak klasörü seç')
        empty.layout().insertWidget(empty.layout().count()-1,self.choose_source,alignment=Qt.AlignHCenter)
        self.search.setPlaceholderText('Teknik resim adı veya açıklama ara…')
        self.report_menu.setToolTip('Raporu kaydet veya işlem günlüğünü kopyala')
        self._pdf_viewport = self.table.viewport()
        self._pdf_viewport.installEventFilter(self)
        for signal in (self.model.modelReset,self.model.rowsInserted,self.model.dataChanged):
            signal.connect(self.refresh_summary)
        self.refresh_icons(); self.refresh_count()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # One quiet report menu keeps the file toolbar readable at every width.
        self.save.hide(); self.copy_log.hide(); self.report_menu.show()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Resize and watched is self._pdf_viewport:
            self.fit_empty_copy()
        return super().eventFilter(watched,event)

    def fit_empty_copy(self):
        width = max(120,min(420,self.table.viewport().width()-48))
        detail = self.empty_state.detail
        detail.setFixedWidth(width)
        detail.setMinimumHeight(max(detail.fontMetrics().height(),detail.heightForWidth(width)))

    def refresh_icons(self):
        colors = COLORS[self.appearance()]
        self.document_icon.setPixmap(icon('pdf',colors['accent']).pixmap(48,48))
        self.choose_source.setIcon(icon('folder',colors['muted']))
        self.report_menu.setIcon(icon('export',colors['muted']))

    def refresh_count(self,*args):
        super().refresh_count(*args)
        if not hasattr(self,'summary'): return
        empty = self.model.rowCount()==0 and not self.busy
        self.document_icon.setVisible(empty)
        self.choose_source.setVisible(empty)
        if empty:
            self.empty_state.title.setText('Teknik resimlerinizi PDF’e aktarın')
            self.empty_state.detail.setText('Kaynak klasörünü seçin, dosyaları tarayın ve aktarımı başlatın. Her teknik resmin tüm sayfaları kendi PDF dosyasına kaydedilir.')
        self.fit_empty_copy()
        self.refresh_summary()

    def refresh_summary(self,*args):
        if not hasattr(self,'summary'): return
        counts = Counter(row.get('status') for row in self.model.rows)
        values = {'total':self.model.rowCount(),**counts}
        for key,widget in self.metrics.items():
            count = values.get(key,0); widget.setText(str(count))
            widget.setAccessibleName(f'{widget.property("metricTitle")}: {count}')
            tone = 'success' if key=='success' else 'danger' if key=='error' else 'text'
            widget.setProperty('pdfTone',tone if count else 'muted')
            widget.style().unpolish(widget); widget.style().polish(widget)
        processed = sum(counts[k] for k in ('success','partial','skipped','error'))
        total = self.model.rowCount()
        self.stage.setText('İşlem sürüyor…' if self.busy else f'{processed} / {total} dosya işlendi' if processed
                           else f'{total} teknik resim · aktarıma hazır' if total else 'Kaynak klasörünü seçerek başlayın.')
        if counts['partial']:
            self.stage.setText(self.stage.text()+f' · {counts["partial"]} kısmi')
        self.stage.setToolTip(self.stage.text())
        if not self.busy:
            self.transfer_progress.setRange(0,max(1,total))
            self.transfer_progress.setValue(processed)
            self.transfer_progress.setVisible(processed>0)

    def set_busy(self,busy):
        super().set_busy(busy)
        self.choose_source.setEnabled(not busy)
        if busy:
            self.transfer_progress.setRange(0,0); self.transfer_progress.show()
        self.refresh_summary()

    def show_progress(self,current,total):
        self.transfer_progress.setRange(0,max(1,total))
        self.transfer_progress.setValue(current)
        self.transfer_progress.setVisible(total>0)
