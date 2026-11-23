"""Body/occurrence selection and collision-safe names, without Qt or COM."""

from collections import defaultdict
from pathlib import Path
import re


def display_rows(inventory, selected, grouped=True):
    rows = []
    for item in inventory:
        instances = tuple(item['instances'])
        chosen = selected.get(item['sheet_id'], set())
        groups = (instances,) if grouped else tuple((instance,) for instance in instances)
        for group in groups:
            count = len(set(group) & chosen)
            row = dict(item, row_id=item['sheet_id'] if grouped else item['sheet_id']+'|'+group[0],
                       quantity=len(group), instances=group, total_quantity=len(instances), grouped=grouped,
                       selected=True if count == len(group) else None if count else False)
            indexed = numbered(item)
            row['source_label'] = (f"{Path(item['source']).stem}-{item['body_index']:02d}" if indexed
                                   else item.get('code') or Path(item['source']).stem)
            if item.get('sheet_count', item.get('body_count', 1)) > 1 and not indexed:
                row['source_label'] += ' · '+item['body_name']
            row['source_label'] += ' ['+item['configuration']+']'
            if not grouped:
                row['source_label'] += ' · '+group[0].rsplit('/', 1)[-1]
            rows.append(row)
    return rows


def selected_items(inventory, selected):
    result = []
    for item in inventory:
        instances = tuple(instance for instance in item['instances'] if instance in selected.get(item['sheet_id'], set()))
        if instances and item.get('exportable'):
            result.append(dict(item, row_id=item['sheet_id'], instances=instances, quantity=len(instances)))
    return result


def numbered(item):
    """A part with several SHEET bodies names them PART-01, PART-02 … (other solids do not count)."""
    sheets = item.get('sheet_count', item.get('body_count', 1))
    return type(sheets) is int and sheets > 1 and type(item.get('body_index')) is int and item['body_index'] > 0


def safe_name(value):
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .')
    if not result:
        raise ValueError('Çıktı adı boş olamaz.')
    devices = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
               *('COM'+digit for digit in '123456789¹²³'),
               *('LPT'+digit for digit in '123456789¹²³')}
    if result.split('.')[0].rstrip(' ').upper() in devices:
        result = '_'+result
    return result


def plan_destinations(items, source, output, formats, group_by_thickness=False, naming=()):
    """Keep legacy single-part names and mm/adet tokens consumed by Nesting.

    Multi-body stems use their full-inventory persistent-ID ordinal, never the
    position in the selected subset. Configurations remain disambiguators. A digest
    resolves sanitization and same-basename/external-path collisions even when
    overwrite is enabled. One body identity is never exported twice.
    """
    from .exporter import normalize_formats, named_destinations
    formats = normalize_formats(formats)
    source=Path(source).resolve()
    by_source = defaultdict(set)
    for item in items:
        by_source[str(item['source']).lower()].add(item['configuration'])
    plans, paths = {}, defaultdict(list)
    for item in sorted(items, key=lambda r:r['sheet_id']):
        identifier = item['sheet_id']
        if identifier in plans:
            raise ValueError('Aynı sac gövdesi tekrar aktarım listesine eklendi.')
        part = Path(item['source']).resolve()
        outside=False
        try:
            relative = part.relative_to(source)
        except ValueError:
            relative = Path(part.name)
            outside=True
        chunks = [safe_name(item.get('code') or part.stem) if 'code' in naming else safe_name(part.stem)]
        # A part code that differs from the file name can be shared by two different files.
        borrowed = chunks[0] != safe_name(part.stem)
        indexed = numbered(item)
        if indexed:chunks[0] += f"-{item['body_index']:02d}"
        if not indexed and item.get('sheet_count', item.get('body_count', 1)) > 1 or 'body' in naming:
            chunks.append(safe_name(item['body_name']))
        multiple_configs = max(item.get('configuration_count',1),len(by_source[str(item['source']).lower()]))>1
        if multiple_configs or 'configuration' in naming:
            chunks.append(safe_name(item['configuration']))
        if 'material' in naming and item.get('material'):
            chunks.append(safe_name(item['material']))
        # A fixed bound leaves room for thickness/quantity and Windows paths.
        full_stem = ' - '.join(chunks)
        stem = full_stem[:140].rstrip(' .')
        # Plain names: ARMJR01 - 4 mm - 4 adet, ARMJR01-02 - 4 mm - 1 adet. A short
        # digest is added only when the name alone could point at another body:
        # truncation, a part code other than the file name (two files may share it),
        # or ARMJR01 body 01 next to a separate ARMJR01-01.SLDPRT.
        # Two selected bodies reaching the same path are separated below.
        if stem != full_stem or borrowed or item.get('numbered_name_collision'):
            stem=stem[:126].rstrip(' .')+' - '+identifier[:10]
        synthetic = Path(source) / relative.parent / (stem + '.sldprt')
        targets = named_destinations(synthetic, source, output, formats, item['thickness_mm'],
                                     item['quantity'], group_by_thickness)
        plans[identifier] = targets
        for target in targets:
            paths[str(target).replace('\\','/').lower()].append(identifier)
    collisions = {identifier for ids in paths.values() if len(ids)>1 for identifier in ids}
    for identifier in collisions:
        plans[identifier] = [p.with_name(p.stem+' - '+identifier[:12]+p.suffix) for p in plans[identifier]]
    claimed = set()
    for targets in plans.values():
        for target in targets:
            canonical = str(target).replace('\\','/').lower()
            if canonical in claimed:
                raise ValueError('Benzersiz çıktı adı oluşturulamadı; aktarım başlatılmadı.')
            claimed.add(canonical)
    return plans
