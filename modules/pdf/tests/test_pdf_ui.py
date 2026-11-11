"""Real Qt presentation and unchanged PDF service boundary; no live CAD."""
import csv
import gc
from pathlib import PureWindowsPath

import pytest
from PySide6.QtCore import QCoreApplication,QEvent,QThread
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import MainWindow,create_application


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([])
    w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1366,768);w.show();w.navigate('pdf')
    yield w
    if w.jobs.busy:
        w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    w.settings.flush();w.close();w.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_empty_action_only_selects_source_and_preserves_settings(window,tmp_path,monkeypatch):
    page=window.pages['pdf']
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(tmp_path))
    page.results.choose_source.click()
    assert page.source.text()==str(tmp_path)
    assert window.settings.get('pdf_source')==str(tmp_path)
    assert not window.jobs.busy
    assert page.results.choose_source.isVisible()


def test_export_uses_original_service_arguments_and_worker(window,qtbot,tmp_path,monkeypatch):
    page=window.pages['pdf'];calls=[]
    source=tmp_path/'in';source.mkdir();output=tmp_path/'out'
    page.source.setText(str(source));page.output.setText(str(output))
    page.form.set_value('recursive',False);page.form.set_value('overwrite',True)
    path=str(source/'Kapak.SLDDRW')
    def export(*args,**kwargs):
        calls.append((args[:4],kwargs,QThread.currentThread()))
        sink=args[4]
        for event in [('files',[path]),('current',path),('progress',(0,1)),
                      ('result',dict(source=path,status='success',detail='2 sayfa',output=str(output/'Kapak.pdf'))),
                      ('progress',(1,1)),('done',dict(state='completed',succeeded=1,skipped=0,failed=0))]:
            sink.put(event)
    monkeypatch.setattr('gui_qt.export.export_drawings',export)
    page.start_button.click();qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert calls[0][:2]==((str(source),str(output),False,True),{})
    assert calls[0][2] is not window.thread()
    assert page.results.metrics['success'].text()=='1'
    assert page.results.transfer_progress.value()==1
    assert page.start_button.isEnabled() and not page.stop_button.isVisible()


def test_names_are_short_but_paths_search_reports_and_identities_are_preserved(window,qtbot,tmp_path):
    page=window.pages['pdf'];panel=page.results
    paths=['C:/Üretim/A/Kapak.SLDDRW','C:/Üretim/B/Kapak.SLDDRW']
    page.handle_events([('files',paths),('result',dict(source=paths[0],status='success',detail='Tamamlandı')),
                        ('result',dict(source=paths[1],status='error',detail='Dosyayı kontrol edin'))])
    assert panel.model.rowCount()==2
    assert panel.model.index(0,0).data()==PureWindowsPath(paths[0]).name
    assert panel.model.index(0,0).data(3)==paths[0]  # Qt.ToolTipRole
    panel.search.setText('/B/');qtbot.wait(130)
    assert panel.proxy.rowCount()==1 and panel.metrics['total'].text()=='2'
    assert panel.metrics['error'].text()=='1'
    assert not panel.choose_source.isVisible()
    panel.save_csv(tmp_path/'report.csv')
    with (tmp_path/'report.csv').open(encoding='utf-8-sig') as stream:
        assert [r['Kaynak'] for r in csv.DictReader(stream,delimiter=';')]==paths
    panel.clear_button.click()
    assert panel.metrics['total'].text()=='0' and panel.choose_source.isVisible()
    assert not panel.transfer_progress.isVisible()


@pytest.mark.parametrize('theme',['dark','light'])
def test_summary_empty_copy_and_commands_fit_small_and_wide_windows(window,qtbot,theme):
    page=window.pages['pdf'];window.set_theme(theme)
    for size in ((1366,768),(820,560),(1024,700)):
        window.resize(*size);qtbot.wait(60)
        panel=page.results
        assert panel.empty_state.detail.height()>=panel.empty_state.detail.heightForWidth(panel.empty_state.detail.width())
        for widget in (*panel.metrics.values(),panel.report_menu,panel.clear_button,panel.choose_source):
            assert widget.isVisible()
            assert page.rect().contains(widget.mapTo(page,widget.rect().bottomRight()))
        assert page.source_scroll.horizontalScrollBar().maximum()==0
        assert panel.empty_state.reset.isHidden()


def test_filter_empty_busy_and_partial_states_remain_distinct(window,qtbot):
    page=window.pages['pdf'];panel=page.results
    page.handle_events([('files',['A.SLDDRW']),('result',dict(source='A.SLDDRW',status='partial',detail='Kontrol gerekli'))])
    assert '1 kısmi' in panel.stage.text()
    panel.search.setText('missing');qtbot.wait(130)
    assert panel.empty_state.reset.isVisible() and not panel.choose_source.isVisible()
    panel.clear_filters();page.set_busy(True)
    assert not panel.clear_button.isEnabled() and panel.transfer_progress.maximum()==0
    page.progressChanged.emit(1,3)
    assert panel.transfer_progress.maximum()==3 and panel.transfer_progress.value()==1
    page.set_busy(False)
    assert panel.clear_button.isEnabled()
