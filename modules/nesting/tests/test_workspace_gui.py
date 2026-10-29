"""Native Qt workbench interactions with real DXFs, worker search and accounting."""

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt,QPointF
from PySide6.QtWidgets import QTreeView,QFileDialog
from shapely.geometry import Polygon,box

from .test_nesting_gui import window,load_parts  # noqa: F401
from modules.nesting.models import Part,Sheet,uid
from modules.nesting.validation import validate_result
from modules.nesting.storage import load_project

ROOT=Path(__file__).resolve().parents[3]


def finish(w,qtbot):
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=10000)


def plan(p,w,qtbot):
    p.form.set_value('quality','Hızlı');p.form.set_value('seconds','2')
    p.nest_button.click();finish(w,qtbot)
    assert p.result is not None
    validate_result(p.project,p.result,complete=False)


def test_only_existing_commands_and_actual_stock_are_present_in_the_empty_workbench(window):
    p=window.pages['nesting']
    assert [b.text() for b in p.command_groups]==['DOSYA','DÜZENLE','YERLEŞİM','GÖRÜNÜM','RAPOR']
    assert isinstance(p.part_tree,QTreeView) and isinstance(p.sheet_tree,QTreeView)
    assert p.sheet_tree_model.rowCount()==len(p.project.sheets) and not p.sheet_tree_model.by_key
    assert p.result is None and p.canvas.mode=='stock'
    assert p.result_sheet_model.rowCount()==0 and not p.result_tabs.isVisible()
    assert not p.excel_button.isEnabled() and p.unit_status.text()=='mm'


def test_real_dxf_hole_is_visible_before_search_and_tree_click_highlights_exact_contour(window,qtbot):
    p=window.pages['nesting'];path=ROOT/'docs/nesting-example/input/GW-002.dxf';before=path.read_bytes()
    p.import_files([str(path)],quantity=2);finish(window,qtbot)
    part=p.project.parts[0];geometry=deepcopy(part.geometry)
    index=p.part_tree_model.index_for_id(part.id)
    qtbot.mouseClick(p.part_tree.viewport(),Qt.LeftButton,pos=p.part_tree.visualRect(index).center())
    assert p.result is None and p.canvas.mode=='part' and p.canvas.key is None
    item=p.canvas.part_items[part.id][0]
    hole=Polygon(part.polygon.interiors[0]).representative_point()
    solid=part.polygon.representative_point()
    assert not item.path().contains(QPointF(hole.x,-hole.y))
    assert item.path().contains(QPointF(solid.x,-solid.y))
    assert p.canvas.selected_part_ids=={part.id} and 'Yerleşim sonucu değildir' in p.current_note.text()
    assert 'Net alan' in p.inspector.part_info.text()
    assert part.geometry==geometry and path.read_bytes()==before


def test_sheet_draft_blocks_old_exports_and_invalid_values_never_mutate_domain(window,qtbot,tmp_path):
    p=load_parts(window,qtbot,tmp_path);plan(p,window,qtbot)
    sheet=p.project.sheets[0];old=deepcopy(sheet);i=p.inspector
    i.sheet_form.fields['width'].setText('0')
    assert i.sheet_dirty and i.sheet_actions.isVisible() and p.result is None
    assert not p.dxf_button.isEnabled() and not i.apply_sheet()
    assert p.project.sheets[0]==old and 'Sac eni' in i.sheet_error.text()
    p.start_nest();assert not window.jobs.busy and p.result is None
    i.revert_sheet();assert not i.sheet_dirty and not i.sheet_actions.isVisible()
    i.sheet_form.fields['width'].setText('900');i.sheet_form.fields['height'].setText('1800')
    assert i.apply_sheet()
    assert p.project.sheets[0].width==900 and p.project.sheets[0].height==1800
    assert p.project.sheets[0].id==old.id and not i.sheet_dirty
    i.sheet_form.fields['width'].setText('')
    p.sheet_table.selectRow(0);p.remove_sheet()
    assert not p.project.sheets and not i.sheet_dirty and not i.sheet_actions.isVisible()
    assert not i.sheet_error.isVisible() and not i.sheet_form.isEnabled()


def test_start_applies_valid_stock_draft_then_uses_unchanged_real_engine(window,qtbot,tmp_path):
    p=load_parts(window,qtbot,tmp_path);i=p.inspector
    i.sheet_form.fields['width'].setText('900')
    plan(p,window,qtbot)
    assert not i.sheet_dirty and p.project.sheets[0].width==900
    assert p.result.digest==p.project.fingerprint() and p.totals['part_count']==3
    assert p.module_status.currentMessage()=='Tamamlandı'


def test_save_applies_stock_draft_and_round_trips_existing_json_without_new_schema(window,qtbot,tmp_path,monkeypatch):
    p=load_parts(window,qtbot,tmp_path);p.inspector.sheet_form.fields['stock'].setText('7')
    target=tmp_path/'project.goknest.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    p.save_project();finish(window,qtbot)
    project,result=load_project(target)
    assert project.sheets[0].stock==7 and result is None
    assert project.parts[0].source_sha256==p.project.parts[0].source_sha256


def test_actual_physical_sheet_children_and_part_selection_drive_the_same_view(window,qtbot):
    p=window.pages['nesting'];s=p.project.sheets[0]
    s.width=s.height=100
    other=Sheet(uid(),'Three millimetres',100,100,3,stock=3)
    unused=Sheet(uid(),'Unused stock',200,300,stock=0)
    p.project.sheets.extend([other,unused])
    p.project.parts=[Part.create('Two',box(0,0,35,35),quantity=5),Part.create('Three',box(0,0,35,35),thickness=3)]
    p.refresh();plan(p,window,qtbot)
    actual={(x.sheet_id,x.sheet_number) for x in p.result.placements}
    assert set(p.sheet_tree_model.by_key)==actual
    assert sum(p.sheet_tree_model.item(r).rowCount() for r in range(p.sheet_tree_model.rowCount()))==len(actual)
    part=p.project.parts[1];p.part_tree.select_index(p.part_tree_model.index_for_id(part.id))
    assert p.canvas.key[0]==other.id and part.id in p.canvas.part_items
    item=p.sheet_tree_model.by_key[(s.id,1)]
    qtbot.mouseClick(p.sheet_tree.viewport(),Qt.LeftButton,pos=p.sheet_tree.visualRect(item.index()).center())
    assert p.canvas.key==(s.id,1) and p.selected_sheet_key()==(s.id,1)
    result=p.result
    i=p.inspector;i.sheet.setCurrentIndex(i.sheet.findData(unused.id));i.sheet.activated.emit(i.sheet.currentIndex())
    assert p.canvas.mode=='stock' and p.canvas.key is None and p.result is result
    assert '200 × 300' in p.current_note.text() and 'Stok önizlemesi' in p.selection_status.text()
    assert unused.id not in {key[0] for key in p.sheet_tree_model.by_key}


def test_zoom_grid_and_view_controls_do_not_change_placement_or_geometry(window,qtbot,tmp_path):
    p=load_parts(window,qtbot,tmp_path);plan(p,window,qtbot)
    before=deepcopy(p.result);fingerprint=p.project.fingerprint();items=set(p.canvas.scene().items())
    scale=p.canvas.transform().m11();p.zoom_in_action.trigger()
    assert p.canvas.transform().m11()>scale and not p.canvas.auto_fit
    p.grid_action.setChecked(False);assert not p.canvas.show_grid
    p.fit_button.click();assert p.canvas.auto_fit
    assert p.result==before and p.project.fingerprint()==fingerprint and set(p.canvas.scene().items())==items
    p.parts_view_action.setChecked(False);assert not p.parts_panel.isVisible()
    p.parts_view_action.setChecked(True);assert p.parts_panel.isVisible() and p.result==before


def test_results_use_real_conservation_values_and_partial_rows_are_explicit(window,qtbot):
    p=window.pages['nesting'];p.project.sheets[0].width=p.project.sheets[0].height=100
    p.project.sheets[0].stock=1
    p.project.parts=[Part.create('Small',box(0,0,35,35),quantity=5),Part.create('Cannot fit',box(0,0,200,200))]
    p.refresh();plan(p,window,qtbot)
    p.results_action.setChecked(True)
    assert p.result_tabs.isVisible() and p.result.unplaced
    assert p.result_sheet_model.rows==p.totals['sheets']
    for row in p.result_sheet_model.rows:
        assert abs(row['gross_weight']-row['net_weight']-row['waste_weight'])<1e-9
    missing=next(r for r in p.result_part_model.rows if r['code']=='Cannot fit')
    assert missing['quantity']==0 and missing['requested']==1 and missing['sheets']=='Yerleşmedi'
    assert not p.pdf_button.isEnabled() and not p.excel_button.isEnabled()
    p.form.set_value('gap','4');assert not p.result_tabs.isVisible() and not p.sheet_tree_model.by_key


def test_requested_resolutions_and_both_themes_keep_geometry_and_selected_ids(window,qtbot,tmp_path):
    p=load_parts(window,qtbot,tmp_path);plan(p,window,qtbot)
    selected=p.project.parts[0].id;p.part_tree.select_index(p.part_tree_model.index_for_id(selected))
    result=p.result
    for theme in ('dark','light'):
        window.set_theme(theme)
        for width,height in ((1366,768),(1920,1080),(1024,700),(820,560)):
            window.resize(width,height);qtbot.wait(50)
            for expanded in (True,False):
                p.results_action.setChecked(expanded);qtbot.wait(40)
                assert window.size().toTuple()==(width,height)
                assert p.canvas.width()>=190 and p.canvas.height()>=60
                assert p.canvas.selected_part_ids=={selected} and p.result is result
                assert p.part_tree.horizontalScrollBar().maximum()==0
                assert p.nesting_commands.rect().contains(p.nest_button.mapTo(p.nesting_commands,p.nest_button.rect().bottomRight()))
