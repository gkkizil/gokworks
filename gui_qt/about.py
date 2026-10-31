"""Application information and developer contact details in native Qt dialogs."""
from html import escape

from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QWidget

from shared.app_info import AUTHOR,GITHUB_URL,EMAIL,LINKEDIN_URL,COPYRIGHT,DISCLAIMER,version_text
from .components import button,label,scroll


def link(text,target):
    widget=label(f'<a href="{escape(target,quote=True)}">{escape(text)}</a>')
    widget.setTextFormat(Qt.RichText)
    widget.setTextInteractionFlags(Qt.TextBrowserInteraction)
    widget.setOpenExternalLinks(False);widget.setToolTip(target)
    widget.linkActivated.connect(lambda url:QDesktopServices.openUrl(QUrl(url)))
    return widget


class AboutDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('GOKWORKS · Hakkında');self.setMinimumSize(380,300)
        available=self.screen().availableGeometry()
        self.resize(min(620,available.width()-40),min(420,available.height()-60))
        outer=QVBoxLayout(self);outer.setSpacing(12)
        content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(4,4,4,4);body.setSpacing(12)
        body.addWidget(label('GOKWORKS','section'))
        body.addWidget(label('CAD aktarımı, ürün ağacı, sac yerleşimi, profil kesimi ve mühendislik hesaplamaları '
                             'için geliştirilmiş ücretsiz ve açık kaynaklı masaüstü mühendislik araçları.'))
        fields=QFormLayout();fields.setSpacing(8)
        self.developer=label(AUTHOR);self.version=label(version_text())
        self.version.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.github=link('github.com/gkkizil/gokworks',GITHUB_URL)
        fields.addRow('Geliştirici',self.developer);fields.addRow('Sürüm',self.version);fields.addRow('GitHub',self.github)
        body.addLayout(fields)
        body.addWidget(label('Sorumluluk reddi','section'))
        self.disclaimer=label(DISCLAIMER);self.disclaimer.setTextFormat(Qt.PlainText)
        self.disclaimer.setTextInteractionFlags(Qt.TextSelectableByMouse);body.addWidget(self.disclaimer)
        body.addWidget(label(COPYRIGHT,'muted'));body.addStretch()
        outer.addWidget(scroll(content),1)
        actions=QHBoxLayout()
        actions.addStretch();actions.addWidget(button('Kapat',self.accept))
        outer.addLayout(actions)


class ContactDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('GOKWORKS · İletişim');self.setMinimumSize(340,240)
        available=self.screen().availableGeometry()
        self.resize(min(520,available.width()-40),min(300,available.height()-60))
        layout=QVBoxLayout(self);layout.setContentsMargins(16,16,16,12);layout.setSpacing(12)
        layout.addWidget(label('İletişim','section'));layout.addWidget(label(AUTHOR))
        layout.addWidget(label('GOKWORKS ile ilgili soru, öneri ve geri bildirimleriniz için:','muted'))
        fields=QFormLayout();fields.setSpacing(10)
        self.email=link(EMAIL,'mailto:'+EMAIL);self.linkedin=link('Orhan Gökkızıl · LinkedIn',LINKEDIN_URL)
        fields.addRow('E-posta',self.email);fields.addRow('LinkedIn',self.linkedin);layout.addLayout(fields)
        layout.addStretch();layout.addWidget(label(COPYRIGHT,'muted'))
        actions=QHBoxLayout();actions.addStretch();actions.addWidget(button('Kapat',self.accept));layout.addLayout(actions)
