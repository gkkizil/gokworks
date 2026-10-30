"""Small worker entry points around unchanged automation services."""

from pathlib import Path
from solidworks import diagnostics


def find_drawings(*args, **kwargs):
    from modules.pdf.exporter import find_drawings as run
    return run(*args, **kwargs)


def scan_files(mode, source, recursive, events, stop):
    # The PDF workbench must not import the DXF parser/NumPy at startup.
    if mode != 'pdf':
        from modules.dxf_dwg.exporter import find_parts
    finder = find_drawings if mode == 'pdf' else find_parts
    files = finder(source, recursive, stop)
    events.put(('files', files))
    events.put(('done', dict(state='cancelled' if stop.is_set() else 'preview', total=len(files))))


def discover_assemblies(source, events, stop):
    from modules.naming.source import discover_assemblies as discover
    files = discover(source, stop)
    events.put(('assemblies', files))


def write_bom(result, path, events, stop):
    from modules.bom.exporter import export_excel, Cancelled
    try:
        export_excel(result, path, stop)
        outcome = dict(state='exported', path=str(path))
    except Cancelled:
        outcome = dict(state='cancelled')
    except Exception as error:
        outcome = dict(state='error', error=str(error))
    events.put(('bom_done', outcome))


def check_connection(events, stop):
    initialized = False
    app = None
    try:
        import pythoncom
        from solidworks.connection import connect_to_solidworks
        from modules.pdf.exporter import read_com_value
        pythoncom.CoInitialize()
        initialized = True
        diagnostics.record('connection_check_connect')
        app = connect_to_solidworks()
        revision = str(read_com_value(app, 'RevisionNumber'))
        events.put(('connection_done', dict(connected=True, revision=revision)))
    except Exception as error:
        events.put(('connection_done', dict(connected=False, error=str(error))))
    finally:
        if initialized:
            diagnostics.record('connection_check_release_application')
            app = None
            diagnostics.record('connection_check_uninitialize_com')
            pythoncom.CoUninitialize()
