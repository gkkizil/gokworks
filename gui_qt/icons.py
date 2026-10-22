"""Local Qt vector icons and stable Windows application identity."""

import os
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


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
    elif name == 'cad_converter':
        painter.drawPolygon([QPointF(10, 14), QPointF(24, 6), QPointF(38, 14), QPointF(24, 22)])
        painter.drawLine(10, 14, 10, 32); painter.drawLine(10, 32, 24, 41)
        painter.drawLine(24, 22, 24, 41); painter.drawLine(24, 41, 38, 32)
        painter.drawLine(38, 14, 38, 32)
    elif name in ('bom', 'naming'):
        painter.drawRect(5, 6, 13, 11)
        painter.drawLine(12, 17, 12, 37)
        for y in (23, 36):
            painter.drawLine(12, y, 27, y)
            painter.drawRoundedRect(QRectF(27, y - 5, 15, 10), 2, 2)
    elif name in ('bolt', 'bolt_torque'):
        path = QPainterPath()
        for i, (x, y) in enumerate(((11, 7), (31, 7), (37, 13), (31, 20), (11, 20), (5, 13))):
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawRect(16, 20, 10, 21)
        for y in (25, 30, 35):
            painter.drawLine(16, y, 26, y - 3)
    elif name == 'nesting':
        painter.drawRect(5, 6, 38, 35)
        painter.drawRect(10, 11, 14, 12)
        painter.drawRect(28, 11, 10, 24)
        painter.drawRect(10, 27, 14, 8)
    elif name == 'profile_cutting':
        for y in (10, 24, 38):
            painter.drawRect(5, y-4, 38, 8)
        for x in (18, 31): painter.drawLine(x, 6, x, 14)
        painter.drawLine(26, 20, 26, 28)
        painter.drawLine(14, 34, 14, 42)
    elif name == 'weight':
        painter.drawRect(8, 15, 31, 26)
        painter.drawArc(16, 4, 15, 20, 0, 180 * 16)
        painter.drawLine(24, 23, 24, 33)
    elif name == 'tolerance_stack':
        for y in (11,24,37):
            painter.drawLine(7,y,41,y)
            painter.drawLine(10,y-4,10,y+4)
            painter.drawLine(37,y-4,37,y+4)
        painter.drawLine(13,8,18,11)
        painter.drawLine(18,11,13,14)
        painter.drawLine(35,21,30,24)
        painter.drawLine(30,24,35,27)
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
