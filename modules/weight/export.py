"""CSV / XLSX / PDF reports for the weight calculation list.

Numbers stay numbers: XLSX cells hold floats with a number format (no text with a
decimal comma), CSV uses ';' and a decimal comma as Turkish Excel expects.
Files are written to a temporary sibling and moved into place when complete.
"""

from html import escape
import csv
from datetime import datetime
import os
from pathlib import Path
from tempfile import mkstemp

from modules.weight.rules import fmt_fixed
from modules.weight.worklist import COST_NOTE, totals

COLUMNS = ('Parça adı', 'Malzeme', 'Yoğunluk (kg/m³)', 'Kesit / profil', 'Ölçüler (mm)', 'Yöntem', 'Boy (mm)',
           'Adet', 'kg/m', 'Birim ağırlık (kg)', 'Toplam ağırlık (kg)', 'Birim fiyat (TL/kg)', 'Toplam tutar (TL)',
           'Kaynak')
DIGITS = (None, None, 0, None, None, None, 1, 0, 3, 3, 3, 2, 2, None)


def rows(items):
    for i in items:
        yield (i.name, i.material, i.density, i.section, i.dimensions, i.method, i.length_mm, i.count, i.kg_per_m,
               i.unit_mass_kg, i.total_mass_kg, i.price_per_kg, i.total_price, i.source)


def summary(items, scrap, vat):
    t = totals(items, scrap, vat)
    lines = [('Toplam adet', t.count, 0), ('Toplam ağırlık (kg)', t.mass_kg, 3),
             (f'Fire dahil ağırlık (kg) · %{fmt_fixed(t.scrap_percent, 1)}', t.mass_with_scrap_kg, 3)]
    if t.unpriced_rows < len(items):
        lines += [('Malzeme tutarı, KDV hariç (TL)', t.net, 2), (f'KDV %{fmt_fixed(t.vat_percent, 1)} (TL)', t.vat, 2),
                  ('Malzeme tutarı, KDV dahil (TL)', t.gross, 2)]
    return t, lines


def _atomic(path, write):
    path = Path(path)
    fd, name = mkstemp(prefix='.gokworks-weight-', suffix=path.suffix, dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        write(temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _cell(value, digits):
    if value is None:
        return ''
    if digits is None:
        return str(value)
    return fmt_fixed(value, digits).replace('.', '')  # 1234,567: no thousands point in CSV


def export_csv(items, path, scrap=0, vat=0):
    _, lines = summary(items, scrap, vat)

    def write(temporary):
        with temporary.open('w', newline='', encoding='utf-8-sig') as stream:
            out = csv.writer(stream, delimiter=';')
            out.writerow(COLUMNS)
            for row in rows(items):
                out.writerow([_cell(v, d) for v, d in zip(row, DIGITS)])
            out.writerow([])
            for title, value, digits in lines:
                out.writerow([title, _cell(value, digits)])
            out.writerow([COST_NOTE])
    return _atomic(path, write)


def export_xlsx(items, path, scrap=0, vat=0):
    _, lines = summary(items, scrap, vat)

    def write(temporary):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        book = Workbook()
        sheet = book.active
        sheet.title = 'Ağırlık listesi'
        sheet.append(COLUMNS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='DDE3EA')
            cell.alignment = Alignment(wrap_text=True, vertical='top')
        for row in rows(items):
            sheet.append(list(row))
            for cell, digits in zip(sheet[sheet.max_row], DIGITS):
                if digits is not None and isinstance(cell.value, (int, float)):
                    cell.number_format = '#,##0' if digits == 0 else '#,##0.' + '0' * digits
        first = sheet.max_row + 2
        for offset, (title, value, digits) in enumerate(lines):
            sheet.cell(first + offset, 1, title).font = Font(bold=True)
            cell = sheet.cell(first + offset, 2, value)
            cell.number_format = '#,##0' if digits == 0 else '#,##0.' + '0' * digits
        sheet.cell(first + len(lines) + 1, 1, COST_NOTE)
        for column, width in zip('ABCDEFGHIJKLMN', (22, 18, 12, 22, 32, 16, 10, 7, 9, 12, 13, 12, 13, 50)):
            sheet.column_dimensions[column].width = width
        sheet.freeze_panes = 'A2'
        book.save(temporary)
    return _atomic(path, write)


def export_pdf(items, path, scrap=0, vat=0, *, image=None, detail_rows=()):
    """Plain technical A4 report; ``image`` (QImage) is the current section sketch."""
    _, lines = summary(items, scrap, vat)

    def write(temporary):
        from PySide6.QtCore import QMarginsF, QSizeF, QUrl
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
        html = ['<h2>GOKWORKS · Ağırlık hesabı</h2>',
                f'<p style="color:#555">{escape(datetime.now().strftime("%d.%m.%Y %H:%M"))}</p>']
        if detail_rows:
            html.append('<h3>Seçili hesap</h3><table cellpadding="3" cellspacing="0" border="1" width="100%">')
            html += [f'<tr><td width="38%">{escape(str(k))}</td><td>{escape(str(v))}</td></tr>' for k, v in detail_rows]
            html.append('</table>')
        if image is not None and not image.isNull():
            html.append('<p><img src="section://sketch" width="360"></p>')
        html.append('<h3>Hesaplama listesi</h3><table cellpadding="3" cellspacing="0" border="1" width="100%"><tr>')
        shown = (0, 1, 3, 6, 7, 8, 10, 11, 12)
        html += [f'<th>{escape(COLUMNS[i])}</th>' for i in shown] + ['</tr>']
        for row in rows(items):
            html.append('<tr>' + ''.join(
                f'<td align="{"left" if DIGITS[i] is None else "right"}">{escape(_cell(row[i], DIGITS[i]) if DIGITS[i] is not None else str(row[i]))}</td>'
                for i in shown) + '</tr>')
        html.append('</table><table cellpadding="3">')
        html += [f'<tr><td><b>{escape(t)}</b></td><td align="right">{escape(fmt_fixed(v, d))}</td></tr>' for t, v, d in lines]
        html.append(f'</table><p style="color:#555">{escape(COST_NOTE)}</p>')
        writer = QPdfWriter(str(temporary))
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Millimeter)
        writer.setTitle('GOKWORKS ağırlık hesabı')
        writer.setCreator('GOKWORKS')
        document = QTextDocument()
        # Print colours are fixed: the app may run in the dark theme (light text).
        document.setDefaultStyleSheet('body, p, td {font-size:9pt; color:#111111;} h2 {color:#24466C;} '
                                      'h3 {color:#111111;} th {background:#DDE3EA; color:#111111;} table {border-color:#888888;}')
        if image is not None and not image.isNull():
            document.addResource(QTextDocument.ImageResource, QUrl('section://sketch'), image)
        document.setHtml(''.join(html))
        # Qt paginates by text blocks, so a row or line is never cut at a page edge.
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.print_(writer)
        del writer
        content = temporary.read_bytes()
        if not content.startswith(b'%PDF-') or b'%%EOF' not in content[-1024:]:
            raise RuntimeError('PDF doğrulanamadı.')
    return _atomic(path, write)


__all__ = ['COLUMNS', 'export_csv', 'export_xlsx', 'export_pdf', 'rows', 'summary']
