"""True-proportion cross-section sketch with dimension lines for the weight calculator.

The outline is built from the same millimetre dimensions the area is computed from
(including corner and root radii), scaled uniformly and centred. Only a thickness
that would be thinner than 2 px is widened, and the sketch then says so.
Drawing only: no calculation, file or COM access.
"""

import math

from shared.theme import UI_FONT
from gui_qt.diagrams import CANVAS as PANEL, MUTED, ACCENT


def _color(value, appearance):
    return value[1 if str(appearance).lower() in ('dark', 'koyu') else 0]


def _mix(first, second, fraction):
    a = tuple(int(first[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(second[i:i + 2], 16) for i in (1, 3, 5))
    return '#' + ''.join(f'{round(x * (1 - fraction) + y * fraction):02x}' for x, y in zip(a, b))


def num(value):
    text = f'{value:,.2f}'.rstrip('0').rstrip('.')
    return text.replace(',', '\0').replace('.', ',').replace('\0', '.')


def fillet(points, radii, segments=8):
    """Round polygon vertices (index → radius); works for convex and concave 90° corners."""
    rounded, count = [], len(points)
    for index, (px, py) in enumerate(points):
        radius = radii.get(index, 0)
        if radius <= 0:
            rounded.append((px, py))
            continue
        ax, ay = points[index - 1]
        bx, by = points[(index + 1) % count]
        la, lb = math.hypot(ax - px, ay - py), math.hypot(bx - px, by - py)
        radius = min(radius, la * .5, lb * .5)
        ux, uy, vx, vy = (ax - px) / la, (ay - py) / la, (bx - px) / lb, (by - py) / lb
        cx, cy = px + (ux + vx) * radius, py + (uy + vy) * radius
        start = math.atan2(py + uy * radius - cy, px + ux * radius - cx)
        end = math.atan2(py + vy * radius - cy, px + vx * radius - cx)
        sweep = (end - start + math.pi) % (2 * math.pi) - math.pi
        rounded += [(cx + radius * math.cos(start + sweep * i / segments),
                     cy + radius * math.sin(start + sweep * i / segments)) for i in range(segments + 1)]
    return rounded


def rectangle(x, y, w, h, r=0.0):
    points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return fillet(points, dict.fromkeys(range(4), r)) if r > 0 else points


def regular(radius, sides, rotation=0.0):
    return [(radius * math.cos(rotation + 2 * math.pi * i / sides), radius * math.sin(rotation + 2 * math.pi * i / sides))
            for i in range(sides)]


def geometry(result):
    """(outlines, holes, width, height, thin_axis) in mm, y up; outlines/holes are point lists or circles."""
    d = dict(result.dimensions_mm)
    shape = result.drawing
    if shape in ('round', 'tube'):
        outer = d['d']
        holes = [('circle', outer / 2, outer / 2, outer / 2 - d['t'])] if shape == 'tube' else []
        return [('circle', outer / 2, outer / 2, outer / 2)], holes, outer, outer
    if shape == 'hexagon':
        corner = d['s'] / math.sqrt(3)
        pts = [(x + corner, y + d['s'] / 2) for x, y in regular(corner, 6)]
        return [pts], [], 2 * corner, d['s']
    if shape == 'square':
        return [rectangle(0, 0, d['b'], d['b'])], [], d['b'], d['b']
    if shape in ('flat', 'plate'):
        return [rectangle(0, 0, d['b'], d['t'])], [], d['b'], d['t']
    if shape == 'box':
        b, t = d['b'], d['t']
        h = d.get('h', b)
        outer, inner = result.corner_radii or (0.0, 0.0)
        return [rectangle(0, 0, b, h, outer)], [rectangle(t, t, b - 2 * t, h - 2 * t, inner)], b, h
    if shape == 'angle':
        b, h, t = d['b'], d.get('h', d['b']), d.get('t', d.get('tf'))
        root, toe = result.corner_radii or (0.0, 0.0)
        pts = [(0, 0), (b, 0), (b, t), (t, t), (t, h), (0, h)]
        return [fillet(pts, {2: toe, 3: root, 4: toe})], [], b, h
    if shape == 'channel':
        h, b, tw, tf, r = d['h'], d['b'], d['tw'], d['tf'], d.get('r', 0.0)
        pts = [(0, 0), (b, 0), (b, tf), (tw, tf), (tw, h - tf), (b, h - tf), (b, h), (0, h)]
        return [fillet(pts, {3: r, 4: r})], [], b, h
    if shape == 'tee':
        b, h, tw, tf = d['b'], d['h'], d['tw'], d['tf']
        x0, x1 = (b - tw) / 2, (b + tw) / 2
        pts = [(x0, 0), (x1, 0), (x1, h - tf), (b, h - tf), (b, h), (0, h), (0, h - tf), (x0, h - tf)]
        return [pts], [], b, h
    if shape == 'i':
        h, b, tw, tf, r = d['h'], d['b'], d['tw'], d['tf'], d.get('r', 0.0)
        x0, x1 = (b - tw) / 2, (b + tw) / 2
        pts = [(0, 0), (b, 0), (b, tf), (x1, tf), (x1, h - tf), (b, h - tf), (b, h), (0, h), (0, h - tf),
               (x0, h - tf), (x0, tf), (0, tf)]
        return [fillet(pts, {3: r, 4: r, 9: r, 10: r})], [], b, h
    return [], [], 1, 1


def _dimension(canvas, start, end, offset, text, color, font, vertical=False):
    (sx, sy), (ex, ey) = start, end
    if vertical:
        x = sx + offset
        canvas.create_line(sx, sy, x, sy, fill=color, width=.8)
        canvas.create_line(ex, ey, x, ey, fill=color, width=.8)
        canvas.create_line(x, sy, x, ey, fill=color, width=1, arrow='both', arrowshape=(6, 7, 2.6))
        canvas.create_text(x + (8 if offset > 0 else -8), (sy + ey) / 2, text=text, fill=color, font=font,
                           anchor='w' if offset > 0 else 'e', tags=('dimension',))
    else:
        y = sy + offset
        canvas.create_line(sx, sy, sx, y, fill=color, width=.8)
        canvas.create_line(ex, ey, ex, y, fill=color, width=.8)
        canvas.create_line(sx, y, ex, y, fill=color, width=1, arrow='both', arrowshape=(6, 7, 2.6))
        canvas.create_text((sx + ex) / 2, y + (9 if offset > 0 else -9), text=text, fill=color, font=font,
                           anchor='n' if offset > 0 else 's', tags=('dimension',))


def labels(result):
    """Dimension texts that are not drawn as dimension lines (thickness, radii)."""
    d, out = result.dimensions_mm, []
    for key, title in (('t', 't'), ('tw', 'tw'), ('tf', 'tf'), ('r', 'r'), ('r1', 'r₁')):
        if d.get(key):
            out.append(f'{title} = {num(d[key])} mm')
    if result.drawing == 'box' and result.corner_radii and result.corner_radii[0]:
        out.append(f'rₒ = {num(result.corner_radii[0])} mm · rᵢ = {num(result.corner_radii[1])} mm')
    return out


def draw(canvas, result, appearance, scale=1, **_):
    """Render ``result`` (rules.Result) into a VectorScene-like canvas."""
    background = _color(PANEL, appearance)
    accent, muted = _color(ACCENT, appearance), _color(MUTED, appearance)
    dark = str(appearance).lower() in ('dark', 'koyu')
    fill = _mix(accent, background, .80 if dark else .86)
    canvas.delete('all')
    canvas.configure(background=background, highlightthickness=0)
    width = canvas.winfo_width() if canvas.winfo_width() > 1 else 650
    height = canvas.winfo_height() if canvas.winfo_height() > 1 else 320
    font = (UI_FONT, -max(10, round(11 * scale)))
    small = (UI_FONT, -max(9, round(10 * scale)))
    if result is None or not result.dimensions_mm or result.method == 'Katalog alanından':
        canvas.create_text(width / 2, height / 2, text='Katalog alanıyla hesap: kesit ölçüsü girilmedi.',
                           fill=muted, font=font)
        return
    outlines, holes, gw, gh = geometry(result)
    margin_x, margin_top, margin_bottom = 110 * scale, 34 * scale, 84 * scale
    box_w, box_h = width - 2 * margin_x, height - margin_top - margin_bottom
    factor = min(box_w / gw, box_h / gh)
    minimum = 2.0 / factor            # 2 px in mm
    widened = gh * factor < 2 or gw * factor < 2
    sx, sy = factor, factor
    if gh * factor < 2:               # plate/flat: keep it visible, say so below
        sy = minimum * factor / gh * 2
    ox = (width - gw * sx) / 2
    oy = margin_top + (box_h + gh * sy) / 2   # baseline (y up → screen down)

    def map_points(points):
        return [coord for x, y in points for coord in (ox + x * sx, oy - y * sy)]

    for item in outlines:
        if item[0] == 'circle':
            _, cx, cy, radius = item
            canvas.create_oval(ox + (cx - radius) * sx, oy - (cy + radius) * sy, ox + (cx + radius) * sx,
                               oy - (cy - radius) * sy, fill=fill, outline=accent, width=1.4, tags=('section',))
        else:
            canvas.create_polygon(*map_points(item), fill=fill, outline=accent, width=1.4, tags=('section',))
    for item in holes:
        if item[0] == 'circle':
            _, cx, cy, radius = item
            canvas.create_oval(ox + (cx - radius) * sx, oy - (cy + radius) * sy, ox + (cx + radius) * sx,
                               oy - (cy - radius) * sy, fill=background, outline=accent, width=1.4, tags=('section',))
        else:
            canvas.create_polygon(*map_points(item), fill=background, outline=accent, width=1.4, tags=('section',))
    left, right, top, bottom = ox, ox + gw * sx, oy - gh * sy, oy
    d = result.dimensions_mm
    if result.drawing in ('round', 'tube'):
        canvas.create_line((left + right) / 2, top - 8, (left + right) / 2, bottom + 8, fill=muted, width=.7,
                           dash=(8, 3, 2, 3))
        canvas.create_line(left - 8, (top + bottom) / 2, right + 8, (top + bottom) / 2, fill=muted, width=.7,
                           dash=(8, 3, 2, 3))
        _dimension(canvas, (left, bottom), (right, bottom), 26 * scale, f'Ø{num(d["d"])}', muted, font)
    elif result.drawing == 'hexagon':
        _dimension(canvas, (right, top), (right, bottom), 26 * scale, f'SW {num(d["s"])}', muted, font, vertical=True)
    else:
        b = d.get('b', gw)
        _dimension(canvas, (left, bottom), (right, bottom), 26 * scale, num(b), muted, font)
        height_value = d.get('h', d.get('t') if result.drawing in ('flat', 'plate') else d.get('b'))
        _dimension(canvas, (left, top), (left, bottom), -26 * scale, num(height_value), muted, font, vertical=True)
    notes = labels(result)
    if result.drawing == 'tube':
        notes.insert(0, f'iç Ø{num(d["d"] - 2 * d["t"])} mm')
    if widened:
        notes.append('kalınlık çizimde okunur olsun diye büyütüldü')
    caption = '   ·   '.join(notes)
    title = result.profile or result.kind
    canvas.create_text(width / 2, 12 * scale, text=title, fill=_color(('#1F2329', '#E6E8EB'), appearance),
                       font=(UI_FONT, -max(11, round(12 * scale)), 'bold'), tags=('title',))
    if caption:
        # Below the bottom dimension line and its text, never on top of them.
        canvas.create_text(width / 2, bottom + 62 * scale, text=caption, fill=muted, font=small, tags=('caption',))
    canvas.create_text(width - 6, height - 30 * scale, text='Ölçek: gerçek oran' if not widened else 'Ölçek: genişlikte gerçek',
                       fill=muted, font=small, anchor='e', tags=('scale',))


__all__ = ['draw', 'geometry', 'fillet', 'labels']
