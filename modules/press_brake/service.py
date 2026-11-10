"""Worker-only geometry, independent collision sampling and immutable results."""
from dataclasses import dataclass
from math import degrees
from .collision import check
from .geometry import Geometry, mesh
from .kinematics import step_angles
from .motion import sample_interval
from modules.cad_converter.models import checkpoint

STATUS = {'collision': 'Çarpışma var', 'clear': 'Kontrol edilen hareketlerde çarpışma yok', 'unknown': 'Kontrol edilemedi'}
PHASES = {'approach': 'Yaklaşma', 'bend': 'Büküm', 'retract': 'Geri çekilme'}
EXCLUDED = ('Tezgâh gövdesi ve arka dayama', 'Adımlar arası yeniden konumlandırma / parça çevirme',
            'Parça çıkarma rotası', 'Kuvvet, yaylanma ve CNC strok hesabı')


@dataclass(frozen=True)
class Frame:
    step: int
    phase: str
    angle: float
    mesh: object
    axis: tuple
    hits: tuple = ()
    tool_bounds: tuple = ()


@dataclass(frozen=True)
class StepResult:
    step: int
    status: str
    first_hit: Frame | None
    samples: int
    notes: tuple[str, ...]
    pairs: tuple[str, ...]
    min_angle_interval: float


@dataclass(frozen=True)
class Result:
    revision: int
    frames: tuple[Frame, ...]
    steps: tuple[StepResult, ...]
    flat_mesh: object
    formed_mesh: object
    excluded: tuple[str, ...] = EXCLUDED

    @property
    def status(self):
        return 'collision' if any(s.status == 'collision' for s in self.steps) else 'unknown' if any(s.status == 'unknown' for s in self.steps) else 'clear'


def step_scope(plan, step):
    notes = []
    die = plan.tool(step.die)
    for tool, segments in ((plan.tool(step.punch), step.punch_segments), (die, step.die_segments)):
        if tool.section is None:
            notes.append(f'{tool.code}: gerçek ölçekli kesit eksik')
        if not tool.mount.compatible:
            notes.append(f'{tool.code}: takım–tutucu–adaptör bağlantısı doğrulanamadı')
        if tool.holder_section is None:
            notes.append(f'{tool.code}: tutucu geometrisi eksik')
        elif not tool.holder_segments:
            notes.append(f'{tool.code}: tutucu boyuna yerleşimi eksik')
        segments = tool.segments if segments is None else segments
        if not segments:
            notes.append(f'{tool.code}: segment atanmamış')
        ordered = sorted(segments, key=lambda s: s.start)
        if any(s.length <= 0 for s in ordered) or any(a.start+a.length > b.start+1e-6 for a, b in zip(ordered, ordered[1:])):
            notes.append(f'{tool.code}: segment boyları veya üst üste yerleşimi geçersiz')
    punch = plan.tool(step.punch)
    if punch.tip is None or punch.tip_radius is None or punch.tip_angle is None:
        notes.append(f'{punch.code}: uç çalışma referansı, uç R veya açı eksik')
    if not any(c.id == step.channel for c in die.channels):
        notes.append(f'{die.code}: seçili V kanalı bulunamadı')
    return notes


def run(plan, stop=None, progress=None, *, max_angle=6., min_angle=2., travel_step=2.):
    """Sample approach/bend/retract independently of playback FPS.

    Nearby solids force subdivision down to min_angle / 0.5 mm travel. Remaining
    between-sample motion is explicitly uncertain, never a continuous clearance
    proof. All inspected frames are kept; first collision stops playback only,
    not the calculation of later steps.
    """
    if not 0 < min_angle <= max_angle <= 15 or not .1 <= travel_step <= 10:
        raise ValueError('Geçersiz hareket örnekleme aralığı.')
    plan.validate(); checkpoint(stop)
    geometry = Geometry(plan)
    flat = mesh(geometry.part_bodies({}), stop)
    final_angles = step_angles(plan, len(plan.steps)-1, 1)
    formed = mesh(geometry.part_bodies(final_angles), stop)
    frames, results = [], []
    for index, step in enumerate(plan.steps):
        checkpoint(stop)
        bend = next(b for b in plan.part.bends if b.id == step.bend)
        notes = step_scope(plan, step)
        first_hit, samples, checked_pairs, minimum = None, 0, set(), max_angle
        phase_cache = {}

        def sample(phase, value):
            nonlocal samples, first_hit
            key = phase, round(value, 9)
            if key in phase_cache:
                return phase_cache[key]
            checkpoint(stop)
            fraction = value/bend.turn if phase == 'bend' else 0 if phase == 'approach' else 1
            angles = step_angles(plan, index, fraction)
            bodies, contacts = geometry.scene(index, angles, phase, value if phase != 'bend' else 0)
            hits, near = check(bodies, contacts, near_margin=3.)
            samples += 1
            for a in bodies:
                for b in bodies:
                    if a.kind == 'sheet' and b.kind != 'sheet':
                        checked_pairs.add('sac–'+b.kind)
            checked_pairs.add('sac–sac')
            angle = degrees(angles.get(bend.id, 0))
            # Axis in the station is X, centre at origin by construction.
            frame = Frame(index, phase, angle, mesh(bodies, stop),
                          ((-bend.length/2, 0, 0), (bend.length/2, 0, 0)), hits,
                          tuple((b.id, b.bounds) for b in bodies if b.kind != 'sheet'))
            phase_cache[key] = (frame, near)
            if progress:
                progress(index, phase, value)
            return phase_cache[key]

        try:
            step_frames = []
            for phase, a, b, limit in (('approach', 15., 0., travel_step), ('bend', 0., bend.turn, max_angle), ('retract', 0., 15., travel_step)):
                sampled = sample_interval(lambda value: sample(phase, value), a, b, maximum=limit, minimum=min_angle if phase == 'bend' else .5)
                if phase == 'bend':
                    minimum = min(abs(b.angle-a.angle) for a, b in zip(sampled, sampled[1:]))
                step_frames.extend(sampled)
            for frame in step_frames:
                if frame.hits:
                    first_hit = frame
                    break
            # Discrete samples cannot establish a swept-volume certificate.
            notes.append(f'Ayrık katı kontrolü: açı ≤ {minimum:.3g}°, hareket ≤ 0,5–{travel_step:g} mm; aradaki hareket sürekli kanıtlanmadı.')
            result_status = 'collision' if first_hit else 'unknown' if step_scope(plan, step) else 'clear'
            frames.extend(step_frames)
        except (ValueError, RuntimeError) as error:
            from modules.cad_converter.models import Cancelled
            if isinstance(error, Cancelled):
                raise
            cached_items = sorted(phase_cache.items(), key=lambda item: (('approach', 'bend', 'retract').index(item[0][0]), -item[0][1] if item[0][0] == 'approach' else item[0][1]))
            cached = [value[0] for _, value in cached_items]
            first_hit = next((f for f in cached if f.hits), None)
            frames.extend(cached)
            notes.append(str(error)); result_status = 'collision' if first_hit else 'unknown'
        results.append(StepResult(index, result_status, first_hit, samples, tuple(notes), tuple(sorted(checked_pairs)), minimum))
    checkpoint(stop)
    return Result(plan.revision, tuple(frames), tuple(results), flat, formed)
