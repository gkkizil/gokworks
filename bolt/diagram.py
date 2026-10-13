"""Responsive vector illustration of a bolt and its load directions."""

from gui.theme import PANEL, INPUT, TEXT, MUTED, BORDER, ACCENT, AMBER, UI_FONT
from bolt.rules import fmt


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
    def text(x, y, value, paint=TEXT, size=11, **kw):
        return canvas.create_text(x*sx, y*sy, text=value, fill=color(paint),
                                  font=(UI_FONT, -round(size*scale)), **kw)
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
    rect((199, 78, 241, 204), fill='#9BADBF', outline='#657B92', tags='bolt_body')
    rect((205, 80, 214, 201), fill='#D5E1EC', outline='')
    rect((232, 80, 240, 201), fill='#7B91A8', outline='')
    thread_start = 88 if result.section == 'Dişli kesit' else 174
    for y in range(thread_start, 201, 7):
        line((200, y+5, 240, y-2), fill='#60768D', width=1.2*scale)
    rect((184, 83, 256, 91), fill='#ABBAC9', outline='#657B92')
    poly((184, 57, 196, 48, 244, 48, 256, 57, 256, 79, 184, 79),
         fill='#B7C7D7', outline='#657B92', width=1.5)
    line((185, 58, 255, 58), fill='#EAF1F7', width=2*scale)
    text(220, 68, result.grade, paint=('#243348', '#243348'), size=11)
    rect((184, 179, 256, 185), fill='#ABBAC9', outline='#657B92')
    poly((187, 185, 253, 185, 253, 203, 244, 211, 196, 211, 187, 203),
         fill='#A8B9CA', outline='#657B92', width=1.5)
    line((199, 186, 199, 207), fill='#D9E4EE', width=2*scale)
    line((242, 186, 242, 207), fill='#70879D', width=2*scale)
    arrow = dict(arrow='last', arrowshape=(8*scale, 10*scale, 4*scale), width=3*scale)
    if result.tension_n:
        line((220, 45, 220, 12), fill=color(ACCENT), tags='tension_arrow', **arrow)
        line((220, 213, 220, 251), fill=color(ACCENT), tags='tension_arrow', **arrow)
        text(237, 238, f'Ft = {fmt(result.tension_n/result.count/1000)} kN', ACCENT, 10, anchor='w')
    if result.shear_n:
        # Double shear: centre plate carries V; each outer plate carries V/2.
        loads = [(132, 1), (102, -1), (164, -1)] if result.planes == 2 else [(115, 1), (152, -1)]
        for y, direction in loads:
            points = (310, y, 402, y) if direction == 1 else (130, y, 38, y)
            line(points, fill=color(AMBER), tags='shear_arrow', **arrow)
        text(422, 78, f'Fv = {fmt(result.shear_n/result.count/1000)} kN', AMBER, 10, anchor='e')
    text(18, 260, 'Bir cıvata · şematik, ölçeksiz', MUTED, 10, anchor='w')
