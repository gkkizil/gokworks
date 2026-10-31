from threading import Event

from PySide6.QtWidgets import QFileDialog

from .test_nesting_gui import window  # noqa: F401
from .test_folder_import import dxf


def test_folder_command_discovers_in_worker_and_keeps_existing_project(window,qtbot,tmp_path,monkeypatch):
    p=window.pages['nesting'];sub=tmp_path/'sub';sub.mkdir()
    source=sub/'Panel - 2 mm - 4 adet.dxf';dxf(source)
    existing=tmp_path/'existing.dxf';dxf(existing)
    p.import_files([existing]);qtbot.waitUntil(lambda:not window.jobs.busy)
    calls=[]
    def configure(files,**kwargs):calls.append((files,kwargs))
    monkeypatch.setattr(p,'configure_import',configure)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a,**k:str(sub.parent))
    p.import_folder_button.click()
    qtbot.waitUntil(lambda:not window.jobs.busy and bool(calls))
    assert str(source) in calls[0][0] and len(p.project.parts)==1
    assert 'Alt klasörler' in calls[0][1]['detail']
    # The reviewed plan enters the normal importer and deduplicates existing data.
    p.import_files(calls[0][0]);qtbot.waitUntil(lambda:not window.jobs.busy)
    assert len(p.project.parts)==2
    p.import_files(calls[0][0]);assert len(p.project.parts)==2 and not window.jobs.busy


def test_stop_does_not_open_a_late_folder_review(window,qtbot,tmp_path,monkeypatch):
    p=window.pages['nesting'];entered=Event();calls=[]
    source=tmp_path/'source.dxf';dxf(source)
    def scan(directory,**kwargs):
        entered.set();assert kwargs['stop'].wait(3)
        return [str(source)],[]
    monkeypatch.setattr('modules.nesting.folder_import.discover_sources',scan)
    monkeypatch.setattr(p,'configure_import',lambda *a,**k:calls.append(True))
    p.import_folder(tmp_path);qtbot.waitUntil(entered.is_set)
    p.stop_button.click();qtbot.waitUntil(lambda:not window.jobs.busy);qtbot.wait(60)
    assert not calls and p.folder_import_pending is None and not p.project.parts


def test_real_folder_review_keeps_filename_quantities_without_double_import(window,qtbot,tmp_path,monkeypatch):
    from modules.nesting.import_ui import ImportDialog
    p=window.pages['nesting'];sub=tmp_path/'sub';sub.mkdir()
    first=tmp_path/'Plate - 2 mm - 3 adet.dxf';second=sub/'Lid - 4 mm - 5 adet.dxf'
    dxf(first);dxf(second);first.with_suffix('.dwg').write_bytes(b'AC1032 paired drawing')
    reviews=[]
    def accept(dialog):
        reviews.append(len(dialog.drafts));dialog.submit();return dialog.result()
    monkeypatch.setattr(ImportDialog,'exec',accept)
    p.import_folder(tmp_path)
    qtbot.waitUntil(lambda:len(p.project.parts)==2 and not window.jobs.busy,timeout=8000)
    assert reviews==[2] and sorted((part.thickness,part.quantity) for part in p.project.parts)==[(2.,3),(4.,5)]
    p.import_folder(tmp_path)
    qtbot.waitUntil(lambda:len(reviews)==2 and not window.jobs.busy,timeout=8000)
    assert len(p.project.parts)==2 and sum(part.quantity for part in p.project.parts)==8


def test_distinct_unicode_file_names_are_not_silently_merged(window,qtbot,tmp_path):
    p=window.pages['nesting']
    first=tmp_path/'Straße.dxf';second=tmp_path/'Strasse.dxf';dxf(first);dxf(second)
    p.import_files([first,second]);qtbot.waitUntil(lambda:not window.jobs.busy)
    assert len(p.project.parts)==2
