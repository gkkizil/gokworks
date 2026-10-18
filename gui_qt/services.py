"""Small worker entry points around unchanged automation services."""

from pathlib import Path
from pdf.exporter import find_drawings
from dxf_dwg.exporter import find_parts


def scan_files(mode, source, recursive, events, stop):
    finder = find_drawings if mode == 'pdf' else find_parts
    files = finder(source, recursive, stop)
    events.put(('files', files))
    events.put(('done', dict(state='cancelled' if stop.is_set() else 'preview', total=len(files))))


def discover_assemblies(source, events, stop):
    from naming.source import discover_assemblies as discover
    files = discover(source, stop)
    events.put(('assemblies', files))


def write_bom(result, path, events, stop):
    from bom.exporter import export_excel, Cancelled
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
    try:
        import pythoncom
        from solidworks.connection import connect_to_solidworks
        from pdf.exporter import read_com_value
        pythoncom.CoInitialize()
        initialized = True
        app = connect_to_solidworks()
        revision = str(read_com_value(app, 'RevisionNumber'))
        events.put(('connection_done', dict(connected=True, revision=revision)))
    except Exception as error:
        events.put(('connection_done', dict(connected=False, error=str(error))))
    finally:
        if initialized:
            pythoncom.CoUninitialize()
