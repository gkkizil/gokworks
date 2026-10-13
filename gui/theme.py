"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F1F6FC", "#15171C")
SIDEBAR = ("#F8FBFF", "#101216")
PANEL = ("#FFFFFF", "#1E2128")
INPUT = ("#F3F7FC", "#272B34")
BORDER = ("#DCE6F2", "#3C424F")
TEXT = ("#233955", "#ECEEF4")
MUTED = ("#61738D", "#ADB4C3")
ACCENT = ("#2F68AD", "#8AB9F0")
ACCENT_HOVER = ("#25568F", "#A8CEF8")
ACCENT_BG = ("#E7F0FC", "#253A55")
PRIMARY_TEXT = ("#FFFFFF", "#10233E")
SUCCESS = ("#2B6EAE", "#91C0F2")
AMBER = ("#896018", "#E4C494")
RED = ("#B23F52", "#F1A7B1")
SECONDARY = ("#EAF1FA", "#2B303B")
HOVER = ("#DFEAF8", "#353D4A")
NAV_TEXT = ("#2B4260", "#F0F2F7")
NAV_MUTED = ("#61728B", "#B0B7C5")
NAV_ACTIVE = ("#E1EDFC", "#293D57")
NAV_ACCENT = ("#285D98", "#B8D8FB")
NAV_HOVER = ("#ECF3FC", "#272E39")
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
