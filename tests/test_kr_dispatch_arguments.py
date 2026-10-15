"""Native COM argument contracts for part-context feature editing.

Python None becomes VT_NULL in pywin32. SolidWorks expects an IDispatch null
for the Component argument of AccessSelections and ModifyDefinition.
"""

from copy import deepcopy

from k_factor import apply as ap
from k_factor.rules import ManualAssignment
from support.fixtures import KApplyTestCase
from support.solidworks import Variant
from test_converted_k_radius import ConvertedFeature
from test_power_sm_k_radius import BendFeature


class DispatchTypeMismatch(Exception):
    hresult = -2147352571

    def __str__(self):
        return "(-2147352571, 'Tür uyuşmazlığı.', None, 2)"


def checked_component_call(call, calls, name):
    def invoke(*args):
        component = args[-1]
        if not isinstance(component, Variant) or component.kind != 9 or component.value is not None:
            raise DispatchTypeMismatch()
        calls.append(name)
        return call(*args[:-1], None)
    return invoke


def dispatch_feature(feature, calls):
    """Keep real feature state doubles, but enforce native dispatch arguments."""
    original = feature.GetDefinition
    feature._oleobj_ = object()

    def definition():
        data = original()
        data._oleobj_ = object()
        data.AccessSelections = checked_component_call(data.AccessSelections, calls, 'AccessSelections')
        return data

    feature.GetDefinition = definition
    feature.ModifyDefinition = checked_component_call(feature.ModifyDefinition, calls, 'ModifyDefinition')
    return feature


class DispatchArgumentTests(KApplyTestCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.sheet = dispatch_feature(self.model.feature, self.calls)
        self.bend = dispatch_feature(BendFeature(self.model), self.calls)
        self.sheet.child = self.bend
        self.recipe = ManualAssignment(2, .274, 2, all_bends=True)

    def process(self, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default', self.recipe, **kwargs)

    def test_legacy_sheet_and_custom_bend_receive_dispatch_null(self):
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        state = self.model.states['Default']
        self.assertEqual((state['k'], state['radius'], state['thickness']), (.274, .002, .002))
        self.assertTrue(all(self.bend.states['Default']['flags'].values()))
        self.assertGreaterEqual(self.calls.count('AccessSelections'), 2)
        self.assertEqual(self.calls.count('AccessSelections'), self.calls.count('ModifyDefinition'))
        self.sheet._FlagAsMethod.assert_any_call('ModifyDefinition')
        self.bend._FlagAsMethod.assert_any_call('ModifyDefinition')

    def test_readback_failure_restores_sheet_and_custom_bend_with_typed_null(self):
        before = deepcopy(self.model.states), deepcopy(self.bend.states)
        self.model.readback_fail = True
        status, detail, _ = self.process(save=True)
        self.assertEqual(status, 'error', detail)
        self.assertIn('geri yüklendi ve kontrol edildi', detail)
        self.assertNotIn('GERİ ALMA HATASI', detail)
        self.assertEqual((self.model.states, self.bend.states), before)
        self.assertEqual(self.model.save_count, 0)
        self.assertTrue(detail.startswith('K/R geri okuma ve konfigürasyon doğrulaması:'), detail)

    def test_converted_sheet_override_edit_uses_dispatch_null(self):
        calls = self.calls

        class DispatchConverted(ConvertedFeature):
            _oleobj_ = object()

            @property
            def GetDefinition(self):
                data = super().GetDefinition
                data.AccessSelections = checked_component_call(data.AccessSelections, calls, 'Converted.AccessSelections')
                return data

            def ModifyDefinition(self, *args):
                return checked_component_call(super().ModifyDefinition, calls, 'Converted.ModifyDefinition')(*args)

        converted = DispatchConverted(self.model)
        converted.flags = dict.fromkeys(converted.flags, True)
        self.bend.next = converted
        status, detail, _ = self.process()
        self.assertEqual(status, 'success', detail)
        self.assertEqual(tuple(converted.flags.values()), (False, False))
        self.assertIn('Converted.AccessSelections', calls)
        self.assertIn('Converted.ModifyDefinition', calls)
