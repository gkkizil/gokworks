from dataclasses import replace
from pathlib import Path
import threading
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt,QThread,QTimer
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox

from gui_qt.app import MainWindow,create_application
from gui_qt.pages.stack_dialogs import DimensionDialog,IsoPairDialog,TermDialog
from tolerance_stack.models import manual_dimension
from tolerance_stack.calculator import Cancelled
from tolerance_stack import solidworks_reader as reader
from test_tolerance_stack_com import Drawing,Display,Dimension,Tolerance


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
    assert [(t.start,t.end) for t in page.project.terms]==[('P0','P1'),('P1','P2'),('P2','P3')]
    assert [t.direction for t in page.project.terms]==[-1,1,-1]
    assert not page.confirm_box.isChecked()
    page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest
    page.chain_table.selectRow(1);page.remove_term();page.confirm_box.setChecked(True)
    assert len(page.project.terms)==2 and page.project.confirmed_digest
    duplicate=page.project.terms[0].dimension_id
    row=next(i for i in range(page.library_proxy.rowCount()) if page.library_proxy.index(i,0).data(Qt.UserRole)['id']==duplicate)
    page.library.selectRow(row);page.add_selected(1)
    assert len(page.project.terms)==2 and 'iki kez' in page.status_text


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


def test_reference_with_missing_values_can_be_confirmed_and_added_without_cad_edits(window,tmp_path):
    from tolerance_stack.calculator import calculate
    from tolerance_stack.storage import save_project,load_project
    path=tmp_path/'Referans.SLDDRW';path.write_bytes(b'untouched drawing')
    drawing=Drawing(path)
    display=Display(Dimension(tolerance=Tolerance(kind=2,status=1)),reference=True)
    display.dimension.GetSystemValue3=lambda *args:None
    drawing.groups[0][0].displays=[display]
    dimensions,source=reader.read_document(drawing)
    original=dimensions[0]
    assert original.kind=='reference' and original.geometry_kind=='linear' and original.nominal is None
    page=window.pages['tolerance_stack'];page.project.dimensions=dimensions;page.project.sources=[source]
    page.refresh();page.library.selectRow(0)
    native_exec=DimensionDialog.exec
    def confirm(dialog):
        def complete():
            assert not dialog.form.fields['kind'].isEnabled()
            for key,value in dict(nominal='50',lower='-0,1',upper='0,1').items():dialog.form.set_value(key,value)
            with pytest.raises(ValueError,match='doğrulayın'):dialog.read_value()
            dialog.form.set_value('reference_confirmed',True)
            dialog.submit()
        QTimer.singleShot(0,complete)
        return native_exec(dialog)
    with patch.object(DimensionDialog,'exec',confirm):page.add_selected(1)
    assert len(page.project.terms)==1
    d=page.project.dimensions[0]
    assert (d.kind,d.geometry_kind,d.provenance)==('linear','linear','manual_override')
    assert d.tolerance_type=='Manuel · Alt / üst sapma'
    assert d.id==original.id and d.original_signature==original.original_signature
    assert d.source==original.source and d.configuration==original.configuration
    page.project.terms[0]=replace(page.project.terms[0],relation='Çizim X → montaj X; datum A')
    page.project.method='worst_case';page.project.confirm()
    with patch.object(reader,'read_sources',return_value=(dimensions,[source])):reader.verify_live(page.project)
    result=calculate(page.project)
    assert (float(result.minimum),float(result.maximum))==(49.9,50.1)
    project_file=tmp_path/'reference.gokstack.json'
    save_project(page.project,project_file)
    loaded,_=load_project(project_file)
    assert loaded.dimensions==page.project.dimensions
    assert not loaded.confirmed_digest
    assert path.read_bytes()==b'untouched drawing' and drawing.dirty is False


def test_cancel_reference_completion_does_not_add_to_chain(window):
    page=window.pages['tolerance_stack']
    d=replace(manual_dimension('Ref','50','-.1','.1'),kind='reference',geometry_kind='linear')
    page.project.dimensions=[d];page.refresh();page.library.selectRow(0)
    native_exec=DimensionDialog.exec
    def cancel(dialog):
        QTimer.singleShot(0,dialog.reject)
        return native_exec(dialog)
    with patch.object(DimensionDialog,'exec',cancel):page.add_selected(1)
    assert page.project.terms==[] and page.project.dimensions==[d]


@pytest.mark.parametrize('geometry',['angle','arc','chamfer','unknown',''])
def test_reference_angle_or_unverified_geometry_cannot_be_disguised_as_linear(window,geometry):
    page=window.pages['tolerance_stack']
    d=replace(manual_dimension('Ref','50','-.1','.1'),kind='reference',geometry_kind=geometry)
    dialog=DimensionDialog(page,d);dialog.form.set_value('reference_confirmed',True)
    with pytest.raises(ValueError,match='geometrik türü'):dialog.read_value()
    page.project.dimensions=[d];page.refresh();page.library.selectRow(0)
    with patch('gui_qt.pages.tolerance_stack.show_details') as details:
        page.add_selected(1);assert details.called
    assert not page.project.terms
    dialog.deleteLater()


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
    with patch.object(QFileDialog,'getOpenFileNames',return_value=([str(path)],'')),patch.object(reader,'read_sources',side_effect=read):
        page.choose_button.click();qtbot.waitUntil(lambda:not window.jobs.busy)
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
    page.tabs.setCurrentIndex(0);QApplication.processEvents()
    assert page.calculate_button.isVisible()
    point=page.calculate_button.mapTo(window,page.calculate_button.rect().bottomRight())
    assert window.rect().contains(point)


def test_drawing_linear_chain_needs_one_explicit_alignment_confirmation_without_free_text(window):
    from decimal import Decimal
    from tolerance_stack.calculator import calculate
    from tolerance_stack.chain import ChainIssue
    page=window.pages['tolerance_stack']
    a=manual_dimension('RD3@Görünüm1@Parça.Drawing','53.5','-.1','.1',source='Parça.SLDDRW')
    b=manual_dimension('RD4@Görünüm1@Parça.Drawing','1.5','-.05','.05',source='Parça.SLDDRW')
    page.project.dimensions=[a,b];page.project.method='worst_case'
    page.append_dimension(a,1);page.append_dimension(b,-1)
    assert page.current_issue is None
    assert not any(t.alignment_confirmed or t.relation for t in page.project.terms)
    with pytest.raises(ChainIssue):calculate(page.project)
    page.start_calculation()
    assert not window.jobs.busy and page.current_issue.target=='confirm'
    page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest and all(t.alignment_confirmed for t in page.project.terms)
    assert all(t.relation=='' for t in page.project.terms)
    result=calculate(page.project)
    assert (result.nominal,result.minimum,result.maximum)==tuple(map(Decimal,('52.0','51.85','52.15')))
    page.chain_table.selectRow(1);page.flip_term()
    assert not page.confirm_box.isChecked() and not page.project.confirmed_digest
    assert page.project.terms[1].direction==1 and '55' in page.formula.text()


def test_missing_tolerance_fix_opens_the_correct_measurement_even_after_filtering(window):
    page=window.pages['tolerance_stack'];page.load_example()
    missing=replace(page.project.dimensions[1],lower=None)
    page.project.dimensions[1]=missing;page.refresh()
    assert page.current_issue.target=='dimension' and page.current_issue.term_index==1
    assert 'L2' in page.review_text.text() and 'eksik' in page.review_text.text()
    page.search.setText('A');edited=[]
    with patch.object(page,'edit_dimension',side_effect=lambda:edited.append(page.selected_dimension().id)):
        page.fix_button.click()
    assert edited==[missing.id] and page.chain_index()==1


def test_custom_point_connections_are_not_silently_changed_by_reordering(window):
    page=window.pages['tolerance_stack'];page.load_example()
    page.project.terms[0]=replace(page.project.terms[0],end='Yüzey B')
    page.project.terms[1]=replace(page.project.terms[1],start='Yüzey B')
    original=page.project.terms[1]
    page.refresh();page.chain_table.selectRow(1);page.move_term(-1)
    assert page.project.terms[0]==original and page.current_issue.target=='relink'
    page.confirm_box.setChecked(True);assert not page.confirm_box.isChecked()
    page.fix_button.click();page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest


def test_alignment_checkbox_does_not_override_different_axes_or_diameter_relationship(window):
    page=window.pages['tolerance_stack'];page.load_example()
    page.project.terms[0]=replace(page.project.terms[0],axis='Y');page.refresh()
    page.confirm_box.setChecked(True)
    assert not page.confirm_box.isChecked() and page.current_issue.target=='term'
    assert page.project.terms[0].axis=='Y' and not page.project.terms[0].alignment_confirmed
    dialog=TermDialog(page,page.project.terms[0],page.project.dimensions[0])
    assert dialog.frame_section.toggle.isChecked();dialog.deleteLater()
    page.project.terms[0]=replace(page.project.terms[0],axis='X')
    page.project.dimensions[0]=replace(page.project.dimensions[0],kind='diameter');page.refresh()
    page.confirm_box.setChecked(True)
    assert not page.confirm_box.isChecked() and page.current_issue.target=='term'
    dialog=TermDialog(page,page.project.terms[0],page.project.dimensions[0])
    with pytest.raises(ValueError,match='seçin'):dialog.read_value()
    dialog.form.set_value('use','Çaptan yarıçap mesafesi (×0,5)')
    term=dialog.read_value();assert str(term.factor)=='0.5' and term.relation
    page.project.terms[0]=term;page.refresh();page.confirm_box.setChecked(True)
    assert page.project.confirmed_digest;dialog.deleteLater()


def test_basic_settings_are_visible_and_advanced_settings_remain_available(window):
    page=window.pages['tolerance_stack'];page.load_example();page.acceptance_button.click()
    assert page.tabs.currentIndex()==1
    assert page.form.fields['acceptance_min'].isVisible() and page.form.fields['acceptance_max'].isVisible()
    assert not page.form.fields['axis'].isVisible() and not page.form.fields['seed'].isVisible()
    page.show_settings('frame');assert page.form.fields['axis'].isVisible()
    page.show_settings('statistics');assert page.form.fields['seed'].isVisible()
    page.form.set_value('acceptance_max','-1');page.tabs.setCurrentIndex(0)
    assert page.current_issue.target=='settings' and 'en küçük' in page.review_text.text()


@pytest.mark.parametrize('theme',['dark','light'])
def test_error_and_fix_button_remain_visible_at_small_window_sizes(window,theme):
    window.resize(1024,700);window.set_theme(theme)
    page=window.pages['tolerance_stack'];page.load_example()
    page.project.dimensions[1]=replace(page.project.dimensions[1],upper=None);page.refresh();QApplication.processEvents()
    for control in (page.fix_button,page.calculate_button,page.confirm_box):
        assert control.isVisible()
        assert window.rect().contains(control.mapTo(window,control.rect().bottomRight()))


@pytest.mark.parametrize('size',[(1024,700),(1366,768)])
def test_compact_diagram_reflows_without_shrinking_text_and_keeps_add_actions_visible(window,qtbot,size):
    window.resize(*size);page=window.pages['tolerance_stack'];page.load_example()
    qtbot.waitUntil(lambda:page.chain_diagram.vector.width==max(360,page.chain_diagram.viewport().width()))
    assert page.chain_diagram.transform().m11()>.85
    for control in (page.add_plus,page.add_minus,page.calculate_button):
        assert control.isVisible() and window.rect().contains(control.mapTo(window,control.rect().bottomRight()))


def test_invalid_advanced_input_targets_its_field_and_does_not_leak_into_a_new_analysis(window):
    page=window.pages['tolerance_stack'];page.load_example();page.show_settings('statistics')
    page.form.set_value('seed','abc');page.tabs.setCurrentIndex(0)
    assert page.current_issue.target=='statistics' and not page.calculate_button.isEnabled()
    page.fix_button.click();assert page.form.fields['seed'].hasFocus()
    with patch.object(page,'confirm_discard',return_value=True):page.new_project()
    assert page.metadata_error=='' and page.metadata_field=='' and page.project.terms==[]
    assert not page.calculate_button.isEnabled()
