"""App controls that let Tk finish a paint in its normal event-loop turn.

CustomTkinter 6.0.0 flushes all idle layout work at the end of each scrollbar
and option-menu paint. During a resize those calls reenter other widgets'
paint/layout callbacks. Suppress only that canvas's flush while drawing;
explicit application geometry flushes and ordinary Tk painting remain intact.
"""

from functools import partial

import customtkinter as ctk


def _paint_without_idle_flush(canvas, draw, no_color_updates=False):
    flush = canvas.update_idletasks
    canvas.update_idletasks = lambda: None
    try:
        return draw(no_color_updates=no_color_updates)
    finally:
        canvas.update_idletasks = flush


class _EventLoopPaint:
    def _draw(self, no_color_updates=False):
        return _paint_without_idle_flush(self._canvas, super()._draw, no_color_updates)


class AppScrollbar(_EventLoopPaint, ctk.CTkScrollbar):
    def set(self, start_value, end_value):
        # Canvas and Treeview report the same fractions during repeated layout.
        # Size, DPI, appearance and hover changes have their own draw paths.
        values = float(start_value), float(end_value)
        if values != self.get():
            super().set(*values)


class AppOptionMenu(_EventLoopPaint, ctk.CTkOptionMenu):
    pass


class AppScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # CTkScrollableFrame creates its own scrollbar internally. Keep that
        # implementation and its bindings, but give its paints the same rule.
        bar = self._scrollbar
        bar._draw = partial(_paint_without_idle_flush, bar._canvas, bar._draw)
