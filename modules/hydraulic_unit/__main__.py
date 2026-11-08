"""Arayüz olmadan HPU projesi hesaplama ve rapor üretme komutu."""
import argparse
from pathlib import Path
from .core import Project, calculate_project
from .serialization import load, save
from .presentation import result_rows


def main():
    parser = argparse.ArgumentParser(description='GOKWORKS Hidrolik Ünite — bağımsız hesap')
    parser.add_argument('project', nargs='?', help='.gwhyd proje dosyası; verilmezse dört fazlı örnek')
    parser.add_argument('--save', type=Path, help='Proje kaydet')
    parser.add_argument('--json', type=Path, help='SI sonuç raporu')
    parser.add_argument('--excel', type=Path, help='Excel raporu')
    parser.add_argument('--pdf', type=Path, help='Qt ile grafik içeren PDF raporu')
    args = parser.parse_args()
    try:
        project = load(args.project) if args.project else Project()
        result = calculate_project(project)
        for label, value, unit, _ in result_rows(project,result):
            print(f'{label}: {"Değerlendirilmedi" if value is None else format(value,".6g")} {unit}')
        for issue in result.issues: print(f'{issue.severity.upper()}: {issue.message}')
        if args.save: save(project,args.save)
        if args.json or args.excel or args.pdf:
            from .report.export import export_json, export_excel, export_pdf
            if args.json: export_json(project,result,args.json)
            if args.excel: export_excel(project,result,args.excel)
            if args.pdf:
                from PySide6.QtGui import QGuiApplication
                from .report.plots import cycle_images
                app = QGuiApplication.instance() or QGuiApplication([])
                export_pdf(project,result,args.pdf,images=cycle_images(project,result))
        return 0
    except (ValueError, TypeError, OSError, RuntimeError, ArithmeticError) as error:
        parser.exit(2, f'Hidrolik hesap hatası: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
