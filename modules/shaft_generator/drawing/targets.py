"""Dimension and surface targets that really exist on a given shaft.

Every key is bound to a stable ``stage_id`` / ``operation_id``. Reordering stages
keeps the binding; deleting a stage or operation makes its keys stale, and
:func:`prune` removes them with an explicit list for the user.
"""

from ..models import Chamfer, Fillet, Groove, Keyway


def _num(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return text.replace('.', ',')


def stage_faces(project, index):
    """Planar end/shoulder faces the stage owns (annulus seen from outside)."""
    stages = project.stages
    radius = stages[index].diameter / 2
    left = index == 0 or stages[index-1].diameter / 2 < radius
    right = index == len(stages)-1 or stages[index+1].diameter / 2 < radius
    return left, right


def dimension_targets(project):
    """Ordered (key, title, nominal_mm, feature) for every dimension the planner can create.

    ``feature`` is ``'shaft'`` or ``'hole'`` for diameters (ISO fit family), else ``''``.
    """
    rows = []
    for i, stage in enumerate(project.stages, 1):
        rows.append((f'stage:{stage.id}:diameter', f'{i}. kademe · çap Ø{_num(stage.diameter)}', stage.diameter, 'shaft'))
        rows.append((f'stage:{stage.id}:length', f'{i}. kademe · boy {_num(stage.length)}', stage.length, ''))
    counts = {}
    for op in project.operations:
        counts[op.kind] = counts.get(op.kind, 0) + 1
        n = counts[op.kind]
        stage = project.stage(op.stage_id)
        if isinstance(op, Groove):
            rows += [(f'op:{op.id}:width', f'Segman {n} · genişlik {_num(op.width)}', op.width, ''),
                     (f'op:{op.id}:position', f'Segman {n} · konum {_num(op.offset)}', op.offset, ''),
                     (f'op:{op.id}:bottom_diameter', f'Segman {n} · dip çapı Ø{_num(stage.diameter-2*op.depth)}',
                      stage.diameter-2*op.depth, 'shaft')]
        elif isinstance(op, Keyway):
            rows += [(f'op:{op.id}:width', f'Kama {n} · genişlik {_num(op.width)}', op.width, ''),
                     (f'op:{op.id}:length', f'Kama {n} · boy {_num(op.length)}', op.length, ''),
                     (f'op:{op.id}:position', f'Kama {n} · konum {_num(op.offset)}', op.offset, ''),
                     (f'op:{op.id}:depth', f'Kama {n} · d − t1 = {_num(stage.diameter-op.depth)}',
                      stage.diameter-op.depth, '')]
        elif isinstance(op, (Chamfer, Fillet)):
            size = op.distance if isinstance(op, Chamfer) else op.radius
            title = 'Pah' if isinstance(op, Chamfer) else 'Radyüs'
            rows.append((f'op:{op.id}:size', f'{title} {n} · {_num(size)}', size, ''))
    if project.bore is not None:
        rows.append(('bore:diameter', f'İç delik · Ø{_num(project.bore.diameter)}', project.bore.diameter, 'hole'))
        if project.bore.end_condition == 'blind':
            rows.append(('bore:depth', f'İç delik · derinlik {_num(project.bore.depth)}', project.bore.depth, ''))
    return rows


def surface_targets(project):
    """Ordered (key, title, kind) for faces that can carry Ra, datums and frames."""
    rows = []
    for i, stage in enumerate(project.stages):
        rows.append((f'stage:{stage.id}:cylinder', f'{i+1}. kademe · silindirik dış yüzey Ø{_num(stage.diameter)}', 'cylinder'))
        left, right = stage_faces(project, i)
        if left:
            rows.append((f'stage:{stage.id}:face_left', f'{i+1}. kademe · sol alın yüzeyi', 'face'))
        if right:
            rows.append((f'stage:{stage.id}:face_right', f'{i+1}. kademe · sağ alın yüzeyi', 'face'))
    counts = {}
    for op in project.operations:
        if isinstance(op, (Groove, Keyway)):
            counts[op.kind] = counts.get(op.kind, 0) + 1
            title = 'Segman kanalı tabanı' if isinstance(op, Groove) else 'Kama kanalı tabanı'
            rows.append((f'op:{op.id}:floor', f'{title} {counts[op.kind]}', 'groove_floor' if isinstance(op, Groove) else 'keyway_floor'))
    if project.bore is not None:
        rows.append(('bore:surface', 'İç delik yüzeyi', 'bore'))
    return rows


def prune(settings, project):
    """Remove requirements whose stage/operation/surface no longer exists. Returns removed keys."""
    dims = {key for key, *_ in dimension_targets(project)}
    surfaces = {key for key, *_ in surface_targets(project)}
    removed = [key for key in settings.tolerances if key not in dims]
    removed += [key for key in settings.finishes if key not in surfaces]
    for key in removed:
        settings.tolerances.pop(key, None)
        settings.finishes.pop(key, None)
    for datum in list(settings.datums):
        if datum.target not in surfaces:
            settings.datums.remove(datum); removed.append('datum ' + datum.label)
    labels = {d.label for d in settings.datums}
    for frame in list(settings.geometric):
        if frame.target not in surfaces or any(label not in labels for label in frame.datums):
            settings.geometric.remove(frame); removed.append('geometrik tolerans ' + frame.characteristic)
    return removed


def thread_designation(diameter, pitch):
    """ISO metric designation only when (d, P) is in the verified bolt thread series."""
    from modules.bolt.rules import THREADS, FINE_PITCHES
    for name, (d, coarse) in THREADS.items():
        if abs(d - diameter) < 1e-9:
            if abs(coarse - pitch) < 1e-9:
                return name
            if any(abs(p - pitch) < 1e-9 for p in FINE_PITCHES.get(name, ())):
                return f'{name}×{_num(pitch)}'
    return None
