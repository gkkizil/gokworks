"""Menus preserve data while skipping unchanged Tk layouts and drawings."""

import time
import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase

from gui.theme import ACCENT, ACCENT_BG, SUCCESS
from iso_fits import window as iso_view
from iso_fits.rules import PRESETS
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB


class MenuRenderingTests(GuiTestCase):
    settle_seconds = .15

    def preload(self):
        if self.app._preload_id is not None:
            self.app.after_cancel(self.app._preload_id)
        self.app._last_ui_activity = time.monotonic()-2
        self.app._preload_page()

    def test_queued_clicks_build_only_last_page_and_keep_form_values(self):
        self.app.source_folder.set('/saved/source')
        with patch.object(self.app, '_build_window', wraps=self.app._build_window) as build:
            for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'bom', 'bolt'):
                self.app.nav_buttons[mode].invoke()
            self.app.update()
        self.assertEqual(build.call_count, 1)
        self.assertEqual(set(self.app._pages), {'pdf', 'bolt'})
        self.assertEqual(self.app.mode, 'bolt')
        self.assertTrue(self.app.workspace.winfo_viewable())
        self.app._switch_mode('pdf')
        self.assertEqual(self.app.source_folder.get(), '/saved/source')

    def test_current_page_or_direct_navigation_supersedes_queued_click(self):
        self.app.nav_buttons['bom'].invoke()
        self.app.nav_buttons['pdf'].invoke()
        self.app.update()
        self.assertEqual(set(self.app._pages), {'pdf'})
        self.app.nav_buttons['bom'].invoke()
        self.app._switch_mode('bolt')
        self.app.update()
        self.assertEqual(self.app.mode, 'bolt')
        self.assertNotIn('bom', self.app._pages)

    def test_queued_navigation_is_discarded_if_worker_starts_or_app_closes(self):
        self.app.nav_buttons['bom'].invoke()
        self.app.busy = True
        try:
            self.app.update()
            self.assertEqual(self.app.mode, 'pdf')
            self.assertEqual(set(self.app._pages), {'pdf'})
        finally:
            self.app.busy = False
        self.app.nav_buttons['bolt'].invoke()
        pending = self.app._navigation_id
        self.app._on_close()
        self.assertNotIn(pending, self.app.tk.splitlist(self.app.tk.call('after', 'info')))

    def test_preloading_never_maps_partial_page(self):
        mapped = []
        shell = self.app._workspace_shell

        def capture_shell():
            workspace = shell()
            tk.Misc.bind(workspace, '<Map>', lambda event: mapped.append(event.widget)
                         if event.widget is workspace else None, add='+')
            return workspace

        with patch.object(self.app, '_workspace_shell', side_effect=capture_shell):
            self.preload()
        self.app.update()
        self.assertEqual(mapped, [])
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertEqual(mapped, [self.app.workspace])

    def test_first_open_keeps_previous_page_visible_until_ready_and_recovers_on_error(self):
        active = self.app.workspace
        self.app.source_folder.set('/saved/source')
        build = self.app._build_window
        partial = []

        def broken_build():
            build()
            self.app.update_idletasks()
            self.assertTrue(active.winfo_viewable())
            self.assertFalse(self.app.workspace.winfo_viewable())
            partial.append(self.app.workspace)
            raise RuntimeError('construction failed')

        with patch.object(self.app, '_build_window', side_effect=broken_build):
            with self.assertRaisesRegex(RuntimeError, 'construction failed'):
                self.app._switch_mode('bom')
        self.wait_layout()
        self.assertIs(self.app.workspace, active)
        self.assertEqual(self.app.mode, 'pdf')
        self.assertEqual(self.app.source_folder.get(), '/saved/source')
        self.assertFalse(partial[0].winfo_exists())
        self.assertNotIn('bom', self.app._pages)
        self.app._switch_mode('bom')
        self.wait_layout()
        self.assertFalse(active.winfo_viewable())
        self.assertTrue(self.app.workspace.winfo_viewable())

    def test_preloading_keeps_active_page_data_and_settings_unchanged(self):
        workspace = self.app.workspace
        source = str(self.root/'drawing.slddrw')
        self.app.source_folder.set(str(self.root))
        self.app._fill_files([source])
        self.app._update_row(source, 'success', 'ready')
        with patch('pdf.window.save_settings') as writer:
            for _ in range(6):
                self.preload()
                self.app.update()
                self.assertEqual(self.app.mode, 'pdf')
                self.assertIs(self.app.workspace, workspace)
                self.assertTrue(workspace.winfo_viewable())
            writer.assert_not_called()
        self.assertEqual(set(self.app._pages),
                         {'pdf', 'dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'bom', 'bolt'})
        self.assertEqual(self.app.source_folder.get(), str(self.root))
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Başarılı')
        for mode, page in self.app._pages.items():
            self.assertEqual(bool(page['workspace'].winfo_viewable()), mode == 'pdf')
        with patch.object(self.app, '_build_window') as build:
            for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'bom', 'bolt', 'pdf'):
                self.app._switch_mode(mode)
                self.app.update()
        build.assert_not_called()

    def test_failed_preload_removes_partial_page_and_restores_active_workspace(self):
        active = self.app.workspace
        partial = []
        def broken_build():
            self.app.workspace = ctk.CTkFrame(self.app)
            self.app.workspace.grid(row=0, column=1)
            partial.append(self.app.workspace)
            raise RuntimeError('construction failed')
        with patch.object(self.app, '_build_window', side_effect=broken_build):
            with self.assertRaisesRegex(RuntimeError, 'construction failed'):
                self.preload()
        self.app.update()
        self.assertEqual(self.app.mode, 'pdf')
        self.assertIs(self.app.workspace, active)
        self.assertTrue(active.winfo_viewable())
        self.assertFalse(partial[0].winfo_exists())
        self.assertIsNone(self.app._preload_id)

    def test_preloading_waits_during_worker_and_recent_input(self):
        self.app.busy = True
        self.preload()
        self.assertEqual(set(self.app._pages), {'pdf'})
        self.app.busy = False
        self.app.after_cancel(self.app._preload_id)
        self.app._note_ui_activity()
        self.app._preload_page()
        self.assertEqual(set(self.app._pages), {'pdf'})
        self.assertIsNotNone(self.app._preload_id)

    def test_new_pages_reuse_table_styles_and_theme_and_scale_still_refresh_them(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        original = self.app.table
        real_theme = ttk.Style.theme_use
        with patch.object(original, 'tag_configure', wraps=original.tag_configure) as tags, \
                patch.object(ttk.Style, 'theme_use', autospec=True, side_effect=real_theme) as theme:
            for _ in range(6):
                self.preload()
            tags.assert_not_called()
            self.assertTrue(all(len(call.args) == 1 for call in theme.call_args_list))
        self.app._switch_mode('bom')
        self.app._change_theme('Koyu')
        self.settle()
        self.assertEqual(str(original.tag_configure('success', 'foreground')), SUCCESS[1])
        self.assertEqual(str(self.app.bom_widgets['tree'].tag_configure('assembly', 'foreground')), ACCENT[1])
        ctk.set_widget_scaling(1.25)
        self.settle()
        style = ttk.Style(self.app)
        self.assertEqual(int(style.lookup('Gok.Treeview', 'rowheight')), 50)
        self.assertEqual(int(style.lookup('Bom.Treeview', 'rowheight')), round(42*1.25))

    def test_preloaded_pages_stay_hidden_after_dpi_changes(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for _ in range(6):
            self.preload()
        for active, scale in (('pdf', 1.25), ('iso_fits', 1.5)):
            self.app._switch_mode(active)
            ctk.set_widget_scaling(scale)
            self.settle()
            for mode, page in self.app._pages.items():
                self.assertEqual(page['workspace'].winfo_manager(), 'grid' if mode == active else '')

    def test_preloading_preserves_active_iso_manual_state(self):
        self.app._switch_mode('iso_fits')
        self.app._fill_compatibility_example()
        self.settle()
        canvas, fit = self.app.iso_widgets['canvas'], self.app.iso_result
        original = canvas.find_all()
        self.preload()
        self.settle()
        self.assertEqual(self.app.mode, 'iso_fits')
        self.assertIs(self.app.iso_widgets['canvas'], canvas)
        self.assertEqual(self.app.iso_result, fit)
        self.assertEqual(self.app.iso_state['hole_lower'].get(), '-0,05')
        self.assertEqual(canvas.find_all(), original)

    def test_conditional_forms_and_filtered_choices_stay_hidden_after_dpi_changes(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        self.app._switch_mode('iso_fits')
        self.app.iso_search.set('H7/g6')
        for method, scale in [('ISO seçimi', 1.25), ('Manuel kontrol', 1.5), ('ISO seçimi', 1)]:
            with self.subTest(method=method, scale=scale):
                self.app.iso_state['method'].set(method)
                self.app.iso_state['view'].set('Tolerans bölgeleri')
                expected_fit = self.app.iso_result
                ctk.set_widget_scaling(scale)
                self.settle()
                manual = method == 'Manuel kontrol'
                widgets = self.app.iso_widgets
                for key in ('manual_inputs', 'assessment', 'comparison'):
                    self.assertEqual(bool(widgets[key].grid_info()), manual)
                for widget in widgets['iso_inputs']:
                    self.assertEqual(bool(widget.grid_info()), not manual)
                self.assertFalse(widgets['section_help'].grid_info())
                visible = [key for key, widget in widgets['preset_buttons'].items() if widget.grid_info()]
                self.assertEqual(visible, ['H7 / g6'])
                self.assertEqual(self.app.iso_result, expected_fit)

        self.app._switch_mode('geometric_tolerances')
        self.app._select_gdt('position')
        self.app.gdt_search.set('SİLİNDİR')
        ctk.set_widget_scaling(1.25)
        self.settle()
        self.assertFalse(self.app.gdt_widgets['size_rule'].grid_info())
        visible = [key for key, widget in self.app.gdt_widgets['choices'].items() if widget.grid_info()]
        self.assertEqual(visible, ['cylindricity'])

        self.app._switch_mode('k_factor')
        for view, scale in [(MANUAL_TAB, 1.5), (RESULTS_TAB, 1), (AUTOMATIC_TAB, 1.25)]:
            with self.subTest(view=view, scale=scale):
                self.app._select_k_view(view)
                ctk.set_widget_scaling(scale)
                self.settle()
                results = view == RESULTS_TAB
                self.assertEqual(bool(self.app.form_panel.grid_info()), not results)
                self.assertEqual(bool(self.app.result_tabs.master.grid_info()), results)
                if not results:
                    self.assertEqual(bool(self.app.k_widgets['manual_panel'].grid_info()), view == MANUAL_TAB)
                    self.assertEqual(bool(self.app.k_widgets['automatic_panel'].grid_info()), view == AUTOMATIC_TAB)

    def test_iso_sample_and_view_changes_only_redraw_diagram(self):
        self.app._switch_mode('iso_fits')
        self.settle()
        fit = self.app.iso_result
        with patch.object(iso_view, 'calculate', wraps=iso_view.calculate) as calculate, \
                patch.object(self.app, '_filter_iso_presets', wraps=self.app._filter_iso_presets) as filter_list:
            self.app.iso_state['sample'].set('En az boşluk')
            self.app.iso_state['view'].set('Tolerans bölgeleri')
            self.app.update()
        calculate.assert_not_called()
        filter_list.assert_not_called()
        self.assertIs(self.app.iso_result, fit)
        text = ' '.join(self.app.iso_widgets['canvas'].itemcget(i, 'text')
                        for i in self.app.iso_widgets['canvas'].find_all()
                        if self.app.iso_widgets['canvas'].type(i) == 'text')
        self.assertIn('nominal çap', text)

    def test_iso_filter_reuses_layout_and_updates_selected_pair(self):
        self.app._switch_mode('iso_fits')
        self.settle()
        original_preset = next(p for p in PRESETS if (p.hole, p.shaft) == ('H8', 'f7'))
        selected_preset = next(p for p in PRESETS if (p.hole, p.shaft) == ('H7', 'k6'))
        original = self.app.iso_widgets['preset_buttons'][original_preset.code]
        selected = self.app.iso_widgets['preset_buttons'][selected_preset.code]
        with patch.object(original, 'grid_remove', wraps=original.grid_remove) as remove, \
                patch.object(iso_view, 'calculate', wraps=iso_view.calculate) as calculate:
            self.app._select_iso_preset(selected_preset)
            self.app._filter_iso_presets()
            self.app.update()
        remove.assert_not_called()
        self.assertEqual(calculate.call_count, 1)
        self.assertEqual(original.cget('fg_color'), 'transparent')
        self.assertEqual(selected.cget('fg_color'), ACCENT_BG)
        with patch.object(iso_view, 'calculate', wraps=iso_view.calculate) as calculate:
            self.app.iso_state['diameter'].set('60')
        self.assertEqual(calculate.call_count, 1+len(PRESETS))

    def test_diagram_cache_invalidates_on_data_theme_size_and_invalid_input(self):
        for mode in ('iso_fits', 'geometric_tolerances'):
            self.app._switch_mode(mode)
            self.settle()
            widgets = self.app.iso_widgets if mode == 'iso_fits' else self.app.gdt_widgets
            canvas = widgets['canvas']
            draw = self.app._draw_iso_diagram if mode == 'iso_fits' else self.app._draw_gdt_diagram
            items = canvas.find_all()
            for _ in range(5):
                draw()
            self.assertEqual(canvas.find_all(), items)
            state = self.app.iso_state if mode == 'iso_fits' else self.app.gdt_state
            key = 'diameter' if mode == 'iso_fits' else 'tolerance'
            state[key].set('60' if mode == 'iso_fits' else '0,2')
            self.assertNotEqual(canvas.find_all(), items)
            items = canvas.find_all()
            self.app._change_theme('Koyu' if self.app.theme_mode.get() == 'Açık' else 'Açık')
            self.settle()
            self.assertNotEqual(canvas.find_all(), items)
            items = canvas.find_all()
            self.app.geometry('1400x900')
            self.settle()
            # Use a different width in each iteration.
            self.app.geometry('1366x768')
            self.settle()
            self.assertNotEqual(canvas.find_all(), items)
            state[key].set('bad input')
            text = ' '.join(canvas.itemcget(i, 'text') for i in canvas.find_all()
                            if canvas.type(i) == 'text')
            self.assertIn('Geçerli', text)

    def test_gdt_numeric_change_does_not_rebuild_catalog_or_static_heading(self):
        self.app._switch_mode('geometric_tolerances')
        self.settle()
        button = self.app.gdt_widgets['choices']['cylindricity']
        heading = self.app.gdt_widgets['title']
        with patch.object(button, 'grid_remove', wraps=button.grid_remove) as remove, \
                patch.object(button, 'configure', wraps=button.configure) as paint, \
                patch.object(heading, 'configure', wraps=heading.configure) as title:
            self.app.gdt_state['tolerance'].set('0,2')
            self.app.gdt_state['measured'].set('0,15')
        remove.assert_not_called()
        paint.assert_not_called()
        title.assert_not_called()
        self.assertTrue(self.app.gdt_result.accepted)
        self.app._select_gdt('position')
        self.assertEqual(button.cget('fg_color'), 'transparent')
        self.assertEqual(self.app.gdt_widgets['choices']['position'].cget('fg_color'), ACCENT_BG)


if __name__ == '__main__':
    unittest.main()
