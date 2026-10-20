"""Qt integration with real DXF files, real background jobs and responsive state."""

import gc
from pathlib import Path
import threading

import ezdxf
import pytest
from PySide6.QtCore import QEvent, QCoreApplication, QTimer, Qt
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import MainWindow,create_application
from gui_qt.pages.nesting_widgets import Editor


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1440,960); w.show(); w.navigate('nesting')
    yield w
    if w.jobs.busy: w.jobs.cancel(); qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    assert w.settings.flush(); w.close(); w.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); gc.collect()


def load_parts(window,qtbot,tmp_path):
    f = tmp_path/'real.dxf'; doc = ezdxf.new(); doc.units = 4
    doc.modelspace().add_lwpolyline([(0,0),(50,0),(50,30),(0,30)],close=True); doc.saveas(f)
    page = window.pages['nesting']; page.import_files([str(f)],quantity=3)
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.project.parts) == 1
    assert page.part_model.rows[0]['quantity'] == 3
    return page


def test_real_import_nest_invalidate_and_source_preserved(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path); data = (tmp_path/'real.dxf').read_bytes()
    page.form.set_value('seconds','2'); page.form.set_value('quality','Hızlı')
    page.start_nest(); assert window.jobs.owner is page; assert not page.import_button.isEnabled()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result is not None and len(page.result.placements) == 3
    assert page.excel_button.isEnabled(); assert '3 parça' in page.summary.text()
    assert page.canvas.scene().items(); assert (tmp_path/'real.dxf').read_bytes() == data
    page.form.set_value('gap','7')
    assert page.result is None and not page.excel_button.isEnabled()
    assert 'yeniden' in page.status_text


def test_responsive_parts_panel_returns_after_resize_and_themes(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    for theme in ('dark','light'):
        window.set_theme(theme)
        for width,height in [(1440,960),(1024,768),(820,620),(1440,960)]:
            window.resize(width,height); qtbot.wait(60)
            if page.compact:
                assert page.tabs.indexOf(page.parts_panel) == 0
                page.tabs.setCurrentWidget(page.parts_panel)
            else:
                assert page.splitter.widget(0) is page.parts_panel
                assert page.parts_panel.isVisible()
            assert not window.grab().isNull()
            assert page.width() >= 550


def test_background_job_keeps_navigation_alive_and_can_cancel(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    page.project.parts[0].quantity = 300
    page.form.set_value('seconds','20'); page.form.set_value('quality','Yüksek')
    ticks = []; timer = QTimer(); timer.setInterval(10); timer.timeout.connect(lambda:ticks.append(1)); timer.start()
    page.start_nest(); window.navigate('weight'); qtbot.waitUntil(lambda:len(ticks)>5,timeout=4000)
    assert window.stack.currentWidget() is window.pages['weight']
    window.jobs.cancel(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000); timer.stop()
    assert len(ticks)>5
    assert page.result is not None and page.result.stopped


def test_invalid_parameters_cannot_start_job(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    page.form.set_value('seconds','0'); page.start_nest()
    assert not window.jobs.busy and page.result is None
    assert 'süresi' in page.status_text


def test_cost_only_changes_reprice_same_coordinates_in_background(window,qtbot,tmp_path,monkeypatch):
    page = load_parts(window,qtbot,tmp_path); page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    coordinates = [(p.x,p.y,p.angle) for p in page.result.placements]
    def unexpected(*args,**kwargs): raise AssertionError('Cost change must not rerun placement search')
    monkeypatch.setattr('nesting.engine.nest',unexpected)
    page.cost_form.set_value('setup','25')
    assert page.result is None and not page.pdf_button.isEnabled()
    qtbot.waitUntil(lambda:page.result is not None and not window.jobs.busy,timeout=8000)
    assert [(p.x,p.y,p.angle) for p in page.result.placements] == coordinates
    from nesting.accounting import calculate
    assert calculate(page.project,page.result)['setup'] == 25


def test_project_open_save_and_reports_use_jobs(window,qtbot,tmp_path,monkeypatch):
    page = load_parts(window,qtbot,tmp_path); page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    for kind,suffix in [('excel','.xlsx'),('pdf','.pdf')]:
        target = tmp_path/('report'+suffix)
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,p=str(target),**kwargs:(p,''))
        page.export_report(kind); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
        assert target.stat().st_size > 1000
    target = tmp_path/'portable.goknest.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
    page.save_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    page.new_project(); assert not page.project.parts
    (tmp_path/'real.dxf').unlink()
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(target),''))
    page.open_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result is not None and len(page.project.parts) == 1 and page.result.placements
    assert page.pdf_button.isEnabled()


def test_editor_preserves_validation_error_in_dialog(window,qtbot):
    def parse(form):
        from nesting.models import number
        return number(form.value('density'),'Yoğunluk',positive=True)
    d = Editor(window,'Malzeme',lambda f:f.text('density','Yoğunluk','nan'),parse)
    qtbot.addWidget(d); d.show(); d.submit()
    assert d.value is None and 'Yoğunluk' in d.error.text()
    d.form.set_value('density','7850'); d.submit(); assert d.value == 7850
