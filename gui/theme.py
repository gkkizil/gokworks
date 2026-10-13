"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F3F5F6", "#171F2A")
SIDEBAR = ("#202C3A", "#151E29")
PANEL = ("#FFFFFF", "#202C3B")
INPUT = ("#F5F7F8", "#263444")
BORDER = ("#E3E8EC", "#364556")
TEXT = ("#283647", "#E8EDF3")
MUTED = ("#657487", "#ADBBCC")
ACCENT = ("#287567", "#8ACFBD")
ACCENT_HOVER = ("#226658", "#A3DECE")
ACCENT_BG = ("#E9F2EF", "#2A423E")
GREEN = ("#26765C", "#A0D6BC")
AMBER = ("#896018", "#E4C494")
RED = ("#B23F52", "#F1A7B1")
SECONDARY = ("#EDF1F3", "#2A394B")
HOVER = ("#E3EBE9", "#354A50")
# Navigation stays dark in both appearances, independent of content surfaces.
NAV_TEXT = ("#EDF2F6", "#EDF2F6")
NAV_MUTED = ("#B2BECC", "#B2BECC")
NAV_ACTIVE = ("#34524D", "#2C4742")
NAV_ACCENT = ("#B8E5D7", "#B8E5D7")
NAV_HOVER = ("#30404E", "#293945")
UI_FONT = "Segoe UI" if os.name == "nt" else "Helvetica"
MONO_FONT = "Consolas" if os.name == "nt" else "Courier"


def configure_widget_theme(theme):
    """Keep native controls consistent across cached workspaces."""
    for widget in ("CTkEntry", "CTkComboBox"):
        theme[widget].update(corner_radius=10, border_width=1,
                             fg_color=INPUT, border_color=BORDER, text_color=TEXT)
    theme["CTkEntry"].update(placeholder_text_color=MUTED)
    theme["CTkComboBox"].update(button_color=SECONDARY, button_hover_color=HOVER)
    theme["CTkOptionMenu"].update(corner_radius=10)
    theme["CTkSegmentedButton"].update(corner_radius=10, border_width=4)
