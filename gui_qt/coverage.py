"""What a tool really covers: supported / partial / unsupported, shown next to its results.

A PASS of a tool means only the checks listed as supported (and the stated part of
the partial ones) passed; everything else is named here instead of being skipped
silently.
"""
from PySide6.QtWidgets import QGridLayout, QWidget

from .components import label

SUPPORTED, PARTIAL, UNSUPPORTED = 'supported', 'partial', 'unsupported'
LEVELS = {SUPPORTED: ('✓ Destekleniyor', 'success'), PARTIAL: ('◐ Kısmi', 'warning'),
          UNSUPPORTED: ('✕ Desteklenmiyor', 'error')}


def coverage_text(items):
    """Plain text (reports, tooltips, accessibility)."""
    return '\n'.join(f'{LEVELS[level][0]} · {topic}: {note}' for topic, level, note in items)


class CoverageList(QWidget):
    """One row per topic: level badge, topic and the precise limit."""

    def __init__(self, items, intro=''):
        super().__init__()
        grid = QGridLayout(self); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(6)
        row = 0
        if intro:
            grid.addWidget(label(intro, 'muted'), row, 0, 1, 2); row += 1
        for topic, level, note in items:
            text, role = LEVELS[level]
            badge = label(text, role, wrap=False)
            grid.addWidget(badge, row, 0)
            grid.addWidget(label(f'<b>{topic}</b> — {note}'), row, 1)
            row += 1
        grid.setColumnStretch(1, 1)
        self.items = tuple(items)
        self.setAccessibleName('Kapsam')
        self.setAccessibleDescription(coverage_text(items))
