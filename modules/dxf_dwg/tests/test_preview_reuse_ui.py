"""Selection reuses snapshots; background export events never start CAD reads."""
from dataclasses import replace
import threading

from PySide6.QtCore import Qt

from .test_preview_ui import page, payload, select  # noqa: F401
from .test_sheet_inventory_ui import install


def test_returning_to_a_part_displays_mesh_and_flat_without_another_capture(page,qtbot):
    p,w,files=page;calls=[]
    p._capture=lambda request,cache,stop:calls.append(request.source) or payload(request.source)
    select(p,qtbot,0);select(p,qtbot,1)
    p.results.table.selectRow(0)
    assert p.preview_payload is not None and p.preview_payload.source==str(files[0])
    assert p.preview.mesh_view.mesh and p.preview.flat_view.scene().items()
    qtbot.wait(250)
    assert calls==[str(files[0]),str(files[1])] and not w.jobs.busy


def test_same_file_different_bodies_have_separate_previews_and_refresh_is_explicit(page,qtbot):
    p,w,files=page;install(p,files);calls=[]
    def capture(request,cache,stop):
        calls.append(request.body_ref)
        return replace(payload(request.source),info=(('Gövde',request.body_name),))
    p._capture=capture
    select(p,qtbot,0);select(p,qtbot,1);select(p,qtbot,0)
    assert calls==['persist:A','persist:B'] and dict(p.preview_payload.info)['Gövde']=='A'
    p.preview.refresh_button.click()
    qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    assert calls==['persist:A','persist:B','persist:A']


def test_export_row_updates_do_not_start_a_background_preview(page,qtbot):
    p,w,files=page;install(p,files);select(p,qtbot,0);calls=[]
    p._capture=lambda request,cache,stop:calls.append(request) or payload(request.source)
    p.handle_events([('sheet_result',dict(p.inventory[0],status='success',detail='exported',
        update_stamp=27,outputs=[dict(format='DXF',path=str(files[0].with_suffix('.dxf')),status='success')]))])
    qtbot.wait(250)
    assert not calls and p.preview_pending is None and not w.jobs.busy


def test_selection_during_export_cannot_queue_new_native_work(page,qtbot):
    p,w,files=page;calls=[];entered=threading.Event();release=threading.Event()
    p._capture=lambda request,cache,stop:calls.append(request) or payload(request.source)
    def export(sink,stop):entered.set();release.wait(3)
    w.jobs.start(p,export);qtbot.waitUntil(entered.is_set)
    p.results.table.selectRow(1);qtbot.wait(220)
    assert p.preview_pending is None
    release.set();qtbot.waitUntil(lambda:not w.jobs.busy);qtbot.wait(250)
    assert not calls
    p.preview_button.click();qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    assert len(calls)==1 and p.preview_payload.source==str(files[1])


def test_stopped_same_selection_can_be_opened_again(page,qtbot):
    p,w,files=page;select(p,qtbot)
    index=p.results.proxy.index(0,1)
    p.results.table.setCurrentIndex(index)
    p.cancel_pending_preview();p.resume_preview()
    qtbot.mouseClick(p.results.table.viewport(),Qt.LeftButton,pos=p.results.table.visualRect(index).center())
    qtbot.waitUntil(lambda:p.preview_payload is not None and not p._preview_cancelled and not w.jobs.busy)
    assert p.preview.flat_view.scene().items()


def test_cached_view_is_validated_again_before_reviewed_export(page,qtbot,monkeypatch):
    p,w,files=page
    p.source.setText(str(files[0].parent));p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files]);captures=[];exports=[]
    p._capture=lambda request,cache,stop:captures.append(request.source) or payload(request.source)
    def export(*args,**kwargs):
        exports.append(True);args[4].put(('done',dict(state='completed',succeeded=1)))
    monkeypatch.setattr('gui_qt.export.export_parts',export)
    select(p,qtbot,0);select(p,qtbot,1);select(p,qtbot,0)
    assert len(captures)==2
    p.start_button.click()
    qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    assert len(captures)==3 and not exports
    p.start_button.click();qtbot.waitUntil(lambda:not w.jobs.busy and bool(exports))


def test_changed_source_cannot_reuse_an_old_preview(page,qtbot):
    p,w,files=page;calls=[]
    p._capture=lambda request,cache,stop:calls.append(request.source) or payload(request.source)
    select(p,qtbot,0);select(p,qtbot,1)
    files[0].write_text('changed source geometry')
    select(p,qtbot,0)
    assert calls==[str(files[0]),str(files[1]),str(files[0])]


def test_clicking_current_part_detects_saved_change_before_watcher_delivery(page,qtbot):
    p,w,files=page;calls=[]
    p._capture=lambda request,cache,stop:calls.append(request.source) or payload(request.source)
    select(p,qtbot)
    p.watcher.blockSignals(True);files[0].write_text('new geometry before watcher delivery')
    index=p.results.proxy.index(0,1)
    qtbot.mouseClick(p.results.table.viewport(),Qt.LeftButton,pos=p.results.table.visualRect(index).center())
    qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    assert calls==[str(files[0]),str(files[0])]
