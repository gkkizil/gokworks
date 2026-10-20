"""Inspect real Qt PDFs without adding a PDF parsing dependency to the product."""

import re
from threading import Event

import ezdxf
import pytest
from PySide6.QtCore import QModelIndex, QSize
from PySide6.QtGui import QColor, QPalette
from PySide6.QtPdf import QPdfDocument, QPdfLinkModel

from nesting.dxf_import import read_dxf
from nesting.materials import new_project
from nesting.models import Placement, Result
from nesting.report import export_pdf


def sample(tmp_path, quantity=1):
    source = tmp_path/'source.dxf'
    cad = ezdxf.new('R2018'); cad.units = 4
    cad.modelspace().add_lwpolyline([(0,0), (5,0), (5,5), (0,5)], close=True)
    cad.saveas(source)
    project = new_project(); project.name = 'PDF okunabilirlik kontrolü'
    project.parts = read_dxf(source, quantity=quantity)
    project.parts[0].code = 'BULK-PART'
    project.sheets[0].width = project.sheets[0].height = 200
    project.sheets[0].price_kg = 45
    project.options.margin = 5; project.options.gap = 1
    result = Result(project.fingerprint(), [
        Placement(project.parts[0].id, index+1, project.sheets[0].id, 1,
                  10+(index % 10)*15, 10+(index // 10)*15, 0)
        for index in range(quantity)], [], 'GOKWORKS NFP', '1.1', 0, 1, '2026-10-20T12:00:00+00:00')
    return project, result, source


def read_pdf(path):
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    assert document.status() == QPdfDocument.Status.Ready
    return document


def test_pdf_dark_and_light_palettes_have_identical_dark_printed_text(tmp_path, qapp):
    project, result, source = sample(tmp_path)
    long_code = 'UZUNPARCAKODU'*7+'KODSONU'
    project.parts[0].code = long_code
    result.digest = project.fingerprint()
    before = source.read_bytes(); palette = qapp.palette()
    rendered = []; texts = []
    try:
        for theme, foreground in [('light', '#17212b'), ('dark', '#eeeeee')]:
            themed = QPalette(palette)
            for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
                themed.setColor(role, QColor(foreground))
            qapp.setPalette(themed)
            path = tmp_path/f'{theme}.pdf'; export_pdf(project, result, path)
            document = read_pdf(path)
            texts.append([document.getAllText(page).text() for page in range(document.pageCount())])
            rendered.append([document.render(page, QSize(595, 842)) for page in range(document.pageCount())])
            # Sources are retained in project/Excel; a reader cannot auto-open
            # a GitHub URL from this production PDF.
            assert 'github' not in ''.join(texts[-1]).lower()
            links = QPdfLinkModel(); links.setDocument(document)
            for page in range(document.pageCount()):
                links.setPage(page)
                assert links.rowCount(QModelIndex()) == 0
            document.close()
        assert texts[0] == texts[1]
        assert rendered[0] == rendered[1]
        # Check actual glyph pixels in the title, where the previous pale
        # theme-derived output had no dark ink. Borders cannot satisfy this.
        title = rendered[1][0]
        ink = sum(title.pixelColor(x, y).alpha() == 255 and title.pixelColor(x, y).lightness() < 100
                  for x in range(32, 560) for y in range(32, 64))
        assert ink > 700
        for image in rendered[1]:
            for x, y in [(5, 5), (580, 5), (5, 830), (580, 830)]:
                assert image.pixelColor(x, y) == QColor('#ffffff')
        assert 'Genel toplam TL:' in texts[1][0]
        assert '7850' in ''.join(texts[1])
        assert long_code+'#1' in re.sub(r'[\s\u200b]', '', ''.join(texts[1]))
        assert source.read_bytes() == before
    finally:
        qapp.setPalette(palette)


def test_pdf_wraps_long_fields_and_repeats_table_headers_without_losing_instances(tmp_path, qapp):
    project, result, source = sample(tmp_path, quantity=90)
    description = 'UZUNACIKLAMAHARFLERI'*15+'ACIKLAMASONU'
    project.parts[0].description = description
    project.parts[0].source_sha256 = '0123456789abcdef'*4
    project.materials[0].name = 'UZUNMALZEMEADI'*3+'SON'
    result.digest = project.fingerprint()
    before = source.read_bytes()
    path = tmp_path/'many-pages.pdf'; export_pdf(project, result, path)
    document = read_pdf(path)
    pages = [document.getAllText(page).text() for page in range(document.pageCount())]
    plain = re.sub(r'[\s\u200b]', '', ''.join(pages))
    assert description in plain
    assert project.parts[0].source_sha256 in plain
    assert project.materials[0].name in plain
    instance_pages = []
    found = []
    for index, page in enumerate(pages):
        markers = list(re.finditer(r'BULK-PART\s+#(\d+)\b', page))
        if not markers:
            continue
        instance_pages.append(index)
        assert 'Parça / örnek' in page
        assert 'Malzeme TL' in page
        for marker in markers:
            found.append(int(marker[1]))
            bounds = document.getSelectionAtIndex(index, marker.start(), len(marker[0])).boundingRectangle()
            assert bounds.left() >= 30
            assert bounds.right() <= document.pagePointSize(index).width()-30
            assert bounds.top() >= 30
            assert bounds.bottom() < document.pagePointSize(index).height()-50
    assert len(instance_pages) >= 3
    assert sorted(found) == list(range(1, 91))
    assert document.pageCount() < 12
    assert source.read_bytes() == before
    document.close()


def test_pdf_cancel_during_pagination_preserves_existing_report_and_source(tmp_path, qapp, monkeypatch):
    import nesting.report as report
    project, result, source = sample(tmp_path, quantity=90)
    path = tmp_path/'report.pdf'; path.write_bytes(b'existing report')
    before = source.read_bytes(); stop = Event(); calls = 0
    original = report.check_cancel

    def cancel_on_second_page(event):
        nonlocal calls
        calls += 1
        if calls == 2:
            event.set()
        original(event)

    monkeypatch.setattr(report, 'check_cancel', cancel_on_second_page)
    with pytest.raises(InterruptedError):
        export_pdf(project, result, path, overwrite=True, stop=stop)
    assert calls == 2
    assert path.read_bytes() == b'existing report'
    assert source.read_bytes() == before
    assert not list(tmp_path.glob('.gokworks-stack-*'))
