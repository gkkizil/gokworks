"""Generate public synthetic DXFs, portable projects and actual GOKWORKS views."""

import json
import importlib.util
import os
from pathlib import Path
import sys
import subprocess
from tempfile import TemporaryDirectory

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

import ezdxf
from PySide6.QtTest import QTest
from gui_qt.app import create_application,MainWindow
from modules.nesting.accounting import calculate
from modules.nesting.dxf_import import read_dxf
from modules.nesting.engine import nest
from modules.nesting.materials import new_project
from modules.nesting.storage import save_project


def main():
    folder=Path(__file__).resolve().parent
    inputs=folder/'source-parts';inputs.mkdir(exist_ok=True)
    for name,width,height,hole in [('Frame',110,150,40),('Insert',12,18,0)]:
        doc=ezdxf.new();doc.units=4;m=doc.modelspace()
        m.add_lwpolyline([(0,0),(width,0),(width,height),(0,height)],close=True)
        if hole:m.add_circle((width/2,height/2),hole)
        doc.saveas(inputs/(name+'.dxf'))
    p=new_project();p.name='Dairesel delik içlerini kullanma örneği'
    p.parts=read_dxf(inputs/'Frame.dxf',quantity=2,tolerance=.01)+read_dxf(inputs/'Insert.dxf',quantity=12)
    for part,name in zip(p.parts,['Çerçeve','Küçük parça']):
        part.code=name;part.source='source-parts/'+Path(part.source).name
    p.sheets[0].name='120 × 320';p.sheets[0].width=120;p.sheets[0].height=320
    p.options.margin=4;p.options.seconds=3;p.options.quality='Hızlı'
    app=create_application([]);records={}
    with TemporaryDirectory() as temporary:
        # Compare against the actual previous GOKWORKS search, without exposing
        # a hole switch in the current application or changing repository files.
        source=subprocess.check_output(['git','show','a9dd65a:modules/nesting/engine.py'],cwd=ROOT)
        baseline_path=Path(temporary)/'previous_engine.py';baseline_path.write_bytes(source)
        spec=importlib.util.spec_from_file_location('gokworks_previous_nfp',baseline_path)
        baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
        baseline.ENGINE_VERSION='1.2'
        window=MainWindow(Path(temporary)/'settings.json');window.resize(1440,960)
        window.show();window.navigate('nesting');page=window.pages['nesting']
        for search,name in [(baseline.nest,'before'),(nest,'after')]:
            result=search(p);totals=calculate(p,result)
            save_project(p,folder/(name+'.goknest.json'),result,overwrite=True)
            page.project=p;page.sync_forms();page.refresh();page.show_result(result,totals)
            page.labels_toggle.setChecked(False)
            QTest.qWait(100)
            window.grab().save(str(folder/(name+'.png')))
            records[name]={key:totals[key] for key in ['sheet_count','part_count','gross_weight','net_weight','waste_weight','efficiency']}
        for theme in ('light','dark'):
            window.set_theme(theme);QTest.qWait(80)
            window.grab().save(str(folder/('after-'+theme+'.png')))
        page.settings_button.click();QTest.qWait(60)
        page.settings_dialog.grab().save(str(folder/'settings.png'))
        page.settings_dialog.reject();window.close();app.processEvents()
    assert records['before']['part_count']==records['after']['part_count']==14
    assert records['before']['sheet_count']==2 and records['after']['sheet_count']==1
    (folder/'comparison.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False))


if __name__=='__main__':main()
