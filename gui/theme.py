"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F3F5F4", "#000000")
SIDEBAR = ("#F3F5F4", "#080808")
PANEL = ("#FFFFFF", "#0B0B0B")
INPUT = ("#F7F9F8", "#101010")
BORDER = ("#DFE5E2", "#262626")
TEXT = ("#202C28", "#EEF2F0")
MUTED = ("#63716A", "#A5AEA9")
ACCENT = ("#177C65", "#52DEBC")
ACCENT_BG = ("#E7F4EE", "#173A33")
GREEN = ("#16815D", "#75DDB3")
AMBER = ("#996722", "#E8BC73")
RED = ("#B63C50", "#F08D99")
SECONDARY = ("#EDF1EF", "#191919")
HOVER = ("#E2E9E5", "#242424")
UI_FONT = "Segoe UI" if os.name == "nt" else "Helvetica"
MONO_FONT = "Consolas" if os.name == "nt" else "Courier"
