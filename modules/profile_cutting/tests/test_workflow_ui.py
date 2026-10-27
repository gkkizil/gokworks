"""Beginner workflow through real Qt controls and the unchanged optimizer."""

from decimal import Decimal

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from .test_ui import page, setup_scan  # noqa: F401
from modules.profile_cutting.dialogs import RowDialog
from modules.profile_cutting.models import Demand, Project
from modules.profile_cutting.widgets import plan_totals, cut_pattern
from modules.profile_cutting.optimizer import optimize, validate_plan


def calculate(p, w, qtbot):
    p.run_button.click()
    qtbot.waitUntil(lambda: p.plan is not None and not w.jobs.busy, timeout=6000)


def test_example_to_stock_selection_and_exact_cut_sequence(page, qtbot):
    p, w = page
    assert not p.run_button.isEnabled() and not p.stock_disclosure.is_expanded()
    assert p.demand_stack.currentIndex() == 1
    p.load_example()
    assert p.run_button.isEnabled() and p.demand_model.rowCount() == 2
    assert '10 parça' in p.input_summary.text() and p.form.value('stock_length') == '6000'
    # Opening and accepting the example must not split its stock group when
    # the editor resolves the wall thickness already present in its section.
    dialog = RowDialog(p, p.project.demands[0]); qtbot.addWidget(dialog)
    dialog.check()
    assert dialog.value.group == p.project.demands[0].group
    calculate(p, w, qtbot)
    validate_plan(p.project, p.plan)
    totals = plan_totals(p.plan)
    assert totals['bars'] == 2 and totals['count'] == 10
    assert totals['stock'] == totals['parts'] + totals['remaining'] + totals['saw'] + totals['trim']
    assert totals['remaining'] == Decimal(2370) and totals['saw'] == 30 and totals['usage'] == 80
    assert '2 çubuktan 10 parça' in p.plan_summary.text()
    assert p.tabs.currentIndex() == 2 and p.cut_order.model.rowCount() == 5
    assert not p.cut_order.table.isSortingEnabled()
    p.plan_view.selectRow(1)
    assert p.cut_order.caption.text().startswith('2. çubuk')
    assert [r['length'] for r in p.cut_order.model.rows] == [Decimal(800)] * 5
    assert p.diagram.vector.tagged['remaining']


def test_manual_add_requires_four_explicit_fields_and_preserves_stock_length(page, qtbot):
    p, _ = page
    def enter():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, RowDialog)
        assert not dialog.form.value('profile') and not dialog.form.value('length')
        assert not dialog.advanced.is_expanded()
        dialog.check()
        assert dialog.result() != QDialog.Accepted and dialog.error_label.isVisible()
        for key, value in dict(profile='40×40×2', material='S235JR', length='1200', count='4').items():
            dialog.form.set_value(key, value)
        dialog.check()
    QTimer.singleShot(0, enter)
    p.add_button.click()
    row, = p.project.demands
    assert row.length == '1200' and row.count == 4 and row.thickness == '2'
    assert p.project.stock_length == '6000' and p.demand_stack.currentIndex() == 0
    assert not p.demands.isColumnHidden(0) and p.demands.isColumnHidden(5)


def test_edit_dialog_preserves_import_identity_and_stale_source_block(page, qtbot):
    p, _ = page
    original = Demand('keep-id', '40×40×2', 'S235JR', '1000', 2,
        source='frame.SLDPRT / CutList1', import_id='import-A', import_revision='revision-A',
        source_changed='Kaynak satırı değişti.', body_refs=['body-A'])
    p.project.demands = [original]; p.refresh_demands(); p.demands.selectRow(0)
    def edit():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, RowDialog) and not dialog.review_mode
        dialog.form.set_value('length','900'); dialog.check()
    QTimer.singleShot(0, edit)
    p.edit_button.click()
    row, = p.project.demands
    assert row.id == original.id and row.import_id == original.import_id
    assert row.import_revision == original.import_revision and row.body_refs == ['body-A']
    assert row.source_changed and row.length == '900'
    p.calculate()
    assert p.plan is None and 'kaynak verisi' in p.status_text


def test_input_change_cannot_repaint_a_stale_plan_after_resize(page, qtbot):
    p, w = page; p.load_example(); calculate(p, w, qtbot)
    assert p.diagram.vector.tagged['stock']
    p.form.set_value('kerf', '4')
    assert p.plan is None and p.diagram.renderer is None and p.cut_order.model.rowCount() == 0
    w.resize(1024,700); qtbot.wait(100)
    assert not p.diagram.vector.items() and not p.report_button.isEnabled()
    assert p.plan_stack.currentIndex() == 1


def test_example_never_silently_replaces_existing_parts(page, monkeypatch):
    p, _ = page
    old = Demand('keep','IPE200','S355JR','1200',2)
    p.project.demands = [old]; p.refresh_demands()
    monkeypatch.setattr(QMessageBox,'question',lambda *a: QMessageBox.No)
    p.load_example()
    assert p.project.demands == [old]
    monkeypatch.setattr(QMessageBox,'question',lambda *a: QMessageBox.Yes)
    p.load_example()
    assert len(p.project.demands) == 2 and p.project.demands[0].id != old.id


def test_losses_and_extra_length_are_presented_separately_without_changing_the_plan(page, qtbot):
    p, _ = page
    p.project = Project([Demand('part','40×40×2','S235JR','100',2,allowance='10')], '1000','3','5')
    plan = optimize(p.project)
    p.handle_events([('profile_plan',plan)])
    totals = plan_totals(plan)
    assert totals['parts'] == 220 and totals['saw'] == 6 and totals['trim'] == 10 and totals['remaining'] == 764
    assert not p.cut_order.table.isColumnHidden(2)
    assert p.cut_order.model.rows[0]['length'] == 100 and p.cut_order.model.rows[0]['allowance'] == 10
    assert '(+10 mm/parça)' in cut_pattern(plan.bars[0])
    assert 'Testere kaybı 6 mm' in p.plan_numbers.text() and 'Uç düzeltme kaybı 10 mm' in p.plan_numbers.text()
    validate_plan(p.project, p.plan)


def test_scan_ready_state_filters_and_append_only_transfer_remain_understandable(page, qtbot, tmp_path, monkeypatch):
    p, w = page; setup_scan(monkeypatch, tmp_path)
    assert not p.scan_disclosure.is_expanded() and not p.transfer_button.isEnabled()
    p.project.demands = [Demand('manual','IPE200','S355JR','1000',1)]; p.refresh_demands()
    p.from_sw_button.click(); assert p.tabs.currentIndex() == 1
    p.scan_button.click(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert p.transfer_button.isEnabled() and '1 hazır satır' in p.transfer_button.text()
    p.status_filter.setCurrentIndex(p.status_filter.findData('İnceleme Gerekli'))
    assert p.scan_proxy.rowCount() == 0
    p.status_filter.setCurrentIndex(0)
    p.transfer_button.click()
    assert p.tabs.currentIndex() == 0 and p.project.demands[0].id == 'manual'
    assert len(p.project.demands) == 2
    p.import_scan(); assert len(p.project.demands) == 2


def test_plan_csv_button_exports_the_real_selected_plan(page, qtbot, tmp_path, monkeypatch):
    p, w = page; p.load_example(); calculate(p, w, qtbot)
    path = tmp_path/'plan.csv'
    monkeypatch.setattr('modules.profile_cutting.ui.QFileDialog.getSaveFileName',lambda *a:(str(path),''))
    p.report_button.click(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert path.is_file() and '1200' in path.read_text(encoding='utf-8-sig')
    assert 'kaydedildi' in p.status_text


def test_invalid_end_trim_reveals_the_field_that_needs_correction(page):
    p, _ = page; p.load_example()
    p.form.set_value('trim','3000')
    p.calculate()
    assert p.plan is None and p.stock_disclosure.is_expanded()
    assert 'İki uç' in p.status_text and p.tabs.currentIndex() == 0


def test_piece_too_long_shows_the_stock_inputs_instead_of_a_blank_result(page, qtbot):
    p, w = page
    p.project.demands = [Demand('long','IPE200','S235JR','7000',1)]; p.refresh_demands()
    p.tabs.setCurrentIndex(1); p.run_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert p.plan is None and 'sığmıyor' in p.status_text and p.tabs.currentIndex() == 0


def test_valid_unproven_plan_does_not_claim_a_minimum(page):
    p, _ = page
    p.project = Project([Demand('many','IPE200','S235JR','6000',23)],'10000','0','0')
    plan = optimize(p.project)
    assert not plan.optimal
    p.handle_events([('profile_plan',plan)])
    assert 'garanti edilmez' in p.plan_proof.text() and 'doğrulandı' not in p.plan_proof.text()
    validate_plan(p.project,p.plan)


def test_editing_section_cannot_silently_retain_a_conflicting_wall_thickness(page, qtbot):
    p, _ = page
    row = Demand('part','40×40×2','S235JR','1000',2,thickness='2')
    p.project.demands = [row]; p.refresh_demands()
    p.demand_model.setData(p.demand_model.index(0,0),'40×40×3')
    assert row.profile == '40×40×2' and row.thickness == '2'
    assert 'Düzenle' in p.status_text and p.demand_model.rows[0]['profile'] == '40×40×2'
    dialog = RowDialog(p,row); qtbot.addWidget(dialog); dialog.show()
    dialog.form.set_value('profile','40×40×3'); dialog.check()
    assert dialog.result() != QDialog.Accepted and dialog.advanced.is_expanded()
    assert 'Et kalınlığı' in dialog.error_label.text() and row.thickness == '2'
    dialog.form.set_value('thickness',''); dialog.check()
    assert dialog.result() == QDialog.Accepted and dialog.value.thickness == '3'
    assert dialog.value.id == row.id
