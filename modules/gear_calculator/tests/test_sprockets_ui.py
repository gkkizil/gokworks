import gc,json
from dataclasses import replace
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QFileDialog,QMessageBox
from gui_qt.app import create_application,MainWindow
from modules.gear_calculator.sprockets import CHAINS
from modules.gear_calculator.serialization import to_dict,from_dict


@pytest.fixture
def page(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1600,950);w.show();w.navigate('gear_calculator');p=w.pages['gear_calculator']
    p.type_picker.setCurrentIndex(p.type_picker.findData('chain_sprocket'));f=p.family_panel
    yield p,f,w
    p.canvas.pause();p.update_timer.stop()
    for panel in p.family_panels.values():
        panel.canvas.pause();panel.timer.stop()
        if panel.mesh_view:
            panel.mesh_view.timer.stop();panel.mesh_view.cancel_render();qtbot.waitUntil(lambda:panel.mesh_view.running is None,timeout=15000)
    if w.jobs.busy:w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=15000)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_catalogue_inputs_mounting_modes_selection_and_type_state_are_preserved(page):
    p,f,w=page
    assert f.result is not None and 'module_mm' not in f.fields and 'pressure_angle_deg' not in f.fields
    for series,c in CHAINS.items():
        f.series.setCurrentIndex(f.series.findData(series));f.calculate()
        assert f.result is not None and f.spec.driver.chain==c
        assert all(f.fields[k].isReadOnly() for k in ('pitch_mm','roller_diameter_mm','inner_width_mm'))
    f.fields['teeth1'].setValue(24);f.calculate();f.selection.setCurrentIndex(1)
    assert f.target.currentData()=='wheel' and f.canvas.selected==1
    f.mounting.setCurrentIndex(1);f.fields['link_count'].setValue(100);f.calculate()
    assert f.spec.link_count==100 and f.spec.center_distance_mm is None
    p.type_picker.setCurrentIndex(p.type_picker.findData('helical'));p.family_panel.fields['module_mm'].setValue(3);p.family_panel.calculate()
    p.type_picker.setCurrentIndex(p.type_picker.findData('chain_sprocket'))
    assert p.family_panel is f and f.fields['teeth1'].value()==24 and f.series.currentData()=='16B-1'
    p.type_picker.setCurrentIndex(0);assert p.result.ratio==pytest.approx(2)


def test_both_themes_and_compact_wide_roundtrip_keep_exports_accessible(page,qtbot):
    p,f,w=page
    for theme in ('light','dark'):
        w.set_theme(theme)
        for size in ((820,560),(1920,1080)):
            w.resize(*size);qtbot.wait(30)
            if f.compact_mode:
                assert f.compact_tabs.count()==3
                for i,panel in enumerate((f.input_scroll,f.viewer_panel,f.results_scroll)):
                    f.compact_tabs.setCurrentIndex(i);assert panel.isVisible()
                f.results_scroll.ensureWidgetVisible(f.step_button)
            else:assert all(x.isVisible() for x in (f.input_scroll,f.viewer_panel,f.results_scroll))
            assert f.step_button.isVisible() and f.step_button.isEnabled()
    f.fields['bore1_mm'].setValue(1000)
    assert not f.step_button.isEnabled()
    qtbot.waitUntil(lambda:f.result is None and f.spec is None,timeout=3000)
    assert not f.canvas.items and f.table.rowCount()==0


def test_real_chain_worker_animation_ratio_static_marks_reset_and_3d(page,qtbot,tmp_path):
    p,f,w=page;f.toggle();qtbot.waitUntil(lambda:f.canvas.timer.isActive() and not w.jobs.busy,timeout=20000)
    qtbot.waitUntil(lambda:f.canvas.angle>0,timeout=2000)
    a,b=f.canvas.items
    assert a.rotation()>0 and b.rotation()==pytest.approx(a.rotation()/2)
    assert not any(item.isVisible() for item,key in f.canvas.helpers if key=='base')
    f.toggle();assert not f.canvas.timer.isActive()
    f.reset_button.click();assert f.canvas.angle==0
    assert all(item.isVisible() for item,key in f.canvas.helpers if key=='base')
    f.target.setCurrentIndex(2);assert f.run('mesh')
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    assert f.mesh_view is not None and f.mesh_view.mesh.triangles>0 and f.views.currentIndex()==1
    if f.mesh_view.hardware is None:
        qtbot.waitUntil(lambda:not f.mesh_view.software.image.isNull(),timeout=20000)
    destination=tmp_path/'pair.step';assert p.start_export('step',destination,'pair')
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    assert f.last_export['solids']==2 and not f.last_export['chain_included']
    original=destination.read_bytes();assert not f.run('step',destination)
    assert destination.read_bytes()==original


def test_json_restore_save_and_explicit_overwrite_confirmation(page,monkeypatch,tmp_path):
    p,f,w=page;s=replace(f.spec,driver=replace(f.spec.driver,material='C45',hub_diameter_mm=30,hub_length_mm=20))
    f.restore(s);assert from_dict(to_dict(f.spec))==s
    path=tmp_path/'chain.json';path.write_text('existing user data')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),'JSON'))
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.No)
    f.save_json();assert path.read_text()=='existing user data'
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
    f.save_json();assert from_dict(json.loads(path.read_text()))==s
    f.fields['teeth1'].setValue(25);f.calculate()
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),'JSON'))
    f.open_json();assert f.spec==s and f.fields['teeth1'].value()==20
