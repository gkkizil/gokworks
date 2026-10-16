"""Packaging-critical flow checks, no native SolidWorks claims."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from k_factor.standalone.desktop_controller import ComparisonFailure, run_pair
from k_factor.standalone import runtime


def native_report(mode):
    before = dict(feature_name="Sac-Levha", feature_type="TemplateSheetMetal", thickness_mm=2.0,
                  k_factor=0.33, radius_mm=2.0, bend_allowance_type=2)
    after = dict(before, k_factor=0.274, radius_mm=1.5) if mode == "verify" else before.copy()
    return dict(schema_version=1, engine="csharp", status="verified" if mode == "verify" else "inspected",
                error=None, warnings=[], document_path=r"C:\işler\üst.sldprt", configuration="Varsayılan",
                before=before, after=after, assignment=dict(thickness_mm=2.0, k_factor=0.274, radius_mm=1.5),
                rollback=dict(status="restored_after_verification", attempted=True, verified=True, restored_state=before))


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.backend = self.folder / "native.exe"
        self.backend.write_bytes(b"fake")
        self.request = dict(schema_version=1, mode="verify", assignments=[dict(thickness_mm=2.0, k_factor=0.274, radius_mm=1.5)])

    def native(self, report):
        def run(args, **kwargs):
            Path(args[args.index("--report") + 1]).write_text(json.dumps(report), encoding="utf-8")
            return SimpleNamespace(returncode=0 if report["status"] != "error" else 2, stdout="", stderr="")
        return run

    def test_verification_runs_python_only_after_csharp_restored_and_binds_document(self):
        report = native_report("verify")
        python = Mock(return_value=dict(deepcopy(report), engine="python"))
        result = run_pair(self.request, self.folder, native_runner=self.native(report), python_runner=python, backend=self.backend)
        self.assertEqual(result["comparison"]["status"], "verified_match")
        self.assertEqual(python.call_args.args[0]["document_path"], report["document_path"])
        self.assertEqual(python.call_args.args[0]["feature_name"], "Sac-Levha")
        self.assertTrue((self.folder / "comparison.json").exists())

    def test_native_failure_or_unverified_restoration_prevents_python(self):
        for failed in (True, False):
            with self.subTest(failed=failed):
                report = native_report("verify")
                if failed:
                    report.update(status="error", error="AccessSelections failed")
                else:
                    report["rollback"]["verified"] = False
                python = Mock()
                with self.assertRaises(ComparisonFailure):
                    run_pair(self.request, self.folder, native_runner=self.native(report), python_runner=python, backend=self.backend)
                python.assert_not_called()

    def test_python_rollback_failure_is_visible_to_desktop_user(self):
        report = native_report("verify")
        python = dict(deepcopy(report), engine="python", status="error", error="Readback mismatch")
        python["rollback"]["verified"] = False
        with self.assertRaisesRegex(ComparisonFailure, "Parçayı kaydetmeyin"):
            run_pair(self.request, self.folder, native_runner=self.native(report), python_runner=lambda request: python, backend=self.backend)

    def test_missing_helper_or_persistent_apply_never_starts_any_motor(self):
        run = Mock()
        for request, helper in ((self.request, self.folder / "missing.exe"), (dict(self.request, mode="apply"), self.backend)):
            with self.assertRaises(ComparisonFailure):
                run_pair(request, self.folder, native_runner=run, backend=helper)
        run.assert_not_called()

    def test_inspection_does_not_claim_write_verification(self):
        report = native_report("inspect")
        result = run_pair(dict(schema_version=1, mode="inspect"), self.folder,
                          native_runner=self.native(report), python_runner=lambda request: dict(report, engine="python"), backend=self.backend)
        self.assertEqual(result["comparison"]["status"], "inspection_match")


class FrozenCacheTests(unittest.TestCase):
    def test_frozen_typelib_generation_uses_persistent_user_path_and_initializes_once(self):
        with TemporaryDirectory() as directory:
            win32com, gen_py, client = (ModuleType(name) for name in ("win32com", "win32com.gen_py", "win32com.client"))
            win32com.gen_py, win32com.client = gen_py, client
            win32com.__gen_path__ = "bundle"
            def initialize():
                cache = Path(win32com.__gen_path__)
                (cache / "__init__.py").write_text("", encoding="utf-8")
            client.gencache = SimpleNamespace(is_readonly=True, is_zip=True, GetGeneratePath=Mock(side_effect=initialize), Rebuild=Mock())
            with patch.dict(sys.modules, {"win32com": win32com, "win32com.gen_py": gen_py, "win32com.client": client}), \
                 patch.object(sys, "frozen", True, create=True), patch.dict("os.environ", LOCALAPPDATA=directory), \
                 patch.object(runtime, "_configured_cache", None):
                first, second = runtime.prepare_generated_cache(), runtime.prepare_generated_cache()
                self.assertEqual(first, second)
                self.assertTrue(first.is_relative_to(Path(directory)))
                self.assertEqual(gen_py.__path__, [str(first)])
                self.assertFalse(client.gencache.is_readonly)
                self.assertFalse(client.gencache.is_zip)
                client.gencache.Rebuild.assert_called_once_with(verbose=0)


if __name__ == "__main__":
    unittest.main()
