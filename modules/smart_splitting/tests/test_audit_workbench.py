"""Read/reload, cancellation, input and transfer failures through real Qt jobs."""
from copy import deepcopy
from threading import Event
import math

import pytest
from PySide6.QtCore import Qt, QPointF, QPoint
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog
from shapely.geometry import box

from modules.nesting.models import Part
from modules.smart_splitting.adapter import transfer_to_nesting
from modules.smart_splitting.models import SplitSettings
from modules.smart_splitting.splitter import split
from .test_workbench import window, finish  # noqa: F401
from .test_geometry import circle_dxf


def test_changed_curve_tolerance_requires_real_reload_before_split(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'CURVE.dxf',radius=100)
    page.load_file(path); finish(window,qtbot)
    old_points=len(page.source.polygon.exterior.coords)
    assert page.source.curve_tolerance==.05
    page.form.set_value('tolerance','.001')
    assert page.import_stale and not page.split_button.isEnabled() and not page.optimize_button.isEnabled()
    page.run_split(); assert not window.jobs.busy and page.solution is None
    page.reload_source(); finish(window,qtbot)
    assert not page.import_stale and page.split_button.isEnabled()
    assert page.source.curve_tolerance==.001 and len(page.source.polygon.exterior.coords)>old_points
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot)
    assert page.solution.source.curve_tolerance==.001


def test_failed_reload_preserves_original_snapshot_and_cannot_use_changed_import_options(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'A.dxf',radius=100)
    page.load_file(path); finish(window,qtbot); source=page.source
    path.write_text('broken'); page.form.set_value('tolerance','.01')
    page.reload_source(); finish(window,qtbot)
    assert page.source is source and page.import_stale and page.solution is None
    assert not page.split_button.isEnabled() and page.status.property('role')=='error'
    page.clear(); assert not page.import_stale and page.import_path is None
    assert page.form.fields['unit'].isEnabled() and page.form.fields['tolerance'].isEnabled()


def test_change_missing_unit_from_mm_to_inch_changes_real_imported_dimensions(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'UNITLESS.dxf',radius=10,units=0)
    page.form.set_value('unit','mm'); page.load_file(path); finish(window,qtbot)
    assert page.source.polygon.bounds[2]-page.source.polygon.bounds[0]==pytest.approx(20,abs=.1)
    page.form.set_value('unit','inch'); assert page.import_stale
    page.reload_source(); finish(window,qtbot)
    assert page.source.polygon.bounds[2]-page.source.polygon.bounds[0]==pytest.approx(508,abs=.1)
    # Flattening keeps an absolute mm tolerance: differently sized circles have
    # different sample counts, so their approximated areas are not exact ratios.
    assert page.source.area==pytest.approx(math.pi*254**2,abs=2*math.pi*254*.05)


def test_nesting_snapshot_cannot_be_misrepresented_by_dxf_import_controls(window,qtbot):
    page=window.pages['smart_splitting']; nesting=window.pages['nesting']
    part=Part.create('EXISTING',box(0,0,200,200)); nesting.project.parts=[part]; nesting.refresh(); nesting.select_canvas_part(part.id)
    page.from_nesting()
    assert page.source is not None and page.import_path is None
    assert not page.reload_button.isEnabled()
    assert not page.form.fields['tolerance'].isEnabled() and not page.form.fields['unit'].isEnabled()


def test_transfer_rejects_over_limit_transaction_without_losing_prior_parts(window):
    page=window.pages['nesting']; source=Part.create('SOURCE',box(0,0,200,200))
    solution=split(source,SplitSettings(count=4,quantity=2))
    page.project.parts=[Part.create('KEEP',box(0,0,10,10),quantity=9999)]; page.refresh()
    before=page.project.fingerprint(); imports=deepcopy(page.imports)
    with pytest.raises(ValueError,match='10000'): transfer_to_nesting(page,solution)
    assert page.project.fingerprint()==before and page.imports==imports


def test_different_parts_in_one_source_file_do_not_replace_each_other(window):
    page=window.pages['nesting']
    a=Part.create('A',box(0,0,200,200),source_sha256='a'*64)
    b=Part.create('B',box(0,0,150,100),source_sha256='a'*64)
    first=split(a,SplitSettings(count=4)); second=split(b,SplitSettings(count=2))
    transfer_to_nesting(page,first); transfer_to_nesting(page,second)
    assert len(page.project.parts)==6
    transfer_to_nesting(page,split(a,SplitSettings(count=6)))
    assert len(page.project.parts)==8
    assert {s.id for s in second.segments}<=set(p.id for p in page.project.parts)


def test_reload_at_another_tolerance_and_changed_file_replaces_its_previous_transfer(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'A.dxf',radius=100)
    page.load_file(path); finish(window,qtbot); page.form.set_value('count',4)
    page.run_split(); finish(window,qtbot); page.transfer()
    nesting=window.pages['nesting']; assert len(nesting.project.parts)==4
    page.form.set_value('tolerance','.01'); page.reload_source(); finish(window,qtbot)
    page.run_split(); finish(window,qtbot); page.transfer()
    assert len(nesting.project.parts)==4
    circle_dxf(path,radius=120); page.reload_source(); finish(window,qtbot)
    page.run_split(); finish(window,qtbot); page.transfer()
    assert len(nesting.project.parts)==4


def test_independent_unsourced_parts_with_identical_names_and_geometry_are_preserved(window):
    page=window.pages['nesting']
    first=Part.create('SAME',box(0,0,100,100)); second=Part.create('SAME',box(0,0,100,100))
    a=split(first,SplitSettings(count=2)); b=split(second,SplitSettings(count=2))
    transfer_to_nesting(page,a); transfer_to_nesting(page,b)
    assert len(page.project.parts)==4 and set(p.id for p in page.project.parts)=={s.id for s in a.segments+b.segments}


def test_reload_keeps_the_selected_component_in_a_multi_part_dxf(window,qtbot,tmp_path):
    import ezdxf
    page=window.pages['smart_splitting']; path=tmp_path/'MULTI.dxf'; doc=ezdxf.new(); doc.units=4
    doc.modelspace().add_circle((0,0),100); doc.modelspace().add_circle((300,0),50); doc.saveas(path)
    page.load_file(path); finish(window,qtbot); page.source_picker.setCurrentIndex(1)
    selected=page.source.code
    page.form.set_value('tolerance','.01'); page.reload_source(); finish(window,qtbot)
    assert page.source.code==selected and page.source_picker.currentIndex()==1


def test_cancellation_while_geometry_job_is_waiting_does_not_mutate_sources_or_nesting(window,qtbot,tmp_path,monkeypatch):
    import modules.smart_splitting.splitter as splitter
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    source=page.source; before=window.pages['nesting'].project.fingerprint(); started=Event()
    def controlled(part,settings,*,stop,**kwargs):
        started.set()
        assert stop.wait(10), 'test cancellation was not delivered'
        raise InterruptedError('İşlem durduruldu.')
    monkeypatch.setattr(splitter,'split',controlled)
    page.run_split(); qtbot.waitUntil(started.is_set)
    assert page.stop_button.isEnabled() and not page.transfer_button.isEnabled()
    window.navigate('nesting'); window.jobs.cancel(); finish(window,qtbot)
    assert page.source is source and page.solution is None
    assert window.pages['nesting'].project.fingerprint()==before
    assert not window.jobs.busy


def test_all_numeric_inputs_fail_cleanly_for_nonfinite_values(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    keys=('count','quantity','start_angle','sheet_width','sheet_height','thickness','margin','gap','kerf',
          'min_width','min_web','hole_clearance','weld_gap','allowance')
    for key in keys:
        saved=page.form.value(key)
        for value in ('nan','inf','-inf','abc'):
            page.form.set_value(key,value); page.run_split()
            assert not window.jobs.busy and page.solution is None,key
            assert page.status.property('role')=='error',key
        page.form.set_value(key,saved)


def test_file_dialog_cancel_and_real_selected_path_export(window,qtbot,tmp_path,monkeypatch):
    page=window.pages['smart_splitting']
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:('',''))
    page.import_dialog(); assert page.source is None and not window.jobs.busy
    path=circle_dxf(tmp_path/'ÖLÇÜ_ÇEMBER.dxf',radius=100)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),'DXF'))
    page.import_dialog(); finish(window,qtbot)
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot)
    assert page.solution is not None
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:('',''))
    page.export_dialog(); assert not window.jobs.busy
    target=tmp_path/'ÇIKTI'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    page.export_dialog(); finish(window,qtbot)
    assert len(list(target.glob('*_SEG_*.dxf')))==4


def test_custom_center_forbidden_region_and_rotation_fields(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    page.form.set_value('center_mode','Özel merkez'); page.form.set_value('center_x','-12,5'); page.form.set_value('center_y','20,5')
    page.form.set_value('rotation',False); page.form.set_value('angles','90;270')
    page.form.set_value('forbidden','30,30,10,20;50,60,10,10')
    settings=page.settings_value()
    assert settings.center==(-12.5,20.5) and len(settings.forbidden)==2 and not settings.rotation
    for value in ('a','1,2,3','1,2,-3,4','nan,2,3,4'):
        page.form.set_value('forbidden',value)
        with pytest.raises(ValueError): page.settings_value()
    page.form.set_value('forbidden',''); page.form.set_value('center_x','nan')
    with pytest.raises(ValueError): page.settings_value()


def test_zoom_original_view_and_reset_do_not_change_geometry(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot)
    solution=page.solution; canvas=page.canvas; before=canvas.transform().m11()
    point=canvas.viewport().rect().center()
    event=QWheelEvent(QPointF(point),QPointF(canvas.viewport().mapToGlobal(point)),QPoint(),QPoint(0,120),
        Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
    QApplication.sendEvent(canvas.viewport(),event)
    assert canvas.transform().m11()>before and not canvas.auto_fit
    canvas.fit(); assert canvas.auto_fit
    page.original.setChecked(True); assert page.solution is solution
    page.original.setChecked(False); assert page.solution is solution
    page.clear(); assert page.solution is None and not canvas.scene().items()


def test_import_limit_and_transfer_error_are_actionable(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'A.dxf',radius=100)
    page.form.set_value('tolerance','2'); page.load_file(path)
    assert not window.jobs.busy and page.source is None and '1 mm' in page.status_text
    page.from_nesting(); assert 'tek parça seçin' in page.status_text
    page.form.set_value('tolerance','.05'); page.load_file(path); finish(window,qtbot)
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot)
    nesting=window.pages['nesting']; nesting.project.parts=[Part.create('KEEP',box(0,0,10,10),quantity=9999)]
    page.transfer(); assert window.mode=='smart_splitting' and '10000' in page.status_text


def test_custom_nesting_material_is_never_silently_replaced_by_a_stock_default(window):
    from modules.nesting.models import Material
    nesting=window.pages['nesting']; page=window.pages['smart_splitting']
    nesting.project.materials.append(Material('CUSTOM_AL','Özel alüminyum',2800))
    source=Part.create('CUSTOM',box(0,0,100,100),material='CUSTOM_AL')
    nesting.project.parts=[source]; nesting.refresh(); nesting.select_canvas_part(source.id)
    page.from_nesting()
    assert page.form.value('material')=='CUSTOM_AL'
    page.run_split(); assert not window.jobs.busy and page.solution is None
    assert 'katalog malzemesini' in page.status_text
    page.form.set_value('material','EN AW-5754')
    assert page.settings_value().material=='EN AW-5754'

