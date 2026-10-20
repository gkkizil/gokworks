"""Generate real DXF examples, analyse them, export and capture the integrated page.

Run from repository root: QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_nesting.py
No fabricated placement or report rows; uses the same reader and engine as the application.
"""

import json
from pathlib import Path
import sys
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

import ezdxf
from gui_qt.app import create_application, MainWindow
from nesting.materials import new_project
from nesting.dxf_import import read_dxf
from nesting.engine import nest
from nesting.accounting import calculate
from nesting.storage import save_project
from nesting.report import export_excel, export_pdf
from nesting.dxf_export import export_dxf


def main():
    app = create_application([])
    target = ROOT/'docs/nesting-example'; target.mkdir(parents=True,exist_ok=True)
    inputs = target/'input'; inputs.mkdir(exist_ok=True)
    for code in ('GW-001','GW-002','GW-003'):
        doc = ezdxf.new('R2018'); doc.units = 4; m = doc.modelspace()
        if code == 'GW-001':
            m.add_lwpolyline([(0,0),(180,0),(180,50),(70,50),(70,140),(0,140)],close=True)
        elif code == 'GW-002':
            m.add_lwpolyline([(0,0),(70,0),(70,50),(0,50)],close=True)
            m.add_circle((35,25),10)
        else:
            m.add_arc((0,0),35,0,180); m.add_line((-35,0),(35,0)); m.add_circle((0,15),5)
        doc.saveas(inputs/(code+'.dxf'))
    project = new_project(); project.name = 'GOKWORKS · Kontur yerleşimi örneği'
    project.sheets[0].name = '600 × 400'; project.sheets[0].width = 600; project.sheets[0].height = 400
    project.sheets[0].price_kg = 45
    for code, quantity in [('GW-001',6),('GW-002',10),('GW-003',6)]:
        project.parts.extend(read_dxf(inputs/(code+'.dxf'),quantity=quantity))
    project.options.quality = 'Dengeli'; project.options.seconds = 5
    result = nest(project); totals = calculate(project,result)
    save_project(project,target/'Ornek.goknest.json',result,overwrite=True)
    export_excel(project,result,target/'Nesting.xlsx',overwrite=True)
    export_pdf(project,result,target/'Nesting.pdf',overwrite=True)
    output = target/'DXF'; output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nesting-dxf-example-') as folder:
        generated = Path(folder)/'DXF'; export_dxf(project,result,generated)
        for old in output.glob('Levha-*.dxf'): old.unlink()
        for source in generated.iterdir(): shutil.copyfile(source,output/source.name)
    with tempfile.TemporaryDirectory(prefix='nesting-capture-') as folder:
        w = MainWindow(Path(folder)/'settings.json'); page = w.pages['nesting']
        page.project = project; page.sync_forms(); page.refresh(); page.show_result(result,totals)
        w.show(); w.navigate('nesting')
        for theme,width,height in [('dark',1440,960),('light',1440,960),('dark',1024,768)]:
            w.set_theme(theme); w.resize(width,height); app.processEvents()
            app.processEvents(); page.canvas.fit()
            assert w.grab().save(str(target/f'nesting-{theme}-{width}.png'))
        w.settings.flush(); w.close()
    (target/'checks.json').write_text(json.dumps(dict(engine=result.engine,engine_version=result.engine_version,
        part_count=totals['part_count'],sheet_count=totals['sheet_count'],gross_weight=totals['gross_weight'],
        net_weight=totals['net_weight'],waste_weight=totals['waste_weight'],efficiency=totals['efficiency'],
        material_cost=totals['material_cost'],elapsed=result.elapsed,iterations=result.iterations,
        validated=True,source='Generated real DXF contours; same production import/engine/report code.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__': main()
