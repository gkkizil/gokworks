"""Visual section-card catalogue: independent upper/lower selection per bend."""
from dataclasses import dataclass
from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                              QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                              QScrollArea, QSplitter, QVBoxLayout, QWidget)
from gui_qt.models import search_text
from gui_qt.theme import COLORS
from .dialogs import segments, format_segments


def paint_profile(painter, rect, tool, colours, channel=None, dimensions=False):
    painter.save(); painter.setRenderHint(QPainter.Antialiasing)
    painter.fillRect(rect, QColor(colours['canvas']))
    if tool is None or tool.section is None:
        painter.setPen(QColor(colours['muted'])); painter.drawText(rect, Qt.AlignCenter, 'Kesit geometrisi eksik')
        painter.restore(); return
    polygon = tool.section.polygon(); x0, y0, x1, y1 = polygon.bounds
    margin = 30 if dimensions else 10
    available = rect.adjusted(margin, margin, -margin, -margin)
    scale = min(available.width()/max(1e-6, x1-x0), available.height()/max(1e-6, y1-y0))
    cx, cy = (x0+x1)/2, (y0+y1)/2
    def point(p):
        return QPointF(available.center().x()+(p[0]-cx)*scale, available.center().y()-(p[1]-cy)*scale)
    path = QPainterPath(); path.setFillRule(Qt.OddEvenFill)
    for ring in (tool.section.outer, *tool.section.holes):
        path.moveTo(point(ring[0]))
        for vertex in ring[1:]:
            path.lineTo(point(vertex))
        path.closeSubpath()
    fill = QColor(colours['accent']); fill.setAlpha(75)
    painter.setPen(QPen(QColor(colours['accent']), 1.3)); painter.setBrush(fill); painter.drawPath(path)
    if dimensions:
        painter.setPen(QColor(colours['muted']))
        painter.drawText(QRectF(rect.left(), rect.bottom()-25, rect.width(), 22), Qt.AlignCenter, f'Kesit {x1-x0:.2f} × {y1-y0:.2f} mm · 1:1 veri')
        ref = channel.center if channel else tool.tip if tool.kind == 'punch' else None
        if ref is not None:
            pos = point(ref); painter.setPen(QPen(QColor('#dd9f28'), 1.6, Qt.DashLine))
            painter.drawLine(QPointF(pos.x(), rect.top()+8), QPointF(pos.x(), rect.bottom()-28))
            painter.drawEllipse(pos, 4, 4)
    painter.restore()


def profile_icon(tool, appearance='dark', size=QSize(140, 130)):
    pixmap = QPixmap(size*2); pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    paint_profile(painter, QRectF(0, 0, size.width(), size.height()), tool, COLORS[appearance])
    painter.end()
    return QIcon(pixmap)


class ProfileView(QWidget):
    def __init__(self, appearance):
        super().__init__(); self.appearance = appearance; self.tool = self.channel = None
        self.setMinimumSize(170, 180); self.setAccessibleName('Seçili takımın gerçek ölçekteki kesiti ve çalışma referansı')

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_profile(painter, QRectF(self.rect()), self.tool, COLORS[self.appearance], self.channel, True)
        painter.end()


@dataclass(frozen=True)
class Selection:
    tool: str
    channel: str
    segments: tuple


class ToolPicker(QDialog):
    def __init__(self, tools, kind, current, *, channel='', assigned_segments=None, appearance='dark', settings=None, parent=None):
        super().__init__(parent)
        self.tools = tuple(t for t in tools if t.kind == kind)
        self.kind, self.appearance, self.settings = kind, appearance, settings
        self.selection = None; self.import_requested = False; self.changing = False
        saved = settings.get('press_brake_favorite_tools', []) if settings else []
        self.favorites = set(saved) if isinstance(saved, list) else set()
        self.setWindowTitle('Üst bıçak kütüphanesi' if kind == 'punch' else 'Alt kalıp kütüphanesi')
        self.resize(1040, 720); self.setMinimumSize(620, 450)
        body = QVBoxLayout(self)
        title = QLabel('Her büküme özel üst bıçak seçin' if kind == 'punch' else 'Her büküme özel alt kalıp seçin')
        title.setProperty('role', 'title'); body.addWidget(title)
        row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Kod, üretici, bağlantı ailesi veya kesit kaynağı ara…'); self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Takım kütüphanesinde ara'); row.addWidget(self.search, 1)
        self.only_favorites = QCheckBox('Yalnız favoriler'); row.addWidget(self.only_favorites)
        self.columns = QComboBox()
        for n in (2, 3, 4):
            self.columns.addItem(f'{n} sütun', n)
        self.columns.setCurrentIndex(1); self.columns.setAccessibleName('Takım kartı sütun sayısı'); row.addWidget(self.columns)
        body.addLayout(row)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        self.cards = QListWidget(); self.cards.setViewMode(QListView.IconMode); self.cards.setMovement(QListView.Static)
        self.cards.setResizeMode(QListView.Adjust); self.cards.setSpacing(6); self.cards.setWordWrap(True)
        self.cards.setTextElideMode(Qt.ElideNone); self.cards.setIconSize(QSize(128, 120)); self.cards.setUniformItemSizes(True)
        self.cards.setAccessibleName('Kesit çizimli takım kartları'); self.cards.setMinimumWidth(300)
        colours = COLORS[appearance]
        self.cards.setStyleSheet(f'QListWidget {{ background: {colours["canvas"]}; }}'
                                f'QListWidget::item {{ border: 1px solid {colours["border"]}; border-radius: 4px; padding: 5px; }}'
                                f'QListWidget::item:selected {{ border: 2px solid {colours["accent"]}; }}')
        self.card_timer = QTimer(self); self.card_timer.setSingleShot(True); self.card_timer.timeout.connect(self.card_sizes)
        self.cards.viewport().installEventFilter(self)
        self.splitter.addWidget(self.cards)
        right = QWidget(); right.setMinimumWidth(220); details = QVBoxLayout(right)
        self.profile = ProfileView(appearance); details.addWidget(self.profile, 1)
        self.description = QLabel(); self.description.setWordWrap(True); self.description.setTextFormat(Qt.PlainText); details.addWidget(self.description)
        self.favorite = QCheckBox('Seçili takımı favoriye ekle'); details.addWidget(self.favorite)
        form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.channel = QComboBox(); self.channel.setAccessibleName('Seçilecek alt kalıbın V kanalı')
        if kind == 'die':
            form.addRow('Aynı gövdede çalışma kanalı', self.channel)
        else:
            self.channel.setParent(self); self.channel.hide()
        self.segment_edit = QLineEdit(); self.segment_edit.setAccessibleName('Seçilecek takımın segment başlangıç ve boyları')
        form.addRow('Segmentler · x:L; x:L (mm)', self.segment_edit)
        self.segment_summary = QLabel(); self.segment_summary.setWordWrap(True); form.addRow(self.segment_summary)
        details.addLayout(form)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setProperty('role', 'error'); details.addWidget(self.error)
        self.detail_scroll = QScrollArea(); self.detail_scroll.setWidgetResizable(True); self.detail_scroll.setMinimumWidth(220)
        self.detail_scroll.setWidget(right); self.splitter.addWidget(self.detail_scroll)
        self.splitter.setSizes([700, 280]); body.addWidget(self.splitter, 1)
        self.count = QLabel(); body.addWidget(self.count)
        footer = QHBoxLayout(); self.import_button = QPushButton('DXF takım ekle…'); footer.addWidget(self.import_button); footer.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        self.use_button = self.buttons.addButton('Seçili bıçağı kullan' if kind == 'punch' else 'Seçili kalıbı kullan', QDialogButtonBox.AcceptRole)
        self.use_button.setProperty('primary', True); footer.addWidget(self.buttons); body.addLayout(footer)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        self.search.textChanged.connect(self.filter); self.only_favorites.toggled.connect(self.filter)
        self.columns.currentIndexChanged.connect(self.card_sizes)
        self.cards.currentItemChanged.connect(self.select); self.cards.itemDoubleClicked.connect(lambda *_: self.accept())
        self.favorite.toggled.connect(self.set_favorite); self.channel.currentIndexChanged.connect(self.channel_changed)
        self.segment_edit.textChanged.connect(self.summarize_segments)
        self.import_button.clicked.connect(self.add_dxf)
        for tool in self.tools:
            item = QListWidgetItem(); item.setData(Qt.UserRole, tool.id); item.setIcon(profile_icon(tool, appearance))
            item.setToolTip(f'{tool.maker} / {tool.code}\n{tool.source}'); self.cards.addItem(item); self.card_text(item, tool)
        self.card_sizes(); self.filter()
        chosen = next((self.cards.item(i) for i in range(self.cards.count()) if self.cards.item(i).data(Qt.UserRole) == current), None)
        if chosen is None and self.cards.count():
            chosen = self.cards.item(0)
        if chosen is not None:
            self.cards.setCurrentItem(chosen)
            tool = self.current_tool()
            if tool.id == current and assigned_segments is not None:
                self.segment_edit.setText(format_segments(assigned_segments))
            if channel:
                self.channel.setCurrentIndex(self.channel.findData(channel))

    def current_tool(self):
        item = self.cards.currentItem()
        return next((t for t in self.tools if item and t.id == item.data(Qt.UserRole)), None)

    def card_text(self, item, tool):
        measure = f'Uç {tool.tip_angle if tool.tip_angle is not None else "?"}° · R {tool.tip_radius if tool.tip_radius is not None else "?"}' if tool.kind == 'punch' else ' / '.join(f'V{c.opening:g}' for c in tool.channels) or 'V bilinmiyor'
        item.setText(('★ ' if tool.id in self.favorites else '')+tool.code+'\n'+tool.maker+'\n'+measure+f'\nYükseklik {tool.height:g} mm'+('\nDEMO · özgün geometri' if tool.demo else '\nDXF · kullanıcı kesiti'))

    def card_sizes(self):
        columns = self.columns.currentData() or 3
        width = max(115, (max(300, self.cards.viewport().width())-16)//columns-12)
        size = QSize(width, 250)
        if self.cards.gridSize() != size:
            self.cards.setGridSize(size); self.cards.setIconSize(QSize(max(60, width-18), 118))
            for i in range(self.cards.count()):
                self.cards.item(i).setSizeHint(size-QSize(6, 6))

    def eventFilter(self, watched, event):
        if watched is self.cards.viewport() and event.type() == QEvent.Resize:
            self.card_timer.start(0)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'cards'):
            self.card_sizes()

    def filter(self, *_):
        needle = search_text(self.search.text().strip()); visible = []
        for i, tool in enumerate(self.tools):
            item = self.cards.item(i)
            match = needle in search_text(' '.join((tool.code, tool.maker, tool.family, tool.source)))
            match &= not self.only_favorites.isChecked() or tool.id in self.favorites
            item.setHidden(not match)
            if match:
                visible.append(item)
        if self.cards.currentItem() not in visible:
            self.cards.setCurrentItem(visible[0] if visible else None)
        self.count.setText(f'{len(visible)} / {len(self.tools)} takım · Kesitler kütüphanedeki gerçek mm verisinden çizilir.')
        self.use_button.setEnabled(bool(visible))
        if not visible:
            self.profile.tool = None; self.profile.update(); self.description.setText('Aramayla eşleşen takım yok.')

    def select(self, current, previous=None):
        tool = self.current_tool()
        if not tool:
            return
        self.changing = True
        self.profile.tool = tool; self.profile.channel = None
        self.channel.clear()
        for c in tool.channels:
            self.channel.addItem(f'{c.id} · V{c.opening:g} / {c.angle:g}°', c.id)
        self.favorite.setChecked(tool.id in self.favorites)
        self.segment_edit.setText(format_segments(tool.segments)); self.changing = False
        load = f'{tool.line_load:g} {tool.line_load_unit}' if tool.line_load is not None else 'bilinmiyor'
        link = 'Arayüz kodları eşleşiyor' if tool.mount.compatible else 'Takım–tutucu bağlantısı doğrulanamadı'
        holder = 'Tutucu kesiti mevcut' if tool.holder_section is not None and tool.holder_segments else 'Tutucu geometri/yerleşimi eksik'
        self.description.setText(f'{tool.maker} · {tool.code}\nAile: {tool.family}\nÇalışma yüksekliği: {tool.height:g} mm\nMontaj referansı: {tool.mount_reference}\nHat yükü: {load}\n{link}\n{holder}\nKaynak: {tool.source}')
        self.error.clear(); self.channel_changed(); self.summarize_segments()

    def channel_changed(self, *_):
        tool = self.current_tool()
        self.profile.channel = next((c for c in tool.channels if c.id == self.channel.currentData()), None) if tool else None
        self.profile.update()

    def set_favorite(self, checked):
        if self.changing:
            return
        tool = self.current_tool()
        if tool:
            self.favorites.add(tool.id) if checked else self.favorites.discard(tool.id)
            if self.settings:
                self.settings.set('press_brake_favorite_tools', sorted(self.favorites))
            self.card_text(self.cards.currentItem(), tool); self.filter()

    def summarize_segments(self, *_):
        try:
            values = segments(self.segment_edit.text())
            self.segment_summary.setText(f'{len(values)} segment · toplam {sum(s.length for s in values):g} mm · aralıklar korunur')
        except ValueError:
            self.segment_summary.setText('Başlangıç:boy biçiminde, üst üste gelmeyen segmentler girin.')

    def accept(self):
        tool = self.current_tool()
        if not tool or self.cards.currentItem().isHidden():
            return
        try:
            chosen = segments(self.segment_edit.text())
            if self.kind == 'die' and self.channel.currentIndex() < 0:
                raise ValueError('Bu alt kalıp için çalışma V kanalı seçin.')
            self.selection = Selection(tool.id, self.channel.currentData() or '', chosen)
            super().accept()
        except ValueError as error:
            self.error.setText(str(error))

    def add_dxf(self):
        self.import_requested = True; self.reject()
