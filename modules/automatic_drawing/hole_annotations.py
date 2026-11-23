"""Native drawing annotations derived from explicit part evidence."""

from collections import defaultdict
import math
from pathlib import Path

from modules.cad_converter.api import ApiError
from .manufacturing import table_box
from .models import Box, checkpoint, to_m
from .part_features import circle, dot
from .rules import MODEL_VIEWS, VIEW_AXES
from .solidworks import call, get, hresult, null_dispatch, optional, put, values, variant

TABLE_MINIMUM = 8


def hole_groups(holes):
    groups = defaultdict(list)
    for hole in holes:
        data = tuple((name, round(value, 6) if isinstance(value, float) else value) for name, value in hole.parameters)
        checked_diameter = next((v for k, v in data if k in (
            'HoleDiameter', 'ThruHoleDiameter', 'Diameter', 'TapDrillDiameter', 'ThruTapDrillDiameter')),
            round(hole.diameter_mm, 6))
        key = (hole.wizard_type, hole.end_condition if hole.wizard_type else '', checked_diameter, data)
        groups[key].append(hole)
    return list(groups.values())


def wizard_text(holes):
    hole = holes[0]
    data = dict(hole.parameters)

    def fmt(value):
        return f'{value:.9g}'.replace('.', ',')

    diameter = next((data[k] for k in ('HoleDiameter', 'ThruHoleDiameter', 'Diameter',
                                     'TapDrillDiameter', 'ThruTapDrillDiameter', 'MinorDiameter') if k in data),
                    hole.diameter_mm)
    entry = (f'{len(holes)}× ' if len(holes) > 1 else '')+f'Ø{fmt(diameter)}'
    if hole.end_condition == 'through':
        entry += ' BOYDAN'
    elif hole.end_condition == 'blind':
        depth = next((data[k] for k in ('HoleDepth', 'Depth', 'TapDrillDepth') if k in data), None)
        if depth is not None:
            entry += f' · derinlik {fmt(depth)}'
    lines = [entry]
    if 'CounterBoreDiameter' in data and 'CounterBoreDepth' in data:
        lines.append(f"Karşı havşa Ø{fmt(data['CounterBoreDiameter'])} × {fmt(data['CounterBoreDepth'])}")
    if 'CounterDrillDiameter' in data and 'CounterDrillDepth' in data:
        lines.append(f"Kademeli delik Ø{fmt(data['CounterDrillDiameter'])} × {fmt(data['CounterDrillDepth'])}")
    for prefix, label in (('', 'Havşa'), ('Near', 'Giriş havşası'), ('Mid', 'Ara havşa'), ('Far', 'Arka havşa')):
        diameter_name, angle_name = prefix+'CounterSinkDiameter', prefix+'CounterSinkAngle'
        if diameter_name in data and angle_name in data:
            lines.append(f'{label} Ø{fmt(data[diameter_name])} × {fmt(data[angle_name])}°')
    size = data.get('FastenerSize')
    if 'ThreadDiameter' in data or 'TapDrillDiameter' in data:
        # The textual designation comes verbatim from the Wizard database.
        thread = size if isinstance(size, str) and size else (
            'Ø'+fmt(data['ThreadDiameter']) if 'ThreadDiameter' in data else '')
        if thread:
            depth = f" · derinlik {fmt(data['ThreadDepth'])}" if 'ThreadDepth' in data else ''
            lines.append(f'Diş {thread}{depth}')
    return '\n'.join(lines)


def rim_match(geometry, hole, *, check_radius=True):
    if geometry is None:
        return False
    center, axis, radius = geometry
    return (abs(dot(axis, hole.axis)) >= .9999 and
            (not check_radius or abs(radius-hole.diameter_mm/2) <= .005) and
            min(math.dist(center, rim) for rim in hole.rims_mm) <= .01)


def component_entities(native, view, kind):
    c = native.session.c
    components = values(call(view, 'GetVisibleComponents'))
    if not components:
        root = get(view, 'RootDrawingComponent')
        component = get(root, 'Component') if root is not None else None
        components = (component if component is not None else null_dispatch(),)
    for comp in components:
        yield from values(call(view, 'GetVisibleEntities2', comp, c('swViewEntityType_'+kind)))


def visible_rims(native, view):
    edges = []
    for edge in component_entities(native, view, 'Edge'):
        checkpoint(native.stop)
        geometry = circle(edge)
        if geometry is not None:
            edges.append((geometry, edge))
    return edges


def import_callouts(native, view, holes):
    flag = native.session.constants.get('swInsertholeCallout')
    if flag is None:
        return set()
    native.select_view(view)
    source = native.session.c('swImportModelItemsFromEntireModel')
    annotations = call(native.drawing, 'InsertModelAnnotations3', source, flag, False, True, False, False)
    matched = set()
    for annotation in values(annotations):
        specific = optional(annotation, 'GetSpecificAnnotation')
        if optional(specific, 'IsHoleCallout') is not True:
            continue
        for edge in values(optional(annotation, 'GetAttachedEntities3', default=())):
            if edge is None or optional(edge, 'GetCurve') is None:
                continue
            geometry = circle(edge)
            candidates = [index for index, hole in enumerate(holes) if rim_match(geometry, hole, check_radius=False)]
            if len(candidates) == 1:
                matched.add(candidates[0])
    call(native.model, 'ClearSelection2', True)
    return matched


def hole_table_tags(session, generic):
    annotation = session.named_interface(generic, 'IHoleTableAnnotation')
    feature = get(annotation, 'HoleTable')
    if feature is None or get(feature, 'CombineTags') is not False:
        return ()
    rows, headers = int(get(generic, 'RowCount')), int(call(generic, 'GetHeaderCount'))
    if not 0 <= headers < rows < 10000:
        raise ApiError('Delik tablosunun kayıtlı satır yapısı geçersiz.')
    bottom = call(generic, 'GetHeaderStyle') == session.constants.get('swTableHeader_Bottom')
    indices = range(rows-headers) if bottom else range(headers, rows)
    tags = tuple(str(optional(feature, 'HoleTag', index, property=True) or '').strip() for index in indices)
    return tags if all(tags) and len(set(tags)) == len(tags) else ()


def hole_table(native, name, view, edges):
    if len(edges) < TABLE_MINIMUM:
        return False
    session = native.session
    installed = Path(str(call(session.app, 'GetExecutablePath') or ''))
    lang = (installed if installed.is_dir() else installed.parent)/'lang'
    templates = [Path(native.options.hole_table_template)] if native.options.hole_table_template else sorted(
        (lang/'english').glob('standard hole table*letters.sldholtbt'))
    if not templates:
        return False
    page = native.pages[name]
    area = page['plan'].usable
    actual = native.actual_views(name)
    occupied = [record['outline'].grow(4.) for record in actual]+page.get('hole_tables', [])
    width, height = 100., 12.+6.*len(edges)
    if area.width < width or area.height < height:
        return False
    slots = [Box(x, y, width, height) for x in (area.x, area.right-width) for y in (area.y, area.top-height)]
    slot = next((box for box in slots if not any(box.overlaps(other) for other in occupied)), None)
    if slot is None:
        return False
    vertices = [(values(call(v, 'GetPoint')), v) for v in component_entities(native, view, 'Vertex')]
    vertices = [(point, vertex) for point, vertex in vertices if len(point) == 3]
    if not vertices:
        return False
    transform = get(view, 'ModelToViewTransform')
    vertex = min(vertices, key=lambda item: native.transform_point(item[0], transform)[:2])[1]
    native.select_view(view)
    call(native.model, 'ClearSelection2', True)
    try:
        manager = get(native.model, 'SelectionManager')
        for mark, entities in ((1, (vertex,)), (2, edges)):
            for entity in entities:
                select = call(manager, 'CreateSelectData')
                put(select, 'Mark', mark)
                put(select, 'View', view)
                if not call(session.named_interface(entity, 'IEntity'), 'Select4', True, select):
                    return False
        c = session.c
        args = False, to_m(slot.x), to_m(slot.top), c('swBOMConfigurationAnchor_TopLeft'), 'A', str(templates[0])
        try:
            table = call(view, 'InsertHoleTable3', *args, c('swHoleTableTagOrder_XY'),
                         c('swHoleTable_AlphaNumericTags'), variant(0, None))
        except Exception as error:
            if hresult(error) not in (-2147352573, -2147352570):
                raise
            table = None
        if table is None:
            table = call(view, 'InsertHoleTable2', *args)
        if table is None:
            return False
        generic = session.named_interface(table, 'ITableAnnotation')
        hole_feature = get(session.named_interface(table, 'IHoleTableAnnotation'), 'HoleTable')
        if hole_feature is not None and get(hole_feature, 'CombineTags'):
            put(hole_feature, 'CombineTags', False)
        bounds = table_box(generic)
        if (len(hole_table_tags(session, generic)) != len(edges) or not area.contains(bounds) or
                any(bounds.overlaps(other) for other in occupied)):
            annotation = call(generic, 'GetAnnotation')
            call(native.model, 'ClearSelection2', True)
            if (not call(annotation, 'Select3', False, null_dispatch()) or
                    not call(get(native.model, 'Extension'), 'DeleteSelection2', 0)):
                raise ApiError('Sığmayan delik tablosu güvenle kaldırılamadı.')
            return False
        page.setdefault('hole_tables', []).append(bounds)
        return True
    finally:
        call(native.model, 'ClearSelection2', True)


def annotate_holes(native, name):
    if not native.info.holes:
        return
    page = native.pages[name]
    base = next(v for v in page['plan'].views if v.role == 'main')
    orientation = next(key for key, value in MODEL_VIEWS.items() if value == base.model_view)
    a, b, c = VIEW_AXES[orientation]
    available = {role: normal for role, normal in (('main', c), ('top', b), ('side', a)) if role in page['views']}
    report, per_view, rim_cache = [], defaultdict(list), {}
    for members in hole_groups(native.info.holes):
        placements = defaultdict(list)
        for hole in members:
            checkpoint(native.stop)
            for role, normal in available.items():
                if abs(hole.axis[normal]) < .9999:
                    continue
                if role not in rim_cache:
                    rim_cache[role] = visible_rims(native, page['views'][role])
                # Prefer the measured rim diameter, including the outer rim of a counterbore.
                edge = next((edge for geometry, edge in rim_cache[role]
                             if rim_match(geometry, hole, check_radius=not hole.wizard_type)), None)
                if edge is None:
                    continue
                placements[role].append((hole, edge))
                break
            else:
                placements[''].append((hole, None))
        for role, items in placements.items():
            hole = items[0][0]
            row = dict(source='Hole Wizard' if hole.wizard_type else 'geometri', feature=hole.feature,
                       features=sorted({h.feature for h, _ in items if h.feature}),
                       view=str(call(page['views'][role], 'GetName2')) if role else '',
                       sheet=name, count=len(items), diameter_mm=hole.diameter_mm,
                       wizard_type=hole.wizard_type, end_condition=hole.end_condition if hole.wizard_type else '',
                       parameters=dict(hole.parameters), method='unplaced')
            report.append(row)
            if row['source'] == 'geometri':
                native.result.warn('hole_type_unknown',
                                   'Delik tipi modelden okunamadı. Çizime yalnız doğrulanan çap ölçüsü eklenir.',
                                   name, row['view'])
            if role:
                per_view[role].append((row, items))
            else:
                native.result.warn('hole_view', 'Delik için eksene dik, çember sınırı görünür bir görünüş bulunamadı.', name)
    for role, groups in per_view.items():
        view = page['views'][role]
        wizard = [(row, items) for row, items in groups if items[0][0].wizard_type]
        all_wizard = [hole for _, items in wizard for hole, _ in items]
        imported = import_callouts(native, view, all_wizard) if all_wizard else set()
        missing = {hole for index, hole in enumerate(all_wizard) if index not in imported}
        table_edges = [edge for _, items in wizard for hole, edge in items if hole in missing]
        in_table = hole_table(native, name, view, table_edges)
        for row, items in groups:
            pending = [(hole, edge) for hole, edge in items if not hole.wizard_type or hole in missing]
            row['annotated_count'] = len(items)-len(pending)
            methods = ['model_callout'] if row['annotated_count'] else []
            if row['source'] == 'Hole Wizard' and pending:
                if in_table:
                    ok = True
                    methods.append('hole_table')
                else:
                    content = wizard_text([h for h, _ in pending])
                    ok = add_hole_annotation(native, view, pending[0][1], content)
                    if ok:
                        methods.append('wizard_note')
                        page.setdefault('wizard_notes', []).append(content)
                if ok:
                    row['annotated_count'] += len(pending)
            elif pending:
                for _, edge in pending:
                    if add_hole_annotation(native, view, edge):
                        row['annotated_count'] += 1
                if row['annotated_count']:
                    methods.append('diameter')
            row['method'] = '+'.join(methods) or 'unplaced'
            if row['annotated_count'] < len(items):
                native.result.warn('hole_annotation', 'Bazı delik bilgileri çizime yerleştirilemedi.', name, row['view'])
    native.result.measurements['holes'] = report
    native.rebuild()


def add_hole_annotation(native, view, edge, text=''):
    from .native import outline
    native.select_view(view)
    call(native.model, 'ClearSelection2', True)
    if not call(view, 'SelectEntity', edge, False):
        return False
    try:
        box = outline(view)
        x, y = to_m(box.right+4.), to_m(box.top+4.)
        if text:
            note = call(native.model, 'InsertNote', text)
            if note is None:
                return False
            annotation = call(note, 'GetAnnotation')
            if int(call(annotation, 'GetLeaderCount')) <= 0:
                raise ApiError('Delik notu çizimdeki deliğe bağlanamadı.')
            if not call(annotation, 'SetPosition2', x, y, 0.):
                native.result.warn('hole_note_position', 'Delik notu varsayılan konumda bırakıldı.')
            return True
        return call(native.model, 'AddDiameterDimension2', x, y, 0.) is not None
    finally:
        call(native.model, 'ClearSelection2', True)
