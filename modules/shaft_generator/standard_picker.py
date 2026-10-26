"""Diameter-aware, offline channel dimension suggestions for the shaft editor."""

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget, QFormLayout, QVBoxLayout, QComboBox
from gui_qt.components import label
from gui_qt.theme import COLORS
from .standards import (DIN_471_SOURCE, DIN_6885_SOURCE, ISO_773_STATUS,
                        groove_size, keyway_size, keyway_lengths, same_dimension)


class ChannelStandardPicker(QWidget):
    valuesSelected = Signal(dict)

    def __init__(self, kind, appearance='dark'):
        super().__init__()
        self.kind = kind
        self.size = None
        self.values = {}
        self.lengths = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.preset = QComboBox()
        self.preset.setMinimumWidth(0)
        self.preset.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset.setMinimumContentsLength(10)
        title = 'Segman kanalı' if kind == 'groove' else 'Kama kanalı'
        self.preset.setAccessibleName(title + ' standart ölçü seçimi')
        form.addRow('Standart yuva' if kind == 'groove' else 'Standart kesit', self.preset)
        self.length = None
        if kind == 'keyway':
            self.length = QComboBox()
            self.length.setAccessibleName('Kama kanalı katalog boyu önerisi')
            form.addRow('Boy önerisi · mm', self.length)
            self.length.activated.connect(self.choose_length)
        layout.addLayout(form)
        self.details = label('', 'muted')
        layout.addWidget(self.details)
        self.source = label('', 'muted')
        self.source.setOpenExternalLinks(True)
        if kind == 'keyway':
            self.source.setToolTip('ISO/R 773:1969 geri çekilmiştir. Güncel DIN 6885-1 esas alınır.\n' + ISO_773_STATUS)
        self.set_appearance(appearance)
        layout.addWidget(self.source)
        # activated also fires when the user re-selects the displayed suggestion.
        # Rebuilding options during project/selection refresh never writes geometry.
        self.preset.activated.connect(self.choose_preset)

    def set_appearance(self, appearance):
        color = COLORS[appearance]['accent']
        if self.kind == 'groove':
            self.source.setText(f'<a style="color:{color}" href="{DIN_471_SOURCE}">DIN 471 ölçü kaynağı</a> · Nominal ölçüler')
        else:
            self.source.setText(f'<a style="color:{color}" href="{DIN_6885_SOURCE}">DIN 6885-1 ölçü kaynağı</a> · Nominal kesit · Form A')

    def set_context(self, diameter, stage_length, values):
        self.values = values
        self.size = groove_size(diameter) if self.kind == 'groove' else keyway_size(diameter)
        size = self.size
        matched = (size is not None and same_dimension(values['width'], size.width)
                   and same_dimension(values['depth'], size.depth)
                   and (self.kind != 'keyway' or values['angle'] == 0))
        with QSignalBlocker(self.preset):
            self.preset.clear()
            self.preset.addItem('Özel ölçü (elle)', None)
            if size is not None:
                text = (f'DIN 471 · Ø{size.diameter:g} · s {size.ring_thickness:g} mm'
                        if self.kind == 'groove' else
                        f'DIN 6885-1 A · {size.width:g} × {size.key_height:g} mm')
                self.preset.addItem(text, 'DIN471' if self.kind == 'groove' else 'DIN6885-1')
                self.preset.setCurrentIndex(1 if matched else 0)
        if self.kind == 'groove':
            self.details.setText(
                f'Yuva: m={size.width:g} mm · Ød₂={size.groove_diameter:g} mm\n'
                f'Radyal derinlik={size.depth:g} mm · En az kenar payı n={size.edge_margin:g} mm'
                if size else 'Bu çap için DIN 471 ölçüsü yok. Katalog: nominal Ø3–100 mm; özel ölçü girin.')
            return
        self.lengths = keyway_lengths(size, stage_length - values['offset'])
        with QSignalBlocker(self.length):
            self.length.clear()
            self.length.addItem('Özel boy (elle)', None)
            for length in self.lengths:
                self.length.addItem(f'{length:g}', length)
            index = self.length.findData(values['length'])
            self.length.setCurrentIndex(max(index, 0))
        self.length.setEnabled(bool(self.lengths))
        if size is None:
            self.details.setText('Bu çap için DIN 6885-1 kesiti yok. Katalog: Ø6–500 mm; özel ölçü girin.')
        else:
            self.details.setText(f'Kama b×h={size.width:g}×{size.key_height:g} mm · Mil kanal derinliği={size.depth:g} mm'
                                 + ('' if self.lengths else '\nBu konuma sığan katalog boyu yok; toplam boyu elle girin.'))

    def choose_preset(self, index):
        if index != 1 or self.size is None:
            return
        values = dict(width=self.size.width, depth=self.size.depth)
        if self.kind == 'keyway':
            values['angle'] = 0
            if self.lengths:
                values['length'] = min(self.lengths, key=lambda length: (abs(length-self.values['length']), length))
        self.valuesSelected.emit(values)

    def choose_length(self, index):
        length = self.length.itemData(index)
        if length in self.lengths:
            self.valuesSelected.emit(dict(length=length))
