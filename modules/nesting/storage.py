"""Versioned, embedded geometry projects; original DXF paths need not exist."""

from dataclasses import asdict
import json
from pathlib import Path

from modules.tolerance_stack.storage import atomic_write
from modules.nesting.models import Project, Material, Part, Sheet, Options, Operations, Result, Placement, number, integer
from modules.nesting.validation import validate_result


def save_project(project, path, result=None, *, overwrite=False, stop=None, imports=None):
    project.validate(require_work=False)
    if result is not None:
        validate_result(project, result, complete=False, stop=stop)
    from modules.nesting.accounting import calculate
    payload = dict(format='GOKWORKS-NESTING', version=1, unit='mm', project=asdict(project),
                   result=asdict(result) if result else None,
                   accounting=calculate(project, result, complete=False, stop=stop) if result else None)
    if imports is not None:
        payload['import_sources'] = validate_imports(imports)
    return atomic_write(path, lambda tmp: tmp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False),
                                                        encoding='utf-8'), overwrite=overwrite, stop=stop)


def validate_imports(entries):
    if not isinstance(entries,list) or len(entries) > 10000:
        raise ValueError('DXF yükleme listesi geçersiz.')
    ids = set()
    for entry in entries:
        if (not isinstance(entry,dict) or not isinstance(entry.get('id'),str) or not entry['id'] or entry['id'] in ids
                or not isinstance(entry.get('source'),str) or not isinstance(entry.get('detail'),str)
                or entry.get('status') not in ('pending','running','success','error','cancelled')
                or not isinstance(entry.get('options'),dict)):
            raise ValueError('DXF yükleme kaydı geçersiz.')
        ids.add(entry['id'])
        options = entry['options']
        if set(options)-{'material','thickness','quantity','unit','tolerance','join_tolerance','excluded_layers','grouped'}:
            raise ValueError('DXF yükleme seçenekleri desteklenmiyor.')
        for key in ('thickness','tolerance','join_tolerance'):
            if key in options: options[key] = number(options[key],key,positive=True)
        if 'quantity' in options: options['quantity'] = integer(options['quantity'],'Adet')
        if (options.get('unit') not in (None,'mm','cm','inch') or not isinstance(options.get('material','S235JR'),str)
                or type(options.get('grouped',False)) is not bool or not isinstance(options.get('excluded_layers',[]),list)
                or not all(isinstance(layer,str) for layer in options.get('excluded_layers',[]))):
            raise ValueError('DXF birim, malzeme veya katman seçeneği geçersiz.')
    return entries


def load_project(path, *, with_imports=False):
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
        imports = validate_imports(data.get('import_sources',[]))
        if with_imports: return project, result, imports
        return project, result
    except (KeyError, TypeError, StopIteration, AttributeError) as error:
        raise ValueError('Nesting proje içeriği eksik veya hatalı.') from error
