"""Shared vector contours for interactive preview and report drawings."""

from modules.nesting.geometry import rings, placed

PALETTE = ('#69a9e9', '#b29be0', '#e3b76e', '#65bec8', '#de8d98', '#8eafe0', '#c3b285')


def painter_path(geometry):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainterPath
    path = QPainterPath(); path.setFillRule(Qt.OddEvenFill)
    for _, coords in rings(geometry):
        path.moveTo(coords[0][0], -coords[0][1])
        for x, y in coords[1:]:
            path.lineTo(x, -y)
        path.closeSubpath()
    return path


def draw_sheet(painter, rectangle, project, result, key):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QFont
    sheet = project.sheet(key[0])
    scale = min((rectangle.width()-40)/sheet.width, (rectangle.height()-50)/sheet.height)
    left = rectangle.left()+(rectangle.width()-sheet.width*scale)/2
    bottom = rectangle.top()+(rectangle.height()+sheet.height*scale)/2
    painter.save(); painter.translate(left, bottom); painter.scale(scale, scale)
    pen = QPen(QColor('#64748b')); pen.setWidthF(1/scale); painter.setPen(pen)
    painter.setBrush(QColor('#f1f5f9')); painter.drawRect(QRectF(0, -sheet.height, sheet.width, sheet.height))
    for p in result.placements:
        if (p.sheet_id, p.sheet_number) != key:
            continue
        part = project.part(p.part_id); g = placed(part, p)
        color = PALETTE[project.parts.index(part) % len(PALETTE)]
        painter.setBrush(QColor(color)); painter.drawPath(painter_path(g))
        minx, miny, maxx, maxy = g.bounds
        center=g.representative_point()
        painter.save(); painter.translate(center.x,-center.y); painter.scale(1/scale, 1/scale)
        painter.setPen(QColor('#12243a')); painter.setFont(QFont('Arial', 8))
        painter.drawText(QRectF(-(maxx-minx)*scale/2, -12, (maxx-minx)*scale, 24), Qt.AlignCenter, part.code)
        painter.restore(); painter.setPen(pen)
    painter.restore()


def sheet_png(project, result, key):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
    from PySide6.QtGui import QImage, QPainter
    image = QImage(1000, 700, QImage.Format_ARGB32); image.fill(0xffffffff)
    painter = QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
    try:
        draw_sheet(painter, QRectF(0, 0, 1000, 700), project, result, key)
    finally:
        painter.end()
    buffer = QBuffer(); buffer.open(QIODevice.WriteOnly); image.save(buffer, 'PNG')
    return bytes(buffer.data())
