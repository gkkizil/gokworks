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
         "-p:PublishSingleFile=true", "-p:IncludeNativeLibrariesForSelfExtract=true", "-p:PublishTrimmed=false"])
    if any(native_output.glob("SolidWorks.Interop.*.dll")):
        raise RuntimeError("Installed SolidWorks interop DLLs must not be redistributed.")
    backend = OUTPUT / "GOKWORKS.KR.Native.exe"
    shutil.copy2(native_output / "Gokworks.KrProbe.exe", backend)
    pyinstaller = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
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
    desktop = OUTPUT / "GOKWORKS-KR-Deneme.exe"
    for executable in (desktop, backend):
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise RuntimeError(executable.name + " is not a Windows executable")
    smoke_file = OUTPUT / "windows-smoke.json"
    run([str(desktop), "--self-check", str(smoke_file)], timeout=120)
    smoke = json.loads(smoke_file.read_text(encoding="utf-8"))
    if smoke.get("status") != "passed" or not smoke.get("frozen"):
        raise RuntimeError("Packaged desktop check failed: " + json.dumps(smoke, ensure_ascii=False))
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (desktop, backend)}
    (OUTPUT / "SHA256.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
    (OUTPUT / "OKU.txt").write_text(
        "GOKWORKS · K/R Denemesi · Windows 10/11 x64\n\n"
        "ZIP dosyasını tamamen çıkartın. İki EXE aynı klasörde kalsın.\n"
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
        "Bu açılış kontrolü SolidWorks bağlantısını veya gerçek CAD yazmasını sınamaz.\n"
        f'Kaynak commit: {os.environ.get("GITHUB_SHA", "local")}\n', encoding="utf-8")
    print(json.dumps({"files": checksums, "smoke": smoke}, ensure_ascii=False))


if __name__ == "__main__":
    main()
