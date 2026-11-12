"""Native autosave policy and disk notifications cannot loop the preview."""
import threading

from modules.dxf_dwg import ui
from .test_preview_ui import page as page, payload, select


def test_real_preview_entry_explicitly_enables_silent_source_saving(page,qtbot,monkeypatch):
    p,w,files=page;calls=[]
    def capture(request,cache,stop,**kwargs):
        calls.append(kwargs);return payload(request.source)
    monkeypatch.setattr(ui,'capture',capture);p._capture=capture
    select(p,qtbot)
    assert calls and calls[0]['save_modified'] is True


def test_native_autosave_notification_during_capture_does_not_queue_another_preview(page,qtbot):
    p,w,files=page;entered=threading.Event();release=threading.Event();calls=[]
    def capture(request,cache,stop):
        calls.append(True);entered.set();release.wait(4)
        return payload(request.source)
    p._capture=capture
    p.results.table.selectRow(0)
    qtbot.waitUntil(entered.is_set,timeout=4000)
    generation=p.preview_generation
    # Deliver the same notification as QFileSystemWatcher after native Save3.
    files[0].write_text('source automatically saved while preview is reading')
    p.source_changed(str(files[0]))
    assert p.preview_generation==generation and p.preview_pending is None
    p.watcher.removePaths(p.watcher.files())  # native replace can drop the watch
    release.set()
    qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None,timeout=6000)
    p.source_changed(str(files[0]))  # a delayed duplicate for the accepted revision
    assert len(calls)==1 and p.preview_generation==generation
    assert str(files[0]) in p.watcher.files()
    assert p._flat_ready_for_export()


def test_source_edit_after_worker_snapshot_is_not_published_as_current(page,qtbot):
    p,w,files=page;select(p,qtbot)
    old=payload(str(files[0]));generation=p.preview_generation
    p.watcher.blockSignals(True)
    files[0].write_text('external save after the last native validation')
    p.process_events([('dxf_preview',(generation,old))])
    assert p.preview_payload is None and not p._flat_ready_for_export()
    assert 'eski önizleme' in p.status_text
