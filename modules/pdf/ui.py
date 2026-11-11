"""PDF workspace, preserving the shared transfer commands and export engine."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout

from gui_qt.export import ExportPage
from gui_qt.components import Disclosure, label
from gui_qt.icons import icon
from gui_qt.theme import COLORS
from .presentation import PdfResultsPanel


class PdfPage(ExportPage):
    def __init__(self, context):
        super().__init__(context, 'pdf')
        self.description_label.setText('Teknik resimlerinizi tüm sayfalarıyla PDF olarak kaydedin.')
        self.results.choose_source.clicked.connect(self.source.browse)
        self.progressChanged.connect(self.results.show_progress)
        self._arrange_source()
        self.page_icon = QLabel(); self.page_icon.setObjectName('pdfPageIcon')
        self.page_icon.setFixedSize(36,36); self.page_icon.setAlignment(Qt.AlignCenter)
        captions = self.heading.takeAt(0).layout()
        title = QHBoxLayout(); title.setSpacing(10)
        title.addWidget(self.page_icon); title.addLayout(captions,1)
        self.heading.insertLayout(0,title,1)
        self.theme_changed()

    def create_results(self):
        return PdfResultsPanel(lambda:self.context.appearance)

    def _arrange_source(self):
        panel = self.source_scroll.widget(); layout = panel.layout()
        retained = (self.form,self.output_form,self.options,self.source_files)
        while layout.count():
            item = layout.takeAt(0); widget = item.widget()
            if widget is not None and widget not in retained:
                widget.hide(); widget.deleteLater()
        layout.setContentsMargins(0,0,6,0); layout.setSpacing(10)
        self.source_block = self._source_block('01','Kaynak çizimler',self.form)
        self.output_block = self._source_block('02','PDF çıktı klasörü',self.output_form,self.open_output_button)
        layout.addWidget(self.source_block); layout.addWidget(self.output_block)
        self.options_form.fields['recursive'].setText('Alt klasörleri dahil et')
        self.options_form.fields['overwrite'].setText('Mevcut PDF’lerin üzerine yaz')
        self.options.setContentsMargins(10,0,10,0)
        layout.addWidget(self.options)
        self.inventory = Disclosure('Bulunan teknik resimler',self.source_files,expanded=False)
        self.inventory.setContentsMargins(10,0,10,0)
        self.source_files.view.setMinimumHeight(140)
        layout.addWidget(self.inventory)
        layout.addStretch(1)
        hint_host = QWidget(); hint_layout = QVBoxLayout(hint_host)
        hint_layout.setContentsMargins(12,10,12,10)
        self.source_hint = label('Her çizim için bir PDF.\nTüm sayfalar dahil edilir.','muted')
        hint_layout.addWidget(self.source_hint)
        layout.addWidget(hint_host)
        for picker in (self.source,self.output):
            picker.entry.setToolTip(picker.text())
            picker.changed.connect(lambda text,p=picker:p.entry.setToolTip(text))

    @staticmethod
    def _source_block(number,title,form,trailing=None):
        block = QFrame(); block.setProperty('pdfBlock',True)
        body = QVBoxLayout(block); body.setContentsMargins(12,12,12,12); body.setSpacing(10)
        heading = QHBoxLayout(); heading.setSpacing(8)
        step = label(number,wrap=False); step.setProperty('pdfStep',True)
        heading.addWidget(step); heading.addWidget(label(title,'section'),1)
        if trailing is not None:heading.addWidget(trailing)
        body.addLayout(heading); body.addWidget(form)
        return block

    def theme_changed(self):
        super().theme_changed()
        if not hasattr(self,'page_icon'): return
        colors = COLORS[self.context.appearance]
        self.page_icon.setPixmap(icon('pdf',colors['accent']).pixmap(26,26))
        for picker in (self.source,self.output):
            picker.choose.setIcon(icon('folder',colors['muted']))
        self.results.refresh_icons()

    def refresh_outcome(self,*args):
        # The PDF summary already presents the same outcome counts above the
        # list. Keep the footer for filtered/total rows without a duplicate line.
        self.outcome.hide()
