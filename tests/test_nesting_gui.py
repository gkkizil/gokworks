"""Qt integration with real DXF files, real background jobs and responsive state."""

import gc
from pathlib import Path
import threading

import ezdxf
import pytest
from PySide6.QtCore import QEvent, QCoreApplication, QTimer, Qt, QPoint, QItemSelectionModel
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import MainWindow,create_application
from gui_qt.pages.nesting_widgets import Editor


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1440,960); w.show(); w.navigate('nesting')
    yield w
    if w.jobs.busy: w.jobs.cancel(); qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    assert w.settings.flush(); w.close(); w.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); gc.collect()


def load_parts(window,qtbot,tmp_path):
    f = tmp_path/'real.dxf'; doc = ezdxf.new(); doc.units = 4
    doc.modelspace().add_lwpolyline([(0,0),(50,0),(50,30),(0,30)],close=True); doc.saveas(f)
    page = window.pages['nesting']; page.import_files([str(f)],quantity=3)
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.project.parts) == 1
    assert page.part_model.rows[0]['quantity'] == 3
    return page


def test_real_import_nest_invalidate_and_source_preserved(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path); data = (tmp_path/'real.dxf').read_bytes()
    page.form.set_value('seconds','2'); page.form.set_value('quality','Hızlı')
    page.start_nest(); assert window.jobs.owner is page; assert not page.import_button.isEnabled()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result is not None and len(page.result.placements) == 3
    assert page.excel_button.isEnabled(); assert '3 parça' in page.summary.text()
    assert page.canvas.scene().items(); assert (tmp_path/'real.dxf').read_bytes() == data
    page.form.set_value('gap','7')
    assert page.result is None and not page.excel_button.isEnabled()
    assert 'yeniden' in page.status_text


def test_steps_and_result_stay_accessible_without_clipping_after_resize_and_themes(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    for theme in ('dark','light'):
        window.set_theme(theme)
        for width,height in [(1440,960),(1024,700),(820,560),(1440,960)]:
            window.resize(width,height); qtbot.wait(60)
            assert page.tabs.count() == 3
            assert page.tabs.indexOf(page.parts_panel) == 0
            assert page.tabs.indexOf(page.stock_widget) == 1
            assert page.tabs.indexOf(page.preview_scroll) == 2
            page.tabs.setCurrentWidget(page.parts_panel); qtbot.wait(30)
            assert page.next_button.isVisible() and page.next_button.isEnabled()
            assert page.part_table.horizontalScrollBar().maximum() == 0
            page.next_button.click(); assert page.tabs.currentWidget() is page.stock_widget
            assert page.nest_button.isVisible() and page.nest_button.isEnabled()
            page.tabs.setCurrentWidget(page.preview_scroll); qtbot.wait(30)
            previous_bottom = 0
            for widget in (page.sheet_tabs,page.current_note,page.canvas,page.labels_toggle,page.summary,page.cost_summary):
                top = widget.mapTo(page,QPoint(0,0)).y()
                assert top >= previous_bottom
                previous_bottom = top+widget.height()
                assert page.rect().contains(widget.mapTo(page,widget.rect().bottomRight()))
            assert page.canvas.viewport().rect().contains(page.canvas.mapFromScene(page.canvas.sceneRect()).boundingRect())
            assert not window.grab().isNull()
            assert page.width() >= 550


def test_background_job_keeps_navigation_alive_and_can_cancel(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    page.project.parts[0].quantity = 300
    page.form.set_value('seconds','20'); page.form.set_value('quality','Yüksek')
    ticks = []; timer = QTimer(); timer.setInterval(10); timer.timeout.connect(lambda:ticks.append(1)); timer.start()
    page.start_nest(); window.navigate('weight'); qtbot.waitUntil(lambda:len(ticks)>5,timeout=4000)
    assert window.stack.currentWidget() is window.pages['weight']
    window.jobs.cancel(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000); timer.stop()
    assert len(ticks)>5
    assert page.result is not None and page.result.stopped


def test_invalid_parameters_cannot_start_job(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path)
    page.form.set_value('seconds','0'); page.start_nest()
    assert not window.jobs.busy and page.result is None
    assert 'süresi' in page.status_text


def test_cost_only_changes_reprice_same_coordinates_in_background(window,qtbot,tmp_path,monkeypatch):
    page = load_parts(window,qtbot,tmp_path); page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    coordinates = [(p.x,p.y,p.angle) for p in page.result.placements]
    def unexpected(*args,**kwargs): raise AssertionError('Cost change must not rerun placement search')
    monkeypatch.setattr('nesting.engine.nest',unexpected)
    page.cost_form.set_value('setup','25')
    assert page.result is None and not page.pdf_button.isEnabled()
    qtbot.waitUntil(lambda:page.result is not None and not window.jobs.busy,timeout=8000)
    assert [(p.x,p.y,p.angle) for p in page.result.placements] == coordinates
    from nesting.accounting import calculate
    assert calculate(page.project,page.result)['setup'] == 25
    assert 'Toplam 25,00 TL' in page.cost_summary.text()
    assert 'Malzeme 0,00 TL' in page.cost_summary.text() and 'Sac fiyatı eksik' in page.cost_summary.text()


def test_project_open_save_and_reports_use_jobs(window,qtbot,tmp_path,monkeypatch):
    page = load_parts(window,qtbot,tmp_path); page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    for kind,suffix in [('excel','.xlsx'),('pdf','.pdf')]:
        target = tmp_path/('report'+suffix)
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,p=str(target),**kwargs:(p,''))
        page.export_report(kind); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
        assert target.stat().st_size > 1000
    target = tmp_path/'portable.goknest.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
    page.save_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    page.new_project(); assert not page.project.parts
    (tmp_path/'real.dxf').unlink()
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(target),''))
    page.open_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result is not None and len(page.project.parts) == 1 and page.result.placements
    assert page.pdf_button.isEnabled()


def test_editor_preserves_validation_error_in_dialog(window,qtbot):
    def parse(form):
        from nesting.models import number
        return number(form.value('density'),'Yoğunluk',positive=True)
    d = Editor(window,'Malzeme',lambda f:f.text('density','Yoğunluk','nan'),parse)
    qtbot.addWidget(d); d.show(); d.submit()
    assert d.value is None and 'Yoğunluk' in d.error.text()
    d.form.set_value('density','7850'); d.submit(); assert d.value == 7850


def test_multiselect_lists_every_source_immediately_and_continues_after_bad_file(window,qtbot,tmp_path,monkeypatch):
    files = []
    for i in range(5):
        f = tmp_path/f'Batch-{i}.dxf'; files.append(str(f))
        if i == 2: f.write_text('not a DXF\n'); continue
        d = ezdxf.new(); d.units = 4
        d.modelspace().add_lwpolyline([(0,0),(20+i,0),(20+i,10),(0,10)],close=True); d.saveas(f)
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *a,**k:(files,''))
    def accept_options(dialog): dialog.submit(); return dialog.result()
    monkeypatch.setattr(Editor,'exec',accept_options)
    page = window.pages['nesting']; page.search.setText('old filter'); page.import_dialog()
    assert len(page.imports) == 5 and page.part_model.rowCount() == 5
    assert page.search.text() == ''
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.project.parts) == 4 and page.part_model.rowCount() == 5
    assert {Path(r['source']).name for r in page.part_model.rows} == {Path(f).name for f in files}
    assert sum(r['status'] == 'error' for r in page.part_model.rows) == 1
    assert '5 dosya seçildi' in page.import_info.text() and '1 sorunlu' in page.import_info.text()
    qtbot.wait(120)
    assert 'Yükleme tamamlandı' in page.status_text and 'okunuyor' not in page.status_text
    page.start_nest(); assert not window.jobs.busy and 'henüz hazır değil' in page.status_text
    broken = next(e for e in page.imports if e['status'] == 'error')
    doc = ezdxf.new(); doc.units = 4
    doc.modelspace().add_lwpolyline([(0,0),(22,0),(22,10),(0,10)],close=True); doc.saveas(files[2])
    page.import_files([files[2]],retry_id=broken['id'],**broken['options'])
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.project.parts) == 5 and len(page.imports) == 5 and page.part_model.rowCount() == 5
    assert all(e['status'] == 'success' for e in page.imports)


def test_partial_batch_is_visible_during_read_and_survives_cancel(window,qtbot,tmp_path,monkeypatch):
    from nesting.dxf_import import read_dxf,check_cancel
    import nesting.batch_import as batch
    files = []
    for i in range(3):
        f = tmp_path/f'Cancel-{i}.dxf'; files.append(str(f)); doc = ezdxf.new(); doc.units = 4
        doc.modelspace().add_lwpolyline([(0,0),(20,0),(20,10),(0,10)],close=True); doc.saveas(f)
    waiting = threading.Event()
    def reader(path,**kwargs):
        if path == files[1]:
            waiting.set()
            kwargs['stop'].wait(5); check_cancel(kwargs['stop'])
        return read_dxf(path,**kwargs)
    monkeypatch.setattr(batch,'read_dxf',reader)
    page = window.pages['nesting']; page.import_files(files)
    qtbot.waitUntil(lambda:waiting.is_set() and len(page.project.parts) == 1,timeout=5000)
    assert window.jobs.busy and page.part_model.rowCount() == 3
    window.jobs.cancel(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.project.parts) == 1 and page.part_model.rowCount() == 3
    assert [e['status'] for e in page.imports] == ['success','cancelled','cancelled']


def test_missing_unit_stays_in_list_and_can_be_retried_with_explicit_mm(window,qtbot,tmp_path):
    f = tmp_path/'Unknown-unit.dxf'; doc = ezdxf.new(); doc.units = 0
    doc.modelspace().add_lwpolyline([(0,0),(20,0),(20,10),(0,10)],close=True); doc.saveas(f)
    page = window.pages['nesting']; page.import_files([str(f)])
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.part_model.rowCount() == 1 and not page.project.parts
    entry = page.imports[0]; assert entry['status'] == 'error' and 'birimi' in entry['detail']
    page.import_files([str(f)],retry_id=entry['id'],unit='mm')
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.imports) == 1 and len(page.project.parts) == 1 and page.project.parts[0].area == 200


def test_three_plates_are_numbered_and_browsable(window,qtbot):
    from nesting.models import Part
    from shapely.geometry import box
    page = window.pages['nesting']; page.project.parts = [Part.create('P',box(0,0,35,35),quantity=9)]
    page.project.sheets[0].width = page.project.sheets[0].height = 100
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result is not None and not page.result.unplaced
    assert page.sheet_tabs.count() == 3
    assert [page.sheet_tabs.tabText(i) for i in range(3)] == ['1. plaka','2. plaka','3. plaka']
    assert '1/3 plaka' in page.current_note.text()
    qtbot.mouseClick(page.sheet_tabs,Qt.LeftButton,pos=page.sheet_tabs.tabRect(1).center())
    assert page.sheet_tabs.currentIndex() == 1 and '2/3 plaka' in page.current_note.text()
    assert page.canvas.key == page.sheet_tabs.tabData(1)
    qtbot.keyClick(page.sheet_tabs,Qt.Key_Right)
    assert page.sheet_tabs.currentIndex() == 2 and page.canvas.key == page.sheet_tabs.tabData(2)
    qtbot.keyClick(page.sheet_tabs,Qt.Key_Left); assert page.sheet_tabs.currentIndex() == 1


def test_many_document_tabs_scroll_to_last_physical_plate_in_small_window(window,qtbot):
    from nesting.models import Part
    from shapely.geometry import box
    page=window.pages['nesting']; window.resize(820,620)
    page.project.parts=[Part.create('P',box(0,0,35,35),quantity=20)]
    sheet=page.project.sheets[0]; sheet.width=sheet.height=60
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.sheet_tabs.count()==20 and page.sheet_tabs.usesScrollButtons()
    page.sheet_tabs.setCurrentIndex(19); qtbot.wait(50)
    assert page.sheet_tabs.rect().contains(page.sheet_tabs.tabRect(19).center())
    assert page.canvas.key==(sheet.id,20) and '20/20 plaka' in page.current_note.text()
    assert page.sheet_tabs.width()<page.width()


def test_document_tabs_keep_distinct_sheet_keys_for_different_materials_and_thicknesses(window,qtbot):
    from dataclasses import replace
    from nesting.models import Part,uid
    from shapely.geometry import box
    page=window.pages['nesting']; first=page.project.sheets[0]
    second=replace(first,id=uid(),material=page.project.materials[3].id,thickness=1.5)
    page.project.sheets.append(second)
    page.project.parts=[Part.create('Steel',box(0,0,35,35)),
        Part.create('Stainless',box(0,0,35,35),material=second.material,thickness=1.5)]
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.sheet_tabs.count()==2
    assert {page.sheet_tabs.tabData(i) for i in range(2)}=={(first.id,1),(second.id,1)}
    for i in range(2):
        page.sheet_tabs.setCurrentIndex(i)
        sheet=page.project.sheet(page.canvas.key[0])
        assert page.project.material(sheet.material).name in page.sheet_tabs.tabToolTip(i)
        assert len(page.canvas.part_labels)==1


def test_unmatched_thickness_targets_stock_instead_of_silently_omitting_parts(window,qtbot,tmp_path):
    page = load_parts(window,qtbot,tmp_path); page.project.parts[0].thickness = 1.5
    page.start_nest()
    assert not window.jobs.busy and page.result is None
    assert page.tabs.currentWidget() is page.stock_widget and '1.5 mm' in page.status_text


def test_problem_sources_remain_visible_after_project_save_open(window,qtbot,tmp_path,monkeypatch):
    page = load_parts(window,qtbot,tmp_path)
    f = tmp_path/'Problem.dxf'; f.write_text('not a DXF\n'); page.import_files([str(f)])
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    target = tmp_path/'With-errors.goknest.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    page.save_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    page.new_project(); monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(target),''))
    page.open_project(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert len(page.imports) == 2 and page.part_model.rowCount() == 2
    assert any(e['status'] == 'error' for e in page.imports) and len(page.project.parts) == 1
    page.start_nest(); assert not window.jobs.busy and 'henüz hazır değil' in page.status_text


def test_incomplete_nest_disables_all_exports_before_opening_file_dialog(window,qtbot,monkeypatch):
    from nesting.models import Part
    from shapely.geometry import box
    page=window.pages['nesting']
    page.project.parts=[Part.create('P',box(0,0,35,35),quantity=5)]
    sheet=page.project.sheets[0]; sheet.width=sheet.height=100; sheet.stock=1
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert page.result and len(page.result.unplaced)==1
    assert '1 parça yerleşmedi' in page.summary.text()
    assert 'Kısmi hesap' in page.cost_summary.text()
    assert page.details_button.isEnabled() and page.detail_button.isEnabled()
    for control in (page.export_button,page.dxf_button,page.excel_button,page.pdf_button):
        assert not control.isEnabled()
    def forbidden(*args,**kwargs): raise AssertionError('Incomplete export must stop before file selection')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',forbidden)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',forbidden)
    page.export_dxf(); page.export_report('excel'); page.export_report('pdf')
    assert not window.jobs.busy and 'tüm parçalar' in page.status_text
    sheet.stock=2; page.start_nest(); qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    assert not page.result.unplaced and page.export_button.isEnabled()


def test_multiple_selected_rows_remove_correct_parts_and_failed_sources_through_sort_filter(window,qtbot):
    from nesting.models import Part
    from shapely.geometry import box
    page=window.pages['nesting']
    page.project.parts=[Part.create(code,box(0,0,20,10)) for code in ('Keep-A','Remove-B','Remove-A','Keep-B')]
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    page.imports=[dict(id='bad',source='Remove-bad.dxf',status='error',detail='Open contour',options={})]
    page.refresh(); page.tabs.setCurrentWidget(page.parts_panel)
    page.search.setText('Remove'); page.part_table.sortByColumn(0,Qt.DescendingOrder)
    assert page.part_proxy.rowCount()==3
    for row in range(3):
        page.part_table.selectionModel().select(page.part_proxy.index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
    assert page.remove_part_button.isEnabled() and not page.edit_part_button.isEnabled()
    assert '(3)' in page.remove_part_button.text()
    page.remove_part_button.click()
    assert {p.code for p in page.project.parts}=={'Keep-A','Keep-B'}
    assert not page.imports and page.result is None and not page.export_button.isEnabled()
    page.search.clear(); assert page.part_proxy.rowCount()==2


def test_cost_refresh_preserves_selected_physical_plate_and_includes_vat_profit(window,qtbot,monkeypatch):
    from nesting.models import Part
    from shapely.geometry import box
    from nesting.accounting import calculate
    page=window.pages['nesting']; page.project.parts=[Part.create('P',box(0,0,35,35),quantity=9)]
    sheet=page.project.sheets[0]; sheet.width=sheet.height=100; sheet.price_kg=45
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    page.sheet_tabs.setCurrentIndex(1); selected=page.selected_sheet_key()
    original=[(p.part_id,p.sheet_number,p.x,p.y,p.angle) for p in page.result.placements]
    def forbidden(*args,**kwargs): raise AssertionError('Repricing must reuse verified placement')
    monkeypatch.setattr('nesting.engine.nest',forbidden)
    page.cost_form.set_value('setup','25'); page.cost_form.set_value('profit_percent','10'); page.cost_form.set_value('vat_percent','20')
    qtbot.waitUntil(lambda:page.result is not None and not window.jobs.busy,timeout=8000)
    assert page.selected_sheet_key()==selected and page.sheet_tabs.currentIndex()==1
    assert [(p.part_id,p.sheet_number,p.x,p.y,p.angle) for p in page.result.placements]==original
    totals=calculate(page.project,page.result)
    assert page.totals==totals and totals['total']>totals['material_cost']+25
    from gui_qt.pages.nesting import fmt
    assert f"Toplam {fmt(totals['total'],2)} TL" in page.cost_summary.text()


def test_collapsed_advanced_settings_are_preserved_and_saved_costs_remain_visible(window,qtbot):
    page=window.pages['nesting']; page.tabs.setCurrentWidget(page.stock_widget)
    assert not page.advanced_button.isChecked() and not page.cost_form.isVisible()
    page.form.set_value('kerf','.35'); page.form.set_value('angles','0;180'); page.form.set_value('seed','73')
    page.cost_form.set_value('setup','25'); page.read_parameters(); page.sync_forms()
    assert page.cost_toggle.isChecked() and page.cost_form.isVisible()
    page.advanced_button.click(); assert page.form.fields['kerf'].isVisible()
    assert page.form.value('kerf')=='0.35' and page.form.value('angles')=='0.0;180.0'
    page.advanced_button.click(); page.read_parameters()
    assert page.project.options.kerf==.35 and page.project.options.angles==[0,180]
    assert page.project.options.seed==73 and page.project.operations.setup==25


def test_material_library_still_edits_project_materials(window,qtbot,monkeypatch):
    from PySide6.QtWidgets import QDialog
    page=window.pages['nesting']
    def execute(dialog):
        if isinstance(dialog,Editor):
            dialog.form.set_value('density','8000'); dialog.submit()
        else:
            page.material_table.selectRow(0); page.edit_material()
        return QDialog.Accepted
    monkeypatch.setattr(QDialog,'exec',execute)
    page.show_materials()
    assert page.project.materials[0].density==8000
    assert page.material_table is None


def test_part_names_toggle_does_not_rebuild_geometry_or_lose_full_source_tooltip(window,qtbot,tmp_path):
    page=load_parts(window,qtbot,tmp_path)
    page.project.parts[0].code='A very long part code that must not overlap adjacent parts'
    page.form.set_value('quality','Hızlı'); page.start_nest()
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=8000)
    items=set(page.canvas.scene().items())
    assert len(page.canvas.part_labels)==3
    assert all(len(item.text())<=18 and page.project.parts[0].code in item.toolTip() for item in page.canvas.part_labels)
    page.labels_toggle.setChecked(False)
    assert all(not item.isVisible() for item in page.canvas.part_labels)
    assert set(page.canvas.scene().items())==items
    page.labels_toggle.setChecked(True); assert all(item.isVisible() for item in page.canvas.part_labels)
