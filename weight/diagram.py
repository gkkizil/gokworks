"""Native, schematic stock-section illustrations for the weight calculator.

Only drawing lives here: no calculation, Tk root, image files or COM imports.
Section dimensions are shown in millimetres; stock length uses the selected unit.
"""

import math

from gui.theme import PANEL, INPUT, TEXT, MUTED, ACCENT, UI_FONT


_I_SECTIONS = frozenset(('HEA', 'HP', 'HD', 'HL', 'HE', 'IPE', 'IPN'))
_U_SECTIONS = frozenset(('U profil', 'UPE', 'UPN'))


def _value(result, name, default=None):
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _positive(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return value if math.isfinite(value) and value > 0 else default


def _dimensions(values):
    if not hasattr(values, 'items'):
        return {}
    return {key: number for key, value in values.items()
            if (number := _positive(value)) is not None}


def _color(value, appearance):
    return value[1 if str(appearance).lower() in ('dark', 'koyu') else 0]


def _mix(first, second, fraction):
    a = tuple(int(first[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(second[i:i + 2], 16) for i in (1, 3, 5))
    return '#' + ''.join(f'{round(x * (1 - fraction) + y * fraction):02x}' for x, y in zip(a, b))


def _number(value):
    if value >= 10000000 or 0 < value < .001:
        return f'{value:.3g}'.replace('.', ',')
    text = f'{value:,.3f}'.rstrip('0').rstrip('.')
    return text.replace(',', '\0').replace('.', ',').replace('\0', '.')


def _section(kind, dimensions):
    """Return a front outline, optional opening and the schematic envelope.

    Extremely thin walls remain visible in this explicitly schematic drawing.
    The values printed beside it always retain the actual supplied dimensions.
    """
    dims = dimensions
    if kind in ('Mil', 'Boru'):
        diameter = dims.get('d', 80)
        wall = min(.34, max(.065, dims.get('t', diameter * .1) / diameter))
        return 'circle', (wall if kind == 'Boru' else None), 1.0, 1.0
    if kind == 'Altıköşe':
        width = 2 / math.sqrt(3)
        return [(width * .25, 0), (width * .75, 0), (width, .5),
                (width * .75, 1), (width * .25, 1), (0, .5)], None, width, 1

    if kind in ('Sac levha', 'Silme lama'):
        b, h = dims.get('b', 140), dims.get('t', 14)
    elif kind == 'Kare demir':
        b = h = dims.get('b', 80)
    else:
        defaults = (100, 160) if kind in ('IPE', 'IPN', 'UPE', 'UPN', 'U profil') else (120, 120)
        b, h = dims.get('b', defaults[0]), dims.get('h', defaults[1])
    aspect = min(3.2, max(.4, b / h))
    w, h = aspect, 1.0
    wall = dims.get('t', min(b, dims.get('h', b)) * .09)
    tx = min(w * .25, max(w * .065, wall / b * w))
    ty = min(.25, max(.065, wall / (dims.get('h', b) or b)))
    web = min(w * .35, max(w * .075, dims.get('tw', wall) / b * w))
    flange = min(.26, max(.08, dims.get('tf', wall) / dims.get('h', 120)))
    rectangle = [(0, 0), (w, 0), (w, h), (0, h)]
    if kind == 'Kutu profil':
        opening = [(tx, ty), (w - tx, ty), (w - tx, 1 - ty), (tx, 1 - ty)]
        return rectangle, opening, w, h
    if kind == 'Köşebent':
        return [(0, 0), (tx, 0), (tx, 1 - ty), (w, 1 - ty), (w, 1), (0, 1)], None, w, h
    if kind == 'T profil':
        x1, x2 = (w - web) / 2, (w + web) / 2
        return [(0, 0), (w, 0), (w, flange), (x2, flange), (x2, 1),
                (x1, 1), (x1, flange), (0, flange)], None, w, h
    if kind in _I_SECTIONS:
        x1, x2 = (w - web) / 2, (w + web) / 2
        toe, heel = (flange * .75, flange * 1.3) if kind == 'IPN' else (flange, flange)
        return [(0, 0), (w, 0), (w, toe), (x2, heel), (x2, 1 - heel),
                (w, 1 - toe), (w, 1), (0, 1), (0, 1 - toe),
                (x1, 1 - heel), (x1, heel), (0, toe)], None, w, h
    if kind in _U_SECTIONS:
        toe, heel = (flange * .75, flange * 1.3) if kind == 'UPN' else (flange, flange)
        return [(0, 0), (w, 0), (w, toe), (web, heel), (web, 1 - heel),
                (w, 1 - toe), (w, 1), (0, 1)], None, w, h
    return rectangle, None, w, h


def _coordinates(points, x, y, factor):
    return [coordinate for a, b in points for coordinate in (x + a * factor, y + b * factor)]


def _polygon(canvas, points, x, y, factor, **options):
    return canvas.create_polygon(*_coordinates(points, x, y, factor), **options)


def _stock(canvas, kind, dimensions, x, y, factor, depth, colors, line_width):
    outline, opening, width, height = _section(kind, dimensions)
    dx, dy = depth, -depth * .47
    front, edge, side, top, hole = (colors[name] for name in ('front', 'edge', 'side', 'top', 'hole'))
    if outline == 'circle':
        radius = factor / 2
        cx, cy = x + radius, y + radius
        normal = (-dy / math.hypot(dx, dy), dx / math.hypot(dx, dy)) if depth else (0, 1)
        nx, ny = normal[0] * radius, normal[1] * radius
        if depth:
            canvas.create_oval(x + dx, y + dy, x + factor + dx, y + factor + dy,
                               fill=side, outline=edge, width=line_width)
            canvas.create_polygon(cx + nx, cy + ny, cx + dx + nx, cy + dy + ny,
                                  cx + dx - nx, cy + dy - ny, cx - nx, cy - ny,
                                  fill=side, outline=edge, width=line_width)
        canvas.create_oval(x, y, x + factor, y + factor, fill=front, outline=edge, width=line_width)
        if opening is not None:
            inset = factor * opening
            canvas.create_oval(x + inset, y + inset, x + factor - inset, y + factor - inset,
                               fill=hole, outline=edge, width=line_width)
            if depth:
                canvas.create_arc(x + inset + line_width, y + inset + line_width,
                                  x + factor - inset - line_width, y + factor - inset - line_width,
                                  start=225, extent=130, style='arc', outline=side,
                                  width=max(line_width, inset * .25))
        return width * factor, height * factor

    if depth:
        _polygon(canvas, outline, x + dx, y + dy, factor, fill=side, outline=edge, width=line_width)
        for first, second in zip(outline, outline[1:] + outline[:1]):
            ax, ay = first
            bx, by = second
            # Clockwise front outlines expose their top and right edges.
            outward = (by - ay, ax - bx)
            if outward[0] * dx + outward[1] * dy > 0:
                canvas.create_polygon(x + ax * factor, y + ay * factor,
                                      x + bx * factor, y + by * factor,
                                      x + bx * factor + dx, y + by * factor + dy,
                                      x + ax * factor + dx, y + ay * factor + dy,
                                      fill=top if abs(by - ay) < abs(bx - ax) else side,
                                      outline=edge, width=line_width)
    _polygon(canvas, outline, x, y, factor, fill=front, outline=edge, width=line_width)
    if opening:
        _polygon(canvas, opening, x, y, factor, fill=hole, outline=edge, width=line_width)
        if depth:
            left, top_y = opening[0]
            right, bottom = opening[2]
            inset = min((right - left) * .09, (bottom - top_y) * .09)
            # Interior shading stays inside the opening; never bridges its hole.
            inner = [(left, bottom), (left + inset, bottom - inset),
                     (right - inset, bottom - inset), (right, bottom)]
            _polygon(canvas, inner, x, y, factor, fill=side, outline='')
            inner = [(left, top_y), (left + inset, top_y + inset),
                     (left + inset, bottom - inset), (left, bottom)]
            _polygon(canvas, inner, x, y, factor, fill=top, outline='')
    return width * factor, height * factor


def _dimension(canvas, start, end, offset, text, color, background, scale, vertical=False):
    sx, sy = start
    ex, ey = end
    width = max(1, scale)
    font = (UI_FONT, -max(9, round(10 * scale)))
    arrow = (round(5 * scale), round(6 * scale), round(2 * scale))
    if vertical:
        line_x = sx + offset
        canvas.create_line(sx, sy, line_x - 4 * scale, sy, fill=color, width=width)
        canvas.create_line(ex, ey, line_x - 4 * scale, ey, fill=color, width=width)
        canvas.create_line(line_x, sy, line_x, ey, fill=color, width=width, arrow='both', arrowshape=arrow)
        label = canvas.create_text(line_x - 8 * scale, (sy + ey) / 2, text=text, fill=color,
                                   font=font, anchor='e', angle=90)
    else:
        line_y = sy + offset
        canvas.create_line(sx, sy, sx, line_y + 4 * scale, fill=color, width=width)
        canvas.create_line(ex, ey, ex, line_y + 4 * scale, fill=color, width=width)
        canvas.create_line(sx, line_y, ex, line_y, fill=color, width=width, arrow='both', arrowshape=arrow)
        label = canvas.create_text((sx + ex) / 2, line_y + 11 * scale, text=text, fill=color,
                                   font=font, anchor='center')
    # Make annotation text readable over fine dimension lines.
    bounds = canvas.bbox(label)
    if bounds:
        pad = 2 * scale
        block = canvas.create_rectangle(bounds[0] - pad, bounds[1] - pad,
                                        bounds[2] + pad, bounds[3] + pad,
                                        fill=background, outline='')
        canvas.tag_lower(block, label)


def draw(canvas, result, appearance, scale, kind='Sac levha', dimensions=None):
    """Redraw a responsive stock diagram with verified, result-backed labels."""
    scale = _positive(scale, 1)
    kind = str(_value(result, 'kind', kind) or kind)
    method = str(_value(result, 'method', ''))
    catalog = method == 'Katalog alanından'
    supplied = _dimensions(_value(result, 'dimensions_mm', dimensions) or dimensions)
    actual = {} if catalog else supplied
    dims = {} if catalog else supplied
    background = _color(PANEL, appearance)
    accent, muted = _color(ACCENT, appearance), _color(MUTED, appearance)
    dark = str(appearance).lower() in ('dark', 'koyu')
    colors = dict(front=_mix(accent, background, .64 if dark else .76), edge=accent,
                  side=_mix(accent, background, .36 if dark else .53),
                  top=_mix(accent, background, .49 if dark else .63),
                  hole=_color(INPUT, appearance))
    canvas.delete('all')
    canvas.configure(background=background, highlightthickness=0)
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width <= 1:
        width = _positive(canvas.cget('width'), 440 * scale)
    if height <= 1:
        height = _positive(canvas.cget('height'), 300 * scale)
    if width < 100 * scale or height < 100 * scale:
        return
    canvas.create_text(16 * scale, 17 * scale, text=kind, anchor='w', fill=_color(TEXT, appearance),
                       font=(UI_FONT, -round(12 * scale), 'bold'))
    canvas.create_text(width - 16 * scale, 17 * scale, text='KESİT ŞEMATİK', anchor='e', fill=muted,
                       font=(UI_FONT, -round(9 * scale), 'bold'))
    _, _, aspect_width, aspect_height = _section(kind, dims)
    room_width, room_height = max(40 * scale, width - 150 * scale), max(35 * scale, height - 137 * scale)
    depth = min(85 * scale, room_width * .25)
    factor = min(150 * scale / aspect_height, (room_width - depth) / aspect_width,
                 (room_height - depth * .47) / aspect_height)
    factor = max(12 * scale, factor)
    front_width, front_height = aspect_width * factor, aspect_height * factor
    x = (width - front_width - depth) / 2 + 7 * scale
    y = 53 * scale + depth * .47 + max(0, (room_height - front_height - depth * .47) / 2)
    _stock(canvas, kind, dims, x, y, factor, depth, colors, max(1, 1.2 * scale))

    horizontal = 'd' if kind in ('Mil', 'Boru') else ('' if kind == 'Altıköşe' else 'b')
    vertical = 't' if kind in ('Sac levha', 'Silme lama') else ('s' if kind == 'Altıköşe' else 'h')
    if horizontal in actual:
        symbol = 'Ø' if horizontal == 'd' else horizontal
        _dimension(canvas, (x, y + front_height), (x + front_width, y + front_height),
                   16 * scale, f'{symbol} {_number(actual[horizontal])} mm', muted, background, scale)
    if vertical in actual and kind not in ('Mil', 'Boru', 'Kare demir'):
        _dimension(canvas, (x, y), (x, y + front_height), -20 * scale,
                   f'{vertical} {_number(actual[vertical])} mm', muted, background, scale, vertical=True)

    # A short leader annotates thin walls without illegible, overlapping arrows.
    thickness = [(key, actual[key]) for key in ('t', 'tw', 'tf') if key in actual
                 and not (vertical == key and key == 't')]
    if thickness:
        label_x = min(width - 18 * scale, x + front_width + depth + 16 * scale)
        label_y = max(47 * scale, y - 6 * scale)
        canvas.create_line(x + front_width * .78, y + front_height * .11,
                           label_x - 8 * scale, label_y + 7 * scale, fill=muted,
                           width=max(1, scale))
        canvas.create_text(label_x, label_y, text='\n'.join(f'{key} {_number(value)} mm' for key, value in thickness),
                           anchor='ne', justify='right', fill=muted, font=(UI_FONT, -round(10 * scale)))

    length = _positive(_value(result, 'length_mm'))
    if length:
        selected = str(_value(result, 'unit', 'mm')).lower().strip()
        unit, divisor = {'cm': ('cm', 10), 'm': ('m', 1000), 'mm': ('mm', 1),
                         'milimetre': ('mm', 1), 'santimetre': ('cm', 10), 'metre': ('m', 1000)}.get(selected, ('mm', 1))
        label_y = y + front_height * .55 - depth * .2
        canvas.create_text(width - 18 * scale, label_y,
                           text=f'Boy {_number(length / divisor)} {unit}', anchor='e', fill=accent,
                           font=(UI_FONT, -round(11 * scale), 'bold'))

    area = _positive(_value(result, 'area_mm2'))
    if catalog and area:
        caption = f'Katalog kesit alanı: {_number(area)} mm²'
    elif result is None:
        caption = 'Ölçüleri girerek ağırlığı hesaplayın.'
    else:
        caption = 'Ölçüler gerçek değerleri gösterir.'
    canvas.create_text(width / 2, height - 35 * scale, text=caption, fill=muted,
                       font=(UI_FONT, -round(10 * scale)), anchor='center')
    canvas.create_text(width / 2, height - 17 * scale, text='Kesit ve boy çizimi ölçekli değildir.', fill=muted,
                       font=(UI_FONT, -round(9 * scale)), anchor='center')


def draw_icon(canvas, kind, color, bg, size=34):
    """Draw a crisp section thumbnail on a native Tk Canvas."""
    size = _positive(size, 34)
    canvas.delete('all')
    canvas.configure(background=bg, highlightthickness=0)
    outline, opening, width, height = _section(kind, {})
    factor = (size * .7) / max(width, height)
    x, y = (size - width * factor) / 2, (size - height * factor) / 2
    stroke = max(1, size / 23)
    if outline == 'circle':
        canvas.create_oval(x, y, x + factor, y + factor, fill=color, outline=color, width=stroke)
        if opening is not None:
            inset = max(stroke * 1.4, factor * opening)
            canvas.create_oval(x + inset, y + inset, x + factor - inset, y + factor - inset,
                               fill=bg, outline=bg)
    else:
        _polygon(canvas, outline, x, y, factor, fill=color, outline=color, width=stroke)
        if opening:
            _polygon(canvas, opening, x, y, factor, fill=bg, outline=bg)
