"""A fast job must keep its lock until ordered, GUI-sized delivery finishes."""
from PySide6.QtCore import QObject,QTimer,QThread
from gui_qt.workers import JobManager


def test_fast_worker_yields_and_finishes_after_all_events(qapp,qtbot):
    class Owner(QObject):
        def __init__(self):
            super().__init__();self.values=[];self.sizes=[];self.completed=[]
        def handle_events(self,values):
            assert QThread.currentThread() is qapp.thread()
            self.values.extend(values);self.sizes.append(len(values))
        def set_busy(self,busy):
            if not busy:self.completed.append(len(self.values))
        def set_status(self,*args,**kwargs):pass
        def job_finished(self):self.completed.append(len(self.values))
    owner=Owner();manager=JobManager();beats=[]
    pulse=QTimer();pulse.setInterval(1);pulse.timeout.connect(lambda:beats.append(len(owner.values)));pulse.start()
    def operation(sink,stop):
        for i in range(500):sink.put(('result',i))
    manager.start(owner,operation)
    qtbot.waitUntil(lambda:not manager.busy,timeout=8000);pulse.stop()
    assert owner.values==[('result',i) for i in range(500)]
    assert max(owner.sizes)<=8 and owner.completed==[500,500]
    assert len([n for n in beats if 0<n<500])>=2
