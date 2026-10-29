"""Real Qt/settings/worker/XLSX flow; only CAD image acquisition is mocked."""

from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook
from PIL import Image
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QFileDialog
import pytest

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.bom import exporter as bom, images
from modules.bom.ui import BomPage


@pytest.fixture
def make_page(qtbot, tmp_path):
    create_application([])
    pages = []

    def make():
        context = SimpleNamespace(settings=SettingsStore(tmp_path/'settings.json'),
                                  jobs=JobManager(), appearance='dark')
        page = BomPage(context)
        qtbot.addWidget(page)
        page.resize(1100, 780)
        page.show()
        pages.append(page)
        return page

    yield make
    for page in pages:
        if page.jobs.busy:
            page.jobs.cancel()
            qtbot.waitUntil(lambda: not page.jobs.busy, timeout=8000)
        page.settings.flush()


def test_image_option_is_visible_and_remembers_both_choices(make_page):
    page = make_page()
    assert page.include_images.isVisible() and page.include_images.isChecked()
    page.include_images.click()
    page.clear()
    assert not page.include_images.isChecked()
    assert page.settings.flush()
    again = make_page()
    assert not again.include_images.isChecked()
    again.include_images.click()
    assert again.settings.flush()
    assert make_page().include_images.isChecked()


@pytest.mark.parametrize('include_images', [False, True])
def test_excel_option_controls_real_worker_output_and_status(make_page, qtbot, tmp_path,
                                                           monkeypatch, include_images):
    page = make_page()
    result = bom.Result('C:/Assembly.SLDASM', 'Default',
                        (bom.Part('Part', 'C:/Part.SLDPRT', 'Default', 2, 1.25, 2.5),),
                        (bom.Node('1', '', 1, 'Assembly', 'Assembly', 'Montaj',
                                  'C:/Assembly.SLDASM', 'Default', 2.5),
                         bom.Node('1.1', '1', 2, 'Part', 'Part-1', 'Parça',
                                  'C:/Part.SLDPRT', 'Default', 1.25),
                         bom.Node('1.2', '1', 2, 'Part', 'Part-2', 'Parça',
                                  'C:/Part.SLDPRT', 'Default', 1.25)), 0, 0, False)
    page.load_result(result)
    page.include_images.setChecked(include_images)
    capture_threads = []

    def capture(scanned, *args, **kwargs):
        capture_threads.append(QThread.currentThread())
        assert scanned is result
        with BytesIO() as stream:
            with Image.new('RGB', (24, 24), 'steelblue') as bitmap:
                bitmap.save(stream, format='PNG')
            preview = images.Preview(stream.getvalue(), '')
        return {bom.sw._part_key('C:/Part.SLDPRT', 'Default'): preview}

    monkeypatch.setattr(images, 'collect_previews', capture)
    path = tmp_path/'BOM.xlsx'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    page.export_button.click()
    assert not page.include_images.isEnabled() and page.stop_button.isEnabled()
    qtbot.waitUntil(lambda: not page.jobs.busy, timeout=8000)
    assert page.include_images.isEnabled() and page.export_button.isEnabled()
    assert not page.stop_button.isEnabled()
    assert len(capture_threads) == int(include_images)
    assert all(thread is not QApplication.instance().thread() for thread in capture_threads)
    assert path.is_file() and page.status_text.startswith('Excel kaydedildi: ')
    assert ('izometrik görsel' in page.status_text) == include_images
    assert 'görseli alınamadı' not in page.status_text
    assert page.result is result
    book = load_workbook(path)
    try:
        flat, tree = book.worksheets
        assert (flat.max_column, tree.max_column) == (9+int(include_images), 11+int(include_images))
        assert (flat.max_row, tree.max_row) == (5, 7)
        assert flat['C5'].value == 2 and flat['H5'].value == 2.5
        assert len(flat._images) == int(include_images)
        assert len(tree._images) == 2*int(include_images)
        assert tree['J6'].value == tree['J7'].value == 1.25
        assert all(sheet['E1'].value == 2.5 for sheet in book)
    finally:
        book.close()
