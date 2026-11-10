"""Tool metadata editor. Drawing parsing/solid creation belongs to workers."""
from uuid import uuid4
from math import isfinite
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                              QPlainTextEdit, QVBoxLayout, QLabel, QScrollArea, QWidget, QMessageBox)
from .models import Channel, Mount, Segment, Tool


def segments(text):
    """Explicit axial positions keep gaps: start:length; start:length (mm)."""
    values = []
    for row in text.split(';'):
        if not row.strip():
            continue
        a, b = row.strip().split(':')
        values.append(Segment(float(a), float(b)))
    if not values or any(not isfinite(s.start) or not isfinite(s.length) or s.length <= 0 for s in values):
        raise ValueError('Segmentler başlangıç:boy biçiminde ve pozitif boylu olmalı.')
    ordered = sorted(values, key=lambda s: s.start)
    if any(a.start+a.length > b.start+1e-6 for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Segmentler üst üste geliyor.')
    return tuple(values)


def format_segments(value):
    return '; '.join(f'{s.start:g}:{s.length:g}' for s in value)


class ToolDialog(QDialog):
    def __init__(self, source, text, contours, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Gerçek DXF takım kesiti · mm'); self.resize(560, 700)
        self.source, self.dxf, self.contours, self.tool = source, text, contours, None
        layout = QVBoxLayout(self)
        note = QLabel('Kesit XY koordinatları takımın (y,z) kesitine dönüşür; boyuna eksen X’tir. Kesit 1:1 mm okunur. Kesit ölçüleri ve çalışma referanslarını çizimden girin.'); note.setWordWrap(True); layout.addWidget(note)
        widget = QWidget(); form = QFormLayout(widget); self.fields = {}
        self.contour = QComboBox()
        for i, (region, _, _) in enumerate(contours):
            p = region.polygon(); x0, y0, x1, y1 = p.bounds
            self.contour.addItem(f'Kesit {i+1} · {x1-x0:.2f} × {y1-y0:.2f} mm · alan {p.area:.2f} mm²', i)
        form.addRow('Kapalı kesit', self.contour)
        self.kind = QComboBox(); self.kind.addItem('Üst bıçak', 'punch'); self.kind.addItem('Alt kalıp', 'die'); form.addRow('Takım tipi', self.kind)
        for key, title, default in (
            ('maker', 'Üretici', ''), ('code', 'Ürün kodu', ''), ('family', 'Bağlantı ailesi (bilgi)', ''),
            ('height', 'Çalışma yüksekliği · mm', ''), ('mount', 'Montaj referansı y,z · mm', ''),
            ('segments', 'Segment başlangıç:boy · mm', '-60:120'),
            ('tool_interface', 'Takım bağlantı tanımı / kodu', ''), ('holder_interface', 'Tutucu bağlantı tanımı / kodu', ''),
            ('adapter_from', 'Adaptör takım tarafı (varsa)', ''), ('adapter_to', 'Adaptör tutucu tarafı (varsa)', ''),
            ('tip', 'Üst bıçak ucu y,z · mm', ''), ('tip_angle', 'Uç açısı · °', ''), ('tip_radius', 'Uç R · mm', ''),
            ('load', 'Üretici hat yükü (boş = bilinmiyor)', ''), ('unit', 'Hat yükünün özgün birimi', ''),
            ('holder_path', 'Tutucu + varsa adaptör kesiti DXF yolu', ''),
            ('holder_segments', 'Tutucu başlangıç:boy · mm', '')):
            edit = QLineEdit(default); edit.setAccessibleName(title); self.fields[key] = edit; form.addRow(title, edit)
        self.channels = QPlainTextEdit(); self.channels.setMaximumHeight(100)
        self.channels.setPlaceholderText('Alt kalıp: her kanal ayrı satır\nKod;V açıklığı;kanal açısı;merkez y;çalışma z;omuz R (isteğe bağlı)')
        self.channels.setAccessibleName('V kanalları'); form.addRow('Tek gövdenin V kanalları · mm, °', self.channels)
        self.confirm = QCheckBox('Bağlantı kodları gerçek takım/tutucu çiziminden doğrulandı')
        form.addRow(self.confirm)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget); layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); layout.addWidget(buttons)
        buttons.button(QDialogButtonBox.Ok).setText('Takımı ekle'); buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

    def accept(self):
        from math import isfinite
        try:
            value = lambda key: self.fields[key].text().strip()
            def number(key, optional=False):
                text = value(key)
                if optional and not text:
                    return None
                n = float(text.replace(',', '.'))
                if not isfinite(n) or n < 0:
                    raise ValueError(key+': sonlu ve negatif olmayan ölçü gerekli.')
                return n
            def point(key):
                p = tuple(float(s.strip()) for s in value(key).split(','))
                if len(p) != 2 or not all(isfinite(v) for v in p):
                    raise ValueError(key+': y,z biçiminde iki koordinat gerekli.')
                return p
            code = value('code')
            if not code or not value('maker'):
                raise ValueError('Üretici ve ürün kodunu girin.')
            kind = self.kind.currentData(); channels = []
            if kind == 'die':
                for line in self.channels.toPlainText().splitlines():
                    if not line.strip():
                        continue
                    cells = [c.strip() for c in line.split(';')]
                    if len(cells) not in (5, 6):
                        raise ValueError('V satırı: Kod;V;açı;y;z;omuzR')
                    id, opening, angle, y, z = cells[:5]
                    channel = Channel(id, float(opening), float(angle), (float(y), float(z)), float(cells[5]) if len(cells) == 6 and cells[5] else None)
                    if not id or channel.opening <= 0 or not 0 < channel.angle < 180:
                        raise ValueError('V kanalının adı, açıklığı veya açısı geçersiz.')
                    channels.append(channel)
                if not channels or len({c.id for c in channels}) != len(channels):
                    raise ValueError('Alt kalıp için benzersiz kodlu en az bir V kanalı girin.')
            load = number('load', True)
            if load is not None and not value('unit'):
                raise ValueError('Hat yükünün üretici birimini girin.')
            mount = Mount(value('tool_interface'), value('holder_interface') if self.confirm.isChecked() else '', value('adapter_from'), value('adapter_to'))
            index = self.contour.currentData()
            self.tool = Tool('user-'+uuid4().hex, value('maker'), code, kind, value('family'), number('height'), point('mount'),
                             self.contours[index][0], self.source, segments(value('segments')), mount,
                             number('tip_angle') if kind == 'punch' else None, number('tip_radius') if kind == 'punch' else None,
                             point('tip') if kind == 'punch' else None, tuple(channels), load, value('unit'), self.dxf, index)
            self.tool.validate()
            super().accept()
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, 'Takım kartını kontrol edin', str(error))
