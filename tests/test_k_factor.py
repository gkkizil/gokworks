"""K/R: bağımsız sayısal örnekler, COM hata/geri alma ve gerçek Tk akışları."""

import unittest
from copy import deepcopy
from dataclasses import replace
from queue import Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import customtkinter as ctk
from support.fixtures import KApplyTestCase
from support.gui import GuiTestCase
from support.solidworks import (
    FakeApp,
    FakeAssembly,
    FakeComponent,
    FakeFeature,
    FakeMultiPartApp,
    SheetPart,
    solidworks_session,
)

from k_factor import apply as ap
from k_factor.rules import (
    Recipe,
    ba_from_outside_dimensions,
    bend_allowance,
    bend_deduction,
    calculate,
    k_from_bend_allowance,
    number,
    recommended_k,
)
from pdf.settings import load_settings


class CalculationTests(unittest.TestCase):
    def test_independent_hand_calculation_90_degrees(self):
        # By hand: π/2 × (2 + 0.4×2) = 4.39822971502571;
        # BD = 2×(2+2)×tan(45°) − BA = 3.60177028497429.
        self.assertAlmostEqual(bend_allowance(2, 2, .4, 90), 4.39822971502571, places=12)
        self.assertAlmostEqual(bend_deduction(2, 2, .4, 90), 3.60177028497429, places=12)
        self.assertAlmostEqual(k_from_bend_allowance(2, 2, 4.39822971502571, 90), .4, places=12)

    def test_published_freecad_manual_example(self):
        # FreeCAD tools/calc-unfold.py inputs; literal independent expected BA.
        self.assertAlmostEqual(bend_allowance(2, 1.64, .38, 90), 3.76991118430775, places=12)
        self.assertAlmostEqual(k_from_bend_allowance(2, 1.64, 3.76991118430775, 90), .38, places=12)

    def test_angles_use_bend_rotation_not_inside_angle(self):
        for angle, expected in ((30, 1.46607657167524), (45, 2.19911485751286),
                                (120, 5.86430628670095)):
            with self.subTest(angle=angle):
                self.assertAlmostEqual(bend_allowance(2, 2, .4, angle), expected, places=11)

    def test_measured_outside_dimensions_and_blank_recover_ba(self):
        # A=50 B=40; independently calculated blank length 86.3982297150257.
        ba = ba_from_outside_dimensions(2, 2, 50, 40, 86.3982297150257)
        self.assertAlmostEqual(ba, 4.39822971502571, places=11)
        self.assertAlmostEqual(k_from_bend_allowance(2, 2, ba), .4, places=11)

    def test_generic_table_classes_and_boundaries(self):
        for material, expected in (('aluminium', (.33,.40,.50)),
                                   ('steel', (.38,.43,.50)), ('stainless', (.40,.45,.50))):
            for radius, index in ((0,0),(2,0),(2.00001,1),(6,1),(6.00001,2)):
                with self.subTest(material=material, radius=radius):
                    self.assertEqual(recommended_k(material, 2, radius), expected[index])

    def test_catalogue_selects_different_v_for_each_thickness(self):
        for t, expected_v in ((1,8),(1.5,12),(2,16),(3,24),(4,32),(6,50)):
            with self.subTest(t=t):
                result=calculate(t)
                self.assertEqual(result.die_opening_mm, expected_v)
                self.assertAlmostEqual(result.radius_mm, max(1,.16*expected_v))
                self.assertFalse(result.calibrated)

    def test_custom_tools_material_and_punch_dominance(self):
        result=calculate(2, Recipe(punch_radius_mm=3.7, die_opening_mm=17))
        self.assertEqual(result.radius_mm, 3.7)
        self.assertTrue(any('baskın' in s for s in result.notes))
        self.assertAlmostEqual(calculate(2, Recipe(material='stainless')).radius_mm, 3.2)

    def test_tool_angles_reject_incompatible_acute_bends(self):
        with self.assertRaisesRegex(ValueError,'daha dar'):
            calculate(2,Recipe(angle_deg=120))
        result=calculate(2,Recipe(angle_deg=120,punch_angle_deg=60,die_angle_deg=60))
        self.assertEqual(result.angle_deg,120)
        with self.assertRaises(ValueError):
            calculate(2,Recipe(measured_radius_mm=9))

    def test_measured_ba_calibration_and_table_difference(self):
        recipe=Recipe(measured_radius_mm=2, calibration_thickness_mm=2,
                      measured_ba_mm=4.39822971502571)
        result=calculate(2,recipe)
        self.assertTrue(result.calibrated)
        self.assertAlmostEqual(result.k_factor,.4,places=12)
        self.assertEqual(result.table_k,.38)
        for bad in (replace(recipe,measured_radius_mm=None), replace(recipe,calibration_thickness_mm=3)):
            with self.subTest(recipe=bad), self.assertRaises(ValueError): calculate(2,bad)

    def test_invalid_and_out_of_model_inputs_are_rejected(self):
        for bad in (True,False,'nan','inf',None,'x',0,-1):
            with self.subTest(bad=bad), self.assertRaises(ValueError): number(bad,'Mesafe')
        self.assertEqual(number('1,25','Mesafe'),1.25)
        for args in ((2,2,.4,0),(2,2,.4,180),(2,2,1.1,90),(0,2,.4,90)):
            with self.subTest(args=args), self.assertRaises(ValueError): bend_allowance(*args)
        for recipe in (Recipe(material='unknown'), Recipe(die_opening_mm=4),
                       Recipe(die_opening_mm=40), Recipe(punch_radius_mm=8),
                       Recipe(measured_radius_mm=.2)):
            with self.subTest(recipe=recipe), self.assertRaises(ValueError): calculate(2,recipe)
        with self.assertRaises(ValueError): calculate(30)
        for ba in (.1,30):
            with self.subTest(ba=ba), self.assertRaises(ValueError): k_from_bend_allowance(2,2,ba)
        with self.assertRaises(ValueError): ba_from_outside_dimensions(2,2,1,40,40)


class ApplyTests(KApplyTestCase):
    def process(self,**kwargs):
        return ap.process_part(self.app,self.model.path,'default',Recipe(),**kwargs)

    def batch(self,**kwargs):
        self.app.ActiveDoc=self.assembly
        events=Queue()
        with patch.object(ap,'connect_to_solidworks',return_value=self.app):
            ap.update_assembly(Recipe(),events,**kwargs)
        return list(events.queue)

    def test_preview_does_not_modify_or_save(self):
        before=deepcopy(self.model.states)
        status,detail,result=self.process(preview=True,save=True)
        self.assertEqual(status,'success',detail)
        self.assertEqual(self.model.states,before)
        self.assertEqual(self.model.feature.modify_count,0)
        self.assertEqual(self.model.save_count,0)
        self.assertAlmostEqual(result.radius_mm,2.56)

    def test_apply_writes_metres_and_k_type_without_saving(self):
        status,detail,_=self.process()
        self.assertEqual(status,'success',detail)
        self.assertAlmostEqual(self.model.states['Default']['radius'],.00256)
        self.assertEqual(self.model.states['Default']['k'],.43)
        self.assertEqual(self.model.states['Default']['type'],2)
        self.assertEqual(self.model.states['Default']['thickness'],.002)
        self.assertEqual(self.model.save_count,0)

    def test_explicit_save_and_existing_dirty_document_protection(self):
        self.assertEqual(self.process(save=True)[0],'success')
        self.assertEqual(self.model.save_count,1)
        self.model.dirty=True
        before=self.model.feature.modify_count
        self.assertEqual(self.process(save=True)[0],'error')
        self.assertEqual(self.model.feature.modify_count,before)

    def test_multiple_configurations_restore_active_and_preserve_other(self):
        self.model.states['Other']=deepcopy(self.model.states['Default'])
        self.model.ShowConfiguration2('Other')
        before=deepcopy(self.model.states['Other'])
        status,detail,_=self.process()
        self.assertEqual(status,'success',detail)
        self.assertEqual(self.model.config,'Other')
        self.assertEqual(self.model.states['Other'],before)
        self.assertEqual(self.model.states['Default']['k'],.43)

    def test_cross_configuration_propagation_rolls_back(self):
        self.model.states['Other']=deepcopy(self.model.states['Default'])
        self.model.propagate=True
        before=deepcopy(self.model.states)
        status,detail,_=self.process()
        self.assertEqual(status,'error')
        self.assertIn('başka konfigürasyona',detail)
        self.assertIn('geri yüklendi',detail)
        self.assertEqual(self.model.states,before)

    def test_modify_rebuild_readback_and_save_errors_restore_values(self):
        for flag in ('modify_fail','rebuild_fail','readback_fail','save_fail'):
            with self.subTest(flag=flag):
                self.model.states['Default'].update(radius=.002,k=.4)
                before=deepcopy(self.model.states)
                setattr(self.model,flag,True)
                status,detail,_=self.process(save=flag=='save_fail')
                self.assertEqual(status,'error',detail)
                self.assertEqual(self.model.states,before,detail)
                self.assertIn('geri yüklendi',detail)

    def test_selection_access_failure_does_not_change_model(self):
        self.model.access_fail=True
        before=deepcopy(self.model.states)
        self.assertEqual(self.process()[0],'error')
        self.assertEqual(self.model.states,before)

    def test_gauge_material_and_individual_bend_overrides_reject_before_write(self):
        for flag in ('gauge','material_link'):
            with self.subTest(flag=flag):
                setattr(self.model,flag,True)
                self.assertEqual(self.process()[0],'error')
                self.assertEqual(self.model.feature.modify_count,0)
                setattr(self.model,flag,False)
        child=FakeFeature('Bend','OneBend')
        child.GetDefinition=lambda:SimpleNamespace(UseDefaultBendRadius=False)
        self.model.feature.child=child
        self.assertEqual(self.process()[0],'error')
        self.assertEqual(self.model.feature.modify_count,0)

    def test_non_sheet_and_multi_body_parts(self):
        self.model.bodies[0].IsSheetMetal=lambda:False
        self.assertEqual(self.process()[0],'skipped')
        self.model.bodies=[SimpleNamespace(IsSheetMetal=lambda:True)]*2
        self.assertEqual(self.process()[0],'error')

    def test_batch_deduplicates_instances_and_restores_assembly(self):
        events=self.batch()
        results=[value for kind,value in events if kind=='result']
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['quantity'],3)
        self.assertEqual(results[0]['status'],'success',results[0]['detail'])
        self.assertEqual(events[-1][1]['succeeded'],1)
        self.assertIs(self.app.ActiveDoc,self.assembly)
        self.com.CoInitialize.assert_called_once()
        self.com.CoUninitialize.assert_called_once()

    def test_batch_nested_assembly_and_suppression(self):
        part=FakeComponent(self.model.path)
        sub=FakeComponent('/work/sub.sldasm',children=(part,part))
        suppressed=FakeComponent('/work/ignored.sldprt',state=0)
        self.assembly.root.children=(sub,sub,suppressed)
        events=self.batch(preview=True)
        results=[v for k,v in events if k=='result']
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['quantity'],4)

    def test_newly_opened_preview_closes_but_unsaved_apply_stays_open(self):
        self.app.existing=False
        def open_part(path, kind, options, configuration, errors, warnings):
            self.assertEqual((path,kind,options,configuration),
                             (self.model.path,1,1,'default'))
            return self.model
        self.app.OpenDoc6=open_part
        self.assertEqual(self.process(preview=True)[0],'success')
        self.assertEqual(len(self.app.closed),1)
        self.app.closed.clear()
        self.assertEqual(self.process()[0],'success')
        self.assertFalse(self.app.closed)

    def test_cancel_after_current_part_keeps_next_part_unchanged(self):
        other=SheetPart('/work/z-next.sldprt')
        original_get=self.app.GetOpenDocumentByName
        self.app.GetOpenDocumentByName=lambda path:other if path==other.path else original_get(path)
        self.assembly.root.children=(FakeComponent(self.model.path),FakeComponent(other.path))
        stopped=Event()
        original_modify=self.model.feature.ModifyDefinition
        def modify(*args):
            result=original_modify(*args)
            stopped.set()
            return result
        self.model.feature.ModifyDefinition=modify
        events=self.batch(stop_event=stopped)
        self.assertEqual(events[-1][1]['state'],'cancelled')
        self.assertEqual(events[-1][1]['processed'],1)
        self.assertEqual(other.feature.modify_count,0)

    def test_failed_rollback_is_explicit_and_never_saved(self):
        original=self.model.feature.ModifyDefinition
        def fail_rollback(*args):
            result=original(*args)
            self.model.access_fail=True
            return result
        self.model.feature.ModifyDefinition=fail_rollback
        self.model.readback_fail=True
        status,detail,_=self.process(save=True)
        self.assertEqual(status,'error')
        self.assertIn('GERİ ALMA HATASI',detail)
        self.assertEqual(self.model.save_count,0)

    def test_wrong_activation_and_unknown_configuration_do_not_write(self):
        self.app.activate_error=1
        self.assertEqual(self.process()[0],'error')
        self.app.activate_error=0
        status,detail,_=ap.process_part(self.app,self.model.path,'missing',Recipe())
        self.assertEqual(status,'error')
        self.assertIn('Konfigürasyon',detail)
        self.assertEqual(self.model.feature.modify_count,0)

    def test_missing_sheet_feature_and_inaccessible_suppression_fail(self):
        self.model.feature.kind='Boss'
        self.assertEqual(self.process()[0],'error')
        self.model.feature.kind='SheetMetal'
        self.model.feature.IsSuppressed2=lambda *args:None
        self.assertEqual(self.process()[0],'error')
        self.assertEqual(self.model.feature.modify_count,0)

    def test_calibration_skips_wrong_thickness_and_continues_batch(self):
        thick=SheetPart('/work/z-thick.sldprt')
        thick.states['Default']['thickness']=.003
        self.assembly.root.children=(FakeComponent(self.model.path),FakeComponent(thick.path))
        app=FakeMultiPartApp((self.model,thick),self.assembly)
        events=Queue()
        recipe=Recipe(measured_radius_mm=2,calibration_thickness_mm=2,
                      measured_ba_mm=4.39822971502571)
        with patch.object(ap,'connect_to_solidworks',return_value=app):
            ap.update_assembly(recipe,events)
        results=[v for k,v in events.queue if k=='result']
        self.assertEqual([r['status'] for r in results],['success','error'])
        self.assertEqual(thick.feature.modify_count,0)
        self.assertEqual(list(events.queue)[-1][1]['failed'],1)
        self.assertIs(app.ActiveDoc,self.assembly)

    def test_com_cleanup_error_still_sends_done(self):
        self.com.CoUninitialize.side_effect=RuntimeError('COM cleanup failed')
        events=self.batch(preview=True)
        self.assertEqual(events[-1][0],'done')
        self.assertEqual(events[-1][1]['state'],'error')
        self.assertIn('COM kapanışı',events[-1][1]['error'])

    def test_missing_platform_cancel_and_invalid_assembly_always_finish(self):
        events=Queue()
        with patch.multiple(ap,pythoncom=None,win32com=None):
            ap.update_assembly(Recipe(),events)
        self.assertEqual(list(events.queue)[-1][1]['state'],'error')
        stopped=Event();stopped.set()
        events=Queue();ap.update_assembly(Recipe(),events,stopped)
        self.assertEqual(list(events.queue)[-1][1]['state'],'cancelled')
        self.assertFalse(self.com.CoInitialize.called)
        self.app.ActiveDoc=self.model
        events=Queue()
        with patch.object(ap,'connect_to_solidworks',return_value=self.app):
            ap.update_assembly(Recipe(),events)
        self.assertEqual(list(events.queue)[-1][1]['state'],'error')
        self.com.CoUninitialize.assert_called_once()


class KGuiTests(GuiTestCase):
    def test_navigation_title_preferences_and_theme_persistence(self):
        self.app.nav_buttons['k_factor'].invoke();self.app.update()
        self.assertEqual(self.app.mode,'k_factor')
        self.assertEqual(self.app.nav_buttons['k_factor'].cget('text'),'K FAKTÖR - RADIUS')
        self.app.k_state['punch'].set('1,5')
        self.app.k_state['die'].set('17')
        workspace=self.app.workspace
        self.app._change_theme('Koyu')
        self.app._switch_mode('dxf_dwg');self.app._switch_mode('pdf');self.app._switch_mode('k_factor')
        self.assertIs(self.app.workspace,workspace)
        self.assertEqual(self.app.k_state['punch'].get(),'1,5')
        self.assertEqual(self.app.k_state['die'].get(),'17')
        self.assertEqual(load_settings(self.settings)['kr_punch'],'1,5')

    def test_measured_ba_and_outside_dimensions_calculator(self):
        self.app._switch_mode('k_factor')
        for key,value in dict(method='BA ölçümü',radius='2',ba='4,39822971502571').items():
            self.app.k_state[key].set(value)
        result=self.app._preview_k_calculation()
        self.assertAlmostEqual(result.k_factor,.4)
        self.assertIn('Ölçümden K',self.app.k_calculation_label.cget('text'))
        for key,value in dict(ba='',outside_a='50',outside_b='40',flat='86.3982297150257').items():
            self.app.k_state[key].set(value)
        self.assertAlmostEqual(self.app._preview_k_calculation().k_factor,.4)

    def test_invalid_calculation_blocks_worker(self):
        self.app._switch_mode('k_factor');self.app.k_state['die'].set('nan')
        with patch('k_factor.window.update_assembly') as worker:
            self.app.start_button.invoke();self.app.scan_button.invoke()
        worker.assert_not_called()
        self.assertFalse(self.app.busy)

    def test_real_preview_and_apply_worker_result_events(self):
        model=SheetPart()
        assembly=FakeAssembly('/work/main.sldasm',[FakeComponent(model.path)])
        app=FakeApp(model,previous=assembly)
        self.app._switch_mode('k_factor')
        with solidworks_session(ap, app, 'kr'):
            self.app.scan_button.invoke();self.wait_idle()
            self.assertTrue(self.app.results[0]['preview'])
            self.assertIn('Önizleme tamamlandı',self.app.status_label.cget('text'))
            self.assertEqual(model.feature.modify_count,0)
            self.app.start_button.invoke();self.wait_idle()
        self.assertFalse(self.app.results[0]['preview'])
        self.assertEqual(self.app.results[0]['status'],'success',self.app.results[0]['detail'])
        self.assertEqual(model.states['Default']['k'],.43)
        self.assertEqual(model.save_count,0)
        self.assertEqual(self.app.progress.get(),1)
        self.assertEqual(self.app.nav_buttons['k_factor'].cget('state'),'normal')

    def test_small_large_and_scaled_layout_in_both_themes(self):
        self.app._switch_mode('k_factor')
        try:
            for size,scale in (('1000x690',1),('1240x860',1),('1400x900',1.25)):
                ctk.set_widget_scaling(scale)
                self.app.geometry(size)
                for theme in ('Açık','Koyu'):
                    with self.subTest(size=size,theme=theme):
                        self.app._change_theme(theme)
                        self.wait_layout()
                        for widget in (self.app.start_button,self.app.stop_button,self.app.scan_button,
                                       self.app.open_button,self.app.table,
                                       self.app.status_label,self.app.nav_buttons['k_factor']):
                            self.assert_inside(widget)
                        self.assertGreater(self.app.table.winfo_height(),80)
        finally:
            ctk.set_widget_scaling(1)


if __name__=='__main__': unittest.main()
