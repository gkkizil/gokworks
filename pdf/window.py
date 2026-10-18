"""Backward-compatible launch path; the desktop UI is entirely Qt Widgets."""
from gui_qt.app import MainWindow as GokworksPdfApp, main

if __name__ == "__main__":
    raise SystemExit(main())
