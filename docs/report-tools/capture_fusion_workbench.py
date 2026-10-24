"""Capture the running native Qt workbench; no rendered mock-ups or live CAD claims."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gui_qt.app import MainWindow, MODULES, create_application
from modules.bom.exporter import Node, Part, Result
from modules.cad_converter.models import Source
from modules.naming.exporter import Document, Snapshot
from modules.nesting.storage import load_project
from modules.profile_cutting.models import Demand
from modules.profile_cutting.optimizer import optimize
from modules.tolerance_stack.calculator import calculate


def prepare(window, folder):
    """Illustrate CAD lists; run actual local nesting, stack and profile engines."""
    for mode in ('pdf', 'dxf_dwg'):
        page = window.pages[mode]
        page.source.setText('C:/GOKWORKS/Ornek montaj')
        page.output.setText('C:/GOKWORKS/Ciktilar')
        suffix = 'SLDDRW' if mode == 'pdf' else 'SLDPRT'
        page.results.files([f'Panel.{suffix}', f'Kapak.{suffix}'])
        page.set_status('Örnek dosya listesi · Aktarım çalıştırılmadı.')
    converter = window.pages['cad_converter']
    converter.sources = [Source('C:/GOKWORKS/Panel.SLDPRT'), Source('C:/GOKWORKS/Sase.SLDASM')]
    converter.refresh_sources()
    window.pages['bom'].load_result(Result('Ornek montaj.SLDASM', 'Varsayılan',
        (Part('Panel', 'Panel.SLDPRT', 'Varsayılan', 2, 1.5, 3),
         Part('Kapak', 'Kapak.SLDPRT', 'Varsayılan', 4, .25, 1)),
        (Node('1', '', 0, 'Örnek montaj', 'Ana', 'Montaj', 'Ornek montaj.SLDASM', 'Varsayılan'),
         Node('1.1', '1', 1, 'Panel', 'Panel-1', 'Parça', 'Panel.SLDPRT', 'Varsayılan', 1.5)),
        0, 0, False))
    source = folder / 'source'
    source.mkdir()
    files = [source / name for name in ('Montaj.SLDASM', 'Panel.SLDPRT', 'Panel.SLDDRW')]
    for file in files:
        file.write_text('Illustrative CAD boundary; not a SolidWorks document.', encoding='utf-8')
    naming = window.pages['naming']
    naming.source_folder.setText(str(source))
    naming.destination.setText(str(folder / 'Yeni paket'))
    naming.form.set_value('prefix', 'DRM-')
    naming.handle_events([('assemblies', [str(files[0])])])
    naming.load_snapshot(Snapshot(str(files[0]), tuple(
        Document(str(file), (() if index else (str(files[1]),)), (0, 0))
        for index, file in enumerate(files))))
    limit = time.monotonic() + 15
    while window.jobs.busy:
        QApplication.processEvents()
        QTest.qWait(5)
        if time.monotonic() > limit:
            raise TimeoutError('Illustrative naming preview timed out')
    assert naming.valid_plan
    kr = window.pages['k_factor']
    for column, value in enumerate(('2', '0,274', '1,5')):
        kr.rows_model.setData(kr.rows_model.index(0, column), value)
    stack = window.pages['tolerance_stack']
    stack.load_example()
    stack.confirm_box.setChecked(True)
    result = calculate(stack.project)
    assert tuple(map(str, (result.nominal, result.minimum, result.maximum))) == ('0.20', '0.02', '0.38')
    stack.show_result(result)
    stack.tabs.setCurrentIndex(0)
    nesting = window.pages['nesting']
    nesting.project, result = load_project(ROOT / 'docs/nesting-example/Ornek.goknest.json')
    nesting.sync_forms()
    nesting.refresh()
    nesting.show_result(result)
    nesting.part_table.selectRow(0)
    profile = window.pages['profile_cutting']
    profile.project.demands = [
        Demand('demo-1', '40×40×2', 'S235JR', '1200', 4),
        Demand('demo-2', '40×40×2', 'S235JR', '800', 6)]
    profile.refresh_demands()
    profile.handle_events([('profile_plan', optimize(profile.project))])
    limit = time.monotonic() + 15
    while window.jobs.busy:
        QApplication.processEvents()
        QTest.qWait(5)
        if time.monotonic() > limit:
            raise TimeoutError('Local nesting cost preview timed out')


def main(destination):
    destination.mkdir(parents=True, exist_ok=True)
    app = create_application([])
    shots = []
    with TemporaryDirectory(prefix='GOKWORKS-workbench-') as folder:
        window = MainWindow(Path(folder) / 'settings.json')
        window.resize(1440, 900)
        window.show()
        prepare(window, Path(folder))

        def shot(name, widget=None):
            QTest.qWait(90)
            target = window if widget is None else widget
            assert target.grab().save(str(destination / (name + '.png')))
            shots.append(dict(file=name + '.png', size=target.size().toTuple(), mode=window.mode))

        for theme in ('dark', 'light'):
            window.set_theme(theme)
            window.resize(1440, 900)
            for mode, _, _ in MODULES:
                window.navigate(mode)
                shot(f'{mode}-{theme}')
                assert window.size().toTuple() == (1440, 900)
            window.resize(820, 560)
            for mode, _, _ in MODULES:
                window.navigate(mode)
                shot(f'{mode}-{theme}-minimum')
                assert window.size().toTuple() == (820, 560)
        window.set_theme('dark')
        window.navigate('nesting')
        window.inspector_button.click()
        shot('nesting-floating-workspace')
        shot('nesting-floating-properties', window.property_dock)
        window.property_dock.close()
        window.resize(1440, 900)
        window.inspector_button.click()
        window.property_dock.setFloating(False)
        window.set_sidebar_collapsed(True)
        shot('collapsed-navigation')
        window.focus_module_search()
        window.browser.search.setText('tork')
        shot('module-search')
        window.browser.search.clear()
        window.navigate('k_factor')
        kr=window.pages['k_factor']
        kr.tabs.setCurrentIndex(1)
        kr.helper.set_value('punch_type','Kaz boynu')
        kr.helper.set_value('die_type','Çift V kalıp')
        kr.calculate_helper()
        shot('kr-tooling-helper')
        kr.tabs.setCurrentIndex(0)
        window.navigate('tolerance_stack')
        stack = window.pages['tolerance_stack']
        stack.tabs.setCurrentIndex(2)
        shot('stack-results')
        stack.tabs.setCurrentIndex(0)
        stack.library_button.click()
        shot('stack-measurement-picker', stack.library_dialog)
        stack.library_dialog.reject()

        def preferences():
            dialog = QApplication.activeModalWidget()
            shot('application-settings', dialog)
            dialog.reject()

        QTimer.singleShot(80, preferences)
        window.show_settings()
        window.close()
    (destination / 'capture.json').write_text(json.dumps(dict(
        platform=app.platformName(), framework='PySide6 / Qt Widgets', modules=len(MODULES),
        themes=['dark', 'light'], sizes=[[1440, 900], [820, 560]], screenshots=shots,
        example_math=['0.20', '0.02', '0.38'],
        nesting='Existing real DXF example, previously validated placements loaded locally',
        profile='Local 1D optimizer executed on explicitly manual example inputs',
        cad_boundary='BOM/PDF/DXF/converter/naming lists illustrative; no live SolidWorks or CAD conversion',
        windows_exe_built=False), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    main(parser.parse_args().destination)
