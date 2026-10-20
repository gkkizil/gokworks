"""Capture real ten-file import/error/retry and sequential three-plate placement."""

from collections import Counter
import json
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import ezdxf
from gui_qt.app import create_application,MainWindow
from nesting.validation import validate_result


def main():
    app = create_application([])
    output = ROOT/'docs/nesting-bulk'; output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gokworks-bulk-capture-') as folder:
        folder = Path(folder); files = []
        for index in range(1,11):
            path = folder/f'P{index:02d}.dxf'; files.append(str(path))
            doc = ezdxf.new(); doc.units = 4
            doc.modelspace().add_lwpolyline([(0,0),(35,0),(35,35),(0,35)],close=True); doc.saveas(path)
        original = Path(files[-1]).read_text()
        Path(files[-1]).write_text(re.sub(r'\n *10\n','\nBAD-CODE\n',original,count=1))
        w = MainWindow(folder/'settings.json'); w.resize(1440,960); w.show(); w.navigate('nesting')
        page = w.pages['nesting']
        def wait():
            started = time.monotonic()
            while w.jobs.busy:
                app.processEvents()
                if time.monotonic()-started > 15: raise TimeoutError('Capture job timed out')
                time.sleep(.005)
            app.processEvents()
        page.import_files(files); wait()
        assert len(page.project.parts) == 9 and page.part_model.rowCount() == 10
        assert sum(e['status'] == 'error' for e in page.imports) == 1
        assert w.grab().save(str(output/'bulk-import-dark.png'))
        broken = next(e for e in page.imports if e['status'] == 'error')
        Path(files[-1]).write_text(original)
        page.import_files([files[-1]],retry_id=broken['id']); wait()
        assert len(page.project.parts) == 10 and len(page.imports) == 10
        page.project.sheets[0].width = page.project.sheets[0].height = 100
        page.project.sheets[0].name = '100 × 100'; page.project.sheets[0].price_kg = 45
        page.form.set_value('margin','5'); page.form.set_value('quality','Hızlı'); page.form.set_value('seconds','5')
        page.start_nest(); wait()
        assert validate_result(page.project,page.result) and page.sheet_picker.count() == 3
        counts = Counter(p.sheet_number for p in page.result.placements)
        assert counts == {1:4,2:4,3:2}
        page.sheet_picker.setCurrentIndex(2); app.processEvents(); page.canvas.fit()
        assert w.grab().save(str(output/'three-plates-dark.png'))
        (output/'checks.json').write_text(json.dumps(dict(selected=10,ready_before_retry=9,errors_before_retry=1,
            ready_after_retry=10,plates=3,parts_per_plate=counts,validated=True,engine_version=page.result.engine_version),indent=2)+'\n')
        assert w.settings.flush(); w.close()


if __name__ == '__main__': main()
