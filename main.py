"""GOKWORKS uygulamasını başlatır."""

from gui_qt.app import main


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        from gui.package_check import run
        raise SystemExit(run(sys.argv[2]))
    main()
