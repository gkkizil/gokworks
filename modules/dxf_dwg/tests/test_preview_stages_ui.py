"""One worker capture; provisional flats never approve a production export."""
import threading
from dataclasses import replace

import pytest

from modules.cad_converter.api import ApiError, RestoreError
from modules.cad_converter.models import Cancelled
from .test_preview_ui import page as page, payload, select


@pytest.mark.parametrize('outcome', ['success', 'error', 'cancel', 'restore_error'])
def test_default_reader_shows_flat_while_mesh_waits_and_clears_it_on_failure(page, qtbot, monkeypatch, outcome):
    from modules.dxf_dwg import ui
    p, window, files = page
    release, calls, threads = threading.Event(), [], []
    def reader(request, cache, stop, *, on_flat, save_modified=False):
        assert save_modified is True
        calls.append(request)
        result = payload(request.source)
        on_flat(result.flat)
        assert release.wait(5)
        if outcome == 'error': raise ApiError('geometry changed')
        if outcome == 'cancel': raise Cancelled()
        if outcome == 'restore_error': raise RestoreError('restore failed')
        return replace(result, timings=(('açınım', .1), ('3D', .2), ('bilgiler', .05), ('toplam', .35)))
    monkeypatch.setattr(ui, 'capture', reader)
    p._capture = reader
    original = p.preview.show_pending_flat
    def display(flat):
        threads.append(threading.get_ident())
        original(flat)
    p.preview.show_pending_flat = display
    p.results.table.selectRow(0)
    qtbot.waitUntil(lambda: bool(p.preview.flat_view.scene().items()), timeout=4000)
    try:
        assert p.preview_payload is None and p.preview.mesh_view.mesh is None
        assert not p._flat_ready_for_export() and not p.preview_snapshots.items
        assert threads == [threading.get_ident()]
        assert len(calls) == 1
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=5000)
    if outcome == 'success':
        assert p.preview_payload.flat and p.preview.mesh_view.mesh
        assert p.preview_snapshots.items
        assert 'açınım: 0.10 sn' in p.results.log.toPlainText()
    else:
        assert p.preview_payload is None and not p.preview.flat_view.scene().items()
        assert not p.preview_snapshots.items
        assert p._preview_restore_failed == (outcome == 'restore_error')


def test_stop_button_clears_provisional_flat_after_native_cleanup_and_does_not_restart(page, qtbot, monkeypatch):
    from modules.dxf_dwg import ui
    p, window, _ = page
    calls = []
    def reader(request, cache, stop, *, on_flat, save_modified=False):
        assert save_modified is True
        calls.append(request)
        on_flat(payload(request.source).flat)
        assert stop.wait(5)
        raise Cancelled()
    monkeypatch.setattr(ui, 'capture', reader)
    p._capture = reader
    p.results.table.selectRow(0)
    qtbot.waitUntil(lambda: bool(p.preview.flat_view.scene().items()), timeout=4000)
    p.stop_button.click()
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=5000)
    assert not p.preview.flat_view.scene().items() and p.preview_payload is None
    assert p.preview_pending is None and not p._flat_ready_for_export()
    qtbot.wait(250)
    assert len(calls) == 1 and 'durduruldu' in p.preview.message.text()


def test_stale_flat_event_cannot_repaint_another_body(page):
    p, _, files = page
    p.request_preview(dict(source=str(files[1])), read=False)
    current = p.preview_generation
    p.handle_events([('dxf_preview_flat', (current-1, payload(files[0]).flat))])
    assert not p.preview.flat_view.scene().items() and p.preview_payload is None
    p.handle_events([('dxf_preview_flat', (current, payload(files[1]).flat))])
    assert p.preview.flat_view.scene().items() and p.preview_payload is None
    p.clear_preview()
    assert not p.preview.flat_view.scene().items()


def test_same_immutable_payload_retains_scene_camera_and_mesh_render(page, qtbot):
    p, _, _ = page
    select(p, qtbot)
    panel, result = p.preview, p.preview_payload
    item = panel.flat_view.scene().items()[0]
    generation = panel.mesh_view.generation
    panel.flat_view.scale(1.5, 1.5)
    transform = panel.flat_view.transform()
    panel.show_payload(result)
    assert panel.flat_view.scene().items()[0] is item
    assert panel.flat_view.transform() == transform and panel.mesh_view.generation == generation
    panel.clear()
    assert not panel.flat_view.scene().items() and panel.mesh_view.mesh is None
