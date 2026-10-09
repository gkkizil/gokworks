"""Önceki şemaların hatalarını ve güncel düzeltmeleri gerçek Tk'da karşılaştır."""

import argparse
import hashlib
import json
from math import atan2, degrees
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from geometric_tolerances.diagram import draw
from geometric_tolerances.rules import specify
from pdf.window import GokworksPdfApp

BASELINE = '870f96c840caf72262d43e41cf51dd8bd67f3efc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    folder = parser.parse_args().output_dir.resolve()
    source = subprocess.check_output(['git', 'show', BASELINE+':geometric_tolerances/diagram.py'],
                                     cwd=ROOT, text=True)
    namespace = {'__name__': 'baseline_gdt_diagram'}
    exec(compile(source, 'baseline_gdt_diagram.py', 'exec'), namespace)
    records, errors = {}, []
    with TemporaryDirectory() as temp:
        app = GokworksPdfApp(settings_path=Path(temp)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app._switch_mode('geometric_tolerances')
            app.geometry('1000x690+0+0')
            app.update()
            canvas, frame = (app.gdt_widgets[key] for key in ('canvas', 'frame'))
            for label, renderer in [('before', namespace['draw']), ('after', draw)]:
                renderer(canvas, specify('angularity', '100', '0.05'))
                edge = next(item for item in canvas.find_withtag('zone') if canvas.type(item) == 'line')
                x1, y1, x2, y2 = canvas.coords(edge)
                angle = abs(degrees(atan2(y2-y1, x2-x1)))
                renderer(canvas, specify('position', '100', '0.05'))
                circle = next(item for item in canvas.find_withtag('zone') if canvas.type(item) == 'oval')
                diameter = canvas.coords(circle)[2]-canvas.coords(circle)[0]
                arrow = next(item for item in canvas.find_withtag('zone')
                             if canvas.type(item) == 'line' and canvas.itemcget(item, 'arrow') == 'both')
                arrow_length = abs(canvas.coords(arrow)[3]-canvas.coords(arrow)[1])
                renderer(frame, specify('position', '100', '999.999999', 'A | B | C'), frame=True)
                cells = [item for item in frame.find_withtag('frame') if frame.type(item) == 'rectangle']
                value = next(item for item in frame.find_withtag('frame') if frame.type(item) == 'text')
                cell, bounds = frame.coords(cells[1]), frame.bbox(value)
                fits = bounds[0] >= cell[0]+5 and bounds[2] <= cell[2]-5
                records[label] = {'angularity_degrees': angle, 'position_arrow_over_diameter': arrow_length/diameter,
                                  'long_value_fits_with_5px_padding': fits,
                                  'number_bbox': list(bounds), 'number_cell': cell}
            assert abs(records['before']['angularity_degrees']-45) > 1
            assert records['before']['position_arrow_over_diameter'] < 1
            assert not records['before']['long_value_fits_with_5px_padding']
            assert abs(records['after']['angularity_degrees']-45) < 1e-9
            assert abs(records['after']['position_arrow_over_diameter']-1) < 1e-9
            assert records['after']['long_value_fits_with_5px_padding']
            assert not errors, errors
        finally:
            app._on_close()
    folder.mkdir(parents=True, exist_ok=True)
    records.update(baseline_commit=BASELINE, baseline_diagram_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   current_diagram_sha256=hashlib.sha256((ROOT/'geometric_tolerances/diagram.py').read_bytes()).hexdigest(),
                   native_tk_measurement=True)
    (folder/'drawing-before-after.json').write_text(json.dumps(records, indent=2)+'\n')
    print(json.dumps({key: records[key] for key in ('before', 'after')}, indent=2))


if __name__ == '__main__':
    main()
