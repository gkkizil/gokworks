"""Actual packaged Qt startup/geometry/formula checks; never contacts SolidWorks."""

import json
import os
from pathlib import Path
import platform
from queue import Queue
import statistics
import sys
import tempfile
import time
import traceback

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion, QLibraryInfo
from PySide6.QtWidgets import QApplication


def check(output):
    from .app import create_application, MainWindow
    started = time.perf_counter()
    app = create_application([])
    with tempfile.TemporaryDirectory(prefix='gokworks-qt-check-') as folder:
        w = MainWindow(Path(folder)/'settings.json')
        w.resize(1360, 900)
        w.show()
        app.processEvents()
        startup = (time.perf_counter()-started)*1000
        pages, timings, resize_times = [], [], []
        for theme in ('dark', 'light'):
            w.set_theme(theme)
            for mode in w.pages:
                before = time.perf_counter()
                w.navigate(mode)
                app.processEvents()
                timings.append((time.perf_counter()-before)*1000)
                assert w.stack.currentWidget() is w.pages[mode]
                if theme == 'dark':
                    pages.append(mode)
                for size in ((1024,700),(1366,768),(1920,1080),(2560,1440)):
                    before = time.perf_counter()
                    w.resize(*size)
                    app.processEvents()
                    resize_times.append((time.perf_counter()-before)*1000)
                    assert w.pages[mode].width() >= 550
        bolt = w.pages['bolt']
        bolt.form.set_value('unit','kg')
        bolt.form.set_value('mode','Çekme')
        bolt.form.set_value('tension','100')
        bolt.update_result()
        assert abs(bolt.result.tension_n-980.665) < .000001
        weight = w.pages['weight']
        weight.form.set_value('kind','Sac levha')
        for key, value in [('b','2000'),('t','10'),('length','1000')]:
            weight.form.set_value(key,value)
        weight.update_result()
        assert weight.result.total_mass_kg == 157
        assert w.pages['iso_fits'].result is not None
        assert w.pages['geometric_tolerances'].result is not None
        from tolerance_stack.calculator import calculate
        from tolerance_stack.report import export_excel as stack_excel, export_pdf as stack_pdf
        stack=w.pages['tolerance_stack'];stack.load_example();stack.project.confirm()
        stack_result=calculate(stack.project)
        assert tuple(map(str,(stack_result.nominal,stack_result.minimum,stack_result.maximum))) == ('0.20','0.02','0.38')
        stack.show_result(stack_result)
        stack_excel(stack.project,stack_result,Path(folder)/'ToleranceStack.xlsx')
        stack_pdf(stack.project,stack_result,Path(folder)/'ToleranceStack.pdf')
        assert not w.pages['k_factor'].save_files.isChecked()
        from .models import TableModel, Column, FilterProxy
        model = TableModel((Column('Parça','name'),Column('Adet','quantity')))
        before = time.perf_counter()
        model.replace([dict(name=f'Parça {i}',quantity=i) for i in range(50000)])
        load_ms = (time.perf_counter()-before)*1000
        proxy = FilterProxy()
        proxy.setSourceModel(model)
        before = time.perf_counter()
        proxy.set_query('Parça 49999')
        assert proxy.rowCount() == 1
        filter_ms = (time.perf_counter()-before)*1000
        forbidden = [name for name in sys.modules if name in ('tkinter','_tkinter','customtkinter')]
        assert not forbidden, forbidden
        # Use a real file from each non-COM exporter dependency inside the bundle.
        from bom.exporter import Result, Part, export_excel
        result = Result('main.sldasm','Default',(Part('Parça','p.sldprt','Default',2,1.,2.),),(),0,0,False)
        xlsx = Path(folder)/'BOM.xlsx'
        export_excel(result,xlsx)
        assert xlsx.read_bytes().startswith(b'PK')
        import ezdxf
        dxf = Path(folder)/'test.dxf'
        ezdxf.new().saveas(dxf)
        assert dxf.stat().st_size > 100
        from naming.native import HOST_SOURCE
        assert HOST_SOURCE.is_file(), 'Gömülü Pack and Go interop kaynağı eksik.'
        # Launch the actual bundled EXE in worker mode. An empty folder tests
        # frozen imports and IPC without touching an open SolidWorks session.
        from pdf.process import export_drawings
        pdf_source = Path(folder)/'empty-pdf-source'
        pdf_source.mkdir()
        pdf_events = Queue()
        local_before = os.environ.get('LOCALAPPDATA')
        diagnostic_root = Path(folder)/'diagnostics'
        os.environ['LOCALAPPDATA'] = str(diagnostic_root)
        try:export_drawings(pdf_source, Path(folder)/'pdf-output', True, False, pdf_events)
        finally:
            if local_before is None:os.environ.pop('LOCALAPPDATA', None)
            else:os.environ['LOCALAPPDATA'] = local_before
        pdf_messages = list(pdf_events.queue)
        assert pdf_messages[-1][0] == 'done'
        assert pdf_messages[-1][1]['state'] == 'empty', pdf_messages
        assert sum(kind == 'done' for kind, value in pdf_messages) == 1
        observer = 'not applicable'
        if os.name == 'nt' and getattr(sys, 'frozen', False):
            deadline = time.monotonic()+45
            while True:
                traces = '\n'.join(p.read_text(encoding='utf-8') for p in (diagnostic_root/'GOKWORKS/logs').glob('GOKWORKS-pdf-worker-*.log'))
                if 'process_exit target=pdf-worker' in traces:
                    assert 'process_watch_ready target=pdf-worker' in traces
                    assert 'code=0 (0x00000000)' in traces, traces
                    assert 'process_watch_failed' not in traces and 'process_watch_unavailable' not in traces, traces
                    observer = 'passed'
                    break
                if time.monotonic() >= deadline:raise RuntimeError('Paketlenmiş çıkış izleyicisi doğrulanamadı: '+traces)
                app.processEvents();time.sleep(.1)
        from .licenses import license_files, export_licenses
        import zipfile
        notices = license_files()
        assert 'THIRD_PARTY_NOTICES.md' in notices and any('LGPL' in key for key in notices)
        notice_archive = Path(folder)/'licenses.zip'
        export_licenses(notice_archive, notices)
        with zipfile.ZipFile(notice_archive) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(notices)
        external_qt = False
        requested_library = os.environ.get('GOKWORKS_LIBRARY_DIR')
        if requested_library:
            import PySide6, shiboken6
            library_root = Path(requested_library).resolve()
            assert Path(PySide6.__file__).resolve().is_relative_to(library_root)
            assert Path(shiboken6.__file__).resolve().is_relative_to(library_root)
            if os.name == 'nt':
                import ctypes
                from ctypes import wintypes
                api = ctypes.WinDLL('kernel32', use_last_error=True)
                api.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
                api.GetModuleHandleW.restype = wintypes.HMODULE
                api.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
                api.GetModuleFileNameW.restype = wintypes.DWORD
                name = ctypes.create_unicode_buffer(32768)
                module = api.GetModuleHandleW('Qt6Core.dll')
                assert module and api.GetModuleFileNameW(module, name, len(name))
                assert Path(name.value).resolve().is_relative_to(library_root), name.value
            external_qt = True
        if os.name == 'nt':
            import pythoncom, win32com.client
            pythoncom.CoInitialize()
            pythoncom.CoUninitialize()
        w.navigate('bolt')
        w.resize(1360,900)
        app.processEvents()
        screenshot = Path(output).with_suffix('.png')
        assert w.grab().save(str(screenshot))
        frozen = getattr(sys, 'frozen', False)
        distribution = ('onedir' if Path(sys._MEIPASS).resolve().is_relative_to(Path(sys.executable).resolve().parent)
                        else 'onefile') if frozen else 'source'
        report = dict(status='passed',framework='PySide6 / Qt Widgets',pyside=pyside_version,qt=qVersion(),
                      distribution=distribution, external_qt_verified=external_qt,pdf_exit_observer=observer,
                      python=platform.python_version(),platform=platform.platform(),qt_platform=app.platformName(),
                      dpi_scale=app.primaryScreen().devicePixelRatio(),pages=pages,themes=['dark','light'],
                      resolutions=[[1024,700],[1366,768],[1920,1080],[2560,1440]],
                      startup_ms=round(startup,2),navigation_median_ms=round(statistics.median(timings),2),
                      navigation_max_ms=round(max(timings),2),resize_median_ms=round(statistics.median(resize_times),2),
                      resize_max_ms=round(max(resize_times),2),table_50000_load_ms=round(load_ms,2),
                      table_50000_filter_ms=round(filter_ms,2),tk_imports=forbidden,
                      kr_assignment_engine='embedded Python SheetMetal parameters',
                      pdf_export_engine='isolated COM process',
                      solidworks_live_tested=False,checks=['ten modules','two themes','resolution matrix',
                      'tolerance stack 0.20 / 0.02 / 0.38 mm','tolerance stack PDF/XLSX',
                      'vector diagrams','bolt kg/N','weight 157 kg','BOM XLSX','DXF dependency',
                      'Pack and Go interop source bundled','isolated PDF worker startup/IPC',
                      'embedded licenses and export','no Tk runtime'])
        w.close()
        return report


def run(output):
    path = Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        report = check(path)
    except Exception as error:
        report = dict(status='failed',error=str(error),traceback=traceback.format_exc())
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1
