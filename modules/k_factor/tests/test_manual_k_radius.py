"""Kalınlık eşleştirerek kullanıcı K/R değerlerini aynen atama."""

import csv
import unittest
from copy import deepcopy
from queue import Queue
from unittest.mock import patch

from support.fixtures import KApplyTestCase
from support.solidworks import (
    FakeAssembly,
    FakeComponent,
    FakeMultiPartApp,
    SheetPart,
    solidworks_session,
)

from modules.k_factor import apply as ap
from modules.k_factor.rules import ManualAssignment, ThicknessMismatch, calculate
from shared.settings import load_settings


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




if __name__=='__main__':unittest.main()
