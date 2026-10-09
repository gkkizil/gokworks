"""Tk üzerinde şematik montaj kesiti ve gerçek sapma ölçeğiyle bölge grafiği."""

from gui.theme import INPUT, PANEL, TEXT, MUTED, BORDER, ACCENT, GREEN, RED, UI_FONT
from iso_fits.rules import format_mm, format_deviation


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
        canvas.create_line(30*scale, y(0), width-22*scale, y(0), fill=color(MUTED), dash=(5, 4))
        text(32*scale, y(0)-9*scale, '0 · nominal çap', fill=color(MUTED), anchor='w')
        for band, fraction, paint, role in [(fit.hole, .39, ACCENT, 'DELİK'), (fit.shaft, .74, MUTED, 'MİL')]:
            x = width*fraction; half = min(38*scale, width*.085)
            canvas.create_rectangle(x-half, y(band.upper_nm), x+half, y(band.lower_nm),
                                    fill=color(paint), outline=color(paint))
            text(x, y(band.upper_nm)-10*scale, format_deviation(band.upper_nm, 'µm'))
            text(x, y(band.lower_nm)+10*scale, format_deviation(band.lower_nm, 'µm'))
            text(x, height-15*scale, f'{role} · {band.code}', font=bold)
        return
    hole, shaft = fit.sample(sample)
    difference = hole-shaft
    hole_dev = float(hole-fit.hole.nominal_mm)
    shaft_dev = float(shaft-fit.shaft.nominal_mm)
    # Keep the magnification fixed while switching between sample sizes.
    maximum = max(*(abs(value)/1_000_000 for band in (fit.hole, fit.shaft)
                    for value in (band.lower_nm, band.upper_nm)), .001)
    nominal_height = min(75*scale, height*.32)
    exaggeration = nominal_height*.4/maximum
    hole_height = nominal_height+hole_dev*exaggeration
    shaft_height = nominal_height+shaft_dev*exaggeration
    center = height*.43; left, right = width*.22, width*.78
    bore_top, bore_bottom = center-hole_height/2, center+hole_height/2
    outer_top, outer_bottom = bore_top-24*scale, bore_bottom+24*scale
    fill = color(PANEL)
    for y0, y1 in [(outer_top, bore_top), (bore_bottom, outer_bottom)]:
        canvas.create_rectangle(left, y0, right, y1, fill=fill, outline=color(BORDER))
        for x in range(round(left+8*scale), round(right), max(1, round(24*scale))):
            canvas.create_line(x, y1-2*scale, min(right-2*scale, x+min(20*scale, y1-y0-4)), y0+2*scale, fill=color(BORDER))
    shaft_top, shaft_bottom = center-shaft_height/2, center+shaft_height/2
    edge = color(GREEN if difference >= 0 else RED)
    canvas.create_line(width*.12, center, width*.88, center, fill=color(MUTED), dash=(5, 4))
    canvas.create_rectangle(width*.31, shaft_top, width*.69, shaft_bottom,
                            fill=color(ACCENT), outline=edge, width=2)
    canvas.create_line(left, bore_top, right, bore_top, fill=edge, width=2)
    canvas.create_line(left, bore_bottom, right, bore_bottom, fill=edge, width=2)
    if difference < 0:
        for y0, y1 in [(shaft_top, bore_top), (bore_bottom, shaft_bottom)]:
            canvas.create_rectangle(width*.31, y0, width*.69, y1, fill=color(RED), outline=color(RED), stipple='gray50')
    text(width/2, 12*scale, f'DELİK · {fit.hole.code} · Ø{format_mm(hole)} mm', font=bold)
    text(width/2, center, f'MİL · {fit.shaft.code}',
         fill='#10231D' if appearance == 'Dark' else '#FFFFFF', font=bold)
    text(width/2, height-40*scale, f'Mil çapı: {format_mm(shaft)} mm')
    text(width/2, height-18*scale,
         f"{'Boşluk' if difference >= 0 else 'Sıkılık'}: {format_mm(abs(difference))} mm", fill=edge, font=bold)
