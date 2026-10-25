"""A destination error must never hide files read from Pack and Go."""

import gc
from pathlib import Path, PureWindowsPath
import queue
import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt

from gui_qt.app import MainWindow, create_application
from modules.naming.exporter import Document, Snapshot, path_key
from modules.naming.hierarchy import document_rows
from modules.naming.ui import NamingPage


def snapshot_at(folder):
    folder.mkdir()
    paths = [str(folder/name) for name in ('Main.sldasm', 'Sub.sldasm', 'Part.sldprt', 'Part.slddrw')]
    for path in paths:
        Path(path).write_text('source fixture')
    return Snapshot(paths[0], tuple(Document(p, refs, (14, 1)) for p, refs in zip(
        paths, ((paths[1], paths[2]), (paths[2],), (), (paths[2],)))))


def values_at(destination):
    return dict(destination=str(destination), prefix='NEW-', suffix='-1', find='', replacement='',
                mode='Ön / son ek', start='1', digits='3')


@pytest.mark.parametrize('fault', ['nonempty', 'file', 'missing_parent', 'blank', 'bad_rule'])
def test_plan_keeps_all_source_rows_when_destination_or_rules_are_invalid(tmp_path, fault):
    snapshot = snapshot_at(tmp_path/'source')
    target = tmp_path/'package'
    values = values_at(target)
    if fault == 'nonempty':
        target.mkdir(); (target/'keep.txt').write_text('keep')
    elif fault == 'file': target.write_text('keep')
    elif fault == 'missing_parent': values['destination'] = str(tmp_path/'missing'/'package')
    elif fault == 'blank': values['destination'] = ''
    elif fault == 'bad_rule': values['prefix'] = 'invalid?'
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    sink = queue.Queue()
    NamingPage.prepare_plan(snapshot, values, {}, 'signature', sink, threading.Event())
    kind, payload = sink.get_nowait()
    assert kind == 'naming_plan' and payload['error']
    assert payload['signature'] == 'signature'
    assert len(payload['rows']) == len(document_rows(snapshot))
    assert {r['source'] for r in payload['rows']} == {d.path for d in snapshot.documents}
    if fault not in ('blank', 'bad_rule'):
        assert all(r['new_name'].startswith('NEW-') for r in payload['rows'])
    assert {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    assert not (tmp_path/'missing').exists()


def test_cancelled_preview_does_not_publish_rows(tmp_path):
    snapshot = snapshot_at(tmp_path/'source')
    sink = queue.Queue(); stop = threading.Event(); stop.set()
    NamingPage.prepare_plan(snapshot, values_at(tmp_path/'new'), {}, 'signature', sink, stop)
    assert sink.empty()


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(window)
    window.resize(1280, 800); window.show(); window.navigate('naming')
    yield window.pages['naming'], window
    if window.jobs.busy:
        window.jobs.cancel(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=8000)
    window.close(); window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); gc.collect()


def visible_sources(page):
    def walk(parent):
        result = []
        for row in range(page.model.rowCount(parent)):
            index = page.model.index(row, 0, parent)
            result.append(index.data(Qt.UserRole)['source'])
            result.extend(walk(index))
        return result
    from PySide6.QtCore import QModelIndex
    return set(walk(QModelIndex()))


def test_fresh_scan_with_nonempty_target_shows_files_and_editable_names(page, qtbot, tmp_path, monkeypatch):
    p, w = page
    snapshot = snapshot_at(tmp_path/'source')
    target = tmp_path/'used'; target.mkdir(); (target/'keep.txt').write_text('keep')
    p.destination.setText(str(target)); p.form.set_value('prefix', 'NEW-')
    p.handle_events([('naming_done', dict(state='scanned', snapshot=snapshot))])
    qtbot.waitUntil(lambda: not w.jobs.busy and bool(p.last_error))
    assert visible_sources(p) == {d.path for d in snapshot.documents}
    assert not p.save_button.isEnabled() and not p.valid_plan
    assert 'Hedef klasör boş olmalı' in p.status_text
    assert all(PureWindowsPath(e.destination).name.startswith('NEW-') for e in p.entries)
    p.tree.setCurrentIndex(p.proxy.index(0, 0))
    monkeypatch.setattr('modules.naming.ui.QInputDialog.getText', lambda *a, **kw: ('Renamed', True))
    p.edit_selected()
    qtbot.waitUntil(lambda: not w.jobs.busy)
    assert p.overrides[path_key(snapshot.root)] == 'Renamed'
    p.destination.setText(str(tmp_path/'new')); p.update_preview()
    qtbot.waitUntil(lambda: not w.jobs.busy and p.valid_plan)
    assert p.save_button.isEnabled() and not p.last_error
    assert PureWindowsPath(p.entries[0].destination).stem == 'Renamed'
    assert visible_sources(p) == {d.path for d in snapshot.documents}
    assert (target/'keep.txt').read_text() == 'keep' and not (tmp_path/'new').exists()


def test_new_snapshot_with_invalid_target_replaces_previous_source_rows(page, qtbot, tmp_path):
    p, w = page
    previous = snapshot_at(tmp_path/'previous')
    p.destination.setText(str(tmp_path/'new')); p.load_snapshot(previous)
    qtbot.waitUntil(lambda: not w.jobs.busy and p.valid_plan)
    p.destination.setText('')
    current = snapshot_at(tmp_path/'current')
    p.load_snapshot(current)
    qtbot.waitUntil(lambda: not w.jobs.busy and bool(p.last_error))
    assert visible_sources(p) == {d.path for d in current.documents}
    assert not visible_sources(p).intersection(d.path for d in previous.documents)
    assert not p.save_button.isEnabled()


def test_api_scan_failure_cannot_leave_previous_assembly_ready_to_save(page, qtbot, tmp_path, monkeypatch):
    p, w = page
    previous = snapshot_at(tmp_path/'previous')
    p.destination.setText(str(tmp_path/'new')); p.load_snapshot(previous)
    qtbot.waitUntil(lambda: not w.jobs.busy and p.valid_plan)
    def failed_scan(sink, stop, **kwargs):
        assert kwargs['operation'] == 'scan' and kwargs['source_path'] is None
        sink.put(('naming_done', dict(state='error', error='GetDocumentNames: test failure')))
    monkeypatch.setattr('modules.naming.ui.engine.worker', failed_scan)
    p.read_active()
    qtbot.waitUntil(lambda: not w.jobs.busy)
    assert p.snapshot is None and not p.entries and not visible_sources(p)
    assert not p.valid_plan and not p.save_button.isEnabled()
    assert 'GetDocumentNames' in p.plan_message.text() and 'GetDocumentNames' in p.status_text
