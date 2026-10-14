"""Responsive vector illustration of a bolt and its load directions."""

from math import cos, sin, pi

from gui.theme import PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG, AMBER, UI_FONT
from bolt.rules import fmt, force_text
from bolt.dimensions import dimensions


def draw_dimensions(canvas, result, appearance, scale, metric='M10', grade='8.8'):
    """Draw a side elevation and end view with nominal head dimensions."""
    color = lambda pair: pair[appearance == 'Dark']
    canvas.configure(background=color(PANEL))
    canvas.delete('all')
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 10 or height < 10:
        return
    metric = result.metric if result else metric
    grade = result.grade if result else grade
    d = dimensions(metric)
    sx, sy = width/440, height/280
    def line(points, paint=BORDER, **kw):
        return canvas.create_line(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(points)],
                                  fill=color(paint), width=1.2*scale, **kw)
    def polygon(points, **kw):
        return canvas.create_polygon(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(points)], **kw)
    def text(x, y, value, paint=TEXT, size=11, **kw):
        return canvas.create_text(x*sx, y*sy, text=value, fill=color(paint),
                                  font=(UI_FONT, -round(size*scale)), **kw)
    # Common geometry scale within the side elevation; length is illustrative.
    factor = 80/d.across_flats
    left, right = 125-d.across_flats*factor/2, 125+d.across_flats*factor/2
    head_top, head_bottom = 53, 53+d.head_height*factor
    shank_left, shank_right = 125-d.diameter*factor/2, 125+d.diameter*factor/2
    bottom = 225
    line((125, 32, 125, 238), MUTED, dash=(4, 4))
    polygon((left, head_top+4, left+6, head_top, right-6, head_top,
             right, head_top+4, right, head_bottom, left, head_bottom),
            fill=color(INPUT), outline=color(MUTED), width=1.3*scale, tags='dimension_head')
    line((left+16, head_top, left+16, head_bottom), MUTED)
    line((right-16, head_top, right-16, head_bottom), MUTED)
    polygon((shank_left, head_bottom, shank_right, head_bottom,
             shank_right, bottom-5, shank_right-4, bottom,
             shank_left+4, bottom, shank_left, bottom-5),
            fill=color(INPUT), outline=color(MUTED), width=1.3*scale, tags='dimension_shank')
    for y in range(round(head_bottom+12), bottom-7, 8):
        line((shank_left+1, y, shank_right-1, y+4), MUTED, tags='dimension_thread')
    line((left-14, head_top, left-14, head_bottom), ACCENT)
    line((left-19, head_top, left-2, head_top), ACCENT)
    line((left-19, head_bottom, left-2, head_bottom), ACCENT)
    text(left-22, (head_top+head_bottom)/2, f'k={fmt(d.head_height, 1)}', ACCENT, 10, anchor='e')
    line((shank_left, bottom+14, shank_right, bottom+14), ACCENT)
    line((shank_left, bottom+8, shank_left, bottom+19), ACCENT)
    line((shank_right, bottom+8, shank_right, bottom+19), ACCENT)
    text(125, bottom+29, f'd={fmt(d.diameter, 0)}', ACCENT, 11)
    cx, cy, radius = 330, 96, 43
    vertices = tuple(v for i in range(6) for v in
                     (cx+radius*cos(pi/6+i*pi/3), cy+radius*sin(pi/6+i*pi/3)))
    polygon(vertices, fill=color(INPUT), outline=color(ACCENT), width=1.8*scale, tags='dimension_hex')
    text(cx, cy, grade, MUTED, 13)
    flat_half = radius*cos(pi/6)
    line((cx-flat_half, cy+radius+15, cx+flat_half, cy+radius+15), ACCENT)
    line((cx-flat_half, cy+radius+8, cx-flat_half, cy+radius+21), ACCENT)
    line((cx+flat_half, cy+radius+8, cx+flat_half, cy+radius+21), ACCENT)
    text(cx, cy+radius+33, f's={fmt(d.across_flats, 1)} mm', ACCENT, 11)
    canvas.create_rectangle(250*sx, 196*sy, 410*sx, 264*sy,
                            fill=color(ACCENT_BG), outline=color(ACCENT), width=scale)
    text(cx, 210, 'KILAVUZ DELİĞİ', MUTED, 9)
    text(cx, 231, f'≈ Ø{fmt(d.tapping_hole, 2)} mm', ACCENT, 15)
    text(cx, 251, 'Yaklaşık d − P', MUTED, 10)
    text(12, 15, f'{metric} × {fmt(d.pitch, 2)} · ISO 4017', ACCENT, 11, anchor='w')
    text(12, 276, 'Nominal baş ölçüleri · boy şematik', MUTED, 9, anchor='w')


def draw(canvas, result, appearance, scale):
    color = lambda pair: pair[appearance == 'Dark']
    canvas.configure(background=color(INPUT))
    canvas.delete('all')
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 10 or height < 10:
        return
    sx, sy = width/440, height/270
    def line(points, **kw):
        return canvas.create_line(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(points)], **kw)
    def rect(box, **kw):
        return canvas.create_rectangle(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(box)], **kw)
    def poly(points, **kw):
        return canvas.create_polygon(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(points)], **kw)
    def oval(box, **kw):
        return canvas.create_oval(*[v*(sx if i % 2 == 0 else sy) for i, v in enumerate(box)], **kw)
    def text(x, y, value, paint=TEXT, size=11, **kw):
        return canvas.create_text(x*sx, y*sy, text=value, fill=color(paint),
                                  font=(UI_FONT, -round(size*scale)), **kw)

    def nut(cx, cy, radius, depth, *, mounted=False):
        # Six true flats, a chamfered annulus and a cylindrical threaded bore.
        # The enlarged loose nut shows the bore that the bolt obscures in assembly.
        tilt = .36 if mounted else .65
        vertices = [(cx+radius*cos(pi/6+i*pi/3), cy+tilt*radius*sin(pi/6+i*pi/3)) for i in range(6)]
        flatten = lambda points: tuple(v for point in points for v in point)
        for index, fill in ((0, '#9AA9B4'), (1, '#708492'), (2, '#536775')):
            a, b = vertices[index], vertices[(index+1) % 6]
            poly(flatten((a, b, (b[0], b[1]+depth), (a[0], a[1]+depth))),
                 fill=fill, outline='#526775', width=1.1*scale, tags='nut_flat')
        poly(flatten(vertices), fill='#CAD4DB', outline='#647985', width=1.2*scale)
        r = radius*.77
        oval((cx-r, cy-r*tilt, cx+r, cy+r*tilt), fill='#AEBFC8', outline='#E9F0F3', width=1.4*scale)
        r = radius*.52
        oval((cx-r, cy-r*tilt, cx+r, cy+r*tilt), fill='#304752', outline='#526976', width=1.2*scale)
        for offset in (2, 5, 8):
            canvas.create_arc((cx-r)*sx, (cy-r*tilt+offset)*sy, (cx+r)*sx, (cy+r*tilt+offset)*sy,
                              start=0, extent=180, style='arc', outline='#B6C7CF', width=1.1*scale, tags='nut_thread')
        if mounted:
            # The shaft enters the bore and is occluded by the front of the nut.
            rect((cx-20, cy-17, cx+20, cy+3), fill='#9BADBF', outline='')
            for y in range(round(cy-14), round(cy+2), 6):
                line((cx-20, y+3, cx+20, y-3), fill='#60768D', width=scale)
        else:
            # Open centre and dark internal wall; no solid "head" surface.
            oval((cx-r*.78, cy-r*tilt*.35, cx+r*.78, cy+r*tilt), fill=color(INPUT), outline='#405965')
    if result is None:
        text(220, 125, 'Hesabı görmek için alanları tamamlayın.', MUTED,
             width=max(80, width-32*scale))
        return
    text(18, 20, 'YÜK GÖSTERİMİ', MUTED, 10, anchor='w')
    text(422, 20, f'{result.metric} × {fmt(result.pitch, 2)}', ACCENT, 12, anchor='e')
    line((220, 32, 220, 250), fill=color(BORDER), dash=(4, 4))
    # Plates in section, offset edges give depth without a bitmap asset.
    spans = [(99, 132), (136, 169)] if result.planes == 1 or result.mode == 'Çekme' else [(91, 113), (117, 149), (153, 175)]
    for y0, y1 in spans:
        rect((104, y0+4, 344, y1+4), fill=color(BORDER), outline='')
        rect((96, y0, 336, y1), fill=color(PANEL), outline=color(BORDER), width=1.5)
        for x in range(106, 331, 20):
            line((x, y1-3, x+12, y0+3), fill=color(BORDER))
    # Metallic shank, turned highlights and visible thread flanks.
    # The threaded end projects beyond the nut, so it cannot read as a second head.
    poly((199, 78, 241, 78, 241, 234, 236, 239, 204, 239, 199, 234),
         fill='#9BADBF', outline='#657B92', tags='bolt_body')
    rect((205, 80, 214, 236), fill='#D5E1EC', outline='')
    rect((232, 80, 240, 233), fill='#7B91A8', outline='')
    thread_start = 88 if result.section == 'Dişli kesit' else 174
    for y in range(thread_start, 233, 7):
        line((200, y+5, 240, y-2), fill='#60768D', width=1.2*scale)
    rect((184, 83, 256, 91), fill='#ABBAC9', outline='#657B92')
    poly((184, 57, 196, 48, 244, 48, 256, 57, 256, 79, 184, 79),
         fill='#B7C7D7', outline='#657B92', width=1.5)
    line((185, 58, 255, 58), fill='#EAF1F7', width=2*scale)
    text(220, 68, result.grade, paint=('#243348', '#243348'), size=11)
    rect((181, 177, 259, 182), fill='#ABBAC9', outline='#657B92')
    nut(220, 192, 42, 21, mounted=True)
    text(83, 172, 'Somun detayı', MUTED, 10)
    nut(83, 203, 38, 23)
    line((130, 213, 155, 213, 176, 202), fill=color(MUTED), dash=(3, 3))
    arrow = dict(arrow='last', arrowshape=(8*scale, 10*scale, 4*scale), width=3*scale)
    if result.tension_n:
        line((220, 45, 220, 12), fill=color(ACCENT), tags='tension_arrow', **arrow)
        line((220, 242, 220, 260), fill=color(ACCENT), tags='tension_arrow', **arrow)
        text(237, 251, f'Ft = {force_text(result.tension_n/result.count, result.unit)}', ACCENT, 10, anchor='w')
    if result.shear_n:
        # Double shear: centre plate carries V; each outer plate carries V/2.
        loads = [(132, 1), (102, -1), (164, -1)] if result.planes == 2 else [(115, 1), (152, -1)]
        for y, direction in loads:
            points = (310, y, 402, y) if direction == 1 else (130, y, 38, y)
            line(points, fill=color(AMBER), tags='shear_arrow', **arrow)
        text(422, 78, f'Fv = {force_text(result.shear_n/result.count, result.unit)}', AMBER, 10, anchor='e')
    text(18, 260, 'Bir cıvata · şematik, ölçeksiz', MUTED, 10, anchor='w')
