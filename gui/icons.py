"""Uygulama logosu ve Pillow ile çizilen ölçeklenebilir arayüz ikonları.

Font veya çevrimiçi ikon servisi gerekmez. CTkImage nesneleri her uygulama
penceresinde ayrı tutulur; farklı Tk kökleri PhotoImage paylaşmaz.
"""

import os
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

ASSETS = Path(__file__).resolve().parent / "assets"
WINDOW_ICON_PATH = ASSETS / "GOK_app_windows.ico"


def make_logo(width=144):
    with Image.open(ASSETS / "GOK_logo_light_UI_1024.png") as source:
        light = source.copy()
    with Image.open(ASSETS / "GOK_logo_dark_UI_1024.png") as source:
        dark = source.copy()
    height = round(width * light.height / light.width)
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(width, height))


def set_window_icon(window):
    if os.name == "nt":
        # Calling CTk's method also prevents its delayed blue default icon.
        window.iconbitmap(str(WINDOW_ICON_PATH))
    else:
        with Image.open(WINDOW_ICON_PATH) as source:
            window._window_icon = ImageTk.PhotoImage(source.copy(), master=window)
        window.iconphoto(True, window._window_icon)


def make_icon(name, color, size=20):
    colors = color if isinstance(color, tuple) else (color, color)
    return ctk.CTkImage(light_image=_draw_icon(name, colors[0]),
                        dark_image=_draw_icon(name, colors[1]), size=(size, size))


def _draw_icon(name, color):
    scale = 4
    image = Image.new("RGBA", (24 * scale, 24 * scale))
    draw = ImageDraw.Draw(image)

    def line(points, width=1.6):
        draw.line([(round(x * scale), round(y * scale)) for x, y in points],
                  fill=color, width=round(width * scale), joint="curve")

    def box(bounds, radius=2, fill=None):
        draw.rounded_rectangle(tuple(round(value * scale) for value in bounds),
                               radius=round(radius * scale), outline=color,
                               width=round(1.6 * scale), fill=fill)

    def circle(bounds, fill=None):
        draw.ellipse(tuple(round(value * scale) for value in bounds),
                     outline=color, width=round(1.6 * scale), fill=fill)

    if name == "folder":
        line([(3, 8), (3, 5), (9, 5), (11, 8), (21, 8), (19, 19), (3, 19), (3, 8), (21, 8)])
    elif name == "file":
        line([(14, 3), (5, 3), (5, 21), (19, 21), (19, 8), (14, 3), (14, 8), (19, 8)])
        line([(8, 13), (16, 13)])
        line([(8, 17), (14, 17)])
    elif name == "layers":
        line([(3, 8), (12, 3), (21, 8), (12, 13), (3, 8)])
        line([(3, 12), (12, 17), (21, 12)])
        line([(3, 16), (12, 21), (21, 16)])
    elif name == 'bolt':
        line([(8, 3), (16, 3), (19, 6), (19, 9), (5, 9), (5, 6), (8, 3)])
        line([(9, 9), (9, 21), (15, 21), (15, 9)])
        for y in (12, 15, 18):
            line([(8, y+1), (16, y-1)])
    elif name == 'weight':
        circle((9, 2, 15, 8))
        line([(7, 7), (17, 7), (21, 21), (3, 21), (7, 7)])
        line([(8, 16), (16, 16)])
    elif name == 'ruler':
        box((3, 7, 21, 17), radius=1)
        for x in (7, 11, 15, 19):
            line([(x, 7), (x, 11 if x % 8 == 7 else 13)])
    elif name == 'tree':
        box((3, 2, 11, 8), radius=1)
        line([(7, 9), (7, 19), (13, 19)])
        line([(7, 12), (13, 12)])
        box((14, 9, 22, 15), radius=1)
        box((14, 17, 22, 23), radius=1)
    elif name == 'target':
        circle((5, 5, 19, 19))
        circle((9, 9, 15, 15))
        line([(12, 2), (12, 7)])
        line([(12, 17), (12, 22)])
        line([(2, 12), (7, 12)])
        line([(17, 12), (22, 12)])
    elif name == "tools":
        line([(4, 4), (20, 20)])
        line([(4, 20), (20, 4)])
        line([(16, 3), (21, 3), (21, 8)])
        circle((2, 16, 8, 22))
    elif name == "arrow":
        line([(4, 12), (20, 12)])
        line([(14, 6), (20, 12), (14, 18)])
    elif name == "stop":
        box((6, 6, 18, 18), radius=2)
    elif name == "search":
        circle((3, 3, 16, 16))
        line([(15, 15), (21, 21)])
    elif name == "close":
        line([(6, 6), (18, 18)])
        line([(18, 6), (6, 18)])
    elif name == "download":
        line([(12, 3), (12, 15)])
        line([(7, 10), (12, 15), (17, 10)])
        line([(4, 15), (4, 21), (20, 21), (20, 15)])
    elif name == "check":
        circle((2, 2, 22, 22))
        line([(7, 12), (10, 15), (17, 8)])
    elif name == "skip":
        circle((2, 2, 22, 22))
        line([(7, 12), (17, 12)])
    elif name == "error":
        circle((2, 2, 22, 22))
        line([(12, 6), (12, 13)])
        circle((11, 16, 13, 18), fill=color)
    elif name == "copy":
        box((8, 8, 21, 21))
        line([(16, 5), (16, 3), (3, 3), (3, 16), (5, 16)])
    else:
        raise ValueError(f"Bilinmeyen arayüz ikonu: {name}")
    return image
