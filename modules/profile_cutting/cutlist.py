"""Workshop cut list: every profile with its length, quantity and end angles, as Excel or PDF.

The list is what the model (or the parts list) states. Identical pieces (same section,
material, length and both angles) are merged and their quantities added; pieces are
grouped by section + material and sorted longest first, the way a saw operator cuts.
Rows without a readable length or quantity are not guessed: they are listed apart as
"eksik bilgi" with their source, so nothing disappears silently.
"""
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path

from .models import number, quantity, checkpoint
from .storage import publish


@dataclass
class Line:
    profile: str
    material: str
    length: Decimal
    angle1: str
    angle2: str
    count: int = 0
    parts: list = field(default_factory=list)

    @property
    def total(self):
        return self.length * self.count


@dataclass
class Group:
    profile: str
    material: str
    lines: list

    @property
    def count(self):
        return sum(line.count for line in self.lines)

    @property
    def total(self):
        return sum((line.total for line in self.lines), Decimal(0))


@dataclass
class CutList:
    title: str
    source: str
    groups: list
    missing: list            # (part, reason) rows that had no usable length/quantity
    excluded: int = 0
    created: str = ''

    @property
    def count(self):
        return sum(group.count for group in self.groups)

    @property
    def total(self):
        return sum((group.total for group in self.groups), Decimal(0))


def angle(value):
    """Angle as written in the model; empty when the model has none."""
    text = str(value or '').strip()
    if not text:
        return ''
    try:
        return format(number(text, 'Açı').normalize(), 'f')
    except ValueError:
        return text


def _merge(entries):
    merged = OrderedDict()
    for profile, material, length, a1, a2, count, part in entries:
        key = (profile.strip(), material.strip(), length, a1, a2)
        line = merged.get(key)
        if line is None:
            line = merged[key] = Line(profile.strip(), material.strip(), length, a1, a2)
        line.count += count
        if part and part not in line.parts:
            line.parts.append(part)
    groups = OrderedDict()
    for line in merged.values():
        groups.setdefault((line.profile.upper(), line.material.upper()), []).append(line)
    result = []
    for key in sorted(groups, key=_natural):
        lines = sorted(groups[key], key=lambda l: (-l.length, l.angle1, l.angle2))
        result.append(Group(lines[0].profile, lines[0].material, lines))
    return result


def _natural(key):
    """'40 x 40' before '100 x 50': numbers compare as numbers."""
    import re
    return [tuple((0, Decimal(part.replace(',', '.'))) if re.fullmatch(r'\d+(?:[.,]\d+)?', part) else (1, part)
                  for part in re.split(r'(\d+(?:[.,]\d+)?)', text) if part) for text in key]


def from_scan(scan):
    entries, missing, excluded = [], [], 0
    for row in scan.rows:
        part = f'{Path(row.source).stem} / {row.folder}'
        if row.excluded:
            excluded += 1
            continue
        try:
            if not row.profile.strip():
                raise ValueError('Profil kesiti okunamadı.')
            if not str(row.length).strip():
                raise ValueError('Kesim listesinde boy (LENGTH) yok.')
            length = number(row.length, 'Boy', positive=True)
            count = quantity(row.count)
        except ValueError as error:
            missing.append((part, str(error)))
            continue
        entries.append((row.profile, row.material, length, angle(row.angle1), angle(row.angle2), count, row.folder))
    title = Path(scan.source).name + (f' · {scan.configuration}' if scan.configuration else '')
    return CutList(title, scan.source, _merge(entries), missing, excluded, _now())


def from_project(project, title='Kesim listesi'):
    entries = [(d.profile, d.material, number(d.length, 'Boy', positive=True), angle(d.angle1), angle(d.angle2),
                quantity(d.count), d.source if d.source != 'Manuel' else '') for d in project.demands]
    return CutList(title, '', _merge(entries), [], 0, _now())


def _now():
    return datetime.now().strftime('%d.%m.%Y %H:%M')


def mm(value):
    text = format(Decimal(value).quantize(Decimal('0.01')).normalize(), 'f')
    return text.replace('.', ',')


def metres(value):
    return format(Decimal(value) / 1000, '.2f').replace('.', ',')


def degrees(value):
    return (value.replace('.', ',') + '°') if value else '—'


# ----------------------------------------------------------------------------- Excel
def export_excel(cut_list, path, *, plan=None, stop=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    head_fill = PatternFill('solid', fgColor='1F2937')
    group_fill = PatternFill('solid', fgColor='E5E7EB')
    thin = Side(style='thin', color='D1D5DB')
    border = Border(bottom=thin)
    white = Font(bold=True, color='FFFFFF')

    def write(temporary):
        book = Workbook()
        sheet = book.active; sheet.title = 'Kesim listesi'
        sheet.append(['Profil kesim listesi']); sheet['A1'].font = Font(bold=True, size=14)
        sheet.append([cut_list.title])
        sheet.append([f'{cut_list.count} parça · toplam {metres(cut_list.total)} m · {cut_list.created}'])
        sheet.append([])
        headers = ['Poz', 'Profil', 'Malzeme', 'Boy (mm)', 'Adet', 'Açı 1 (°)', 'Açı 2 (°)', 'Toplam boy (m)', 'Parça']
        sheet.append(headers)
        header_row = sheet.max_row
        for cell in sheet[header_row]:
            cell.font = white; cell.fill = head_fill; cell.alignment = Alignment(horizontal='center', vertical='center')
        position = 0
        for group in cut_list.groups:
            checkpoint(stop)
            sheet.append(['', f'{group.profile}', group.material, '', group.count, '', '', float(group.total / 1000), ''])
            for cell in sheet[sheet.max_row]:
                cell.font = Font(bold=True); cell.fill = group_fill
            for line in group.lines:
                position += 1
                sheet.append([position, line.profile, line.material, float(line.length), line.count,
                              float(line.angle1) if _numeric(line.angle1) else (line.angle1 or None),
                              float(line.angle2) if _numeric(line.angle2) else (line.angle2 or None),
                              float(line.total / 1000), ', '.join(line.parts)])
                for cell in sheet[sheet.max_row]:
                    cell.border = border
        sheet.append([])
        sheet.append(['', 'TOPLAM', '', '', cut_list.count, '', '', float(cut_list.total / 1000), ''])
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
        for row in sheet.iter_rows(min_row=header_row + 1):
            row[3].number_format = '0.0#'; row[7].number_format = '0.00'
            for index in (0, 3, 4, 5, 6, 7):
                row[index].alignment = Alignment(horizontal='right')
        for index, width in enumerate((6, 22, 14, 11, 7, 10, 10, 15, 40), 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
        sheet.auto_filter.ref = f'A{header_row}:I{sheet.max_row}'
        sheet.print_options.gridLines = False
        sheet.page_setup.orientation = 'portrait'; sheet.page_setup.fitToWidth = 1; sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.print_title_rows = f'{header_row}:{header_row}'

        summary = book.create_sheet('Özet')
        summary.append(['Profil', 'Malzeme', 'Adet', 'Toplam boy (m)'])
        for cell in summary[1]:
            cell.font = white; cell.fill = head_fill
        for group in cut_list.groups:
            summary.append([group.profile, group.material, group.count, float(group.total / 1000)])
            summary.cell(row=summary.max_row, column=4).number_format = '0.00'
        summary.append(['TOPLAM', '', cut_list.count, float(cut_list.total / 1000)])
        for cell in summary[summary.max_row]:
            cell.font = Font(bold=True)
        summary.cell(row=summary.max_row, column=4).number_format = '0.00'
        for index, width in enumerate((24, 14, 8, 15), 1):
            summary.column_dimensions[get_column_letter(index)].width = width

        if cut_list.missing:
            gaps = book.create_sheet('Eksik bilgi')
            gaps.append(['Parça', 'Neden']); [setattr(c, 'font', Font(bold=True)) for c in gaps[1]]
            for part, reason in cut_list.missing:
                gaps.append([part, reason])
            gaps.column_dimensions['A'].width = 45; gaps.column_dimensions['B'].width = 50

        if plan is not None:
            bars = book.create_sheet('Kesim planı')
            bars.append(['Çubuk', 'Profil / malzeme', 'Kesimler (mm)', 'Artan (mm)'])
            for cell in bars[1]:
                cell.font = white; cell.fill = head_fill
            for index, bar in enumerate(plan.bars, 1):
                checkpoint(stop)
                bars.append([index, ' / '.join(str(v) for v in bar.group if v),
                             ' + '.join(mm(cut.length) for cut in bar.cuts), float(number(bar.remaining))])
            for index, width in enumerate((8, 28, 60, 12), 1):
                bars.column_dimensions[get_column_letter(index)].width = width
        checkpoint(stop)
        book.save(temporary)
    return publish(path, write, stop)


def _numeric(value):
    try:
        number(value); return True
    except ValueError:
        return False


# ----------------------------------------------------------------------------- PDF
def html(cut_list):
    parts = [f'''<html><body style="font-family:Arial; color:#111827">
<h2 style="margin:0">Profil kesim listesi</h2>
<p style="margin:2px 0 10px 0; color:#374151">{escape(cut_list.title)}<br>
{cut_list.count} parça &nbsp;·&nbsp; toplam {metres(cut_list.total)} m &nbsp;·&nbsp; {cut_list.created}</p>''']
    position = 0
    for group in cut_list.groups:
        parts.append(f'''<h3 style="margin:14px 0 4px 0">{escape(group.profile)} &nbsp;
<span style="font-weight:normal; color:#374151">{escape(group.material)} · {group.count} adet · {metres(group.total)} m</span></h3>
<table width="100%" cellspacing="0" cellpadding="4" style="border-collapse:collapse">
<tr style="background:#1f2937; color:#ffffff">
<th align="right" width="7%">Poz</th><th align="right" width="15%">Boy (mm)</th><th align="right" width="9%">Adet</th>
<th align="right" width="12%">Açı 1</th><th align="right" width="12%">Açı 2</th><th align="left">Parça</th></tr>''')
        for index, line in enumerate(group.lines):
            position += 1
            shade = ' style="background:#f3f4f6"' if index % 2 else ''
            parts.append(f'''<tr{shade}><td align="right">{position}</td><td align="right"><b>{mm(line.length)}</b></td>
<td align="right"><b>{line.count}</b></td><td align="right">{degrees(line.angle1)}</td><td align="right">{degrees(line.angle2)}</td>
<td style="color:#4b5563">{escape(', '.join(line.parts))}</td></tr>''')
        parts.append('</table>')
    if cut_list.missing:
        parts.append('<h3 style="margin:16px 0 4px 0">Eksik bilgi — listeye girmedi</h3><table cellpadding="3">')
        for part, reason in cut_list.missing:
            parts.append(f'<tr><td>{escape(part)}</td><td style="color:#4b5563">{escape(reason)}</td></tr>')
        parts.append('</table>')
    parts.append('<p style="margin-top:14px; color:#6b7280; font-size:8pt">Açılar SolidWorks kesim listesindeki '
                 'ANGLE1 / ANGLE2 değerleridir. Boylar mm, toplamlar metredir.</p></body></html>')
    return ''.join(parts)


def export_pdf(cut_list, path, *, stop=None):
    def write(temporary):
        from PySide6.QtCore import QMarginsF, QSizeF
        from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
        writer = QPdfWriter(str(temporary)); writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(QMarginsF(12, 12, 12, 14), QPageLayout.Millimeter)
        writer.setTitle('Profil kesim listesi · ' + cut_list.title); writer.setCreator('GOKWORKS')
        document = QTextDocument(); document.setDocumentMargin(0)
        font = QFont('Arial'); font.setPointSizeF(9.5); document.setDefaultFont(font)
        document.documentLayout().setPaintDevice(writer)
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        checkpoint(stop)
        document.setHtml(html(cut_list))
        document.print_(writer)
    return publish(path, write, stop)
