"""Modern SAC LEVHA selection with independent parent/child stored state.

The parent is intentionally absent from normal feature traversal. Each lookup
returns a new wrapper/definition; modifying a child cannot update the parent.
These are API-contract tests, not native SolidWorks geometry validation.
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from k_factor import apply as ap
from k_factor.rules import ManualAssignment
from support.fixtures import KApplyTestCase
from support.solidworks import Definition, SheetFeature
from test_converted_k_radius import ConvertedFeature


class ChildDefinition(Definition):
    def GetOverrideDefaultParameter2(self, parameter, overridden):
        overridden.value = self.feature.model.overrides[parameter]
        return self.feature.model.override_error


class ParentDefinition(Definition):
    def __init__(self, feature):
        super().__init__(feature)
        data = feature.model.parent_states[feature.model.config]
        self.Thickness, self.BendRadius = data['thickness'], data['radius']
        self.allowance = SimpleNamespace(Type=data['type'], KFactor=data['k'],
                        BendAllowance=data['ba'], BendDeduction=data['bd'],
                        BendTableFile=data.get('table', ''),
                        BendCalculationTableFile=data.get('calculation_table', ''))
        self.UseMaterialSheetMetalParameters = feature.model.parent_material

    def GetUseGaugeTable(self, used, filename):
        used.value = self.feature.model.parent_gauge
        return 0


class ParentFeature(SheetFeature):
    def __init__(self, model):
        super().__init__(model)
        self.Name = 'SAC LEVHA – Özelleştirilmiş'
        self.kind = 'TemplateSheetMetal'

    def GetDefinition(self):
        self.model.parent_reads += 1
        return ParentDefinition(self)

    def ModifyDefinition(self, definition, model, component):
        model.parent_writes += 1
        # Child writes do NOT share this storage. The original child-only
        # implementation would leave the UI-visible parent at K=.5.
        state = model.parent_states[model.config]
        state.update(radius=definition.BendRadius, type=definition.allowance.Type,
                     k=definition.allowance.KFactor, ba=definition.allowance.BendAllowance,
                     bd=definition.allowance.BendDeduction,
                     table=definition.allowance.BendTableFile,
                     calculation_table=definition.allowance.BendCalculationTableFile)
        if not model.freeze_child:
            model.states[model.config].update({key: state[key] for key in model.states[model.config]})
        if model.parent_leak:
            for config in model.parent_states:
                model.parent_states[config] = deepcopy(state)
        return True


class ParentApplyTests(KApplyTestCase):
    def setUp(self):
        super().setUp()
        self.model.states['Default'].update(k=.5, radius=.0005, thickness=.0015)
        self.model.states['Other'] = dict(self.model.states['Default'], k=.4)
        self.model.parent_states = {name: dict(state, table='', calculation_table='')
                                    for name, state in self.model.states.items()}
        self.model.parent_reads = self.model.parent_writes = 0
        self.model.parent_gauge = self.model.parent_material = False
        self.model.freeze_child = self.model.parent_leak = False
        self.model.overrides = {0: False, 1: False}
        self.model.override_error = 0
        self.model.feature.GetDefinition = lambda: ChildDefinition(self.model.feature)
        self.lookup_count = 0
        self.model.Extension.GetTemplateSheetMetal = self.parent
        self.converted = ConvertedFeature(self.model)
        self.model.feature.child = self.converted

    def parent(self):
        self.lookup_count += 1
        return ParentFeature(self.model)

    def process(self, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default',
                               ManualAssignment('1,5', '0,274', '1,5'), **kwargs)

    def test_separate_parent_and_inherited_child_conversion_are_verified(self):
        self.model.ShowConfiguration2('Other')
        other_parent = deepcopy(self.model.parent_states['Other'])
        other_child = deepcopy(self.model.states['Other'])
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        for state in (self.model.states['Default'], self.model.parent_states['Default']):
            self.assertEqual((state['k'], state['radius'], state['thickness'], state['type']),
                             (.274, .0015, .0015, 2))
        self.assertEqual(self.model.parent_states['Other'], other_parent)
        self.assertEqual(self.model.states['Other'], other_child)
        self.assertEqual(self.model.config, 'Other')
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.parent_writes, 1)
        self.assertGreater(self.lookup_count, 5)
        self.assertGreater(self.model.parent_reads, 3)
        self.assertIn('SAC LEVHA – Özelleştirilmiş (TemplateSheetMetal)', detail)
        self.assertIn('Konfigürasyon: Default', detail)
        self.assertIn('Önceki K=0.5, R=0.5 mm', detail)
        self.assertIn('Doğrulanan K=0.274, R=1.5 mm', detail)
        self.assertIn('dosyaya kaydedilmedi', detail)
        self.assertIn('1 SheetMetal alt unsuru doğrulandı', detail)
        self.assertIn('Katıyı Saca Dönüştür: 1 unsurda', detail)

    def test_folder_api_is_valid_fallback_for_explicit_null_template(self):
        self.model.Extension.GetTemplateSheetMetal = lambda: None
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(GetFeature=self.parent)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.save_count, 1)
        self.assertIn('Parça dosyası kaydedildi', detail)

    def test_tree_order_and_localized_display_name_do_not_select_a_child(self):
        parent = self.parent()
        self.model.feature.next = parent
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_writes, 1)
        self.assertEqual(self.model.feature.modify_count, 0)

    def test_preview_and_body_thickness_mismatch_never_write(self):
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(preview=True, save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        # Parent defaults match the requested thickness, but actual body does not.
        self.model.states['Default']['thickness'] = .002
        self.model.parent_material = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'skipped', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_child_only_write_cannot_qualify_as_parent_success(self):
        real_modify = ap._modify
        def child_only(model, feature, state):
            if state.k_factor == .274:
                # Reproduce the old bug even though selector now found parent.
                return real_modify(model, model.feature, state)
            return real_modify(model, feature, state)
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        with patch.object(ap, '_modify', side_effect=child_only):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri okumada eşleşmedi', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_stale_child_readback_restores_separately_obtained_parent(self):
        self.model.freeze_child = True
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('SheetMetal alt unsuru', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.parent_writes, 2)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_unreadable_conversion_still_restores_parent_and_verifies_rollback(self):
        self.converted.missing_on_change = True
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_cross_configuration_parent_drift_never_reports_success(self):
        self.model.parent_leak = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('başka konfigürasyona', detail)
        # This artificial global setter cannot restore two different originals.
        self.assertIn('GERİ ALMA HATASI', detail)
        self.assertEqual(self.model.save_count, 0)

    def test_parent_and_child_material_gauge_and_override_restrictions(self):
        for flag in ('parent_gauge', 'parent_material', 'gauge', 'material_link'):
            with self.subTest(flag=flag):
                setattr(self.model, flag, True)
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
                setattr(self.model, flag, False)
        for parameter in (0, 1):
            self.model.overrides[parameter] = True
            status, detail, _ = self.process(save=True)
            self.assertEqual(status, 'error', detail)
            self.model.overrides[parameter] = False
        self.model.override_error = 3
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('API hata kodu: 3', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_parent_lookup_errors_null_folder_feature_and_wrong_types_fail_closed(self):
        def broken():
            raise RuntimeError('lookup failed')
        for lookup in (broken, lambda: self.model.feature):
            with self.subTest(lookup=lookup):
                self.model.Extension.GetTemplateSheetMetal = lookup
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
        self.model.Extension.GetTemplateSheetMetal = lambda: None
        self.model.FeatureManager.GetSheetMetalFolder = broken
        self.assertEqual(self.process()[0], 'error')
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(GetFeature=lambda: None)
        self.assertEqual(self.process()[0], 'error')
        self.model.FeatureManager.GetSheetMetalFolder = lambda: None
        self.model.feature.next = self.parent()
        self.assertEqual(self.process()[0], 'error')
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_suppressed_or_errored_parent_stops_before_writing(self):
        for failure in ('suppressed', 'error', 'suppression_api'):
            def lookup():
                parent = self.parent()
                parent.suppressed = failure == 'suppressed'
                parent.GetErrorCode = lambda: 7 if failure == 'error' else 0
                if failure == 'suppression_api':
                    parent.IsSuppressed2 = lambda *args: None
                return parent
            self.model.Extension.GetTemplateSheetMetal = lookup
            status, detail, _ = self.process(save=True)
            self.assertEqual(status, 'error', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_parent_lookup_failure_after_write_cannot_report_success(self):
        def lookup():
            if self.model.parent_writes == 1:
                # One transient readback failure; rollback can still reacquire.
                self.model.Extension.GetTemplateSheetMetal = self.parent
                raise RuntimeError('fresh parent lookup failed')
            return self.parent()
        self.model.Extension.GetTemplateSheetMetal = lookup
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('fresh parent lookup failed', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_child_disappearing_after_write_restores_parent(self):
        self.model.feature.IsSuppressed2 = lambda *args: (self.model.states[self.model.config]['k'] == .274,)
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('alt unsur listesi değişti', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_override_side_effect_cannot_be_reported_as_verified_rollback(self):
        original = ParentFeature.ModifyDefinition
        def add_override(feature, definition, model, component):
            result = original(feature, definition, model, component)
            model.overrides[1] = True
            return result
        with patch.object(ParentFeature, 'ModifyDefinition', add_override):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('GERİ ALMA HATASI', detail)
        self.assertEqual(self.model.save_count, 0)
