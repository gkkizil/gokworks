"""Direct Sheet-Metal API contracts; these doubles do not run SolidWorks."""

from copy import deepcopy
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch

from modules.k_factor import apply as ap
from modules.k_factor import sheetmetal_parameters as sm
from modules.k_factor.rules import AssignmentTable, ManualAssignment
from support.fixtures import KApplyTestCase
from support.solidworks import Definition, FakeFeature, SheetFeature, Variant
from modules.k_factor.tests.test_parent_k_radius import ParentDefinition, ParentFeature
from modules.k_factor.tests.test_power_sm_k_radius import BendFeature


class DirectParameterTests(KApplyTestCase):
    def process(self, recipe=None, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default',
                               recipe or ManualAssignment('2', '0,274', '1,5'),
                               parameter_only=True, **kwargs)

    def forbid_legacy_paths(self):
        for member in ('_check_defaults', '_normalize_bends', '_check_converted_values',
                       '_check_inherited_sheet', '_radius_dimension'):
            self.enterContext(patch.object(ap, member, side_effect=AssertionError(member)))
        original = self.model.feature.GetDefinition

        def definition():
            data = original()
            data.GetUseGaugeTable = lambda *args: self.fail('Gauge table must not be queried')
            data.GetOverrideDefaultParameter2 = lambda *args: self.fail('Overrides must not be queried')
            return data

        self.model.feature.GetDefinition = definition

    def test_direct_values_without_any_table_inheritance_or_dimension_path(self):
        self.forbid_legacy_paths()
        self.model.gauge = self.model.material_link = True
        status, detail, result = self.process()
        self.assertEqual(status, 'success', detail)
        state = self.model.states['Default']
        self.assertEqual((state['k'], state['radius'], state['thickness'], state['type']),
                         (.274, .0015, .002, 2))
        self.assertEqual(result.radius_mm, 1.5)
        self.assertEqual(self.model.save_count, 0)

    def test_preview_is_read_only_even_when_save_requested(self):
        self.forbid_legacy_paths()
        before = deepcopy(self.model.states)
        status, detail, result = self.process(preview=True, save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states, before)
        self.assertEqual((self.model.feature.modify_count, self.model.save_count), (0, 0))
        self.assertEqual(result.k_factor, .274)

    def test_nonmatching_thickness_skips_before_allowance_read(self):
        class ThicknessOnly:
            Thickness = .003

            def GetCustomBendAllowance(self):
                raise AssertionError('Nonmatching sheets must stop before allowance reads')

        self.model.feature.GetDefinition = lambda: ThicknessOnly()
        status, detail, result = self.process(save=True)
        self.assertEqual(status, 'skipped', detail)
        self.assertIn('eşleşmedi', detail)
        self.assertIsNone(result)
        self.assertEqual(self.model.save_count, 0)

    def test_regular_solid_skips_without_requesting_its_definition(self):
        self.model.feature = FakeFeature(kind='Boss')
        self.model.feature.GetDefinition = lambda: self.fail('Regular solid definition queried')
        self.model.feature.IsSuppressed2 = lambda *args: self.fail('Unrelated suppression queried')
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'skipped', detail)
        self.assertEqual(self.model.save_count, 0)

    def test_custom_bends_are_never_read_or_normalized(self):
        bend = BendFeature(self.model)
        self.model.feature.child = bend
        before = deepcopy(bend.states)
        bend.GetDefinition = lambda: self.fail('Only the SheetMetal parameters may be edited')
        status, detail, _ = self.process(ManualAssignment(2, .31, 2.5, all_bends=True))
        self.assertEqual(status, 'success', detail)
        self.assertEqual(bend.states, before)

    def test_readback_mismatch_restores_original_active_bend_allowance(self):
        self.model.states['Default'].update(type=4, bd=.0032)
        self.model.readback_fail = True
        before = deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('geri yüklendi ve kontrol edildi', detail)
        self.assertNotIn('GERİ ALMA HATASI', detail)
        # K is inactive in mode 4; restore the actual bend-deduction payload.
        self.assertTrue(sm.same(sm.snapshot(self.model), (
            sm.Parameters('Sheet-Metal1', 'SheetMetal', .002, .002, 4, .0032),)))
        self.assertEqual(self.model.states['Default']['thickness'], before['Default']['thickness'])
        self.assertEqual(self.model.save_count, 0)

    def test_modify_failure_releases_access_and_does_not_save(self):
        self.model.modify_fail = True
        before = deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('ModifyDefinition', detail)
        self.assertEqual(self.model.states, before)
        self.assertEqual(self.model.feature.release_count, 1)
        self.assertEqual(self.model.save_count, 0)

    def test_other_configuration_is_unchanged_and_original_view_restored(self):
        self.model.states['Other'] = dict(self.model.states['Default'], k=.41, radius=.003)
        self.model.ShowConfiguration2('Other')
        baseline = deepcopy(self.model.states['Other'])
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Other'], baseline)
        self.assertEqual(self.model.config, 'Other')
        self.assertEqual(self.model.save_count, 1)

    def test_cross_configuration_leak_is_rolled_back_and_not_saved(self):
        self.model.states['Other'] = deepcopy(self.model.states['Default'])
        self.model.propagate = True
        before = deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('başka konfigürasyona yayıldı', detail)
        self.assertEqual(self.model.states, before)
        self.assertEqual(self.model.save_count, 0)

    def test_failed_rollback_is_visible_and_open_document_is_retained(self):
        self.model.readback_fail = True
        with patch.object(sm.ParameterEdit, 'rollback', side_effect=RuntimeError('rollback failed')):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('GERİ ALMA HATASI', detail)
        self.assertIn('Parçayı kaydetmeyin', detail)
        self.assertEqual(self.model.save_count, 0)
        self.assertFalse(self.app.closed)

    def test_unreadable_post_write_snapshot_still_attempts_known_baseline_restore(self):
        baseline = deepcopy(self.model.states)
        snapshot = sm.snapshot

        def temporarily_unreadable(model):
            if model.states['Default']['k'] == .274:
                raise RuntimeError('Rebuild left the post-write snapshot unreadable')
            return snapshot(model)

        with patch.object(sm, 'snapshot', side_effect=temporarily_unreadable):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('geri yüklendi ve kontrol edildi', detail)
        self.assertNotIn('GERİ ALMA HATASI', detail)
        self.assertEqual(self.model.states, baseline)
        self.assertEqual(self.model.save_count, 0)

    def test_repeated_assignment_retains_new_values(self):
        for recipe in (ManualAssignment(2, .274, 1.5), ManualAssignment(2, .33, 2),
                       ManualAssignment(2, .33, 2)):
            status, detail, _ = self.process(recipe)
            self.assertEqual(status, 'success', detail)
            self.assertEqual(self.model.states['Default']['k'], recipe.k_factor)
            self.assertEqual(self.model.states['Default']['radius'], recipe.radius_mm / 1000)

    def test_assembly_worker_uses_direct_parameter_path(self):
        self.forbid_legacy_paths()
        events = Queue()
        table = AssignmentTable((ManualAssignment(2, .274, 1.5),))
        with patch.object(ap, 'connect_to_solidworks', return_value=self.app):
            ap.update_assembly(table, events)
        results = [value for kind, value in events.queue if kind == 'result']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'success', results)
        self.assertEqual(results[0]['quantity'], 3)
        self.assertEqual(self.model.feature.modify_count, 1)
        self.assertIs(self.app.ActiveDoc, self.assembly)


class ModernParameterTests(KApplyTestCase):
    process = DirectParameterTests.process

    def setUp(self):
        super().setUp()
        self.model.parent_states = {name: dict(value, table='', calculation_table='')
                                    for name, value in self.model.states.items()}
        self.model.parent_reads = self.model.parent_writes = 0
        self.model.parent_gauge = self.model.parent_material = True
        self.model.freeze_child = self.model.parent_leak = False
        self.model.Extension.GetTemplateSheetMetal = lambda: ParentFeature(self.model)

    def test_parent_code_two_and_body_code_two_cannot_block_assignment(self):
        class NoTableParent(ParentDefinition):
            def GetUseGaugeTable(self, *args):
                raise AssertionError('API status 2 is irrelevant to direct K/R edits')

        with patch.object(ParentFeature, 'GetDefinition', lambda feature: NoTableParent(feature)):
            status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.parent_states['Default']['radius'], .0015)

    def test_conversion_overrides_and_different_template_thickness_are_retained(self):
        self.model.freeze_child = True
        self.model.parent_states['Default']['thickness'] = .009
        self.model.states['Default']['thickness'] = .0015
        from modules.k_factor.tests.test_converted_k_radius import ConvertedFeature

        class ConversionWithoutModifierAccess(ConvertedFeature):
            @property
            def GetDefinition(self):
                raise AssertionError('Never request the conversion modifier')

        converted = ConversionWithoutModifierAccess(self.model)
        converted.flags = dict.fromkeys(converted.flags, True)
        self.model.feature.child = converted
        before = deepcopy(self.model.states)
        status, detail, result = self.process(ManualAssignment(1.5, .274, 1.5))
        self.assertEqual(status, 'success', detail)
        self.assertEqual(result.thickness_mm, 1.5)
        self.assertEqual(self.model.parent_states['Default']['thickness'], .009)
        self.assertEqual(self.model.states, before)
        self.assertTrue(all(converted.flags.values()))
        self.assertIn('Hedef: SAC LEVHA', detail)


class RawOle:
    """A COM server whose type information is unavailable (TYPE_E_ELEMENTNOTFOUND)."""

    def __init__(self, target):
        self.target = target
        self.calls = []

    def GetTypeInfo(self, *args):
        raise AssertionError('GetTypeInfo must never be needed')

    def GetIDsOfNames(self, lcid, member):
        return member

    def Invoke(self, member, lcid, flags, want_result, *args):
        self.calls.append((member, flags, args))
        args = tuple(arg.target if isinstance(arg, RawOle) else
                     None if isinstance(arg, Variant) and arg.kind == 9 else arg for arg in args)
        if flags == 4:
            setattr(self.target, member, args[0])
            return None
        value = getattr(self.target, member)
        value = value(*args) if flags == 1 and callable(value) else value
        if isinstance(value, (str, int, float, bool, tuple, list)) or value is None:
            return value
        return RawOle(value)


class RawDispatchTests(KApplyTestCase):
    def test_native_invoke_avoids_broken_type_info_and_uses_dispatch_null(self):
        raw_model = RawOle(self.model)
        before = sm.read(RawOle(self.model.feature))
        target = sm.target(before, SimpleNamespace(k_factor=.274, radius_mm=1.5))
        modules = {'pythoncom': self.com, 'win32com.client': self.client}
        with patch.dict('sys.modules', modules):
            sm.write(raw_model, target)
        self.assertTrue(sm.same((target,), (sm.read(RawOle(self.model.feature)),)))
        self.assertEqual(self.model.feature.access_count, 1)
        self.assertEqual(self.model.feature.modify_count, 1)
