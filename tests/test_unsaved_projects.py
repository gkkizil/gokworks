"""Unsaved project work survives New / Open / Example / quit and a failed save (Ö1 acceptance).

The Save / Continue without saving / Cancel question is answered through
``gui_qt.projects.ask`` so each path runs the real page commands and jobs.
"""
import json
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog

from gui_qt import projects
from gui_qt.app import MainWindow, create_application
from modules.nesting.tests.test_filename_import import drawing


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.show(); yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=8000)
    projects.ask = ORIGINAL_ASK
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


ORIGINAL_ASK = projects.ask


def answer(monkeypatch, *choices):
    asked = []
    queue = list(choices)
    def ask(page, action):
        asked.append((page.project_title, action))
        if not queue:
            raise AssertionError(f'unexpected question: {page.project_title} / {action}')
        return queue.pop(0)
    monkeypatch.setattr(projects, 'ask', ask)
    return asked


def no_dialog(*args, **kwargs):
    raise AssertionError('a file dialog must not open')


def nesting_with_part(window, qtbot, tmp_path):
    page = window.pages['nesting']
    page.import_files([drawing(tmp_path, 'GOVDE_T2_8AD.dxf')], thickness=2)
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert len(page.project.parts) == 1
    return page


def test_unchanged_project_never_asks(window, qtbot, monkeypatch):
    asked = answer(monkeypatch)
    page = window.pages['nesting']
    assert not page.has_unsaved_changes()
    page.new_project()
    assert asked == []


def test_nesting_new_after_part_and_quantity_change_asks_and_cancel_keeps_work(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    part = page.project.parts[0]
    page.set_part_quantity(part.id, part.quantity + 4)
    assert page.has_unsaved_changes()
    asked = answer(monkeypatch, projects.CANCEL)
    page.new_project()
    assert asked == [('Nesting projesi', 'Yeni projeye geçmeden')]
    assert len(page.project.parts) == 1 and page.project.parts[0].quantity == part.quantity + 4
    assert page.has_unsaved_changes()


def test_open_cancel_keeps_work_and_opens_no_dialog(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', no_dialog)
    answer(monkeypatch, projects.CANCEL)
    page.open_project()
    assert len(page.project.parts) == 1 and page.has_unsaved_changes()


def test_continue_without_saving_replaces_work_and_is_clean(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    answer(monkeypatch, projects.DISCARD)
    page.new_project()
    assert not page.project.parts and not page.has_unsaved_changes()


def test_cancelled_save_dialog_keeps_work(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    answer(monkeypatch, projects.SAVE)
    assert page.guard_unsaved('Yeni projeye geçmeden', page._new_project) is False
    assert len(page.project.parts) == 1 and page.has_unsaved_changes()


def test_failed_save_keeps_work_and_does_not_continue(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    target = tmp_path/'proje.goknest.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    import modules.nesting.storage as storage
    def disk_full(*args, **kwargs):
        raise OSError(28, 'No space left on device')
    monkeypatch.setattr(storage, 'save_project', disk_full)
    answer(monkeypatch, projects.SAVE)
    page.new_project()
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert not target.exists()
    assert len(page.project.parts) == 1 and page.has_unsaved_changes()


def test_async_save_continues_only_after_it_succeeded(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    target = tmp_path/'proje.goknest.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    answer(monkeypatch, projects.SAVE)
    page.new_project()
    assert len(page.project.parts) == 1          # still saving: nothing replaced yet
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert target.is_file() and not page.project.parts and not page.has_unsaved_changes()


def test_returning_to_saved_content_does_not_warn(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    page.mark_project_saved()
    part = page.project.parts[0]
    page.set_part_quantity(part.id, part.quantity + 1)
    assert page.has_unsaved_changes()
    page.set_part_quantity(part.id, part.quantity)
    assert not page.has_unsaved_changes()


def test_open_resets_dirty_state(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    target = tmp_path/'kayit.goknest.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    page.save_project(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert not page.has_unsaved_changes()
    answer(monkeypatch, projects.DISCARD)
    saved = page.project.parts[0].quantity
    page.set_part_quantity(page.project.parts[0].id, saved + 3)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(target), ''))
    page.open_project(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert page.project.parts[0].quantity == saved and not page.has_unsaved_changes()


def user_close(window):
    event = QCloseEvent()
    window.user_close = True
    window.closeEvent(event)
    return event.isAccepted()


def test_exit_asks_for_every_module_with_unsaved_work_and_cancel_keeps_window(window, qtbot, tmp_path, monkeypatch):
    nesting = nesting_with_part(window, qtbot, tmp_path)
    hydraulic = window.pages['hydraulic_unit']
    hydraulic.project = replace(hydraulic.project, name=hydraulic.project.name + ' değişti')
    assert hydraulic.has_unsaved_changes() and nesting.has_unsaved_changes()
    asked = answer(monkeypatch, projects.DISCARD, projects.CANCEL)
    assert not user_close(window)
    assert [title for title, _ in asked] == ['Nesting projesi', 'Hidrolik proje'] or \
           [title for title, _ in asked] == ['Hidrolik proje', 'Nesting projesi']
    assert window.isVisible() and len(nesting.project.parts) == 1


def test_exit_without_changes_asks_nothing(window, monkeypatch):
    answer(monkeypatch)
    window.pages['nesting']; window.pages['hydraulic_unit']
    assert window.confirm_unsaved_projects()


def test_programmatic_close_keeps_shaft_only_check(window, monkeypatch):
    # Test and shutdown paths close the window without a user: only the shaft's own check runs there.
    answer(monkeypatch)
    hydraulic = window.pages['hydraulic_unit']
    hydraulic.project = replace(hydraulic.project, name=hydraulic.project.name + ' x')
    shaft = window.pages['shaft_generator']
    assert shaft.confirm_close()


def test_recovery_copy_is_separate_atomic_and_restored_as_unsaved(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    window.write_recovery()
    folder = window.recovery.folder
    manifest = json.loads((folder/'nesting.recovery.json').read_text(encoding='utf-8'))
    assert manifest['format'] == 'GOKWORKS-RECOVERY' and manifest['version'] == 1
    data = folder/manifest['file']
    assert data.is_file() and data.parent == folder and not list(folder.glob('*.tmp'))
    # A damaged second manifest is ignored, never raised.
    (folder/'hydraulic_unit.recovery.json').write_text('{bozuk', encoding='utf-8')
    found = window.recovery.available(set(window.pages))
    assert [key for key, _, _ in found] == ['nesting']
    answer(monkeypatch, projects.DISCARD)
    page.new_project(); assert not page.project.parts
    window.restore_recovery(found); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=15000)
    assert len(page.project.parts) == 1 and page.has_unsaved_changes()


def test_clean_page_drops_its_recovery_copy(window, qtbot, tmp_path, monkeypatch):
    page = nesting_with_part(window, qtbot, tmp_path)
    window.write_recovery(); assert (window.recovery.folder/'nesting.recovery.json').exists()
    page.mark_project_saved(); window.write_recovery()
    assert not list(window.recovery.folder.glob('nesting.recovery*'))


def test_corrupt_recovery_folder_does_not_block_startup(qtbot, tmp_path):
    folder = tmp_path/'recovery'; folder.mkdir()
    (folder/'nesting.recovery.json').write_bytes(b'\xff\xfe bozuk')
    (folder/'x.recovery.json').write_text(json.dumps(dict(format='GOKWORKS-RECOVERY', version=1, module='nesting',
                                                          file='../../etc/passwd')), encoding='utf-8')
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.show(); QCoreApplication.processEvents()
    assert w.recovery.available(set(w.pages)) == []
    w.close()


@pytest.mark.parametrize('key', ['nesting', 'profile_cutting', 'shaft_generator', 'tolerance_stack',
                                 'sheet_unfolding', 'hydraulic_unit', 'belt_drive'])
def test_every_project_module_starts_clean_and_has_a_recovery_writer(window, key):
    page = window.pages[key]
    assert page.project_title and page.recovery_suffix
    assert not page.has_unsaved_changes()


def test_hydraulic_example_is_guarded_and_loading_it_is_clean(window, monkeypatch):
    page = window.pages['hydraulic_unit']
    page.project = replace(page.project, name='Kullanıcı ünitesi')
    answer(monkeypatch, projects.CANCEL)
    page.load_example()
    assert page.project.name == 'Kullanıcı ünitesi' and page.has_unsaved_changes()
    answer(monkeypatch, projects.DISCARD)
    page.load_example()
    assert page.project.name != 'Kullanıcı ünitesi' and not page.has_unsaved_changes()


def test_tolerance_stack_new_and_example_are_guarded(window, monkeypatch):
    page = window.pages['tolerance_stack']
    page.load_example(); assert not page.has_unsaved_changes()
    page.form.set_value('name', page.form.value('name') + ' değişti')
    assert page.has_unsaved_changes()
    asked = answer(monkeypatch, projects.CANCEL, projects.CANCEL)
    page.new_project(); page.load_example()
    assert len(asked) == 2 and page.form.value('name').endswith(' değişti')
