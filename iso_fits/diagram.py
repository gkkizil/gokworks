"""Tk üzerinde şematik montaj kesiti ve gerçek sapma ölçeğiyle bölge grafiği."""

from gui.theme import (INPUT, PANEL, TEXT, MUTED, BORDER, ACCENT, ACCENT_BG,
                       SUCCESS, AMBER, RED, UI_FONT, PRIMARY_TEXT)
from iso_fits.rules import CLASSIFICATION, format_mm, format_deviation, mm


def draw(canvas, fit, view, sample, appearance, scale):
    color = lambda pair: pair[1 if appearance == 'Dark' else 0]
    canvas.configure(background=color(INPUT))
    canvas.delete('all')
    width, height = canvas.winfo_width(), canvas.winfo_height()
    font = (UI_FONT, -round(11*scale))
    bold = (UI_FONT, -round(12*scale), 'bold')
    def text(x, y, value, fill=None, **kw):
        canvas.create_text(x, y, text=value, fill=fill or color(TEXT), font=kw.pop('font', font), **kw)
    if fit is None:
        text(width/2, height/2, 'Geçerli çap ve tolerans sınıflarını seçin.', fill=color(MUTED), width=width-32)
        return
    if view == 'Tolerans bölgeleri':
        low = min(fit.hole.lower_nm, fit.shaft.lower_nm, 0)
        high = max(fit.hole.upper_nm, fit.shaft.upper_nm, 0)
        padding = max((high-low)*.15, 1000)
        low -= padding; high += padding
        top, bottom = 28*scale, height-45*scale
        y = lambda value: top+(high-value)/(high-low)*(bottom-top)
        canvas.create_line(60*scale, y(0), width-22*scale, y(0), fill=color(MUTED), dash=(5, 4))
        text(12*scale, y(0), '0 µm', fill=color(MUTED), anchor='w')
        text(width/2, 10*scale, 'Sapmalar (µm) · 0 = nominal çap', fill=color(MUTED))
        for band, fraction, paint, role in [(fit.hole, .39, ACCENT, 'DELİK'), (fit.shaft, .74, MUTED, 'MİL')]:
            x = width*fraction; half = min(38*scale, width*.085)
            canvas.create_rectangle(x-half, y(band.upper_nm), x+half, y(band.lower_nm),
                                    fill=color(paint), outline=color(paint), tags='hole_band' if role == 'DELİK' else 'shaft_band')
            text(x, y(band.upper_nm)-10*scale, format_deviation(band.upper_nm, 'µm'))
            if band.lower_nm != band.upper_nm:
                text(x, y(band.lower_nm)+10*scale, format_deviation(band.lower_nm, 'µm'))
            text(x, height-15*scale, f'{role} · {band.code}', font=bold)
        return
    _draw_section(canvas, fit, sample, appearance, scale, color)


def _draw_section(canvas, fit, sample, appearance, scale, color):
    """Concentric longitudinal section; numeric values remain exact Decimal."""
    width = canvas.winfo_width()
    compact = width/scale < 440
    font = (UI_FONT, -round((10 if compact else 12)*scale))
    bold = (UI_FONT, -round((11 if compact else 13)*scale), 'bold')
    def text(x, y, value, fill=None, **kw):
        canvas.create_text(x, y, text=value, fill=fill or color(TEXT),
                           font=kw.pop('font', font), **kw)
    hole, shaft = fit.sample(sample)
    difference = hole-shaft
    # This is an explicitly unscaled illustration. A nonzero radial gap must
    # exceed the strokes, even for tiny differences or a large common offset.
    # Use the signed D-d relation, not deviations from the nominal diameter.
    maximum = mm(max(abs(fit.minimum_clearance_nm), abs(fit.maximum_clearance_nm)))
    radial_pixels = (6+10*float(abs(difference)/maximum))*scale if difference else 0
    nominal_height = 82*scale
    hole_height = nominal_height
    shaft_height = nominal_height+2*radial_pixels*(-1 if difference > 0 else 1)
    center = 112*scale
    left, right = width*.18, width*.82
    bore_top, bore_bottom = center-hole_height/2, center+hole_height/2
    outer_top, outer_bottom = bore_top-22*scale, bore_bottom+22*scale
    fill = color(PANEL)
    for y0, y1 in [(outer_top, bore_top), (bore_bottom, outer_bottom)]:
        canvas.create_rectangle(left, y0, right, y1, fill=fill, outline=color(MUTED), tags='housing')
        for x in range(round(left+8*scale), round(right), max(1, round(24*scale))):
            canvas.create_line(x, y1-2*scale, min(right-2*scale, x+min(20*scale, y1-y0-4)), y0+2*scale, fill=color(MUTED))
    shaft_top, shaft_bottom = center-shaft_height/2, center+shaft_height/2
    edge = color(SUCCESS if difference > 0 else RED if difference < 0 else AMBER)
    canvas.create_line(12*scale, center, width-12*scale, center,
                       fill=color(MUTED), dash=(8, 3, 2, 3), tags='axis')
    shaft_left, shaft_right = width*.25, width*.75
    canvas.create_rectangle(shaft_left, shaft_top, shaft_right, shaft_bottom,
                            fill=color(ACCENT), outline=edge, width=2, tags='shaft')
    if difference > 0:
        for y0, y1 in [(bore_top, shaft_top), (shaft_bottom, bore_bottom)]:
            canvas.create_rectangle(shaft_left, y0, shaft_right, y1,
                                    fill=color(ACCENT_BG), outline=edge, tags='clearance')
    elif difference < 0:
        # Red regions show dimensional overlap before elastic deformation,
        # rather than a physically assembled, undeformed interference fit.
        for y0, y1 in [(shaft_top, bore_top), (bore_bottom, shaft_bottom)]:
            canvas.create_rectangle(shaft_left, y0, shaft_right, y1, fill=color(RED),
                                    outline=color(RED), tags='overlap')
    canvas.create_line(left, bore_top, right, bore_top, fill=edge, width=2)
    canvas.create_line(left, bore_bottom, right, bore_bottom, fill=edge, width=2)

    # Dimension arrows span the full diameter. g spans one radial side only.
    for x, y0, y1, label, anchor in [(width*.09, bore_top, bore_bottom, 'D', 'e'),
                                    (width*.91, shaft_top, shaft_bottom, 'd', 'w')]:
        start = left if label == 'D' else shaft_right
        for y in (y0, y1):
            canvas.create_line(start, y, x, y, fill=color(MUTED), tags='extension')
        canvas.create_line(x, y0, x, y1, arrow='both', arrowshape=(5*scale, 6*scale, 2*scale),
                           fill=color(TEXT), tags=f'dimension_{label}')
        text(x+(-4 if label == 'D' else 4)*scale, center-9*scale, label, font=bold, anchor=anchor)
    if difference:
        gx = shaft_right-12*scale
        canvas.create_line(gx, min(bore_top, shaft_top), gx, max(bore_top, shaft_top),
                           fill=edge, arrow='both', arrowshape=(3*scale, 4*scale, 1.5*scale), tags='radial_dimension')
        text(right+4*scale, (bore_top+shaft_top)/2, 'g', fill=edge, font=bold, anchor='w')
    text(width/2, 16*scale, f'DELİK {fit.hole.code} · D = Ø{format_mm(hole)} mm',
         font=bold, width=width-24*scale, tags='hole_label')
    text(width/2, center, f'MİL {fit.shaft.code}\nd = Ø{format_mm(shaft)} mm',
         fill=color(PRIMARY_TEXT), font=bold,
         width=shaft_right-shaft_left-12*scale, tags='shaft_label')
    canvas.create_line(12*scale, 197*scale, width-12*scale, 197*scale, fill=color(BORDER))
    state = 'BOŞLUK VAR' if difference > 0 else 'SIKILIK VAR' if difference < 0 else 'SINIRDA TEMAS'
    text(width/2, 215*scale, f'Seçilen örnek: {state}', fill=edge, font=bold, tags='sample_state')
    if difference:
        relation = 'boşluk' if difference > 0 else 'sıkılık'
        text(width/2, 239*scale, f'D − d = {format_mm(difference, signed=True)} mm · {relation}',
             font=bold, width=width-24*scale, tags='diametral_result')
        text(width/2, 263*scale, f'Tek tarafta: g = {format_mm(abs(difference)/2)} mm ({relation})',
             width=width-24*scale, tags='radial_result')
    else:
        text(width/2, 239*scale, f'D = d = {format_mm(hole)} mm', font=bold, tags='diametral_result')
        text(width/2, 263*scale, 'Çapsal fark = 0 mm · Tek tarafta g = 0 mm', tags='radial_result')
    text(width/2, 290*scale, f'Tolerans çiftinin türü: {CLASSIFICATION[fit.kind]}',
         fill=color(MUTED), width=width-24*scale, tags='fit_kind')
