"""Akıllı bölme ekranı: sıralı adımlar, okunur sonuçlar, dar pencerede kesilmeyen form."""
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from gui_qt.app import MainWindow, create_application
from modules.smart_splitting.tests.test_workbench import circle_dxf, finish
from modules.smart_splitting.ui import area_text, length_text


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w); w.show()
    w.navigate('smart_splitting'); qtbot.wait(20)
    yield w
    if w.jobs.busy: w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=15000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_units_are_readable():
    assert area_text(2534987.4) == '2,5350 m²' and area_text(1234.56) == '1234,6 mm²'
    assert length_text(5399.8) == '5399,8 mm' and length_text(25000) == '25,000 m'


def test_empty_screen_says_where_to_start_and_locks_later_steps(window):
    page = window.pages['smart_splitting']
    assert page.canvas.empty and 'DXF/DWG ekle' in page.canvas.EMPTY
    assert page.open_button.property('primary') and page.next_hint.text() == 'Sonraki: parça seçin'
    assert not page.split_button.isEnabled() and not page.transfer_button.isEnabled() and not page.export_button.isEnabled()


def test_sections_share_one_form_and_keep_saved_values(window, tmp_path):
    page = window.pages['smart_splitting']
    assert {'count', 'tolerance', 'sheet_width', 'kerf', 'joining', 'forbidden'} <= set(page.form.fields)
    page.form.set_value('count', '8'); page.form.set_value('kerf', '.3')
    assert page.settings.get('smart_splitting/count') == '8' and page.form.value('kerf') == '.3'


def test_split_fills_tiles_and_marks_the_next_step(window, qtbot, tmp_path):
    page = window.pages['smart_splitting']
    page.load_file(circle_dxf(tmp_path/'A.dxf', radius=100)); finish(window, qtbot)
    assert not page.canvas.empty and page.preview_center() is not None
    assert page.next_hint.text().startswith('Sonraki: Parçayı Böl')
    page.form.set_value('count', 4); page.run_split(); finish(window, qtbot)
    assert page.tiles['segments'].value.text() == '4 × 1' and page.tiles['check'].value.text().startswith('✓')
    assert page.transfer_button.property('primary') and not page.split_button.property('primary')
    assert page.next_hint.text() == 'Sonraki: DXF’e veya Nesting’e aktarın'
    page.form.set_value('count', 5)
    assert page.solution is None and page.tiles['segments'].value.text() == '—' and not page.transfer_button.isEnabled()


def test_forbidden_zones_are_drawn_and_bad_text_is_explained(window, qtbot, tmp_path):
    page = window.pages['smart_splitting']
    page.load_file(circle_dxf(tmp_path/'A.dxf', radius=100)); finish(window, qtbot)
    page.form.set_value('forbidden', '10,10,20,20;bad')
    assert len(page.forbidden_boxes(strict=False)) == 1
    with pytest.raises(ValueError, match='x,y,en,boy'):
        page.forbidden_boxes()
    page.form.set_value('center_mode', 'Özel merkez')
    assert page.form.fields['center_x'].isEnabled()
    page.form.set_value('center_mode', 'Sınır kutusu merkezi')
    assert not page.form.fields['center_x'].isEnabled() and 'Özel merkez' in page.form.fields['center_x'].toolTip()


@pytest.mark.parametrize('size', [(1024, 700), (1366, 768), (1920, 1080)])
def test_left_column_never_cuts_values(window, qtbot, size):
    window.resize(*size); qtbot.wait(60)
    page = window.pages['smart_splitting']
    assert page.left_scroll.widget().width() <= page.left_scroll.viewport().width()
    assert page.left_scroll.horizontalScrollBar().maximum() == 0


def test_batch_dxf_reads_quantities_from_names_splits_all_and_transfers_together(window, qtbot, tmp_path):
    """Toplu: birkaç DXF bir seferde eklenir, aynı ayarla bölünür, birlikte aktarılır; bozuk dosya diğerlerini durdurmaz."""
    from modules.smart_splitting.tests.test_geometry import circle_dxf as make
    page = window.pages['smart_splitting']
    first = make(tmp_path/'Flans - 3 mm - 5 adet.dxf', radius=120)
    second = make(tmp_path/'Halka - 2 mm - 2 adet.dxf', radius=90)
    broken = tmp_path/'Bozuk.dxf'; broken.write_text('not a dxf', encoding='utf-8')
    page.load_files([first, second, broken]); finish(window, qtbot)
    assert len(page.sources) == 2 and page.source_table.rowCount() == 2
    assert [m['quantity'] for m in page.meta] == [5, 2] and [m['thickness'] for m in page.meta] == [3., 2.]
    assert 'Bozuk.dxf' in page.status_text and page.all_button.isVisible() and page.all_button.text() == 'Tümünü Böl (2)'
    page.form.set_value('count', 4)
    page.run_all(); finish(window, qtbot)
    assert set(page.solutions) == {0, 1} and not page.part_errors
    assert [page.solutions[i].settings.quantity for i in (0, 1)] == [5, 2]
    assert page.source_table.item(1, 3).text() == '✓ 4' and 'doğrulandı' in page.source_table.item(1, 3).toolTip()
    assert [s.code for s in page.sources] == ['Flans', 'Halka']        # short names from the file name
    assert page.transfer_button.text() == 'Nesting’e Aktar (2) →'
    page.source_table.selectRow(1)
    assert page.solution is page.solutions[1] and page.tiles['segments'].value.text() == '4 × 2'

    output = tmp_path/'out'; page.export_to(output); finish(window, qtbot)
    folders = sorted(p.name for p in output.iterdir())
    assert len(folders) == 2 and all((output/f/'BOLME_RAPORU.json').is_file() for f in folders)

    page.transfer()
    nesting = window.pages['nesting']; parts = nesting.project.parts
    assert len(parts) == 8 and sum(p.quantity for p in parts) == 4*5 + 4*2
    assert {p.thickness for p in parts} == {3., 2.}


def test_editing_one_parts_quantity_only_reopens_that_part(window, qtbot, tmp_path):
    from modules.smart_splitting.tests.test_geometry import circle_dxf as make
    page = window.pages['smart_splitting']
    page.load_files([make(tmp_path/'A - 2 adet.dxf', radius=80), make(tmp_path/'B - 3 adet.dxf', radius=70)]); finish(window, qtbot)
    page.form.set_value('count', 3); page.run_all(); finish(window, qtbot)
    page.source_table.item(0, 1).setText('7')
    assert page.meta[0]['quantity'] == 7 and 0 not in page.solutions and 1 in page.solutions
    assert page.source_table.item(0, 3).text() == 'bekliyor'
    page.source_table.item(1, 1).setText('-1')
    assert page.meta[1]['quantity'] == 3 and page.status.property('role') == 'error'
    page.form.set_value('count', 5)
    assert not page.solutions                     # shared settings changed: every result is stale


def test_dwg_files_load_through_the_bundled_converter_with_names_and_quantities(window, qtbot, tmp_path, monkeypatch):
    """DWG: Nesting ile aynı dönüştürücü (kuruluysa ODA, yoksa paketteki LibreDWG); ek indirme yok."""
    from modules.nesting import dwg_import
    from modules.nesting.tests.test_bundled_dwg import LIBREDWG, fake_tool
    monkeypatch.setattr(dwg_import, 'converter_path', lambda: (_ for _ in ()).throw(ValueError('ODA yok')))
    tools = tmp_path/'tools'; tools.mkdir()
    monkeypatch.setenv('GOKWORKS_LIBREDWG_DWG2DXF', str(fake_tool(tools, 'dwg2dxf', LIBREDWG)))
    drawing = tmp_path/'Kapak - 4 mm - 6 adet.dwg'; drawing.write_bytes(b'AC1032 test drawing')
    page = window.pages['smart_splitting']
    page.load_files([drawing]); finish(window, qtbot)
    assert [s.code for s in page.sources] == ['Kapak'] and page.meta[0]['quantity'] == 6 and page.meta[0]['thickness'] == 4.
    assert 'LibreDWG' in page.sources[0].notes[-1] and drawing.read_bytes() == b'AC1032 test drawing'
    page.form.set_value('count', 2); page.run_split(); finish(window, qtbot)
    assert page.solution is not None and page.solution.settings.quantity == 6


def test_two_files_with_the_same_short_name_stay_apart_in_nesting(window, qtbot, tmp_path):
    from modules.smart_splitting.tests.test_geometry import circle_dxf as make
    page = window.pages['smart_splitting']; (tmp_path/'a').mkdir()
    first = make(tmp_path/'a'/'Flans - 3 mm - 1 adet.dxf', radius=120); second = make(tmp_path/'Flans - 2 mm - 1 adet.dxf', radius=90)
    page.load_files([first, second]); finish(window, qtbot)
    assert [s.code for s in page.sources] == ['Flans', 'Flans_2']
    page.load_files([second]); finish(window, qtbot)                       # the same file again is not added twice
    assert len(page.sources) == 2
    page.form.set_value('count', 3); page.run_all(); finish(window, qtbot); page.transfer()
    codes = [p.code for p in window.pages['nesting'].project.parts]
    assert len(codes) == 6 and len(set(codes)) == 6 and 'Flans_2_SEG_001' in codes


def test_a_failed_batch_transfer_leaves_nesting_exactly_as_it_was(window, qtbot, tmp_path, monkeypatch):
    from modules.smart_splitting import adapter
    from modules.smart_splitting.tests.test_geometry import circle_dxf as make
    page = window.pages['smart_splitting']; nesting = window.pages['nesting']
    page.load_files([make(tmp_path/'A - 1 adet.dxf', radius=80), make(tmp_path/'B - 1 adet.dxf', radius=70)]); finish(window, qtbot)
    page.form.set_value('count', 3); page.form.set_value('gap', 7); page.run_all(); finish(window, qtbot)
    parts = [p.id for p in nesting.project.parts]; gap = nesting.project.options.gap
    transfers = dict(getattr(nesting, '_split_transfers', {})); real = adapter.transfer_to_nesting; calls = []

    def second_fails(target, solution):
        calls.append(solution)
        if len(calls) == 2: raise ValueError('ikinci parça aktarılamadı')
        return real(target, solution)
    monkeypatch.setattr(adapter, 'transfer_to_nesting', second_fails)
    page.transfer()
    assert [p.id for p in nesting.project.parts] == parts and nesting.project.options.gap == gap
    assert getattr(nesting, '_split_transfers', {}) == transfers and 'ikinci parça' in page.status_text


def test_export_suggests_the_name_of_the_part_that_was_split(window, qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from modules.smart_splitting.tests.test_geometry import circle_dxf as make
    page = window.pages['smart_splitting']
    page.load_files([make(tmp_path/'Bir - 1 adet.dxf', radius=80), make(tmp_path/'Iki - 1 adet.dxf', radius=70)]); finish(window, qtbot)
    page.form.set_value('count', 3); page.source_picker.setCurrentIndex(0); page.run_split(); finish(window, qtbot)
    page.source_picker.setCurrentIndex(1); asked = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda parent, title, name, *rest: (asked.append(name), ('', ''))[1])
    page.export_dialog()
    assert asked == ['Bir_SEGMENTLER']
