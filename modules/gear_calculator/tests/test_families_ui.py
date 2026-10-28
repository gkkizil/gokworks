import gc
from dataclasses import replace
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from gui_qt.app import MainWindow,create_application
from modules.gear_calculator.families.models import CATALOG


@pytest.fixture
def page(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1400,900);w.show();w.navigate('gear_calculator');p=w.pages['gear_calculator']
    yield p,w
    p.canvas.pause();p.update_timer.stop()
    if p.family_panel:
        f=p.family_panel;f.canvas.pause();f.timer.stop()
        if f.mesh_view:
            f.mesh_view.timer.stop();f.mesh_view.cancel_render()
            qtbot.waitUntil(lambda:f.mesh_view.running is None,timeout=10000)
    if w.jobs.busy:w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=15000)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def select(p,kind):
    p.type_picker.setCurrentIndex(p.type_picker.findData(kind));return p.family_panel


def test_all_types_open_without_misrepresenting_unverified_cad_and_spur_is_preserved(page):
    p,w=page;original=p.fields['module_mm'].value()
    for kind,cap in CATALOG.items():
        f=select(p,kind)
        assert f.result is not None,(kind,f.warnings.text())
        assert f.step_button.isEnabled()==cap.geometry
        assert f.dxf_button.isEnabled()==cap.geometry
        assert f.canvas.items or not cap.geometry
    p.type_picker.setCurrentIndex(0)
    assert p.result.ratio==2 and p.fields['module_mm'].value()==original
    assert p.family_stack.currentWidget() is p.body


def test_parametric_edits_clear_old_geometry_and_each_type_retains_own_inputs(page,qtbot):
    p,w=page;f=select(p,'rack');f.fields['module_mm'].setValue(3);f.calculate()
    assert f.result.value('d₁')==60
    f=select(p,'helical');assert f.fields['module_mm'].value()==2
    f=select(p,'rack');assert f.fields['module_mm'].value()==3
    f.fields['bore1_mm'].setValue(1000)
    assert not f.step_button.isEnabled()
    qtbot.waitUntil(lambda:f.spec is None,timeout=3000)
    assert not f.canvas.items and f.table.rowCount()==0


def test_real_worker_animation_and_export_are_available_from_family_screen(page,qtbot,tmp_path):
    p,w=page;f=select(p,'rack')
    assert p.start_export('step',tmp_path/'rack.step','pair')
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    assert f.last_export['solids']==2
    assert f.run('mesh')
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    assert f.mesh_view is not None and f.mesh_view.mesh.triangles>0
    f.toggle();qtbot.waitUntil(lambda:f.canvas.timer.isActive() and not w.jobs.busy,timeout=20000)
    qtbot.waitUntil(lambda:f.canvas.angle!=0,timeout=2000)
    f.toggle();assert not f.canvas.timer.isActive()
    p.type_picker.setCurrentIndex(0);assert not f.canvas.timer.isActive()
