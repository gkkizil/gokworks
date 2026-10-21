"""Sade ISO geçme seçimi için canlı, ölçeksiz montaj kesiti.

Hesaplar ``Fit.sample`` üzerinden tam Decimal değerleriyle yapılır. Çizimde
boşluk ve sıkılık görülebilmeleri için büyütülür; fiziksel deformasyon veya
montaj yöntemi modellenmez. Manuel tolerans görünümünden bağımsızdır.
"""

from shared.theme import ACCENT, ACCENT_BG, BORDER, MUTED, PANEL, PRIMARY_TEXT, RED, TEXT, UI_FONT
from modules.iso_fits.rules import format_mm, mm


def _nominal(value):
    """Keep the nominal label short without rounding the supplied diameter."""
    result = format(value, 'f')
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    return result.replace('.', ',')


def draw_selection(canvas, fit, appearance, scale, sample='Orta değer'):
    """Draw the selected tolerance sample in the current canvas dimensions."""
    color = lambda pair: pair[1 if appearance == 'Dark' else 0]
    canvas.configure(background=color(PANEL))
    canvas.delete('all')
    width, height = canvas.winfo_width(), canvas.winfo_height()
    scale = max(float(scale), .1)
    if width < 40 * scale or height < 40 * scale:
        return

    compact = width / scale < 420
    font = (UI_FONT, -max(1, round((10 if compact else 11) * scale)))
    bold = (UI_FONT, -max(1, round((11 if compact else 12) * scale)), 'bold')
    small = (UI_FONT, -max(1, round(10 * scale)))

    def text(x, y, value, *, fill=None, **kwargs):
        canvas.create_text(x, y, text=value, fill=fill or color(TEXT),
                           font=kwargs.pop('font', font), **kwargs)

    if fit is None:
        text(width / 2, height / 2, 'Geçerli bir nominal çap girin.',
             fill=color(MUTED), width=max(1, width - 32 * scale), tags='empty_state')
        return

    hole, shaft = fit.sample(sample)
    difference = hole - shaft
    maximum = mm(max(abs(fit.minimum_clearance_nm), abs(fit.maximum_clearance_nm)))
    # Only the signed, actual D-d relation determines the illustration.
    # Decimal division is retained until converting the final pixel ratio.
    ratio = float(abs(difference) / maximum) if maximum else 0
    diagram_top = 48 * scale
    narrow = width / scale < 330
    diagram_bottom = max(diagram_top + 20 * scale, height - (64 if narrow else 48) * scale)
    available = max(20 * scale, diagram_bottom - diagram_top)
    center = (diagram_top + diagram_bottom) / 2
    bore_height = min(96 * scale, available * .40)
    housing_thickness = min(55 * scale, available * .23)
    amplification = min(16 * scale, bore_height * .20) * (.4 + .6 * ratio) if difference else 0
    shaft_height = bore_height + 2 * amplification * (-1 if difference > 0 else 1)

    housing_width = min(350 * scale, width * .65)
    shaft_width = housing_width * .68
    left, right = (width - housing_width) / 2, (width + housing_width) / 2
    shaft_left, shaft_right = (width - shaft_width) / 2, (width + shaft_width) / 2
    bore_top, bore_bottom = center - bore_height / 2, center + bore_height / 2
    shaft_top, shaft_bottom = center - shaft_height / 2, center + shaft_height / 2

    text(20 * scale, 21 * scale, 'MONTAJ KESİTİ', fill=color(MUTED),
         font=small, anchor='w', tags='diagram_title')
    housing_fill = '#EDF0F5' if appearance != 'Dark' else '#343A45'
    hatch_color = '#A8B3C2' if appearance != 'Dark' else '#58616F'
    for top, bottom, edge in ((bore_top - housing_thickness, bore_top, 'bottom'),
                              (bore_bottom, bore_bottom + housing_thickness, 'top')):
        canvas.create_rectangle(left, top, right, bottom, fill=housing_fill,
                                outline=color(BORDER), width=max(1, scale), tags='housing')
        hatch_length = min(8 * scale, housing_thickness * .2)
        hatch_left = left + 18 * scale
        while hatch_left + hatch_length < right:
            y0, y1 = ((bottom - 2 * scale, bottom - 2 * scale - hatch_length)
                      if edge == 'bottom' else (top + 2 * scale + hatch_length, top + 2 * scale))
            canvas.create_line(hatch_left, y0, hatch_left + hatch_length, y1,
                               fill=hatch_color, width=max(1, scale), tags='hatch')
            hatch_left += 30 * scale

    axis_half = min(width * .43, housing_width * .65)
    canvas.create_line(width / 2 - axis_half, center, width / 2 + axis_half, center,
                       fill=color(BORDER), dash=(max(1, round(4 * scale)), max(1, round(3 * scale))),
                       tags='axis')

    shaft_color = color(RED if difference < 0 else ACCENT)
    canvas.create_rectangle(shaft_left, shaft_top, shaft_right, shaft_bottom,
                            fill=shaft_color, outline=shaft_color,
                            width=max(1, scale), tags='shaft')
    if difference > 0:
        for top, bottom in ((bore_top, shaft_top), (shaft_bottom, bore_bottom)):
            canvas.create_rectangle(shaft_left, top, shaft_right, bottom,
                                    fill=color(ACCENT_BG), outline='', tags='clearance')
    elif difference < 0:
        overlap_fill = '#973347' if appearance != 'Dark' else '#CF6F81'
        for top, bottom in ((shaft_top, bore_top), (bore_bottom, shaft_bottom)):
            canvas.create_rectangle(shaft_left, top, shaft_right, bottom,
                                    fill=overlap_fill, outline='', tags='overlap')

    nominal = _nominal(fit.hole.nominal_mm)
    # Class labels describe nominal sizes; the second line gives the actual
    # exact sample diameter, so the drawing cannot imply nominal = actual.
    hole_label_y = bore_top - housing_thickness / 2 - 8 * scale
    if housing_thickness > 30 * scale:
        text(left + 10 * scale, hole_label_y, f'DELİK · Ø{nominal} {fit.hole.code}',
             anchor='w', width=housing_width - 20 * scale, font=bold, tags='hole_label')
        text(left + 10 * scale, hole_label_y + 16 * scale, f'Ø{format_mm(hole)} mm',
             anchor='w', fill=color(MUTED), font=small, tags='hole_sample')
    else:
        text(width / 2, bore_top - housing_thickness / 2,
             f'DELİK · Ø{nominal} {fit.hole.code}', font=bold, tags='hole_label')
    text(width / 2, center - 8 * scale, f'MİL · Ø{nominal} {fit.shaft.code}',
         fill=color(PRIMARY_TEXT), font=bold,
         width=max(1, shaft_width - 12 * scale), tags='shaft_label')
    if shaft_height > 37 * scale:
        text(width / 2, center + 12 * scale, f'Ø{format_mm(shaft)} mm',
             fill=color(PRIMARY_TEXT), font=small,
             width=max(1, shaft_width - 12 * scale), tags='shaft_sample')

    state = 'Boşluk var' if difference > 0 else 'Sıkılık var' if difference < 0 else 'Sınırda temas'
    if narrow:
        text(width / 2, height - 32 * scale, f'{sample} · {state}',
             fill=shaft_color, font=small, tags='sample_state')
        text(width / 2, height - 15 * scale, 'Şematik · ölçeksiz',
             fill=color(MUTED), font=small, tags='schematic_note')
    else:
        text(20 * scale, height - 19 * scale, f'{sample} · {state}',
             fill=shaft_color, font=small, anchor='w', tags='sample_state')
        text(width - 20 * scale, height - 19 * scale, 'Şematik · ölçeksiz',
             fill=color(MUTED), font=small, anchor='e', tags='schematic_note')
