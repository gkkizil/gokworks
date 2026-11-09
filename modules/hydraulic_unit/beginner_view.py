"""Kolay kullanım: Ölçüler → Hareketler → Sonuç ve rapor.

Teknik olmayan kullanıcı için ölçü, hareket ve sonuç odaklı görünüm. Hesap
yapmaz: değerleri projeye yazar, sonuçları çekirdeğin ürettiği ``ProjectResult``
ve ``presentation.result_rows`` üzerinden gösterir. Ayrıntılı ayarlar korunur.
"""
from dataclasses import replace
import math

from PySide6.QtCore import Qt, QEvent, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget)

from gui_qt.components import Disclosure, button, label, scroll
from gui_qt.theme import COLORS
from .beginner import FORCE_FACTORS, phase_seconds, simple_supported
from .charts import MotionStrip, StepChart
from .core.cylinder import areas, buckling
from .core.units import convert
from .core.validation import InputError
from .presentation import result_rows

MOVEMENTS = {'extend': 'İleri itme', 'retract': 'Geri çekme', 'regenerate': 'Hızlı ileri hareket (yağ geri kazanımlı)',
             'hold': 'Yerinde basınçla bekleme', 'idle': 'Makine boşta bekliyor'}
DIRECTION = {'extend': '→', 'regenerate': '→', 'retract': '←', 'hold': '■', 'idle': '○'}
STEP_TITLES = ('Ölçüler', 'Hareketler', 'Sonuç ve rapor')
STEP_HINTS = ('Silindirin üç ölçüsünü girin. Çizim hangi ölçünün nerede olduğunu gösterir.',
              'Makinenin sırayla ne yapacağını girin: her hareketin yolu, süresi ve kuvveti.',
              'Motor, pompa, hat, tank ve soğutucu ihtiyacını inceleyin; uyarıları çözüp rapor alın.')
NEXT_HINTS = ('Sonraki: hareketleri girin', 'Sonraki: sonuçları inceleyin', '')
FIELDS = {
    'bore': ('Piston çapı', 'Silindirin iç çapı. Etikette veya teknik resimde “D” ya da “Ø63” gibi yazar. '
             'Gövdenin dışını ölçmeyin; gövde dış çapı piston çapından büyüktür.', 'örn. 63'),
    'rod': ('Mil çapı', 'Dışarı çıkan parlak milin çapı. Etikette veya teknik resimde “d” ya da “Ø36” gibi yazar; '
            'kumpasla milden de ölçülebilir.', 'örn. 36'),
    'stroke': ('Strok (toplam yol)', 'Milin tamamen içeriden tamamen dışarıya kadar gidebildiği yol. Etikette “H” ya da '
               '“strok 300” gibi yazar. Her hareketin yolu bundan büyük olamaz.', 'örn. 300'),
}
PLAIN_ISSUES = {
    'HOT_OIL': ('Yağ soğutucusuz çok ısınıyor.', 'Soğutucu ekleyin (gücü aşağıdaki kartta) veya hareket sürelerini uzatıp basıncı azaltın.'),
    'COOLER': ('Yağı hedef sıcaklıkta tutmak için soğutucu gerekiyor.', 'Soğutucu kartındaki gücü üreticiyle seçin.'),
    'BUCKLING': ('Mil yük altında bükülebilir (burkulma).', 'Mil çapını büyütün veya bağlantı şeklini ayrıntılı ayarlarda kontrol edin.'),
    'VELOCITY': ('Hattaki yağ akış hızı önerilen aralığın dışında.', 'Hat ayarlarında iç çapı kontrol edin veya önerilen hızları uygulayın.'),
    'CAPACITY': ('Seçili pompa bu hareketlere yetişemiyor.', '“Önerilen pompa hacmini uygula” ile deneyin ya da hareket sürelerini uzatın.'),
    'RELIEF_LIMIT': ('Emniyet valfi ayarı pompanın sınırını aşıyor.', 'Pompa ve motor ayarlarında emniyet valfi değerini düşürün.'),
    'MOTOR_SMALL': ('Elle seçilen motorun gücü yetersiz.', 'Motor alanını boş bırakıp öneriyi kullanın veya daha güçlü motor seçin.'),
    'CYCLE_NOT_CLOSED': ('Silindir çevrim sonunda başlangıç yerine dönmüyor.', 'Hareketler adımında milin geri döneceği bir geri çekme ekleyin.'),
    'TANK_VOLUME': ('Tankın kullanılabilir yağ hacmi yetersiz.', 'Tank ölçülerini büyütün veya doluluk oranını kontrol edin.'),
}
TOPIC = {'HOT_OIL': 'yağ soğutması', 'COOLER': 'yağ soğutması', 'BUCKLING': 'mil burkulması', 'VELOCITY': 'hat çapı',
         'CAPACITY': 'pompa kapasitesi', 'RELIEF_LIMIT': 'emniyet valfi', 'MOTOR_SMALL': 'motor gücü',
         'CYCLE_NOT_CLOSED': 'hareket sırası', 'TANK_VOLUME': 'tank hacmi'}
PUMP_TIP = 'Pompa hacmini nominal öneriyle değiştirir; basınç sınırı ve verimler değişmez. Sonuç yeniden hesaplanır.'
ISSUE_STEP = {'BUCKLING': 0, 'CYCLE_NOT_CLOSED': 1}


def text_number(value, digits=3):
    """Display only: rounded with a decimal comma. The exact SI value stays in ``_shown``."""
    text = f'{value:.{digits}f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return ('0' if text in ('-0', '') else text).replace('.', ',')


UNIT_TEXT = {'cm3/rev': 'cm³/dev', 'm3': 'm³', 'm2': 'm²'}


def show(value, unit=''):
    if value is None:
        return 'seri dışında'
    digits = 0 if abs(value) >= 100 else 1 if abs(value) >= 10 else 2
    unit = UNIT_TEXT.get(unit, unit)
    return (text_number(value, digits) + (' ' + unit if unit else '')).strip()


def parse_mm(text):
    try:
        value = float(text.strip().replace(',', '.'))
        return value if math.isfinite(value) and value > 0 else None
    except ValueError:
        return None


def polish(widget):
    widget.style().unpolish(widget); widget.style().polish(widget)


# ----------------------------------------------------------------------------- drawings
class CylinderDiagram(QWidget):
    """Kesit görünüşü: piston çapı (iç çap), mil çapı ve strok; gövde dış çapı ayrı gösterilir.

    Ölçekli değildir; piston/mil oranı girilen değerleri izler, odaklanılan ölçü vurgulanır.
    """

    def __init__(self, context):
        super().__init__(); self.context = context
        self.values = {'bore': 63., 'rod': 36., 'stroke': 300.}; self.focus = None
        self.setMinimumSize(320, 230); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setAccessibleName('Silindir ölçü çizimi: piston çapı silindirin iç çapıdır, mil çapı ve strok')

    def set_values(self, values, focus=None):
        self.values.update({k: v for k, v in values.items() if v}); self.focus = focus; self.update()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(460, 250)

    def paintEvent(self, event):
        c = COLORS[self.context.appearance]
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        try:
            p.fillRect(self.rect(), QColor(c['canvas']))
            ink, muted, accent = QColor(c['text']), QColor(c['muted']), QColor(c['accent'])
            steel = QColor(c['border_strong']); oil = QColor(c['accent']); oil.setAlpha(28)
            small = QFont(self.font()); small.setPixelSize(11); p.setFont(small)
            w, h = self.width(), self.height()
            ratio = min(.85, max(.2, self.values['rod'] / max(self.values['bore'], 1e-9)))
            bore_h = min(96., h * .40); wall = 9.; cy = 30 + wall + bore_h / 2 + 6
            x0 = 26.; body = max(140., min(w * .52, w - 210)); x1 = x0 + body
            rod_h = max(8., bore_h * ratio); stroke_px = max(70., min(w - x1 - 70, body * .75))
            piston_x = x0 + body * .46; piston_w = 18.
            # barrel: wall section hatched, bore with oil
            p.setPen(Qt.NoPen); p.setBrush(oil); p.drawRect(QRectF(x0, cy - bore_h / 2, body, bore_h))
            p.setBrush(steel)
            for y in (cy - bore_h / 2 - wall, cy + bore_h / 2):
                p.drawRect(QRectF(x0, y, body, wall))
            p.drawRect(QRectF(x0 - 12, cy - bore_h / 2 - wall, 12, bore_h + 2 * wall))     # cap end
            gland = QRectF(x1, cy - bore_h / 2 - wall, 14, bore_h + 2 * wall)
            p.drawRect(gland)
            # piston and rod (retracted), rod extended ghost
            p.setBrush(QColor(c['muted'])); p.drawRect(QRectF(piston_x, cy - bore_h / 2, piston_w, bore_h))
            rod_end = x1 + 14 + 36
            p.setBrush(QColor(c['panel'])); p.setPen(QPen(ink, 1.2))
            p.drawRect(QRectF(piston_x + piston_w, cy - rod_h / 2, rod_end - piston_x - piston_w, rod_h))
            p.setPen(QPen(muted, 1, Qt.DashLine)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(rod_end, cy - rod_h / 2, stroke_px, rod_h))
            p.setPen(QPen(ink, 1.2)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x0 - 12, cy - bore_h / 2 - wall, body + 26, bore_h + 2 * wall))

            def colour(key):
                return accent if self.focus == key else ink

            def arrow(a, b, pen):
                p.setPen(pen); p.drawLine(a, b)
                for tip, other in ((a, b), (b, a)):
                    d = QPointF(other.x() - tip.x(), other.y() - tip.y()); n = math.hypot(d.x(), d.y()) or 1
                    ux, uy = d.x() / n * 7, d.y() / n * 7
                    p.setBrush(pen.color()); p.setPen(Qt.NoPen)
                    p.drawPolygon(QPolygonF([tip, QPointF(tip.x() + ux - uy * .45, tip.y() + uy + ux * .45),
                                             QPointF(tip.x() + ux + uy * .45, tip.y() + uy - ux * .45)]))
                    p.setPen(pen)

            def width_pen(key):
                return QPen(colour(key), 2 if self.focus == key else 1.2)

            bold = QFont(small); bold.setBold(True)
            # piston diameter: inside the bore, wall to wall
            def text(rect, flags, value, font, pen):
                p.setFont(font); p.setPen(pen)
                p.drawText(rect, flags, p.fontMetrics().elidedText(value, Qt.ElideRight, int(rect.width())))

            bx = x0 + 14
            arrow(QPointF(bx, cy - bore_h / 2 + 1), QPointF(bx, cy + bore_h / 2 - 1), width_pen('bore'))
            text(QRectF(x0 - 12, 6, max(body, 160), 16), Qt.AlignLeft | Qt.AlignVCenter,
                 f"Ø{show(self.values['bore'])} piston çapı = iç çap", bold, colour('bore'))
            p.setPen(QPen(colour('bore'), 1, Qt.DotLine)); p.drawLine(QPointF(bx, 22), QPointF(bx, cy - bore_h / 2 - wall))
            # body outside diameter: not an input
            under = cy + bore_h / 2 + wall
            p.setPen(QPen(muted, 1, Qt.DotLine)); p.drawLine(QPointF(x0 + 30, under), QPointF(x0 + 30, under + 8))
            text(QRectF(x0 - 12, under + 8, body, 16), Qt.AlignLeft | Qt.AlignVCenter, 'Gövde dış çapı: girmeyin', small, muted)
            # rod diameter: on the exposed rod
            rx = x1 + 14 + 22
            arrow(QPointF(rx, cy - rod_h / 2 - 22), QPointF(rx, cy - rod_h / 2), width_pen('rod'))
            arrow(QPointF(rx, cy + rod_h / 2 + 22), QPointF(rx, cy + rod_h / 2), width_pen('rod'))
            text(QRectF(rx - 50, cy - rod_h / 2 - 40, 100, 16), Qt.AlignHCenter, f"Ø{show(self.values['rod'])} mil", bold, colour('rod'))
            # stroke: how far the rod end travels
            sy = cy + bore_h / 2 + wall + 38
            p.setPen(QPen(muted, 1, Qt.DotLine))
            for x in (rod_end, rod_end + stroke_px):
                p.drawLine(QPointF(x, cy + rod_h / 2 + 2), QPointF(x, sy + 6))
            arrow(QPointF(rod_end, sy), QPointF(rod_end + stroke_px, sy), width_pen('stroke'))
            text(QRectF(rod_end - 10, sy + 4, stroke_px + 20, 16), Qt.AlignHCenter, f"Strok {show(self.values['stroke'])} mm", bold, colour('stroke'))
            text(QRectF(rod_end - 4, sy - 20, stroke_px + 8, 14), Qt.AlignHCenter, 'uzamış hâli (kesikli)', small, muted)
            p.drawText(QRectF(8, h - 18, w - 16, 14), Qt.AlignLeft | Qt.AlignVCenter, 'Kesit görünüşü · ölçekli değildir')
        finally:
            p.end()


# ----------------------------------------------------------------------------- small building blocks
class Responsive(QWidget):
    """Side by side when wide, stacked when narrow."""

    def __init__(self, threshold, spacing=16):
        super().__init__(); self.threshold = threshold
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self); self.box.setContentsMargins(0, 0, 0, 0); self.box.setSpacing(spacing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = QBoxLayout.TopToBottom if self.width() < self.threshold else QBoxLayout.LeftToRight
        if self.box.direction() != direction:
            self.box.setDirection(direction)


def panel(role=None):
    frame = QFrame(); frame.setProperty('card', True)
    if role:
        frame.setProperty('tone', role)
    box = QVBoxLayout(frame); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(6)
    return frame, box


class ResultCard(QFrame):
    def __init__(self, title):
        super().__init__(); self.setProperty('card', True)
        box = QVBoxLayout(self); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(3)
        head = QHBoxLayout(); head.setSpacing(6)
        self.title = label(title, 'section', wrap=False); head.addWidget(self.title); head.addStretch(1)
        self.tag = label('', 'muted', wrap=False); self.tag.setProperty('tag', True); head.addWidget(self.tag)
        box.addLayout(head)
        self.value = label('—', 'result', wrap=False); self.value.setTextInteractionFlags(Qt.TextSelectableByMouse); box.addWidget(self.value)
        self.lines = label('', None); self.lines.setTextFormat(Qt.PlainText); box.addWidget(self.lines)
        self.note = label('', 'muted'); box.addWidget(self.note)
        self.state = label('', 'muted'); self.state.hide(); box.addWidget(self.state)
        self.actions = QHBoxLayout(); self.actions.setContentsMargins(0, 4, 0, 0); box.addLayout(self.actions)
        box.addStretch(1)

    def fill(self, tag, value, lines, note, tip='', state=None):
        self.tag.setText(tag); self.value.setText(value); self.lines.setText('\n'.join(lines)); self.note.setText(note)
        self.setToolTip(tip)
        if state:
            role, text = state; self.state.setText(text); self.state.setProperty('role', role); polish(self.state); self.state.show()
        else:
            self.state.hide()


class ResultCards(QWidget):
    """Six decision cards; reflows 3 → 2 → 1 columns. ``rowCount`` = cards with a value."""

    ORDER = ('motor', 'pump', 'pressure', 'pipe', 'tank', 'cooler')
    TITLES = {'motor': 'Motor gücü', 'pump': 'Pompa debisi', 'pressure': 'Çalışma basıncı',
              'pipe': 'Hat iç çapı', 'tank': 'Tank yağ hacmi', 'cooler': 'Soğutucu'}

    def __init__(self):
        super().__init__(); self.grid = QGridLayout(self); self.grid.setContentsMargins(0, 0, 0, 0); self.grid.setSpacing(8)
        self.cards = {key: ResultCard(self.TITLES[key]) for key in self.ORDER}; self.columns = 0; self.count = 0
        self.placeholder = label('Sonuçlar, girilen bilgiler geçerli olduğunda burada görünür.', 'muted')
        self.reflow(3)

    def reflow(self, columns):
        if columns == self.columns:
            return
        self.columns = columns
        for card in self.cards.values():
            self.grid.removeWidget(card)
        self.grid.removeWidget(self.placeholder)
        for i, key in enumerate(self.ORDER):
            self.grid.addWidget(self.cards[key], i // columns, i % columns)
        self.grid.addWidget(self.placeholder, 0, 0, 1, columns)
        for col in range(3):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow(3 if self.width() >= 820 else 2 if self.width() >= 520 else 1)

    def rowCount(self):
        return self.count

    def setRowCount(self, count):
        """Compatibility with the table it replaces: 0 clears every card."""
        if count == 0:
            self.count = 0
            for card in self.cards.values():
                card.hide()
            self.placeholder.show()

    def shown(self, count):
        self.count = count; self.placeholder.hide()
        for card in self.cards.values():
            card.show(); card.setEnabled(True)


class IssueRow(QFrame):
    def __init__(self, severity, problem, action, target):
        super().__init__(); self.setProperty('issue', severity)
        box = QHBoxLayout(self); box.setContentsMargins(10, 6, 8, 6); box.setSpacing(10)
        tag = label('KRİTİK' if severity == 'critical' else 'KONTROL', 'error' if severity == 'critical' else 'warning', wrap=False)
        bold = QFont(tag.font()); bold.setBold(True); tag.setFont(bold); tag.setMinimumWidth(64)
        box.addWidget(tag, 0, Qt.AlignTop)
        text = QVBoxLayout(); text.setSpacing(1)
        text.addWidget(label(problem)); text.addWidget(label('Ne yapabilirsiniz: ' + action, 'muted'))
        box.addLayout(text, 1)
        self.go = None
        if target is not None:
            self.go = button('Göster →', target); self.go.setToolTip('İlgili alanı veya ayarı açar.')
            box.addWidget(self.go, 0, Qt.AlignVCenter)


# ----------------------------------------------------------------------------- the view
class BeginnerView(QWidget):
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.loading = False; self.inputs = {}; self.phase_inputs = []
        self.previous_cycle = None; self.supported = True; self.problem = None; self.step_errors = set()
        self._force_unit = 'kN'; self.cells = []
        box = QVBoxLayout(self); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(8)

        # step bar: where am I, what is next, calculation state
        bar = QHBoxLayout(); bar.setSpacing(4)
        self.step_buttons = []
        for i, title in enumerate(STEP_TITLES):
            if i:
                bar.addWidget(label('›', 'muted', wrap=False))
            b = QPushButton(f'{i + 1}  {title}'); b.setCheckable(True); b.setProperty('step', True)
            b.setAccessibleName(f'Adım {i + 1}: {title}'); b.clicked.connect(lambda _=False, i=i: self.go_to_step(i))
            bar.addWidget(b); self.step_buttons.append(b)
        bar.addStretch(1)
        self.state_pill = label('', 'muted', wrap=False); self.state_pill.setProperty('pill', True); bar.addWidget(self.state_pill)
        box.addLayout(bar)
        self.step_hint = label('', 'muted'); box.addWidget(self.step_hint)

        self.unsupported = label('Bu projede birden fazla silindir veya 12’den fazla hareket var. Verileriniz korunuyor; '
                                 'düzenlemek için görünümü “Ayrıntılı ayarlar” yapın.', 'warning')
        box.addWidget(self.unsupported)
        self.error_box, error_layout = panel('error'); error_row = QHBoxLayout(); error_row.setSpacing(12)
        error_text = QVBoxLayout(); error_text.setSpacing(2)
        heading = label('Girdi hatası · hesap durdu', 'error', wrap=False); f = QFont(heading.font()); f.setBold(True); heading.setFont(f)
        error_text.addWidget(heading)
        self.error_notice = label('', None); self.error_notice.setTextFormat(Qt.PlainText); error_text.addWidget(self.error_notice)
        error_text.addWidget(label('Düzeltene kadar sonuçlar gizlenir ve rapor alınamaz.', 'muted'))
        error_row.addLayout(error_text, 1)
        self.fix_button = button('Alana git →', self.go_to_problem, primary=True); error_row.addWidget(self.fix_button, 0, Qt.AlignVCenter)
        error_layout.addLayout(error_row); self.error_box.hide(); box.addWidget(self.error_box)

        self.steps = QTabWidget(); self.steps.setDocumentMode(True); self.steps.tabBar().hide()
        self.steps.addTab(scroll(self.build_measure()), STEP_TITLES[0])
        self.steps.addTab(scroll(self.build_motion()), STEP_TITLES[1])
        self.steps.addTab(scroll(self.build_report()), STEP_TITLES[2])
        self.steps.currentChanged.connect(self.step_changed)
        box.addWidget(self.steps, 1)

        nav = QHBoxLayout(); nav.setSpacing(8)
        self.back_button = button('← Geri', lambda: self.go_to_step(self.steps.currentIndex() - 1))
        self.next_hint = label('', 'muted', wrap=False)
        self.next_button = button('Devam →', lambda: self.go_to_step(self.steps.currentIndex() + 1), primary=True)
        self.detail_button = button('Ayrıntılı ayarlar…', lambda: owner.open_detailed(0), flat=True)
        self.detail_button.setToolTip('Pompa, hat, yağ, tank, akümülatör ve çok silindirli projeler için tüm ayarlar.')
        nav.addWidget(self.back_button); nav.addWidget(self.detail_button); nav.addStretch(1)
        nav.addWidget(self.next_hint); nav.addWidget(self.next_button)
        box.addLayout(nav)
        self.apply_theme(); self.step_changed(0)

    # ---------------------------------------------------------------- step 1: measurements
    def build_measure(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(4, 4, 4, 4); outer.setSpacing(10)
        outer.addWidget(label('Silindirin ölçüleri', 'section'))
        outer.addWidget(label('Alanlardaki ilk değerler örnektir; kendi silindirinizin değerlerini yazın. '
                              'Bilgiyi silindir etiketinden, teknik resimden veya üretici kataloğundan alın.', 'muted'))
        split = Responsive(720)
        form_box, form = panel(); grid = QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(2)
        grid.setColumnStretch(0, 1)
        row = 0
        for key, (title, help_, example) in FIELDS.items():
            name = label(title, wrap=False); f = QFont(name.font()); f.setBold(True); name.setFont(f)
            grid.addWidget(name, row, 0)
            widget = self.input('cylinder.' + key, title); widget.setPlaceholderText(example); widget.setFixedWidth(110)
            name.setBuddy(widget)
            widget.installEventFilter(self)
            widget.textEdited.connect(self.update_diagram)
            grid.addWidget(widget, row, 1); grid.addWidget(label('mm', 'muted', wrap=False), row, 2)
            hint = label(help_, 'muted'); grid.addWidget(hint, row + 1, 0, 1, 3)
            grid.setRowMinimumHeight(row + 2, 8)
            row += 3
        form.addLayout(grid)
        self.auto_values = label('', 'muted'); self.auto_values.setTextFormat(Qt.PlainText)
        auto_title = label('Otomatik hesaplanan', wrap=False); f = QFont(auto_title.font()); f.setBold(True); auto_title.setFont(f)
        form.addWidget(auto_title); form.addWidget(self.auto_values); form.addStretch(1)
        split.box.addWidget(form_box, 5)
        draw_box, draw = panel(); self.diagram = CylinderDiagram(self.owner.context); draw.addWidget(self.diagram, 1)
        split.box.addWidget(draw_box, 6)
        outer.addWidget(split); outer.addStretch(1)
        return page

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.FocusIn, QEvent.FocusOut) and isinstance(watched, QLineEdit):
            key = next((k.split('.', 1)[1] for k, w in self.inputs.items() if w is watched and k.startswith('cylinder.')), None)
            self.diagram.set_values({}, key if event.type() == QEvent.FocusIn else None)
        return super().eventFilter(watched, event)

    def update_diagram(self, *args):
        values = {key: parse_mm(self.inputs['cylinder.' + key].text()) for key in FIELDS}
        self.diagram.set_values(values, self.diagram.focus)

    # ---------------------------------------------------------------- step 2: motions
    def build_motion(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(4, 4, 4, 4); outer.setSpacing(10)
        head = QHBoxLayout(); head.setSpacing(8)
        head.addWidget(label('Makine sırayla ne yapsın?', 'section'), 1)
        head.addWidget(label('Kuvvet birimi', 'muted', wrap=False))
        self.force_unit = QComboBox(); self.force_unit.addItem('Kilonewton (kN)', 'kN'); self.force_unit.addItem('Ton-kuvvet (tonf)', 'tonf')
        self.force_unit.setAccessibleName('Kuvvet birimi')
        self.force_unit.setToolTip('Ton-kuvvet bir kuvvet birimidir, yükün kütlesi değildir. 1 tonf = 9,80665 kN.')
        self.force_unit.currentIndexChanged.connect(self.change_force_unit); head.addWidget(self.force_unit)
        outer.addLayout(head)
        outer.addWidget(label('Her satır bir harekettir ve yukarıdan aşağı sırayla yapılır. Yol: milin o harekette gittiği mesafe. '
                              'Kuvvet: milin yenmesi gereken yük (itme veya çekme). 1 tonf = 9,81 kN; ton-kuvvet yükün kütlesi '
                              'değildir — sürtünme ve mekanizma oranı gerçek kuvveti değiştirir.', 'muted'))
        table_box, table = panel()
        self.motion_grid = QGridLayout(); self.motion_grid.setHorizontalSpacing(14); self.motion_grid.setVerticalSpacing(6)
        self.motion_grid.setColumnMinimumWidth(0, 130); self.motion_grid.setColumnStretch(4, 1)   # spare width after the inputs
        headers = ('Hareket', 'Ne kadar yol alsın?\nmilin bu hareketteki yolu', 'Kaç saniye sürsün?\nhareketin süresi', '')
        self.header_labels = []
        for col, text in enumerate(headers):
            h = label(text, wrap=False); f = QFont(h.font()); f.setBold(True); h.setFont(f)
            self.motion_grid.addWidget(h, 0, col); self.header_labels.append(h)
        self.force_header = self.header_labels[3]
        self.force_header.setText(self.force_title())
        table.addLayout(self.motion_grid)
        self.derived_note = label('Eğik yazılı süreler hızdan hesaplanmıştır; üzerine yazarsanız süre esas alınır.', 'muted')
        table.addWidget(self.derived_note)
        outer.addWidget(table_box)
        actions = QHBoxLayout(); actions.setSpacing(8)
        self.example_button = button('İleri – bekle – geri örneğini kur', self.owner.use_basic_cycle)
        self.example_button.setToolTip('Silindirin ölçülerini koruyup üç adımlı örnek bir hareket sırası yazar. Geri alınabilir.')
        self.undo_button = button('Önceki hareketlere dön', self.owner.undo_basic_cycle)
        more = button('Silindir veya hareket ekle… (Ayrıntılı ayarlar)', lambda: self.owner.open_detailed(1), flat=True)
        for widget in (self.example_button, self.undo_button, more):
            actions.addWidget(widget)
        actions.addStretch(1); outer.addLayout(actions)
        self.motion_chart = MotionStrip(); self.motion_chart.appearance = self.owner.context.appearance
        outer.addWidget(self.motion_chart); outer.addStretch(1)
        return page

    # ---------------------------------------------------------------- step 3: results and report
    def build_report(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(4, 4, 4, 4); outer.setSpacing(10)
        banner, b = panel(); top = QHBoxLayout(); top.setSpacing(12)
        words = QVBoxLayout(); words.setSpacing(2)
        self.verdict = label('', 'section'); self.verdict.setTextFormat(Qt.PlainText); words.addWidget(self.verdict)
        self.explanation = label('', 'muted'); self.explanation.setTextFormat(Qt.PlainText); words.addWidget(self.explanation)
        top.addLayout(words, 1)
        reports = QVBoxLayout(); reports.setSpacing(4)
        row = QHBoxLayout(); row.setSpacing(6)
        self.pdf_button = button('PDF raporu al…', self.owner.export_pdf, primary=True)
        self.excel_button = button('Excel tablosu al…', lambda: self.owner.export('excel'))
        self.cancel_pdf_button = button('Raporu durdur', self.owner.cancel_pdf, destructive=True); self.cancel_pdf_button.hide()
        for widget in (self.pdf_button, self.excel_button, self.cancel_pdf_button):
            row.addWidget(widget)
        reports.addLayout(row)
        self.status = label('', 'muted'); self.status.setTextFormat(Qt.PlainText); self.status.setAlignment(Qt.AlignRight)
        reports.addWidget(self.status)
        top.addLayout(reports)
        b.addLayout(top); outer.addWidget(banner)

        issues_box, issues = panel()
        self.warnings = label('', 'section'); self.warnings.setTextFormat(Qt.PlainText); issues.addWidget(self.warnings)
        self.issue_rows = QVBoxLayout(); self.issue_rows.setSpacing(4); issues.addLayout(self.issue_rows)
        outer.addWidget(issues_box)

        outer.addWidget(label('Ne seçmeliyim?', 'section'))
        outer.addWidget(label('Her kartta ne olduğu yazar: İHTİYAÇ hareketler için gereken değerdir, MEVCUT projedeki elemandır, '
                              'ÖNERİ standart seriden bir üst değerdir. Öneriler üretici veya imalat onayı değildir.', 'muted'))
        self.results = ResultCards(); outer.addWidget(self.results)
        self.pump_button = button('Önerilen pompa hacmini uygula', self.owner.use_pump_recommendation)
        self.pump_button.setToolTip(PUMP_TIP)
        self.results.cards['pump'].actions.addWidget(self.pump_button); self.results.cards['pump'].actions.addStretch(1)
        for key, (text, tab) in {'pipe': ('Hat ayarlarını aç', 3), 'tank': ('Tank ayarlarını aç', 4),
                                 'cooler': ('Isı ayarlarını aç', 4), 'motor': ('Motor ayarlarını aç', 2)}.items():
            card = self.results.cards[key]; card.actions.addWidget(button(text, lambda _=False, t=tab: self.owner.open_detailed(t), flat=True))
            card.actions.addStretch(1)

        charts = Responsive(760, 8)
        self.charts = {'pressure': StepChart('Gerekli basınç', 'bar'), 'shaft_power': StepChart('Pompa mil gücü', 'kW')}
        for chart in self.charts.values():
            chart.appearance = self.owner.context.appearance; chart.setMinimumHeight(170); charts.box.addWidget(chart, 1)
        outer.addWidget(label('Çevrim boyunca', 'section'))
        outer.addWidget(label('Basınç ve güç, hareketlerin gerektirdiği değerdir (pompanın verdiği değil). Mil gücü pompa milindeki '
                              'güçtür; elektrik şebekesinden çekilen güç değildir.', 'muted'))
        outer.addWidget(charts)
        self.assumptions = label('', 'muted'); self.assumptions.setTextFormat(Qt.PlainText)
        outer.addWidget(Disclosure('Varsayımlar, örnek değerler ve sınırlar', self.assumptions))
        outer.addStretch(1)
        return page

    # ---------------------------------------------------------------- navigation and state
    def go_to_step(self, index):
        if 0 <= index < self.steps.count():
            self.steps.setCurrentIndex(index)

    def step_changed(self, index):
        for i, b in enumerate(self.step_buttons):
            b.setChecked(i == index)
            title = f'{i + 1}  {STEP_TITLES[i]}' + ('  ·  düzeltin' if i in self.step_errors else '')
            b.setText(title); b.setProperty('problem', i in self.step_errors); polish(b)
        self.step_hint.setText(f'Adım {index + 1}/3 · {STEP_HINTS[index]}')
        self.back_button.setEnabled(index > 0)
        last = index == self.steps.count() - 1
        self.next_button.setVisible(not last); self.next_hint.setVisible(not last)
        self.next_hint.setText(NEXT_HINTS[index])
        self.next_button.setText('Devam: ' + STEP_TITLES[min(index + 1, 2)] + ' →')
        first = {0: self.inputs.get('cylinder.bore'), 1: (self.phase_inputs[0].get('stroke') or self.phase_inputs[0].get('duration'))
                 if self.phase_inputs else None, 2: None}.get(index)
        if first is not None and self.isVisible() and not self.loading:
            first.setFocus(Qt.OtherFocusReason)

    def set_state(self, role, text):
        self.state_pill.setText(text); self.state_pill.setProperty('role', role); polish(self.state_pill)

    def mark_pending(self):
        """Inputs changed: results are stale until the debounced calculation finishes."""
        self.set_state('muted', 'Hesaplanıyor…')
        self.verdict.setText('Bilgiler değişti; hesap güncelleniyor…')
        for card in self.results.cards.values():
            card.setEnabled(False)

    def on_status(self, text, error=False):
        lowered = text.lower()
        if any(word in lowered for word in ('rapor', 'pdf', 'excel', 'iptal', 'kaydedil', 'açıldı', 'uygulandı')):
            self.status.setText(text)
            if 'iptal' in lowered:
                self.set_state('warning', 'Rapor iptal edildi')
            elif error:
                self.set_state('error', 'Rapor alınamadı')

    def apply_theme(self):
        c = COLORS[self.owner.context.appearance]
        self.setStyleSheet(f'''
            QPushButton[step="true"] {{ border: 1px solid {c['border']}; border-radius: 12px; padding: 4px 16px; font-weight: 600;
                                        color: {c['muted']}; background: transparent; }}
            QPushButton[step="true"]:hover {{ color: {c['text']}; border-color: {c['border_strong']}; }}
            QPushButton[step="true"]:checked {{ color: {c['on_accent']}; background: {c['accent']}; border-color: {c['accent']}; }}
            QPushButton[step="true"][problem="true"] {{ color: {c['danger']}; border-color: {c['danger']}; }}
            QPushButton[step="true"][problem="true"]:checked {{ color: {c['on_accent']}; background: {c['danger']}; }}
            QLabel[pill="true"] {{ border: 1px solid {c['border']}; border-radius: 10px; padding: 2px 10px; }}
            QLabel[pill="true"][role="success"] {{ border-color: {c['success']}; }}
            QLabel[pill="true"][role="warning"] {{ border-color: {c['warning']}; }}
            QLabel[pill="true"][role="error"] {{ border-color: {c['danger']}; }}
            QLabel[tag="true"] {{ font-size: 10px; font-weight: 600; letter-spacing: 0.5px; }}
            QFrame[tone="error"] {{ border: 1px solid {c['danger']}; border-left: 4px solid {c['danger']}; }}
            QFrame[issue="critical"] {{ border-left: 3px solid {c['danger']}; background: {c['panel']}; }}
            QFrame[issue="warning"] {{ border-left: 3px solid {c['warning']}; background: {c['panel']}; }}
            QLineEdit[derived="true"] {{ font-style: italic; color: {c['muted']}; }}
        ''')
        for widget in (getattr(self, 'diagram', None), getattr(self, 'motion_chart', None), *getattr(self, 'charts', {}).values()):
            if widget is not None:
                widget.appearance = self.owner.context.appearance; widget.update()

    # ---------------------------------------------------------------- inputs
    def input(self, key, title):
        w = QLineEdit(); w.setAccessibleName(title); w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        w.textEdited.connect(self.owner.changed); w.textEdited.connect(lambda *_: self.mark_pending())
        w.textEdited.connect(lambda *_, w=w: (w.setProperty('derived', False), polish(w)) if w.property('derived') else None)
        self.inputs[key] = w
        return w

    def set_value(self, widget, value):
        widget.setText(text_number(value)); widget._shown = (widget.text(), value)

    def value(self, widget, field):
        shown = getattr(widget, '_shown', None)
        if shown is not None and shown[0] == widget.text():
            return shown[1]
        try:
            value = float(widget.text().strip().replace(',', '.'))
            if not math.isfinite(value):
                raise ValueError
            return value
        except ValueError:
            raise InputError(field, 'Sayı girin; örneğin 63 veya 2,5.') from None

    def populate(self, project):
        self.loading = True
        try:
            self.supported = simple_supported(project); self.unsupported.setVisible(not self.supported)
            self.steps.setEnabled(self.supported); self.undo_button.setEnabled(self.previous_cycle is not None)
            for b in self.step_buttons:
                b.setEnabled(self.supported)
            if not self.supported:
                return
            for key in FIELDS:
                self.set_value(self.inputs['cylinder.' + key], getattr(project.cylinders[0], key) * 1000)
            self.update_diagram()
            for widget in self.cells:
                self.motion_grid.removeWidget(widget); widget.hide(); widget.deleteLater()
            self.cells = []
            self.inputs = {k: w for k, w in self.inputs.items() if k.startswith('cylinder.')}
            self.phase_inputs = []; factor = FORCE_FACTORS[self.force_unit.currentData()]
            derived_any = False
            for i, phase in enumerate(project.phases):
                row = i + 1; controls = {}
                name = QWidget(); nb = QVBoxLayout(name); nb.setContentsMargins(0, 0, 0, 0); nb.setSpacing(0)
                title = label(f'{i + 1}. {phase.name}', wrap=False); f = QFont(title.font()); f.setBold(True); title.setFont(f)
                nb.addWidget(title); nb.addWidget(label(f'{DIRECTION[phase.kind]}  {MOVEMENTS[phase.kind]}', 'muted'))
                self.place(name, row, 0)
                if phase.kind in ('hold', 'idle'):
                    na = label('— yerinde (yol yok)', 'muted', wrap=False)
                    na.setToolTip('Bekleme ve boşta durumunda mil hareket etmez; yalnız süre girilir.')
                    self.place(na, row, 1)
                else:
                    controls['stroke'] = self.cell(f'phase.{i}.stroke', 'Ne kadar yol alsın?', phase.stroke * 1000, 'mm', row, 1)
                controls['duration'] = self.cell(f'phase.{i}.duration', 'Kaç saniye sürsün?', phase_seconds(phase), 's', row, 2)
                if phase.duration is None:
                    derived_any = True; w = controls['duration']; w.setProperty('derived', True); polish(w)
                    w.setToolTip(f'Hızdan hesaplandı: {text_number(phase.speed * 1000)} mm/s. Yazarsanız süre esas alınır.')
                if phase.kind == 'idle':
                    na = label('— yük yok', 'muted', wrap=False); na.setToolTip('Boşta harekette silindir yük taşımaz.')
                    self.place(na, row, 3)
                else:
                    w = self.cell(f'phase.{i}.force', 'Gerekli itme / çekme kuvveti', phase.force / factor, self.force_symbol(), row, 3)
                    w._force_label = self.force_header; w._si_force = phase.force; controls['force'] = w
                self.phase_inputs.append(controls)
            self.derived_note.setVisible(derived_any)
        finally:
            self.loading = False

    def place(self, widget, row, col):
        self.motion_grid.addWidget(widget, row, col); self.cells.append(widget)

    def cell(self, key, title, value, unit, row, col):
        holder = QWidget(); hb = QHBoxLayout(holder); hb.setContentsMargins(0, 0, 0, 0); hb.setSpacing(4)
        widget = self.input(key, f'{title} · {unit}'); widget.setFixedWidth(96); self.set_value(widget, value)
        hb.addWidget(widget); unit_label = label(unit, 'muted', wrap=False); unit_label.setMinimumWidth(30); hb.addWidget(unit_label)
        widget._unit_label = unit_label; hb.addStretch(1)
        self.place(holder, row, col)
        return widget

    def force_title(self):
        return 'Gerekli itme / çekme kuvveti\n' + self.force_unit.currentText()

    def force_symbol(self):
        return 'kN' if self.force_unit.currentData() == 'kN' else 'tonf'

    def read_project(self, base):
        if not self.supported:
            return base
        c = base.cylinders[0]
        sizes = {}
        for key in FIELDS:
            widget = self.inputs['cylinder.' + key]; value = self.value(widget, f'cylinders.0.{key}')
            if widget.text() != getattr(widget, '_shown', ('', None))[0]:
                sizes[key] = value / 1000
        cylinder = replace(c, **sizes)
        try:
            areas(cylinder); buckling(cylinder, 0)
        except InputError as error:
            raise InputError('cylinders.0.' + error.field, str(error)) from None
        except ArithmeticError as error:
            raise InputError('cylinders.0.bore', 'Ölçü çok büyük; milimetre cinsinden gerçek değeri girin.') from error
        phases = []; factor = FORCE_FACTORS[self.force_unit.currentData()]
        for i, (phase, controls) in enumerate(zip(base.phases, self.phase_inputs)):
            values = {k: self.value(w, f'phases.{i}.{k}') for k, w in controls.items()}
            changed = {k for k, w in controls.items() if getattr(w, '_shown', ('', None))[0] != w.text()}
            update = {}
            if 'force' in controls:
                update['force'] = values['force'] * factor if 'force' in changed else controls['force']._si_force
            if 'stroke' in changed:
                update['stroke'] = values['stroke'] / 1000
            if changed & {'duration', 'stroke'}:
                update.update(speed=None, duration=values['duration'])
            phases.append(replace(phase, **update))
        return replace(base, cylinders=(cylinder,), phases=tuple(phases), name=self.owner.name.text(),
                       display_units=self.owner.units.currentData())

    def change_force_unit(self):
        if self.loading:
            return
        # The typed number is read in the previous unit; switching never changes the physical force.
        new = self.force_unit.currentData(); old = self._force_unit
        candidates = []
        for i, controls in enumerate(self.phase_inputs):
            if 'force' not in controls:
                continue
            w = controls['force']
            try:
                value = self.value(w, f'phases.{i}.force')
                force = w._si_force if getattr(w, '_shown', ('', None))[0] == w.text() else value * FORCE_FACTORS[old]
            except InputError:
                self.force_unit.blockSignals(True); self.force_unit.setCurrentIndex(self.force_unit.findData(old)); self.force_unit.blockSignals(False)
                self.status.setText('Birim değiştirmeden önce kuvvet alanındaki sayıyı düzeltin.')
                self.set_state('error', 'Kuvvet alanını düzeltin'); w.setFocus(); return
            candidates.append((w, force))
        for w, force in candidates:
            self.set_value(w, force / FORCE_FACTORS[new]); w._si_force = force; w._unit_label.setText(self.force_symbol())
        self.force_header.setText(self.force_title())
        self._force_unit = new

    # ---------------------------------------------------------------- results
    def show_result(self, project, result):
        self.error_box.hide(); self.problem = None; self.step_errors = set()
        for widget in self.inputs.values():
            if widget.property('invalid'):          # restore only what the error replaced
                widget.setToolTip(getattr(widget, '_tip', ''))
            widget.setProperty('invalid', False); polish(widget)
        cycle, thermal = result.cycle, result.thermal
        critical = [i for i in result.issues if i.severity == 'critical']
        warning = [i for i in result.issues if i.severity == 'warning']
        if not cycle['demand_met']:
            self.verdict.setText('✕  Pompa bu hareketlere yetişemiyor')
            self.verdict.setProperty('role', 'error')
            self.explanation.setText('Hareket sürelerini uzatın, kuvveti azaltın veya önerilen pompa hacmini uygulayın. '
                                     'Aşağıdaki değerler ancak bir tasarım senaryosudur.')
        elif critical:
            topics = ', '.join(dict.fromkeys(TOPIC.get(i.code, 'diğer') for i in critical))
            self.verdict.setText(f'!  Hesap tamam · {len(critical)} kritik konu çözülmeli: {topics}')
            self.verdict.setProperty('role', 'error')
            self.explanation.setText('Pompa hareketleri karşılıyor; ancak aşağıdaki kritik konu(lar) çözülmeden ünite uygun sayılmaz.')
        elif warning:
            topics = ', '.join(dict.fromkeys(TOPIC.get(i.code, 'diğer') for i in warning))
            self.verdict.setText(f'!  Hesap tamam · {len(warning)} konu kontrol edilmeli: {topics}')
            self.verdict.setProperty('role', 'warning')
            self.explanation.setText('Ön boyutlandırma tamam. Aşağıdaki kontrolleri yapıp gerçek ürün verileriyle doğrulayın.')
        else:
            self.verdict.setText('✓  Ön boyutlandırma tamam')
            self.verdict.setProperty('role', 'success')
            self.explanation.setText('Kritik konu yok. Kullanım öncesinde gerçek ürün bilgileri ve uzman kontrolü gereklidir.')
        if thermal.get('status') == 'scenario_only':
            self.explanation.setText(self.explanation.text() + ' Isı ve soğutma değerleri varsayımsal senaryodur.')
        polish(self.verdict)
        self.set_state('error' if critical or not cycle['demand_met'] else 'warning' if warning else 'success',
                       'Hesap güncel' + (f' · {len(critical)} kritik' if critical else f' · {len(warning)} kontrol' if warning else ' · uygun'))
        self.show_issues(critical, warning)
        self.fill_cards(project, result)
        self.fill_charts(project, result)
        a1, a2, ratio = areas(project.cylinders[0])
        self.auto_values.setText(f'İtme alanı (piston): {show(a1 * 1e4, "cm²")}\nÇekme alanı (halka): {show(a2 * 1e4, "cm²")}\n'
                                 f'Alan oranı: {show(ratio)}  — geri çekme aynı basınçta bu oran kadar zayıf, aynı debide bu oran kadar hızlıdır.')
        info = [i.message for i in result.issues if i.severity == 'info']
        rpm = project.pump.angular_speed * 60 / (2 * math.pi)
        self.assumptions.setText('\n'.join(
            [f'• Pompa, verim, yağ, hat ve tank ayarları projeden alınır (şu an {show(project.pump.displacement * 1e6, "cm³/dev")}, '
             f'{rpm:.0f} dev/dak). Ayrıntılı ayarlardan değiştirebilirsiniz.',
             '• İlk açılış değerleri ve hazır yağ eğrileri örnektir.', '• Öneriler nominal seriden seçilir; üretici veya imalat onayı değildir.']
            + ['• ' + text for text in result.assumptions] + ['• ' + text for text in info]))
        self.step_changed(self.steps.currentIndex())

    def show_issues(self, critical, warning):
        while self.issue_rows.count():
            item = self.issue_rows.takeAt(0)
            if item.widget():
                item.widget().hide(); item.widget().deleteLater()
        if critical:
            self.warnings.setText(f'Önemli: {len(critical)} kritik konu' + (f' · {len(warning)} kontrol' if warning else ''))
            self.warnings.setProperty('role', 'error')
        elif warning:
            self.warnings.setText(f'Kontrol edin: {len(warning)} konu'); self.warnings.setProperty('role', 'warning')
        else:
            self.warnings.setText('Yapılması gereken bir konu yok'); self.warnings.setProperty('role', 'success')
        polish(self.warnings)
        for issue in critical + warning:
            problem, action = PLAIN_ISSUES.get(issue.code, (issue.message, 'Ayrıntılı ayarlarda ilgili bölümü inceleyin.'))
            target = (lambda _=False, issue=issue: self.go_to_field(issue.field, ISSUE_STEP.get(issue.code)))
            self.issue_rows.addWidget(IssueRow(issue.severity, problem, action, target))

    def fill_cards(self, project, result):
        rows = {name: (value, unit, formula) for name, value, unit, formula in result_rows(project, result)}
        cycle, pipe, thermal = result.cycle, result.pipe, result.thermal
        pressure_unit = rows['Maksimum gerekli basınç'][1]
        v = lambda name: show(rows[name][0], rows[name][1]) if name in rows else '—'
        tip = lambda *names: '\n'.join(f'{n}: {rows[n][2]}' for n in names if n in rows)
        cards = self.results.cards
        own_motor = project.selected_motor is not None
        cards['motor'].fill('SİZİN SEÇİMİNİZ' if own_motor else 'ÖNERİ', v('Seçilen motor'),
                            [f'İhtiyaç (en yüksek mil gücü): {v("Tepe mil gücü")}', f'Sürekli ortalama (RMS): {v("RMS mil gücü")}'],
                            'Elektrik motorunun etiket gücü. Mil gücü, şebekeden çekilen güç değildir.',
                            tip('Seçilen motor', 'Tepe mil gücü', 'RMS mil gücü'))
        rpm = project.pump.angular_speed * 60 / (2 * math.pi)
        nominal = cycle['displacement']['nominal']
        cards['pump'].fill('İHTİYAÇ', v('Maksimum gerekli debi'),
                           [f'Gereken pompa hacmi: {v("Gerekli deplasman")}',
                            f'Mevcut pompa: {show(project.pump.displacement * 1e6, "cm³/dev")} · {rpm:.0f} dev/dak',
                            f'Öneri (nominal seri): {show(None if nominal is None else nominal * 1e6, "cm³/dev")}'],
                           'Hareketler için dakikada gereken en fazla yağ miktarı.',
                           tip('Maksimum gerekli debi', 'Gerekli deplasman', 'Nominal deplasman adayı'),
                           None if cycle['demand_met'] else ('error', 'Mevcut pompa yetersiz'))
        cards['pressure'].fill('İHTİYAÇ', v('Maksimum gerekli basınç'),
                               [f'Emniyet valfi ayarı: {v("Emniyet valfi ayarı")}' + (' (öneri)' if project.relief_pressure is None else ' (sizin)'),
                                f'Mevcut pompanın sınırı: {show(convert(project.pump.max_pressure, "Pa", pressure_unit), pressure_unit)}',
                                f'Hat basınç kaybı: {v("Hat basınç kaybı")}'],
                               'Yükü hareket ettirmek için hattaki en yüksek basınç (hat kayıpları dahil).',
                               tip('Maksimum gerekli basınç', 'Emniyet valfi ayarı', 'Hat basınç kaybı'))
        user_pipe = project.pipe.diameter is not None
        cards['pipe'].fill('SİZİN GİRDİĞİNİZ' if user_pipe else 'ÖNERİ', v('Boru/hortum iç çapı'),
                           [f'En az gereken iç çap: {show(pipe["required_diameter"] * 1000, "mm")}',
                            f'Bu çapta yağ hızı: {v("Gerçek hat hızı")}'],
                           'Hortum veya borunun İÇ çapı; dış çap ya da bağlantı ölçüsü değildir. Basınç dayanımını üreticiden doğrulayın.',
                           tip('Boru/hortum iç çapı', 'Gerçek hat hızı', 'Hat basınç kaybı'))
        enough = thermal['usable_volume'] >= thermal['required_volume']
        cards['tank'].fill('İHTİYAÇ', v('Gerekli kullanılabilir tank'),
                           [f'Mevcut tankın kullanılabilir hacmi: {v("Mevcut kullanılabilir tank")}'],
                           'Tankta kullanılabilir yağ hacmi; tankın dış (brüt) hacmi değildir.',
                           tip('Gerekli kullanılabilir tank', 'Mevcut kullanılabilir tank'),
                           ('success', 'Mevcut tank yeterli') if enough else ('error', 'Mevcut tank küçük'))
        target = convert(project.thermal.target, 'K', '°C')
        scenario = thermal.get('status') == 'scenario_only'
        cards['cooler'].fill('İHTİYAÇ' + (' · SENARYO' if scenario else ''), v('Gerekli soğutucu'),
                             [f'Soğutucusuz yağ sıcaklığı: {v("Soğutucusuz denge")}', f'Hedef yağ sıcaklığı: {show(target, "°C")}'],
                             'Yağı hedef sıcaklıkta tutmak için atılması gereken ısı. 0 kW ise soğutucu gerekmez.',
                             tip('Gerekli soğutucu', 'Soğutucusuz denge', 'Çevrim ortalama ısı yükü'),
                             ('warning', 'Varsayımsal: pompa yetersizken hesaplandı') if scenario else None)
        self.results.shown(6)

    def fill_charts(self, project, result):
        phases = result.cycle['phases']
        unit = 'psi' if project.display_units == 'us' else 'bar'
        durations = [f.duration for f in phases]; names = [f.name for f in phases]
        self.charts['pressure'].unit = unit
        self.charts['pressure'].set_values(durations, [convert(f.pressure, 'Pa', unit) for f in phases], names)
        self.charts['shaft_power'].set_values(durations, [f.shaft_power / 1000 for f in phases], names)
        self.motion_chart.set_segments([(f.name, f.duration, f.start_position * 1000, f.end_position * 1000, f.feasible) for f in phases])

    def show_error(self, error):
        self.problem = error.field
        self.error_notice.setText(str(error)); self.error_box.show()
        self.verdict.setText('Önce girilen bilgileri düzeltin'); self.verdict.setProperty('role', 'error'); polish(self.verdict)
        self.explanation.setText(str(error))
        self.results.setRowCount(0); self.show_issues([], [])
        self.warnings.setText('Sonuç yok: girdi hatası'); self.warnings.setProperty('role', 'error'); polish(self.warnings)
        for chart in self.charts.values():
            chart.set_values([], [])
        self.motion_chart.set_segments([])
        self.auto_values.setText('Ölçüler geçerli olduğunda hesaplanır.')
        key = self.input_key(error.field)
        for name, w in self.inputs.items():
            if name == key and not getattr(w, '_tip', None):
                w._tip = w.toolTip()
            w.setProperty('invalid', name == key); polish(w)
            w.setToolTip(str(error) if name == key else getattr(w, '_tip', w.toolTip()))
        step = 0 if key and key.startswith('cylinder.') else 1 if key or error.field.startswith('phases') else None
        self.step_errors = {step} if step is not None else set()
        self.fix_button.setText('Alana git →' if key else 'İlgili ayarı aç →')
        self.set_state('error', 'Girdi hatası · hesap durdu')
        self.status.setText(str(error))
        self.step_changed(self.steps.currentIndex())

    def input_key(self, field):
        parts = field.split('.')
        if len(parts) >= 3 and parts[0] == 'cylinders' and parts[2] in FIELDS:
            return 'cylinder.' + parts[2]
        if len(parts) >= 3 and parts[0] == 'phases':
            key = 'phase.' + parts[1] + '.' + parts[2]
            return key if key in self.inputs else None
        return None

    def go_to_field(self, field, step=None):
        key = self.input_key(field or '')
        if key:
            self.go_to_step(0 if key.startswith('cylinder.') else 1)
            widget = self.inputs[key]

            def focus():   # after the page switch settles, or the stack moves focus to its first field
                widget.setFocus(Qt.OtherFocusReason); widget.selectAll()
                container = self.steps.currentWidget()
                if hasattr(container, 'ensureWidgetVisible'):
                    container.ensureWidgetVisible(widget)
            focus(); QTimer.singleShot(0, focus)
        elif step is not None:
            self.go_to_step(step)
        else:
            self.owner.navigate_to_field(field or '')

    def go_to_problem(self):
        self.go_to_field(self.problem)

    def update_actions(self, result, busy, pdf_active):
        ready = result is not None and not busy and not pdf_active
        reason = '' if ready else ('Rapor hazırlanıyor.' if pdf_active or busy else 'Rapor için önce geçerli bir sonuç gerekli.')
        for widget in (self.pdf_button, self.excel_button):
            widget.setEnabled(ready); widget.setToolTip(reason)
        nominal_ok = result is not None and result.cycle['displacement']['nominal'] is not None
        self.pump_button.setEnabled(ready and nominal_ok)
        self.pump_button.setToolTip(PUMP_TIP if nominal_ok else 'Önerilen değer nominal seri dışında; üreticiye danışın.')
        self.cancel_pdf_button.setVisible(pdf_active)
        if pdf_active:
            self.set_state('muted', 'PDF hazırlanıyor…')
