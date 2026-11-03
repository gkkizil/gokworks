"""QA (2026-11-03): no single-line label or button text is cut off on any page.

Runs at the smallest supported desktop (1366 x 768) and at a wide window. The
same audit was run manually at 100/125/150 % for 1366x768, 1920x1080 and
2560x1440 (QT_SCALE_FACTOR must be set before QApplication, so the scale
variants are not repeated inside one pytest process).
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QRadioButton, QToolButton

from gui_qt.app import MODULES, MainWindow, create_application


def clipped_controls(page):
    found = []
    for widget in (page.findChildren(QLabel) + page.findChildren(QPushButton) + page.findChildren(QCheckBox)
                   + page.findChildren(QRadioButton) + page.findChildren(QToolButton)):
        if not widget.isVisible() or widget.width() <= 0:
            continue
        text = widget.text()
        if not text or '<' in text:
            continue
        if isinstance(widget, QLabel):
            if widget.wordWrap() or (widget.pixmap() is not None and not widget.pixmap().isNull()):
                continue
            need = max(widget.fontMetrics().horizontalAdvance(line) for line in text.split('\n'))
            have = widget.contentsRect().width() - 2 * widget.margin()
        else:
            if isinstance(widget, QToolButton) and widget.toolButtonStyle() == Qt.ToolButtonIconOnly:
                continue
            need, have = widget.sizeHint().width(), widget.width()
        if need > have + 2:
            found.append(f'{type(widget).__name__} "{text[:50]}" needs {need}px, has {have}px')
    return found


@pytest.mark.parametrize('size', [(1366, 768), (1920, 1080)])
def test_no_page_cuts_off_single_line_text(qtbot, tmp_path, size):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json')
    window.resize(*size)
    qtbot.addWidget(window)
    window.show()
    problems = {}
    for key, _, _ in MODULES:
        window.navigate(key)
        qtbot.wait(5)
        found = clipped_controls(window.pages[key])
        if found:
            problems[key] = found
    assert not problems, problems
