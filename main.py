"""GOKWORKS uygulamasını başlatır."""

def main():
    # The internal PDF worker must start without importing Qt or creating a GUI.
    from gui_qt.app import main as run
    return run()


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--pdf-export-worker':
        from pdf.process import run_worker
        raise SystemExit(run_worker(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        from gui.package_check import run
        raise SystemExit(run(sys.argv[2]))
    main()
