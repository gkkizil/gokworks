"""Real Tk checks for event-loop paints and root Configure event routing."""

from unittest.mock import patch

from support.gui import GuiTestCase
from gui.widgets import AppOptionMenu, AppScrollableFrame, AppScrollbar


class RenderingEventTests(GuiTestCase):
    def test_option_menu_does_not_run_unrelated_idle_callbacks_while_painting(self):
        menu = self.app.filter_menu
        self.assertIsInstance(menu, AppOptionMenu)
        idle = []
        self.app.after_idle(lambda: idle.append('paint finished'))
        menu.configure(fg_color=('#ddeeff', '#223344'))
        self.assertEqual(idle, [])
        menu._canvas.update_idletasks()
        self.assertEqual(idle, ['paint finished'])
        menu.set('Hatalı')
        self.assertEqual(menu.get(), 'Hatalı')

    def test_scrollable_frame_thumb_paints_without_reentering_layout(self):
        frame = self.app.settings_body
        self.assertIsInstance(frame, AppScrollableFrame)
        idle = []
        self.app.after_idle(lambda: idle.append('layout'))
        frame._scrollbar.set(.2, .7)
        self.assertEqual(frame._scrollbar.get(), (.2, .7))
        self.assertEqual(idle, [])
        self.app.update_idletasks()
        self.assertEqual(idle, ['layout'])

    def test_unchanged_scroll_fractions_skip_redraw_but_changed_values_paint(self):
        bar = AppScrollbar(self.app.workspace)
        self.addCleanup(bar.destroy)
        with patch.object(bar, '_draw', wraps=bar._draw) as draw:
            bar.set(.1, .8)
            bar.set('0.1', '0.8')
            self.assertEqual(draw.call_count, 1)
            bar.set(.2, .9)
            self.assertEqual(draw.call_count, 2)
        self.assertEqual(bar.get(), (.2, .9))

    def test_child_resize_skips_root_size_queries_but_window_resize_reaches_ctk(self):
        with patch.object(self.app, '_reverse_window_scaling', wraps=self.app._reverse_window_scaling) as reverse:
            self.app.sidebar.event_generate('<Configure>', width=208, height=740)
            reverse.assert_not_called()
            self.app.event_generate('<Configure>')
            self.assertGreater(reverse.call_count, 0)
