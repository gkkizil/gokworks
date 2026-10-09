"""Yazı tipi sembollerine bağımlı olmayan Tk vektör şemaları."""

from gui.theme import INPUT, TEXT, MUTED, ACCENT, ACCENT_BG, UI_FONT
from geometric_tolerances.rules import fmt


def symbol(canvas, key, x, y, size, color, width=2, tag='symbol'):
    r = size / 2
    def line(*points, **kw):
        return canvas.create_line(*points, fill=color, width=width, tags=tag, **kw)
    def circle(radius):
        canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                           outline=color, width=width, tags=tag)
    if key == 'straightness':
        line(x-r, y, x+r, y)
    elif key == 'flatness':
        canvas.create_polygon(x-r, y+r*.5, x-r*.5, y-r*.5, x+r, y-r*.5,
                              x+r*.5, y+r*.5, fill='', outline=color, width=width, tags=tag)
    elif key in ('circularity', 'cylindricity', 'position', 'concentricity'):
        circle(r*.65)
        if key == 'cylindricity':
            line(x-r, y+r, x, y-r)
            line(x, y+r, x+r, y-r)
        elif key == 'position':
            line(x-r, y, x+r, y)
            line(x, y-r, x, y+r)
        elif key == 'concentricity':
            circle(r*.32)
    elif key in ('line_profile', 'surface_profile'):
        canvas.create_arc(x-r, y-r*.6, x+r, y+r*.6, start=0, extent=180,
                          style='arc', outline=color, width=width, tags=tag)
        if key == 'surface_profile':
            line(x-r, y+r*.4, x+r, y+r*.4)
    elif key == 'parallelism':
        line(x-r, y+r, x, y-r)
        line(x, y+r, x+r, y-r)
    elif key == 'perpendicularity':
        line(x-r, y+r*.7, x+r, y+r*.7)
        line(x, y+r*.7, x, y-r)
    elif key == 'angularity':
        line(x+r, y+r*.7, x-r, y+r*.7, x+r*.4, y-r)
    elif key == 'symmetry':
        for offset, half in ((-.6, .7), (0, 1), (.6, .7)):
            line(x-r*half, y+r*offset, x+r*half, y+r*offset)
    elif key in ('circular_runout', 'total_runout'):
        line(x-r*.7, y+r*.7, x+r*.5, y-r*.7, arrow='last', arrowshape=(size*.3, size*.38, size*.15))
        if key == 'total_runout':
            line(x-r*.1, y+r*.7, x+r*1.1, y-r*.7, arrow='last', arrowshape=(size*.3, size*.38, size*.15))
            line(x-r*.7, y+r*.7, x-r*.1, y+r*.7)
    else:
        raise ValueError(f'Bilinmeyen geometrik sembol: {key}')


def draw(canvas, spec, appearance='Light', scale=1, *, frame=False):
    dark = appearance == 'Dark'
    color = lambda pair: pair[1 if dark else 0]
    canvas.configure(background=color(INPUT))
    canvas.delete('all')
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if spec is None:
        canvas.create_text(w/2, h/2, text='Geçerli değerleri girin.', fill=color(MUTED),
                           font=(UI_FONT, -round(12*scale)), tags='invalid')
        return
    if frame:
        sizes = [40, 88] + [38] * len(spec.datums)
        start = max(10*scale, (w-sum(sizes)*scale)/2)
        top, bottom = 12*scale, 48*scale
        for index, width in enumerate(sizes):
            end = start + width*scale
            canvas.create_rectangle(start, top, end, bottom, outline=color(ACCENT), tags='frame')
            if index == 0:
                symbol(canvas, spec.characteristic.key, (start+end)/2, (top+bottom)/2,
                       20*scale, color(TEXT), max(1, 2*scale))
            else:
                text = (('Ø' if spec.characteristic.diametrical else '')+fmt(spec.tolerance)) if index == 1 else spec.datums[index-2]
                canvas.create_text((start+end)/2, (top+bottom)/2, text=text, fill=color(TEXT),
                                   font=(UI_FONT, -round(14*scale), 'bold'), tags='frame')
            start = end
        return
    # Logical 460 × 210 scene: horizontal shrink keeps diagrams accessible at minimum size.
    sx = sy = min(w/460, h/210)
    offset = (w-460*sx)/2
    def coords(points):
        return [value*sx+offset if index % 2 == 0 else value*sy for index, value in enumerate(points)]
    def line(*points, **kwargs):
        canvas.create_line(*coords(points), fill=color(ACCENT), width=max(1, 2*scale), tags='zone', **kwargs)
    def rect(*points):
        canvas.create_rectangle(*coords(points), fill=color(ACCENT_BG), outline=color(ACCENT), width=max(1, 2*scale), tags='zone')
    def oval(*points, dashed=False):
        canvas.create_oval(*coords(points), fill='' if dashed else color(ACCENT_BG), outline=color(ACCENT),
                           width=max(1, 2*scale), dash=(4, 3) if dashed else (), tags='zone')
    def text(x, y, message, muted=False):
        canvas.create_text(x*sx+offset, y*sy, text=message, fill=color(MUTED if muted else TEXT),
                           font=(UI_FONT, -round(11*scale)), width=max(120, w-30*scale), tags='annotation')
    def datum():
        canvas.create_line(*coords([46, 172, 414, 172]), fill=color(MUTED), dash=(5, 4), tags='datum')
        text(230, 190, 'Datum '+(' | '.join(spec.datums) or 'tanımlı değil'), True)
    key = spec.characteristic.key
    if key == 'straightness':
        line(55, 80, 405, 80)
        line(55, 120, 405, 120)
        canvas.create_line(*coords([55, 103, 130, 90, 220, 110, 310, 98, 405, 107]),
                           fill=color(TEXT), width=max(1, 2*scale), tags='feature')
        line(420, 80, 420, 120, arrow='both')
        text(435, 100, 't')
    elif key == 'flatness':
        for y in (62, 115):
            canvas.create_polygon(*coords([65, y+35, 332, y+35, 397, y, 130, y]),
                                  fill=color(ACCENT_BG), outline=color(ACCENT), tags='zone')
        line(415, 62, 415, 115, arrow='both')
        text(435, 88, 't')
        text(230, 183, 'İki paralel düzlem · 3B bölge', True)
    elif key in ('circularity', 'circular_runout', 'position', 'concentricity'):
        if key in ('position', 'concentricity'):
            oval(160, 30, 300, 170)
            line(230, 40, 230, 160, arrow='both')
            text(250, 98, 'Øt')
            text(230, 183, 'Silindirik bölgenin enine kesiti', True)
        else:
            oval(150, 20, 310, 180)
            canvas.create_oval(*coords([176, 46, 284, 154]), fill=color(INPUT), outline=color(ACCENT), tags='zone')
            line(284, 100, 310, 100, arrow='both')
            text(333, 100, 't')
        if spec.datums:
            canvas.create_line(*coords([100, 100, 360, 100]), fill=color(MUTED), dash=(4, 3), tags='datum')
            text(230, 198, 'Datum ekseni '+spec.datums[0], True)
    elif key in ('cylindricity', 'total_runout'):
        rect(75, 52, 385, 146)
        canvas.create_rectangle(*coords([75, 77, 385, 121]), fill=color(INPUT), outline=color(ACCENT), tags='zone')
        line(400, 52, 400, 77, arrow='both')
        text(423, 65, 't')
        text(230, 27, 'İki eş eksenli silindir · boyuna kesit', True)
        if key == 'total_runout':
            canvas.create_line(*coords([42, 99, 418, 99]), fill=color(MUTED), dash=(5, 4), tags='datum')
            text(230, 183, 'Datum ekseni '+spec.datums[0], True)
        else:
            text(230, 183, 'Şekil kontrolü · datum gerekmez', True)
    elif key in ('line_profile', 'surface_profile'):
        for y in (44, 86):
            canvas.create_line(*coords([55, y+75, 135, y+20, 220, y, 305, y+25, 405, y+70]),
                               smooth=True, fill=color(ACCENT), width=max(1, 2*scale), tags='zone')
        line(220, 44, 220, 86, arrow='both')
        text(243, 64, 't')
        text(230, 166, 'Toplam profil bölgesi · simetrik örnek', True)
        if spec.datums:
            text(230, 191, 'Datum '+ ' | '.join(spec.datums), True)
    elif key == 'symmetry':
        rect(190, 28, 270, 157)
        canvas.create_line(*coords([230, 15, 230, 175]), fill=color(MUTED), dash=(4, 3), tags='datum')
        line(190, 100, 270, 100, arrow='both')
        text(230, 85, 't')
        text(230, 193, 'Datum orta düzlemi '+spec.datums[0], True)
    else:
        if key == 'parallelism':
            rect(70, 66, 390, 108)
            line(408, 66, 408, 108, arrow='both')
            text(431, 87, 't')
        elif key == 'perpendicularity':
            rect(195, 30, 250, 158)
            line(195, 85, 250, 85, arrow='both')
            text(223, 68, 't')
            text(280, 140, '90°', True)
        elif key == 'angularity':
            line(110, 142, 300, 35)
            line(160, 158, 350, 51)
            line(208, 87, 244, 108, arrow='both')
            text(249, 82, 't')
            text(330, 143, '45° örnek', True)
        datum()
    text(230, 8, 'BOYUT '+fmt(spec.size)+' mm · ŞEMATİK BÖLGE', True)
