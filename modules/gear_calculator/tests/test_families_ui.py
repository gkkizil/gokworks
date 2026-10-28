import gc
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QColor
from gui_qt.app import MainWindow,create_application
from gui_qt.theme import COLORS
from modules.gear_calculator.families.models import CATALOG
from modules.gear_calculator.ui import number
from modules.gear_calculator.workspace import GearWorkspace


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


def test_every_type_shares_three_columns_and_restores_them_after_compact_mode(page,qtbot):
    p,w=page
    assert isinstance(p.body,GearWorkspace)
    for kind,cap in CATALOG.items():
        f=select(p,kind);w.resize(1600,950);qtbot.wait(20)
        assert isinstance(f.body,GearWorkspace) and not f.compact_mode
        panels=(f.input_scroll,f.viewer_panel,f.results_scroll)
        assert tuple(f.splitter.widget(i) for i in range(3))==panels
        assert all(panel.isVisible() and panel.width()>=200 for panel in panels)
        assert f.views.count()==2 and f.table.isVisible() and f.step_button.isVisible()
        assert f.table.item(0,1).text()==f.selection.currentText().split(' · ')[0]
        assert f.plot_stack.currentIndex()==(0 if cap.geometry else 1)
        assert f.views.isTabEnabled(1)==cap.geometry
        assert f.construction.isEnabled()==(kind in ('helical','herringbone','internal','planetary','chain_sprocket'))
        w.resize(820,560);qtbot.wait(20)
        assert f.compact_mode and f.compact_tabs.count()==3
        for i,panel in enumerate(panels):
            f.compact_tabs.setCurrentIndex(i)
            assert panel.isVisible()
        f.results_scroll.ensureWidgetVisible(f.step_button)
        button_position=f.step_button.mapTo(f.results_scroll.viewport(),f.step_button.rect().center())
        assert f.results_scroll.viewport().rect().contains(button_position)
        w.resize(1600,950);qtbot.wait(20)
        assert not f.compact_mode and all(panel.isVisible() for panel in panels)
        assert f.dxf_button.isEnabled()==cap.geometry


def test_family_helper_circles_selection_targets_and_theme_changes(page,qtbot):
    p,w=page;f=select(p,'planetary');qtbot.wait(20)
    for theme in ('light','dark'):
        w.set_theme(theme);qtbot.wait(20)
        assert f.canvas.backgroundBrush().color()==QColor(COLORS[theme]['canvas'])
        f.pitch.setChecked(False);f.base.setChecked(True)
        assert all(item.isVisible()==(key=='base') for item,key in f.canvas.helpers)
        f.selection.setCurrentIndex(f.selection.findData(2))
        assert f.canvas.selected==2 and f.target.currentData()=='wheel'
        assert f.table.item(0,1).text()=='Halka'
        f.canvas.partSelected.emit(1)
        assert f.selection.currentData()==1 and f.target.currentData()=='pair'
    f=select(p,'cycloidal')
    assert f.pitch.text()=='Pim dairesi' and not f.base.isEnabled()
    f.selection.setCurrentIndex(1)
    assert f.target.currentData()=='wheel' and f.canvas.selected==1
    assert all(item.pen().widthF()==pytest.approx(1.7) for item in f.canvas.pin_items)
    f=select(p,'hypoid')
    assert not f.play_button.isEnabled() and not f.preview_button.isEnabled()
    assert f.empty.isVisible() and 'henüz yok' in f.empty.text()


def test_primary_load_and_type_specific_labels_remain_parametric(page):
    p,w=page;f=select(p,'helical')
    assert 'Normal modül' in f.form.labelForField(f.fields['module_mm']).text()
    f.load_mode.setCurrentIndex(1);f.fields['torque_nm'].setValue(12);f.calculate()
    assert f.result.value('T₁')==pytest.approx(12)
    assert f.derived_load.text()==f'Hesaplanan P = {number(f.result.value("P"))} kW'
    assert not f.fields['power_kw'].isVisible() and f.fields['torque_nm'].isVisible()
    f=select(p,'worm')
    assert 'Eksenel modül' in f.form.labelForField(f.fields['module_mm']).text()
    f=select(p,'planetary')
    assert 'Güneş' in f.form.labelForField(f.fields['teeth1']).text()
    assert 'Planet' in f.form.labelForField(f.fields['teeth2']).text()
    f=select(p,'helical')
    assert f.load_mode.currentData()=='torque' and f.result.value('T₁')==pytest.approx(12)


def test_real_dxf_uses_selected_part_current_parameters_and_helper_checkbox(page,qtbot,tmp_path):
    import ezdxf
    p,w=page;f=select(p,'helical')
    f.fields['module_mm'].setValue(3);f.selection.setCurrentIndex(1);f.selection.setCurrentIndex(0);f.construction.setChecked(False)
    first=tmp_path/'pinion-only.dxf';assert f.run('dxf',first)
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    doc=ezdxf.readfile(first)
    assert not [e for e in doc.modelspace() if e.dxf.layer in ('PITCH_CIRCLE','BASE_CIRCLE')]
    outline=list(doc.modelspace().query('LWPOLYLINE[layer=="GEAR_PROFILE"]'))
    assert len(outline)==1 and outline[0].closed
    assert f.spec.module_mm==3
    f.construction.setChecked(True);second=tmp_path/'pinion-helpers.dxf';assert f.run('dxf',second)
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=30000)
    doc=ezdxf.readfile(second)
    circles=list(doc.modelspace().query('CIRCLE[layer=="PITCH_CIRCLE"]'))
    from math import cos,radians
    assert len(circles)==1 and circles[0].dxf.radius==pytest.approx(30/cos(radians(20)))
    assert doc.header['$INSUNITS']==4
