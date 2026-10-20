"""Live press-brake tooling sections; schematic bodies, exact input labels.

The profiles illustrate selected tool families, not a manufacturer's catalogue
or a collision/contact simulation. No CAD or assignment state is touched.
"""

from math import cos, sin, tan, radians

from .theme import COLORS


PUNCH_TYPES = ('Düz bıçak', 'Kaz boynu')
DIE_TYPES = ('Tek V kalıp', 'Çift V kalıp')


def fmt(value):
    return f'{value:.6g}'.replace('.', ',')


def draw_tooling(scene, recipe, result, punch_type, die_type, appearance):
    """Draw tool profiles and a separate sample using the validated recipe."""
    c = COLORS[appearance]
    scene.delete('all')
    scene.configure(background=c['panel'])
    font = ('Segoe UI', -15)
    bold = ('Segoe UI', -16, 'bold')

    def text(x, y, value, *, tag=None, color=None, **options):
        return scene.create_text(x, y, text=value, font=options.pop('font', font),
                                 fill=color or c['text'], tags=tag or (), **options)

    def line(*points, **options):
        return scene.create_line(*points, fill=options.pop('fill', c['muted']),
                                 width=options.pop('width', 1.2), **options)

    def polygon(points, tag, *, fill=None, outline=None):
        return scene.create_polygon([v for p in points for v in p],
                                    fill=fill or c['input'], outline=outline or c['muted'],
                                    width=1.6, tags=tag)

    if result is None:
        text(400, 250, 'Takım çizimi için geçerli ölçüler girin.',
             tag='tooling_empty', color=c['muted'], width=700)
        return

    text(200, 27, 'ÜST BIÇAK', color=c['muted'])
    text(200, 51, punch_type, font=bold, tag='punch_type')
    text(600, 27, 'ALT KALIP', color=c['muted'])
    text(600, 51, die_type, font=bold, tag='die_type')
    line(400, 20, 400, 322, fill=c['border'])
    line(24, 336, 776, 336, fill=c['border'])

    # Rounded wedge: the tangent flanks retain the entered included angle.
    # Body lengths and overall scale are illustrative; only labelled sizes
    # have supplied dimensions. A bounded radius keeps the nose legible.
    x, tip_y = 200, 254
    nose_r = 8 + 24 * recipe.punch_radius_mm / (recipe.punch_radius_mm + 2)
    half = radians(recipe.punch_angle_deg / 2)
    cy = tip_y - nose_r
    tangent_y = cy + nose_r * sin(half)
    rise = min(60, 90 / tan(half))
    shoulder_y = tangent_y - rise
    shoulder_half = nose_r * cos(half) + rise * tan(half)
    arc = [(x + nose_r * cos(radians(90) - half + 2 * half * i / 32),
            cy + nose_r * sin(radians(90) - half + 2 * half * i / 32))
           for i in range(33)]
    if punch_type == 'Kaz boynu':
        profile = [(125, 76), (200, 76), (200, 105), (155, 125),
                   (130, 151), (150, 176), (x + shoulder_half, shoulder_y),
                   *arc, (x - shoulder_half, shoulder_y), (100, 210),
                   (90, 175), (90, 115), (125, 95)]
    else:
        profile = [(158, 76), (242, 76), (242, 130),
                   (x + shoulder_half, shoulder_y), *arc,
                   (x - shoulder_half, shoulder_y), (158, 130)]
    polygon(profile, 'punch_profile')
    line(200, 65, 200, 268, dash=(5, 4), fill=c['border'], tags='punch_axis')
    line(200 + nose_r * .7, cy + nose_r * .7, 255, 279, 255, 292,
         fill=c['accent'], tags='punch_radius_leader')
    text(200, 309, f'Rp = {fmt(recipe.punch_radius_mm)} mm',
         tag='punch_radius', color=c['accent'], width=330)
    flank_x = x + (shoulder_half + nose_r * cos(half)) / 2
    flank_y = (shoulder_y + tangent_y) / 2
    line(flank_x, flank_y, 307, 167, fill=c['accent'])
    text(309, 148, f'αp = {fmt(recipe.punch_angle_deg)}°',
         tag='punch_angle', color=c['accent'])

    # A double-V body has a second, unmeasured illustrative opening. The
    # highlighted left opening alone carries the entered V and die angle.
    double = die_type == 'Çift V kalıp'
    groove_x = 535 if double else 600
    groove_half = (49 if double else 85) * (result.die_opening_mm / (result.die_opening_mm + 8)) ** .25
    groove_depth = groove_half / tan(radians(recipe.die_angle_deg / 2))
    if groove_depth > 96:
        groove_half *= 96 / groove_depth
        groove_depth = 96
    top, bottom = 166, 292
    root = top + groove_depth
    profile = [(436, top), (groove_x - groove_half, top), (groove_x, root),
               (groove_x + groove_half, top)]
    if double:
        profile += [(680 - groove_half * .75, top),
                    (680, top + groove_depth * .75), (680 + groove_half * .75, top)]
    profile += [(764, top), (764, bottom), (436, bottom)]
    polygon(profile, 'die_profile')
    line(groove_x - groove_half, top, groove_x, root, groove_x + groove_half, top,
         fill=c['accent'], width=2.2, tags='active_v')
    for edge in (-1, 1):
        xx = groove_x + edge * groove_half
        line(xx, top - 5, xx, 121, fill=c['accent'])
    line(groove_x - groove_half, 124, groove_x + groove_half, 124,
         arrow='both', fill=c['accent'], tags='v_dimension')
    text(groove_x, 102, f'V = {fmt(result.die_opening_mm)} mm',
         tag='die_opening', color=c['accent'], font=bold)
    if double:
        text(groove_x, 146, 'Aktif ağız', color=c['muted'], font=('Segoe UI', -12))
    line(groove_x + groove_half * .32, top + groove_depth * .68,
         631, 306, 646, 306, fill=c['accent'])
    text(650, 306, f'αv = {fmt(recipe.die_angle_deg)}°',
         tag='die_angle', color=c['accent'], anchor='w')

    # Separate bent sample: beta is the turn from a flat sheet, not the
    # included angle of the tooling. No assembled contact is implied.
    text(35, 361, 'BÜKÜM NUMUNESİ', color=c['muted'], anchor='w')
    bx, by = 400, 414
    ri = 8 + 25 * result.radius_mm / (result.radius_mm + 3)
    t = 6 + 8 * result.thickness_mm / (result.thickness_mm + 2)
    phi = radians(result.angle_deg / 2)
    arm = min(115, 62 / max(sin(phi), .1))

    def arc_points(radius, reverse=False):
        return [(bx + radius * cos(radians(90) + phi - 2 * phi * i / 32),
                 by + radius * sin(radians(90) + phi - 2 * phi * i / 32))
                for i in (range(32, -1, -1) if reverse else range(33))]

    outer, inner = arc_points(ri + t), arc_points(ri, True)
    def end(point, side):
        return point[0] + side * arm * cos(phi), point[1] - arm * sin(phi)
    polygon([end(outer[0], -1), *outer, end(outer[-1], 1),
             end(inner[0], 1), *inner, end(inner[-1], -1)],
            'sample_profile', fill=c['selected'], outline=c['accent'])
    # Thickness arrows run normal to the right flange, not vertically.
    inner_t = (bx + ri * sin(phi) + .62 * arm * cos(phi),
               by + ri * cos(phi) - .62 * arm * sin(phi))
    outer_t = (inner_t[0] + t * sin(phi), inner_t[1] + t * cos(phi))
    line(*inner_t, *outer_t, arrow='both', fill=c['accent'], tags='thickness_dimension')
    line(*outer_t, 579, 440, 607, 440, fill=c['accent'])
    text(611, 440, f't = {fmt(result.thickness_mm)} mm',
         tag='thickness', color=c['accent'], anchor='w')
    line(bx, by + ri, 280, 468, 242, 468, fill=c['accent'])
    text(35, 466, f'İç R = {fmt(result.radius_mm)} mm',
         tag='part_radius', color=c['accent'], anchor='w')
    text(35, 488, 'Ölçülmüş iç R' if recipe.measured_radius_mm is not None else 'Tahmini iç R',
         tag='radius_source', color=c['muted'], anchor='w', font=('Segoe UI', -13))
    text(625, 381, f'β = {fmt(result.angle_deg)}°',
         tag='bend_angle', color=c['accent'], font=bold)
    text(625, 402, 'Düz sactan dönüş', color=c['muted'], font=('Segoe UI', -13))
