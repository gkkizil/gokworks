"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#EFF3F8", "#0E1624")
SIDEBAR = ("#142033", "#0B1320")
PANEL = ("#FFFFFF", "#162133")
INPUT = ("#F5F7FB", "#1B293D")
BORDER = ("#DCE4EE", "#2C3C52")
TEXT = ("#1C2B40", "#EAF0F8")
MUTED = ("#5E7087", "#A0B1C8")
ACCENT = ("#087D68", "#55DEBC")
ACCENT_BG = ("#E3F4EE", "#183E3A")
GREEN = ("#087D59", "#75DDB3")
AMBER = ("#94600D", "#EDC17B")
RED = ("#B83450", "#FA9AAA")
SECONDARY = ("#E8EDF5", "#24334A")
HOVER = ("#E2E9F2", "#30425C")
# Navigation stays dark in both appearances, independent of content surfaces.
NAV_TEXT = ("#EEF4FC", "#EEF4FC")
NAV_MUTED = ("#A8B8CE", "#A8B8CE")
NAV_ACTIVE = ("#234740", "#1C3C37")
NAV_ACCENT = ("#78E7C4", "#78E7C4")
NAV_HOVER = ("#21334C", "#1D2C42")
UI_FONT = "Segoe UI" if os.name == "nt" else "Helvetica"
MONO_FONT = "Consolas" if os.name == "nt" else "Courier"
