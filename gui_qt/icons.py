"""Local Qt vector icons and stable Windows application identity."""

import os
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget

ASSETS = Path(__file__).resolve().parents[1] / 'gui/assets'


def set_application_identity():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GOKWORKS.Desktop')


def icon(name, color='#80B6F5'):
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    if name in ('pdf', 'dxf_dwg'):
        painter.drawRoundedRect(QRectF(11, 5, 27, 36), 3, 3)
        for y in (18, 25, 32):
            painter.drawLine(17, y, 31, y)
    elif name in ('bom', 'naming'):
        painter.drawRect(5, 6, 13, 11)
        painter.drawLine(12, 17, 12, 37)
        for y in (23, 36):
            painter.drawLine(12, y, 27, y)
            painter.drawRoundedRect(QRectF(27, y - 5, 15, 10), 2, 2)
    elif name == 'bolt':
        path = QPainterPath()
        for i, (x, y) in enumerate(((11, 7), (31, 7), (37, 13), (31, 20), (11, 20), (5, 13))):
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawRect(16, 20, 10, 21)
        for y in (25, 30, 35):
            painter.drawLine(16, y, 26, y - 3)
    elif name == 'weight':
        painter.drawRect(8, 15, 31, 26)
        painter.drawArc(16, 4, 15, 20, 0, 180 * 16)
        painter.drawLine(24, 23, 24, 33)
    elif name == 'iso_fits':
        painter.drawEllipse(6, 6, 35, 35)
        painter.drawEllipse(14, 14, 19, 19)
        painter.drawLine(3, 24, 44, 24)
    elif name == 'geometric_tolerances':
        painter.drawRect(6, 13, 36, 22)
        painter.drawLine(20, 13, 20, 35)
        painter.drawEllipse(10, 20, 7, 7)
        painter.drawLine(27, 19, 35, 29)
    else:
        painter.drawLine(8, 37, 8, 12)
        painter.drawLine(8, 37, 39, 37)
        painter.drawArc(8, 16, 22, 22, 0, 90 * 16)
    painter.end()
    return QIcon(pixmap)


class BrandLogo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.appearance = 'light'
        self.images = {key: QPixmap(str(ASSETS / f'GOK_logo_{key}_UI_1024.png')) for key in ('light', 'dark')}
        self.setFixedHeight(64)
        self.setMinimumWidth(120)

    def set_appearance(self, appearance):
        self.appearance = appearance
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        image = self.images[self.appearance]
        width = min(self.width() - 18, 164)
        height = width * image.height() / max(1, image.width())
        painter.drawPixmap(QRectF(8, (self.height() - height) / 2, width, height), image, QRectF(image.rect()))
