import threading
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from gui_qt.app import MainWindow, create_application
from gui_qt.workspace import WORKSPACES


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1366, 900); w.show(); w.navigate('press_brake')
    w.pages['press_brake'].library_path = tmp_path/'tools.json'
    yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=20000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def finish(w, qtbot, timeout=60000):
    qtbot.waitUntil(lambda: not w.jobs.busy and not w.pages['press_brake'].preview_pending, timeout=timeout)


def test_navigation_demo_reorder_assignment_and_compact_themes(window, qtbot):
    w = window; p = w.pages['press_brake']
    assert 'press_brake' in dict(WORKSPACES)['Üretim']
    p.load_demo('U'); finish(w, qtbot)
    assert p.plan.part.demo and p.viewer.frame is not None
    assert p.plan.steps[0].bend == 'B01'
    p.down.click(); finish(w, qtbot)
    assert p.plan.steps[0].bend == 'B02' and p.bends.currentRow() == 1
    p.punch.setCurrentIndex(p.punch.findData('demo-wide')); finish(w, qtbot)
    assert p.plan.steps[1].punch == 'demo-wide'
    assert 'Takım değişimi' in p.bends.item(1).text()
    p.channel.setCurrentIndex(p.channel.findData('V24')); finish(w, qtbot)
    assert p.plan.steps[1].channel == 'V24'
    for theme in ('light', 'dark'):
        w.set_theme(theme)
        for size in ((1366, 900), (1024, 700), (820, 560)):
            w.resize(*size); qtbot.wait(30)
            assert p.check_button.isVisible() and p.demo_button.isVisible() and p.play.isVisible()
            assert p.width() >= 550 and p.viewer.width() >= 100
    w.navigate('pdf'); w.navigate('press_brake')
    assert w.pages['press_brake'] is p and p.plan.steps[1].channel == 'V24'


@pytest.mark.timeout(180)
def test_normal_entry_real_worker_playback_pdf_and_stale_result_invalidation(window, qtbot, tmp_path):
    p = window.pages['press_brake']; p.load_demo('L120'); finish(window, qtbot)
    p.channel.setCurrentIndex(p.channel.findData('V24')); finish(window, qtbot)
    p.check_button.click(); assert window.jobs.busy
    # The normal GUI event loop remains available while native solids are checked.
    window.set_theme('light'); qtbot.wait(40)
    finish(window, qtbot, 150000)
    assert p.result is not None, p.status_text
    assert p.result.status == 'clear' and p.pdf_button.isEnabled()
    assert {f.phase for f in p.result.frames} == {'approach', 'bend', 'retract'}
    assert p.result.steps[0].samples > 30
    p.play.click(); assert p.timer.isActive()
    before = p.frame_index; qtbot.waitUntil(lambda: p.frame_index > before, timeout=5000)
    p.pause(); p.formed_button.click(); assert p.viewer.mesh is p.formed_mesh
    p.flat_button.click(); assert p.viewer.mesh is p.flat_mesh
    path = tmp_path/'operator.pdf'; p.export_pdf(path); finish(window, qtbot)
    assert path.read_bytes().startswith(b'%PDF') and path.stat().st_size > 10000
    p.punch.setCurrentIndex(p.punch.findData('demo-wide')); finish(window, qtbot)
    assert p.result is None and not p.pdf_button.isEnabled()
    p.calculate(); finish(window, qtbot, 150000)
    assert p.result.status == 'collision' and p.result.steps[0].first_hit
    p.slider.setValue(0); p.toggle_play()
    for _ in range(len(p.result.frames)+1):
        if not p.timer.isActive():
            break
        p.advance()
    assert not p.timer.isActive() and p.result.frames[p.frame_index].hits
    old = p.result
    p.direction.setCurrentIndex(1); finish(window, qtbot)
    assert p.result is None and not p.pdf_button.isEnabled() and p.formed_mesh is None
    p.accept_result(p.generation-1, old)
    assert p.result is None


def test_worker_cancellation_does_not_publish_completed_result(window, qtbot):
    from modules.cad_converter.models import checkpoint
    p = window.pages['press_brake']; started = threading.Event()
    def operation(sink, stop):
        started.set(); stop.wait(10); checkpoint(stop)
        sink.put(('press_result', 'must not publish'))
    assert p.start(operation); qtbot.waitUntil(started.is_set)
    window.jobs.cancel(); finish(window, qtbot)
    assert p.result is None and 'durduruldu' in p.status_text


def test_live_com_is_not_required_to_open_workbench(window):
    p = window.pages['press_brake']
    assert p.plan is None and not p.check_button.isEnabled()
    assert p.sw_button.isVisible() and p.demo_button.isEnabled()


def test_dxf_tool_card_and_library_add_before_loading_part_preserves_existing_cards(window, qtbot, tmp_path, monkeypatch):
    from dataclasses import replace
    from modules.press_brake import ui
    from modules.press_brake.demo import tools
    from modules.press_brake.tooling import load_catalog, save_catalog
    from .test_tooling import drawing
    p = window.pages['press_brake']
    existing = replace(tools()[0], id='user-existing', demo=False)
    save_catalog((existing,), p.library_path)
    path = tmp_path/'tool.dxf'; path.write_text(drawing(), encoding='utf-8')
    class Editor(ui.ToolDialog):
        def exec(self):
            data = dict(maker='Own test maker', code='TEST-IMPORT', height='80', mount='0,80', segments='-20:40',
                        tool_interface='tongue-10x8', holder_interface='tongue-10x8', tip='0,0', tip_angle='45', tip_radius='.2')
            for key, value in data.items():
                self.fields[key].setText(value)
            self.confirm.setChecked(True); self.accept()
            assert self.tool is not None
            return True
    monkeypatch.setattr(ui, 'ToolDialog', Editor)
    p.load_tool_dxf(path)
    qtbot.waitUntil(lambda: len(load_catalog(p.library_path)) == 2, timeout=15000)
    finish(window, qtbot)
    loaded = load_catalog(p.library_path)
    assert {t.code for t in loaded} == {existing.code, 'TEST-IMPORT'}
    imported = next(t for t in loaded if t.code == 'TEST-IMPORT')
    assert imported.section_dxf and imported.tip_radius == .2 and imported.mount.compatible
    assert imported.line_load is None and p.plan is None
