"""Draft sheet preview: the same view/scale/paper plan the generator uses, drawn before SolidWorks runs.

Views are their planned bounding boxes (model extents × scale), not lines. The plan
comes from ``rules.plan_views`` + ``layout.plan_sheets`` exactly as in
``pipeline.generate_one``, so paper, scale, projection and sheet split match the
drawing that will be created; the isometric box is the planner's conservative bound.
"""
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui_qt.theme import COLORS
from .layout import LayoutError, plan_sheets
from .rules import CLASS_TITLES, MODEL_VIEWS, plan_views

ROLE_TITLES = {'main': 'Ana görünüş', 'top': 'Üst izdüşüm', 'side': 'Yan izdüşüm', 'isometric': 'İzometrik'}
VIEW_NAMES = {v: k for k, v in MODEL_VIEWS.items()}
DIRECTION_TITLES = {'front': 'ön', 'back': 'arka', 'top': 'üst', 'bottom': 'alt', 'right': 'sağ',
                    'left': 'sol', 'isometric': 'izometrik'}


def scale_text(scale):
    def number(value):
        return f'{value:.4g}'.replace('.', ',')
    return f'{number(scale)}:1' if scale >= 1 else f'1:{number(1/scale)}'


def plan_preview(info, options):
    """Sheets for ``info`` under ``options`` (same rules as generation); raises LayoutError/ValueError."""
    if options.classification != 'auto' and info.kind == 'part' and options.classification in CLASS_TITLES:
        info = replace(info, classification=options.classification)
    return plan_sheets(plan_views(info, options), options)


class SheetPreview(QWidget):
    """Paints the planned sheets side by side (or stacked when the panel is tall)."""

    TITLE_BLOCK = 180.    # mm, drawn inside the title strip the planner reserves

    def __init__(self):
        super().__init__(); self.plans = []; self.message = ''; self.error = False
        self.info = None; self.options = None; self.colours = COLORS['dark']
        self.setMinimumSize(240, 180); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName('Teknik resim taslak pafta önizlemesi')

    def sizeHint(self):
        return QSize(640, 460)

    def show_plan(self, info, options):
        self.info, self.options = info, options
        try:
            self.plans = plan_preview(info, options); self.message = ''; self.error = False
        except (LayoutError, ValueError) as error:
            self.plans = []; self.message = str(error); self.error = True
        self.setAccessibleDescription(self.summary())
        self.update()

    def show_message(self, text):
        self.info = None; self.plans = []; self.message = text; self.error = False; self.update()

    def summary(self):
        if not self.plans:
            return self.message
        first = self.plans[0]
        return (f'{len(self.plans)} pafta · {first.paper} · ölçek {scale_text(first.scale)} · '
                + ', '.join(ROLE_TITLES.get(v.role, v.role) for p in self.plans for v in p.views))

    # ------------------------------------------------------------------ paint
    def _layout(self):
        """Sheet rectangles in widget pixels and the mm → px factor shared by all sheets."""
        gap, pad, caption = 24., 16., 22.
        sheets = [(p.width_mm, p.height_mm) for p in self.plans]
        avail_w, avail_h = self.width()-2*pad, self.height()-2*pad
        best = None
        for horizontal in (True, False):
            total_w = sum(w for w, _ in sheets) if horizontal else max(w for w, _ in sheets)
            total_h = max(h for _, h in sheets) if horizontal else sum(h for _, h in sheets)
            free_w = avail_w-(gap*(len(sheets)-1) if horizontal else 0)
            free_h = avail_h-caption*len(sheets if not horizontal else [0])-(gap*(len(sheets)-1) if not horizontal else 0)
            k = min(free_w/total_w, free_h/total_h)
            if best is None or k > best[0]:
                best = (k, horizontal)
        k, horizontal = best
        rects = []; x, y = pad, pad
        used_w = (sum(w for w, _ in sheets)*k+gap*(len(sheets)-1)) if horizontal else max(w for w, _ in sheets)*k
        x += max(0., (avail_w-used_w)/2)
        for w, h in sheets:
            rect = QRectF(x, y+caption, w*k, h*k); rects.append(rect)
            if horizontal:
                x += w*k+gap
            else:
                y += h*k+gap+caption
        return k, rects

    def paintEvent(self, event):
        c = self.colours; painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(c['canvas']))
        if not self.plans:
            painter.setPen(QColor(c['danger'] if self.error else c['muted']))
            text = ('Paftaya sığmıyor\n\n' if self.error else '')+(self.message or '')
            painter.drawText(self.rect().adjusted(24, 24, -24, -24), Qt.AlignCenter | Qt.TextWordWrap, text)
            return
        k, rects = self._layout()
        small = QFont(painter.font()); small.setPointSizeF(max(7., small.pointSizeF()-1))
        bold = QFont(painter.font()); bold.setBold(True)
        for index, (plan, rect) in enumerate(zip(self.plans, rects)):
            painter.setFont(bold); painter.setPen(QColor(c['text']))
            painter.drawText(QRectF(rect.left(), rect.top()-20, rect.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                             f'Pafta {index+1} · {plan.name}')
            painter.setFont(small); painter.setPen(QColor(c['muted']))
            painter.drawText(QRectF(rect.left(), rect.top()-20, rect.width(), 18), Qt.AlignRight | Qt.AlignVCenter,
                             f'{plan.paper} · {plan.width_mm:g} × {plan.height_mm:g} mm · ölçek {scale_text(plan.scale)}')
            self._sheet(painter, plan, rect, k)

    def _sheet(self, painter, plan, rect, k):
        c = self.colours; options = self.options
        def point(x, y):            # sheet mm (origin bottom-left) → widget px
            return QPointF(rect.left()+x*k, rect.bottom()-y*k)
        def box(x, y, w, h):
            return QRectF(point(x, y+h), point(x+w, y))
        painter.setPen(QPen(QColor(c['border_strong']), 1)); painter.setBrush(QColor(c['panel']))
        painter.drawRect(rect)
        margin = options.margin_mm
        frame = box(margin, margin, plan.width_mm-2*margin, plan.height_mm-2*margin)
        painter.setPen(QPen(QColor(c['muted']), 1.2)); painter.setBrush(Qt.NoBrush); painter.drawRect(frame)
        # Title block in the strip the planner keeps free above the bottom margin.
        tb_w = min(self.TITLE_BLOCK, plan.width_mm-2*margin)
        title = box(plan.width_mm-margin-tb_w, margin, tb_w, options.title_height_mm)
        painter.drawRect(title)
        mid = title.top()+title.height()/2
        painter.drawLine(QPointF(title.left(), mid), QPointF(title.right(), mid))
        painter.setPen(QColor(c['muted']))
        name = (self.info.title or '').strip() if self.info is not None else ''
        painter.drawText(title.adjusted(6, 2, -6, 0).intersected(QRectF(title.left(), title.top(), title.width(), title.height()/2)),
                         Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, name or 'Antet')
        projection = 'ISO 1. açı' if options.projection == 'first' else '3. açı'
        painter.drawText(QRectF(title.left()+6, mid, title.width()-12, title.height()/2), Qt.AlignLeft | Qt.AlignVCenter,
                         f'Ölçek {scale_text(plan.scale)}   {plan.paper}   {projection}')
        # Views: planned extents (footprint × scale) around their planned centres.
        accent = QColor(c['accent']); fill = QColor(c['accent']); fill.setAlpha(28)
        for view in plan.views:
            w, h = view.footprint[0]*plan.scale, view.footprint[1]*plan.scale
            area = box(view.center[0]-w/2, view.center[1]-h/2, w, h)
            pen = QPen(accent, 1.4)
            if view.role == 'isometric':
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen); painter.setBrush(fill); painter.drawRect(area)
            caption = ROLE_TITLES.get(view.role, view.role)
            if view.role == 'main':
                direction = VIEW_NAMES.get(view.model_view, '')
                caption += f' · {DIRECTION_TITLES.get(direction, direction)}'
            if view.role == 'isometric':
                caption += ' (yaklaşık)'
            painter.setPen(QColor(c['text']))
            label = area.adjusted(4, 3, -4, -3)
            metrics = painter.fontMetrics()
            if label.height() >= metrics.height() and label.width() >= metrics.horizontalAdvance(caption):
                painter.drawText(label, Qt.AlignLeft | Qt.AlignTop, caption)
            else:                    # a thin or small view: name it just above its box
                outside = QRectF(area.left()-40, area.top()-metrics.height()-2, area.width()+80, metrics.height())
                painter.drawText(outside, Qt.AlignHCenter | Qt.AlignBottom, caption)
            extent = f'{view.footprint[0]:g} × {view.footprint[1]:g} mm'.replace('.', ',')
            if view.role != 'isometric' and label.height() >= 2*metrics.height()+2 \
                    and label.width() >= metrics.horizontalAdvance(extent):
                painter.setPen(QColor(c['muted']))
                painter.drawText(label, Qt.AlignRight | Qt.AlignBottom, extent)
