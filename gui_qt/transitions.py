"""Subtle page transition for the workspace stack.

A background-coloured veil covers the newly selected page and fades out in
about 150 ms. Pages themselves are never wrapped in graphics effects, so
OpenGL previews, native windows and focus behave exactly as without it.
"""

import os

from PySide6.QtCore import Property, QEasingCurve, QEvent, QObject, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QApplication, QWidget

DURATION_MS = 150
_HEADLESS = ('offscreen', 'minimal')


class _Veil(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self._opacity = 0.0
        self.color = QColor('#000000')
        self.hide()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = float(value)
        self.update()

    def paintEvent(self, event):
        if self._opacity <= 0:
            return
        painter = QPainter(self)
        color = QColor(self.color)
        color.setAlphaF(self._opacity)
        painter.fillRect(self.rect(), color)


class PageTransition(QObject):
    """Fade the stack's new page in from the workspace background."""

    def __init__(self, stack, enabled=True):
        super().__init__(stack)
        self.stack = stack
        self.enabled = bool(enabled)
        # Automated/headless runs grab windows right after navigation; keep
        # them deterministic unless a test opts in explicitly.
        self.headless_allowed = False
        self.veil = _Veil(stack)
        self.animation = QPropertyAnimation(self, b'opacity', self)
        self.animation.setDuration(DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.veil.hide)
        stack.installEventFilter(self)

    def _get(self):
        return self.veil.get_opacity()

    def _set(self, value):
        self.veil.set_opacity(value)

    opacity = Property(float, _get, _set)

    def active(self):
        if not self.enabled or not self.stack.isVisible():
            return False
        if self.headless_allowed:
            return True
        if os.environ.get('GOKWORKS_PAGE_TRANSITIONS', '1') == '0':
            return False
        return QApplication.platformName() not in _HEADLESS

    def play(self, color):
        """Start the fade over the page that is now current."""
        if not self.active():
            self.stop()
            return False
        self.veil.color = QColor(color)
        self.veil.setGeometry(self.stack.rect())
        self.animation.stop()
        self.veil.set_opacity(1.0)
        self.veil.show(); self.veil.raise_()
        # Start the clock after the new page has been laid out and painted,
        # so a first-time (lazy) page build does not eat the fade.
        QTimer.singleShot(0, self._start)
        return True

    def _start(self):
        if self.veil.isVisible() and self.animation.state() != QPropertyAnimation.Running:
            self.animation.start()

    def stop(self):
        self.animation.stop()
        self.veil.set_opacity(0.0)
        self.veil.hide()

    def eventFilter(self, watched, event):
        if watched is self.stack and event.type() == QEvent.Resize:
            self.veil.setGeometry(self.stack.rect())
        return super().eventFilter(watched, event)
