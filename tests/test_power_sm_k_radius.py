"""PowerSM routes: ignored definition radius, custom bends, verified rollback.

These models exercise COM contracts; they are not native SolidWorks sessions.
Parent and child values/flags are stored independently for each configuration.
"""

from copy import deepcopy
from types import SimpleNamespace

from k_factor import apply as ap
from k_factor.rules import ManualAssignment
from support.fixtures import KApplyTestCase
from support.solidworks import Definition, FakeFeature, SheetFeature
from test_parent_k_radius import ParentDefinition, ParentFeature


class RadiusDefinition(ParentDefinition):
    def __init__(self, feature):
        self.ignore_radius = False
        super().__init__(feature)
        self.ignore_radius = feature.model.ignore_radius_setter

    @property
    def BendRadius(self):
        return self.radius

    @BendRadius.setter
    def BendRadius(self, value):
        if not self.ignore_radius:
            self.radius = value


def inherit(model):
    parent = model.parent_states[model.config]
    child = model.states[model.config]
    flags = model.flags[model.config]
    if not flags[0]:
        child.update(thickness=parent['thickness'], radius=parent['radius'])
    if not flags[1]:
        child.update({key: parent[key] for key in ('type', 'k', 'ba', 'bd')})


class ModernParent(ParentFeature):
    def GetDefinition(self):
        return RadiusDefinition(self)

    def ModifyDefinition(self, definition, model, component):
        model.parent_writes += 1
        parent = model.parent_states[model.config]
        parent.update(radius=definition.BendRadius, type=definition.allowance.Type,
                      k=definition.allowance.KFactor, ba=definition.allowance.BendAllowance,
                      bd=definition.allowance.BendDeduction,
                      table=definition.allowance.BendTableFile,
                      calculation_table=definition.allowance.BendCalculationTableFile)
        inherit(model)
        return True

    def GetFirstDisplayDimension(self):
        displays = self.model.displays
        return displays[0] if displays else None

    def GetNextDisplayDimension(self, display):
        index = self.model.displays.index(display) + 1
        return self.model.displays[index] if index < len(self.model.displays) else None


class RadiusDimension:
    def __init__(self, model, name='D1', owner=None, kind=5):
        self.model = model
        self.FullName = f'{name}@SAC LEVHA@part'
        self.owner = owner
        self.Type2 = kind

    def GetDimension2(self, index):
        assert index == 0
        return self

    def GetFeatureOwner(self):
        return self.owner or ModernParent(self.model)

    def SetSystemValue3(self, value, configuration, names):
        assert configuration == 1 and names.value is None
        self.model.dimension_calls.append((value, configuration, self.model.config, self.FullName))
        if self.model.dimension_failure:
            self.model.dimension_failure = False
            return 3
        self.model.parent_states[self.model.config]['radius'] = value
        inherit(self.model)
        return 0


class ModernSheetDefinition(Definition):
    def __init__(self, feature):
        super().__init__(feature)
        self.overrides = deepcopy(feature.model.flags[feature.model.config])

    def GetOverrideDefaultParameter2(self, parameter, overridden):
        overridden.value = self.overrides[parameter]
        return 0

    def SetOverrideDefaultParameter2(self, parameter, overridden):
        self.overrides[parameter] = overridden
        return 0


class ModernSheet(SheetFeature):
    def GetDefinition(self):
        return ModernSheetDefinition(self)

    def ModifyDefinition(self, definition, model, component):
        result = super().ModifyDefinition(definition, model, component)
        model.flags[model.config] = deepcopy(definition.overrides)
        inherit(model)
        return result


class BendDefinition:
    def __init__(self, feature):
        self.feature = feature
        self.data = deepcopy(feature.states[feature.model.config])
        for key, value in self.data['flags'].items():
            setattr(self, key, value)
        self.BendRadius = self.data['radius']
        self.UseGaugeTable = self.data['gauge']
        self.relief = self.data['relief']
        self.bend = SimpleNamespace(**self.data['allowance'])

    def GetCustomBendAllowance(self):
        if self.UseDefaultBendAllowance:
            raise AssertionError('Custom getter invalid in inherited mode')
        return self.bend

    def SetCustomBendAllowance(self, bend):
        assert not self.UseDefaultBendAllowance
        self.bend = bend

    def AccessSelections(self, model, component):
        assert model is self.feature.model and component is None
        return not self.feature.access_failure

    def ReleaseSelectionAccess(self):
        self.feature.releases += 1


class BendFeature(FakeFeature):
    def __init__(self, model, name='Kenar-Flanş1', kind='EdgeFlange'):
        super().__init__(name, kind)
        self.model = model
        initial = dict(flags={member: False for member in ap.BEND_DEFAULTS[kind]},
                       radius=.0007, allowance=dict(Type=3, BendAllowance=.005,
                       KFactor=.2, BendDeduction=.003, BendTableFile='old.xls',
                       BendCalculationTableFile='calc.xls'), gauge=False, relief=42)
        self.states = {config: deepcopy(initial) for config in model.states}
        self.failure = self.ignore_flags = self.access_failure = False
        self.writes = self.releases = 0

    def GetDefinition(self):
        return BendDefinition(self)

    def GetErrorCode(self):
        return 0

    def ModifyDefinition(self, definition, model, component):
        assert model is self.model and component is None
        self.writes += 1
        data = self.states[model.config]
        if not self.ignore_flags:
            data['flags'] = {member: getattr(definition, member) for member in data['flags']}
        data.update(radius=definition.BendRadius, allowance=vars(definition.bend).copy(),
                    relief=definition.relief, gauge=definition.UseGaugeTable)
        if self.failure:
            self.failure = False
            return False
        return True


class PowerSmApplyTests(KApplyTestCase):
    def setUp(self):
        super().setUp()
        self.model.states['Other'] = dict(self.model.states['Default'], k=.5, radius=.003)
        self.model.parent_states = {name: dict(state, table='', calculation_table='')
                                    for name, state in self.model.states.items()}
        self.model.parent_writes = self.model.parent_reads = 0
        self.model.parent_gauge = self.model.parent_material = False
        self.model.ignore_radius_setter = True
        self.model.flags = {name: {0: False, 1: False} for name in self.model.states}
        self.model.displays = [RadiusDimension(self.model)]
        self.model.dimension_calls = []
        self.model.dimension_failure = False
        self.model.feature = ModernSheet(self.model)
        self.model.Extension.GetTemplateSheetMetal = lambda: ModernParent(self.model)
        self.bend = BendFeature(self.model)
        self.model.feature.child = self.bend

    def process(self, **kwargs):
        all_bends = kwargs.pop('all_bends', True)
        return ap.process_part(self.app, self.model.path, 'Default',
                               ManualAssignment('2', '0,274', '1,5', all_bends=all_bends), **kwargs)

    def snapshot(self):
        return deepcopy((self.model.parent_states, self.model.states,
                         self.model.flags, self.bend.states))

    def test_dimension_route_applies_when_definition_radius_setter_is_ignored(self):
        self.bend.states['Default']['flags'] = {member: True for member in self.bend.states['Default']['flags']}
        other = self.snapshot()
        self.model.ShowConfiguration2('Other')
        status, detail, _ = self.process(all_bends=False)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.parent_states['Default']['radius'], .0015)
        self.assertEqual(self.model.parent_states['Default']['k'], .274)
        self.assertEqual(self.model.states['Default']['thickness'], .002)
        self.assertTrue(all(self.bend.states['Default']['flags'].values()))
        self.assertEqual(self.bend.states['Default']['relief'], 42)
        self.assertEqual(self.model.dimension_calls, [(.0015, 1, 'Default', 'D1@SAC LEVHA@part')])
        self.assertEqual(self.model.config, 'Other')
        self.assertEqual(self.model.parent_states['Other'], other[0]['Other'])
        self.assertEqual(self.model.states['Other'], other[1]['Other'])
        self.assertEqual(self.bend.states['Other'], other[3]['Other'])
        self.assertIn('Yarıçap ölçüsü', detail)

    def test_preview_plans_custom_bends_without_changing_values_or_flags(self):
        before = self.snapshot()
        status, detail, _ = self.process(preview=True, save=True)
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.model.dimension_calls, [])
        self.assertEqual(self.bend.writes, 0)
        self.assertEqual(self.model.save_count, 0)
        self.assertIn('Kapsam: tüm bükümler', detail)

    def test_keep_custom_bends_mode_rejects_before_any_write(self):
        before = self.snapshot()
        status, detail, _ = self.process(all_bends=False)
        self.assertEqual(status, 'error', detail)
        self.assertIn('Tüm bükümlere uygula', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.snapshot(), before)

    def test_custom_sheet_values_are_inherited_without_changing_thickness(self):
        self.model.flags['Default'] = {0: True, 1: True}
        self.model.states['Default'].update(radius=.0008, type=3, ba=.005)
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.flags['Default'], {0: False, 1: False})
        self.assertEqual(self.model.states['Default']['thickness'], .002)
        self.assertEqual(self.model.states['Default']['radius'], .0015)
        self.assertEqual(self.model.states['Default']['k'], .274)

    def test_different_parent_body_thickness_is_blocked_before_write(self):
        self.model.flags['Default'][0] = True
        self.model.parent_states['Default']['thickness'] = .003
        before = self.snapshot()
        status, detail, _ = self.process()
        self.assertEqual(status, 'error', detail)
        self.assertIn('kalınlığıyla eşleşmedi', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.parent_writes, 0)

    def test_radius_write_failure_restores_k_and_r_without_saving(self):
        before = self.snapshot()
        self.model.dimension_failure = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('Yarıçap ölçüsü yazılamadı', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.save_count, 0)

    def test_partial_bend_failure_restores_custom_ba_radius_and_sheet_overrides(self):
        self.model.flags['Default'] = {0: True, 1: True}
        self.model.states['Default'].update(radius=.0008, type=3, ba=.005)
        second = BendFeature(self.model, 'Çizilmiş-Büküm1', 'SketchBend')
        self.bend.next = second
        before = self.snapshot(), deepcopy(second.states)
        second.failure = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertNotIn('GERİ ALMA HATASI', detail)
        self.assertEqual((self.snapshot(), second.states), before)
        self.assertEqual(self.model.save_count, 0)

    def test_silent_default_flag_failure_does_not_report_success(self):
        before = self.snapshot()
        self.bend.ignore_flags = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('büküm ayarları geri okumada eşleşmedi', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.save_count, 0)

    def test_dimension_selection_excludes_child_radius_and_diameter(self):
        self.model.displays.insert(0, RadiusDimension(self.model, 'Wrong', self.bend))
        self.model.displays.append(RadiusDimension(self.model, 'Diameter', kind=6))
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.model.dimension_calls[0][-1], 'D1@SAC LEVHA@part')

    def test_ambiguous_parent_radial_dimensions_do_not_write(self):
        self.model.displays.append(RadiusDimension(self.model, 'D2'))
        before = self.snapshot()
        status, detail, _ = self.process()
        self.assertEqual(status, 'error', detail)
        self.assertIn('birden fazla yarıçap ölçüsü', detail)
        self.assertEqual(self.model.parent_writes, 0)
        self.assertEqual(self.snapshot(), before)

    def test_hidden_radius_dimension_uses_definition_setter(self):
        self.model.displays = []
        self.model.ignore_radius_setter = False
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertIn('R atama yolu: Sac unsur tanımı', detail)
        self.assertEqual(self.model.parent_states['Default']['radius'], .0015)
        self.assertEqual(self.model.dimension_calls, [])

    def test_gauge_bound_custom_bend_is_rejected_without_mutation(self):
        self.bend.states['Default']['gauge'] = True
        before = self.snapshot()
        status, detail, _ = self.process()
        self.assertEqual(status, 'error', detail)
        self.assertIn('özel büküm ayarı sac kalınlık tablosuna bağlı', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.parent_writes, 0)

    def test_supported_bend_types_use_their_documented_default_flags(self):
        for kind in ('OneBend', 'SMMiteredFlange', 'Jog', 'ProcessBends', 'FlattenBends',
                     'Bends', 'SketchBend', 'SM3dBend', 'ToroidalBend', 'SweepFlange', 'SweptFlange', 'Hem'):
            with self.subTest(kind=kind):
                self.bend = BendFeature(self.model, kind, kind)
                self.model.feature.child = self.bend
                status, detail, _ = self.process()
                self.assertEqual(status, 'success', detail)
                self.assertTrue(all(self.bend.states['Default']['flags'].values()))

    def test_save_failure_restores_bend_modes_and_original_custom_table(self):
        self.bend.states['Default']['allowance']['Type'] = 5
        before = self.snapshot()
        self.model.save_fail = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual(self.snapshot(), before)

    def test_bend_access_failure_rolls_back_parent_and_radius(self):
        before = self.snapshot()
        self.bend.access_failure = True
        status, detail, _ = self.process()
        self.assertEqual(status, 'error', detail)
        self.assertIn('büküm seçim erişimi alınamadı', detail)
        self.assertEqual(self.snapshot(), before)

    def test_bend_flag_propagation_to_other_configuration_is_detected_and_restored(self):
        before = self.snapshot()
        original = self.bend.ModifyDefinition
        leaked = False
        def propagate_once(definition, model, component):
            nonlocal leaked
            result = original(definition, model, component)
            if not leaked and all(self.bend.states['Default']['flags'].values()):
                self.bend.states['Other']['flags'] = deepcopy(self.bend.states['Default']['flags'])
                leaked = True
            return result
        self.bend.ModifyDefinition = propagate_once
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('başka konfigürasyona yayıldı (Other)', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.model.save_count, 0)

