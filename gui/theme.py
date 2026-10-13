"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F0F4F1", "#17231F")
SIDEBAR = ("#FAFCFA", "#111C18")
PANEL = ("#FFFFFF", "#203029")
INPUT = ("#F4F7F5", "#293B32")
BORDER = ("#DFE7E2", "#3A4D42")
TEXT = ("#273B31", "#EAF0EC")
MUTED = ("#607268", "#ACBDB3")
ACCENT = ("#286A54", "#A0D7BC")
ACCENT_HOVER = ("#205941", "#B7E5CD")
ACCENT_BG = ("#E7F1E9", "#30483B")
GREEN = ("#26765C", "#A0D6BC")
AMBER = ("#896018", "#E4C494")
RED = ("#B23F52", "#F1A7B1")
SECONDARY = ("#EBF1EC", "#2D4035")
HOVER = ("#E1EBE3", "#3A5142")
NAV_TEXT = ("#2B3D31", "#EDF3EF")
NAV_MUTED = ("#66766D", "#AFBEB5")
NAV_ACTIVE = ("#E3EEE6", "#2D4436")
NAV_ACCENT = ("#276346", "#B8E5CA")
NAV_HOVER = ("#EDF3EE", "#243A2D")
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
