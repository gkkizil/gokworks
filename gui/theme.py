"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F1F6FC", "#101C30")
SIDEBAR = ("#F8FBFF", "#0C172A")
PANEL = ("#FFFFFF", "#192940")
INPUT = ("#F3F7FC", "#233650")
BORDER = ("#DCE6F2", "#364B67")
TEXT = ("#233955", "#E8F0FD")
MUTED = ("#61738D", "#A8B9D1")
ACCENT = ("#2F68AD", "#8AB9F0")
ACCENT_HOVER = ("#25568F", "#A8CEF8")
ACCENT_BG = ("#E7F0FC", "#294364")
PRIMARY_TEXT = ("#FFFFFF", "#10233E")
SUCCESS = ("#2B6EAE", "#91C0F2")
AMBER = ("#896018", "#E4C494")
RED = ("#B23F52", "#F1A7B1")
SECONDARY = ("#EAF1FA", "#263B58")
HOVER = ("#DFEAF8", "#365273")
NAV_TEXT = ("#2B4260", "#EDF3FE")
NAV_MUTED = ("#61728B", "#AFBED4")
NAV_ACTIVE = ("#E1EDFC", "#2B4568")
NAV_ACCENT = ("#285D98", "#B8D8FB")
NAV_HOVER = ("#ECF3FC", "#233C5C")
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
