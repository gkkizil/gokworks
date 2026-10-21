"""Capture the unified parts-and-layout workspace with real DXFs and plate tabs.

QT_QPA_PLATFORM=offscreen python docs/report-tools/capture_nesting_usability.py
"""

from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

import ezdxf
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from gui_qt.app import create_application,MainWindow
from modules.nesting.validation import validate_result


def main():
    app=create_application([])
    output=ROOT/'docs/nesting-workspace'; output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gokworks-nesting-review-') as folder:
        folder=Path(folder); paths=[]
        for index in range(1,11):
            path=folder/f'PARCA-{index:02d}.dxf'; paths.append(str(path))
            doc=ezdxf.new(); doc.units=4
            doc.modelspace().add_lwpolyline([(0,0),(35,0),(35,35),(0,35)],close=True)
            doc.saveas(path)
        good=Path(paths[-1]).read_bytes(); Path(paths[-1]).write_text('Invalid DXF\n')
        w=MainWindow(folder/'settings.json'); w.resize(1440,960); w.show(); w.navigate('nesting')
        page=w.pages['nesting']

        def wait():
            deadline=time.monotonic()+20
            while w.jobs.busy:
                app.processEvents()
                if time.monotonic()>deadline: raise TimeoutError('Nesting capture timed out')
                # Release the Python GIL between UI batches, as app.exec does
                # in normal use. A tight native qWait loop starves the worker.
                time.sleep(.005)
            QTest.qWait(80)

        def capture(name):
            QTest.qWait(80)
            page.canvas.fit()
            assert w.grab().save(str(output/name))

        page.import_files(paths); wait()
        assert len(page.project.parts)==9 and page.part_model.rowCount()==10
        capture('01-parts-dark.png')
        w.resize(1440,900)
        failed=next(e for e in page.imports if e['status']=='error')
        Path(paths[-1]).write_bytes(good)
        page.import_files([paths[-1]],retry_id=failed['id']); wait()
        sheet=page.project.sheets[0]
        sheet.width=sheet.height=100; sheet.name='100 × 100'; sheet.price_kg=45
        page.form.set_value('margin','5'); page.form.set_value('quality','Hızlı'); page.form.set_value('seconds','5')
        page.refresh(); page.show_settings(); QTest.qWait(80)
        assert page.settings_dialog.grab().save(str(output/'02-stock-dark.png'))
        page.settings_dialog.reject()
        page.start_nest(); wait()
        assert validate_result(page.project,page.result)
        counts=Counter(p.sheet_number for p in page.result.placements)
        assert counts=={1:4,2:4,3:2} and page.sheet_tabs.count()==3
        page.sheet_tabs.setCurrentIndex(1)
        assert page.canvas.key==(sheet.id,2)
        selected=next(i for i in range(page.part_proxy.rowCount()) if page.part_proxy.index(i,0).data(Qt.UserRole)['id'] in page.canvas.part_items)
        page.part_table.selectRow(selected)
        capture('03-plates-dark.png')
        w.set_theme('light'); capture('04-plates-light.png')
        w.set_theme('dark'); w.resize(1024,700); capture('05-plates-small.png')
        w.resize(820,560); capture('06-plates-minimum.png')
        page.parts_toggle.click(); capture('07-drawing-focus.png')
        (output/'capture.json').write_text(json.dumps(dict(
            source='Real Qt workspace, ten generated DXFs, production import and NFP engine; no fabricated placements.',
            selected=10,ready_before_retry=9,failed_before_retry=1,ready_after_retry=10,
            part_count=len(page.result.placements),plates=3,parts_per_plate=dict(counts),
            selected_plate=2,validated=True,engine=page.result.engine,engine_version=page.result.engine_version,
            screenshots=['01-parts-dark.png','02-stock-dark.png','03-plates-dark.png','04-plates-light.png','05-plates-small.png','06-plates-minimum.png','07-drawing-focus.png'],
            windows_exe_built=False,solidworks_required=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        assert w.settings.flush(); w.close()


if __name__=='__main__': main()
