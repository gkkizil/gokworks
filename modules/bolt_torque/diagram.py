"""Schematic longitudinal bolt-joint section for the quick torque tool.

Only diameter/pitch and the existing calculated torque/preload are labelled.
Head, nut, grip, hole and plate geometry is illustrative, not catalogue data.
"""

from math import floor
from PySide6.QtGui import QTextOption

from gui_qt.theme import COLORS


def draw_section(scene, result, appearance, format_value):
    c = COLORS[appearance]
    scene.delete('all')
    scene.configure(background=c['panel'])

    def line(*points, color=None, **options):
        return scene.create_line(*points, fill=color or c['muted'],
                                 width=options.pop('width', 1.2), **options)

    def text(x, y, value, *, tag=None, color=None, bold=False, **options):
        item = scene.create_text(x, y, text=value, fill=color or c['text'],
                                 font=('Segoe UI', -17, 'bold') if bold else ('Segoe UI', -16),
                                 tags=tag or (), **options)
        if options.get('width') and tag != 'section_empty':
            # Numeric captions stay on one line. Segoe UI on Windows has
            # different metrics from the fallback fonts used on Linux.
            option = item.document().defaultTextOption()
            option.setWrapMode(QTextOption.NoWrap)
            item.document().setDefaultTextOption(option)
            item.setTextWidth(-1)
            bounds = item.boundingRect()
            item.setPos(x-bounds.width()/2,y-bounds.height()/2)
        bounds = item.sceneBoundingRect(); area = scene.sceneRect().adjusted(8,8,-8,-8)
        dx = max(area.left()-bounds.left(),min(0,area.right()-bounds.right()))
        dy = max(area.top()-bounds.top(),min(0,area.bottom()-bounds.bottom()))
        item.moveBy(dx,dy)
        return item

    def polygon(points, tag, *, fill=None, outline=None):
        return scene.create_polygon(points, fill=fill or c['input'],
                                    outline=outline or c['muted'], width=1.5, tags=tag)

    def section(x0, y0, x1, y1, reverse=False):
        scene.create_rectangle(x0, y0, x1, y1, fill=c['input'], outline=c['border'],
                               tags='clamped_parts')
        # Clip hatch strokes to each plate wall; the bolt bore remains clear.
        height = y1-y0
        for start in range(floor(x0-height), floor(x1), 12):
            left, right = max(x0, start), min(x1, start+height)
            if right <= left:
                continue
            first, last = y1-(left-start), y1-(right-start)
            if reverse:
                first, last = y0+y1-first, y0+y1-last
            line(left, first, right, last, color=c['muted'], width=.8, tags='plate_hatch')

    if result is None:
        text(250, 150, 'Geçerli ölçüler girildiğinde kesit burada görünür.',
             tag='section_empty', color=c['muted'], width=440)
        return

    y = 150
    # Modest diameter-dependent proportions keep M3 and M36 readable in the
    # same viewport. No unprovided length is presented as a real dimension.
    diameter = 26 + 14*result.diameter_mm/36
    top, bottom = y-diameter/2, y+diameter/2
    for x0, x1, reverse in ((139, 231, False), (235, 335, True)):
        section(x0, 88, x1, top-5, reverse)
        section(x0, bottom+5, x1, 208, reverse)
    line(24, y, 476, y, color=c['border'], dash=(6, 4), tags='bolt_axis')

    # Washers and a chamfered nut side elevation. Fasteners remain unhatched
    # in this longitudinal section; the projecting threaded end is visible.
    nut_half = diameter*.88
    for x0, x1 in ((132, 139), (335, 342)):
        scene.create_rectangle(x0, y-nut_half, x1, y+nut_half,
                               fill=c['selected'], outline=c['muted'], tags='washers')
    polygon((342, y-nut_half+6, 348, y-nut_half, 382, y-nut_half,
             388, y-nut_half+6, 388, y+nut_half-6, 382, y+nut_half,
             348, y+nut_half, 342, y+nut_half-6), 'nut_profile')
    for x in (354, 376):
        line(x, y-nut_half+2, x, y+nut_half-2, color=c['border'])

    polygon((131, top, 410, top, 415, top+5, 415, bottom-5,
             410, bottom, 131, bottom), 'bolt_shank', fill=c['selected'], outline=c['accent'])
    step = 4 + 24*result.pitch_mm/result.diameter_mm
    x = 252.
    while x < 410:
        line(x, top+2, x-step*.48, bottom-2, color=c['accent'], width=.9, tags='bolt_thread')
        x += step
    head_left = 132-diameter*1.4
    head_half = diameter*.95
    polygon((head_left, y-head_half+6, head_left+6, y-head_half,
             126, y-head_half, 132, y-head_half+6,
             132, y+head_half, head_left, y+head_half), 'bolt_head')
    line(head_left+8, y-head_half+3, head_left+8, y+head_half-3, color=c['border'])

    # Opposing axial arrows denote the target bolt tension, not an external
    # service load or an assessment of the plates/nut's capacity.
    if result.preload_n > 0:
        line(76, y, 28, y, color=c['accent'], width=2.2, arrow='last', tags='preload_arrow')
        line(424, y, 473, y, color=c['accent'], width=2.2, arrow='last', tags='preload_arrow')
        text(48, 126, 'F', color=c['accent'], bold=True)
        text(453, 126, 'F', color=c['accent'], bold=True)
    if result.torque_nm > 0:
        # Conventional tightening-moment symbol beside the head.
        scene.create_arc(78, 48, 124, 80, start=35, extent=285,
                         outline=c['accent'], width=2, tags='torque_arc')
        line(113, 77, 122, 68, color=c['accent'], width=2, arrow='last', tags='torque_arrow')
    text(116, 23, f'T ≈ {format_value(result.torque_nm)} N·m',
         tag='section_torque', color=c['accent'], bold=True, width=220)
    pitch = f'{result.pitch_mm:g}'.replace('.', ',')
    text(385, 23, f'{result.metric} × {pitch} · {result.grade}',
         tag='section_selection', color=c['muted'], width=210)
    text(255, 65, 'Sıkılan parçalar', color=c['muted'], tag='parts_label')
    line(255, 78, 255, 88, color=c['border'])
    line(head_left+12, y+head_half, 89, 217, color=c['muted'])
    text(79, 235, 'Cıvata', tag='bolt_label', color=c['muted'])
    line(370, y+nut_half, 397, 217, color=c['muted'])
    text(410, 235, 'Somun', tag='nut_label', color=c['muted'])
    d = f'{result.diameter_mm:g}'.replace('.', ',')
    text(250, 240, f'd = {d} mm · P = {pitch} mm', tag='section_dimensions', width=290)
    text(250, 276, f'Ön yük F = {format_value(result.preload_kn)} kN',
         tag='section_preload', color=c['accent'], bold=True, width=450)
