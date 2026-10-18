"""Build a standalone Windows executable; run on Windows with Python 3.13 x64."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import importlib.metadata
import shutil

ROOT = Path(__file__).resolve().parents[1]


def collect_licenses():
    """Preserve wheel notices, including transitive dependencies, without code edits."""
    target = ROOT/'packaging/licenses/installed'
    target.mkdir(parents=True, exist_ok=True)
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name']
        inventory.append(dict(name=name, version=distribution.version,
                              license=distribution.metadata.get('License-Expression') or distribution.metadata.get('License'),
                              homepage=distribution.metadata.get('Home-page')))
        for file in distribution.files or ():
            if any(term in file.name.lower() for term in ('license', 'licence', 'copying', 'notice')) and file.suffix.lower() in ('', '.txt', '.md', '.rst'):
                source = distribution.locate_file(file)
                if source.is_file():
                    shutil.copy2(source, target/(name+'-'+str(file).replace('/', '_').replace('\\', '_')))
    for name in ('LICENSE.txt','LICENSE'):
        source = Path(sys.base_prefix)/name
        if source.is_file():
            shutil.copy2(source,target/('Python-'+name))
    (target/'dependency-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    if sys.platform != 'win32':
        raise SystemExit('Windows EXE oluşturmak için bu betiği Windows üzerinde çalıştırın.')
    collect_licenses()
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed', '--noupx',
            '--name', 'GOKWORKS', '--icon', str(ROOT/'gui/assets/GOK_app_windows.ico'),
            '--distpath', str(ROOT/'dist'), '--workpath', str(ROOT/'build/pyinstaller'),
            '--specpath', str(ROOT/'build'), '--paths', str(ROOT),
            '--collect-data', 'ezdxf',
            '--hidden-import', 'win32timezone', '--hidden-import', 'pythoncom',
            '--hidden-import', 'pywintypes', '--hidden-import', 'win32com.client',
            '--exclude-module', 'k_factor.standalone',
            '--exclude-module', 'tkinter', '--exclude-module', '_tkinter',
            '--exclude-module', 'customtkinter', '--exclude-module', 'PySide6.QtQml',
            '--exclude-module', 'PySide6.QtQuick', '--exclude-module', 'PySide6.QtWebEngineCore',
            '--add-data', f'{ROOT / "packaging/licenses"};licenses',
            '--add-data', f'{ROOT / "docs/THIRD_PARTY_NOTICES.md"};licenses',
            '--add-data', f'{ROOT / "gui/assets/GOK_logo_light_UI_1024.png"};gui/assets',
            '--add-data', f'{ROOT / "gui/assets/GOK_logo_dark_UI_1024.png"};gui/assets',
            '--add-data', f'{ROOT / "gui/assets/GOK_app_windows.ico"};gui/assets',
            '--add-data', f'{ROOT / "iso_fits/tables.json"};iso_fits', str(ROOT/'main.py')]
    subprocess.run(args, cwd=ROOT, check=True)
    exe = ROOT/'dist/GOKWORKS/GOKWORKS.exe'
    if exe.read_bytes()[:2] != b'MZ':
        raise RuntimeError('Üretilen dosya Windows yürütülebilir dosyası değil.')
    report = ROOT/'dist/windows-smoke.json'
    reports = []
    for scale in ('1', '1.25', '1.5'):
        scaled_report = report if scale == '1' else report.with_name(f'windows-smoke-{scale}.json')
        subprocess.run([str(exe), '--self-check', str(scaled_report)], cwd=ROOT, check=True, timeout=180,
                       env={**os.environ, 'QT_SCALE_FACTOR': scale})
        result = json.loads(scaled_report.read_text(encoding='utf-8'))
        if result.get('status') != 'passed':
            raise RuntimeError(f'Paket açılış kontrolü başarısız: {result}')
        reports.append(result)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256.txt').write_text(f'{digest}  GOKWORKS/GOKWORKS.exe\n', encoding='utf-8')
    (ROOT/'dist/OKU.txt').write_text(
        'GOKWORKS · Windows 10/11 x64\n\n'
        'ZIP dosyasının tamamını çıkartın. GOKWORKS klasöründeki GOKWORKS.exe dosyasını açın.\n'
        '_internal klasörü EXE yanında kalmalıdır; yalnız EXE dosyasını taşımayın. Python kurulumu gerekmez.\n'
        'Cıvata, ISO geçme ve geometrik tolerans ekranları SolidWorks olmadan açılır.\n'
        'CAD aktarımı ve montaj işlemleri için SolidWorks kurulu ve açık olmalıdır.\n'
        'Ayarlar %APPDATA%\\GOKWORKS altında saklanır.\n'
        'Bu deneme paketi kod imzası taşımaz.\n\n'
        'PySide6/Qt dinamik DLL dosyaları LGPL v3 kapsamında ayrı paketlenmiştir.\n'
        'Lisanslar: GOKWORKS/_internal/licenses/THIRD_PARTY_NOTICES.md\n\n'
        f'Kaynak commit: {os.environ.get("GITHUB_SHA", "yerel derleme")}\n', encoding='utf-8')
    print(json.dumps({'exe': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest, 'smoke': reports}))


if __name__ == '__main__':
    main()
