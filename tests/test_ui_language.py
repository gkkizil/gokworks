"""Turkish casing, visible glyphs and unsupported rendering detection."""

from tkinter import font
from unittest.mock import patch

from gui.text import turkish_upper
from gui.theme import UI_FONT, MONO_FONT
from gui.typography import check_turkish_fonts
from support.gui import GuiTestCase


class TurkishRenderingTests(GuiTestCase):
    def test_turkish_letters_are_drawable_in_ui_and_log_fonts(self):
        for family in (UI_FONT, MONO_FONT):
            for weight in ('normal', 'bold'):
                face = font.Font(root=self.app, family=family, size=14, weight=weight)
                for char in 'ÇçĞğİıÖöŞşÜü':
                    with self.subTest(family=family, weight=weight, char=char):
                        self.assertGreater(face.measure(char), 0)
        self.app._switch_mode('bom')
        self.assertEqual(self.app.nav_buttons['bom'].cget('text'), 'BOM - ürün ağacı')
        self.app.bom_widgets['tabs'].set('ürün ağacı')
        self.assertEqual(self.app.bom_widgets['tabs'].get(), 'ürün ağacı')

    def test_uppercase_headings_use_turkish_dotted_i(self):
        self.assertEqual(turkish_upper('ürün ağacı'), 'ÜRÜN AĞACI')
        self.assertEqual(turkish_upper('eski işaretler'), 'ESKİ İŞARETLER')
        self.app._switch_mode('geometric_tolerances')
        self.assertEqual(self.app.gdt_widgets['groups']['Şekil'].cget('text'), 'ŞEKİL')
        self.assertEqual(self.app.gdt_widgets['groups']['Eski işaretler'].cget('text'), 'ESKİ İŞARETLER')

    def test_missing_glyph_is_reported_instead_of_silently_losing_a_letter(self):
        original = font.Font.measure
        def missing(face, text, *args, **kwargs):
            return 0 if text == 'Ğ' else original(face, text, *args, **kwargs)
        with patch.object(font.Font, 'measure', missing):
            with self.assertRaisesRegex(RuntimeError, 'Türkçe harfler görüntülenemiyor: Ğ'):
                check_turkish_fonts(self.app)
