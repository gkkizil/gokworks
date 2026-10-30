"""Real Qt selection/group/export routing; native scanning is explicitly mocked."""
from dataclasses import replace
import threading
from PySide6.QtCore import Qt,QThread
from PySide6.QtWidgets import QFileDialog
from modules.dxf_dwg.sheetmetal import identity
from modules.dxf_dwg.inventory import selected_items
from .test_preview_ui import page,payload  # noqa: F401


def catalog(files):
    rows=[]
    for i,(source,body) in enumerate(((files[0],'A'),(files[0],'B'),(files[1],'Broken'))):
        rows.append(dict(source=str(source),configuration='Default',body_name=body,body_ref='persist:'+body,
            flat_ref='persist:flat-'+body if i<2 else '',flat_pattern='Flat-'+body if i<2 else '',
            sheet_id=identity(str(source),'Default',body),body_count=2 if i<2 else 1,
            material='S235JR',thickness_mm=1.5,quantity=3 if i<2 else 1,
            instances=[f'Assembly/Sub-{n}/Part-1' for n in range(3 if i<2 else 1)],
            status='pending' if i<2 else 'error',exportable=i<2,
            detail='Hazır' if i<2 else 'Flat-Pattern bulunamadı.',code=source.stem))
    return rows


def install(p,files):
    p.preview_before_export.setChecked(False)
    p.handle_events([('sheet_inventory',catalog(files)),('done',dict(state='preview',total=3))])


def test_checkboxes_grouping_preserve_exact_instance_selection(page):
    p,w,files=page;install(p,files)
    assert p.results.model.rowCount()==3 and p.results.model.columnCount()==8
    assert p.results.model.rows[0]['body_ref']!=p.results.model.rows[1]['body_ref']
    assert p.results.model.data(p.results.model.index(2,0),Qt.CheckStateRole)==Qt.Unchecked
    assert not p.results.model.setData(p.results.model.index(2,0),Qt.Checked,Qt.CheckStateRole)
    p.select_none_button.click();assert not selected_items(p.inventory,p.checked_instances)
    p.select_all_button.click();assert len(selected_items(p.inventory,p.checked_instances))==2
    p.group_instances.setChecked(False);assert p.results.model.rowCount()==7
    assert p.results.model.setData(p.results.model.index(0,0),Qt.Unchecked,Qt.CheckStateRole)
    selected=selected_items(p.inventory,p.checked_instances)
    assert selected[0]['quantity']==2 and selected[1]['quantity']==3
    p.group_instances.setChecked(True)
    assert p.results.model.data(p.results.model.index(0,0),Qt.CheckStateRole)==Qt.PartiallyChecked
    p.results.model.locked=True
    assert not p.results.model.setData(p.results.model.index(0,0),Qt.Checked,Qt.CheckStateRole)


def test_export_uses_only_checked_body_counts_without_clearing_the_inventory(page,qtbot,monkeypatch):
    p,w,files=page;p.source.setText(str(files[0].parent));p.output.setText(str(files[0].parent/'out'));install(p,files)
    p.results.model.setData(p.results.model.index(1,0),Qt.Unchecked,Qt.CheckStateRole)
    calls=[]
    def export(*args,**kwargs):
        calls.append((args,kwargs));args[4].put(('done',dict(state='completed',succeeded=1)))
    monkeypatch.setattr('gui_qt.export.export_parts',export)
    p.start_button.click();qtbot.waitUntil(lambda:not w.jobs.busy)
    assert len(calls)==1 and len(calls[0][1]['items'])==1
    assert calls[0][1]['items'][0]['body_name']=='A' and calls[0][1]['items'][0]['quantity']==3
    assert p.results.model.rowCount()==3 and not (files[0].parent/'out').exists()


def test_body_specific_result_and_preview_do_not_overwrite_a_sibling_body(page,qtbot):
    p,w,files=page;install(p,files)
    p._capture=lambda request,cache,stop:replace(payload(request.source),info=(('Gövde',request.body_name),('Adet',str(request.quantity))))
    p.results.table.selectRow(0);qtbot.waitUntil(lambda:p.preview_payload is not None and not w.jobs.busy)
    assert p.preview_request.body_name=='A'
    p.results.table.selectRow(1);qtbot.waitUntil(lambda:p.preview_payload is not None and not w.jobs.busy)
    assert p.preview_request.body_name=='B' and p.preview_request.flat_ref=='persist:flat-B'
    assert dict(p.preview_payload.info)['Gövde']=='B'
    row=dict(p.inventory[0],status='success',detail='Aktarıldı',outputs=[])
    p.handle_events([('sheet_result',row)])
    assert p.results.model.rowCount()==3
    assert [r['status'] for r in p.results.model.rows]==['success','pending','error']
    assert p.preview_request.body_name=='B'
    p.group_instances.setChecked(False)
    assert [r['status'] for r in p.results.model.rows]==['success']*3+['pending']*3+['error']


def test_active_and_file_scan_use_one_worker_and_only_verified_sheet_rows(page,qtbot,monkeypatch):
    p,w,files=page;p.preview_before_export.setChecked(False);calls=[]
    def scan(source,recursive,events,stop,**kwargs):
        calls.append((source,kwargs['mode'],QThread.currentThread() is w.thread()))
        events.put(('sheet_inventory',catalog(files)));events.put(('done',dict(state='preview',total=3)))
    monkeypatch.setattr('modules.dxf_dwg.sheetmetal.scan_sources',scan)
    p.active_scan_button.click();qtbot.waitUntil(lambda:not w.jobs.busy)
    assert calls==[('', 'active',False)] and p.results.model.rowCount()==3
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(files[0]),''))
    p.file_scan_button.click();qtbot.waitUntil(lambda:not w.jobs.busy)
    assert calls[-1]==(str(files[0]),'file',False)


def test_stop_scan_prevents_late_inventory_and_keeps_gui_responsive(page,qtbot,monkeypatch):
    p,w,files=page;p.preview_before_export.setChecked(False);entered=threading.Event()
    def scan(source,recursive,events,stop,**kwargs):
        entered.set();assert stop.wait(4)
        # Simulate a batch already on its way when the Stop click arrives.
        events.put(('sheet_inventory',catalog(files)))
        events.put(('done',dict(state='preview',total=3)))
    monkeypatch.setattr('modules.dxf_dwg.sheetmetal.scan_sources',scan)
    p.active_scan_button.click();qtbot.waitUntil(entered.is_set)
    p.stop_button.click();qtbot.waitUntil(lambda:not w.jobs.busy)
    assert p.results.model.rowCount()==0 and p.inventory is None and p.preview_pending is None


def test_empty_selection_never_starts_export_and_external_references_stay_in_scope(page,monkeypatch):
    p,w,files=page;install(p,files)
    p.source.setText(str(files[0].parent/'not-the-assembly-folder'));install(p,files)
    assert p._source_in_scope(str(files[0]))
    p.select_sheets(False);p.start_export()
    assert not w.jobs.busy and 'işaretleyin' in p.status_text


def test_csv_distinguishes_body_configuration_and_selected_occurrences(page,tmp_path):
    import csv
    p,w,files=page;install(p,files);p.group_instances.setChecked(False)
    p.results.model.setData(p.results.model.index(0,0),Qt.Unchecked,Qt.CheckStateRole)
    path=tmp_path/'sheets.csv';p.results.save_csv(path)
    with path.open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream,delimiter=';'))
    assert len(rows)==3 and rows[0]['Gövde']=='A' and rows[0]['Konfigürasyon']=='Default'
    assert rows[0]['Montaj adedi']=='3' and rows[0]['Seçili adet']=='2'
    assert rows[2]['Durum']=='Hata' and 'Flat-Pattern' in rows[2]['Açıklama']


def test_source_change_discards_stale_verified_inventory_instead_of_legacy_export(page):
    p,w,files=page;install(p,files)
    p.source.setText(str(files[0].parent/'new'))
    assert p.inventory is None and p.results.model.rowCount()==0


def test_broken_unchecked_body_cannot_block_review_of_the_checked_ready_body(page,qtbot,monkeypatch):
    p,w,files=page;p.source.setText(str(files[0].parent));install(p,files)
    p.results.table.selectRow(2);qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    p.preview_before_export.setChecked(True);p.start_export()
    qtbot.waitUntil(lambda:not w.jobs.busy and p.preview_payload is not None)
    assert p.preview_request.body_name in ('A','B') and p.preview.flat_view.isVisible()
