"""Workshop cut list export: every profile with length, quantity and angles (PDF / Excel)."""
import shutil
import subprocess
from decimal import Decimal

import pytest
from openpyxl import load_workbook
from PySide6.QtWidgets import QFileDialog

from modules.profile_cutting.cutlist import export_excel, export_pdf, from_project, from_scan
from modules.profile_cutting.models import Demand, Project, ScanResult, ScanRow
from .test_ui import page  # noqa: F401  (window fixture)


def scan_result():
    rows = [ScanRow(str(i), 'C:/m/PLATFORM.SLDPRT', 'Varsayılan', folder, profile, 'ST-37', length, count, a1, a2)
            for i, (folder, profile, length, count, a1, a2) in enumerate((
                ('60 x 40 x 5.0<55>', '60 x 40 x 5.0', '152.9', 4, '45', '0'),
                ('60 x 40 x 5.0<57>', '60 x 40 x 5.0', '152.9', 2, '45', '0'),      # same piece: merged
                ('60 x 40 x 5.0<52>', '60 x 40 x 5.0', '857.32', 2, '45', '45'),
                ('100 x 50 x 4.0<3>', '100 x 50 x 4.0', '255', 2, '30', ''),
                ('40 x 40 x 3.2<1>', '40 x 40 x 3.2', '861.76', 2, '', ''),
                ('60 x 40 x 5.0<9>', '60 x 40 x 5.0', '', 1, '', '')))]          # no length: listed apart
    rows.append(ScanRow('plate', 'C:/m/PLATFORM.SLDPRT', 'Varsayılan', 'Kesim Listesi Öğesi45', '', 'S235', '', 2,
                        excluded=True))
    return ScanResult('C:/m/PLATFORM.SLDPRT', 'Varsayılan', rows)


def test_cut_list_merges_identical_pieces_groups_by_section_and_sorts_longest_first():
    cut = from_scan(scan_result())
    assert [g.profile for g in cut.groups] == ['40 x 40 x 3.2', '60 x 40 x 5.0', '100 x 50 x 4.0']
    sixty = cut.groups[1]
    assert [(str(l.length), l.count, l.angle1, l.angle2) for l in sixty.lines] == [
        ('857.32', 2, '45', '45'), ('152.9', 6, '45', '0')]
    assert sixty.count == 8 and sixty.total == Decimal('857.32')*2 + Decimal('152.9')*6
    assert cut.count == 12 and cut.excluded == 1
    assert cut.missing and 'PLATFORM / 60 x 40 x 5.0<9>' == cut.missing[0][0]


def test_excel_has_one_row_per_piece_with_numbers_angles_and_totals(tmp_path):
    path = tmp_path/'kesim.xlsx'
    export_excel(from_scan(scan_result()), path)
    book = load_workbook(path)
    assert book.sheetnames == ['Kesim listesi', 'Özet', 'Eksik bilgi']
    sheet = book['Kesim listesi']
    rows = [r for r in sheet.iter_rows(values_only=True) if isinstance(r[0], int)]
    assert [(r[1], r[3], r[4], r[5], r[6]) for r in rows] == [
        ('40 x 40 x 3.2', 861.76, 2, None, None),
        ('60 x 40 x 5.0', 857.32, 2, 45.0, 45.0), ('60 x 40 x 5.0', 152.9, 6, 45.0, 0.0),
        ('100 x 50 x 4.0', 255.0, 2, 30.0, None)]
    total = next(r for r in sheet.iter_rows(values_only=True) if r[1] == 'TOPLAM')
    assert total[4] == 12
    summary = list(book['Özet'].iter_rows(values_only=True))
    assert summary[2][:3] == ('60 x 40 x 5.0', 'ST-37', 8)


@pytest.mark.skipif(not shutil.which('pdftotext'), reason='pdftotext not installed')
def test_pdf_lists_each_profile_with_length_quantity_and_angles(qtbot, tmp_path):
    path = tmp_path/'kesim.pdf'
    export_pdf(from_scan(scan_result()), path)
    assert path.read_bytes().startswith(b'%PDF-')
    text = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True).stdout
    for expected in ('Profil kesim listesi', '60 x 40 x 5.0', '857,32', '152,9', '45°', '30°', 'Eksik bilgi', '12 parça'):
        assert expected in text, expected


def test_parts_list_export_uses_the_entered_parts():
    project = Project([Demand('a', '40×40×2', 'S235JR', '1200', 4, angle1='45'), Demand('b', '40×40×2', 'S235JR', '1200', 2, angle1='45')])
    cut = from_project(project)
    assert len(cut.groups) == 1 and cut.groups[0].lines[0].count == 6


def test_solidworks_tab_buttons_save_the_scanned_cut_list(page, qtbot, tmp_path, monkeypatch):  # noqa: F811
    p, w = page
    p.handle_events([('weldment_scan', scan_result())])
    assert p.scan_pdf_button.isEnabled() and p.scan_excel_button.isEnabled()
    assert p.scan_proxy.rowCount() == 6                                 # profiles shown; the plate is filtered
    target = tmp_path/'liste'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    p.scan_excel_button.click(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=10000)
    assert (tmp_path/'liste.xlsx').is_file() and 'Kesim listesi kaydedildi' in p.status_text
    p.scan_pdf_button.click(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=10000)
    assert (tmp_path/'liste.pdf').read_bytes().startswith(b'%PDF-')
