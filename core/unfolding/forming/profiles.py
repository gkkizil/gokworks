"""Straight/constant-radius flange chains with explicit dimension references."""
from dataclasses import replace
import math

from .mechanics import bend_values
from ..models import FrozenMap, Line2D, Mesh3D
from ..geometry import outline
from ..shapes.common import finish_part, check_cancel


def develop_bends(lengths_mm, angles_deg, radii_mm, thickness_mm, options, *, dimension_reference):
    """Lengths: outside/inside virtual sharps, or straight tangent-to-tangent spans."""
    from .mechanics import finite
    if dimension_reference not in ('outside', 'inside', 'tangent'):
        raise ValueError('Flanş ölçü türü outside/inside/tangent olmalı.')
    lengths = tuple(finite(v, 'Flanş boyu', high=1e7, positive=True) for v in lengths_mm)
    angles, radii = tuple(angles_deg), tuple(radii_mm)
    if not 1 <= len(angles) <= 64 or len(lengths) != len(angles)+1 or len(radii) != len(angles):
        raise ValueError('1–64 büküm ve her birleşimde bir açı/yarıçap gerekli.')
    bends = tuple(bend_values(a, r, thickness_mm, options) for a, r in zip(angles, radii))
    setbacks = [b.outside_setback_mm if dimension_reference == 'outside' else b.inside_setback_mm
                if dimension_reference == 'inside' else 0. for b in bends]
    straights = tuple(v-(setbacks[i-1] if i else 0.)-(setbacks[i] if i < len(bends) else 0.)
                      for i, v in enumerate(lengths))
    if any(v < -1e-9 for v in straights):
        raise ValueError('Flanş boyu komşu bükümlerin teğet mesafelerine yetmiyor.')
    straights = tuple(max(0., v) for v in straights)
    cursor = 0.; zones = []
    for i, straight in enumerate(straights):
        cursor += straight
        if i < len(bends):
            b = bends[i]
            zones.append(dict(start_mm=cursor, end_mm=cursor+b.allowance_mm, line_at_mm=cursor+b.allowance_mm/2))
            cursor += b.allowance_mm
    return straights, bends, tuple(zones), cursor


def profile_inputs(n):
    p = n['parameters']; count = 1 if n['variant_id'] == 'single' else 2
    return (tuple(p[f'flange_{i+1}'] for i in range(count+1)),
            tuple(p[f'bend_{i+1}_deg'] for i in range(count)),
            tuple(p[f'radius_{i+1}'] for i in range(count)),
            {1: 'outside', 2: 'inside', 3: 'tangent'}[p['length_reference']])


def profile_part(n, material, options, token=None, *, forming=None):
    check_cancel(token)
    lengths, angles, radii, ref = profile_inputs(n)
    # Explicit nominal reference surface, not a default production K-factor.
    spec = forming or dict(method='k_factor', k_factor=.5)
    straights, bends, zones, total = develop_bends(lengths, angles, radii, n['thickness'], spec, dimension_reference=ref)
    width = n['parameters']['width']
    geometry = outline(((0., 0.), (total, 0.), (total, width), (0., width)))
    # Preview of the final mid-surface uses final radii/angles and the same straight spans.
    pts = [(0., 0.)]; direction = 0.; x = z = 0.
    for i, straight in enumerate(straights):
        if straight:
            x += straight*math.cos(direction); z += straight*math.sin(direction); pts.append((x, z))
        if i < len(bends):
            a = math.radians(angles[i]); radius = radii[i]+n['thickness']/2
            sign = 1 if a > 0 else -1
            cx, cz = x-sign*radius*math.sin(direction), z+sign*radius*math.cos(direction)
            samples = max(2, math.ceil(abs(a)/.08))
            for j in range(1, samples+1):
                q = direction+a*j/samples
                pts.append((cx+sign*radius*math.sin(q), cz-sign*radius*math.cos(q)))
            x, z = pts[-1]; direction += a
    vertices = tuple((x, y, z) for x, z in pts for y in (0., width))
    triangles = tuple(tri for i in range(1, len(pts)) for tri in
                      ((2*i-2, 2*i, 2*i-1), (2*i, 2*i+1, 2*i-1)))
    part = finish_part('bent-profile', geometry, Mesh3D(vertices, triangles), (), total*width,
                       n, material, options)
    part = replace(part, bending_lines=tuple(Line2D((v['line_at_mm'], 0.), (v['line_at_mm'], width), f'B{i+1}')
                                            for i, v in enumerate(zones)),
                   forming_basis=FrozenMap(dict(kind='bend_profile',angles_deg=angles)))
    return part, bends, zones, total, straights


def normalize_profile(p, t, ref, variant):
    if t <= 0: raise ValueError('Bükümlü profil için pozitif sac kalınlığı gerekli.')
    if ref != 'mid': raise ValueError('Profilde iç/dış/teğet flanş türünü ayrı ölçü referansından seçin.')
    return dict(p)


def build_profile(n, material, options, token=None):
    part, bends, zones, length, straights = profile_part(n, material, options, token)
    return (part,), dict(calculation_method='explicit_bend_profile', nominal_mid_length_mm=length,
                         neutral_axis='geometric_mid_surface; production K not assumed')
