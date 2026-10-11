"""Convert-to-sheet-metal COM contract regressions, not native SW geometry tests.

The documented feature type is SolidToSheetMetal. Its definition has
SheetThickness (not Thickness), two parent override flags, and no
SetCustomBendAllowance. These doubles deliberately expose that interface.
"""

from copy import deepcopy
from types import SimpleNamespace

from k_factor import apply as ap
from k_factor.rules import ManualAssignment, Recipe
from support.fixtures import KApplyTestCase
from support.solidworks import FakeFeature


class Dispatch(SimpleNamespace):
    _oleobj_ = object()

    def __call__(self):
        raise AssertionError('Do not invoke a returned COM default member.')


class ConvertedDefinition(Dispatch):
    @property
    def OverrideBendRadius(self):
        raise AssertionError('This gauge property is only valid before feature creation.')


class ConvertedFeature(FakeFeature):
    def __init__(self, model):
        super().__init__('Katıyı-Saca-Dönüştür1', 'SolidToSheetMetal')
        self.model = model
        self.initial = deepcopy(model.states)
        self.flags = dict(OverrideDefaultSheetMetalParameters=False,
                          OverrideDefaultBendAllowanceParameters=False)
        self.freeze = None
        self.error_on_change = self.suppress_on_change = self.leak = False
        self.drift_thickness = self.missing_on_change = False

    @property
    def changed(self):
        states = deepcopy(self.model.states)
        for config, state in states.items():
            if state['type'] != 2:
                # Cached K is inactive when the direct BA mode is restored.
                state['k'] = self.initial[config]['k']
        return states != self.initial

    @property
    def GetDefinition(self):
        if self.missing_on_change and self.changed:
            return None
        state = deepcopy(self.model.states[self.model.config])
        if self.freeze:
            state[self.freeze] = self.initial[self.model.config][self.freeze]
        if self.drift_thickness and self.changed:
            state['thickness'] += .0001
        if self.leak and self.changed and self.model.config == 'Other':
            state['k'] = self.model.states['Default']['k']
        return ConvertedDefinition(**self.flags, SheetThickness=state['thickness'],
                        BendRadius=state['radius'], GetCustomBendAllowance=Dispatch(
                            Type=state['type'], KFactor=state['k'], BendAllowance=state['ba'],
                            BendDeduction=state['bd'], BendTableFile=''))

    def GetErrorCode(self):
        return 1 if self.error_on_change and self.changed else 0

    def IsSuppressed2(self, scope, configurations):
        return (self.suppress_on_change and self.changed,)


class ConvertedApplyTests(KApplyTestCase):
    def setUp(self):
        super().setUp()
        self.model.states['Default'].update(thickness=.0015, radius=.0005, k=.5)
        self.converted = ConvertedFeature(self.model)
        self.model.feature.next = self.converted

    def process(self, recipe=None, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default',
                               recipe or ManualAssignment('1,5', '0,274', '1,5'), **kwargs)

    def test_inherited_conversion_preview_and_manual_or_calculated_apply(self):
        for recipe in (ManualAssignment('1,5', '0,274', '1,5'), Recipe()):
            with self.subTest(recipe=recipe):
                # Check both top-level and nested feature traversal.
                self.model.feature.next = self.converted if isinstance(recipe, ManualAssignment) else None
                self.model.feature.child = None if isinstance(recipe, ManualAssignment) else self.converted
                self.model.states = deepcopy(self.converted.initial)
                self.model.feature.modify_count = self.model.save_count = 0
                status, detail, _ = self.process(recipe, preview=True, save=True)
                self.assertEqual(status, 'success', detail)
                self.assertEqual(self.model.states, self.converted.initial)
                self.assertEqual(self.model.feature.modify_count, 0)
                self.assertEqual(self.model.save_count, 0)
                status, detail, result = self.process(recipe, save=True)
                self.assertEqual(status, 'success', detail)
                converted = self.converted.GetDefinition
                self.assertAlmostEqual(converted.BendRadius, result.radius_mm / 1000)
                self.assertEqual(converted.GetCustomBendAllowance.KFactor, result.k_factor)
                self.assertEqual(converted.GetCustomBendAllowance.Type, 2)
                self.assertEqual(converted.SheetThickness, .0015)
                self.assertIn('Katıyı Saca Dönüştür: 1 unsurda', detail)
                self.assertEqual(self.model.save_count, 1)

    def test_conversion_overrides_are_rejected_before_preview_or_apply(self):
        for flag in self.converted.flags:
            for preview in (True, False):
                with self.subTest(flag=flag, preview=preview):
                    self.converted.flags[flag] = True
                    status, detail, _ = self.process(preview=preview, save=True)
                    self.assertEqual(status, 'error', detail)
                    self.assertIn(flag, detail)
                    self.assertIn(self.converted.Name, detail)
                    self.assertEqual(self.model.feature.modify_count, 0)
                    self.assertEqual(self.model.save_count, 0)
                    self.assertEqual(self.model.states, self.converted.initial)
                    self.converted.flags[flag] = False

    def test_stale_conversion_values_and_feature_errors_roll_back_without_save(self):
        baseline = deepcopy(self.model.states)
        for failure in ('k', 'radius', 'thickness', 'type', 'error', 'suppression', 'definition'):
            with self.subTest(failure=failure):
                self.model.states = deepcopy(baseline)
                # A direct BA must be replaced with Type=2 in the conversion too.
                self.model.states['Default']['type'] = 3
                self.converted = ConvertedFeature(self.model)
                self.model.feature.next = self.converted
                self.model.feature.modify_count = 0
                self.converted.freeze = failure if failure in ('k', 'radius', 'type') else None
                self.converted.error_on_change = failure == 'error'
                self.converted.suppress_on_change = failure == 'suppression'
                self.converted.drift_thickness = failure == 'thickness'
                self.converted.missing_on_change = failure == 'definition'
                before = deepcopy(self.model.states)
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
                self.assertIn('unsur tanımı okunamadı' if failure == 'definition' else 'dönüşüm doğrulanamadı', detail)
                restored = deepcopy(self.model.states)
                restored['Default'].pop('k')  # Inactive in restored BA mode.
                before['Default'].pop('k')
                self.assertEqual(restored, before)
                self.assertEqual(self.model.save_count, 0)
                self.assertIn('geri yüklendi', detail)
                self.assertNotIn('GERİ ALMA HATASI', detail)

    def test_converted_values_in_other_configuration_are_also_protected(self):
        self.model.states['Other'] = dict(self.model.states['Default'], k=.4)
        self.converted = ConvertedFeature(self.model)
        self.model.feature.next = self.converted
        self.converted.leak = True
        self.model.ShowConfiguration2('Other')
        before = deepcopy(self.model.states)
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('başka konfigürasyona', detail)
        self.assertIn('geri yüklendi', detail)
        self.assertEqual(self.model.states, before)
        self.assertEqual(self.model.config, 'Other')
        self.assertEqual(self.model.save_count, 0)

    def test_missing_conversion_contract_fails_and_wrong_thickness_skips(self):
        attribute = 'OverrideDefaultBendAllowanceParameters'
        self.converted.flags[attribute] = None
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    del self.converted.flags[attribute]
                status, detail, _ = self.process(save=True)
                self.assertEqual(status, 'error', detail)
                self.assertIn(attribute, detail)
        status, detail, _ = self.process(ManualAssignment(2, .274, 2), save=True)
        self.assertEqual(status, 'skipped', detail)
        self.assertEqual(self.model.feature.modify_count, 0)
        self.assertEqual(self.model.save_count, 0)
