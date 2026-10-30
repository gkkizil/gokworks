"""Native parameter editing, one-command edge batches and safe rollback."""
from copy import deepcopy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from modules.shaft_generator.tests.test_ui import page  # noqa: F401
from modules.shaft_generator.models import Groove,Chamfer,Fillet,Stage,Project
from modules.shaft_generator import storage,controller


def test_section_picker_replaces_overflowing_tabs_and_keeps_targets_in_sync(page,qtbot):
    assert page.tabs.tabBar().isHidden() and page.section_picker.count()==8
    assert not page.new_operation_button.isVisible() and page.operation_count.text().endswith('0')
    page.section_picker.setCurrentIndex(2)
    assert page.tabs.currentIndex()==2 and page.add_operation_buttons['keyway'].isVisible()
    assert not page.operation_actions['groove'].isVisible()
    target=page.operation_targets['keyway'];target.setCurrentIndex(2)
    assert page.selected_stage==page.project.stages[2].id and page.table.currentRow()==2
    assert '3. kademe' in page.selected_stage_caption.text()
    assert page.top_view.selected_stage==page.section_view.selected_stage==page.selected_stage
    assert not page.project.operations


def test_new_and_existing_operation_modes_are_distinct_and_do_not_duplicate_records(page):
    page.section_picker.setCurrentIndex(1);page.add_operation_buttons['groove'].click()
    op=page.project.operations[0]
    assert page.selected_operation==op.id and page.new_operation_button.isVisible()
    assert not page.add_operation_buttons['groove'].isEnabled()
    assert page.update_operation_buttons['groove'].isEnabled()
    assert 'düzenleniyor' in page.edit_mode.text()
    page.operation_fields['groove']['width'].setValue(3)
    assert op.width==3 and len(page.project.operations)==1
    page.new_operation_button.click()
    assert not page.selected_operation and page.add_operation_buttons['groove'].isEnabled()
    assert not page.update_operation_buttons['groove'].isEnabled()
    page.operation_fields['groove']['offset'].setValue(12)
    assert op.offset==5  # The draft no longer edits the selected live operation.
    page.add_operation_buttons['groove'].click()
    assert len(page.project.operations)==2 and page.project.operations[1].offset==12
    page.section_picker.setCurrentIndex(2)
    assert not page.selected_operation and page.edit_mode.text()=='Yeni işlem ekle'


@pytest.mark.parametrize('kind',['chamfer','fillet'])
def test_one_button_applies_all_real_corners_and_produces_the_existing_cad_payload(page,qtbot,kind):
    before=page.project.to_dict();page.bulk_shortcut.click()
    assert page.tabs.currentIndex()==7 and page.section_picker.currentData()==7
    assert not page.bulk_shortcut.isVisible() and '8 gerçek kenar' in page.bulk_info.text()
    page.bulk_kind.setCurrentIndex(page.bulk_kind.findData(kind));page.bulk_size.setValue(.5)
    assert page.bulk_size_label.text()==('Pah mesafesi · mm' if kind=='chamfer' else 'Radyüs · mm')
    page.bulk_button.click()
    assert page.dirty and len(page.project.operations)==8 and page.create_button.isEnabled()
    assert {op.kind for op in page.project.operations}=={kind}
    assert '8 yeni' in page.status_text and page.operation_count.text().endswith('8')
    request=controller.request(page.project)
    assert len(request['plan'])==12 and request['project']['version']==1
    assert [row['kind'] for row in request['plan']]==['revolve']*4+[kind]*8
    qtbot.waitUntil(lambda:len(page.top_view.operation_regions)==len(page.section_view.operation_regions)==8)
    assert page.edge_undo_button.isEnabled()
    page.edge_undo_button.click()
    assert page.project.to_dict()==before and not page.dirty and not page.edge_undo_button.isEnabled()


def test_existing_edges_are_preserved_until_explicit_replace_and_repeated_apply_is_a_noop(page):
    page.project.operations=[Fillet(page.project.stages[0].id,radius=.75)]
    page.populate();page.refresh();page.show_bulk_treatments();page.bulk_button.click()
    old=next(op for op in page.project.operations if isinstance(op,Fillet))
    assert old.radius==.75 and len(page.project.operations)==8 and '1 korundu' in page.status_text
    applied=page.project.to_dict();undo=page.edge_undo
    page.bulk_button.click()
    assert page.project.to_dict()==applied and page.edge_undo is undo
    page.bulk_kind.setCurrentIndex(1);page.bulk_size.setValue(.5);page.bulk_replace.setChecked(True)
    assert '8 güncelleme' in page.bulk_info.text()
    page.bulk_button.click()
    assert len(page.project.operations)==8 and all(isinstance(op,Fillet) and op.radius==.5 for op in page.project.operations)
    assert {op.id for op in page.project.operations}=={op['id'] for op in applied['operations']}


def test_invalid_batch_is_atomic_and_undo_never_erases_a_later_manual_edit(page):
    page.project=Project(stages=[Stage(30,40),Stage(32,40)])
    page.selected_stage=page.project.stages[0].id;page.populate();page.refresh()
    before=page.project.to_dict();original=page.project;page.show_bulk_treatments()
    page.bulk_size.setValue(.75);page.bulk_button.click()
    assert page.project is original and page.project.to_dict()==before and not page.dirty
    assert 'uygulanamadı' in page.status_text and 'omuz' in page.status_text
    assert page.edge_undo is None and page.create_button.isEnabled()
    page.bulk_size.setValue(.25);page.bulk_button.click()
    assert len(page.project.operations)==4 and page.edge_undo_button.isEnabled()
    page.table.item(0,2).setText('45')
    assert not page.edge_undo_button.isEnabled()
    changed=page.project.to_dict();page.undo_bulk_treatments()
    assert page.project.to_dict()==changed and page.dirty and 'geri alınmadı' in page.status_text


def test_batch_keeps_channels_and_works_after_project_save_load_without_schema_changes(page,tmp_path,monkeypatch):
    page.project.operations=[Groove(page.project.stages[0].id)]
    channel=deepcopy(page.project.operations[0]);page.populate();page.refresh()
    page.show_bulk_treatments();page.bulk_size.setValue(.5);page.bulk_button.click()
    assert page.project.operations[0]==channel and len(page.project.operations)==9
    target=tmp_path/'bulk.gokshaft.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    assert page.save_dialog() and not page.dirty
    loaded=storage.load(target)
    assert loaded.to_dict()==page.project.to_dict() and loaded.to_dict()['version']==1
    page.edge_undo_button.click()
    assert page.project.operations==[channel] and page.dirty  # Saved file still contains the batch.
    assert len(storage.load(target).operations)==9


def test_loading_a_project_clears_the_previous_batch_undo(page,tmp_path,monkeypatch):
    page.show_bulk_treatments();page.bulk_button.click();assert page.edge_undo is not None
    path=tmp_path/'other.json';other=Project(name='OTHER');storage.save(other,path)
    monkeypatch.setattr(page,'confirm_discard',lambda:True)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    page.open_dialog()
    assert page.project.name=='OTHER' and page.edge_undo is None and not page.edge_undo_button.isEnabled()


def test_bulk_form_accepts_turkish_decimal_comma_without_touching_drafts_until_apply(page,qtbot):
    page.show_bulk_treatments();field=page.bulk_size.lineEdit()
    field.setFocus();field.selectAll();qtbot.keyClicks(field,'0,75');qtbot.keyClick(field,Qt.Key_Return)
    assert page.bulk_size.value()==.75 and not page.project.operations
    page.bulk_button.click()
    assert len(page.project.operations)==8 and all(op.distance==.75 for op in page.project.operations)


@pytest.mark.parametrize('theme',['dark','light'])
def test_bulk_controls_and_add_action_stay_reachable_at_normal_size_and_preview_classes_unchanged(page,qtbot,theme):
    from gui_qt.theme import apply_theme
    from PySide6.QtWidgets import QApplication
    from modules.shaft_generator.preview import ShaftPreview
    page.context.appearance=theme;apply_theme(QApplication.instance(),theme);page.theme_changed()
    page.resize(1100,780);page.show_bulk_treatments();qtbot.wait(40)
    assert type(page.top_view) is ShaftPreview and type(page.section_view) is ShaftPreview
    page.source_scroll.ensureWidgetVisible(page.bulk_button);qtbot.wait(20)
    viewport=page.source_scroll.viewport()
    assert viewport.rect().contains(page.bulk_button.mapTo(viewport,page.bulk_button.rect().bottomRight()))
    page.section_picker.setCurrentIndex(2);qtbot.wait(30)
    action=page.add_operation_buttons['keyway']
    assert action.isVisible() and page.rect().contains(action.mapTo(page,action.rect().bottomRight()))
