from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from gui_qt.app import create_application, MainWindow
from gui_qt.settings import SettingsStore
from modules.press_brake.demo import tools
from modules.press_brake.tool_picker import ToolPicker
from modules.press_brake.models import Segment


def test_profile_cards_search_favorites_and_type_specific_catalogues(qtbot, tmp_path):
    create_application([]); settings = SettingsStore(tmp_path/'settings.json')
    dialog = ToolPicker(tools(), 'punch', 'demo-punch', settings=settings)
    qtbot.addWidget(dialog); dialog.show(); qtbot.wait(30)
    assert dialog.cards.count() == 2 and all(t.kind == 'punch' for t in dialog.tools)
    assert dialog.cards.gridSize().width() > 150
    dialog.search.setText('wide')
    assert dialog.current_tool().id == 'demo-wide'
    assert dialog.cards.item(0).isHidden() and not dialog.cards.item(1).isHidden()
    dialog.favorite.setChecked(True)
    assert settings.get('press_brake_favorite_tools') == ['demo-wide']
    dialog.search.clear(); dialog.only_favorites.setChecked(True)
    assert dialog.current_tool().id == 'demo-wide' and dialog.cards.item(0).isHidden()
    dialog.search.setText('no such tool')
    assert not dialog.use_button.isEnabled() and dialog.profile.tool is None
    dialog.search.clear(); dialog.segment_edit.setText('-40:20; 10:30'); dialog.accept()
    assert dialog.selection.tool == 'demo-wide'
    assert dialog.selection.segments == (Segment(-40, 20), Segment(10, 30))
    assert settings.flush()
    assert SettingsStore(settings.path).get('press_brake_favorite_tools') == ['demo-wide']


def test_multi_v_channel_and_segments_apply_together_and_invalid_segments_stay_open(qtbot):
    create_application([])
    d = ToolPicker(tools(), 'die', 'demo-die', assigned_segments=(Segment(-30, 60),))
    qtbot.addWidget(d); d.show()
    assert d.cards.count() == 1 and d.profile.tool.kind == 'die'
    assert d.segment_edit.text() == '-30:60'
    d.channel.setCurrentIndex(d.channel.findData('V24'))
    assert d.profile.channel.center == (36, 0)
    d.segment_edit.setText('0:10;5:10'); d.accept()
    assert d.selection is None and d.isVisible() and d.error.text()
    d.segment_edit.setText('-30:20; 0:30'); d.accept()
    assert d.selection.tool == 'demo-die' and d.selection.channel == 'V24'
    assert len(d.selection.segments) == 2


def test_actual_workbench_buttons_open_card_picker_and_commit_once(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.show(); w.navigate('press_brake'); p = w.pages['press_brake']; p.library_path = tmp_path/'tools.json'
    p.load_demo('L120'); qtbot.waitUntil(lambda: not w.jobs.busy and not p.preview_pending, timeout=15000)
    revision = p.plan.revision
    def pick_punch():
        d = QApplication.activeModalWidget(); assert isinstance(d, ToolPicker)
        d.search.setText('WIDE'); d.segment_edit.setText('-40:80'); d.use_button.click()
    QTimer.singleShot(40, pick_punch); p.punch_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy and not p.preview_pending, timeout=15000)
    assert p.plan.steps[0].punch == 'demo-wide' and p.plan.revision == revision+1
    assert 'DEMO-WIDE' in p.punch_button.text() and not p.punch.isVisible()
    def pick_die():
        d = QApplication.activeModalWidget(); assert isinstance(d, ToolPicker)
        d.channel.setCurrentIndex(d.channel.findData('V24')); d.use_button.click()
    QTimer.singleShot(40, pick_die); p.die_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy and not p.preview_pending, timeout=15000)
    assert p.plan.steps[0].channel == 'V24' and p.plan.revision == revision+2
    assert p.result is None and not p.pdf_button.isEnabled()
    w.close()


def test_cancel_does_not_change_selection_and_both_themes_fit_compact_dialog(qtbot):
    create_application([])
    for appearance in ('light', 'dark'):
        d = ToolPicker(tools(), 'die', 'demo-die', appearance=appearance); qtbot.addWidget(d)
        d.resize(680, 500); d.show(); qtbot.wait(30)
        assert d.use_button.isVisible() and d.height() <= 560
        d.channel.setCurrentIndex(d.channel.findData('V24')); d.reject()
        assert d.selection is None
