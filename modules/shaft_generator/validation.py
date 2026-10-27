"""Conservative manufacturing geometry checks, before any CAD connection."""

import math
from .models import Groove, Keyway, Chamfer, Fillet, OPERATION_TYPES


def number(value, *, positive=True):
    return type(value) in (int, float) and math.isfinite(value) and (1e-5 <= value <= 1e6 if positive else 0 <= value <= 1e6)


def validate(project):
    errors = []
    if not isinstance(project.name, str) or not project.name.strip() or len(project.name) > 80 or any(c in project.name for c in '\\/:*?"<>|') or any(ord(c)<32 for c in project.name):
        errors.append('Parça adı 1–80 karakter olmalı; dosya adı için geçersiz karakter içeremez.')
    if not number(project.minimum_wall):
        errors.append('En az kalan radyal et kalınlığı pozitif ve sonlu olmalı.')
    if not 1 <= len(project.stages) <= 100:
        errors.append('1–100 kademe gerekli.')
    if len(project.operations) > 200:
        errors.append('En fazla 200 operasyon desteklenir.')
    ids = [s.id for s in project.stages] + [op.id for op in project.operations]
    if any(not isinstance(v, str) or not v or len(v) > 80 for v in ids) or len(set(map(str, ids))) != len(ids):
        errors.append('Kademe ve operasyon kimlikleri benzersiz, geçerli metin olmalı.')
    for i, stage in enumerate(project.stages, 1):
        for title, value in (('çap', stage.diameter), ('boy', stage.length)):
            if not number(value):
                errors.append(f'{i}. kademe: {title} 0,00001–1.000.000 mm arasında ve sonlu olmalı.')
    # Never evaluate arithmetic on invalid cells (NaN, strings, overflow).
    if errors:
        return errors
    if not number(project.total_length):
        errors.append('Toplam boy 1.000.000 mm sınırını aşıyor.')
    intervals = []
    edges = set()
    shoulders = []
    for op in project.operations:
        index = next((i for i, s in enumerate(project.stages) if s.id == op.stage_id), None)
        if index is None:
            errors.append('Operasyonun hedef kademesi bulunamadı.')
            continue
        stage = project.stages[index]
        title = {'groove': 'Segman kanalı', 'keyway': 'Kama kanalı',
                 'chamfer': 'Pah', 'fillet': 'Radyüs'}.get(op.kind, op.kind)
        if isinstance(op, (Chamfer, Fillet)):
            title += ' · ' + {'left': 'Sol', 'right': 'Sağ'}.get(op.edge, str(op.edge))
        prefix = f'{index + 1}. kademe ({title}): '
        if type(op) not in OPERATION_TYPES.values():
            errors.append(prefix + 'desteklenmeyen operasyon.')
            continue
        values = {key: value for key, value in vars(op).items() if key not in ('id', 'kind', 'stage_id', 'edge')}
        bad = [key for key, value in values.items() if not number(value, positive=key not in ('offset', 'angle'))]
        if bad:
            errors.append(prefix + 'geçersiz sayısal alan: ' + ', '.join(bad))
            continue
        radius = stage.diameter / 2
        if isinstance(op, (Groove, Keyway)):
            extent = op.width if isinstance(op, Groove) else op.length
            if op.offset + extent > stage.length + 1e-8:
                errors.append(prefix + 'kanal kademe sınırlarını aşıyor.')
            if radius - op.depth < project.minimum_wall:
                errors.append(prefix + f'Ø{stage.diameter:g} mm üzerinde {op.depth:g} mm radyal derinlik, {project.minimum_wall:g} mm et bırakmıyor.')
            if isinstance(op, Keyway):
                if op.length - op.width < 1e-5:
                    errors.append(prefix + 'yuvarlak uçlu kama kanalının toplam boyu genişliğinden en az 0,00001 mm büyük olmalı.')
                if op.angle != 0:
                    errors.append(prefix + 'bu sürümde kama açısı yalnız 0° desteklenir.')
                # Slot floor must meet the cylinder over its entire width.
                if op.width >= stage.diameter or (op.width / 2) ** 2 + (radius - op.depth) ** 2 >= radius ** 2:
                    errors.append(prefix + 'kama genişliği/derinliği silindirin tamamında geçerli bir taban oluşturmuyor.')
            intervals.append((op.stage_id, op.offset, op.offset + extent, prefix))
        else:
            if op.edge not in ('left', 'right'):
                errors.append(prefix + 'kenar sol veya sağ olmalı.')
                continue
            neighbor_index = index - 1 if op.edge == 'left' else index + 1
            neighbor = project.stages[neighbor_index] if 0 <= neighbor_index < len(project.stages) else None
            radial_room = abs(radius - neighbor.diameter / 2) if neighbor else radius
            size = op.distance if isinstance(op, Chamfer) else op.radius
            if size >= min(radial_room, stage.length, neighbor.length if neighbor else stage.length):
                errors.append(prefix + 'pah/radyüs omuz yüksekliği, yarıçap veya komşu boy için fazla büyük; eş çap geçişinde kenar yok.')
            if isinstance(op, Chamfer) and op.angle != 45:
                errors.append(prefix + 'bu sürümde yalnız 45° eş mesafeli pah desteklenir.')
            edge_key = (project.end(stage.id) if op.edge == 'right' else project.start(stage.id), radius)
            if edge_key in edges:
                errors.append(prefix + 'aynı kenarda birden fazla pah/radyüs uygulanamaz.')
            edges.add(edge_key)
            start = 0 if op.edge == 'left' else stage.length - size
            intervals.append((stage.id, start, start + size, prefix))
            # Each circular corner consumes axial room on its OWN stage. A
            # blanket neighbor interval falsely clashes the two radial edges
            # of one annular shoulder, even when they are far apart.
            if neighbor:
                shoulders.append((edge_key[0], radius, size, prefix))
    for i, (position, radius, size, prefix) in enumerate(shoulders):
        for other_position, other_radius, other_size, other_prefix in shoulders[:i]:
            radial_gap = abs(radius - other_radius)
            if position == other_position and radial_gap > 1e-8 and size + other_size > radial_gap + 1e-8:
                total = f'{size + other_size:g}'.replace('.', ',')
                gap = f'{radial_gap:g}'.replace('.', ',')
                errors.append(prefix + other_prefix.rstrip(': ') + ' ile ortak omuzda yeterli yer yok. '
                              + f'İki pah/radyüs toplamı {total} mm; omuz yüksekliği {gap} mm.')
    for i, (stage_id, start, end, prefix) in enumerate(intervals):
        for other_id, other_start, other_end, other_prefix in intervals[:i]:
            if stage_id == other_id and min(end, other_end) - max(start, other_start) > 1e-8:
                errors.append(prefix + 'operasyonlar çakışıyor: ' + other_prefix.rstrip(': '))
    return errors


def require_valid(project):
    errors = validate(project)
    if errors:
        raise ValueError('\n'.join(errors))
