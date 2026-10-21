"""Capture the revised real Qt workflow with the manual example; no CAD connection."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PySide6.QtCore import QEventLoop,QTimer
from gui_qt.app import MainWindow,create_application
from modules.tolerance_stack.calculator import calculate


def capture(destination):
    destination.mkdir(parents=True,exist_ok=True)
    app=create_application([])

    def settle():
        # Exercise the actual coalesced resize/redraw timers before taking evidence.
        loop=QEventLoop();QTimer.singleShot(80,loop.quit);loop.exec()

    with TemporaryDirectory() as folder:
        window=MainWindow(Path(folder)/'settings.json');window.resize(1440,950);window.show()
        window.navigate('tolerance_stack');page=window.pages['tolerance_stack'];page.load_example()
        page.chain_table.selectRow(0)
        def shot(name):
            settle();assert window.grab().save(str(destination/(name+'.png')))
        shot('chain-dark')
        window.set_theme('light');shot('chain-light')
        window.set_theme('dark')
        page.project.dimensions[1]=replace(page.project.dimensions[1],lower=None);page.refresh()
        shot('missing-tolerance')
        window.resize(1024,700);shot('missing-tolerance-compact')
        page.project.dimensions[1]=replace(page.project.dimensions[1],lower=page.project.dimensions[1].upper*-1)
        page.refresh();window.resize(1440,950);page.confirm_box.setChecked(True)
        result=calculate(page.project);page.show_result(result);shot('results-dark')
        assert tuple(map(str,(result.nominal,result.minimum,result.maximum)))==('0.20','0.02','0.38')
        (destination/'validation.json').write_text(json.dumps(dict(
            example='Manual A-B-C, 50 - 20 - 29.80',qt_platform=app.platformName(),
            expected=['0.20','0.02','0.38'],actual=list(map(str,(result.nominal,result.minimum,result.maximum))),
            screenshots=5,solidworks_live_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        window.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    capture(parser.parse_args().destination)
