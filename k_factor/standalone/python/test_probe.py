"""Focused transaction tests; generated-style fakes, never production fallbacks."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from .probe import EarlyBound, ProbeError, execute, report_template, validate_request, Trace, load_request


NULL_COMPONENT = object()
EMPTY_CONFIGURATIONS = object()


class FakeAllowance:
    def __init__(self, state):
        self.Type = state["type"]
        self.KFactor = state["k"]
        self.BendAllowance = state["allowance"]
        self.BendDeduction = state["deduction"]
        self.BendTableFile = state["table"]


class FakeData:
    def __init__(self, feature):
        self.feature = feature
        self.state = deepcopy(feature.model.state)
        self.Thickness = self.state["thickness"]
        self.BendRadius = self.state["radius"]
        self.allowance = FakeAllowance(self.state)

    def GetCustomBendAllowance(self):
        return deepcopy(self.allowance)

    def SetCustomBendAllowance(self, allowance):
        self.allowance = deepcopy(allowance)

    def GetUseGaugeTable(self):
        model = self.feature.model
        # A generated wrapper supplies the out arguments; the test deliberately
        # accepts zero input args and returns retval first, followed by OUTs.
        return model.gauge_code, model.gauge_used, model.gauge_file

    @property
    def UseMaterialSheetMetalParameters(self):
        model = self.feature.model
        model.material_reads += 1
        if model.gauge_code != 0 or model.gauge_used:
            raise AssertionError("Material property must not be queried when gauge outputs invalid/used")
        return model.material_used

    def AccessSelections(self, model, component):
        if model is not self.feature.model or component is not NULL_COMPONENT:
            raise AssertionError("AccessSelections requires active model and typed dispatch null")
        model.selection_accesses += 1
        return True

    def ReleaseSelectionAccess(self):
        self.feature.model.selection_releases += 1
        if getattr(self.feature.model, "fail_selection_release", False):
            raise RuntimeError("Selection release failed")


class FakeDimension:
    def __init__(self, feature, name="R@Sac-Levha", own=True):
        self.feature, self.FullName, self.own = feature, name, own

    def GetFeatureOwner(self):
        return self.feature if self.own else self.feature.model.other_feature

    def GetSystemValue3(self, configuration, names):
        if configuration != 1 or names is not EMPTY_CONFIGURATIONS:
            raise AssertionError("Dimension read must only target the active configuration")
        return (self.feature.model.state["radius"],)

    def SetSystemValue3(self, value, configuration, names):
        if configuration != 1 or names is not EMPTY_CONFIGURATIONS:
            raise AssertionError("Dimension must only target the active configuration")
        self.feature.model.state["radius"] = value
        self.feature.model.dimension_writes += 1
        return 0


class FakeDisplay:
    Type2 = 5

    def __init__(self, dimension):
        self.dimension = dimension

    def GetDimension2(self, index):
        if index != 0:
            raise AssertionError("GetDimension2 must use index 0")
        return self.dimension


class FakeFeature:
    def __init__(self, model, name="Sac-Levha", kind="TemplateSheetMetal"):
        self.model, self.Name, self.kind = model, name, kind
        self.dimensions = []

    def GetTypeName2(self):
        return self.kind

    def IsSuppressed2(self, configuration, names):
        if configuration != 1 or names is not None:
            raise AssertionError("Suppression must use current configuration")
        return (False,)

    def GetFirstSubFeature(self):
        return None

    def GetNextSubFeature(self):
        return None

    def GetNextFeature(self):
        return None

    def GetDefinition(self):
        return FakeData(self)

    def GetFirstDisplayDimension(self):
        return self.dimensions[0] if self.dimensions else None

    def GetNextDisplayDimension(self, display):
        index = self.dimensions.index(display) + 1
        return self.dimensions[index] if index < len(self.dimensions) else None

    def ModifyDefinition(self, data, model, component):
        if model is not self.model or component is not NULL_COMPONENT:
            raise AssertionError("ModifyDefinition requires active model and typed dispatch null")
        self.model.modifications += 1
        state = self.model.state
        allowance = data.allowance
        state.update(thickness=data.Thickness, radius=data.BendRadius, type=allowance.Type,
                     k=allowance.KFactor, allowance=allowance.BendAllowance,
                     deduction=allowance.BendDeduction, table=allowance.BendTableFile)
        if self.model.modifications == 1:
            if self.model.corrupt_first_readback:
                state["k"] = 0.99
            if self.model.change_thickness:
                state["thickness"] += 0.001
            if self.model.reject_first_write:
                return False
        return True

    def GetErrorCode2(self):
        return ((17, False) if self.model.feature_error_first and self.model.modifications == 1 else (0, False))


class FakeModel:
    def __init__(self):
        self.path = r"C:\test\part.SLDPRT"
        self.configuration = "Varsayılan"
        self.state = {"type": 2, "k": 0.33, "thickness": 0.002, "radius": 0.002,
                      "allowance": 0.006, "deduction": 0.003, "table": "table.xls"}
        self.initial = deepcopy(self.state)
        self.gauge_code, self.gauge_used, self.gauge_file = 0, False, ""
        self.material_used = False
        self.material_reads = self.modifications = self.rebuilds = 0
        self.selection_accesses = self.selection_releases = self.dimension_writes = 0
        self.reject_first_write = self.corrupt_first_readback = self.change_thickness = False
        self.feature_error_first = self.fail_rebuild_first = False
        self.feature = FakeFeature(self)
        self.other_feature = FakeFeature(self, "Unrelated", "Sketch")
        self.Extension = SimpleNamespace(GetTemplateSheetMetal=lambda: self.feature)
        self.FeatureManager = SimpleNamespace(GetSheetMetalFolder=lambda: None)

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name=self.configuration))

    def GetType(self):
        return 1

    def GetPathName(self):
        return self.path

    def FirstFeature(self):
        return self.feature

    def EditRebuild3(self):
        self.rebuilds += 1
        return not (self.fail_rebuild_first and self.rebuilds == 1)


class FakeBinding:
    null_component = NULL_COMPONENT
    empty_configurations = EMPTY_CONFIGURATIONS

    def cast(self, obj, interface):
        if obj is None:
            raise ProbeError("NULL interface")
        return obj


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.request = {"schema_version": 1, "mode": "verify", "document_path": self.model.path,
                        "assignments": [{"thickness_mm": 2, "k_factor": 0.274, "radius_mm": 1.5}]}

    def run_probe(self, **changes):
        request = dict(self.request, **changes)
        return execute(request, lambda trace: (SimpleNamespace(ActiveDoc=self.model), FakeBinding(), lambda: None))

    def test_inspect_never_mutates(self):
        report = self.run_probe(mode="inspect")
        self.assertEqual(report["status"], "inspected")
        self.assertEqual(self.model.modifications, 0)
        self.assertEqual(self.model.state, self.model.initial)

    def test_verify_changes_readback_then_restores(self):
        report = self.run_probe()
        self.assertEqual(report["status"], "verified", report["error"])
        self.assertEqual(report["after"]["k_factor"], 0.274)
        self.assertEqual(report["after"]["radius_mm"], 1.5)
        self.assertEqual(report["rollback"]["status"], "restored_after_verification")
        self.assertEqual(self.model.modifications, 2)
        self.assertEqual(self.model.state, self.model.initial)

    def test_apply_leaves_verified_edits_unsaved(self):
        report = self.run_probe(mode="apply")
        self.assertEqual(report["status"], "applied", report["error"])
        self.assertFalse(report["files_saved"])
        self.assertEqual(self.model.state["k"], 0.274)
        self.assertEqual(self.model.state["radius"], 0.0015)
        self.assertEqual(report["rollback"]["status"], "not_needed")

    def test_failed_modify_may_have_mutated_and_is_restored(self):
        self.model.reject_first_write = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertIn("ModifyDefinition", report["error"])
        self.assertTrue(report["rollback"]["verified"])
        self.assertEqual(self.model.state, self.model.initial)
        self.assertEqual(self.model.selection_releases, 1)

    def test_selection_cleanup_failure_preserves_original_write_error(self):
        self.model.reject_first_write = self.model.fail_selection_release = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertIn("ModifyDefinition", report["error"])
        self.assertTrue(any("ReleaseSelectionAccess" in warning for warning in report["warnings"]))
        self.assertTrue(report["rollback"]["verified"])
        self.assertEqual(self.model.state, self.model.initial)

    def test_wrong_readback_is_error_and_restores(self):
        self.model.corrupt_first_readback = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertTrue(report["rollback"]["verified"])
        self.assertEqual(self.model.state, self.model.initial)

    def test_thickness_change_detected_and_restoration_failure_reported(self):
        self.model.change_thickness = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["rollback"]["status"], "failed")
        self.assertIn("DO NOT SAVE", report["rollback"]["error"])

    def test_rebuild_failure_rolls_back(self):
        self.model.fail_rebuild_first = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["rollback"]["status"], "restored_after_error")
        self.assertEqual(self.model.state, self.model.initial)

    def test_feature_rebuild_error_rejects_successful_modify(self):
        self.model.feature_error_first = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertIn("Feature rebuild error", report["error"])
        self.assertTrue(report["rollback"]["verified"])

    def test_gauge2_inspect_reports_unavailable_without_material_read(self):
        self.model.gauge_code = 2
        report = self.run_probe(mode="inspect")
        self.assertEqual(report["status"], "inspected")
        controls = report["features"][0]["controls"]
        self.assertEqual(controls["gauge_status_name"], "NotEnabledOnTemplate")
        self.assertIsNone(controls["use_gauge_table"])
        self.assertEqual(self.model.material_reads, 0)

    def test_gauge2_verify_temporarily_writes_but_apply_blocked(self):
        self.model.gauge_code = 2
        report = self.run_probe()
        self.assertEqual(report["status"], "verified", report["error"])
        self.assertTrue(report["warnings"])
        self.assertEqual(self.model.state, self.model.initial)
        report = self.run_probe(mode="apply")
        self.assertEqual(report["status"], "error")
        self.assertEqual(self.model.modifications, 2)

    def test_active_controls_block_without_mutation(self):
        for control in ("gauge_used", "material_used"):
            with self.subTest(control=control):
                setattr(self.model, control, True)
                report = self.run_probe()
                self.assertEqual(report["status"], "error")
                self.assertEqual(self.model.modifications, 0)
                setattr(self.model, control, False)

    def test_disabled_gauge_table_accepts_null_filename_but_enabled_table_still_blocks(self):
        self.model.gauge_file = None  # NULL BSTR is valid when UseGaugeTable is false.
        report = self.run_probe()
        self.assertEqual(report["status"], "verified", report["error"])
        self.assertTrue(report["rollback"]["verified"])
        self.assertGreater(self.model.material_reads, 0)
        writes = self.model.modifications
        self.model.gauge_used = True
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertEqual(self.model.modifications, writes)

    def test_restore_non_k_allowance_payload(self):
        for kind, key in ((1, "table"), (3, "allowance"), (4, "deduction")):
            with self.subTest(kind=kind):
                self.model.state["type"] = kind
                expected = self.model.state[key]
                report = self.run_probe()
                self.assertEqual(report["status"], "verified", report["error"])
                self.assertEqual(self.model.state["type"], kind)
                self.assertEqual(self.model.state[key], expected)

    def test_unsupported_allowance_type_can_be_inspected_but_not_modified(self):
        self.model.state["type"] = 5
        self.assertEqual(self.run_probe(mode="inspect")["status"], "inspected")
        result = self.run_probe()
        self.assertEqual(result["status"], "error")
        self.assertIn("rollback", result["error"])
        self.assertEqual(self.model.modifications, 0)

    def test_owned_radial_dimension_uses_active_configuration_and_restores(self):
        self.model.feature.dimensions = [FakeDisplay(FakeDimension(self.model.feature))]
        report = self.run_probe()
        self.assertEqual(report["status"], "verified", report["error"])
        self.assertEqual(report["radius_method"], "owned_radial_dimension")
        self.assertEqual(self.model.dimension_writes, 2)
        self.assertEqual(self.model.state, self.model.initial)

    def test_unrelated_radial_dimension_is_not_written(self):
        self.model.feature.dimensions = [FakeDisplay(FakeDimension(self.model.feature, own=False))]
        report = self.run_probe()
        self.assertEqual(report["status"], "verified", report["error"])
        self.assertEqual(report["radius_method"], "bend_radius_definition")
        self.assertEqual(self.model.dimension_writes, 0)

    def test_root_owned_radial_must_match_bend_radius_before_any_mutation(self):
        dimension = FakeDimension(self.model.feature, "OtherRadius@Sac-Levha")
        dimension.GetSystemValue3 = lambda *args: (0.005,)
        self.model.feature.dimensions = [FakeDisplay(dimension)]
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertIn("does not match", report["error"])
        self.assertEqual(self.model.modifications, 0)
        self.assertEqual(self.model.dimension_writes, 0)
        self.assertFalse(report["rollback"]["attempted"])

    def test_ambiguous_radial_dimensions_prevent_mutation(self):
        self.model.feature.dimensions = [FakeDisplay(FakeDimension(self.model.feature, name)) for name in ("r1", "r2")]
        report = self.run_probe()
        self.assertEqual(report["status"], "error")
        self.assertEqual(self.model.modifications, 0)

    def test_path_mismatch_prevents_mutation(self):
        report = self.run_probe(document_path=r"C:\other.SLDPRT")
        self.assertEqual(report["status"], "error")
        self.assertEqual(self.model.modifications, 0)

    def test_selected_configuration_change_prevents_mutation(self):
        report = self.run_probe(configuration="Another configuration")
        self.assertEqual(report["status"], "error")
        self.assertIn("configuration", report["error"])
        self.assertEqual(self.model.modifications, 0)
        self.assertEqual(self.model.selection_accesses, 0)

    def test_parameters_changed_since_inspect_prevent_mutation(self):
        snapshot = self.run_probe(mode="inspect")["before"]
        self.model.state["k"] = 0.42
        report = self.run_probe(expected_state=snapshot)
        self.assertEqual(report["status"], "error")
        self.assertIn("changed since", report["error"])
        self.assertEqual(self.model.modifications, 0)
        self.assertEqual(self.model.selection_accesses, 0)

    def test_unmatched_thickness_skips(self):
        report = self.run_probe(assignments=[{"thickness_mm": 1.5, "k_factor": 0.274, "radius_mm": 1.5}])
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(self.model.modifications, 0)

    def test_strict_numbers_and_overlapping_matching_windows(self):
        for bad in (True, "2", float("nan"), float("inf")):
            request = dict(self.request, assignments=[{"thickness_mm": bad, "k_factor": 0.2, "radius_mm": 1}])
            with self.subTest(bad=bad), self.assertRaises(ProbeError):
                validate_request(request)
        rows = [{"thickness_mm": value, "k_factor": 0.2, "radius_mm": 1} for value in (2, 2.01)]
        with self.assertRaises(ProbeError):
            validate_request(dict(self.request, assignments=rows))

    def test_real_binding_requires_declared_typelib_interface(self):
        casts = []
        client = SimpleNamespace(VARIANT=lambda kind, value: (kind, value))
        module = SimpleNamespace(NamesToIIDMap={"ISheetMetalFeatureData": "iid"},
                                 ISheetMetalFeatureData=lambda obj: casts.append(obj) or obj)
        module.ISheetMetalFeatureData.CLSID = "iid"
        queries = []
        data = SimpleNamespace()
        data.QueryInterface = lambda iid, wrapper: queries.append((iid, wrapper)) or data
        binding = EarlyBound(client, SimpleNamespace(VT_DISPATCH=9, VT_ARRAY=8192, VT_BSTR=8, IID_IDispatch="dispatch"), module, Trace(report_template()))
        self.assertIs(binding.cast(data, "ISheetMetalFeatureData"), data)
        self.assertEqual(casts, [data])
        dynamic_wrapper = SimpleNamespace(_oleobj_=data)
        self.assertIs(binding.cast(dynamic_wrapper, "ISheetMetalFeatureData"), data)
        self.assertEqual(casts[-1], data)
        self.assertEqual(queries, [("iid", "dispatch"), ("iid", "dispatch")])
        self.assertEqual(binding.null_component, (9, None))
        self.assertEqual(binding.empty_configurations, (8200, ()))
        with self.assertRaises(ProbeError):
            binding.cast(data, "IGuessedInterface")

    def test_coclass_alias_queries_default_interface_and_wrong_interface_fails(self):
        queries, constructions = [], []
        def interface(raw):
            constructions.append(raw)
            return raw
        interface.CLSID = "interface-iid"
        module = SimpleNamespace(NamesToIIDMap={"SheetMetalFeatureData": "coclass-clsid"},
                                 SheetMetalFeatureData=SimpleNamespace(default_interface=interface))
        client = SimpleNamespace(VARIANT=lambda kind, value: (kind, value))
        com = SimpleNamespace(VT_DISPATCH=9, VT_ARRAY=8192, VT_BSTR=8, IID_IDispatch="dispatch")
        data = SimpleNamespace()
        data.QueryInterface = lambda iid, wrapper: queries.append((iid, wrapper)) or data
        binding = EarlyBound(client, com, module, Trace(report_template()))
        self.assertIs(binding.cast(data, "ISheetMetalFeatureData"), data)
        self.assertEqual(queries, [("interface-iid", "dispatch")])
        def reject(*args):
            raise RuntimeError("E_NOINTERFACE")
        data.QueryInterface = reject
        with self.assertRaisesRegex(RuntimeError, "E_NOINTERFACE"):
            binding.cast(data, "ISheetMetalFeatureData")
        self.assertEqual(len(constructions), 1)

    def test_strict_contract_rejects_unknown_duplicate_keys_and_zero_tolerance(self):
        for changes in ({"tolerance_mm": 0}, {"typo": 1}, {"document_path": "assembly.SLDASM"}):
            with self.subTest(changes=changes), self.assertRaises(ProbeError):
                validate_request(dict(self.request, **changes))
        with self.assertRaises(ProbeError):
            load_request('{"schema_version":1,"schema_version":1}')
        self.assertEqual(validate_request({"schema_version": 1})["mode"], "inspect")


if __name__ == "__main__":
    unittest.main()
