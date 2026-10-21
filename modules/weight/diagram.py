"""Native, schematic stock-section illustrations for the weight calculator.

Only drawing lives here: no calculation, Tk root, image files or COM imports.
Section dimensions are shown in millimetres; stock length uses the selected unit.
"""

import math

from shared.theme import PANEL, MUTED, ACCENT, UI_FONT


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


def _front(canvas, kind, dimensions, x, y, factor, fill, edge, background, line_width):
    """Draw one flat section, keeping hollow profiles genuinely open."""
    outline, opening, width, height = _section(kind, dimensions)
    if outline == 'circle':
        canvas.create_oval(x, y, x + factor, y + factor, fill=fill, outline=edge, width=line_width)
        if opening is not None:
            inset = factor * opening
            canvas.create_oval(x + inset, y + inset, x + factor - inset, y + factor - inset,
                               fill=background, outline=edge, width=line_width)
        return width * factor, height * factor
    _polygon(canvas, outline, x, y, factor, fill=fill, outline=edge, width=line_width)
    if opening:
        _polygon(canvas, opening, x, y, factor, fill=background, outline=edge, width=line_width)
    return width * factor, height * factor


def _dimension(canvas, start, end, offset, text, color, background, scale, vertical=False):
    sx, sy = start
    ex, ey = end
    width = max(1, scale)
    font = (UI_FONT, -max(9, round(10 * scale)))
    tick = 3 * scale
    if vertical:
        line_x = sx + offset
        canvas.create_line(line_x, sy, line_x, ey, fill=color, width=width)
        canvas.create_line(line_x - tick, sy, line_x + tick, sy, fill=color, width=width)
        canvas.create_line(line_x - tick, ey, line_x + tick, ey, fill=color, width=width)
        canvas.create_text(line_x - 12 * scale, (sy + ey) / 2, text=text, fill=color,
                           font=font, angle=90)
    else:
        line_y = sy + offset
        canvas.create_line(sx, line_y, ex, line_y, fill=color, width=width)
        canvas.create_line(sx, line_y - tick, sx, line_y + tick, fill=color, width=width)
        canvas.create_line(ex, line_y - tick, ex, line_y + tick, fill=color, width=width)
        canvas.create_text((sx + ex) / 2, line_y + 12 * scale, text=text, fill=color, font=font)


def draw(canvas, result, appearance, scale, kind='Sac levha', dimensions=None):
    """Redraw a simple 2D section with minimal, result-backed measurements."""
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
    fill = _mix(accent, background, .87 if dark else .92)
    canvas.delete('all')
    canvas.configure(background=background, highlightthickness=0)
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width <= 1:
        width = _positive(canvas.cget('width'), 440 * scale)
    if height <= 1:
        height = _positive(canvas.cget('height'), 250 * scale)
    if width < 100 * scale or height < 100 * scale:
        return
    _, _, aspect_width, aspect_height = _section(kind, dims)
    room_width, room_height = max(40 * scale, width - 128 * scale), max(25 * scale, height - 112 * scale)
    factor = min(135 * scale / aspect_height, 180 * scale / aspect_width,
                 room_width / aspect_width, room_height / aspect_height)
    factor = max(12 * scale, factor)
    front_width, front_height = aspect_width * factor, aspect_height * factor
    x = (width - front_width) / 2
    y = max(15 * scale, (height - 76 * scale - front_height) / 2)
    _front(canvas, kind, dims, x, y, factor, fill, accent, background, max(1, 1.35 * scale))

    horizontal = 'd' if kind in ('Mil', 'Boru') else ('' if kind == 'Altıköşe' else 'b')
    vertical = 's' if kind == 'Altıköşe' else 'h'
    if horizontal in actual:
        symbol = 'Ø' if horizontal == 'd' else horizontal
        _dimension(canvas, (x, y + front_height), (x + front_width, y + front_height),
                   14 * scale, f'{symbol} {_number(actual[horizontal])} mm', muted, background, scale)
    if vertical in actual and kind not in ('Mil', 'Boru', 'Kare demir'):
        _dimension(canvas, (x, y), (x, y + front_height), -20 * scale,
                   f'{vertical} {_number(actual[vertical])} mm', muted, background, scale, vertical=True)

    thickness = [(key, actual[key]) for key in ('t', 'tw', 'tf') if key in actual]
    if thickness:
        canvas.create_text(width - 18 * scale, 20 * scale,
                           text='\n'.join(f'{key} {_number(value)} mm' for key, value in thickness),
                           anchor='ne', justify='right', fill=muted, font=(UI_FONT, -round(10 * scale)))

    length = _positive(_value(result, 'length_mm'))
    if length:
        selected = str(_value(result, 'unit', 'mm')).lower().strip()
        unit, divisor = {'cm': ('cm', 10), 'm': ('m', 1000), 'mm': ('mm', 1),
                         'milimetre': ('mm', 1), 'santimetre': ('cm', 10), 'metre': ('m', 1000)}.get(selected, ('mm', 1))
        canvas.create_text(width / 2, height - 41 * scale,
                           text=f'Boy: {_number(length / divisor)} {unit}', fill=accent,
                           font=(UI_FONT, -round(11 * scale)))

    area = _positive(_value(result, 'area_mm2'))
    if catalog and area:
        canvas.create_text(width / 2, height - 63 * scale, text=f'Alan: {_number(area)} mm²',
                           fill=muted, font=(UI_FONT, -round(10 * scale)))
    canvas.create_text(width / 2, height - 18 * scale, text='Ölçeksiz kesit', fill=muted,
                       font=(UI_FONT, -round(9 * scale)))


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
