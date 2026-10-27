import gc
from pathlib import Path
from math import radians

import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from gui_qt.app import MainWindow,create_application


@pytest.fixture
def page(qtbot,tmp_path):
    create_application([]);window=MainWindow(tmp_path/'settings.json');qtbot.addWidget(window)
    window.resize(1600,950);window.show();window.navigate('gear_calculator');qtbot.wait(20)
    p=window.pages['gear_calculator']
    yield p,window
    p.canvas.pause();p.update_timer.stop()
    if window.jobs.busy:
        window.jobs.cancel();qtbot.waitUntil(lambda:not window.jobs.busy,timeout=15000)
    if p.mesh_view:
        p.mesh_view.timer.stop();p.mesh_view.cancel_render()
        qtbot.waitUntil(lambda:p.mesh_view.running is None,timeout=10000)
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_menu_load_mode_selection_helpers_and_invalid_inputs_clear_stale_results(page,qtbot):
    p,w=page
    assert w.browser.group_for_mode['gear_calculator']=='Makine Elemanları'
    assert p.result.ratio==pytest.approx(2)
    assert p.fields['power_kw'].isEnabled() and not p.fields['torque_nm'].isEnabled()
    p.load_mode.setCurrentIndex(1);p.fields['torque_nm'].setValue(12);p.calculate()
    assert p.result.input_torque_nm==pytest.approx(12) and p.fields['torque_nm'].isEnabled()
    p.selection.setCurrentIndex(1);assert p.selected==1 and p.export_target.currentData()=='wheel'
    p.base.setChecked(True);assert all(i.isVisible() for i in p.canvas.helpers)
    p.fields['bore1'].setValue(100)
    assert not p.step_button.isEnabled()  # disabled immediately, before debounce
    qtbot.waitUntil(lambda:p.specification is None,timeout=2000)
    assert not p.canvas.gears and p.result_table.rowCount()==0
    assert 'Delik' in p.warning_label.text()


def test_under_cut_warns_without_enabling_unverified_manufacturing_or_motion(page):
    p,w=page;p.fields['z1'].setValue(12);p.fields['bore1'].setValue(0);p.calculate()
    assert p.result is not None and 'alttan kesilme' in p.warning_label.text()
    assert not p.step_button.isEnabled() and not p.dxf_button.isEnabled() and not p.play_button.isEnabled()


@pytest.mark.parametrize('size',[(820,560),(1366,768),(1920,1080)])
def test_small_wide_layouts_and_both_themes_keep_input_view_and_exports_accessible(page,qtbot,size):
    p,w=page;w.resize(*size);qtbot.wait(30)
    for theme in ('light','dark'):
        w.set_theme(theme);qtbot.wait(20)
        assert p.canvas.appearance==theme
        if p.compact_mode:
            assert p.compact_tabs.count()==3
            p.compact_tabs.setCurrentIndex(0);assert p.fields['module_mm'].isVisible()
            p.compact_tabs.setCurrentIndex(1);assert p.canvas.isVisible()
            p.compact_tabs.setCurrentIndex(2);p.results_scroll.ensureWidgetVisible(p.step_button)
        assert p.step_button.isVisible() and p.dxf_button.isEnabled()
        viewport=p.results_scroll.viewport()
        assert viewport.rect().intersects(p.step_button.geometry().translated(p.step_button.parentWidget().mapTo(viewport,p.step_button.parentWidget().rect().topLeft())))


def test_real_async_validation_motion_and_stop_reset(page,qtbot):
    p,w=page;p.views.setCurrentIndex(1);p.toggle_animation()
    qtbot.waitUntil(lambda:p.canvas.timer.isActive() and not w.jobs.busy,timeout=10000)
    assert p.views.currentIndex()==0
    qtbot.waitUntil(lambda:p.canvas.input_angle!=0,timeout=1000)
    a=p.canvas.input_angle
    assert p.canvas.gears[0].rotation()==pytest.approx(a*180/3.141592653589793)
    p.toggle_animation();assert not p.canvas.timer.isActive()
    p.reset_button.click();assert p.canvas.input_angle==0
    assert p.canvas.gears[1].rotation()==pytest.approx(180-180/40)


def test_compact_to_wide_roundtrip_restores_all_three_panels(page,qtbot):
    p,w=page
    original=(p.input_scroll,p.viewer_panel,p.results_scroll)
    for size in ((820,560),(1600,950),(820,560),(1920,1080)):
        w.resize(*size);qtbot.wait(40)
        if p.compact_mode:
            p.compact_tabs.setCurrentIndex(2)
            assert p.results_scroll.isVisible()
        else:
            assert all(panel.isVisible() and panel.width()>0 for panel in original)
            assert p.canvas.isVisible() and p.step_button.isVisible()


def test_real_worker_export_uses_latest_fields_and_3d_is_from_the_same_brep(page,qtbot,tmp_path):
    p,w=page;p.fields['module_mm'].setValue(3)
    assert p.start_export('step',tmp_path/'takım.step','pair')
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=20000)
    assert p.last_export['solids']==2 and (tmp_path/'takım.step').is_file()
    assert p.specification.pinion.module_mm==pytest.approx(3)
    assert p.last_export['bounds_mm'][0]==pytest.approx(-33,abs=1e-5)
    p.build_preview();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=20000)
    assert p.mesh_view is not None and p.mesh_view.mesh.triangles>0
    assert p._mesh_key==p.specification
    p.fields['bore1'].setValue(999);p.calculate()
    assert p.mesh_view.mesh is None and not p.step_button.isEnabled()
