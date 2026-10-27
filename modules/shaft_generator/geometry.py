"""Shared true-scale geometry, unit conversion and native feature plan."""

import math
from .models import Groove, Keyway, Chamfer, Fillet, CosmeticThread
from .validation import require_valid


def metres(mm):
    return mm * .001


def radians(degrees):
    return math.radians(degrees)


def profile(project):
    """Closed axisymmetric half-profile in mm, without zero-length shoulders."""
    require_valid(project)
    points = [(0., 0.)]
    boundaries = project.boundaries
    for i,stage in enumerate(project.stages):
        radius = stage.diameter / 2
        for point in ((boundaries[i], radius), (boundaries[i+1], radius)):
            if point != points[-1]:
                points.append(point)
    points.extend(((boundaries[-1], 0.), (0., 0.)))
    check_profile(points)
    return points


def check_profile(points):
    if len(points) < 4 or points[0] != points[-1]:
        raise ValueError('Profil kapalı olmalı.')
    segments = list(zip(points, points[1:]))
    for a, b in segments:
        if a == b or not all(math.isfinite(v) for p in (a, b) for v in p):
            raise ValueError('Profilde sıfır uzunluk veya geçersiz koordinat var.')
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a, b, c):
        return abs(cross(a,b,c)) < 1e-10 and all(min(a[k],b[k])-1e-10 <= c[k] <= max(a[k],b[k])+1e-10 for k in (0,1))
    for i, (a,b) in enumerate(segments):
        for j in range(i+2,len(segments)):
            if i == 0 and j == len(segments)-1:
                continue
            c,d = segments[j]
            if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any((on(a,b,c),on(a,b,d),on(c,d,a),on(c,d,b))):
                raise ValueError('Profil kendisiyle kesişiyor.')


def treated_profile(project):
    """Sampled exact circular fillets and 45° chamfers for the section view."""
    points = profile(project)
    treatments = {}
    for op in project.operations:
        if isinstance(op, (Chamfer, Fillet)):
            stage = project.stage(op.stage_id)
            x = project.end(stage.id) if op.edge == 'right' else project.start(stage.id)
            treatments[(x, stage.diameter / 2)] = op
    result = [points[0]]
    def append(point):
        # Two treatments may exactly consume the annular shoulder. Their
        # coincident endpoints form one vertex, never a zero-length edge.
        if math.dist(result[-1], point) > 1e-10:
            result.append(point)
    for i in range(1, len(points)-1):
        a, b, c = points[i-1:i+2]
        op = treatments.get(b)
        if op is None:
            append(b)
            continue
        size = op.distance if isinstance(op, Chamfer) else op.radius
        u = tuple((b[k]-a[k])/math.dist(a,b) for k in (0,1))
        v = tuple((c[k]-b[k])/math.dist(b,c) for k in (0,1))
        before = tuple(b[k]-u[k]*size for k in (0,1))
        after = tuple(b[k]+v[k]*size for k in (0,1))
        append(before)
        if isinstance(op, Fillet):
            center = tuple(before[k]+v[k]*size for k in (0,1))
            start = math.atan2(before[1]-center[1],before[0]-center[0])
            sweep = math.copysign(math.pi/2,u[0]*v[1]-u[1]*v[0])
            for j in range(1,16):
                append((center[0]+size*math.cos(start+sweep*j/16),center[1]+size*math.sin(start+sweep*j/16)))
        append(after)
    append(points[-1])
    return result


def operation_plan(project):
    require_valid(project)
    plan = [dict(kind='revolve', name=f'MIL_ANA_GEOMETRI_{i:02}', sketch=f'MIL_PROFIL_{i:02}',
                 stage_id=stage.id, angle_rad=math.tau, start_m=metres(project.start(stage.id)),
                 diameter_m=metres(stage.diameter), length_m=metres(stage.length))
            for i,stage in enumerate(project.stages,1)]
    counts = {}
    if project.bore is not None:
        a,b=project.bore.interval(project.total_length)
        plan.append(dict(kind='bore',name='IC_DELIK_01',sketch='IC_DELIK_01_ESKIZI',
                         start_m=metres(a),length_m=metres(b-a),diameter_m=metres(project.bore.diameter)))
    # Preserve the original circular end edges while making edge treatments.
    # Validation keeps their axial footprints separate from channel cuts.
    for kind in (Chamfer, Fillet, Groove, Keyway, CosmeticThread):
        for op in project.operations:
            if not isinstance(op, kind):
                continue
            key = op.kind
            counts[key] = counts.get(key,0)+1
            name = {'groove':'SEGMAN_KANALI','keyway':'KAMA_KANALI','chamfer':'PAH','fillet':'RADYUS','cosmetic_thread':'KOZMETIK_DIS'}[key]
            plan.append(dict(kind=key, name=f'{name}_{counts[key]:02}', operation_id=op.id))
    return plan
