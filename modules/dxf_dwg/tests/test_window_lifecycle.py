"""Production startup in a fresh process; no CAD session or mocked renderer."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]
PROBE=r'''
import json,sys
from PySide6.QtCore import Qt,QObject,QEvent,QCoreApplication
from PySide6.QtTest import QTest
from gui_qt.app import create_application,MainWindow
app=create_application([])
assert app.testAttribute(Qt.AA_ShareOpenGLContexts)
window=MainWindow(sys.argv[1]);window.show();QTest.qWait(150)
before=int(window.winId());events=[]
class Observer(QObject):
    def eventFilter(self,obj,event):
        if obj is window and event.type() in (QEvent.Close,QEvent.WinIdChange):events.append(event.type().name)
        return False
observer=Observer();window.installEventFilter(observer)
handles=[]
for mode in ('dxf_dwg','pdf','dxf_dwg','weight','dxf_dwg'):
    window.navigate(mode);QTest.qWait(220)
    handles.append(int(window.winId()))
    assert window.isVisible() and not window.closing
native=app.platformName()=='windows'
if native:
    assert handles==[before]*len(handles),(before,handles,events)
    assert not events,events
print(json.dumps(dict(platform=app.platformName(),before=before,handles=handles,events=events,shared=True)))
window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
'''


def run_probe(tmp_path):
    result=subprocess.run([sys.executable,'-X','faulthandler','-c',PROBE,str(tmp_path/'settings.json')],
                          cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_fresh_application_configures_shared_contexts_before_lazy_preview(tmp_path):
    assert run_probe(tmp_path)['shared']


@pytest.mark.skipif(os.name!='nt',reason='Actual Windows HWND lifecycle requires a native Windows desktop.')
def test_native_windows_navigation_preserves_the_main_window_handle(tmp_path):
    result=run_probe(tmp_path)
    assert result['platform']=='windows' and not result['events']
    assert result['handles']==[result['before']]*5
