"""Actual import-preview edits, background reads and safe production gating."""
from copy import deepcopy

from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import QDialog

from .test_nesting_gui import window  # noqa: F401
from .test_filename_import import drawing
from modules.nesting.import_ui import ImportDialog
from modules.nesting.storage import load_project, save_project


def finish(window, qtbot):
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=10000)


def select(dialog, rows):
    selection=dialog.table.selectionModel(); selection.clearSelection()
    for row in rows:
        selection.select(dialog.preview_model.index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)


def test_preview_direct_and_selected_bulk_edits_reach_each_part(window,qtbot,tmp_path,monkeypatch):
    files=[drawing(tmp_path,n) for n in ('GOVDE 1,2 mm 12 adet.dxf','KAPAK T 2mm 5 adet.dxf','FLANS_T0,8_QTY20.dxf')]
    def check(dialog):
        m=dialog.preview_model
        assert [m.index(i,1).data() for i in range(3)]==['1.2','2','0.8']
        assert [m.index(i,2).data() for i in range(3)]==['12','5','20']
        assert m.setData(m.index(0,2),'7')
        select(dialog,[0,2]); dialog.bulk_thickness.setText('1,5'); dialog.apply_selected()
        assert [m.index(i,1).data() for i in range(3)]==['1.5','2','1.5']
        assert [m.index(i,2).data() for i in range(3)]==['7','5','20']
        dialog.submit(); return dialog.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import(files); finish(window,qtbot)
    assert [(p.thickness,p.quantity) for p in page.project.parts]==[(1.5,7),(2.,5),(1.5,20)]
    assert {e['options']['thickness'] for e in page.imports}=={1.5,2.}
    assert 'stok eksik' not in page.status_text  # Loading works independently of stock.
    assert page.missing_stock()


def test_conflicts_block_submission_until_each_field_is_explicitly_corrected(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,'KAPAK_T2_3MM_10AD_QTY20.dxf')
    def check(d):
        m=d.preview_model; assert m.index(0,3).data()=='Kontrol gerekli'
        d.submit(); assert d.result()!=QDialog.Accepted and d.value is None
        assert not m.setData(m.index(0,2),'1.5')
        assert 'tam sayı' in d.error.text()
        assert m.setData(m.index(0,1),'1,2'); d.submit()
        assert d.result()!=QDialog.Accepted
        assert m.setData(m.index(0,2),'8'); d.submit()
        assert d.result()==QDialog.Accepted
        return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import([path]); finish(window,qtbot)
    assert (page.project.parts[0].thickness,page.project.parts[0].quantity)==(1.2,8)


def test_auto_off_uses_manual_batch_defaults_and_keeps_explicit_cell_edits(window,qtbot,tmp_path,monkeypatch):
    paths=[drawing(tmp_path,n) for n in ('A_T2_12AD.dxf','B_T3_5AD.dxf')]
    def check(d):
        d.preview_model.setData(d.preview_model.index(0,2),'7')
        d.form.set_value('thickness','1,5'); d.form.set_value('quantity','4')
        d.auto.setChecked(False)
        assert d.preview_model.index(1,1).data()=='1.5' and d.preview_model.index(1,2).data()=='4'
        d.auto.setChecked(True)
        assert d.preview_model.index(0,2).data()=='7' and d.preview_model.index(1,2).data()=='5'
        d.auto.setChecked(False); d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import(paths); finish(window,qtbot)
    assert [(p.thickness,p.quantity) for p in page.project.parts]==[(1.5,7),(1.5,4)]
    assert page.project.parts[0].code=='A_T2_12AD'


def test_multicontour_review_blocks_nesting_and_retry_requires_count_confirmation(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,separate=3,hole=True); page=window.pages['nesting']
    page.import_files([path],quantity=8); finish(window,qtbot)
    e=page.imports[0]; assert e['status']=='review' and not page.project.parts
    page.start_nest(); assert not window.jobs.busy and 'henüz hazır değil' in page.status_text
    assert 'kontrol gerekli' in page.import_info.text()
    def check(d):
        d.submit(); assert d.result()!=QDialog.Accepted and 'onaylayın' in d.error.text()
        d.confirm_contours.setChecked(True)
        d.preview_model.setData(d.preview_model.index(0,2),'9')
        assert '27 kesim parçası' in d.contour_summary.text() and not d.confirm_contours.isChecked()
        d.preview_model.setData(d.preview_model.index(0,2),'8')
        d.confirm_contours.setChecked(True); d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page.configure_import([path],defaults=e['options'],retry_id=e['id'],detail=e['detail']); finish(window,qtbot)
    assert len(page.project.parts)==3 and sum(p.quantity for p in page.project.parts)==24
    assert len(page.imports)==1 and e['status']=='success'
    page.import_files([path]); assert not window.jobs.busy and len(page.project.parts)==3


def test_grouping_reviewed_contours_does_not_multiply_quantity(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,separate=3); page=window.pages['nesting']
    page.import_files([path],quantity=8); finish(window,qtbot); e=page.imports[0]
    def check(d):
        d.form.set_value('grouped',True); d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page.configure_import([path],defaults=e['options'],retry_id=e['id']); finish(window,qtbot)
    assert len(page.project.parts)==1 and page.project.parts[0].quantity==8


def test_error_retry_preserves_options_and_can_set_missing_unit_in_form(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,unit=0); page=window.pages['nesting']
    page.import_files([path],quantity=9,thickness=1.5,excluded_layers=['AUX']); finish(window,qtbot)
    e=page.imports[0]; assert e['status']=='error'
    def check(d):
        assert d.preview_model.index(0,2).data()=='9'
        assert d.preview_model.index(0,1).data()=='1.5'
        d.form.set_value('unit','mm'); d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page.configure_import([path],defaults=e['options'],retry_id=e['id']); finish(window,qtbot)
    part=page.project.parts[0]
    assert (part.quantity,part.thickness,part.area)==(9,1.5,600)
    assert len(page.imports)==1 and e['options']['excluded_layers']==['AUX']


def test_source_deduplication_survives_save_load_and_successful_retry(window,qtbot,tmp_path):
    path=drawing(tmp_path); page=window.pages['nesting']
    page.import_files([path,path],quantity=3); finish(window,qtbot)
    part=page.project.parts[0]; e=page.imports[0]
    page.set_part_quantity(part.id,7)
    target=tmp_path/'saved.goknest.json'; save_project(page.project,target,imports=page.imports)
    page.project,_,page.imports=load_project(target,with_imports=True)
    page.import_files([path]); assert not window.jobs.busy
    assert len(page.project.parts)==1 and page.project.parts[0].quantity==7
    e=page.imports[0]
    page.import_files([path],retry_id=e['id'],quantity=4); finish(window,qtbot)
    assert len(page.project.parts)==1 and page.project.parts[0].quantity==4
    assert len(page.imports)==1 and page.project.parts[0].id!=part.id
    page.part_table.selectRow(0); page.remove_part()
    assert not page.project.parts and not page.imports
    page.import_files([path]); finish(window,qtbot); assert len(page.project.parts)==1


def test_file_specific_advanced_options_do_not_change_other_sources(window,qtbot,tmp_path,monkeypatch):
    from modules.nesting.ui_widgets import Editor
    paths=[drawing(tmp_path,n,unit=0) for n in ('A_T2_2AD.dxf','B_T3_3AD.dxf')]
    def advanced(d):
        d.form.set_value('unit','cm'); d.form.set_value('excluded_layers','AUX;NOTE')
        d.form.set_value('join_tolerance','.005'); d.submit(); return d.result()
    monkeypatch.setattr(Editor,'exec',advanced)
    def check(d):
        select(d,[0]); d.edit_source_options()
        d.form.set_value('unit','mm')
        assert d.drafts[0].options(d.preview_model.defaults)['unit']=='cm'
        assert d.drafts[1].options(d.preview_model.defaults)['unit']=='mm'
        d.preview_model.setData(d.preview_model.index(0,2),'4')
        assert d.drafts[0].manual['excluded_layers']==['AUX','NOTE']
        d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import(paths); finish(window,qtbot)
    assert [(p.area,p.quantity) for p in page.project.parts]==[(60000,4),(600,3)]
    assert page.imports[0]['options']['join_tolerance']==.005
    assert page.imports[1]['options']['join_tolerance']==.001


def test_cancelling_preview_preserves_existing_geometry_and_result(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path); page=window.pages['nesting']; page.import_files([path]); finish(window,qtbot)
    page.form.set_value('quality','Hızlı'); page.start_nest(); finish(window,qtbot)
    result=page.result; fingerprint=page.project.fingerprint(); imports=deepcopy(page.imports)
    monkeypatch.setattr(ImportDialog,'exec',lambda d:QDialog.Rejected)
    page.configure_import([path])
    assert page.result is result and page.project.fingerprint()==fingerprint and page.imports==imports


def test_hundred_row_preview_bulk_edit_does_not_reset_other_fields(window,qtbot,tmp_path,monkeypatch):
    files=[tmp_path/f'P{i}_T2_2AD.dxf' for i in range(100)]
    def check(d):
        select(d,range(20)); d.bulk_thickness.setText('1,5'); d.apply_selected()
        assert sum(p.options(d.preview_model.defaults)['thickness']==1.5 for p in d.drafts)==20
        assert all(p.options(d.preview_model.defaults)['quantity']==2 for p in d.drafts)
        d.bulk_quantity.setText('10001'); d.apply_selected()
        assert 'tam sayı' in d.error.text()
        assert all(p.options(d.preview_model.defaults)['quantity']==2 for p in d.drafts)
        return QDialog.Rejected
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import(files)
    assert not page.imports and not window.jobs.busy


def test_actual_cell_editor_rejects_invalid_quantity_and_commits_decimal_comma(window,qtbot,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QLineEdit
    path=drawing(tmp_path)
    def check(d):
        d.show(); qtbot.wait(40)
        index=d.preview_model.index(0,1); d.table.edit(index)
        field=next(e for e in d.table.findChildren(QLineEdit) if e.isVisible())
        field.selectAll(); qtbot.keyClicks(field,'1,5'); qtbot.keyClick(field,Qt.Key_Return)
        qtbot.waitUntil(lambda:d.drafts[0].manual.get('thickness')==1.5)
        assert not d.preview_model.setData(d.preview_model.index(0,2),'0')
        d.submit(); assert d.result()!=QDialog.Accepted and 'Hatalı hücre' in d.error.text()
        d.preview_model.setData(d.preview_model.index(0,2),'4'); d.submit()
        return d.result()
    monkeypatch.setattr(ImportDialog,'exec',check)
    page=window.pages['nesting']; page.configure_import([path]); finish(window,qtbot)
    assert (page.project.parts[0].thickness,page.project.parts[0].quantity)==(1.5,4)


def test_preview_fits_available_screen_and_both_themes_without_losing_edits(window,qtbot,tmp_path,monkeypatch):
    files=[tmp_path/n for n in ('ŞASE_T1,2_12AD.dxf','KAPAK_T2_3MM_10AD.dxf')]
    def check(d):
        m=d.preview_model; assert m.index(1,1).data()=='—'
        m.setData(m.index(0,2),'7')
        d.show(); qtbot.wait(30)
        for theme in ('dark','light'):
            window.set_theme(theme); qtbot.wait(30)
            available=d.screen().availableGeometry()
            assert d.width()<=available.width() and d.height()<=available.height()
            assert d.table.viewport().height()>100
            assert d.table.visualRect(m.index(0,3)).right()<=d.table.viewport().width()
            assert m.index(0,2).data()=='7'
            assert d.buttons.geometry().bottom()<=d.height()
        return QDialog.Rejected
    monkeypatch.setattr(ImportDialog,'exec',check)
    window.pages['nesting'].configure_import(files)


def test_old_import_history_without_part_ids_replaces_geometry_on_retry(window,qtbot,tmp_path):
    path=drawing(tmp_path); page=window.pages['nesting']
    page.import_files([path],quantity=2); finish(window,qtbot)
    e=page.imports[0]; e.pop('part_ids')  # Version 1 history produced before the new links.
    page.import_files([path],retry_id=e['id'],quantity=3); finish(window,qtbot)
    assert len(page.project.parts)==1 and page.project.parts[0].quantity==3


def test_failed_successful_source_retry_keeps_original_geometry(window,qtbot,tmp_path):
    path=drawing(tmp_path); page=window.pages['nesting']
    page.import_files([path],quantity=2); finish(window,qtbot)
    part=page.project.parts[0]; e=page.imports[0]; path.write_text('broken DXF')
    page.import_files([path],retry_id=e['id'],quantity=3); finish(window,qtbot)
    assert page.project.parts==[part] and e['status']=='error'
    page.start_nest(); assert not window.jobs.busy and 'henüz hazır değil' in page.status_text


def test_project_without_import_history_still_deduplicates_source_geometry(window,qtbot,tmp_path):
    path=drawing(tmp_path); page=window.pages['nesting']
    page.import_files([path],quantity=2); finish(window,qtbot)
    target=tmp_path/'legacy.goknest.json'; save_project(page.project,target)
    page.project,_,page.imports=load_project(target,with_imports=True)
    page.import_files([path]); assert not window.jobs.busy
    assert len(page.project.parts)==1 and page.project.parts[0].quantity==2
