"""Measure native BOM filtering/layout costs with synthetic data and no COM."""

import argparse
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modules.bom.exporter import Node, Part, Result
from shared.text import BOM_TREE_TAB
from modules.pdf.window import GokworksPdfApp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    errors = []
    with TemporaryDirectory() as temporary:
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app.after_cancel(app._preload_id)
            app._preload_id = None
            app._switch_mode('bom')
            parts = tuple(Part(f'İmalat-{i:05}', f'C:/Üretim/Montaj/Parçalar/İmalat-{i:05}.sldprt',
                               'İnce sac', 1) for i in range(10000))
            nodes = tuple(Node(str(i+1), '', 1, p.name, p.name+'-1', 'Parça', p.path, p.configuration)
                          for i, p in enumerate(parts))
            result = Result('C:/Üretim/Montaj.sldasm', 'Default', parts, nodes, 0, 0, False)
            app._bom_busy(True)
            app._start_bom_render(result)
            while app.busy:
                app.update()
            until = time.monotonic()+.2
            while time.monotonic() < until:
                app.update()
            samples, tab_samples, switch_samples = [], [], []
            for _ in range(5):
                for query in ('imalat-000', 'İMALAT-000', 'imalat-009', 'olmayan', ''):
                    begin = time.perf_counter()
                    app.bom_query.set(query)
                    samples.append((time.perf_counter()-begin)*1000)
                    app.update_idletasks()
                for tab in (BOM_TREE_TAB, 'Parça listesi'):
                    begin = time.perf_counter()
                    app.bom_widgets['tabs'].set(tab)
                    app.update_idletasks()
                    tab_samples.append((time.perf_counter()-begin)*1000)
                for mode in ('pdf', 'bom'):
                    begin = time.perf_counter()
                    app._switch_mode(mode)
                    app.update_idletasks()
                    switch_samples.append((time.perf_counter()-begin)*1000)
            assert len(app.bom_widgets['parts'].get_children()) == len(parts)
            table = app.bom_widgets['parts']
            app.bom_query.set('imalat-000')
            with patch.object(table, 'set_children', wraps=table.set_children) as bulk:
                app.bom_query.set('İMALAT-000')
                same_filter_writes = bulk.call_count
            with patch.object(app.status_label, 'configure', wraps=app.status_label.configure) as status, \
                    patch.object(table, 'column', wraps=table.column) as columns:
                for _ in range(20):
                    app._resize_bom_workspace()
                layout_writes = dict(status=status.call_count, columns=columns.call_count)
            data = dict(rows=len(parts), synthetic_data=True, native_solidworks_executed=False,
                        filter_median_ms=statistics.median(samples), filter_max_ms=max(samples),
                        tab_median_ms=statistics.median(tab_samples),
                        warm_switch_median_ms=statistics.median(switch_samples),
                        equivalent_query_table_writes=same_filter_writes,
                        repeated_layout_writes=layout_writes)
            assert not errors, errors
            args.output.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(data, indent=2))
        finally:
            app._on_close()


if __name__ == '__main__':
    main()
