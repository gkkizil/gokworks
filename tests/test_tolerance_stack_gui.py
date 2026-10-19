from dataclasses import replace
from pathlib import Path
import threading
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt,QThread,QTimer
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox

from gui_qt.app import MainWindow,create_application
from gui_qt.pages.stack_dialogs import DimensionDialog,IsoPairDialog
from tolerance_stack.models import manual_dimension
from tolerance_stack.calculator import Cancelled
from tolerance_stack import solidworks_reader as reader
from test_tolerance_stack_com import Drawing


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');w.resize(1440,950)
    qtbot.addWidget(w);w.show();w.navigate('tolerance_stack')
    yield w
    if w.jobs.busy:w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=10000)
    w.close()


def compute(page,window,qtbot):
    page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest
    page.calculate_button.click()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=10000)
    assert page.result is not None,page.status_text


def test_module_example_complete_analysis_and_edit_invalidates_every_result(window,qtbot):
    page=window.pages['tolerance_stack'];page.load_example();compute(page,window,qtbot)
    assert str(page.result.minimum)=='0.02' and str(page.result.maximum)=='0.38'
    assert page.metric_model.rowCount()>20 and page.chain_diagram.scene().items()
    assert page.contribution_diagram.scene().items()
    page.copy_result();assert '0,020000' in QApplication.clipboard().text()
    page.form.set_value('acceptance_max','.3')
    assert page.result is None and not page.confirm_box.isChecked() and page.metric_model.rowCount()==0
    compute(page,window,qtbot);assert page.result.worst_case_pass is False
    page.confirm_box.setChecked(False);assert page.result is None


def test_chain_reorder_remove_relink_and_duplicate_are_user_controlled(window):
    page=window.pages['tolerance_stack'];page.load_example();page.chain_table.selectRow(1);page.move_term(-1)
    page.confirm_box.setChecked(True)
    assert not page.confirm_box.isChecked() and 'süreksiz' in page.status_text
    page.relink();page.confirm_box.setChecked(True);assert page.project.confirmed_digest
    page.chain_table.selectRow(1);page.remove_term();page.relink();page.confirm_box.setChecked(True)
    assert len(page.project.terms)==2 and page.project.confirmed_digest
    duplicate=page.project.terms[0].dimension_id
    row=next(i for i in range(page.library_proxy.rowCount()) if page.library_proxy.index(i,0).data(Qt.UserRole)['id']==duplicate)
    page.library.selectRow(row);page.add_selected(1);page.confirm_box.setChecked(True)
    assert not page.confirm_box.isChecked() and 'iki kez' in page.status_text


def test_native_manual_limits_units_and_iso_pair_editors(window):
    page=window.pages['tolerance_stack'];dialog=DimensionDialog(page)
    for key,value in dict(name='Inch part',unit='in',mode='Alt / üst ölçü limiti',nominal='1',lower='.99',upper='1.01').items():dialog.form.set_value(key,value)
    dimension=dialog.read_value()
    assert float(dimension.nominal)==25.4 and float(dimension.lower)==-.254 and float(dimension.upper)==.254
    iso=IsoPairDialog(page);iso.form.set_value('relation','Radyal boşluk (D−d)/2')
    hole,shaft,factor,relation=iso.read_value()
    assert str(factor)=='0.5' and hole.kind==shaft.kind=='diameter'
    page.project.dimensions.extend((hole,shaft));page.append_dimension(hole,1,factor=factor,relation=relation)
    page.append_dimension(shaft,-1,factor=factor,relation=relation);page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest
    dialog.deleteLater();iso.deleteLater()


def test_library_filter_search_and_numeric_sort_do_not_create_row_widgets(window):
    page=window.pages['tolerance_stack']
    page.project.dimensions=[manual_dimension('Part '+str(value),value,'-.1','.1') for value in (100,2,10)]
    page.refresh();page.library.sortByColumn(1,Qt.AscendingOrder)
    assert [page.library_proxy.index(i,1).data(Qt.UserRole+1) for i in range(3)]==[2.,10.,100.]
    page.search.setText('Part 10');assert page.library_proxy.rowCount()==2
    page.filter.setCurrentText('Eksik tolerans');assert page.library_proxy.rowCount()==0
    page.project.dimensions.append(replace(page.project.dimensions[0],id='missing',name='Part 101',lower=None))
    page.refresh();assert page.library_proxy.rowCount()==1


def test_multi_source_scan_runs_off_gui_thread_and_retains_chain_identity(window,qtbot,tmp_path):
    page=window.pages['tolerance_stack'];path=tmp_path/'a.SLDDRW';path.write_bytes(b'first drawing')
    drawing=Drawing(path);dims,s=reader.read_document(drawing);threads=[]
    def read(paths,**kwargs):threads.append(QThread.currentThread());return dims,[s]
    with patch.object(QFileDialog,'getOpenFileNames',return_value=([str(path)],'')):page.choose_sources()
    with patch.object(reader,'read_sources',side_effect=read):
        page.scan_button.click();qtbot.waitUntil(lambda:not window.jobs.busy)
    assert len(page.project.dimensions)==1 and threads[0] is not window.thread()
    page.library.selectRow(0);page.add_selected(1)
    changed=replace(dims[0],nominal=dims[0].nominal+1,original_signature='changed')
    page.merge_sources([changed],[s])
    assert page.project.terms[0].dimension_id==changed.id
    assert page.project.dimensions[0].nominal==51 and not page.confirm_box.isChecked()


def test_changed_disk_source_removes_visible_results_without_blocking_gui(window,qtbot,tmp_path):
    page=window.pages['tolerance_stack'];page.load_example();compute(page,window,qtbot)
    path=tmp_path/'part.SLDDRW';path.write_bytes(b'before')
    from tolerance_stack.storage import fingerprint
    page.project.sources=[fingerprint(path)];page.watch_sources()
    path.write_bytes(b'after')
    qtbot.waitUntil(lambda:page.result is None)
    assert 'yeniden tarayın' in page.status_text


def test_project_save_load_marks_archive_historical_and_exports_real_reports(window,qtbot,tmp_path):
    page=window.pages['tolerance_stack'];page.load_example();compute(page,window,qtbot)
    path=tmp_path/'project.json'
    with patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'')):
        page.save_project();qtbot.waitUntil(lambda:not window.jobs.busy)
    assert path.exists() and not page.dirty
    for kind in ('pdf','xlsx'):
        output=tmp_path/('report.'+kind)
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(output),'')):
            page.export_report(kind);qtbot.waitUntil(lambda:not window.jobs.busy)
        assert output.exists() and output.stat().st_size>1000,page.status_text
    with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')):
        page.open_project();qtbot.waitUntil(lambda:not window.jobs.busy)
    assert page.result is None and not page.project.confirmed_digest
    assert 'Eski sonuç güncel sayılmaz' in page.status_text


def test_source_save_is_not_called_when_explicit_user_confirmation_is_denied(window,qtbot,tmp_path):
    page=window.pages['tolerance_stack'];page.load_example();compute(page,window,qtbot)
    page.target.setText(str(tmp_path/'source.SLDDRW'));page.output_mode.setCurrentIndex(3)
    with patch.object(QMessageBox,'question',return_value=QMessageBox.No),patch('gui_qt.pages.tolerance_stack.drawing_writer.write_drawing') as write:
        page.export_drawing();assert not window.jobs.busy;write.assert_not_called()
    page.output_mode.setCurrentIndex(1)
    with patch('gui_qt.pages.tolerance_stack.drawing_writer.write_drawing',return_value=dict(path=page.target.text(),mode='memory',saved=False,backup=None)) as write:
        page.export_drawing();qtbot.waitUntil(lambda:not window.jobs.busy)
    assert write.call_args.kwargs['approved'] is False
    assert 'çizim kaydedilmedi' in page.status_text


def test_calculation_worker_cancellation_keeps_navigation_and_qt_events_responsive(window,qtbot):
    page=window.pages['tolerance_stack'];page.load_example();page.confirm_box.setChecked(True);started=threading.Event()
    def calculate(*args,stop,**kwargs):
        assert QThread.currentThread() is not window.thread();started.set();stop.wait(3);raise Cancelled('Durduruldu')
    with patch('gui_qt.pages.tolerance_stack.calculate',side_effect=calculate):
        page.start_calculation();qtbot.waitUntil(started.is_set)
        window.navigate('bolt');assert window.stack.currentWidget() is window.pages['bolt']
        fired=[];QTimer.singleShot(0,lambda:fired.append(True));qtbot.waitUntil(lambda:bool(fired))
        window.jobs.cancel();qtbot.waitUntil(lambda:not window.jobs.busy)
    assert page.result is None and 'Durduruldu' in page.status_text


@pytest.mark.parametrize('theme',['dark','light'])
@pytest.mark.parametrize('size',[(1024,700),(1366,768),(1920,1080)])
def test_stack_workspaces_remain_usable_in_both_themes_and_sizes(window,theme,size):
    window.resize(*size);window.set_theme(theme);page=window.pages['tolerance_stack'];page.load_example()
    for i in range(page.tabs.count()):
        page.tabs.setCurrentIndex(i);QApplication.processEvents()
        assert page.width()>=550 and page.tabs.width()>300
        assert window.stack.geometry().right()<window.width()
        assert page.library.viewport().height()>=120
        assert page.chain_table.viewport().height()>=100
