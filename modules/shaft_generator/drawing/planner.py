"""Build the complete, CAD-independent drawing plan for one shaft project.

The plan names every dimension, note, surface symbol, datum and frame with the
real geometry it belongs to (axial position ``x`` and radius ``r`` in mm along
the shaft axis, measured from the left end face). The SOLIDWORKS host matches
those references to actual model edges/faces and refuses anything it cannot
match; nothing is placed by guessing screen coordinates.
"""

from ..geometry import profile
from ..models import Chamfer, CosmeticThread, Fillet, Groove, Keyway
from ..validation import validate as validate_project
from . import layout as layout_engine
from .models import CHARACTERISTICS, DrawingSettings
from .targets import dimension_targets, prune, stage_faces, surface_targets, thread_designation
from .tolerances import resolve

PLAN_VERSION = 1
EPS = 1e-6


def _num(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return text.replace('.', ',')


def segments(project):
    """Maximal runs of equal diameter: the physical cylinders of the shaft."""
    rows = []
    for i, stage in enumerate(project.stages):
        x0, x1 = project.boundaries[i], project.boundaries[i+1]
        if rows and abs(rows[-1]['r'] - stage.diameter / 2) < EPS:
            rows[-1]['x1'] = x1; rows[-1]['stage_ids'].append(stage.id)
        else:
            rows.append(dict(x0=x0, x1=x1, r=stage.diameter / 2, stage_ids=[stage.id]))
    return rows


class _Plan:
    def __init__(self, project, settings):
        self.project, self.settings = project, settings
        self.errors, self.warnings = [], []
        self.dimensions, self.notes, self.finishes, self.datums, self.frames = [], [], [], [], []
        self.views = [dict(id='main', kind='main', hidden_lines=project.bore is not None)]
        self.dimension_titles = {key: (title, nominal, feature) for key, title, nominal, feature in dimension_targets(project)}
        self.surfaces = {key: (title, kind) for key, title, kind in surface_targets(project)}
        self.used_tolerances = set()

    # -- tolerances -----------------------------------------------------
    def tolerance(self, target, nominal, feature=''):
        spec = self.settings.tolerances.get(target)
        if spec is None or spec.kind == 'none':
            return None
        self.used_tolerances.add(target)
        try:
            return resolve(spec, nominal, feature).as_dict()
        except ValueError as error:
            self.errors.append(f'{self.dimension_titles.get(target, (target,))[0]}: {error}')
            return None

    def add_dimension(self, target, view, kind, refs, nominal, *, prefix='', band='below', span=None,
                      reference=False, label=None, feature='', priority=5, text=None):
        tolerance = None if reference else self.tolerance(target, nominal, feature)
        base = text or f'{prefix}{_num(nominal)}'
        shown = f'({base})' if reference else base
        if tolerance:
            shown += ' ' + tolerance['text']
        x0, x1 = span if span else (refs[0].get('x', refs[0].get('x0', 0)), refs[-1].get('x', refs[-1].get('x1', 0)))
        self.dimensions.append(dict(
            id=f'dim:{len(self.dimensions)+1:03d}', target=target, view=view, kind=kind, refs=refs,
            nominal_mm=nominal, prefix=prefix, reference=reference, tolerance=tolerance,
            label=label or self.dimension_titles.get(target, (target,))[0], text=shown,
            band=band, x0_mm=min(x0, x1), x1_mm=max(x0, x1), priority=priority))

    # -- geometry -------------------------------------------------------
    def build(self):
        p, s = self.project, self.settings
        self.segments = segments(p)
        if len(self.segments) < len(p.stages):
            merged = [seg for seg in self.segments if len(seg['stage_ids']) > 1]
            self.warnings.append(f'{len(merged)} eşit çaplı kademe birleşimi fiziksel omuz değildir; '
                                 'bu sınırlarda boy ölçüsü oluşturulmaz.')
        self.diameters(); self.lengths(); self.operations(); self.bore()
        self.surface_requirements(); self.datum_requirements(); self.frame_requirements()
        stale = [k for k in s.tolerances if k not in self.dimension_titles]
        if stale:
            self.errors.append(f'{len(stale)} tolerans artık var olmayan kademe/operasyona bağlı. Teknik resim ayarlarını gözden geçirin.')

    def diameters(self):
        for seg in self.segments:
            keys = [f'stage:{sid}:diameter' for sid in seg['stage_ids']]
            specs = {repr(self.settings.tolerances[k]) for k in keys if k in self.settings.tolerances}
            if len(specs) > 1:
                self.errors.append('Aynı silindiri paylaşan eşit çaplı kademelere farklı çap toleransı verilmiş: '
                                   + ', '.join(self.dimension_titles[k][0] for k in keys))
            target = next((k for k in keys if k in self.settings.tolerances), keys[0])
            self.add_dimension(target, 'main', 'diameter',
                               [dict(type='circle_in', x0=seg['x0'], x1=seg['x1'], r=seg['r'])],
                               seg['r'] * 2, prefix='Ø', band='inside', span=(seg['x0'], seg['x1']),
                               feature='shaft', priority=1)
            for extra in keys:
                if extra != target and extra in self.settings.tolerances:
                    self.used_tolerances.add(extra)

    def lengths(self):
        segs, total = self.segments, self.project.total_length
        cuts = [seg['x1'] for seg in segs[:-1]]
        scheme = self.settings.scheme
        stage_of = {}
        for seg in segs:
            for sid in seg['stage_ids']:
                stage_of[sid] = seg
        length_keys = {}
        for seg in segs:
            if len(seg['stage_ids']) == 1:
                length_keys[(seg['x0'], seg['x1'])] = f'stage:{seg["stage_ids"][0]}:length'
        if scheme == 'baseline':
            for x in cuts:
                self.add_dimension(None, 'main', 'distance', [dict(type='plane_x', x=0.), dict(type='plane_x', x=x)],
                                   x, band='below', label=f'Sol uçtan {_num(x)}', priority=3)
            self.add_dimension('total', 'main', 'distance', [dict(type='plane_x', x=0.), dict(type='plane_x', x=total)],
                               total, band='below', label='Toplam boy', priority=9)
            for key, spec in self.settings.tolerances.items():
                if key.endswith(':length') and spec.kind != 'none':
                    self.used_tolerances.add(key)
                    self.warnings.append(f'{self.dimension_titles.get(key, (key,))[0]}: ortak referans ölçülendirmede '
                                         'kademe boyu ölçüsü yoktur; tolerans uygulanmadı. Zincir veya karma yöntem seçin.')
            return
        chain = segs if scheme == 'chain' else segs[:-1]
        for seg in chain:
            key = length_keys.get((seg['x0'], seg['x1']))
            self.add_dimension(key, 'main', 'distance', [dict(type='plane_x', x=seg['x0']), dict(type='plane_x', x=seg['x1'])],
                               seg['x1'] - seg['x0'], band='below', label=self.dimension_titles.get(key, ('Kademe boyu',))[0],
                               priority=3)
        if scheme == 'mixed':
            last = segs[-1]
            key = length_keys.get((last['x0'], last['x1']))
            if key and key in self.settings.tolerances and self.settings.tolerances[key].kind != 'none':
                self.used_tolerances.add(key)
                self.warnings.append(f'{self.dimension_titles[key][0]}: karma ölçülendirmede son kademe boyu kapalı zinciri '
                                     'önlemek için ölçülmez; tolerans uygulanmadı.')
        if scheme == 'mixed' or self.settings.total_length_reference:
            self.add_dimension('total', 'main', 'distance', [dict(type='plane_x', x=0.), dict(type='plane_x', x=total)],
                               total, band='below', reference=(scheme == 'chain'), label='Toplam boy', priority=9)

    def neighbor_radius(self, index, edge):
        j = index - 1 if edge == 'left' else index + 1
        if 0 <= j < len(self.project.stages):
            return self.project.stages[j].diameter / 2
        return None

    def operations(self):
        p, s = self.project, self.settings
        counts = {}
        groups = {}
        for op in p.operations:
            counts[op.kind] = counts.get(op.kind, 0) + 1
            n = counts[op.kind]
            index = next(i for i, st in enumerate(p.stages) if st.id == op.stage_id)
            stage = p.stages[index]
            r = stage.diameter / 2
            start = p.boundaries[index]
            if isinstance(op, Groove):
                x0, x1, rb = start + op.offset, start + op.offset + op.width, r - op.depth
                view = 'main'
                if s.detail_views and layout_engine.needs_detail(op.width, self._factor()):
                    view = f'detail:{op.id}'
                    self.views.append(dict(id=view, kind='detail', parent='main', center=[(x0+x1)/2, r],
                                           radius=max(op.width, op.depth) * 2.5,
                                           enlargement=layout_engine.detail_enlargement(op.width, self._factor()),
                                           label=f'Segman {n}'))
                self.add_dimension(f'op:{op.id}:width', view, 'distance',
                                   [dict(type='circle', x=x0, r=rb), dict(type='circle', x=x1, r=rb)], op.width,
                                   band='above', priority=4)
                self.add_dimension(f'op:{op.id}:bottom_diameter', view, 'diameter',
                                   [dict(type='circle_in', x0=x0, x1=x1, r=rb)], rb * 2, prefix='Ø',
                                   band='inside', span=(x0, x1), feature='shaft', priority=2)
                origin = start if stage_faces(p, index)[0] else 0.
                self.add_dimension(f'op:{op.id}:position', 'main', 'distance',
                                   [dict(type='plane_x', x=origin), dict(type='circle', x=x0, r=rb)], x0 - origin,
                                   band='above', priority=4)
            elif isinstance(op, Keyway):
                x0, x1 = start + op.offset, start + op.offset + op.length
                floor = r - op.depth
                if not any(v['id'] == 'top' for v in self.views):
                    self.views.append(dict(id='top', kind='projected', parent='main', direction='radial'))
                if s.keyway_section and not any(v.get('op') == op.id for v in self.views):
                    label = chr(ord('A') + sum(v['kind'] == 'section' for v in self.views))
                    self.views.append(dict(id=f'section:{op.id}', kind='section', parent='main', x=(x0 + x1) / 2,
                                           label=label, op=op.id))
                half = op.width / 2
                self.add_dimension(f'op:{op.id}:width', 'top', 'distance',
                                   [dict(type='line', y=floor, z=-half, x0=x0+half, x1=x1-half),
                                    dict(type='line', y=floor, z=half, x0=x0+half, x1=x1-half)], op.width,
                                   band='inside', span=(x0, x1), priority=2)
                self.add_dimension(f'op:{op.id}:length', 'top', 'keyway_length',
                                   [dict(type='arc', x=x0+half, y=floor, radius=half, condition='max'),
                                    dict(type='arc', x=x1-half, y=floor, radius=half, condition='max')], op.length,
                                   band='above', span=(x0, x1), priority=4)
                origin = start if stage_faces(p, index)[0] else 0.
                self.add_dimension(f'op:{op.id}:position', 'top', 'keyway_position',
                                   [dict(type='plane_x', x=origin),
                                    dict(type='arc', x=x0+half, y=floor, radius=half, condition='min')], x0 - origin,
                                   band='above', span=(origin, x0), priority=4)
                # DIN 6885 drawings give the remaining material d − t1 from the floor
                # to the opposite generatrix; the floor is a real model edge.
                self.add_dimension(f'op:{op.id}:depth', 'main', 'keyway_depth',
                                   [dict(type='line', y=floor, z=half, x0=x0+half, x1=x1-half),
                                    dict(type='silhouette', x0=x0, x1=x1, y=-r)], stage.diameter - op.depth,
                                   band='inside', span=(x0, x1), priority=2)
            elif isinstance(op, (Chamfer, Fillet)):
                size = op.distance if isinstance(op, Chamfer) else op.radius
                x = start if op.edge == 'left' else p.boundaries[index+1]
                neighbor = self.neighbor_radius(index, op.edge)
                concave = neighbor is not None and neighbor > r + EPS
                ref = dict(type='circle', x=x, r=(r + size) if concave else (r - size))
                tolerance = s.tolerances.get(f'op:{op.id}:size')
                key = (op.kind, round(size, 9), round(getattr(op, 'angle', 0), 9), repr(tolerance))
                groups.setdefault(key, []).append((op, ref))
            elif isinstance(op, CosmeticThread):
                designation = thread_designation(stage.diameter, op.pitch)
                if designation is None:
                    self.warnings.append(f'Kozmetik diş Ø{_num(stage.diameter)} × {_num(op.pitch)}: doğrulanmış ISO metrik '
                                         'diş serisinde yok; teknik resme diş bilgisi yazılmadı.')
                    continue
                a, b = p.thread_interval(op)
                self.notes.append(dict(id=f'note:thread:{op.id}', target=f'op:{op.id}', view='main',
                                       text=f'{designation} - {_num(op.length)}',
                                       ref=dict(type='circle_in', x0=start + a, x1=start + b, r=r),
                                       band='above', x0_mm=start + a, x1_mm=start + b))
        for (kind, size, angle, _), members in groups.items():
            op, ref = members[0]
            count = f'{len(members)}× ' if len(members) > 1 else ''
            target = f'op:{op.id}:size'
            tolerance = self.tolerance(target, size)
            for other, _ in members[1:]:
                if f'op:{other.id}:size' in s.tolerances:
                    self.used_tolerances.add(f'op:{other.id}:size')
            text = (f'{count}{_num(size)} × {_num(angle)}°' if kind == 'chamfer' else f'{count}R{_num(size)}')
            if tolerance:
                text += ' ' + tolerance['text']
            self.notes.append(dict(id=f'note:{kind}:{op.id}', target=target, view='main', text=text, ref=ref,
                                   members=[m.id for m, _ in members], tolerance=tolerance,
                                   band='above', x0_mm=ref['x'], x1_mm=ref['x']))

    def bore(self):
        b, total = self.project.bore, self.project.total_length
        if b is None:
            return
        a, z = b.interval(total)
        end = 'left' if a < EPS else 'right'
        view = 'side_left' if end == 'left' else 'side_right'
        self.views.append(dict(id=view, kind='projected', parent='main', direction='axial_' + end))
        entry = 0. if end == 'left' else total
        self.add_dimension('bore:diameter', view, 'diameter',
                           [dict(type='circle', x=entry, r=b.diameter / 2)], b.diameter, prefix='Ø',
                           band='inside', span=(0, 0), feature='hole', priority=1)
        if b.end_condition == 'blind':
            bottom = z if end == 'left' else a
            self.add_dimension('bore:depth', 'main', 'distance',
                               [dict(type='plane_x', x=entry), dict(type='circle', x=bottom, r=b.diameter / 2)],
                               b.depth, band='above', priority=6)

    def _factor(self):
        if not hasattr(self, '_sheet_factor'):
            chosen = layout_engine.choose_sheet(self.project.total_length, self.project.maximum_diameter,
                                                ['top'], size=self.settings.sheet_size,
                                                scale_mode=self.settings.scale_mode, scale=tuple(self.settings.scale))
            self._sheet_factor = chosen.factor
        return self._sheet_factor

    # -- requirements on surfaces --------------------------------------
    def surface_ref(self, key):
        p = self.project
        kind = self.surfaces[key][1]
        if key == 'bore:surface':
            a, z = p.bore.interval(p.total_length)
            return dict(type='cylinder', x0=a, x1=z, r=p.bore.diameter / 2, inner=True), 'main'
        scope, ident, part = key.split(':')
        if scope == 'stage':
            index = next(i for i, st in enumerate(p.stages) if st.id == ident)
            stage = p.stages[index]; r = stage.diameter / 2
            x0, x1 = p.boundaries[index], p.boundaries[index+1]
            if part == 'cylinder':
                return dict(type='cylinder', x0=x0, x1=x1, r=r), 'main'
            neighbor = self.neighbor_radius(index, 'left' if part == 'face_left' else 'right')
            x = x0 if part == 'face_left' else x1
            return dict(type='plane', x=x, r_in=(neighbor or 0.), r_out=r), 'main'
        op = next(o for o in p.operations if o.id == ident)
        index = next(i for i, st in enumerate(p.stages) if st.id == op.stage_id)
        r = p.stages[index].diameter / 2; start = p.boundaries[index]
        if kind == 'groove_floor':
            return dict(type='cylinder', x0=start + op.offset, x1=start + op.offset + op.width, r=r - op.depth), 'main'
        return dict(type='keyway_floor', x0=start + op.offset, x1=start + op.offset + op.length, y=r - op.depth), 'top'

    def surface_requirements(self):
        s = self.settings
        requested = dict(s.finishes)
        if s.default_finish is not None:
            # Opt-in bulk value for machined cylinders; per-surface entries override it.
            for key, (_, kind) in self.surfaces.items():
                if kind == 'cylinder' and key not in requested:
                    requested[key] = s.default_finish
        for key, finish in requested.items():
            if key not in self.surfaces:
                self.errors.append(f'Yüzey pürüzlülüğü artık var olmayan yüzeye bağlı: {key}')
                continue
            ref, view = self.surface_ref(key)
            text = f'Ra {_num(finish.ra)}'
            self.finishes.append(dict(id=f'sf:{len(self.finishes)+1:03d}', target=key, view=view, surface=ref,
                                      ra=finish.ra, process=finish.process, method=finish.method, lay=finish.lay,
                                      text=text, title=self.surfaces[key][0], band='above',
                                      x0_mm=ref.get('x0', ref.get('x', 0)), x1_mm=ref.get('x1', ref.get('x', 0))))

    def datum_requirements(self):
        for datum in self.settings.datums:
            if datum.target not in self.surfaces:
                self.errors.append(f'Datum {datum.label}: hedef yüzey artık yok.')
                continue
            ref, view = self.surface_ref(datum.target)
            attach = 'surface'
            if ref['type'] == 'cylinder':
                # ISO 5459: an axis datum is indicated in line with the diameter dimension.
                dimension = next((d for d in self.dimensions if d['kind'] == 'diameter'
                                  and d['refs'][0].get('r') == ref['r'] and d['view'] == 'main'
                                  and d['x0_mm'] <= ref['x0'] + EPS and d['x1_mm'] >= ref['x1'] - EPS), None)
                if dimension is None:
                    self.errors.append(f'Datum {datum.label}: eksen datumu için ilgili çap ölçüsü bulunamadı.')
                    continue
                attach = dimension['id']
            self.datums.append(dict(id=f'datum:{datum.label}', label=datum.label, text=datum.label, target=datum.target, view=view,
                                    surface=ref, attach=attach, title=self.surfaces[datum.target][0], band='below',
                                    x0_mm=ref.get('x0', ref.get('x', 0)), x1_mm=ref.get('x1', ref.get('x', 0))))

    def frame_requirements(self):
        labels = {d['label'] for d in self.datums}
        for i, frame in enumerate(self.settings.geometric, 1):
            name, needs = CHARACTERISTICS[frame.characteristic]
            if frame.target not in self.surfaces:
                self.errors.append(f'{name}: hedef yüzey artık yok.'); continue
            missing = [d for d in frame.datums if d not in labels]
            if needs and (not frame.datums or missing):
                self.errors.append(f'{name}: referans datum tanımlı değil ({", ".join(missing) or "datum yok"}); '
                                   'çerçeve oluşturulmaz.')
                continue
            ref, view = self.surface_ref(frame.target)
            diameter_zone = frame.characteristic == 'position' and ref['type'] == 'cylinder'
            text = f'{name} {"Ø" if diameter_zone else ""}{_num(frame.value)} {" ".join(frame.datums)}'.strip()
            self.frames.append(dict(id=f'gtol:{i:03d}', characteristic=frame.characteristic, value=frame.value,
                                    datums=list(frame.datums), diameter_zone=diameter_zone, target=frame.target,
                                    view=view, surface=ref, text=text, band='above',
                                    x0_mm=ref.get('x0', ref.get('x', 0)), x1_mm=ref.get('x1', ref.get('x', 0))))


def plan(project, settings=None):
    """Return ``dict`` with views, annotations, layout and issues (never raises for user data)."""
    settings = settings or getattr(project, 'drawing', None) or DrawingSettings()
    errors = list(validate_project(project))
    if errors:
        return dict(version=PLAN_VERSION, ready=False, errors=errors, warnings=[], dimensions=[], notes=[],
                    finishes=[], datums=[], frames=[], views=[], layout=None)
    profile(project)
    errors = settings.basic_errors()
    builder = _Plan(project, settings)
    builder.errors += errors
    builder.build()
    annotations = [dict(id=a['id'], view=a['view'], kind=a.get('kind', 'note'), text=a['text'], x0_mm=a['x0_mm'],
                        x1_mm=a['x1_mm'], band=a['band'], priority=a.get('priority', 7))
                   for a in builder.dimensions + builder.notes + builder.finishes + builder.datums + builder.frames]
    view_ids = [v['id'] for v in builder.views if v['id'] != 'main' and not v['id'].startswith('detail:')]
    details = [v['id'] for v in builder.views if v['id'].startswith('detail:')]
    if settings.isometric:
        builder.views.append(dict(id='iso', kind='iso'))
        view_ids.append('iso')
    result = layout_engine.build(project.total_length, project.maximum_diameter, ['main', *view_ids],
                                 [a for a in annotations], size=settings.sheet_size, scale_mode=settings.scale_mode,
                                 scale=tuple(settings.scale), projection=settings.projection, detail_ids=details)
    builder.warnings += result.conflicts
    unused = [k for k, spec in settings.tolerances.items() if spec.kind != 'none' and k not in builder.used_tolerances
              and k in builder.dimension_titles]
    for key in unused:
        builder.warnings.append(f'{builder.dimension_titles[key][0]}: bu ölçü seçilen düzenle teknik resimde yer almıyor; '
                                'tolerans uygulanmadı.')
    title = {k: v for k, v in settings.title.items() if v}
    missing = [name for name, key in (('Malzeme', 'material'), ('Resim numarası', 'drawing_number'), ('Revizyon', 'revision'))
               if not title.get(key)]
    if missing:
        builder.warnings.append('Antette boş kalacak alanlar: ' + ', '.join(missing)
                                + (' (malzeme SOLIDWORKS parçasından okunabilirse doldurulur)' if 'Malzeme' in missing else '') + '.')
    return dict(
        version=PLAN_VERSION, ready=not builder.errors, part_name=project.name,
        axis=dict(length_mm=project.total_length, max_diameter_mm=project.maximum_diameter),
        segments=[dict(seg) for seg in builder.segments], views=builder.views,
        dimensions=builder.dimensions, notes=builder.notes, finishes=builder.finishes, datums=builder.datums,
        frames=builder.frames, centerlines=settings.centerlines, scheme=settings.scheme,
        projection=settings.projection, template=settings.template, sheet_format=settings.sheet_format,
        title=title, outputs=dict(pdf=settings.pdf, dwg=settings.dwg),
        layout=result.as_dict(), errors=builder.errors, warnings=builder.warnings)


def summary(result):
    """Short Turkish counts for the UI."""
    if not result.get('layout'):
        return 'Teknik resim planı oluşturulamadı.'
    sheet = result['layout']['sheet']
    scale = sheet['scale']
    return (f'{sheet["size"]} · {scale[0]}:{scale[1]} · {len(result["views"])} görünüş · '
            f'{len(result["dimensions"])} ölçü · {len(result["notes"])} not · {len(result["finishes"])} yüzey işareti · '
            f'{len(result["datums"])} datum · {len(result["frames"])} geometrik tolerans')


__all__ = ['plan', 'summary', 'segments', 'prune', 'PLAN_VERSION']
