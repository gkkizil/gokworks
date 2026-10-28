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
                    if mode=='gear_calculator' and not w.pages[mode].compact_mode:
                        gear_page=w.pages[mode]
                        assert all(panel.isVisible() for panel in
                            (gear_page.input_scroll,gear_page.viewer_panel,gear_page.results_scroll))
        bolt = w.pages['bolt']
        bolt.form.set_value('unit','kg')
        bolt.form.set_value('mode','Çekme')
        bolt.form.set_value('tension','100')
        bolt.update_result()
        assert abs(bolt.result.tension_n-980.665) < .000001
        torque = w.pages['bolt_torque']
        assert abs(torque.result.torque_nm - 51.958678824053294) < 1e-8
        assert abs(torque.result.preload_kn - 25.979339412026646) < 1e-8
        assert torque.section_diagram.vector.tagged['section_torque'][0].toPlainText() == 'T ≈ 51,96 N·m'
        assert torque.section_diagram.vector.tagged['bolt_shank']
        torque.form.set_value('condition', 'Hafif yağlı')
        torque.update_result()
        assert torque.result.k == .15
        assert abs(torque.result.torque_nm - 38.96900911803997) < 1e-8
        assert torque.section_diagram.vector.tagged['section_torque'][0].toPlainText() == 'T ≈ 38,97 N·m'
        torque.copy_result()
        assert 'Tahmini Sıkma Torku' in QApplication.clipboard().text()
        weight = w.pages['weight']
        weight.form.set_value('kind','Sac levha')
        for key, value in [('b','2000'),('t','10'),('length','1000')]:
            weight.form.set_value(key,value)
        weight.update_result()
        assert weight.result.total_mass_kg == 157
        assert w.pages['iso_fits'].result is not None
        assert w.pages['geometric_tolerances'].result is not None
        # Exercise the real worker command in source and frozen distributions.
        # This is local OCCT, not a mocked SOLIDWORKS or an STL-to-STEP conversion.
        from modules.gear_calculator.service import execute as gear_execute
        gears = w.pages['gear_calculator']
        assert abs(gears.result.ratio-2)<1e-10
        gear_step = gear_execute(gears.specification,'step',path=Path(folder)/'gear-pair.step')
        gear_dxf = gear_execute(gears.specification,'dxf',path=Path(folder)/'gear-pair.dxf')
        assert gear_step['solids']==2 and gear_step['volume_mm3']>0
        assert gear_dxf['gears']==2
        # Exercise the actual frozen mechanism UI imports and worker schema,
        # including the separate smooth helical loft path.
        from modules.gear_calculator.families.models import CATALOG
        for kind,capability in CATALOG.items():
            gears.type_picker.setCurrentIndex(gears.type_picker.findData(kind))
            assert gears.family_panel.result is not None,kind
            assert gears.family_panel.step_button.isEnabled()==capability.geometry,kind
        gears.type_picker.setCurrentIndex(gears.type_picker.findData('chain_sprocket'))
        chain_spec=gears.family_panel.spec
        chain_step=gear_execute(chain_spec,'step',path=Path(folder)/'chain-sprocket-pair.step')
        chain_dxf=gear_execute(chain_spec,'dxf',target='pinion',path=Path(folder)/'chain-sprocket.dxf')
        assert chain_step['solids']==2 and chain_step['volume_mm3']>0
        assert chain_dxf['contours']==1 and not chain_step['chain_included']
        gears.type_picker.setCurrentIndex(gears.type_picker.findData('rack'))
        family_rack=gear_execute(gears.family_panel.spec,'step',path=Path(folder)/'rack-pair.step')
        assert family_rack['solids']==2
        gears.type_picker.setCurrentIndex(gears.type_picker.findData('helical'))
        family_helical=gear_execute(gears.family_panel.spec,'step',path=Path(folder)/'helical-pair.step')
        assert family_helical['solids']==2 and family_helical['volume_mm3']>0
        gears.type_picker.setCurrentIndex(0)
        selected_cad = os.environ.get('GOKWORKS_CAD_DIR')
        external_cad = bool(selected_cad and Path(gear_step['kernel_module_path']).resolve().is_relative_to(Path(selected_cad).resolve()))
        if selected_cad:
            assert external_cad, 'OCP/OCCT değiştirme yolu kullanılmadı.'
        from modules.cad_converter.formats import FORMATS
        from modules.cad_converter.models import Source
        cad = w.pages['cad_converter']
        cad.form.set_value('output', str(Path(folder)/'CAD-export'))
        cad.handle_events([('cad_sources', [Source(str(Path(folder)/'Sample.SLDPRT'))])])
        cad.format_checks['xt'].setChecked(True)
        assert cad.options().formats == ('step214', 'xt')
        assert len(FORMATS) == 8 and {f.protocol for f in FORMATS if f.protocol} == {203, 214, 242}
        assert cad.files_model.rowCount() == 1
        cad.results.clear_button.click()
        assert not cad.sources and cad.files_model.rowCount() == 0
        from modules.profile_cutting.models import Project, Demand, ScanResult, ScanRow, transfer
        from modules.profile_cutting.optimizer import optimize as profile_optimize, validate_plan
        from modules.profile_cutting.storage import save as profile_save, load as profile_load, export_report as profile_report
        profiles = w.pages['profile_cutting']
        profiles.project = Project([Demand('manual','50×30×2','S355JR','1200',2)])
        fixture_scan = ScanResult('fixture.SLDPRT','Default',[
            ScanRow('fixture','fixture.SLDPRT','Default','Cut-List-1','40×40×2','S235JR','1000',5,
                    geometry_verified=True)], scanned_parts=1, weldments=1)
        assert transfer(profiles.project,fixture_scan)['added'] == 1
        assert transfer(profiles.project,fixture_scan)['duplicate'] == 1
        profiles.refresh_demands()
        profile_plan = profile_optimize(profiles.project)
        validate_plan(profiles.project,profile_plan)
        assert len(profile_plan.bars) == 2 and sum(len(b.cuts) for b in profile_plan.bars) == 7
        profiles.handle_events([('profile_plan',profile_plan)])
        assert profiles.diagram.vector.tagged['stock']
        profile_save(profiles.project,fixture_scan,Path(folder)/'profiles.gokprofile')
        assert profile_load(Path(folder)/'profiles.gokprofile')[0] == profiles.project
        profile_report(profiles.project,fixture_scan,profile_plan,Path(folder)/'profiles.csv')
        kr = w.pages['k_factor']
        kr.tabs.setCurrentIndex(1)
        kr.helper.set_value('punch_type', 'Kaz boynu')
        kr.helper.set_value('die_type', 'Çift V kalıp')
        kr.calculate_helper()
        assert kr.helper_result.die_opening_mm == 16
        for tag, expected in (('punch_type', 'Kaz boynu'), ('die_type', 'Çift V kalıp'),
                              ('die_opening', 'V = 16 mm'), ('thickness', 't = 2 mm')):
            item = kr.tool_diagram.vector.tagged[tag][0]
            assert item.toPlainText() == expected
            assert kr.tool_diagram.sceneRect().contains(item.sceneBoundingRect())
        kr.tabs.setCurrentIndex(0)
        from modules.tolerance_stack.calculator import calculate
        from modules.tolerance_stack.report import export_excel as stack_excel, export_pdf as stack_pdf
        stack=w.pages['tolerance_stack'];stack.load_example();stack.project.confirm()
        stack_result=calculate(stack.project)
        assert tuple(map(str,(stack_result.nominal,stack_result.minimum,stack_result.maximum))) == ('0.20','0.02','0.38')
        stack.show_result(stack_result)
        stack_excel(stack.project,stack_result,Path(folder)/'ToleranceStack.xlsx')
        stack_pdf(stack.project,stack_result,Path(folder)/'ToleranceStack.pdf')
        from modules.nesting.materials import new_project
        from modules.nesting.dxf_import import read_dxf
        from modules.nesting.engine import nest
        from modules.nesting.accounting import calculate as nesting_cost, mass as nesting_mass
        from modules.nesting.dxf_export import export_dxf as nesting_dxf
        from modules.nesting.report import export_excel as nesting_excel, export_pdf as nesting_pdf
        import ezdxf
        sample = Path(folder)/'Nesting-input.dxf'
        doc = ezdxf.new(); doc.units = 4
        doc.modelspace().add_lwpolyline([(0,0),(100,0),(100,50),(0,50)],close=True)
        doc.modelspace().add_circle((25,25),5); doc.saveas(sample)
        nesting_project = new_project(); nesting_project.parts = read_dxf(sample,quantity=3)
        nesting_project.options.quality = 'Hızlı'; nesting_project.options.seconds = 2
        nesting_result = nest(nesting_project)
        assert len(nesting_result.placements) == 3 and not nesting_result.unplaced
        assert abs(nesting_mass(1250*2500,2,7850)-49.0625) < 1e-9
        nesting_totals = nesting_cost(nesting_project,nesting_result)
        assert nesting_totals['net_weight'] <= nesting_totals['gross_weight']
        nesting_dxf(nesting_project,nesting_result,Path(folder)/'Nesting-DXF')
        nesting_excel(nesting_project,nesting_result,Path(folder)/'Nesting.xlsx')
        nesting_pdf(nesting_project,nesting_result,Path(folder)/'Nesting.pdf')
        from shapely.geometry import Polygon,box
        from modules.nesting.models import Part
        hole_project=new_project()
        hole_project.sheets[0].width=110;hole_project.sheets[0].height=110;hole_project.sheets[0].stock=1
        hole_project.options.margin=4;hole_project.options.seconds=.7;hole_project.options.quality='Hızlı'
        hole_project.parts=[Part.create('Host',Polygon(box(0,0,90,90).exterior,[box(10,10,80,80).exterior])),
                            Part.create('Insert',box(0,0,25,25),quantity=4)]
        hole_result=nest(hole_project)
        assert len(hole_result.placements)==5 and not hole_result.unplaced
        assert len({p.sheet_number for p in hole_result.placements})==1
        nesting_dxf(hole_project,hole_result,Path(folder)/'Hole-nesting-DXF')
        assert (Path(folder)/'Hole-nesting-DXF/KESIM-SIRASI.csv').is_file()
        w.pages['nesting'].project = nesting_project
        w.pages['nesting'].refresh(); w.pages['nesting'].show_result(nesting_result,nesting_totals)
        assert w.pages['nesting'].workspace.count() == 2
        assert w.pages['nesting'].workspace.widget(0) is w.pages['nesting'].parts_panel
        assert w.pages['nesting'].workspace.widget(1) is w.pages['nesting'].preview_scroll
        assert w.pages['nesting'].sheet_tabs.tabText(0) == '1. plaka'
        assert w.pages['nesting'].canvas.key == (nesting_project.sheets[0].id,1)
        assert w.pages['nesting'].export_button.isEnabled()
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
        from modules.bom.exporter import Result, Part, export_excel
        result = Result('main.sldasm','Default',(Part('Parça','p.sldprt','Default',2,1.,2.),),(),0,0,False)
        xlsx = Path(folder)/'BOM.xlsx'
        export_excel(result,xlsx)
        assert xlsx.read_bytes().startswith(b'PK')
        import ezdxf
        dxf = Path(folder)/'test.dxf'
        ezdxf.new().saveas(dxf)
        assert dxf.stat().st_size > 100
        from modules.naming.native import HOST_SOURCE
        assert HOST_SOURCE.is_file(), 'Gömülü Pack and Go interop kaynağı eksik.'
        # Launch the actual bundled EXE in worker mode. An empty folder tests
        # frozen imports and IPC without touching an open SolidWorks session.
        from modules.pdf.process import export_drawings
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
                      distribution=distribution, external_qt_verified=external_qt,external_cad_verified=external_cad,pdf_exit_observer=observer,
                      python=platform.python_version(),platform=platform.platform(),qt_platform=app.platformName(),
                      dpi_scale=app.primaryScreen().devicePixelRatio(),pages=pages,themes=['dark','light'],
                      resolutions=[[1024,700],[1366,768],[1920,1080],[2560,1440]],
                      startup_ms=round(startup,2),navigation_median_ms=round(statistics.median(timings),2),
                      navigation_max_ms=round(max(timings),2),resize_median_ms=round(statistics.median(resize_times),2),
                      resize_max_ms=round(max(resize_times),2),table_50000_load_ms=round(load_ms,2),
                      table_50000_filter_ms=round(filter_ms,2),tk_imports=forbidden,
                      kr_assignment_engine='embedded Python SheetMetal parameters',
                      pdf_export_engine='isolated COM process',
                      solidworks_live_tested=False,checks=[f'{len(pages)} modules','two themes','resolution matrix',
                        '1D profile stock / quantities, grouping, duplicate-safe import, JSON and CSV / no live COM',
                        '3D CAD converter / eight formats / queue, options and clear / no live COM',
                      'NFP true-contour nesting / 49.0625 kg / DXF-XLSX-PDF',
                      'hole nesting / five parts on one plate / contour cut-order CSV',
                      'nesting shared parts-and-layout workspace / document plate tabs',
                      'live press-brake tooling profiles and dimensions',
                      'quick bolt torque / 51.96 Nm / 25.98 kN / clipboard',
                      'torque joint section / live thread and preload',
                      'tolerance stack 0.20 / 0.02 / 0.38 mm','tolerance stack PDF/XLSX',
                      'vector diagrams','bolt kg/N','weight 157 kg','BOM XLSX','DXF dependency',
                      'Pack and Go interop source bundled','isolated PDF worker startup/IPC',
                      'external involute gear pair / native OCCT STEP readback / closed DXF',
                      'mechanism catalogue capabilities / rack and helical frozen-worker STEP readback',
                      'roller-chain sprockets / separate schema / real pair STEP and single exact-arc DXF',
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
