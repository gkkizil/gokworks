"""Capture the actual Nesting workbench using repository DXFs and real NFP results."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import ezdxf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from PySide6.QtTest import QTest
from gui_qt.app import create_application,MainWindow
from modules.nesting.validation import validate_result


def capture(destination):
    out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    app=create_application([]); shots=[]
    sources=sorted((ROOT/'docs/nesting-example/input').glob('*.dxf'))
    with tempfile.TemporaryDirectory(prefix='gokworks-nesting-workbench-') as folder:
        w=MainWindow(Path(folder)/'settings.json');w.resize(1366,768);w.show();w.navigate('nesting')
        p=w.pages['nesting']
        def shot(name):
            QTest.qWait(80)
            assert w.grab().save(str(out/(name+'.png')))
            shots.append(dict(file=name+'.png',size=w.size().toTuple()))
        def wait():
            end=time.monotonic()+20
            while w.jobs.busy:
                app.processEvents();time.sleep(.005)
                if time.monotonic()>end: raise TimeoutError('Actual Nesting operation timed out')
            QTest.qWait(60)
        def resize(width,height):
            if app.platformName()=='windows':
                bounds=w.screen().availableGeometry();margins=w.windowHandle().frameMargins()
                width=min(width,bounds.width()-margins.left()-margins.right())
                height=min(height,bounds.height()-margins.top()-margins.bottom())
            w.resize(width,height)
        shot('01-empty-dark')
        p.import_files([str(x) for x in sources],quantity=3);wait()
        assert len(p.project.parts)==3
        s=p.project.sheets[0];s.name='300 × 240';s.price_kg=45
        i=p.inspector
        for key,value in dict(width='300',height='240',stock='8').items(): i.sheet_form.set_value(key,value)
        assert i.apply_sheet()
        p.form.set_value('quality','Hızlı')
        p.part_table.selectRow(0)
        assert p.result is None and p.canvas.mode=='part'
        shot('02-part-preview-dark')
        bad=Path(folder)/'Acik-kontur.dxf';doc=ezdxf.new();doc.units=4
        doc.modelspace().add_line((0,0),(20,0));doc.saveas(bad)
        p.import_files([str(bad)]);wait()
        failed=next(row for row in p.imports if row['status']=='error')
        p.part_tree.select_index(p.part_tree_model.index_for_id(failed['id']))
        shot('02b-import-error-dark')
        p.remove_part_button.click();assert len(p.project.parts)==3
        p.sheet_tree.setCurrentIndex(p.sheet_tree_model.by_stock[s.id].index())
        assert p.canvas.mode=='stock';shot('03-stock-preview-dark')
        i.sheet_form.fields['width'].setText('0');assert not i.apply_sheet()
        shot('03b-stock-validation-dark');i.revert_sheet()
        p.start_nest();wait();assert p.result is not None;validate_result(p.project,p.result)
        assert not p.result.unplaced
        shot('04-layout-dark')
        resize(1920,1080);shot('05-layout-wide-dark')
        resize(1366,768);w.set_theme('light');shot('06-layout-light')
        if p.sheet_tabs.count()>1:p.sheet_tabs.setCurrentIndex(1)
        p.results_action.setChecked(True);shot('07-results-light')
        p.results_action.setChecked(False);w.set_theme('dark');resize(1024,700);shot('08-compact-dark')
        p.parts_toggle.setChecked(False);shot('09-canvas-focus-dark')
        report=dict(source='Actual native Qt application and production NFP engine',
            source_inputs={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},
            fabricated_results=False,parts=len(p.result.placements),sheets=len(p.sheet_totals),
            errors='Production importer rejects a temporary open-contour DXF; invalid stock draft does not mutate the project.',
            unplaced=len(p.result.unplaced),totals=p.totals,
            screenshots=shots,qt_platform=app.platformName(),windows_exe_built=False,
            solidworks_required=False)
        (out/'capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        w.close();app.processEvents()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination')
    capture(parser.parse_args().destination)
