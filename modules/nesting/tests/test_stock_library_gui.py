from dataclasses import asdict
import json
from copy import deepcopy

from gui_qt.app import MainWindow
from modules.nesting.ui_widgets import Editor
from .test_nesting_gui import window  # noqa: F401
from modules.nesting.materials import new_project


def add_sheet(page,monkeypatch):
    def accept(dialog):
        for key,value in dict(name='Paslanmaz stok',width='1500',height='3000',thickness='4',
                              stock='17',price_kg='145',price_sheet='12000',pricing='TL/levha').items():
            dialog.form.set_value(key,value)
        material=next(label for label,key in dialog.form.material_ids.items() if key=='AISI 304')
        dialog.form.set_value('material',material)
        dialog.submit();return dialog.result()
    monkeypatch.setattr(Editor,'exec',accept)
    page.edit_sheet(new=True)
    return page.project.sheets[-1]


def test_added_sheet_survives_new_project_with_all_properties(window,monkeypatch):
    page=window.pages['nesting'];sheet=add_sheet(page,monkeypatch);expected=asdict(sheet)
    page.new_project()
    assert asdict(page.project.sheet(sheet.id))==expected
    assert not page.project.parts and not page.imports
    page.project.sheet(sheet.id).stock=0
    page.new_project()
    assert page.project.sheet(sheet.id).stock==17


def test_stock_is_written_automatically_and_restored_after_restart(window,qtbot,monkeypatch):
    page=window.pages['nesting'];sheet=add_sheet(page,monkeypatch)
    # No explicit project save or SettingsStore.flush call.
    saved=json.loads(window.settings.path.read_text())
    assert any(s['id']==sheet.id for s in saved['nesting_stock_library']['sheets'])
    reopened=MainWindow(window.settings.path);qtbot.addWidget(reopened)
    try:
        assert asdict(reopened.pages['nesting'].project.sheet(sheet.id))==asdict(sheet)
    finally:reopened.close()


def test_inspector_changes_and_zero_stock_are_remembered(window):
    page=window.pages['nesting'];sheet=page.project.sheets[0];inspector=page.inspector
    inspector.sheet_form.set_value('width','900')
    inspector.sheet_form.set_value('stock','0')
    assert inspector.apply_sheet()
    page.new_project()
    assert page.project.sheet(sheet.id).width==900 and page.project.sheet(sheet.id).stock==0


def test_loading_an_old_project_does_not_replace_shared_stock(window,monkeypatch):
    page=window.pages['nesting'];sheet=add_sheet(page,monkeypatch)
    saved=deepcopy(window.settings.get('nesting_stock_library'))
    old=new_project();old.sheets[0].width=444
    page.handle_events([('nest_project',(old,None,[],None))])
    assert page.project.sheets[0].width==444 and window.settings.get('nesting_stock_library')==saved
    page.new_project()
    assert page.project.sheet(sheet.id).width==1500


def test_removing_every_sheet_keeps_new_project_empty(window,monkeypatch):
    page=window.pages['nesting'];add_sheet(page,monkeypatch)
    while page.project.sheets:
        page.sheet_table.selectRow(0);page.remove_sheet()
    page.new_project()
    assert not page.project.sheets


def test_save_failure_is_visible_and_keeps_the_current_sheet(window,monkeypatch):
    page=window.pages['nesting']
    with monkeypatch.context() as fault:
        fault.setattr(window.settings,'flush',lambda:False)
        sheet=add_sheet(page,monkeypatch)
        assert page.project.sheet(sheet.id).stock==17
        assert 'kaydedilemedi' in page.status_text and window.settings.dirty


def test_corrupt_library_is_not_overwritten_by_a_stock_edit(window,monkeypatch):
    page=window.pages['nesting'];broken={'version':999,'sheets':[]}
    window.settings.set('nesting_stock_library',broken)
    add_sheet(page,monkeypatch)
    assert window.settings.get('nesting_stock_library')==broken
    assert 'kaydedilemedi' in page.status_text
