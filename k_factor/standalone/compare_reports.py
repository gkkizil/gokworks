"""Compare independent native runs; matching error reports never count as success."""

from __future__ import annotations

import argparse
import json
import math
import ntpath
from pathlib import Path


def _number_equal(first, second, tolerance):
    return (
        type(first) in (int, float)
        and type(second) in (int, float)
        and math.isfinite(first)
        and math.isfinite(second)
        and abs(first - second) <= tolerance
    )


def compare(csharp: dict, python: dict, *, inspection: bool = False) -> dict:
    """Require real target readback AND restoration in both verification reports."""
    issues = []
    for name, report in (("csharp", csharp), ("python", python)):
        if report.get("schema_version") != 1 or report.get("engine") != name:
            issues.append(f"{name}: unexpected schema_version / engine")
        expected_status = "inspected" if inspection else "verified"
        if report.get("status") != expected_status:
            issues.append(f"{name}: status must be {expected_status}, got {report.get('status')!r}")
        if report.get("error"):
            issues.append(f"{name}: run contains an error")
        if not isinstance(report.get("before"), dict):
            issues.append(f"{name}: missing baseline readback")
    if issues:
        return {"schema_version": 1, "status": "not_verified", "issues": issues}

    left_path, right_path = csharp.get("document_path"), python.get("document_path")
    if not left_path or not right_path or ntpath.normcase(ntpath.normpath(left_path)) != ntpath.normcase(ntpath.normpath(right_path)):
        issues.append("Runs must target the same saved part")
    if not csharp.get("configuration") or csharp.get("configuration") != python.get("configuration"):
        issues.append("Runs must target the same configuration")

    numeric = {"thickness_mm": 1e-6, "k_factor": 1e-8, "radius_mm": 1e-6}

    def compare_states(left, right, label):
        if not isinstance(left, dict) or not isinstance(right, dict):
            issues.append(f"{label}: missing state")
            return
        for key in ("feature_name", "feature_type", "bend_allowance_type"):
            if key not in left or left.get(key) != right.get(key):
                issues.append(f"{label}: different or missing {key}")
        state_numeric = {key: numeric[key] for key in ("thickness_mm", "radius_mm")}
        allowance_type = left.get("bend_allowance_type")
        if allowance_type == 2:
            state_numeric["k_factor"] = numeric["k_factor"]
        elif allowance_type in (3, 4):
            state_numeric["bend_allowance_mm" if allowance_type == 3 else "bend_deduction_mm"] = 1e-6
        elif allowance_type == 1:
            if not isinstance(left.get("bend_table_file"), str) or left.get("bend_table_file") != right.get("bend_table_file"):
                issues.append(f"{label}: different or invalid bend_table_file")
        else:
            issues.append(f"{label}: unsupported bend allowance type")
        for key, tolerance in state_numeric.items():
            if not _number_equal(left.get(key), right.get(key), tolerance):
                issues.append(f"{label}: different or invalid {key}")

    compare_states(csharp["before"], python["before"], "baseline")
    if not inspection:
        for name, report in (("csharp", csharp), ("python", python)):
            before, after = report["before"], report.get("after")
            rule, restored = report.get("assignment"), report.get("rollback")
            if not isinstance(after, dict) or not isinstance(rule, dict) or not isinstance(restored, dict):
                issues.append(f"{name}: missing target / assignment / restoration")
                continue
            for key in ("k_factor", "radius_mm"):
                if not _number_equal(after.get(key), rule.get(key), numeric[key]):
                    issues.append(f"{name}: target {key} was not verified")
            if not _number_equal(before.get("thickness_mm"), after.get("thickness_mm"), numeric["thickness_mm"]):
                issues.append(f"{name}: thickness changed")
            for key in ("feature_name", "feature_type"):
                if before.get(key) != after.get(key):
                    issues.append(f"{name}: target {key} changed")
            if after.get("bend_allowance_type") != 2:
                issues.append(f"{name}: target is not K-factor bend allowance")
            if all(_number_equal(before.get(key), after.get(key), numeric[key]) for key in ("k_factor", "radius_mm")) and before.get("bend_allowance_type") == 2:
                issues.append(f"{name}: target equals baseline; this run did not demonstrate a value change")
            if restored.get("status") != "restored_after_verification" or restored.get("verified") is not True:
                issues.append(f"{name}: restoration was not verified")
            compare_states(before, restored.get("restored_state"), f"{name} restoration")
        compare_states(csharp.get("after"), python.get("after"), "target")

    return {
        "schema_version": 1,
        "status": "not_verified" if issues else ("inspection_match" if inspection else "verified_match"),
        "document_path": left_path,
        "configuration": csharp.get("configuration"),
        "issues": issues,
        "scope": "selected root sheet-metal feature in the active configuration",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csharp_report", type=Path)
    parser.add_argument("python_report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inspection", action="store_true", help="Compare reads only; never establishes write parity")
    args = parser.parse_args(argv)
    try:
        reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.csharp_report, args.python_report)]
        if not all(isinstance(report, dict) for report in reports):
            raise ValueError("Reports must be JSON objects")
        result = compare(*reports, inspection=args.inspection)
    except (OSError, ValueError, TypeError) as error:
        result = {"schema_version": 1, "status": "not_verified", "issues": [str(error)]}
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 2 if result["status"] == "not_verified" else 0


if __name__ == "__main__":
    raise SystemExit(main())
