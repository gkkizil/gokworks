"""Qt receiver/emitter teardown is independent of a running SolidWorks session."""
import os
from pathlib import Path
import subprocess
import sys
import threading

from PySide6.QtGui import QImage
import shiboken6

from modules.dxf_dwg.preview import viewer


def test_render_finishing_after_qt_emitter_teardown_is_safe(qapp,monkeypatch):
    monkeypatch.setattr(viewer,'raster',lambda *args:QImage())
    job=viewer.RenderJob(1,None,(1,1),(),threading.Event())
    shiboken6.delete(job.signals)
    job.run()  # shutdown must not throw "Signal source has been deleted"


def test_cancelled_render_still_releases_the_live_views_running_slot(qapp,monkeypatch):
    monkeypatch.setattr(viewer,'raster',lambda *args:None)
    stop=threading.Event();stop.set();job=viewer.RenderJob(1,None,(1,1),(),stop)
    done=[];job.signals.done.connect(lambda generation,result:done.append((generation,result)))
    job.run()
    assert done==[(1,None)]


def test_destroying_view_cancels_native_render_before_its_pool_is_destroyed(tmp_path):
    root=Path(__file__).resolve().parents[3]
    script=r'''
import threading,time
from PySide6.QtCore import QCoreApplication,QEvent
from gui_qt.app import create_application
from modules.dxf_dwg.preview import viewer
from modules.dxf_dwg.tests.test_preview_geometry import ring_mesh
app=create_application([]);entered=threading.Event();observed=[]
def raster(mesh,width,height,state,stop,*args):
    entered.set();observed.append(stop.wait(2));return None
viewer.raster=raster
view=viewer.MeshView();view.resize(400,250);view.show();view.fallback();view.set_mesh(ring_mesh())
deadline=time.monotonic()+5
while not entered.is_set() and time.monotonic()<deadline:
    app.processEvents();time.sleep(.005)
assert entered.is_set()
view.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
assert observed==[True],observed
print('DESTROYED_RENDER_CANCELLED')
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=root,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert 'DESTROYED_RENDER_CANCELLED' in result.stdout
