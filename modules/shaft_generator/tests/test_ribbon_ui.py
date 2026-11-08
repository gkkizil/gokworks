"""Parametrik mil: üstte komut şeridi (bölüm → komut), altta mil görünüşleri."""

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QBoxLayout

from gui_qt.app import create_application
from gui_qt.workers import JobManager
from gui_qt.settings import SettingsStore
from modules.shaft_generator.ribbon import CATEGORIES
from modules.shaft_generator.ui import ShaftPage


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path / 'settings.json'), jobs=JobManager(), appearance='dark')
    page = ShaftPage(context); qtbot.addWidget(page); page.resize(1400, 900); page.show(); qtbot.wait(10)
    yield page
    page.settings.flush()


def test_ribbon_is_above_the_editor_and_views_are_below(page):
    ribbon, editor, views = (w.mapTo(page, w.rect().topLeft()).y() for w in (page.ribbon, page.source_scroll, page.views))
    assert ribbon < editor < views
    assert page.splitter.widget(0) is page.source_scroll and page.splitter.widget(1) is page.views
    assert [b.text() for b in page.ribbon.category_buttons.values()] == [title for _, title, _, _ in CATEGORIES]


@pytest.mark.parametrize('command,index', [('stages', 0), ('groove', 1), ('keyway', 2), ('chamfer', 3), ('fillet', 4),
                                           ('cosmetic_thread', 5), ('bore', 6), ('bulk', 7)])
def test_each_command_opens_its_editor_and_marks_its_category(page, command, index):
    page.ribbon.command_buttons[command].click()
    assert page.tabs.currentIndex() == index and page.section_picker.currentData() == index
    category = page.ribbon.command_of[command]
    assert page.ribbon.category_buttons[category].isChecked()
    shown = [k for k, b in page.ribbon.command_buttons.items() if b.isVisible()]
    assert shown == [k for k in page.ribbon.command_buttons if page.ribbon.command_of[k] == category]
    assert page.ribbon.command_buttons[command].isChecked()


def test_category_click_opens_its_first_command_and_drawing_is_reachable(page):
    page.ribbon.category_buttons['channels'].click()
    assert page.tabs.currentIndex() == 1
    page.ribbon.category_buttons['drawing'].click()
    assert page.tabs.currentIndex() == page.drawing_tab
    page.ribbon.command_buttons['keyway'].click(); page.add_operation('keyway')
    page.ribbon.command_buttons['stages'].click()
    page.select_operation(page.project.operations[-1].id)
    assert page.tabs.currentIndex() == 2 and page.ribbon.command_buttons['keyway'].isChecked()


def test_add_button_is_in_the_editor_header_and_fields_fit_without_scrolling(page, qtbot):
    page.ribbon.command_buttons['groove'].click(); qtbot.wait(20)
    add = page.add_operation_buttons['groove']
    viewport = page.source_scroll.viewport()
    assert add.isVisible() and viewport.rect().contains(add.mapTo(viewport, add.rect().bottomRight()))
    for control in page.operation_fields['groove'].values():
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().bottomRight()))


@pytest.mark.parametrize('size,stacked,compact', [((1400, 900), True, False), ((820, 520), False, False), ((600, 450), False, True)])
def test_views_and_ribbon_adapt_to_the_window(page, qtbot, size, stacked, compact):
    page.resize(*size); qtbot.wait(30)
    assert (page.views.box.direction() == QBoxLayout.TopToBottom) == stacked
    style = next(iter(page.ribbon.category_buttons.values())).toolButtonStyle()
    assert (style.name == 'ToolButtonIconOnly') == compact
    for view in (page.top_view, page.section_view):
        assert view.width() >= 180 and view.height() >= 170
    assert page.rect().contains(page.create_button.mapTo(page, page.create_button.rect().bottomRight()))


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_ribbon_follows_the_theme(page, theme):
    page.context.appearance = theme; page.theme_changed()
    for button in page.ribbon.category_buttons.values():
        assert not button.icon().isNull()
    assert not page.grab().isNull()


def test_menu_bar_reaches_the_same_commands_and_settings(page):
    bar = page.menu_bar
    assert [a.text().replace('&', '') for a in bar.actions()] == ['Dosya', 'Kademe', 'Kanal', 'Kenar', 'Diş ve delik', 'Teknik resim']
    stages = len(page.project.stages)
    bar.items['Kademe/Kademe ekle'].trigger()
    assert len(page.project.stages) == stages + 1
    bar.items['Kanal/Kama kanalı ekle…'].trigger()
    assert page.tabs.currentIndex() == 2 and page.ribbon.command_buttons['keyway'].isChecked()
    bar.items['Diş ve delik/İç deliği aç'].trigger()
    assert page.bore_enabled.isChecked() and page.project.bore is not None
    page.bore_enabled.setChecked(False)
    assert not bar.items['Diş ve delik/İç deliği aç'].isChecked()
    assert bar.items['Dosya/SolidWorks’te çiz'].isEnabled() and bar.items['Dosya/Proje kaydet…'].isEnabled()
