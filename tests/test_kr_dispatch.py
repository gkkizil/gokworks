"""Regressions for callable COM return objects and inactive allowance members."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from k_factor import apply as ap
from k_factor.rules import ManualAssignment
import test_k_factor as fixtures
from test_k_factor import Definition, SheetFeature


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
    fields = {'KFactor': 2, 'BendAllowance': 3, 'BendDeduction': 4, 'BendTableFile': (1, 5)}

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


class NativeDispatchApplyTests(unittest.TestCase):
    setUp = fixtures.ApplyTests.setUp

    def manual(self, **kwargs):
        return ap.process_part(self.app, self.model.path, 'Default',
                               ManualAssignment(2, .274, 2), **kwargs)

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


if __name__ == '__main__':
    unittest.main()
