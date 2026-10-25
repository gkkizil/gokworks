import gc
import threading

import pytest
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QDialog

from gui_qt.app import MainWindow,create_application
from modules.profile_cutting.models import Demand,Project,ScanResult
from modules.profile_cutting.scanner import scan as real_scan
from modules.profile_cutting.dialogs import RowDialog,MappingDialog
from .fakes import Model,Folder,factory


@pytest.fixture
def page(qtbot,tmp_path):
    create_application([])
    w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1440,900);w.show();w.navigate('profile_cutting')
    yield w.pages['profile_cutting'],w
    if w.jobs.busy:
        w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def setup_scan(monkeypatch,tmp_path):
    model=Model(tmp_path/'frame.SLDPRT',[Folder()])
    session,make=factory([model],model)
    calls=[]
    def operation(path,options,mapping,events,stop):
        calls.append((threading.get_ident(),path))
        return real_scan(options=options,mapping=mapping,events=events,stop=stop,session_factory=make)
    monkeypatch.setattr('modules.profile_cutting.ui.scan',operation)
    return calls


def test_read_review_transfer_optimize_and_repeat_preserve_manual_rows(page,qtbot,tmp_path,monkeypatch):
    p,w=page;calls=setup_scan(monkeypatch,tmp_path)
    p.project.demands=[Demand('manual','50×30×2','S355JR','1200',2)];p.refresh_demands()
    p.tabs.setCurrentIndex(1);p.scan_button.click()
    qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert calls[0][0]!=threading.get_ident()
    assert p.scan_model.rowCount()==1 and p.scan_result.rows[0].ready
    p.transfer_button.click()
    assert p.demand_model.rowCount()==2 and p.project.demands[0].id=='manual'
    p.transfer_button.click();assert len(p.project.demands)==2 and 'tekrar aktarılmadı' in p.status_text
    p.run_button.click();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert p.plan and sum(len(b.cuts) for b in p.plan.bars)==3
    assert p.plan_model.rowCount()==2 and p.diagram.vector.tagged['stock']
    p.form.set_value('kerf','4')
    assert p.plan is None and p.plan_model.rowCount()==0


def test_source_file_picker_and_refresh_use_same_source(page,qtbot,tmp_path,monkeypatch):
    p,w=page;calls=setup_scan(monkeypatch,tmp_path)
    source=str(tmp_path/'frame.SLDPRT')
    monkeypatch.setattr('modules.profile_cutting.ui.QFileDialog.getOpenFileName',lambda *args:(source,''))
    p.file_button.click();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    p.refresh_button.click();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert [path for _,path in calls]==[source,source]


def test_cell_edits_validate_numbers_and_require_review_before_import(page,qtbot,tmp_path,monkeypatch):
    p,w=page;setup_scan(monkeypatch,tmp_path)
    p.start_scan(None);qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert p.scan_model.setData(p.scan_model.index(0,3),'bad',Qt.EditRole)
    assert p.scan_result.rows[0].length=='1000' and 'Boy' in p.status_text
    assert p.scan_model.setData(p.scan_model.index(0,3),'950',Qt.EditRole)
    assert not p.scan_result.rows[0].ready
    p.import_scan();assert not p.project.demands
    row=p.scan_result.rows[0]
    dialog=RowDialog(p,row);qtbot.addWidget(dialog)
    dialog.form.set_value('confirmed',True);dialog.form.set_value('note','Ham stok boyu ölçülerek doğrulandı.')
    dialog.check();assert dialog.result()==QDialog.Accepted and dialog.value.ready
    p.scan_result.rows[0]=dialog.value;p.import_scan()
    assert p.project.demands[0].length=='950'


def test_mapping_dialog_does_not_apply_cancelled_changes(page,qtbot):
    p,_=page;before=p.mapping['length'][:]
    dialog=MappingDialog(p);qtbot.addWidget(dialog)
    dialog.form.set_value('length','MY-LENGTH');dialog.reject()
    assert p.mapping['length']==before
    dialog=MappingDialog(p);qtbot.addWidget(dialog)
    dialog.form.set_value('length','MY-LENGTH');dialog.check()
    assert dialog.mapping['length']==['MY-LENGTH']


def test_refresh_with_changed_source_invalidates_plan_before_import_button(page,qtbot,tmp_path,monkeypatch):
    p,w=page;setup_scan(monkeypatch,tmp_path)
    p.start_scan(None);qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    p.import_scan();p.calculate();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert p.plan
    p.scan_result.rows[0].length='1200'
    p.handle_events([('weldment_scan',p.scan_result)])
    assert p.plan is None and p.project.demands[0].source_changed
    assert 'değişmiş kaynak' in p.demand_summary.text()
    p.calculate();assert not w.jobs.busy and 'kaynak verisi' in p.status_text


def test_review_filter_and_failed_refresh_do_not_allow_stale_import(page,qtbot,tmp_path,monkeypatch):
    p,w=page;setup_scan(monkeypatch,tmp_path)
    p.start_scan(None);qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    p.status_filter.setCurrentText('Hazır');assert p.scan_proxy.rowCount()==1
    p.status_filter.setCurrentText('Hariç');assert p.scan_proxy.rowCount()==0
    def failure(*args):raise RuntimeError('Bağlantı koptu')
    monkeypatch.setattr('modules.profile_cutting.ui.scan',failure)
    p.refresh_scan();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert p.scan_result and not p.scan_current
    p.import_scan();assert not p.project.demands and 'Verileri yenile' in p.status_text


def test_report_uses_snapshot_on_worker_and_writes_local_csv(page,qtbot,tmp_path,monkeypatch):
    p,w=page;p.project.demands=[Demand('manual','40×40×2','S235JR','1000',2)];p.refresh_demands()
    path=tmp_path/'cuts.csv'
    monkeypatch.setattr('modules.profile_cutting.ui.QFileDialog.getSaveFileName',lambda *args:(str(path),''))
    p.report();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert path.is_file() and 'GOKWORKS' in path.read_text(encoding='utf-8-sig')
    assert 'kaydedildi' in p.status_text


def test_navigation_remains_responsive_while_scan_is_running(page,qtbot,monkeypatch):
    p,w=page;started=threading.Event()
    def operation(path,options,mapping,events,stop):
        started.set();stop.wait(3)
    monkeypatch.setattr('modules.profile_cutting.ui.scan',operation)
    p.start_scan(None);qtbot.waitUntil(started.is_set)
    assert not p.scan_button.isEnabled() and p.stop_button.isVisible()
    w.navigate('weight');assert w.pages['weight'].isVisible()
    w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=6000)
    assert p.scan_button.isEnabled()


def test_failed_scan_shows_the_actual_cause_and_plain_details(page,monkeypatch):
    p,_=page;message='FeatureManager ağacında yinelenen/döngüsel unsur bulundu.'
    result=ScanResult('Şase.SLDPRT','Default<As Machined>',
        diagnostics=[dict(source='Şase.SLDPRT',configuration='Default<As Machined>',detail=message)],unscanned=1)
    p.handle_events([('weldment_scan',result)])
    assert message in p.status_text and '1 belge okunamadı' in p.status_text
    assert p.status.property('role')=='error' and p.scan_model.rowCount()==0
    shown=[]
    monkeypatch.setattr('modules.profile_cutting.ui.show_details',lambda *args:shown.append(args[-1]))
    p.scan_details()
    assert shown==[f'Şase.SLDPRT [Default<As Machined>]\n{message}']


def test_empty_cutlist_does_not_display_a_success_message(page):
    p,_=page;p.handle_events([('weldment_scan',ScanResult('Şase.SLDPRT','Default',scanned_parts=1))])
    assert 'Cut List bulunamadı' in p.status_text and p.status.property('role')=='error'


@pytest.mark.parametrize('theme',['dark','light'])
def test_all_tabs_fit_small_and_wide_windows_without_forcing_app_height(page,qtbot,theme):
    p,w=page;w.set_theme(theme)
    for size in ((820,560),(1024,700),(1440,900)):
        w.resize(*size);qtbot.wait(30)
        for index in range(3):
            p.tabs.setCurrentIndex(index);qtbot.wait(20)
            assert w.width()==size[0] and w.height()==size[1],(size,w.size())
            assert p.rect().contains(p.run_button.mapTo(p,p.run_button.rect().bottomRight()))
            assert p.tabs.isVisible() and not w.grab().isNull()
            if index==1:
                scroller=p.tabs.widget(1);scroller.verticalScrollBar().setValue(0)
                qtbot.wait(20)
                for control in p.source_actions:
                    assert scroller.viewport().rect().contains(control.mapTo(scroller.viewport(),control.rect().bottomRight())),control.text()
                assert scroller.horizontalScrollBar().maximum()==0
                if size[0]==1440:
                    header=p.scan_view.horizontalHeader()
                    assert header.length() <= p.scan_view.viewport().width()
