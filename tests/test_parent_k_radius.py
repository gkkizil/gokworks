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
from support.solidworks import Definition, SheetFeature, FakeFeature
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
        state.update(thickness=definition.Thickness, radius=definition.BendRadius, type=definition.allowance.Type,
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


class TemplateGaugeUnavailable(ParentDefinition):
    """Native TemplateSheetMetal reports NotEnabledOnTemplate, not a gauge flag."""
    def GetUseGaugeTable(self, used, filename):
        # Outputs are not valid on this result and must never be consumed.
        used.value, filename.value = True, 'invalid-output.xls'
        return 2

    @property
    def UseMaterialSheetMetalParameters(self):
        raise AssertionError('Material getter is invalid after NotEnabledOnTemplate.')

    @UseMaterialSheetMetalParameters.setter
    def UseMaterialSheetMetalParameters(self, value):
        pass


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

    def test_template_gauge_code_two_uses_body_checks_for_preview_and_apply(self):
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        with patch.object(ParentFeature, 'GetDefinition', lambda f: TemplateGaugeUnavailable(f)):
            status, detail, _ = self.process(preview=True)
            self.assertEqual(status, 'success', detail)
            self.assertEqual((self.model.parent_states, self.model.states), before)
            status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.states['Default']['radius'], .0015)
        self.assertEqual(self.model.parent_states['Other'], before[0]['Other'])

    def test_template_gauge_unavailable_still_blocks_body_gauge_and_material_links(self):
        with patch.object(ParentFeature, 'GetDefinition', lambda f: TemplateGaugeUnavailable(f)):
            for attribute in ('gauge', 'material_link'):
                with self.subTest(attribute=attribute):
                    setattr(self.model, attribute, True)
                    before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
                    status, detail, _ = self.process(save=True)
                    self.assertEqual(status, 'error', detail)
                    self.assertIn('tablo bağını kaldırın' if attribute == 'gauge' else 'malzemeye bağlı', detail)
                    self.assertEqual((self.model.parent_states, self.model.states), before)
                    self.assertEqual(self.model.parent_writes, 0)
                    self.assertEqual(self.model.save_count, 0)
                    setattr(self.model, attribute, False)

    def test_non_template_gauge_errors_are_not_treated_as_unused_tables(self):
        with patch.object(ParentFeature, 'GetDefinition', lambda f: TemplateGaugeUnavailable(f)):
            original = self.model.feature.GetDefinition
            for code in (1, 2, 3, 4):
                with self.subTest(code=code):
                    def child_definition():
                        data = original()
                        data.GetUseGaugeTable = lambda used, filename: code
                        return data
                    self.model.feature.GetDefinition = child_definition
                    status, detail, _ = self.process(save=True)
                    self.assertEqual(status, 'error', detail)
                    self.assertIn(f'API hata kodu: {code}', detail)
                    self.assertEqual(self.model.parent_writes, 0)
                    self.assertEqual(self.model.save_count, 0)
            self.model.feature.GetDefinition = original

    def test_inherited_body_code_two_uses_verified_parent_for_preview_apply_and_undo(self):
        original = self.model.feature.GetDefinition

        def body_definition():
            data = original()
            def unavailable(used, filename):
                used.value, filename.value = True, 'invalid-output.xls'
                return 2
            data.GetUseGaugeTable = unavailable
            return data

        self.model.feature.GetDefinition = body_definition
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, result = self.process(preview=True)
        self.assertEqual(status, 'success', detail)
        self.assertIn('ana sac unsurundan doğrulandı', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.parent_writes, 0)
        status, detail, result = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual((self.model.states['Default']['k'], self.model.states['Default']['radius']), (.274, .0015))
        self.assertEqual(self.model.states['Other'], before[1]['Other'])
        self.model.parent_states, self.model.states = deepcopy(before)
        self.model.freeze_child = True
        status, detail, result = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_body_gauge_fallback_requires_verified_parent_and_no_overrides(self):
        original = self.model.feature.GetDefinition
        for code in (1, 2, 3, 4):
            for overrides in ((False, False), (True, False), (False, True)):
                with self.subTest(code=code, overrides=overrides):
                    self.model.overrides = dict(enumerate(overrides))
                    def body_definition():
                        data = original()
                        data.GetUseGaugeTable = lambda used, filename: code
                        return data
                    self.model.feature.GetDefinition = body_definition
                    status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
                        ManualAssignment(1.5, .274, 1.5, all_bends=True), preview=True)
                    self.assertEqual(status, 'success' if code == 2 and not any(overrides) else 'error', detail)
                    if status == 'error':
                        self.assertIn(f'API hata kodu: {code}', detail)
                        self.assertIn('Gövde sac unsuru', detail)
                    self.assertEqual(self.model.parent_writes, 0)

    def test_parent_gauge_and_material_block_body_code_two_inheritance(self):
        original = self.model.feature.GetDefinition
        def body_definition():
            data = original()
            data.GetUseGaugeTable = lambda used, filename: 2
            return data
        self.model.feature.GetDefinition = body_definition
        for attribute in ('parent_gauge', 'parent_material'):
            with self.subTest(attribute=attribute):
                setattr(self.model, attribute, True)
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
                self.assertEqual(self.model.parent_writes, 0)
                self.assertEqual(self.model.save_count, 0)
                setattr(self.model, attribute, False)

    def _set_multiple_bodies(self, flags):
        self.model.bodies = [SimpleNamespace(IsSheetMetal=lambda flag=flag: flag,
            GetFeatures=lambda: (self.model.feature,)) for flag in flags]

    def test_one_sheet_and_regular_solid_preview_apply_preserve_other_configuration(self):
        self._set_multiple_bodies((True, False))
        before = deepcopy(self.model.states)
        status, detail, _ = self.process(preview=True)
        self.assertEqual(status, 'success', detail)
        self.assertIn('1 normal katı gövde K/R kapsamı dışında', detail)
        self.assertEqual(self.model.states, before)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(self.model.states['Other'], before['Other'])
        self.assertEqual(len(self.model.bodies), 2)
        self.assertEqual(self.model.save_count, 1)

    def test_same_thickness_sheet_bodies_share_parent_with_ownership_and_readback(self):
        self._set_multiple_bodies((True, True, True))
        second = SheetFeature(self.model)
        second.Name = 'Sac-Levha2'
        second.GetDefinition = lambda: ChildDefinition(second)
        self.model.feature.next = second
        self.model.bodies[1].GetFeatures = lambda: (second,)
        recipe = ManualAssignment(1.5, .274, 1.5, all_bends=True)
        before = deepcopy(self.model.states)
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default', recipe, preview=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states, before)
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default', recipe, save=True)
        self.assertEqual(status, 'success', detail)
        self.assertIn('3 sac gövdesi', detail)
        self.assertIn('2 SheetMetal alt unsuru doğrulandı', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(self.model.states['Other'], before['Other'])

    def test_multiple_sheet_targets_must_have_one_template_and_no_mixed_solids(self):
        for failure in ('templates', 'mixed'):
            with self.subTest(failure=failure):
                self._set_multiple_bodies((True, True, False) if failure == 'mixed' else (True, True))
                self.model.feature.next = FakeFeature('Other-template', ap.TEMPLATE_SHEET) if failure == 'templates' else None
                status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
                    ManualAssignment(1.5, .274, 1.5, all_bends=True), save=True)
                self.assertEqual(status, 'error', detail)
                self.assertEqual(self.model.parent_writes, 0)
                self.assertEqual(self.model.save_count, 0)

    def test_multibody_missing_ownership_and_unreadable_sheet_flags_never_write(self):
        for failure in ('missing', 'unreadable'):
            with self.subTest(failure=failure):
                self._set_multiple_bodies((True, False))
                if failure == 'missing':
                    self.model.bodies[0].GetFeatures = lambda: (FakeFeature(kind='Boss'),)
                else:
                    self.model.bodies[1].IsSheetMetal = lambda: None
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
                self.assertEqual(self.model.parent_writes, 0)
                self.assertEqual(self.model.save_count, 0)

    def test_multi_sheet_requires_all_bends_and_rejects_mixed_feature_thicknesses(self):
        self._set_multiple_bodies((True, True))
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('Tüm bükümlere uygula', detail)
        child = FakeFeature('SheetMetal-other', 'SheetMetal', thickness=.002)
        self.model.feature.next = child
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
            ManualAssignment(1.5, .274, 1.5, all_bends=True), save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('farklı kalınlıkta', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_multibody_failed_readback_restores_parameters_without_saving(self):
        self._set_multiple_bodies((True, False))
        self.model.freeze_child = True
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_changed_body_inventory_after_rebuild_rolls_back_before_save(self):
        self._set_multiple_bodies((True, False))
        before = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        bodies = tuple(self.model.bodies)
        modify = ParentFeature.ModifyDefinition

        def modify_and_rebuild(feature, definition, model, component):
            result = modify(feature, definition, model, component)
            model.bodies = list(bodies)
            if definition.allowance.KFactor == .274:
                model.bodies.append(SimpleNamespace(IsSheetMetal=lambda: False))
            return result

        with patch.object(ParentFeature, 'ModifyDefinition', modify_and_rebuild):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('gövde sayısı değişti', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual((self.model.parent_states, self.model.states), before)
        self.assertEqual(len(self.model.bodies), 2)
        self.assertEqual(self.model.save_count, 0)

    def test_template_gauge_fallback_requires_a_verified_body_sheet(self):
        self.model.FirstFeature = lambda: self.converted
        self.model.feature.child = None
        with patch.object(ParentFeature, 'GetDefinition', lambda f: TemplateGaugeUnavailable(f)):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('gövde sacının tablo/malzeme durumu doğrulanamadı', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_converted_definition_supplies_actual_thickness_without_sheetmetal_child(self):
        self.model.FirstFeature = lambda: self.converted
        self.model.bodies[0].IsSheetMetal = lambda: False
        self.model.feature.child = None
        status, detail, result = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(result.thickness_mm, 1.5)
        self.assertIn('(SolidToSheetMetal)', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.feature.modify_count, 0)

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

    def test_sac_levha_ui_parent_gets_exact_user_radius_and_k_factor(self):
        def sac_levha():
            feature = self.parent()
            feature.Name = 'Sac-Levha'
            return feature
        self.model.Extension.GetTemplateSheetMetal = sac_levha
        self.model.feature.Name = 'Sac-Levha1'
        for states in (self.model.parent_states, self.model.states):
            states['Default'].update(thickness=.002, type=3, ba=.005)
        with patch('k_factor.rules.recommended_k', side_effect=AssertionError('No table for assignment')):
            status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
                                               ManualAssignment('2', '0,274', '2'))
        self.assertEqual(status, 'success', detail)
        for states in (self.model.parent_states, self.model.states):
            state = states['Default']
            self.assertEqual((state['radius'], state['k'], state['type'], state['thickness']),
                             (.002, .274, 2, .002))
        self.assertEqual(self.model.parent_writes, 1)
        self.assertIn('Sac-Levha (TemplateSheetMetal)', detail)
        self.assertIn('Sac-Levha1 (SheetMetal)', detail)

    def test_conversion_keeps_actual_thickness_when_template_default_differs(self):
        self.model.states.pop('Other')
        self.model.parent_states.pop('Other')
        self.converted = ConvertedFeature(self.model)
        self.model.feature.child = self.converted
        self.model.parent_states['Default']['thickness'] = .001
        self.converted.flags = dict.fromkeys(self.converted.flags, True)
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
            ManualAssignment(1.5, .274, 2, all_bends=True))
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['thickness'], .0015)
        self.assertEqual(self.model.parent_states['Default']['thickness'], .0015)
        self.assertEqual(self.model.states['Default']['radius'], .002)
        self.assertEqual(self.model.states['Default']['k'], .274)
        self.assertEqual(tuple(self.converted.flags.values()), (False, False))
        self.assertIn('gerçek gövde kalınlığı korundu', detail)

    def test_failed_conversion_restores_distinct_template_thickness_and_overrides(self):
        self.model.states.pop('Other')
        self.model.parent_states.pop('Other')
        self.converted = ConvertedFeature(self.model)
        self.model.feature.child = self.converted
        self.model.parent_states['Default']['thickness'] = .001
        self.converted.flags = dict.fromkeys(self.converted.flags, True)
        before_parent, before_body = deepcopy(self.model.parent_states), deepcopy(self.model.states)
        self.model.freeze_child = True
        status, detail, _ = ap.process_part(self.app, self.model.path, 'Default',
            ManualAssignment(1.5, .274, 2, all_bends=True))
        self.assertEqual(status, 'error', detail)
        self.assertEqual(self.model.parent_states, before_parent)
        self.assertEqual(self.model.states, before_body)
        self.assertEqual(tuple(self.converted.flags.values()), (True, True))
        self.assertEqual(self.model.save_count, 0)

    def test_folder_api_is_valid_fallback_for_explicit_null_template(self):
        self.model.Extension.GetTemplateSheetMetal = lambda: None
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(GetFeature=self.parent)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.save_count, 1)
        self.assertIn('Parça dosyası kaydedildi', detail)

    def test_missing_template_member_uses_the_documented_folder_feature(self):
        class MissingTemplate:
            @property
            def GetTemplateSheetMetal(self):
                error = RuntimeError('member not found')
                error.hresult = -2147352573
                raise error
        self.model.Extension = MissingTemplate()
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(GetFeature=self.parent)
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertIn('GetSheetMetalFolder.GetFeature', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.feature.modify_count, 0)

    def test_unique_tree_template_is_used_when_discovery_apis_return_null(self):
        self.model.Extension.GetTemplateSheetMetal = lambda: None
        self.model.feature.next = self.parent()
        for preview in (True, False):
            with self.subTest(preview=preview):
                status, detail, _ = self.process(preview=preview)
                self.assertEqual(status, 'success', detail)
                self.assertIn('Kaynak: unsur ağacı', detail)
                self.assertEqual(self.model.parent_states['Default']['k'], .5 if preview else .274)
                self.assertEqual(self.model.feature.modify_count, 0)

    def test_folder_sheet_list_covers_children_absent_from_feature_tree(self):
        self.model.FirstFeature = lambda: None
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(
            GetFeature=self.parent, GetSheetMetals=lambda: (self.model.feature,))
        for preview in (True, False):
            with self.subTest(preview=preview):
                status, detail, _ = self.process(preview=preview)
                self.assertEqual(status, 'success', detail)
                self.assertIn('1 SheetMetal alt unsuru doğrulandı' if not preview else 'Önizleme', detail)
                self.assertEqual(self.model.states['Default']['k'], .5 if preview else .274)
                self.assertEqual(self.model.feature.modify_count, 0)

    def test_folder_list_and_tree_do_not_duplicate_the_same_sheet(self):
        self.model.FeatureManager.GetSheetMetalFolder = lambda: SimpleNamespace(
            GetFeature=self.parent, GetSheetMetals=lambda: (self.model.feature,self.model.feature))
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertIn('1 SheetMetal alt unsuru doğrulandı', detail)
        self.assertEqual(self.model.parent_writes, 1)

    def test_unrelated_history_folder_does_not_block_sheet_discovery(self):
        folder = FakeFeature('Geçmiş', 'HistoryFolder', next_feature=self.model.feature)
        folder.IsSuppressed2 = lambda *args: None
        folder.GetDefinition = lambda: (_ for _ in ()).throw(AssertionError('History has no K/R.'))
        self.model.FirstFeature = lambda: folder
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)

    def test_instant3d_wrapper_uses_its_underlying_sheet_feature_type(self):
        self.model.feature.GetTypeName2 = lambda: 'ICE'
        self.model.feature.GetTypeName = lambda: 'SheetMetal'
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.states['Default']['k'], .274)

    def test_multiple_tree_templates_are_rejected_without_writing(self):
        self.model.Extension.GetTemplateSheetMetal = lambda: None
        first, second = self.parent(), self.parent()
        second.Name = 'SAC LEVHA – İkinci'
        first.next = second
        self.model.feature.next = first
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('Birden fazla ana SAC LEVHA', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.save_count, 0)

    def test_gauge_table_is_checked_before_reading_the_material_property(self):
        class GaugeDefinition(ParentDefinition):
            @property
            def UseMaterialSheetMetalParameters(self):
                raise AssertionError('This property is invalid when a gauge table is used.')

            @UseMaterialSheetMetalParameters.setter
            def UseMaterialSheetMetalParameters(self, value):
                pass
        self.model.parent_gauge = True
        with patch.object(ParentFeature, 'GetDefinition', lambda feature: GaugeDefinition(feature)):
            status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error')
        self.assertIn('Sac kalınlık tablosuna bağlı parça', detail)
        self.assertNotIn('This property is invalid', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.save_count, 0)

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
