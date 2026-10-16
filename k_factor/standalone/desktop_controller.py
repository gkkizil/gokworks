"""Sequential native/early-bound runs. Worker code never touches Tk widgets."""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from k_factor.standalone.compare_reports import compare
from k_factor.standalone.python.probe import execute, validate_request


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


def run_pair(request, folder, *, notify=lambda message: None, native_runner=subprocess.run, python_runner=execute, backend=None):
    """Stop before Python when C# did not verify/restore the selected part."""
    request = validate_request(request)
    if request["mode"] not in ("inspect", "verify"):
        raise ComparisonFailure("Masaüstü denemesi yalnız inspect ve verify modlarını destekler.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    request_file = folder / "request.json"
    csharp_file, python_file = folder / "csharp.json", folder / "python.json"
    write_json(request_file, request)
    helper = Path(backend) if backend is not None else native_executable()
    if not helper.is_file():
        raise ComparisonFailure("C# motoru bulunamadı. ZIP dosyasını tüm alt klasörleriyle çıkartın; EXE'yi tek başına taşımayın.")
    notify("C# motoru sac parametrelerini okuyor…" if request["mode"] == "inspect" else "C# motoru K/R yazma ve geri alma denemesi yapıyor…")
    # No timeout/TerminateProcess during writes: rollback must finish before exit.
    result = native_runner([str(helper), "--request", str(request_file), "--report", str(csharp_file)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not csharp_file.is_file():
        raise ComparisonFailure("C# motoru rapor oluşturamadı: " + (result.stderr or result.stdout or f"çıkış kodu {result.returncode}")[-3000:])
    csharp = json.loads(csharp_file.read_text(encoding="utf-8-sig"))
    expected = "inspected" if request["mode"] == "inspect" else "verified"
    if result.returncode != 0 or csharp.get("status") != expected:
        raise ComparisonFailure("C# denemesi tamamlanamadı. Python başlatılmadı.\n" + str(csharp.get("error") or "; ".join(csharp.get("warnings", [])) or csharp.get("status")))
    if request["mode"] == "verify" and ((csharp.get("rollback") or {}).get("verified") is not True):
        raise ComparisonFailure("C# geri alma işlemi doğrulanamadı. Python başlatılmadı. Parçayı kaydetmeyin.")
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
