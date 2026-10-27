from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem,QMessageBox
from gui_qt.app import create_application,MainWindow
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from gui_qt.theme import COLORS
from modules.shaft_generator.ui import ShaftPage
from modules.shaft_generator.models import Groove


@pytest.fixture
def page(qtbot,tmp_path):
    create_application([])
    context=SimpleNamespace(settings=SettingsStore(tmp_path/'settings.json'),jobs=JobManager(),appearance='dark')
    page=ShaftPage(context);qtbot.addWidget(page);page.resize(1100,780);page.show();qtbot.wait(10)
    yield page
    if page.jobs.busy:page.jobs.cancel();qtbot.waitUntil(lambda:not page.jobs.busy,timeout=8000)
    page.settings.flush()


def test_direct_table_edit_updates_both_true_scale_views_and_native_plan(page,qtbot):
    before=page.top_view.stage_regions[0][1].width()
    page.table.item(0,2).setText('80,5');qtbot.wait(10)
    assert page.project.total_length==230.5
    assert page.plan[1]['start_m']==pytest.approx(.0805)
    assert page.top_view.stage_regions[0][1].width()>before
    assert page.section_view.stage_regions[0][1].width()==page.top_view.stage_regions[0][1].width()
    page.table.item(2,1).setText('NaN');qtbot.wait(10)
    assert not page.create_button.isEnabled() and not page.plan
    assert not page.top_view.stage_regions and '3. kademe' in page.validation_label.text()
    page.table.item(2,1).setText('35');assert page.create_button.isEnabled()


@pytest.mark.parametrize('view_name',['top_view','section_view'])
def test_preview_click_selects_table_and_both_views(page,qtbot,view_name):
    view=getattr(page,view_name);sid,rect=view.stage_regions[2]
    qtbot.mouseClick(view,Qt.LeftButton,pos=rect.center().toPoint())
    assert page.table.currentRow()==2 and page.selected_stage==sid
    assert page.top_view.selected_stage==page.section_view.selected_stage==sid
    page.table.selectRow(1)
    assert page.top_view.selected_stage==page.project.stages[1].id
    assert page.section_view.selected_stage==page.project.stages[1].id


def test_stage_commands_reorder_copy_and_delete_in_place(page):
    sid=page.selected_stage;page.add_stage(copy=True)
    new=page.selected_stage;assert new!=sid and len(page.project.stages)==5
    page.move_stage(-1);assert page.project.stages[0].id==new
    page.delete_stage();assert len(page.project.stages)==4
    assert page.project.total_length==190


def test_operation_form_edits_update_preview_and_selection_immediately(page,qtbot):
    page.add_operation('groove');op=page.project.operations[0]
    page.operation_fields['groove']['width'].setValue(3.5);qtbot.wait(10)
    assert op.width==3.5 and page.section_view.selected_operation==op.id
    rect=page.section_view.operation_regions[0][2]
    qtbot.mouseClick(page.section_view,Qt.LeftButton,pos=rect.center().toPoint())
    assert page.selected_operation==op.id and page.operations.currentRow()==0
    page.select_stage(page.project.stages[1].id)
    assert page.selected_operation==''
    page.select_operation(op.id);page.delete_operation();assert not page.project.operations


@pytest.mark.parametrize('kind',['chamfer','fillet'])
def test_adding_opposite_end_treatments_keeps_first_edge_and_labels_both(page,kind):
    from modules.shaft_generator.validation import validate
    edge=page.operation_fields[kind]['edge']
    edge.setCurrentIndex(edge.findData('left'))
    page.add_operation(kind)
    first=page.project.operations[0]
    assert first.edge=='left' and not page.selected_operation
    edge.setCurrentIndex(edge.findData('right'))
    assert first.edge=='left'  # Preparing a second feature must not move the first.
    page.add_operation(kind)
    assert [(op.stage_id,op.edge) for op in page.project.operations]==[
        (first.stage_id,'left'),(first.stage_id,'right')]
    assert not validate(page.project) and page.create_button.isEnabled()
    assert 'Sol' in page.operations.item(0).text() and 'Sağ' in page.operations.item(1).text()
    assert len([row for row in page.plan if row['kind']==kind])==2
    # Explicit list selection continues to edit the existing operation live.
    page.select_operation(first.id)
    control=page.operation_fields[kind]['distance' if kind=='chamfer' else 'radius']
    control.setValue(1.25)
    assert getattr(first,'distance' if kind=='chamfer' else 'radius')==1.25
    assert len(page.project.operations)==2 and page.project.operations[1].edge=='right'


def test_add_same_end_treatment_does_not_create_an_invalid_duplicate(page):
    page.add_operation('chamfer');before=page.project.to_dict()
    page.add_operation('chamfer')
    assert page.project.to_dict()==before and len(page.project.operations)==1
    assert 'zaten pah/radyüs var' in page.status_text and page.create_button.isEnabled()


def test_reported_groove_keyway_and_four_chamfers_keep_create_enabled(page):
    a,b=page.project.stages[:2]
    page.add_operation('groove')
    for edge in ('left','right'):
        control=page.operation_fields['chamfer']['edge']
        control.setCurrentIndex(control.findData(edge))
        page.add_operation('chamfer')
    page.select_stage(b.id)
    page.add_operation('keyway')
    for edge in ('right','left'):
        control=page.operation_fields['chamfer']['edge']
        control.setCurrentIndex(control.findData(edge))
        page.add_operation('chamfer')
    assert len(page.project.operations)==6
    assert [(op.kind,op.stage_id,getattr(op,'edge',None)) for op in page.project.operations]==[
        ('groove',a.id,None),('chamfer',a.id,'left'),('chamfer',a.id,'right'),
        ('keyway',b.id,None),('chamfer',b.id,'right'),('chamfer',b.id,'left')]
    assert page.create_button.isEnabled() and len(page.plan)==10
    assert page.validation_label.property('role')!='error'
    assert page.top_view.stage_regions and page.section_view.stage_regions


@pytest.mark.parametrize('kind',['chamfer','fillet'])
def test_opposite_end_draft_keeps_the_explicitly_chosen_target_stage(page,kind):
    chosen=page.project.stages[2].id
    target=page.operation_targets[kind]
    edge=page.operation_fields[kind]['edge']
    target.setCurrentIndex(target.findData(chosen))
    edge.setCurrentIndex(edge.findData('left'))
    page.add_operation(kind)
    assert page.selected_stage==chosen and target.currentData()==chosen
    edge.setCurrentIndex(edge.findData('right'))
    page.add_operation(kind)
    assert [(op.stage_id,op.edge) for op in page.project.operations]==[(chosen,'left'),(chosen,'right')]
    assert page.create_button.isEnabled()


def test_keyway_plan_has_round_ends_true_width_and_selects_operation(page,qtbot):
    from PySide6.QtGui import QColor
    page.add_operation('keyway');qtbot.wait(20)
    op=page.project.operations[0]
    top=page.top_view;section=page.section_view
    rect=top.operation_regions[0][2].adjusted(3,4,-3,-4)
    section_rect=section.operation_regions[0][2].adjusted(3,4,-3,-4)
    assert rect.width()/rect.height()==pytest.approx(op.length/op.width)
    assert section_rect.width()/section_rect.height()==pytest.approx(op.length/op.depth)
    image=top.grab().toImage()
    background=QColor(COLORS[top.appearance]['canvas'])
    assert image.pixelColor(rect.center().toPoint())==background
    # A rectangular pocket would also erase this corner; a semicircular end doesn't.
    radius=rect.height()/2
    corner=rect.topLeft();corner.setX(corner.x()+radius*.15);corner.setY(corner.y()+radius*.15)
    assert image.pixelColor(corner.toPoint())!=background
    page.select_stage(page.project.stages[2].id)
    qtbot.mouseClick(top,Qt.LeftButton,pos=rect.center().toPoint())
    assert page.selected_operation==op.id and page.selected_stage==op.stage_id
    page.operation_fields['keyway']['length'].setValue(op.width)
    assert not page.create_button.isEnabled() and 'toplam boyu' in page.validation_label.text()


def activate(combo,index):
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def test_groove_standard_fills_a_draft_then_edits_only_the_selected_operation(page):
    picker=page.standard_pickers['groove']
    assert picker.preset.count()==2 and picker.preset.currentIndex()==0
    activate(picker.preset,1)
    assert page.operation_fields['groove']['width'].value()==1.6
    assert page.operation_fields['groove']['depth'].value()==.7
    assert not page.project.operations and not page.dirty
    page.add_operation('groove');op=page.project.operations[0];op_id=op.id
    assert (op.width,op.depth)==(1.6,.7) and page.create_button.isEnabled()
    page.operation_fields['groove']['width'].setValue(2.3)
    assert picker.preset.currentIndex()==0 and op.width==2.3
    activate(picker.preset,1)
    assert op.id==op_id and (op.width,op.depth)==(1.6,.7) and len(page.project.operations)==1


def test_keyway_standard_selects_shaft_depth_and_fitting_catalogue_length(page):
    page.select_stage(page.project.stages[1].id)  # Ø45, L65, 5 mm offset.
    picker=page.standard_pickers['keyway']
    activate(picker.preset,1)
    values=page.operation_values('keyway')
    assert (values['width'],values['depth'],values['length'])==(14,5.5,36)
    assert max(picker.lengths)==60
    activate(picker.length,picker.length.findData(50))
    page.add_operation('keyway');op=page.project.operations[0]
    assert (op.width,op.depth,op.length)==(14,5.5,50)
    assert op.stage_id==page.project.stages[1].id and page.create_button.isEnabled()
    assert picker.preset.currentIndex()==1 and picker.length.currentData()==50


def test_diameter_changes_refresh_suggestions_without_recutting_existing_operations(page):
    picker=page.standard_pickers['groove'];activate(picker.preset,1)
    page.add_operation('groove');op=page.project.operations[0]
    page.table.item(0,1).setText('32')
    assert (op.width,op.depth)==(1.6,.7) and picker.preset.currentIndex()==0
    assert picker.size.diameter==32 and picker.size.depth==pytest.approx(.85)
    activate(picker.preset,1)
    assert (op.width,op.depth)==(1.6,.85)
    page.table.item(0,1).setText('30,2')
    assert picker.preset.count()==1 and picker.size is None
    assert (op.width,op.depth)==(1.6,.85) and 'ölçüsü yok' in picker.details.text()
    page.table.item(0,1).setText('NaN')
    assert picker.preset.count()==1 and not page.create_button.isEnabled()


def test_target_changes_and_short_stages_do_not_apply_a_stale_standard(page):
    picker=page.standard_pickers['keyway'];activate(picker.preset,1)
    before=page.operation_values('keyway')
    page.operation_targets['keyway'].setCurrentIndex(2)  # Ø35: width10/depth5, not Ø30: width8/depth4.
    assert picker.size.width==10 and picker.preset.currentIndex()==0
    assert page.operation_values('keyway')['width']==before['width']
    activate(picker.preset,1)
    assert page.operation_values('keyway')['depth']==5
    page.operation_fields['keyway']['offset'].setValue(49)
    assert not picker.lengths and not picker.length.isEnabled()
    assert 'sığan katalog boyu yok' in picker.details.text()


def test_standard_dimensions_survive_save_load_without_new_json_fields(page,tmp_path):
    from modules.shaft_generator import storage
    picker=page.standard_pickers['keyway'];activate(picker.preset,1)
    page.add_operation('keyway');op=page.project.operations[0]
    path=tmp_path/'standard.gokshaft.json';storage.save(page.project,path)
    page.project=storage.load(path)
    page.selected_stage=op.stage_id;page.selected_operation=op.id;page.populate();page.refresh()
    assert page.standard_pickers['keyway'].preset.currentIndex()==1
    assert (page.project.operations[0].width,page.project.operations[0].depth)==(8,4)


def test_existing_project_and_error_during_load_keep_current_data(page,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'mil.gokshaft.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    page.name.setText('TEST_MIL');page.save_dialog();assert path.is_file() and not page.dirty
    page.table.item(0,2).setText('55')
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    page.open_dialog();assert page.project.total_length==190 and page.name.text()=='TEST_MIL'
    original=page.project;path.write_text('{broken')
    page.open_dialog();assert page.project is original and page.status.property('role')=='error'


def test_background_job_uses_snapshot_keeps_gui_responsive_and_locks_mutation(page,qtbot,monkeypatch):
    started=threading.Event();release=threading.Event();captured=[]
    def create(project,events,stop,**kwargs):
        captured.append(project);started.set();release.wait(3)
        events.put(('shaft_created',dict(document='TEST',feature_count=4)))
    monkeypatch.setattr('modules.shaft_generator.ui.controller.create',create)
    page.create_model();qtbot.waitUntil(started.is_set)
    assert not page.source_scroll.isEnabled() and not page.create_button.isEnabled()
    assert captured[0] is not page.project
    page.resize(900,700);qtbot.wait(20);assert page.top_view.isVisible()
    release.set();qtbot.waitUntil(lambda:not page.jobs.busy,timeout=8000)
    assert page.create_button.isEnabled() and 'Rebuild' in page.status_text


@pytest.mark.parametrize('error_first',[False,True])
def test_startup_error_is_not_hidden_by_an_older_phase_in_the_same_batch(page,error_first):
    error=('job_error',dict(error='SOLIDWORKS şablonu bulunamadı.'))
    phase=('shaft_phase','SOLIDWORKS bağlantısı ve yerel özellikler hazırlanıyor…')
    page.handle_events([error,phase] if error_first else [phase,error])
    assert page.status_text==error[1]['error']
    assert page.status.property('role')=='error' and page.status.isVisible()


def test_failed_create_returns_to_idle_with_the_actual_error_visible(page,qtbot,monkeypatch):
    def fail(*args,**kwargs):
        raise RuntimeError('ShaftHost başlangıç hatası: test ayrıntısı')
    monkeypatch.setattr('modules.shaft_generator.bridge.execute',fail)
    page.create_model()
    qtbot.waitUntil(lambda:not page.jobs.busy,timeout=8000)
    assert page.create_button.isEnabled()
    assert page.status_text=='ShaftHost başlangıç hatası: test ayrıntısı'
    assert page.status.property('role')=='error' and page.status.isVisible()


@pytest.mark.parametrize('size',[(550,450),(790,560),(1120,780)])
def test_narrow_page_scrolls_forms_and_keeps_both_views_and_bottom_command_reachable(page,qtbot,size):
    page.resize(*size);qtbot.wait(30)
    assert page.size().toTuple()==size
    for view in (page.top_view,page.section_view):
        assert view.width()>=180 and view.height()>=170
        assert page.rect().contains(view.mapTo(page,view.rect().bottomRight()))
    assert page.rect().contains(page.create_button.mapTo(page,page.create_button.rect().bottomRight()))
    for index in range(5):
        page.tabs.setCurrentIndex(index);qtbot.wait(5)
        assert page.source_scroll.isVisible()


def test_registered_page_is_persistent_in_production_workspace(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'app.json');qtbot.addWidget(w)
    w.show();w.navigate('shaft_generator');p=w.pages['shaft_generator']
    assert w.browser.group_for_mode['shaft_generator']=='Üretim'
    p.table.item(0,2).setText('55');w.navigate('pdf');w.navigate('shaft_generator')
    assert w.pages['shaft_generator'] is p and p.project.total_length==205
    w.set_theme('light');assert p.top_view.appearance=='light'
    p.dirty=False;w.close()


def test_new_target_created_while_dialog_open_requires_explicit_overwrite(page,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path=tmp_path/'race.json'
    def dialog(*args,**kwargs):path.write_text('other process');return str(path),''
    monkeypatch.setattr(QFileDialog,'getSaveFileName',dialog)
    asked=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:asked.append(a[2]) or QMessageBox.No)
    page.dirty=True
    assert not page.save_dialog() and asked and page.dirty
    assert path.read_text()=='other process'


@pytest.mark.parametrize('answer,expected',[(QMessageBox.Cancel,False),(QMessageBox.Discard,True)])
def test_unsaved_project_close_can_be_cancelled_or_discarded(page,monkeypatch,answer,expected):
    page.dirty=True
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:answer)
    assert page.confirm_close() is expected


def test_save_cancel_or_error_does_not_authorize_close(page,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    page.dirty=True
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Save)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:('',''))
    assert not page.confirm_close() and page.dirty


def test_main_window_vetoes_close_for_unsaved_shaft(qtbot,tmp_path,monkeypatch):
    create_application([]);w=MainWindow(tmp_path/'close.json');qtbot.addWidget(w);w.show()
    p=w.pages['shaft_generator'];p.name.setText('UNSAVED')
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Cancel)
    w.close();assert w.isVisible() and not w.closing
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Discard)
    w.close();assert not w.isVisible()


@pytest.mark.parametrize('factor',['1','1.25','1.5'])
def test_qt_scale_factors_in_fresh_processes_keep_views_and_actions_inside(factor,tmp_path):
    import os,subprocess,sys
    code='''
from pathlib import Path
import sys
from gui_qt.app import create_application,MainWindow
app=create_application([]);w=MainWindow(Path(sys.argv[1]));w.navigate('shaft_generator')
for theme in ('dark','light'):
 w.set_theme(theme)
 for size in ((820,560),(1360,900)):
  w.resize(*size);w.show();app.processEvents();p=w.pages['shaft_generator']
  assert w.size().toTuple()==size
  for view in (p.top_view,p.section_view):
   assert view.width()>=180 and view.height()>=170
   assert p.rect().contains(view.mapTo(p,view.rect().bottomRight()))
  assert p.rect().contains(p.create_button.mapTo(p,p.create_button.rect().bottomRight()))
w.close()
'''
    subprocess.run([sys.executable,'-c',code,str(tmp_path/'scaled.json')],check=True,timeout=30,
                   cwd=Path(__file__).resolve().parents[3],env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QT_SCALE_FACTOR':factor})
