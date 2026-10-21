"""Native K/R assignment; cross-language comparison is an optional diagnostic."""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from modules.k_factor.standalone.compare_reports import compare
from modules.k_factor.standalone.python.probe import execute, validate_request


def native_executable():
    directory = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    installed = directory / "native/Gokworks.KrProbe.exe"
    if installed.is_file():
        return installed
    return directory / "GOKWORKS.KR.Native.exe"


def report_directory():
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home() / "AppData/Local")
    folder = base / "GOKWORKS/KR-Deneme/reports" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class ComparisonFailure(RuntimeError):
    pass


def run_native(request, folder, *, notify=lambda message: None, native_runner=subprocess.run, backend=None):
    """Read or write with the typed native engine, without Python COM binding."""
    request = validate_request(request)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    request_file = folder / "request.json"
    csharp_file = folder / "csharp.json"
    write_json(request_file, request)
    helper = Path(backend) if backend is not None else native_executable()
    if not helper.is_file():
        raise ComparisonFailure("C# motoru bulunamadı. ZIP dosyasını tüm alt klasörleriyle çıkartın; EXE'yi tek başına taşımayın.")
    notify("SolidWorks sac parametreleri okunuyor…" if request["mode"] == "inspect" else "Sac-Levha K/R değerleri yazılıyor ve geri okunuyor…")
    csharp_file.unlink(missing_ok=True)
    # No timeout/TerminateProcess during writes: rollback must finish before exit.
    result = native_runner([str(helper), "--request", str(request_file), "--report", str(csharp_file)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not csharp_file.is_file():
        raise ComparisonFailure("C# motoru rapor oluşturamadı: " + (result.stderr or result.stdout or f"çıkış kodu {result.returncode}")[-3000:])
    csharp = json.loads(csharp_file.read_text(encoding="utf-8-sig"))
    expected = {"inspect": "inspected", "apply": "applied", "verify": "verified"}[request["mode"]]
    if (result.returncode != 0 or csharp.get("status") != expected or csharp.get("error")
            or csharp.get("schema_version") != 1 or csharp.get("engine") != "csharp"):
        detail = str(csharp.get("error") or "; ".join(csharp.get("warnings", [])) or csharp.get("status"))
        rollback = csharp.get("rollback") or {}
        if rollback.get("attempted") and rollback.get("verified") is not True:
            detail = "Eski değerler geri yüklenip doğrulanamadı. Parçayı kaydetmeyin.\n" + detail
        raise ComparisonFailure("SolidWorks işlemi tamamlanamadı.\n" + detail)
    if request["mode"] == "verify" and ((csharp.get("rollback") or {}).get("verified") is not True):
        raise ComparisonFailure("C# geri alma işlemi doğrulanamadı. Python başlatılmadı. Parçayı kaydetmeyin.")
    if request["mode"] == "apply":
        # A preview/exit code alone must never be presented as an assignment.
        before, after, assignment = (csharp.get(key) for key in ("before", "after", "assignment"))
        if not all(isinstance(state, dict) for state in (before, after, assignment)):
            raise ComparisonFailure("K/R atamasının geri okuma raporu eksik. Sonucu SolidWorks'te kontrol edin.")
        if (after.get("bend_allowance_type") != 2
                or any(type(after.get(key)) not in (int, float) or type(assignment.get(key)) not in (int, float)
                       or not abs(after[key] - assignment[key]) <= tolerance
                       for key, tolerance in (("k_factor", 1e-8), ("radius_mm", 1e-6)))
                or any(after.get(key) != before.get(key) for key in ("feature_name", "feature_type"))
                or type(after.get("thickness_mm")) not in (int, float)
                or type(before.get("thickness_mm")) not in (int, float)
                or not abs(after["thickness_mm"] - before["thickness_mm"]) <= 1e-6):
            raise ComparisonFailure("K/R ataması geri okunarak doğrulanamadı. Raporu ve SolidWorks değerlerini kontrol edin.")
    return {"csharp": csharp, "folder": str(folder)}


def run_pair(request, folder, *, notify=lambda message: None, native_runner=subprocess.run, python_runner=execute, backend=None):
    """Optional diagnostic only; the assignment desktop never calls this."""
    request = validate_request(request)
    if request["mode"] not in ("inspect", "verify"):
        raise ComparisonFailure("Karşılaştırma yalnız inspect ve verify modlarını destekler.")
    result = run_native(request, folder, notify=notify, native_runner=native_runner, backend=backend)
    folder, csharp = Path(folder), result["csharp"]
    python_file = folder / "python.json"
    # Bind the second run to the document and root read by the first engine.
    bound = dict(request, document_path=csharp["document_path"], configuration=csharp["configuration"],
                 feature_name=csharp["before"]["feature_name"], expected_state=csharp["before"])
    notify("Python motoru aynı parçayı okuyor…" if request["mode"] == "inspect" else "Python motoru aynı K/R denemesini yapıyor…")
    python = python_runner(bound)
    write_json(python_file, python)
    comparison = compare(csharp, python, inspection=request["mode"] == "inspect")
    write_json(folder / "comparison.json", comparison)
    if comparison["status"] == "not_verified":
        detail = python.get("error") or "\n".join(comparison["issues"])
        rollback = python.get("rollback") or {}
        if rollback.get("attempted") and not rollback.get("verified"):
            detail = "Eski değerler geri yüklenip doğrulanamadı. Parçayı kaydetmeyin.\n" + str(detail)
        raise ComparisonFailure("İki motorun sonucu doğrulanamadı.\n" + str(detail))
    return {"csharp": csharp, "python": python, "comparison": comparison, "folder": str(folder)}
