"""Regressions for callable COM return objects and inactive allowance members."""

import unittest
from copy import deepcopy
from types import SimpleNamespace

from support.fixtures import KApplyTestCase
from support.solidworks import Definition, SheetFeature

from k_factor import apply as ap
from k_factor.rules import ManualAssignment


class MemberNotFound(Exception):
    hresult = -2147352573

    def __init__(self):
        super().__init__(self.hresult, 'Üye bulunamadı.', None, None)


class ReturnedAllowance(SimpleNamespace):
    _oleobj_ = object()

    def __call__(self):
        # A dispatch object's default member is not GetCustomBendAllowance.
        raise MemberNotFound()


class NativeDefinition(Definition):
    _oleobj_ = object()

    def __init__(self, feature):
        super().__init__(feature)
        self.allowance = ReturnedAllowance(**vars(self.allowance))

    @property
    def GetCustomBendAllowance(self):
        return self.allowance

    def __call__(self):
        raise MemberNotFound()


class ActiveAllowance:
    _oleobj_ = object()
    fields = {'KFactor': 2, 'BendAllowance': 3, 'BendDeduction': 4, 'BendTableFile': 1, 'BendCalculationTableFile': 5}

    def __init__(self, base):
        object.__setattr__(self, 'base', base)

    def __getattr__(self, key):
        mode = self.fields.get(key)
        if mode is not None and self.base.Type not in (mode if isinstance(mode, tuple) else (mode,)):
            raise MemberNotFound()
        return getattr(self.base, key)

    def __setattr__(self, key, value):
        # Reject inactive writes too, so a read-only fix is insufficient.
        self.__getattr__(key)
        setattr(self.base, key, value)


class ModeDefinition(Definition):
    @property
    def GetCustomBendAllowance(self):
        return ActiveAllowance(self.allowance)

    def SetCustomBendAllowance(self, value):
        self.allowance = value.base


class NativeDispatchApplyTests(KApplyTestCase):
    @staticmethod
    def flagged(obj):
        obj._FlagAsMethod = lambda *names: None
        return obj

    def manual(self, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default',
                               ManualAssignment(2, .274, 2), **kwargs)

    def test_late_bound_children_mark_methods_before_metadata_can_infer_getters(self):
        class MetadataDispatch:
            _oleobj_ = object()
            def __init__(self):
                self.methods = set()
            def _FlagAsMethod(self, *names):
                self.methods.update(names)
            def __getattr__(self, name):
                if name not in self.methods:
                    raise MemberNotFound()
                if name == 'GetTemplateSheetMetal':
                    return lambda: self.feature
                if name == 'GetUseGaugeTable':
                    def gauge(used, filename):
                        used.value = True
                        return 0
                    return gauge
                raise AttributeError(name)
        dispatch = MetadataDispatch()
        dispatch.feature = self.model.feature
        self.assertIs(ap._optional_read(dispatch, 'GetTemplateSheetMetal'), self.model.feature)
        used, filename = ap._out(ap.pythoncom.VT_BOOL), ap._out(ap.pythoncom.VT_BSTR)
        self.assertEqual(ap._call_byref(dispatch, 'GetUseGaugeTable', used, filename), 0)
        self.assertTrue(used.value)
        self.assertEqual(dispatch.methods, {'GetTemplateSheetMetal', 'GetUseGaugeTable'})

    def test_assembly_loaded_proxy_is_replaced_before_reading_sheet_parameters(self):
        model = self.model
        class LoadedProxy:
            ConfigurationManager = model.ConfigurationManager
            GetType = model.GetType
            GetPathName = model.GetPathName
            GetSaveFlag = model.GetSaveFlag

            @property
            def Visible(self):
                return model.Visible

            @Visible.setter
            def Visible(self, value):
                model.Visible = value

            def GetBodies2(self, *args):
                raise AssertionError('Read bodies from the activated document.')

            def ExportToDWG2(self, *args):
                raise AssertionError('K/R must not export anything.')

        self.app.GetOpenDocument = lambda path: LoadedProxy()
        self.model.Visible = False
        for preview in (True, False):
            with self.subTest(preview=preview):
                status, detail, _ = self.manual(preview=preview)
                self.assertEqual(status, 'success', detail)
                self.assertEqual(model.states['Default']['k'], .4 if preview else .274)
                self.assertFalse(model.Visible)
                self.assertFalse(self.app.closed)

    def test_rebuild_warning_does_not_block_manual_sheet_parameter_reading(self):
        self.app.activate_error = 2
        for preview in (True, False):
            with self.subTest(preview=preview):
                status, detail, _ = self.manual(preview=preview)
                self.assertEqual(status, 'success', detail)
                self.assertEqual(self.model.states['Default']['k'], .4 if preview else .274)

    def test_activation_rebuild_failure_stops_before_any_kr_write(self):
        self.app.activate_error = 2
        self.model.rebuild_fail = True
        before = deepcopy(self.model.states)
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('Etkinleştirilen belge yeniden oluşturulamadı', detail)
        self.assertEqual(self.model.states, before)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_real_activation_error_still_stops_before_any_kr_write(self):
        self.app.activate_error = 1
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('hata kodu: 1', detail)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_type_aware_nested_definition_does_not_break_gauge_outputs(self):
        class TypedDefinition(NativeDefinition):
            def GetUseGaugeTable(self, *args):
                # InvokeTypes returns the retval together with output values.
                return (0, self.feature.model.gauge, '')
        self.model.feature.GetDefinition = lambda: TypedDefinition(self.model.feature)
        self.client.dynamic.DumbDispatch.side_effect = lambda obj: self.flagged(Definition(obj.feature))
        status, detail, _ = self.manual()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.model.gauge = True
        writes = self.model.feature.modify_count
        status, detail, _ = self.manual()
        self.assertEqual(status, 'error')
        self.assertIn('tablo bağını kaldırın', detail)
        self.assertEqual(self.model.feature.modify_count, writes)

    def test_type_aware_child_override_outputs_keep_true_and_false_distinct(self):
        typed = SimpleNamespace(_oleobj_=object(),
                                GetOverrideDefaultParameter2=lambda *args: (0, False))
        def read_override(parameter, output):
            output.value = parameter == 1
            return 0
        self.client.dynamic.DumbDispatch.side_effect = lambda obj: self.flagged(SimpleNamespace(
            GetOverrideDefaultParameter2=read_override))
        self.assertEqual(ap._sheet_overrides(typed), (False, True))

    def test_nested_document_save_uses_explicit_error_and_warning_outputs(self):
        self.model._oleobj_ = object()
        save = self.model.Save3
        self.model.Save3 = lambda *args: (True, 0, 0)
        self.client.dynamic.DumbDispatch.side_effect = lambda obj: self.flagged(SimpleNamespace(Save3=save))
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.save_count, 1)
        self.model.save_fail = True
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('kaydedilemedi', detail)

    def test_our_configuration_switch_is_not_mistaken_for_preexisting_edits(self):
        self.model.states['Other'] = deepcopy(self.model.states['Default'])
        self.model.ShowConfiguration2('Other')
        original_switch = self.model.ShowConfiguration2
        def switch(name):
            self.model.dirty = True
            return original_switch(name)
        self.model.ShowConfiguration2 = switch
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.save_count, 1)
        self.assertEqual(self.model.config, 'Other')
        # A subsequent call must still protect edits made by the user at entry.
        self.model.dirty = True
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('önceden kaydedilmemiş', detail)
        self.assertEqual(self.model.save_count, 1)

    def test_callable_custom_allowance_return_is_not_invoked_as_default_member(self):
        self.model.feature.GetDefinition = lambda: NativeDefinition(self.model.feature)
        status, detail, _ = self.manual()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(self.model.states['Default']['radius'], .002)
        self.assertEqual(self.model.save_count, 0)

    def test_callable_feature_definition_return_is_not_invoked_as_default_member(self):
        class NativeFeature(SheetFeature):
            @property
            def GetDefinition(self):
                return NativeDefinition(self)
        self.model.feature = NativeFeature(self.model)
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(self.model.save_count, 1)

    def test_inactive_allowance_getters_and_setters_are_not_used(self):
        self.model.feature.GetDefinition = lambda: ModeDefinition(self.model.feature)
        before = deepcopy(self.model.states['Default'])
        status, detail, _ = self.manual()
        self.assertEqual(status, 'success', detail)
        after = self.model.states['Default']
        self.assertEqual(after['k'], .274)
        for key in ('thickness', 'ba', 'bd'):
            self.assertEqual(after[key], before[key])

    def test_manual_assignment_can_replace_bend_allowance_mode(self):
        self.model.states['Default']['type'] = 3
        self.model.feature.GetDefinition = lambda: ModeDefinition(self.model.feature)
        status, detail, _ = self.manual()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['type'], 2)
        self.assertEqual(self.model.states['Default']['k'], .274)

    def test_rollback_restores_original_active_allowance_mode(self):
        self.model.states['Default']['type'] = 3
        self.model.feature.GetDefinition = lambda: ModeDefinition(self.model.feature)
        self.model.rebuild_fail = True
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        state = self.model.states['Default']
        self.assertEqual(state['type'], 3)
        self.assertEqual(state['ba'], .004)
        self.assertEqual(state['radius'], .002)
        self.assertEqual(self.model.save_count, 0)

    def test_required_getter_failure_names_member_and_stage_without_writing(self):
        class BrokenAllowance:
            Type = 2
            @property
            def KFactor(self):
                raise MemberNotFound()
        def definition():
            result = Definition(self.model.feature)
            result.allowance = BrokenAllowance()
            return result
        self.model.feature.GetDefinition = definition
        status, detail, _ = self.manual(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('Mevcut K/R ve büküm payı okuma', detail)
        self.assertIn('KFactor', detail)
        self.assertIn('-2147352573', detail)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_wrong_thickness_never_reads_allowance_api(self):
        self.model.states['Default']['thickness'] = .003
        class ThicknessOnly(Definition):
            def GetCustomBendAllowance(self):
                raise AssertionError('Nonmatching thickness must not read allowance.')
        self.model.feature.GetDefinition = lambda: ThicknessOnly(self.model.feature)
        status, detail, _ = self.manual()
        self.assertEqual(status, 'skipped', detail)
        self.assertEqual(self.model.feature.modify_count, 0)


class CalculationTableAllowance(ActiveAllowance):
    fields = dict(ActiveAllowance.fields, BendTableFile=1, BendCalculationTableFile=5)

    def __init__(self, base):
        super().__init__(base)
        object.__setattr__(self, 'last_set', None)

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        object.__setattr__(self, 'last_set', key)
        if key in self.fields:
            # Real active setters also select their own mode.
            self.base.Type = self.fields[key]


class CalculationTableDefinition(Definition):
    def __init__(self, feature):
        super().__init__(feature)
        self.allowance.BendCalculationTableFile = self.data['calculation_table']

    def GetCustomBendAllowance(self):
        return CalculationTableAllowance(self.allowance)

    def SetCustomBendAllowance(self, value):
        assert value.last_set == 'Type', 'Finalize Type after the active value setter'
        self.allowance = value.base


class CalculationTableFeature(SheetFeature):
    def GetDefinition(self):
        return CalculationTableDefinition(self)

    def ModifyDefinition(self, definition, model, component):
        self.modify_count += 1
        state = model.states[model.config]
        state.update(radius=definition.BendRadius, type=definition.allowance.Type)
        if state['type'] == 2:
            state['k'] = definition.allowance.KFactor
        elif state['type'] == 5:
            state['calculation_table'] = definition.allowance.BendCalculationTableFile
        return True


class CalculationTableTests(KApplyTestCase):
    def setUp(self):
        super().setUp()
        self.model.feature = CalculationTableFeature(self.model)
        self.model.states['Default'].update(type=5, calculation_table=r'C:\Tablolar\Özel hesap.xls')

    def test_type_five_snapshot_reads_calculation_table_not_bend_table(self):
        before = ap._state(self.model.feature)
        self.assertEqual(before.allowance_type, 5)
        self.assertEqual(before.bend_table, r'C:\Tablolar\Özel hesap.xls')
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
                                          ManualAssignment(2, .274, 2))
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(self.model.states['Default']['type'], 2)

    def test_failed_write_restores_type_five_file_and_finalizes_type_last(self):
        before = ap._state(self.model.feature)
        self.model.rebuild_fail = True
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
                                          ManualAssignment(2, .274, 3), save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertTrue(ap._same([before], [ap._state(self.model.feature)]))
        self.assertEqual(self.model.states['Default']['calculation_table'], r'C:\Tablolar\Özel hesap.xls')
        self.assertEqual(self.model.save_count, 0)


if __name__ == '__main__':
    unittest.main()
