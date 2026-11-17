"""Regenerate the add-in icon strips from GOKWORKS' own tool icons.

    python solidworks_addin/make_icons.py

Writes icons/tools_<size>.png (one column per command, Tools.cs order) and
icons/main_<size>.png for sizes 20, 32, 40, 64, 96 and 128 px, as the
SolidWorks CommandManager expects (ICommandGroup.IconList / MainIconList).
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SIZES = (20, 32, 40, 64, 96, 128)
COLOUR = '#2F6FB2'      # reads on SolidWorks' light and dark toolbars


def icon_names():
    """Icon column per command, in Tools.cs order."""
    return re.findall(r'new Tool\("[^"]*", "[^"]*", "[^"]*", (?:true|false), Needs\.\w+(?: \| Needs\.\w+)?, "([a-z_]+)"\)',
                      (ROOT/'Tools.cs').read_text(encoding='utf-8'))


def main():
    sys.path.insert(0, str(ROOT.parent))
    from PySide6.QtCore import Qt, QRect, QSize
    from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap
    QGuiApplication.instance() or QGuiApplication([])
    from gui_qt.icons import icon
    logo = QPixmap(str(ROOT.parent/'assets'/'GOK_logo_light_UI_1024.png'))
    names = icon_names()
    out = ROOT/'icons'; out.mkdir(exist_ok=True)
    def draw(painter, name, rect):
        if name == 'app':
            painter.drawPixmap(rect, logo.scaled(rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            painter.drawPixmap(rect, icon(name, COLOUR).pixmap(rect.size()))
    for size in SIZES:
        strip = QImage(size*len(names), size, QImage.Format_ARGB32); strip.fill(Qt.transparent)
        painter = QPainter(strip); painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for i, name in enumerate(names):
            draw(painter, name, QRect(i*size, 0, size, size))
        painter.end(); strip.save(str(out/f'tools_{size}.png'))
        main = QImage(size, size, QImage.Format_ARGB32); main.fill(Qt.transparent)
        painter = QPainter(main); draw(painter, 'app', QRect(0, 0, size, size)); painter.end()
        main.save(str(out/f'main_{size}.png'))
    print(f'{len(names)} ikon × {len(SIZES)} boyut → {out}')


if __name__ == '__main__':
    main()
