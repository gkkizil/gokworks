"""Versioned, embedded geometry projects; original DXF paths need not exist."""

from dataclasses import asdict
import json
from pathlib import Path

from tolerance_stack.storage import atomic_write
from .models import Project, Material, Part, Sheet, Options, Operations, Result, Placement
from .validation import validate_result


def save_project(project, path, result=None, *, overwrite=False, stop=None):
    project.validate(require_work=False)
    if result is not None:
        validate_result(project, result, complete=False, stop=stop)
    from .accounting import calculate
    payload = dict(format='GOKWORKS-NESTING', version=1, unit='mm', project=asdict(project),
                   result=asdict(result) if result else None,
                   accounting=calculate(project, result, complete=False, stop=stop) if result else None)
    return atomic_write(path, lambda tmp: tmp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False),
                                                        encoding='utf-8'), overwrite=overwrite, stop=stop)


def load_project(path):
    path = Path(path)
    if path.stat().st_size > 100*1024*1024:
        raise ValueError('Nesting projesi 100 MB sınırını aşıyor.')
    def invalid(value):
        raise ValueError('JSON içinde sonlu olmayan sayı.')
    try:
        data = json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid)
        if data.get('format') != 'GOKWORKS-NESTING' or type(data.get('version')) is not int or data['version'] != 1 or data.get('unit') != 'mm':
            raise ValueError('Nesting proje biçimi veya sürümü desteklenmiyor.')
        raw = data['project']
        project = Project(raw['name'], [Material(**m) for m in raw['materials']], [Part(**p) for p in raw['parts']],
                          [Sheet(**s) for s in raw['sheets']], Options(**raw['options']), Operations(**raw['operations']))
        project.validate(require_work=False)
        result = None
        if data.get('result'):
            r = dict(data['result']); r['placements'] = [Placement(**p) for p in r['placements']]
            result = Result(**r)
            validate_result(project, result, complete=False)
        return project, result
    except (KeyError, TypeError, StopIteration, AttributeError) as error:
        raise ValueError('Nesting proje içeriği eksik veya hatalı.') from error
