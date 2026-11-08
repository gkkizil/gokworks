"""DXF / DWG: ayarlar üstte grup şeridinde, parça listesi ve önizleme altta tam genişlikte."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt

from gui_qt.app import MainWindow, create_application


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    w = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(w); w.show(); w.navigate('dxf_dwg')
    yield w
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def top(widget, page):
    return widget.mapTo(page, QPoint()).y()


@pytest.mark.parametrize('size', [(1600, 900), (1366, 768), (820, 560)])
def test_settings_ribbon_on_top_list_and_preview_below_commands_visible(window, qtbot, size):
    page = window.pages['dxf_dwg']; window.resize(*size); qtbot.wait(40)
    assert page.splitter.orientation() == Qt.Vertical and page.splitter.count() == 2
    assert page.splitter.widget(0) is page.source_scroll and page.splitter.widget(1) is page.results
    assert top(page.source_scroll, page) < top(page.results, page)
    assert page.results.width() >= page.width() - 40                  # full width below the settings
    assert page.source_scroll.height() <= max(110, page.splitter.height() * .31) + 1 or size[1] >= 900
    assert page.results.height() >= 260
    assert page.command_bar.isVisible()
    for number in range(page.actions.count()):
        control = page.actions.itemAt(number).widget()
        if control.isVisible():
            assert page.rect().contains(control.mapTo(page, control.rect().bottomRight()))
    for widget in (page.form, page.output_form, page.options_form, page.source_files):
        assert page.ribbon.isAncestorOf(widget)


def test_groups_sit_side_by_side_when_wide_and_wrap_when_narrow(window, qtbot):
    page = window.pages['dxf_dwg']
    window.resize(1700, 900); qtbot.wait(40)
    assert page.ribbon.columns == 4
    tops = {top(group, page) for group in page.ribbon.groups}
    assert len(tops) == 1
    window.resize(820, 560); qtbot.wait(40)
    assert page.ribbon.columns < 4


def test_dragged_divider_is_kept_and_values_still_flow_to_the_export(window, qtbot):
    page = window.pages['dxf_dwg']; window.resize(1440, 900); qtbot.wait(40)
    page.splitter.moveSplitter(180, 1); qtbot.wait(10)
    assert abs(page.splitter.sizes()[0] - 180) <= 2
    window.resize(1500, 920); qtbot.wait(40)
    assert abs(page.splitter.sizes()[0] - 180) <= 2
    assert page.options.is_expanded() and not page.options.toggle.isVisible()
    page.form.set_value('format', 'DWG'); page.form.set_value('overwrite', True)
    assert page.form.values()['format'] == 'DWG' and page.form.values()['overwrite'] is True


def test_menu_bar_mirrors_options_and_runs_the_same_commands(window, qtbot):
    page = window.pages['dxf_dwg']; bar = page.menu_bar
    assert [a.text().replace('&', '') for a in bar.actions()] == ['Dosya', 'Kaynak', 'Çıktı', 'Seçenekler', 'Seçim', 'Aktarım']
    item = bar.items['Seçenekler/Üzerine yaz']
    item.trigger()
    assert page.form.values()['overwrite'] is item.isChecked()
    page.form.set_value('overwrite', not item.isChecked())
    assert item.isChecked() is page.form.values()['overwrite']
    bar.items['Çıktı türü/DWG'].trigger()
    assert page.form.value('format') == 'DWG'
    page.form.set_value('format', 'DXF')
    assert bar.items['Çıktı türü/DXF'].isChecked()
    bar.items['Dosya adı/Malzeme'].trigger()
    assert page.form.value('name_material') is True
    bar.items['Dosya/Klasörü tara'].trigger()                         # no source chosen → same message as the button
    assert 'kaynak' in page.status_text.lower()
