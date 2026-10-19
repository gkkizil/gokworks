"""GOKWORKS uygulamasını başlatır."""

def main():
    # The internal PDF worker must start without importing Qt or creating a GUI.
    from gui_qt.app import main as run
    return run()


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 6 and sys.argv[1] == '--process-exit-watch':
        from solidworks.process_watch import run_watch
        raise SystemExit(run_watch(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]))
    if len(sys.argv) == 3 and sys.argv[1] == '--pdf-export-worker':
        from pdf.process import run_worker
        raise SystemExit(run_worker(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        from gui.package_check import run
        raise SystemExit(run(sys.argv[2]))
    main()
