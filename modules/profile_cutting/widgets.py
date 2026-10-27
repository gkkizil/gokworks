"""Plain-language presentation of the existing, validated 1D plan."""

from decimal import Decimal
from itertools import groupby

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QHeaderView

from gui_qt.components import label, configure_view
from gui_qt.diagrams import EngineeringDiagram
from gui_qt.models import TableModel, Column
from .models import number


def mm(value):
    return format(number(value).normalize(), 'f').replace('.', ',')


def source_name(value):
    return str(value).replace('\\', '/').rsplit('/', 1)[-1]


def group_name(group):
    section, thickness, material, standard, stock_code = group
    parts = [section, material]
    if thickness:
        parts.append(f'et {mm(thickness)} mm')
    if standard:
        parts.append(standard)
    if stock_code:
        parts.append('Kod: ' + stock_code)
    return ' · '.join(v for v in parts if v)


def cut_pattern(bar):
    """Compress consecutive identical cuts while retaining their actual order."""
    groups = groupby(bar.cuts, key=lambda c: (c.length, c.allowance))
    parts = []
    for (length, allowance), cuts in groups:
        count = sum(1 for _ in cuts)
        text = f'{count} × {mm(length)} mm'
        if number(allowance):
            text += f' (+{mm(allowance)} mm/parça)'
        parts.append(text)
    return ' → '.join(parts)


def plan_totals(plan):
    stock = number(plan.stock_length) * len(plan.bars)
    parts = sum((number(c.length) + number(c.allowance) for b in plan.bars for c in b.cuts), Decimal(0))
    count = sum(len(b.cuts) for b in plan.bars)
    return dict(bars=len(plan.bars), count=count, stock=stock, parts=parts,
                remaining=sum((number(b.remaining) for b in plan.bars), Decimal(0)),
                saw=number(plan.kerf) * count, trim=number(plan.trim) * 2 * len(plan.bars),
                usage=parts / stock * 100 if stock else Decimal(0))


class CutOrder(QWidget):
    """Selected stock's scaled geometry and an unsortable, exact cut sequence."""
    def __init__(self, context):
        super().__init__()
        self.context = context
        body = QVBoxLayout(self); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(6)
        self.caption = label('Bir çubuk seçin.', 'section'); body.addWidget(self.caption)
        self.diagram = EngineeringDiagram(width=650, height=160)
        self.diagram.setMinimumHeight(130); self.diagram.setMaximumHeight(200)
        body.addWidget(self.diagram)
        self.legend = label('Mavi: parça · İnce aralık: testere payı · Gri: artan profil', 'muted')
        body.addWidget(self.legend)
        body.addWidget(label('Bu çubuktaki kesim sırası', 'section'))
        self.model = TableModel((Column('Sıra', 'order'), Column('Parça boyu · mm', 'length', mm),
            Column('İlave boy · mm', 'allowance', mm), Column('Testere payı · mm', 'kerf', mm)))
        self.table = configure_view(QTableView()); self.table.setModel(self.model)
        self.table.setSortingEnabled(False)
        self.table.setAccessibleName('Seçili çubuğun değiştirilmeyen kesim sırası')
        self.table.setMinimumHeight(100)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        body.addWidget(self.table, 1)

    def clear(self):
        self.caption.setText('Bir çubuk seçin.')
        self.model.replace([])
        # Deleting items alone leaves EngineeringDiagram's old resize renderer
        # alive and can repaint an invalidated plan after the inputs change.
        self.diagram.renderer = None
        self.diagram.vector.delete('all')

    def show_bar(self, plan, index):
        bar = plan.bars[index]
        self.caption.setText(f'{index + 1}. çubuk · {group_name(bar.group)}')
        self.model.replace([dict(order=i + 1, length=number(c.length),
            allowance=number(c.allowance), kerf=number(plan.kerf)) for i, c in enumerate(bar.cuts)])
        self.table.setColumnHidden(2, not any(number(c.allowance) for c in bar.cuts))

        def draw(scene):
            scene.delete('all')
            dark = self.context.appearance == 'dark'
            text = '#E8EEF7' if dark else '#203550'
            waste = '#41464D' if dark else '#DFE3E8'
            scene.configure(background='#1C2533' if dark else '#F4F7FC')
            scale = 610 / float(plan.stock_length)
            trim = float(plan.trim) * scale
            left = 20 + trim
            scene.create_rectangle(20, 42, 630, 94, outline=text, tags='stock')
            if trim:
                scene.create_rectangle(20, 42, left, 94, fill=waste, outline='', tags='trim')
                scene.create_rectangle(630-trim, 42, 630, 94, fill=waste, outline='', tags='trim')
            for order, cut in enumerate(bar.cuts, 1):
                width = float(number(cut.length) + number(cut.allowance)) * scale
                part = scene.create_rectangle(left, 42, left+width, 94,
                    fill='#80B6F5', outline=text, tags='cut')
                part.setToolTip(f'{order}. kesim · {mm(cut.length)} mm · İlave {mm(cut.allowance)} mm')
                if width > 55:
                    scene.create_text(left+width/2, 68, text=mm(cut.length),
                        fill='#10233A', font=('Segoe UI', -12))
                left += width
                saw = float(plan.kerf) * scale
                if saw:
                    scene.create_rectangle(left, 42, left+saw, 94, fill=waste, outline='', tags='kerf')
                left += saw
            if number(bar.remaining):
                remaining = scene.create_rectangle(left, 42, 630-trim, 94, fill=waste, outline='', tags='remaining')
                remaining.setToolTip(f'Artan profil: {mm(bar.remaining)} mm')
            scene.create_text(325, 18, text=f'Ham çubuk: {mm(plan.stock_length)} mm',
                fill=text, width=630, font=('Segoe UI', -12))
            scene.create_text(325, 125, text=f'{len(bar.cuts)} parça · Artan: {mm(bar.remaining)} mm · '
                f'Testere payı: {mm(plan.kerf)} mm/kesim', fill=text, width=630, font=('Segoe UI', -12))
        self.diagram.render_geometry(draw)
