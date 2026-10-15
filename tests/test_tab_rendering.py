"""Tab replacements paint before the previous view is unmapped."""

from unittest.mock import patch

import customtkinter as ctk

from support.gui import GuiTestCase
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB


class TabRenderingTests(GuiTestCase):
    def assert_selected_result(self, name):
        tabs = self.app.result_tabs
        self.assertEqual(tabs.get(), name)
        self.assertTrue(tabs.tab(name).winfo_viewable())
        for other in ('Dosyalar', 'Günlük'):
            if other != name:
                self.assertFalse(tabs.tab(other).winfo_manager())

    def test_result_tab_paints_replacement_before_unmapping_previous(self):
        tabs = self.app.result_tabs
        previous, target = tabs.tab('Dosyalar'), tabs.tab('Günlük')
        observations = []
        forget = previous.grid_forget

        def forget_previous():
            observations.append((previous.winfo_viewable(), target.winfo_viewable()))
            forget()

        with patch.object(previous, 'grid_forget', side_effect=forget_previous):
            tabs.set('Günlük')
        self.assertEqual(observations, [(True, True)])
        self.assert_selected_result('Günlük')

    def test_rapid_programmatic_and_mouse_tab_changes_keep_latest_visible(self):
        tabs = self.app.result_tabs
        clicked = []
        tabs.configure(command=lambda: clicked.append(tabs.get()))
        for _ in range(3):
            tabs.set('Günlük')
            tabs._segmented_button._buttons_dict['Dosyalar'].invoke()
        self.settle(.15)
        self.assertEqual(clicked, ['Dosyalar'] * 3)
        self.assert_selected_result('Dosyalar')
        with patch.object(tabs, '_set_grid_current_tab') as layout:
            tabs.set('Dosyalar')
        layout.assert_not_called()

    def test_selected_result_survives_theme_and_dpi_changes(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for name, theme, scale in [('Günlük', 'Koyu', 1.25), ('Dosyalar', 'Açık', 1)]:
            with self.subTest(name=name, theme=theme, scale=scale):
                self.app.result_tabs.set(name)
                self.app._change_theme(theme)
                ctk.set_widget_scaling(scale)
                self.settle(.15)
                self.assert_selected_result(name)

    def test_k_views_paint_replacement_before_unmapping_previous(self):
        self.app._switch_mode('k_factor')
        self.app.update()
        widgets = self.app.k_widgets
        transitions = [
            (AUTOMATIC_TAB, widgets['manual_panel'], widgets['automatic_panel']),
            (RESULTS_TAB, self.app.form_panel, self.app.result_tabs.master),
            (MANUAL_TAB, self.app.result_tabs.master, widgets['manual_panel']),
        ]
        for selection, previous, target in transitions:
            with self.subTest(selection=selection):
                observations = []
                remove = previous.grid_remove

                def remove_previous():
                    observations.append((previous.winfo_viewable(), target.winfo_viewable()))
                    remove()

                with patch.object(previous, 'grid_remove', side_effect=remove_previous):
                    self.app._select_k_view(selection)
                self.assertEqual(observations, [(True, True)])
                self.assertTrue(target.winfo_viewable())
                self.assertFalse(previous.winfo_manager())
