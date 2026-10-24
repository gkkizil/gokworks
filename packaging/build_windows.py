"""Build a standalone Windows executable; run on Windows with Python 3.13 x64."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import importlib.metadata
import shutil
import argparse
import tempfile

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--onedir', action='store_true', help='Developer option: unpacked distribution')
    options = parser.parse_args()
    mode = 'onedir' if options.onedir else 'onefile'
    collect_licenses()
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--'+mode, '--windowed', '--noupx',
            '--name', 'GOKWORKS', '--icon', str(ROOT/'assets/GOK_app_windows.ico'),
            '--distpath', str(ROOT/'dist'), '--workpath', str(ROOT/'build/pyinstaller'),
            '--specpath', str(ROOT/'build'), '--paths', str(ROOT),
            '--runtime-hook', str(ROOT/'packaging/runtime_hook.py'),
            '--collect-data', 'ezdxf',
            '--collect-all', 'shapely',
            '--hidden-import', 'win32timezone', '--hidden-import', 'pythoncom',
            '--hidden-import', 'pywintypes', '--hidden-import', 'win32com.client',
            '--exclude-module', 'modules.k_factor.standalone',
            '--exclude-module', 'tkinter', '--exclude-module', '_tkinter',
            '--exclude-module', 'customtkinter', '--exclude-module', 'PySide6.QtQml',
            '--exclude-module', 'PySide6.QtQuick', '--exclude-module', 'PySide6.QtWebEngineCore',
            '--add-data', f'{ROOT / "packaging/licenses"};licenses',
            '--add-data', f'{ROOT / "docs/THIRD_PARTY_NOTICES.md"};licenses',
            '--add-data', f'{ROOT / "assets/GOK_logo_light_UI_1024.png"};assets',
            '--add-data', f'{ROOT / "assets/GOK_logo_dark_UI_1024.png"};assets',
            '--add-data', f'{ROOT / "assets/GOK_app_windows.ico"};assets',
            '--add-data', f'{ROOT / "assets/qt/chevron-dark.png"};assets/qt',
            '--add-data', f'{ROOT / "assets/qt/chevron-light.png"};assets/qt',
            '--add-data', f'{ROOT / "modules/iso_fits/tables.json"};modules/iso_fits',
            '--add-data', f'{ROOT / "modules/naming/interop/PackAndGoHost.cs"};modules/naming/interop', str(ROOT/'main.py')]
    subprocess.run(args, cwd=ROOT, check=True)
    exe = ROOT/('dist/GOKWORKS/GOKWORKS.exe' if options.onedir else 'dist/GOKWORKS.exe')
    if exe.read_bytes()[:2] != b'MZ':
        raise RuntimeError('Üretilen dosya Windows yürütülebilir dosyası değil.')
    report = ROOT/'dist/windows-smoke.json'
    reports = []
    with tempfile.TemporaryDirectory(prefix='GOKWORKS dağıtım kontrolü ') as folder:
        deploy = Path(folder)
        runnable = exe if options.onedir else deploy/'GOKWORKS.exe'
        if not options.onedir:
            shutil.copy2(exe, runnable)
        for scale in ('1', '1.25', '1.5'):
            scaled_report = report if scale == '1' else report.with_name(f'windows-smoke-{scale}.json')
            env = {**os.environ, 'QT_SCALE_FACTOR': scale}
            env.pop('PYTHONPATH', None)
            env.pop('PYTHONHOME', None)
            env.pop('GOKWORKS_LIBRARY_DIR', None)
            # Also prove compatible external Qt/PySide packages can replace
            # the bundled libraries without repacking the application.
            if scale == '1.5':
                import PySide6
                env['GOKWORKS_LIBRARY_DIR'] = str(Path(PySide6.__file__).resolve().parent.parent)
            subprocess.run([str(runnable), '--self-check', str(scaled_report)], cwd=deploy, check=True, timeout=240, env=env)
            result = json.loads(scaled_report.read_text(encoding='utf-8'))
            if result.get('status') != 'passed' or result.get('distribution') != mode:
                raise RuntimeError(f'Paket açılış kontrolü başarısız: {result}')
            if scale == '1.5' and not result.get('external_qt_verified'):
                raise RuntimeError('Harici Qt kitaplıklarıyla çalıştırma kontrolü başarısız.')
            if not options.onedir and list(deploy.iterdir()) != [runnable]:
                raise RuntimeError('Tek EXE dağıtımında yan dosya oluştu.')
            reports.append(result)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256.txt').write_text(f'{digest}  {exe.relative_to(ROOT/"dist").as_posix()}\n', encoding='utf-8')
    (ROOT/'dist/OKU.txt').write_text(
        'GOKWORKS · Windows 10/11 x64\n\n'+
        ('GOKWORKS klasöründeki GOKWORKS.exe dosyasını _internal ile birlikte taşıyın.\n' if options.onedir else
         'Yalnız GOKWORKS.exe dosyasını taşıyıp dağıtabilirsiniz. Yanında klasör gerekmez.\n')+
        'Python kurulumu gerekmez. Tek EXE kaynakları açılışta geçici klasöre açılır.\n'
        'Cıvata, ISO geçme ve geometrik tolerans ekranları SolidWorks olmadan açılır.\n'
        'Tolerans yığılması manuel analiz, Monte Carlo ve PDF/Excel raporları yerel çalışır.\n'
        'Teknik resim ölçü okuma/anotasyon işlemleri için açık SolidWorks oturumu gerekir.\n'
        'CAD aktarımı ve montaj işlemleri için SolidWorks kurulu ve açık olmalıdır.\n'
        '3D Dönüştürücü; STEP AP203/AP214, Parasolid, IGES ve STL aktarır. AP242 için MBD lisansı gerekir.\n'
        'Profil kesim manuel 1D stok planı çevrimdışı çalışır. Weldments taraması kurulu/açık SolidWorks gerektirir.\n'
        'PDF aktarımı ayrı yardımcı süreçte çalışır; hata kayıtları %LOCALAPPDATA%\\GOKWORKS\\logs altındadır.\n'
        'Ayarlar %APPDATA%\\GOKWORKS altında saklanır.\n'
        'Bu deneme paketi kod imzası taşımaz.\n\n'
        'PySide6/Qt dinamik DLL dosyaları LGPL v3 kapsamında dağıtılır.\n'
        'Gömülü lisanslar uygulamadaki Lisanslar düğmesinden okunabilir ve kaydedilebilir.\n'
        'Uyumlu Qt/PySide kitaplıkları GOKWORKS_LIBRARY_DIR ile değiştirilebilir.\n\n'
        f'Kaynak commit: {os.environ.get("GITHUB_SHA", "yerel derleme")}\n', encoding='utf-8')
    (ROOT/'dist/release-notes.md').write_text(
        'Windows 10/11 x64 · Tek dosya GOKWORKS.exe. Yanında klasör veya Python kurulumu gerekmez.\n\n'
        'Lisanslar uygulamadaki Lisanslar ekranındadır. CAD işlemleri kurulu ve açık SolidWorks gerektirir.\n\n'
        f'SHA256: `{digest}`\n\nKaynak: `{os.environ.get("GITHUB_SHA", "yerel derleme")}`\n', encoding='utf-8')
    print(json.dumps({'exe': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest, 'smoke': reports}))


if __name__ == '__main__':
    main()
