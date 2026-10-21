"""Exercise cached native workspaces, rapid resizing and a real settings restart.

No live CAD calls, no existing settings, no source documents are modified.
"""

import argparse
import gc
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QCoreApplication,QEvent,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from gui_qt.app import create_application,MainWindow
from modules.nesting.storage import load_project


def validate(destination,cycles=10):
    app=create_application([]);destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    heartbeats=[];last=[time.perf_counter()]
    timer=QTimer();timer.setInterval(5)
    def heartbeat():
        now=time.perf_counter();heartbeats.append((now-last[0])*1000);last[0]=now
    with TemporaryDirectory(prefix='GOKWORKS-stability-') as folder:
        settings=Path(folder)/'settings.json';w=MainWindow(settings);w.show()
        identities=dict(w.pages)
        weight=w.pages['weight']
        for key,value in dict(b='125',t='4',length='1750',count='2').items():weight.form.set_value(key,value)
        weight.update_result();assert abs(weight.result.total_mass_kg-13.7375)<1e-10
        torque=w.pages['bolt_torque'];torque.form.set_value('k','0,18');torque.update_result()
        expected_torque=torque.result
        kr=w.pages['k_factor']
        for column,value in enumerate(('2','0,274','1,5')):kr.rows_model.setData(kr.rows_model.index(0,column),value)
        expected_assignment=kr.recipe()
        stack=w.pages['tolerance_stack'];stack.load_example();expected_chain=list(stack.project.terms)
        nesting=w.pages['nesting'];nesting.project,result=load_project(ROOT/'docs/nesting-example/Ornek.goknest.json')
        nesting.sync_forms();nesting.refresh();nesting.show_result(result)
        expected_placement=nesting.result;expected_plate=nesting.selected_sheet_key()
        sizes=((820,560),(1024,700),(1440,900))
        # Include both sidebar states and all lazy scroll/tab controls before
        # counting widgets. Render caches are not evidence of a widget leak.
        for compact in (False,True):
            w.set_sidebar_collapsed(compact)
            for size in sizes:
                w.resize(*size)
                for mode in w.pages:w.navigate(mode);app.processEvents()
        w.set_theme('light');w.set_theme('dark');QTest.qWait(100)
        gc.collect();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        before=len(QApplication.allWidgets());navigation=[];resizing=[];theme_changes=[]
        last[0]=time.perf_counter();timer.timeout.connect(heartbeat);timer.start()
        for cycle in range(cycles):
            appearance='light' if cycle%2==0 else 'dark'
            start=time.perf_counter();w.set_theme(appearance);app.processEvents()
            theme_changes.append((time.perf_counter()-start)*1000)
            w.set_sidebar_collapsed(cycle%3==1)
            for width,height in sizes:
                for index,mode in enumerate(w.pages):
                    start=time.perf_counter();w.resize(width+index%3*9,height+index%2*8);app.processEvents()
                    resizing.append((time.perf_counter()-start)*1000)
                    start=time.perf_counter();w.navigate(mode);app.processEvents()
                    navigation.append((time.perf_counter()-start)*1000)
                    assert w.stack.currentWidget() is identities[mode]
                    assert w.stack.geometry().right()<w.width()
                    assert not w.jobs.busy
                    time.sleep(.001)
        QTest.qWait(100);timer.stop()
        gc.collect();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
        after=len(QApplication.allWidgets())
        assert after<=before+8,(before,after)
        assert w.pages==identities and weight.form.value('length')=='1750'
        assert abs(weight.result.total_mass_kg-13.7375)<1e-10
        assert torque.result==expected_torque and kr.recipe()==expected_assignment
        assert stack.project.terms==expected_chain
        assert nesting.result is expected_placement and nesting.selected_sheet_key()==expected_plate
        assert not kr.save_files.isChecked() and w.settings.flush()
        w.navigate('weight');w.close();w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
        restored=MainWindow(settings);restored.show();QTest.qWait(100)
        assert restored.mode=='weight'
        assert abs(restored.pages['weight'].result.total_mass_kg-13.7375)<1e-10
        assert restored.pages['bolt_torque'].result==expected_torque
        assert restored.pages['k_factor'].recipe()==expected_assignment
        assert not restored.pages['k_factor'].save_files.isChecked()
        restored.close();restored.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        report=dict(status='passed',platform=app.platformName(),cycles=cycles,
            navigation_count=len(navigation),resize_count=len(resizing),themes=['dark','light'],sizes=sizes,
            sidebar_states=['labels','icons'],widgets_before=before,widgets_after=after,
            navigation_median_ms=round(statistics.median(navigation),2),navigation_max_ms=round(max(navigation),2),
            resize_median_ms=round(statistics.median(resizing),2),resize_max_ms=round(max(resizing),2),
            theme_change_count=len(theme_changes),theme_change_median_ms=round(statistics.median(theme_changes),2),
            theme_change_max_ms=round(max(theme_changes),2),
            heartbeat_samples=len(heartbeats),heartbeat_max_interval_ms=round(max(heartbeats),2),
            settings_restart='passed',input_and_result_preservation='passed',cad_calls_made=False,
            native_windows_tested=False,performance_note='Source/offscreen Linux; concurrent test load, not a Windows timing guarantee.')
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--cycles',type=int,default=10);args=parser.parse_args()
    if not 1<=args.cycles<=100:parser.error('cycles must be between 1 and 100')
    validate(args.destination,args.cycles)
