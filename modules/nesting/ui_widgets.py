"""Small Qt-only editors and a vector, zoomable sheet preview."""

import math

from PySide6.QtCore import Qt, QRectF, Signal, QLineF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QTransform, QBrush
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QDialogButtonBox, QGraphicsView, QGraphicsScene, QSizePolicy, QGraphicsItem)

from gui_qt.components import ValueForm, label, scroll
from gui_qt.models import TableModel
from gui_qt.theme import COLORS
from modules.nesting.geometry import placed
from modules.nesting.render import painter_path, PALETTE, CANVAS_PALETTE


class Values(dict):
    def set(self, key, value):
        self[key] = value


NUMERIC_KEYS = ('quantity','thickness','stock','weight','price','width','height','gross_weight','net_weight',
                'waste_weight','efficiency','plate','requested','total_weight')


def part_colors(index, appearance):
    """Fill, outline and label colours of one part type on the drawing.

    Fills are translucent tints of a part palette without the accent blue
    (blue means selection), so the sheet
    surface (``panel``) shows through, holes stay visibly open and the label
    uses the theme's ``text`` colour in both appearances.
    """
    base = QColor(CANVAS_PALETTE[index % len(CANVAS_PALETTE)])
    fill = QColor(base); fill.setAlpha(110 if appearance == 'dark' else 120)
    outline = QColor(base) if appearance == 'dark' else base.darker(165)
    return fill, outline


class NestingTableModel(TableModel):
    """Keep numeric columns legible and full source/error text discoverable."""
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if (role == Qt.TextAlignmentRole and orientation == Qt.Horizontal
                and 0 <= section < len(self.columns) and self.columns[section].key in NUMERIC_KEYS):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            row = self.rows[index.row()]
            if role == Qt.TextAlignmentRole and self.columns[index.column()].key in NUMERIC_KEYS:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            if role == Qt.ToolTipRole:
                details=[str(row['code'])] if row.get('code') else []
                if self.columns[index.column()].key in ('width','height','gross_weight','net_weight','waste_weight',
                    'efficiency','plate','requested','total_weight'):
                    title=self.columns[index.column()].title.replace('\n',' ')
                    details.insert(0,f'{title}: {super().data(index,Qt.DisplayRole)}')
                if row.get('material'):
                    details.append(f"Malzeme: {row['material']}")
                if row.get('status'):
                    column = next((i for i,c in enumerate(self.columns) if c.key == 'status'),None)
                    status = super().data(self.index(index.row(),column),Qt.DisplayRole) if column is not None else row['status']
                    details.append(f'Durum: {status}')
                details.extend(str(row[k]) for k in ('source','detail') if row.get(k))
                if row.get('weight') is not None:
                    details.append(f"Net ağırlık: {row['weight']:.3f} kg/adet".replace('.',','))
                return '\n'.join(details) or super().data(index,role)
        return super().data(index,role)


class Editor(QDialog):
    def __init__(self, parent, title, build, parse):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(520, 650); self.value = None; self.parse = parse
        layout = QVBoxLayout(self)
        self.form = ValueForm(Values(), '')
        build(self.form)
        layout.addWidget(scroll(self.form), 1)
        self.error = label('', 'error'); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Uygula'); buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        buttons.accepted.connect(self.submit); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def submit(self):
        try:
            self.value = self.parse(self.form)
        except (ValueError, TypeError) as error:
            self.error.setText(str(error)); return
        self.accept()


class NestingCanvas(QGraphicsView):
    # An empty ID means the user clicked the sheet/background to clear selection.
    partActivated = Signal(str)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self)); self.setMinimumSize(0,0)
        # The sheet takes the remaining space. A minimum viewport height can
        # force Qt to overlap the result labels at native Windows font sizes.
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Ignored)
        self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # fitInView must not toggle scrollbars and start another resize/layout
        # cycle while a progress update is synchronously repainting the window.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.theme = 'dark'; self.project = self.result = self.key = None
        self.auto_fit = True
        self.mode = 'empty'; self.show_grid = True
        self.label_geometry = []
        self.show_labels = True; self.part_labels = []
        self.part_items = {}; self.part_styles = {}; self.selected_part_ids = set()
        self.content_rect = None; self.content_margin = 8
        self._click_position = None; self._click_part_id = ''; self._dragged = False
        self.setAccessibleName('Sac üzerinde parça yerleşimi')
        self.setToolTip('Parçaya tıkla: listede seç · Tekerlek: yakınlaştır · Sürükle: kaydır · Sığdır: bütün plakayı göster')
        self.empty_label = label('DXF dosyalarını ekleyin, ardından Yerleştir düğmesine basın.', 'muted')
        self.empty_label.setParent(self.viewport()); self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.empty()

    def _clear_scene(self):
        # Drop Python references before Qt deletes the underlying graphics items.
        self.part_labels = []
        self.label_geometry = []
        self.part_items = {}; self.part_styles = {}
        self.content_rect = None; self.content_margin = 8
        self.scene().clear()

    def _colors(self):
        return COLORS[self.theme]

    def empty(self):
        self.mode = 'empty'
        self.project = self.result = self.key = None
        self._clear_scene()
        self.scene().setSceneRect(QRectF(0,0,100,100))
        colors = self._colors()
        self.setBackgroundBrush(QColor(colors['canvas']))
        self.empty_label.setStyleSheet('font-size: 13px; color: '+colors['muted']+';')
        self.empty_label.setGeometry(self.viewport().rect().adjusted(24,24,-24,-24))
        self.empty_label.show(); self.fit()

    def drawBackground(self,painter,rect):
        super().drawBackground(painter,rect)
        if not self.show_grid or self.mode=='empty': return
        scale = abs(self.transform().m11())
        if scale <= 0: return
        # Adaptive logical-mm spacing keeps the grid bounded at every zoom.
        base = 10**math.floor(math.log10(48/scale))
        step = next(base*x for x in (1,2,5,10) if base*x*scale >= 28)
        pen = QPen(QColor(self._colors()['grid'])); pen.setCosmetic(True); painter.setPen(pen)
        lines = []
        for i in range(math.floor(rect.left()/step),math.ceil(rect.right()/step)+1):
            lines.append(QLineF(i*step,rect.top(),i*step,rect.bottom()))
        for i in range(math.floor(rect.top()/step),math.ceil(rect.bottom()/step)+1):
            lines.append(QLineF(rect.left(),i*step,rect.right(),i*step))
        painter.drawLines(lines)

    def set_grid_visible(self,visible):
        self.show_grid = bool(visible); self.viewport().update()

    def _caption(self, text, color, size=11):
        """A fixed-pixel annotation that stays legible at every zoom."""
        item = self.scene().addSimpleText(text)
        font = QFont(self.font()); font.setPixelSize(size); item.setFont(font)
        item.setBrush(QColor(color)); item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        item.setAcceptedMouseButtons(Qt.NoButton)
        return item

    def _sheet_boundary(self,project,sheet,margin=None):
        """Plate surface, solid outer edge, dashed usable area and its dimensions."""
        colors = self._colors()
        self.setBackgroundBrush(QColor(colors['canvas']))
        pen = QPen(QColor(colors['muted']),1.5); pen.setCosmetic(True)
        item = self.scene().addRect(QRectF(0,-sheet.height,sheet.width,sheet.height),pen,QColor(colors['panel']))
        item.setZValue(-3); item.setToolTip(f'{sheet.width:g} × {sheet.height:g} mm · Sac sınırı')
        margin = project.options.margin if margin is None else margin
        if margin and margin > 0:
            edge = QPen(QColor(colors['border_strong']),1,Qt.DashLine); edge.setCosmetic(True)
            item = self.scene().addRect(QRectF(margin,-sheet.height+margin,max(0,sheet.width-2*margin),
                                               max(0,sheet.height-2*margin)),edge)
            item.setZValue(-2); item.setToolTip(f'Kullanılabilir alan · kenar payı {margin:g} mm')
        # Width under the bottom edge, height left of the plate, in screen px.
        width = self._caption(f'{sheet.width:g} mm',colors['muted'])
        bounds = width.boundingRect()
        width.setPos(sheet.width/2,0); width.setTransform(QTransform.fromTranslate(-bounds.width()/2,5))
        height = self._caption(f'{sheet.height:g} mm',colors['muted'])
        side = height.boundingRect()
        height.setPos(0,-sheet.height/2); height.setTransform(QTransform.fromTranslate(-side.width()-6,-side.height()/2))
        self.content_rect = QRectF(0,-sheet.height,sheet.width,sheet.height)
        self.content_margin = max(bounds.height()+12,side.width()+14)

    def render_stock(self,project,sheet,*,margin=None):
        self.project,self.result,self.key = project,None,None; self.mode = 'stock'
        self._clear_scene(); self.empty_label.hide(); self._sheet_boundary(project,sheet,margin)
        self.scene().setSceneRect(self.content_rect)
        self.fit()

    def render_part(self,project,part):
        self.project,self.result,self.key = project,None,None; self.mode = 'part'
        self._clear_scene(); self.empty_label.hide()
        self.setBackgroundBrush(QColor(self._colors()['canvas']))
        fill, outline = part_colors(project.parts.index(part), self.theme)
        pen = QPen(outline,1.5); pen.setCosmetic(True)
        item = self.scene().addPath(painter_path(part.polygon),pen,fill)
        item.setData(0,part.id); item.setToolTip(f'{part.code}\n{part.area:.3f} mm² · {part.thickness:g} mm\nKaynak kontur önizlemesi; yerleşim sonucu değil.')
        self.part_items[part.id] = [item]; self.part_styles[part.id] = (pen,QBrush(fill))
        bounds = item.path().boundingRect()
        x0,y0,x1,y1 = part.polygon.bounds; colors = self._colors()
        size = self._caption(f'{x1-x0:g} × {y1-y0:g} mm',colors['muted'])
        size.setPos(bounds.center().x(),bounds.bottom())
        size.setTransform(QTransform.fromTranslate(-size.boundingRect().width()/2,5))
        self.content_rect = bounds; self.content_margin = size.boundingRect().height()+14
        self.scene().setSceneRect(bounds); self.fit(); self._apply_selection()

    def render(self, project, result, key):
        self.project, self.result, self.key = project, result, key
        self.mode = 'layout'
        self._clear_scene()
        if result is None or key is None:
            return self.empty()
        self.empty_label.hide()
        colors = self._colors()
        sheet = project.sheet(key[0]); self._sheet_boundary(project,sheet)
        part_lookup = {part.id:(part,*part_colors(index,self.theme),part.area)
                       for index,part in enumerate(project.parts)}
        font = QFont(self.font()); font.setPixelSize(11)
        for p in result.placements:
            if (p.sheet_id, p.sheet_number) != key:
                continue
            part,fill,outline,area = part_lookup[p.part_id]; g = placed(part, p)
            pen = QPen(outline,1); pen.setCosmetic(True)
            item = self.scene().addPath(painter_path(g), pen, fill)
            item.setData(0,part.id)
            self.part_items.setdefault(part.id,[]).append(item); self.part_styles[part.id] = (pen,QBrush(fill))
            item.setToolTip(f'{part.code} #{p.instance}\n{area:,.2f} mm² · {part.thickness:g} mm\n'
                            f'X={p.x:.3f}; Y={p.y:.3f}; {p.angle:g}°')
            # Keep long file names out of neighbouring parts. The full code
            # and instance remain available on hover, including with names off.
            caption = part.code if len(part.code) <= 18 else part.code[:15]+'…'
            text = self.scene().addSimpleText(caption)
            text.setData(0,part.id); text.setZValue(2)
            text.setFont(font)
            text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            text.setBrush(QColor(colors['text'])); center = g.representative_point()
            self.label_geometry.append((text,item.path(),center.x,-center.y))
            text.setToolTip(item.toolTip())
            text.setVisible(self.show_labels); self.part_labels.append(text)
        self._apply_selection()
        self.scene().setSceneRect(self.content_rect); self.fit()

    def set_selected_parts(self, ids):
        """Highlight every placement of these IDs without rebuilding the scene."""
        self.selected_part_ids = set(ids)
        self._apply_selection()

    def _apply_selection(self):
        colors = self._colors()
        selected = QPen(QColor(colors['accent']),3); selected.setCosmetic(True)
        highlight = QColor(colors['accent']); highlight.setAlpha(90)
        for part_id,items in self.part_items.items():
            active = part_id in self.selected_part_ids
            normal, brush = self.part_styles.get(part_id,(QPen(QColor(colors['muted'])),QBrush()))
            for item in items:
                item.setPen(selected if active else normal)
                item.setBrush(QBrush(highlight) if active else brush)
                item.setZValue(1 if active else 0)

    def set_labels_visible(self, visible):
        self.show_labels = visible
        self.update_labels()

    def update_labels(self):
        scale = abs(self.transform().m11())
        if scale <= 0: return
        for text,path,x,y in self.label_geometry:
            if not self.show_labels:
                text.hide(); continue
            bounds = text.boundingRect()
            # A label must fit inside actual material, including concavities
            # and holes. Its pixels therefore cannot cover a neighbouring part.
            pad = 2/scale
            area = path.boundingRect(); cx,cy = area.center().x(),area.center().y()
            points = ((x,y),(cx,area.top()+area.height()*.2),(cx,area.bottom()-area.height()*.2),
                      (area.left()+area.width()*.2,cy),(area.right()-area.width()*.2,cy))
            for px,py in points:
                rect = QRectF(px-bounds.width()/scale/2,py-bounds.height()/scale/2,bounds.width()/scale,bounds.height()/scale)
                if path.contains(rect.adjusted(-pad,-pad,pad,pad)):
                    text.setPos(rect.topLeft()); text.show(); break
            else: text.hide()

    def fit(self):
        self.auto_fit = True
        content = getattr(self,'content_rect',None)
        if content is not None and content.width() > 0 and content.height() > 0:
            # Reserve a fixed pixel margin around the plate for the dimension
            # captions, whatever the plate size or window size.
            view = self.viewport().rect()
            margin = min(self.content_margin,view.width()*.2,view.height()*.2)
            scale = min(max(1,view.width()-2*margin)/content.width(),max(1,view.height()-2*margin)/content.height())
            pad = margin/scale
            self.scene().setSceneRect(content.adjusted(-pad,-pad,pad,pad))
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        self.update_labels()

    def zoom(self,factor):
        if .0001 < self.transform().m11()*factor < 10000:
            self.auto_fit = False; self.scale(factor,factor); self.update_labels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'empty_label'): self.empty_label.setGeometry(self.viewport().rect().adjusted(24,24,-24,-24))
        # Only update the transform, not the scene. A deferred fit can still
        # describe the previous native Windows viewport after a second resize.
        # Both scrollbars are permanently off, so fitting cannot toggle their
        # visibility and recursively resize the viewport.
        if getattr(self,'auto_fit',False): self.fit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._click_position = event.position().toPoint()
            item = self.itemAt(self._click_position)
            self._click_part_id = str(item.data(0) or '') if item is not None else ''
            self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._click_position is not None:
            distance = (event.position().toPoint()-self._click_position).manhattanLength()
            self._dragged |= distance >= QApplication.startDragDistance()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        activated = None
        if event.button() == Qt.LeftButton and self._click_position is not None:
            distance = (event.position().toPoint()-self._click_position).manhattanLength()
            if not self._dragged and distance < QApplication.startDragDistance():
                activated = self._click_part_id
            self._click_position = None
        super().mouseReleaseEvent(event)
        if activated is not None:
            self.partActivated.emit(activated)
            event.accept()

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        self.zoom(factor)
        event.accept()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Plus,Qt.Key_Equal): self.zoom(1.25); event.accept()
        elif event.key()==Qt.Key_Minus: self.zoom(.8); event.accept()
        elif event.key()==Qt.Key_Home: self.fit(); event.accept()
        else: super().keyPressEvent(event)
