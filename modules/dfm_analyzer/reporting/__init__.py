"""JSON (re-openable) and CSV (Excel-friendly) DFM reports, written atomically."""

from pathlib import Path
import json

from shared.files import write_csv_atomic, write_text_atomic
from ..models import AnalysisResult, SEVERITY_TITLES, STATUS_TITLES

CSV_HEADER = ('Kural', 'Kural adı', 'Yöntem', 'Önem', 'Parça', 'Bulgu', 'Ölçülen', 'Sınır', 'Fark', 'Birim',
              'Öneri', 'Konum (x; y mm)', 'DXF nesneleri')


def _number(value):
    return '' if value is None else f'{value:.4f}'.rstrip('0').rstrip('.').replace('.', ',')


def write_json(result, path):
    return write_text_atomic(path, result.to_json() + '\n', encoding='utf-8')


def read_json(path):
    return AnalysisResult.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def write_csv(result, path):
    rows = []
    for f in result.findings:
        bounds = f.bounds()
        where = '' if bounds is None else f'{_number((bounds[0] + bounds[2]) / 2)}; {_number((bounds[1] + bounds[3]) / 2)}'
        rows.append((f.rule_id, f.rule_name, f.process, SEVERITY_TITLES[f.severity], f.part, f.message,
                     _number(f.measured), _number(f.limit), _number(f.difference), f.unit, f.suggestion, where,
                     ', '.join(f.entities)))
    for o in result.outcomes:
        if o.status != 'FAILED':
            rows.append((o.rule_id, o.rule_name, o.process, STATUS_TITLES[o.status], '', o.reason or '',
                         '', _number(o.limit), '', o.unit, '', '', ''))
    return write_csv_atomic(path, CSV_HEADER, rows)
