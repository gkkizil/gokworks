"""Kalınlık eşleştirerek kullanıcı K/R değerlerini aynen atama."""

import csv
import unittest
from copy import deepcopy
from queue import Queue
from unittest.mock import patch

from support.fixtures import KApplyTestCase
from support.gui import GuiTestCase
from support.solidworks import (
    FakeAssembly,
    FakeComponent,
    FakeMultiPartApp,
    SheetPart,
    solidworks_session,
)

from k_factor import apply as ap
from k_factor.rules import ManualAssignment, ThicknessMismatch, calculate
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB
from pdf.settings import load_settings


class ManualRulesTests(unittest.TestCase):
    def test_user_values_and_decimal_comma_are_preserved(self):
        result=calculate('2,0',ManualAssignment('2','0,274','2'))
        self.assertEqual((result.thickness_mm,result.k_factor,result.radius_mm),(2,.274,2))
        self.assertIsNone(result.ba_mm)

    def test_unit_roundoff_matches_but_other_thicknesses_do_not(self):
        assignment=ManualAssignment(2,.274,2)
        self.assertEqual(calculate(2+1e-10,assignment).k_factor,.274)
        for actual in (1,1.99,2.01,3,2+2e-6):
            with self.subTest(actual=actual),self.assertRaises(ThicknessMismatch):
                calculate(actual,assignment)

    def test_manual_assignment_is_independent_of_tool_catalogue(self):
        # Large/custom radii are not passed through the air-bending V model.
        result=calculate(25,ManualAssignment(25,.274123456,80))
        self.assertEqual(result.k_factor,.274123456)
        self.assertEqual(result.radius_mm,80)

    def test_invalid_values_are_rejected_before_any_worker(self):
        for values in ((0,.274,2),(2,-.1,2),(2,1.001,2),(2,.274,0),
                       (2,'nan',2),(2,.274,'inf'),(True,.274,2)):
            with self.subTest(values=values),self.assertRaises(ValueError):
                ManualAssignment(*values).validate()
        for k in (0,1):self.assertEqual(calculate(2,ManualAssignment(2,k,2)).k_factor,k)


class ManualApplyTests(KApplyTestCase):
    def manual(self,**kwargs):
        return ap.process_part(self.app,self.model.path,'default',ManualAssignment(2,.274,2),**kwargs)

    def test_exact_values_and_metres_written_without_changing_thickness(self):
        self.model.states['Default']['radius']=.001
        status,detail,_=self.manual()
        self.assertEqual(status,'success',detail)
        state=self.model.states['Default']
        self.assertEqual((state['k'],state['radius'],state['thickness'],state['type']),(.274,.002,.002,2))
        self.assertEqual(self.model.save_count,0)
        self.assertIn('Manuel atama',detail)

    def test_parameter_assignment_does_not_query_dxf_export_members(self):
        def unrelated_export(_):
            raise AssertionError('K/R must not access the DXF export interface')
        with patch.object(type(self.model), 'ExportToDWG2', property(unrelated_export)):
            status, detail, _ = self.manual()
        self.assertEqual(status, 'success', detail)

    def test_mismatched_thickness_skips_even_gauge_override_without_save(self):
        self.model.states['Default']['thickness']=.003
        self.model.gauge=self.model.material_link=True
        before=deepcopy(self.model.states)
        status,detail,result=self.manual(save=True)
        self.assertEqual(status,'skipped',detail)
        self.assertIn('eşleşmedi',detail)
        self.assertIsNone(result)
        self.assertEqual(self.model.states,before)
        self.assertEqual(self.model.feature.modify_count,0)
        self.assertEqual(self.model.save_count,0)

    def test_preview_does_not_modify(self):
        before=deepcopy(self.model.states)
        status,detail,result=self.manual(preview=True,save=True)
        self.assertEqual(status,'success',detail)
        self.assertEqual(result.k_factor,.274)
        self.assertEqual(self.model.states,before)
        self.assertEqual(self.model.feature.modify_count,0)
        self.assertEqual(self.model.save_count,0)

    def test_manual_failure_uses_existing_verified_rollback(self):
        self.model.readback_fail=True
        before=deepcopy(self.model.states)
        status,detail,_=self.manual(save=True)
        self.assertEqual(status,'error')
        self.assertIn('geri yüklendi',detail)
        self.assertEqual(self.model.states,before)
        self.assertEqual(self.model.save_count,0)

    def test_only_matching_referenced_configuration_is_updated(self):
        self.model.states['Other']=deepcopy(self.model.states['Default'])
        self.model.states['Other']['thickness']=.003
        before=deepcopy(self.model.states['Other'])
        self.model.ShowConfiguration2('Other')
        status,detail,_=self.manual()
        self.assertEqual(status,'success',detail)
        self.assertEqual(self.model.states['Default']['k'],.274)
        self.assertEqual(self.model.states['Other'],before)
        self.assertEqual(self.model.config,'Other')

    def test_nested_batch_updates_and_saves_matching_parts_once(self):
        thick=SheetPart('/work/thick.sldprt')
        thick.states['Default']['thickness']=.003
        before=deepcopy(thick.states)
        sub=FakeComponent('/work/sub.sldasm',children=(FakeComponent(self.model.path),)*2)
        self.assembly.root.children=(sub,sub,FakeComponent(thick.path))
        app=FakeMultiPartApp((self.model,thick),self.assembly)
        events=Queue()
        with patch.object(ap,'connect_to_solidworks',return_value=app):
            ap.update_assembly(ManualAssignment(2,.274,2),events,save=True)
        results=[v for k,v in events.queue if k=='result']
        self.assertEqual([r['status'] for r in results],['success','skipped'])
        self.assertEqual(results[0]['quantity'],4)
        self.assertEqual(self.model.save_count,1)
        self.assertEqual(thick.save_count,0)
        self.assertEqual(thick.states,before)
        self.assertEqual(list(events.queue)[-1][1]['skipped'],1)
        self.assertIs(app.ActiveDoc,self.assembly)


class ManualGuiTests(GuiTestCase):
    def test_calibration_fields_follow_method_without_losing_measurements(self):
        self.app._switch_mode('k_factor')
        self.app._select_k_view(AUTOMATIC_TAB)
        panel = self.app.k_widgets['calibration_panel']
        self.app.update()
        self.assertFalse(panel.winfo_viewable())
        self.app.k_state['method'].set('BA ölçümü')
        self.app.k_state['radius'].set('2')
        self.app.k_state['ba'].set('4,08407044966673')
        self.app.update()
        self.assertTrue(panel.winfo_viewable())
        self.assertAlmostEqual(self.app._preview_k_calculation().k_factor, .3)
        self.app.k_state['method'].set('Tablo')
        self.app.update()
        self.assertFalse(panel.winfo_viewable())
        self.assertAlmostEqual(self.app._preview_k_calculation().k_factor, .38)
        self.app._switch_mode('pdf')
        self.app._switch_mode('k_factor')
        self.app.update()
        self.assertFalse(panel.winfo_viewable())
        self.app.k_state['method'].set('BA ölçümü')
        self.app.update()
        self.assertTrue(panel.winfo_viewable())
        self.assertEqual(self.app.k_state['ba'].get(), '4,08407044966673')
        self.assertAlmostEqual(self.app._preview_k_calculation().k_factor, .3)

    def select_manual(self):
        self.app._switch_mode('k_factor')
        self.app.k_widgets['assignment_tabs']._buttons_dict[MANUAL_TAB].invoke()
        for key,value in (('manual_thickness','2'),('manual_k','0,274'),('manual_r','2')):
            self.app.k_state[key].set(value)
        self.app.update()

    def test_default_manual_and_calculated_values_cannot_start_assignment(self):
        self.app._switch_mode('k_factor')
        self.assertEqual(self.app.k_state['assignment_mode'].get(), MANUAL_TAB)
        self.assertEqual(self.app.k_state['manual_k'].get(), '')
        self.assertEqual(self.app.k_state['manual_r'].get(), '')
        self.app._select_k_view(AUTOMATIC_TAB)
        self.assertIsNotNone(self.app._preview_k_calculation())
        with patch('k_factor.window.update_assembly') as worker:
            self.app.start_button.invoke()
            self.app.scan_button.invoke()
        worker.assert_not_called()
        self.assertEqual(self.app.k_state['assignment_mode'].get(), MANUAL_TAB)
        self.assertFalse(self.app.busy)

    def test_apply_from_calculator_uses_only_entered_values_without_table_lookup(self):
        self.select_manual()
        self.app.k_state['manual_k'].set('0,274123456')
        self.app.k_state['manual_r'].set('2,3456789')
        self.app._select_k_view(AUTOMATIC_TAB)
        self.assertNotEqual(self.app._preview_k_calculation().k_factor, .274123456)
        model = SheetPart()
        assembly = FakeAssembly('/work/main.sldasm', (FakeComponent(model.path),))
        with solidworks_session(ap, FakeMultiPartApp((model,), assembly), 'kr'), \
                patch('k_factor.rules.recommended_k', side_effect=AssertionError('No table for assignment')):
            self.app.start_button.invoke()
            self.wait_idle()
        self.assertEqual(self.app.results[0]['status'], 'success', self.app.results[0]['detail'])
        self.assertEqual(model.states['Default']['k'], .274123456)
        self.assertAlmostEqual(model.states['Default']['radius'], .0023456789, places=14)
        self.assertEqual(model.states['Default']['thickness'], .002)
        self.assertEqual(model.states['Default']['type'], 2)
        self.assertIn('Sac-Levha', self.app.log_box.get('1.0', 'end'))

    def test_tabs_keep_independent_values_and_ignore_invalid_automatic_fields(self):
        self.select_manual()
        self.app.k_state['punch'].set('nan')
        result=self.app._preview_k_calculation()
        self.assertEqual(result.k_factor,.274)
        self.assertIn('yalnız girilen kalınlıklardaki',self.app.k_calculation_label.cget('text'))
        self.app.k_widgets['assignment_tabs']._buttons_dict[AUTOMATIC_TAB].invoke()
        self.assertIsNone(self.app._preview_k_calculation())
        self.app.k_widgets['assignment_tabs']._buttons_dict[MANUAL_TAB].invoke()
        self.assertEqual(self.app._preview_k_calculation().radius_mm,2)
        self.app._switch_mode('pdf');self.app._switch_mode('k_factor')
        self.assertEqual(self.app.k_state['assignment_mode'].get(),MANUAL_TAB)
        self.assertEqual(self.app.k_state['manual_k'].get(),'0,274')

    def test_invalid_manual_inputs_block_scan_and_apply(self):
        self.select_manual()
        for key,value in (('manual_k','1.01'),('manual_k',''),('manual_r','0'),('manual_thickness','nan')):
            with self.subTest(key=key,value=value):
                self.app.k_state['manual_k'].set('.274');self.app.k_state['manual_r'].set('2')
                self.app.k_state['manual_thickness'].set('2');self.app.k_state[key].set(value)
                self.app._select_k_view('Montaj sonuçları')
                with patch('k_factor.window.update_assembly') as worker:
                    self.app.scan_button.invoke();self.app.start_button.invoke()
                worker.assert_not_called();self.assertFalse(self.app.busy)
                self.app.update()
                self.assertTrue(self.app.form_panel.winfo_viewable())
                self.assertIn('K/R başlatılmadı', self.app.status_label.cget('text'))

    def test_failed_assignment_exposes_complete_reason_and_copies_log(self):
        self.select_manual()
        model = SheetPart()
        model.access_fail = True
        assembly = FakeAssembly('/work/main.sldasm', [FakeComponent(model.path)])
        with solidworks_session(ap, FakeMultiPartApp((model,), assembly), 'kr'):
            self.app.start_button.invoke()
            self.wait_idle()
        self.assertEqual(self.app.results[0]['status'], 'error')
        self.assertEqual(model.feature.modify_count, 0)
        self.assertEqual(self.app.result_tabs.get(), 'Günlük')
        self.assertTrue(self.app.k_widgets['copy_log'].winfo_viewable())
        self.app.k_widgets['copy_log'].invoke()
        log = self.app.clipboard_get()
        self.assertIn('AccessSelections', log)
        self.assertIn('sheet.sldprt', log)
        self.assertIn('K=0.274', log)
        # Return to the entered values directly from the results view.
        self.app.open_button.invoke()
        self.app.update()
        self.assertTrue(self.app.form_panel.winfo_viewable())

    def test_real_preview_apply_and_csv_report_from_gui(self):
        self.select_manual()
        model=SheetPart()
        thick=SheetPart('/work/thick.sldprt');thick.states['Default']['thickness']=.003
        assembly=FakeAssembly('/work/main.sldasm',(FakeComponent(model.path),FakeComponent(thick.path)))
        app=FakeMultiPartApp((model,thick),assembly)
        with solidworks_session(ap, app, 'kr'):
            self.app.scan_button.invoke();self.wait_idle()
            self.assertEqual(model.feature.modify_count,0)
            self.assertTrue(self.app.results[0]['preview'])
            preview_report=self.root/'manuel-kontrol.csv'
            with patch('pdf.window.filedialog.asksaveasfilename',return_value=str(preview_report)):
                self.app.report_button.invoke()
            with preview_report.open(encoding='utf-8-sig') as stream:
                preview_rows=list(csv.reader(stream,delimiter=';'))
            self.assertEqual(preview_rows[1][2],'Uygulamaya hazır')
            self.assertIn('Uygulamaya hazır',self.app.log_box.get('1.0','end'))
            self.app.table.selection_set('file_0')
            self.app._show_detail()
            detail=next(widget for widget in self.app.detail_window.winfo_children()
                        if hasattr(widget,'get') and widget.__class__.__name__=='CTkTextbox')
            self.assertIn('Uygulamaya hazır',detail.get('1.0','end'))
            self.app._close_detail()
            self.app.start_button.invoke();self.wait_idle()
        self.assertEqual([r['status'] for r in self.app.results],['success','skipped'])
        self.assertEqual(model.states['Default']['k'],.274)
        self.assertEqual(model.states['Default']['radius'],.002)
        self.assertEqual(thick.states['Default']['k'],.4)
        self.assertEqual(self.app.stat_values['skipped'].cget('text'),'1')
        report=self.root/'manuel.csv'
        with patch('pdf.window.filedialog.asksaveasfilename',return_value=str(report)):
            self.app.report_button.invoke()
        with report.open(encoding='utf-8-sig') as stream:rows=list(csv.reader(stream,delimiter=';'))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1][2],'Uygulandı')
        self.assertIn('K=0.274',rows[1][3])

    def test_manual_preferences_reload_and_save_choice_starts_off(self):
        self.select_manual();self.app.k_state['save'].set(True)
        self.assertNotIn('all_bends', self.app.k_widgets)
        self.assertFalse(self.app._k_recipe()[1].all_bends)
        self.app._on_close()
        self.open_app()
        self.app._switch_mode('k_factor');self.app.update()
        self.assertEqual(self.app.k_state['assignment_mode'].get(),MANUAL_TAB)
        self.assertEqual(self.app.k_state['manual_k'].get(),'0,274')
        self.assertFalse(self.app.k_state['save'].get())
        self.assertFalse(self.app._k_recipe()[1].all_bends)
        self.assertEqual(load_settings(self.settings)['kr_manual_r'],'2')

    def test_manual_gui_preserves_custom_bends_after_preview_and_assignment(self):
        from test_power_sm_k_radius import BendFeature
        self.select_manual()
        model = SheetPart()
        bend = BendFeature(model)
        model.feature.child = bend
        assembly = FakeAssembly('/work/main.sldasm', (FakeComponent(model.path),))
        app = FakeMultiPartApp((model,), assembly)
        before = deepcopy(bend.states)
        with solidworks_session(ap, app, 'kr'):
            self.app.scan_button.invoke(); self.wait_idle()
            self.assertEqual(self.app.results[0]['status'], 'success', self.app.results[0]['detail'])
            self.assertEqual(bend.states, before)
            self.assertEqual(model.feature.modify_count, 0)
            self.app.start_button.invoke(); self.wait_idle()
        self.assertEqual(self.app.results[0]['status'], 'success', self.app.results[0]['detail'])
        self.assertEqual(bend.states, before)
        self.assertEqual(model.states['Default']['k'], .274)
        self.assertEqual(model.save_count, 0)
        self.assertIs(app.ActiveDoc, assembly)
        self.assertIn('özel alt büküm ayarları korundu', self.app.results[0]['detail'])

    def test_manual_fields_scroll_into_view_and_actions_remain_visible(self):
        self.select_manual()
        for size in ('1000x690','1240x860'):
            self.app.geometry(size)
            for theme in ('Açık','Koyu'):
                with self.subTest(size=size,theme=theme):
                    self.app._change_theme(theme)
                    self.settle(.3)
                    canvas=self.app.settings_body._parent_canvas
                    field=self.app.k_widgets['manual_thickness']
                    offset=field.master.winfo_rooty()-self.app.settings_body.winfo_rooty()
                    canvas.yview_moveto(offset/self.app.settings_body.winfo_height())
                    self.app.update()
                    for widget in (self.app.k_widgets['manual_thickness'],self.app.k_widgets['manual_k'],
                                   self.app.k_widgets['manual_r'],self.app.start_button,self.app.scan_button):
                        self.assert_inside(widget, mapped=True)
                        if widget in (self.app.k_widgets['manual_thickness'],self.app.k_widgets['manual_k'],self.app.k_widgets['manual_r']):
                            self.assertGreaterEqual(widget.winfo_rooty(),canvas.winfo_rooty())
                            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                                 canvas.winfo_rooty()+canvas.winfo_height())
                    self.app._select_k_view(RESULTS_TAB)
                    self.settle(.1)
                    self.assertTrue(self.app.table.winfo_viewable())
                    self.assertGreater(self.app.table.winfo_height(),80)
                    self.app._select_k_view(MANUAL_TAB)


if __name__=='__main__':unittest.main()
