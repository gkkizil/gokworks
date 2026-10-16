"""Acceptance checks for false-positive native parity claims."""

from copy import deepcopy
import unittest

from k_factor.standalone.compare_reports import compare


def reports():
    before = dict(feature_name="Sac-Levha", feature_type="TemplateSheetMetal", thickness_mm=2.0,
                  k_factor=0.274, radius_mm=2.0, bend_allowance_type=2)
    after = {**before, "k_factor": 0.31, "radius_mm": 1.8}
    base = dict(schema_version=1, status="verified", error=None, document_path="C:\\işler\\üst.sldprt",
                configuration="Varsayılan", before=before, after=after,
                assignment=dict(thickness_mm=2.0, k_factor=0.31, radius_mm=1.8),
                rollback=dict(status="restored_after_verification", verified=True, restored_state=before))
    return [{**deepcopy(base), "engine": engine} for engine in ("csharp", "python")]


class NativeComparisonTests(unittest.TestCase):
    def test_verified_target_and_restoration_match(self):
        self.assertEqual(compare(*reports())["status"], "verified_match")

    def test_same_api_errors_do_not_count_as_matching_implementations(self):
        left, right = reports()
        left["status"] = right["status"] = "error"
        self.assertEqual(compare(left, right)["status"], "not_verified")

    def test_original_allowance_mode_and_payload_must_be_restored(self):
        left, right = reports()
        for report in (left, right):
            report["before"].update(bend_allowance_type=3, k_factor=None, bend_allowance_mm=3.5)
        self.assertEqual(compare(left, right)["status"], "verified_match")
        right["rollback"]["restored_state"]["bend_allowance_mm"] = 4.0
        self.assertEqual(compare(left, right)["status"], "not_verified")

    def test_reads_are_insufficient_for_write_parity(self):
        left, right = reports()
        left["status"] = right["status"] = "inspected"
        self.assertEqual(compare(left, right)["status"], "not_verified")
        self.assertEqual(compare(left, right, inspection=True)["status"], "inspection_match")

    def test_same_values_before_and_after_do_not_demonstrate_a_write(self):
        left, right = reports()
        left["before"] = left["after"]
        right["before"] = right["after"]
        self.assertEqual(compare(left, right)["status"], "not_verified")

    def test_unrestored_or_other_document_is_rejected(self):
        for change in (lambda r: r["rollback"].update(verified=False),
                       lambda r: r.update(document_path="C:\\other.sldprt"),
                       lambda r: r["rollback"]["restored_state"].update(radius_mm=4.0)):
            with self.subTest(change=change):
                left, right = reports()
                change(right)
                self.assertEqual(compare(left, right)["status"], "not_verified")

    def test_same_wrong_or_nonfinite_readback_is_rejected(self):
        for value in (5.0, float("nan"), True):
            left, right = reports()
            left["after"]["radius_mm"] = right["after"]["radius_mm"] = value
            self.assertEqual(compare(left, right)["status"], "not_verified")


if __name__ == "__main__":
    unittest.main()
