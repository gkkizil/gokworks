"""Prevent silently missing Turkish letters in unsupported Tk/font builds."""

from tkinter import font
from gui.theme import UI_FONT, MONO_FONT


def check_turkish_fonts(root):
    for family in (UI_FONT, MONO_FONT):
        for weight in ('normal', 'bold'):
            face = font.Font(root=root, family=family, size=14, weight=weight)
            missing = ''.join(c for c in 'ÇçĞğİıÖöŞşÜü' if face.measure(c) <= 0)
            if missing:
                raise RuntimeError(
                    f'Türkçe harfler görüntülenemiyor: {missing}. '
                    'Türkçe karakterleri destekleyen bir Tk kurulumu ve yazı tipi kullanın.')
