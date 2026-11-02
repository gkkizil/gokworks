"""Scroll areas with word-wrapped content must not recurse while resizing.

Before StableScrollArea, specific window widths made the ISO fits result pane
re-enter QScrollArea resize handling until the native stack overflowed.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui_qt.app import MainWindow, create_application
from gui_qt.components import StableScrollArea, scroll


def test_scroll_helper_uses_the_guarded_area(qtbot):
    content = QWidget()
    area = scroll(content)
    qtbot.addWidget(area)
    assert isinstance(area, StableScrollArea) and area.widget() is content


def test_wrapped_content_survives_a_width_sweep(qtbot):
    content = QWidget(); body = QVBoxLayout(content)
    for _ in range(12):
        text = QLabel('Kullanım yorumu (öneri): Hareketli / yağlı çalışma adayı\n'
                      'C = delik − mil: (+) boşluk, (−) sıkılık, 0 temas.\n'
                      'Montaj kuvveti, malzeme, sıcaklık ve yağlama ayrıca değerlendirilir.')
        text.setWordWrap(True); body.addWidget(text)
    area = scroll(content); qtbot.addWidget(area); area.show()
    for width in range(160, 700, 3):
        area.resize(width, 420); qtbot.wait(1)
    assert area.widget().width() <= area.viewport().width()


def test_iso_fits_page_survives_window_width_sweep(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window)
    window.resize(1440, 900); window.show()
    try:
        for theme in ('dark', 'light'):
            window.set_theme(theme); window.navigate('iso_fits')
            for width in range(820, 1700, 7):
                window.resize(width, 700); qtbot.wait(1)
                assert not window.grab().isNull()
    finally:
        window.settings.flush()
