"""Native workbench navigation, contextual commands and live inspector bindings."""

import gc
from pathlib import Path
import threading

import pytest
from PySide6.QtCore import Qt,QEvent,QCoreApplication
from PySide6.QtWidgets import QToolBar,QDockWidget

from gui_qt.app import MainWindow,create_application,MODULES
from modules.nesting.storage import load_project

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1440,900);w.show();qtbot.wait(40)
    yield w
    if w.jobs.busy:w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_workspaces_groups_and_search_navigate_existing_pages_without_reset(window,qtbot):
    w=window;pages=dict(w.pages)
    w.pages['weight'].form.set_value('length','2350')
    w.workspace_picker.setCurrentIndex(w.workspace_picker.findData('Üretim'))
    assert w.mode=='nesting'
    w.navigation['profile_cutting'].click()
    w.workspace_picker.setCurrentIndex(w.workspace_picker.findData('Aktarım'))
    assert w.mode=='pdf'
    w.workspace_picker.setCurrentIndex(w.workspace_picker.findData('Üretim'))
    assert w.mode=='profile_cutting'
    w.browser.search.setText('tork');qtbot.wait(10)
    assert w.navigation['bolt_torque'].isVisible() and not w.navigation['pdf'].isVisible()
    w.navigation['bolt_torque'].click();assert w.mode=='bolt_torque'
    w.browser.search.clear();group=w.browser.groups['Montaj'];group.toggle.click()
    assert not w.navigation['bom'].isVisible()
    w.navigate('bom');assert w.navigation['bom'].isVisible() and group.toggle.isChecked()
    assert w.pages==pages and w.pages['weight'].form.value('length')=='2350'
    assert not w.jobs.busy


def test_native_command_strip_stays_above_source_scrolling_and_uses_same_buttons(window,qtbot):
    for mode in ('pdf','dxf_dwg','cad_converter','bom','naming'):
        window.navigate(mode);p=window.pages[mode]
        assert isinstance(p.command_bar,QToolBar)
        if hasattr(p,'source_scroll'):p.source_scroll.verticalScrollBar().setValue(100000)
        qtbot.wait(20)
        for control in p.command_controls:
            if control.isVisible():
                assert p.command_bar.isAncestorOf(control)
                assert p.rect().contains(control.mapTo(p,control.rect().bottomRight()))
    assert isinstance(window.workbench_bar,QToolBar)


def example(w):
    p=w.pages['nesting'];p.project,r=load_project(ROOT/'docs/nesting-example/Ornek.goknest.json')
    p.sync_forms();p.refresh();p.show_result(r);w.navigate('nesting');return p


def test_inspector_shares_existing_parameters_and_changes_invalidate_only_results(window,qtbot):
    p=example(window);qtbot.wait(40);i=p.inspector
    assert isinstance(window.property_dock,QDockWidget) and window.property_dock.isVisible()
    old_parts=[part.id for part in p.project.parts]
    p.part_table.selectRow(0);qtbot.wait(10)
    assert i.part_name.text()==p.project.parts[0].code and i.edit_part_button.isEnabled()
    assert p.result is not None  # Selection does not change a plan.
    i.fields['gap'].setText('4,5')
    assert p.form.value('gap')=='4,5' and p.result is None
    p.form.set_value('margin','12');assert i.fields['margin'].text()=='12'
    p.form.set_value('rotation',False);assert not i.fields['rotation'].isChecked()
    assert [part.id for part in p.project.parts]==old_parts
    section=i.sections['YERLEŞİM'];section.toggle.click()
    assert not i.fields['gap'].isVisible() and p.form.value('gap')=='4,5'
    section.toggle.click();assert i.fields['gap'].isVisible()
    window.navigate('iso_fits');assert not window.property_dock.isVisible()
    window.navigate('nesting');assert window.property_dock.isVisible() and p.inspector is i


def test_inspector_reuses_existing_sheet_editor_and_follows_the_selected_sheet(window,monkeypatch):
    p=example(window);called=[]
    monkeypatch.setattr(p,'edit_sheet',lambda:called.append(p.selected(p.sheet_table)['id']))
    p.inspector.edit_sheet_button.click()
    assert called==[p.inspector.sheet.currentData()]


def test_inspector_resize_is_retained_on_navigation_and_window_resize(window,qtbot):
    example(window);qtbot.wait(30)
    window.resizeDocks([window.property_dock],[330],Qt.Horizontal);qtbot.wait(30)
    width=window.property_dock.width()
    assert abs(width-330)<10
    window.navigate('weight');window.navigate('nesting');qtbot.wait(30)
    assert abs(window.property_dock.width()-width)<10
    window.resize(1540,950);qtbot.wait(30)
    assert abs(window.property_dock.width()-width)<10


def test_status_preserves_full_details_and_accessible_error_feedback(window):
    window.pages['pdf'].set_status('Örnek hata\nAyrıntılı kaynak bilgisi',True)
    assert window.global_status.text()=='Örnek hata'
    assert '\nAyrıntılı' in window.global_status.toolTip()
    assert window.global_status.property('role')=='error'
    window.set_status('')
    assert window.global_status.text()=='Hazır' and window.global_status.property('role')=='muted'


def test_reselecting_current_theme_preserves_existing_views_without_rebuilding(window,monkeypatch):
    calls=[]
    monkeypatch.setattr(window.pages['weight'],'theme_changed',lambda:calls.append('changed'))
    window.set_theme(window.appearance)
    assert not calls
    window.set_theme('light' if window.appearance=='dark' else 'dark')
    assert calls==['changed']


@pytest.mark.parametrize('theme',['dark','light'])
def test_docked_narrow_and_floating_properties_preserve_the_viewport(window,qtbot,theme):
    window.set_theme(theme);p=example(window);qtbot.wait(30)
    assert window.property_dock.isVisible() and p.canvas.width()>=400
    for width,height in ((1024,700),(820,560)):
        window.resize(width,height);qtbot.wait(50)
        assert window.size().toTuple()==(width,height) and not window.property_dock.isVisible()
        assert p.canvas.width()>=190 and p.canvas.height()>=60
    window.inspector_button.click();qtbot.wait(30)
    assert window.property_dock.isFloating() and window.property_dock.isVisible()
    assert p.canvas.width()>=190
    window.property_dock.close();assert not window.inspector_requested
    window.resize(1440,900);window.navigate('pdf');assert not window.property_dock.isVisible()


def test_inspector_and_source_cannot_edit_during_a_worker_job(window,qtbot):
    p=example(window);started=threading.Event()
    def work(events,stop):started.set();stop.wait(2)
    window.jobs.start(p,work);qtbot.waitUntil(started.is_set)
    assert not p.inspector.isEnabled() and not p.form.isEnabled()
    window.navigate('weight');assert window.mode=='weight'
    window.jobs.cancel();qtbot.waitUntil(lambda:not window.jobs.busy,timeout=6000)
    window.navigate('nesting');assert p.inspector.isEnabled() and p.form.isEnabled()


def test_light_dark_and_minimum_navigation_keep_labels_and_focus(window,qtbot):
    for theme in ('dark','light'):
        window.set_theme(theme)
        for mode,_,_ in MODULES:
            window.navigate(mode);assert window.pages[mode].isVisible()
        window.set_sidebar_collapsed(True);window.focus_module_search();qtbot.wait(20)
        assert not window.sidebar_collapsed and window.browser.search.hasFocus()
    assert window.pages['pdf'].form.fields['source'].entry.accessibleName()!=''
