"""Conservative manufacturing geometry checks, before any CAD connection."""

import math
from .models import Bore, CosmeticThread, Groove, Keyway, Chamfer, Fillet, OPERATION_TYPES


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
    bore_span = None
    if project.bore is not None:
        b = project.bore
        if (type(b) is not Bore or not number(b.diameter) or not number(b.depth)
                or b.entry not in ('left','right') or b.end_condition not in ('through_all','blind')):
            return errors + ['İç delik: çap, derinlik, giriş veya sonlandırma geçersiz.']
        if b.end_condition == 'blind' and b.depth >= project.total_length-1e-5:
            return errors + ['İç delik: kör delik derinliği toplam mil boyundan kısa olmalı.']
        bore_span = b.interval(project.total_length)
        for i,s in enumerate(project.stages,1):
            bottom=bore_span[1] if b.entry=='left' else bore_span[0]
            touches_bottom=b.end_condition=='blind' and project.start(s.id)-1e-8 <= bottom <= project.end(s.id)+1e-8
            if touches_bottom or min(project.end(s.id),bore_span[1])-max(project.start(s.id),bore_span[0]) > 1e-8:
                if (s.diameter-b.diameter)/2 < project.minimum_wall:
                    errors.append(f'{i}. kademe: iç delik en az radyal et kalınlığını bırakmıyor.')
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
        elif isinstance(op, CosmeticThread):
            if op.edge not in ('left','right'):
                errors.append(prefix + 'kenar sol veya sağ olmalı.');continue
            if stage.diameter-1.226869*op.pitch <= 0:
                errors.append(prefix + 'diş adımı mil çapı için fazla büyük.')
            start,end = project.thread_interval(op)
            # The thread occupies an uninterrupted cylindrical land; end
            # treatments may touch its ends but may not consume its length.
            if start < -1e-8 or end > stage.length+1e-8:
                errors.append(prefix + 'diş boyu kademe sınırlarını aşıyor.')
            neighbor_index = index-1 if op.edge=='left' else index+1
            if 0 <= neighbor_index < len(project.stages) and project.stages[neighbor_index].diameter == stage.diameter:
                errors.append(prefix + 'eş çap geçişinde kozmetik diş başlangıcı için dairesel kenar yok.')
            intervals.append((stage.id,start,end,prefix))
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
        if bore_span is not None:
            if isinstance(op,CosmeticThread):
                start,end=project.thread_interval(op);extent=end-start;consumed=.6134345*op.pitch
            else:
                extent = op.width if isinstance(op,Groove) else op.length if isinstance(op,Keyway) else size
                start = op.offset if isinstance(op,(Groove,Keyway)) else 0 if op.edge=='left' else stage.length-size
                consumed = op.depth if isinstance(op,(Groove,Keyway)) else 0 if neighbor and neighbor.diameter>stage.diameter else size
            a,b = project.start(stage.id)+start,project.start(stage.id)+start+extent
            if min(b,bore_span[1])-max(a,bore_span[0]) > 1e-8:
                if radius-consumed-project.bore.diameter/2 < project.minimum_wall:
                    errors.append(prefix + 'iç delik ile operasyon arasında en az radyal et kalınlığı kalmıyor.')
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
