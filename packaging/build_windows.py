"""Build a standalone Windows executable; run on Windows with Python 3.13 x64."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32':
        raise SystemExit('Windows EXE oluşturmak için bu betiği Windows üzerinde çalıştırın.')
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
            '--name', 'GOKWORKS', '--icon', str(ROOT/'gui/assets/gokworks-logo.ico'),
            '--distpath', str(ROOT/'dist'), '--workpath', str(ROOT/'build/pyinstaller'),
            '--specpath', str(ROOT/'build'), '--paths', str(ROOT),
            '--collect-data', 'customtkinter', '--collect-data', 'ezdxf',
            '--hidden-import', 'win32timezone', '--hidden-import', 'pythoncom',
            '--hidden-import', 'pywintypes', '--hidden-import', 'win32com.client',
            '--add-data', f'{ROOT / "gui/assets/gokworks-logo.jpg"};gui/assets',
            '--add-data', f'{ROOT / "gui/assets/gokworks-logo.ico"};gui/assets',
            '--add-data', f'{ROOT / "iso_fits/tables.json"};iso_fits', str(ROOT/'main.py')]
    subprocess.run(args, cwd=ROOT, check=True)
    exe = ROOT/'dist/GOKWORKS.exe'
    if exe.read_bytes()[:2] != b'MZ':
        raise RuntimeError('Üretilen dosya Windows yürütülebilir dosyası değil.')
    report = ROOT/'dist/windows-smoke.json'
    subprocess.run([str(exe), '--self-check', str(report)], cwd=ROOT, check=True, timeout=120)
    result = json.loads(report.read_text(encoding='utf-8'))
    if result.get('status') != 'passed':
        raise RuntimeError(f'Paket açılış kontrolü başarısız: {result}')
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256.txt').write_text(f'{digest}  GOKWORKS.exe\n', encoding='utf-8')
    (ROOT/'dist/OKU.txt').write_text(
        'GOKWORKS · Windows 10/11 x64\n\n'
        'ZIP dosyasını çıkartın ve GOKWORKS.exe dosyasını açın. Python kurulumu gerekmez.\n'
        'Cıvata, ISO geçme ve geometrik tolerans ekranları SolidWorks olmadan açılır.\n'
        'CAD aktarımı ve montaj işlemleri için SolidWorks kurulu ve açık olmalıdır.\n'
        'Ayarlar %APPDATA%\\GOKWORKS altında saklanır.\n'
        'Bu deneme paketi kod imzası taşımaz.\n\n'
        f'Kaynak commit: {os.environ.get("GITHUB_SHA", "yerel derleme")}\n', encoding='utf-8')
    print(json.dumps({'exe': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest, 'smoke': result}))


if __name__ == '__main__':
    main()
