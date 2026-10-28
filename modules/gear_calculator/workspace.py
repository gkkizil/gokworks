"""Shared three-column desktop / three-tab compact gear workspace."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter,QStackedWidget,QTabWidget


class GearWorkspace(QStackedWidget):
    def __init__(self,inputs,viewer,results,parent=None):
        super().__init__(parent)
        self.panels=(inputs,viewer,results);self.compact_mode=False
        self.splitter=QSplitter(Qt.Horizontal);self.splitter.setChildrenCollapsible(False)
        for panel in self.panels:self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(1,1);self.splitter.setSizes([290,600,310])
        self.compact_tabs=QTabWidget();self.addWidget(self.splitter);self.addWidget(self.compact_tabs)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        compact=self.width()<1100
        if compact==self.compact_mode:return
        self.compact_mode=compact
        if compact:
            for panel,title in zip(self.panels,('Parametreler','Görünüm','Sonuçlar / CAD')):
                self.compact_tabs.addTab(panel,title)
            self.compact_tabs.setCurrentIndex(1);self.setCurrentWidget(self.compact_tabs)
        else:
            while self.compact_tabs.count():self.compact_tabs.removeTab(0)
            for panel in self.panels:self.splitter.addWidget(panel);panel.show()
            self.setCurrentWidget(self.splitter);self.splitter.setSizes([290,max(300,self.width()-600),310])
