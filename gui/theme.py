"""Masaüstü arayüzünün ortak renkleri ve yazı tipleri."""

import os

BG = ("#F2F4F7", "#0C1117")
SIDEBAR = ("#F8FAFC", "#111923")
PANEL = ("#FFFFFF", "#151F2A")
INPUT = ("#F7F9FC", "#0F1720")
BORDER = ("#E1E6ED", "#293746")
TEXT = ("#202937", "#ECF2F8")
MUTED = ("#687586", "#A1B0C0")
ACCENT = ("#177C65", "#52DEBC")
ACCENT_BG = ("#E7F4EE", "#173A33")
GREEN = ("#16815D", "#75DDB3")
AMBER = ("#996722", "#E8BC73")
RED = ("#BF4557", "#F08D99")
SECONDARY = ("#EFF2F6", "#223242")
HOVER = ("#E3E9EF", "#2C4053")
UI_FONT = "Segoe UI" if os.name == "nt" else "Helvetica"
MONO_FONT = "Consolas" if os.name == "nt" else "Courier"
