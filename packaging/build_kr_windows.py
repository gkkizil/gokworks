"""Package the independent K/R desktop and self-contained native engine."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/kr-probe"
PACKAGE = OUTPUT / "GOKWORKS-KR-Deneme"
REFERENCES = {
    "SolidWorks.Interop.sldworks.dll": "7a6bf74d2a9f60563959d738c3c85f825f257c9def2a3bec464511aaebfc88e4",
    "SolidWorks.Interop.swconst.dll": "2272a99dd0dc1bd40b16a8dcc7849616fe7d90349a06342f9ac6999ec0587a3b",
}


def run(command, **kwargs):
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def main():
    if sys.platform != "win32":
        raise SystemExit("Build this package on Windows x64.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    interop = ROOT / "build/kr-interop"
    interop.mkdir(parents=True, exist_ok=True)
    base = "https://raw.githubusercontent.com/angelsix/solidworks-api/85a773aedc87b49afda3a65c8bb650f5ba771092/References/2023/"
    for name, expected in REFERENCES.items():
        data = urllib.request.urlopen(base + name, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(name + " SHA256 mismatch")
        (interop / name).write_bytes(data)
    native_output = ROOT / "build/kr-native"
    run(["dotnet", "publish", str(ROOT / "k_factor/standalone/csharp/Gokworks.KrProbe.csproj"),
         "-c", "Release", "-r", "win-x64", "--self-contained", "true", "-o", str(native_output),
         f"-p:SolidWorksInteropDir={interop}", "-p:ExternalSolidWorksInterop=true",
         "-p:PublishSingleFile=false", "-p:PublishTrimmed=false"])
    if any(native_output.glob("SolidWorks.Interop.*.dll")):
        raise RuntimeError("Installed SolidWorks interop DLLs must not be redistributed.")
    pyinstaller = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noupx", "--windowed",
                   "--name", "GOKWORKS-KR-Deneme", "--icon", str(ROOT / "gui/assets/GOK_app_windows.ico"),
                   "--distpath", str(OUTPUT), "--workpath", str(ROOT / "build/kr-pyinstaller"),
                   "--specpath", str(ROOT / "build"), "--paths", str(ROOT),
                   "--collect-data", "customtkinter", "--collect-submodules", "win32com.client",
                   "--hidden-import", "win32com.gen_py", "--hidden-import", "win32timezone",
                   "--hidden-import", "pythoncom", "--hidden-import", "pywintypes"]
    for name in ("GOK_logo_light_UI_1024.png", "GOK_logo_dark_UI_1024.png", "GOK_app_windows.ico"):
        pyinstaller.extend(["--add-data", f'{ROOT / "gui/assets" / name};gui/assets'])
    pyinstaller.append(str(ROOT / "k_factor/standalone/desktop_entry.py"))
    run(pyinstaller)
    shutil.copytree(native_output, PACKAGE / "native", dirs_exist_ok=True)
    backend = PACKAGE / "native/Gokworks.KrProbe.exe"
    desktop = PACKAGE / "GOKWORKS-KR-Deneme.exe"
    for executable in (desktop, backend):
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise RuntimeError(executable.name + " is not a Windows executable")
    # Inspect all original package bytes before executing either generated EXE.
    manifest = {str(path.relative_to(PACKAGE)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(PACKAGE.rglob('*')) if path.is_file()}
    scan_request = ROOT / "build/kr-security-request.json"
    scan_request.write_text(json.dumps({"source_commit": os.environ.get("GITHUB_SHA", "local"),
                                      "artifact_id": None, "expected_files": manifest}, indent=2), encoding="utf-8")
    security_file = ROOT / "build/kr-security-report.json"
    run(["pwsh", "-NoProfile", "-File", str(ROOT / "k_factor/standalone/security/scan-package.ps1"),
         "-PackagePath", str(PACKAGE), "-RequestPath", str(scan_request), "-ReportPath", str(security_file)])
    security = json.loads(security_file.read_text(encoding="utf-8-sig"))
    if security.get("status") != "no_detection":
        raise RuntimeError("Package antivirus inspection was unavailable or detected a threat; publication blocked")
    shutil.copy2(security_file, PACKAGE / "security-check.json")
    shutil.copy2(scan_request, PACKAGE / "package-manifest.json")
    smoke_file = PACKAGE / "windows-smoke.json"
    run([str(desktop), "--self-check", str(smoke_file)], timeout=120)
    smoke = json.loads(smoke_file.read_text(encoding="utf-8"))
    if smoke.get("status") != "passed" or not smoke.get("frozen"):
        raise RuntimeError("Packaged desktop check failed: " + json.dumps(smoke, ensure_ascii=False))
    checksums = {path.relative_to(PACKAGE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in (desktop, backend)}
    (PACKAGE / "SHA256.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
    (PACKAGE / "OKU.txt").write_text(
        "GOKWORKS · K/R Denemesi · Windows 10/11 x64\n\n"
        "ZIP dosyasını tüm alt klasörleriyle çıkartın. EXE'yi tek başına taşımayın.\n"
        "GOKWORKS-KR-Deneme.exe dosyasına çift tıklayın.\n"
        "Python, .NET ve terminal kurulumu/kullanımı gerekmez.\n\n"
        "SolidWorks kurulu ve açık olmalı. Sac parçayı kendi penceresinde etkinleştirin.\n"
        "İlk denemeyi bir kopyada yapın. Önce Parçayı oku düğmesine basın.\n"
        "K ve R girip K/R yazma denemesi düğmesine basın.\n"
        "Önce C#, sonra Python yazar, geri okur ve eski değerleri geri yükler.\n"
        "Otomatik kayıt yapılmaz. Geri alma hatası varsa parçayı kaydetmeyin.\n"
        "İşlem bitene kadar SolidWorks'te belge veya konfigürasyon değiştirmeyin.\n"
        "Rapor klasörü düğmesi ayrıntılı sonuçları açar.\n\n"
        "SolidWorks API dosyaları yerel kurulumdan alınır; bu pakette dağıtılmaz.\n"
        "Bu standart klasör paketi geçici klasöre kendini açan EXE kullanmaz.\n"
        "Windows Defender taramasında tespit yok: security-check.json. Yayıncı imzası yoktur.\n"
        "Defender sonucu Chrome'un kabul edeceği veya yazılımın kesin güvenli olduğu anlamına gelmez.\n"
        "Bu açılış kontrolü SolidWorks bağlantısını veya gerçek CAD yazmasını sınamaz.\n"
        f'Kaynak commit: {os.environ.get("GITHUB_SHA", "local")}\n', encoding="utf-8")
    print(json.dumps({"files": checksums, "smoke": smoke, "security": security}, ensure_ascii=False))


if __name__ == "__main__":
    main()
