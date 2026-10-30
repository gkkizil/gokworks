"""Reproducible local performance probes; no CAD automation or new dependencies.

Run this script against two checkouts, alternating fresh processes. JSON and
optional cProfile/tracemalloc evidence belong outside the source tree. A fresh
process is NOT an OS-cold disk-cache measurement. GUI timing uses the selected
Qt platform; offscreen results must not be presented as native Windows timing.
"""
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time


def resources():
    """Current resident bytes and cumulative process I/O, without psutil."""
    if sys.platform.startswith('linux'):
        status = Path('/proc/self/status').read_text()
        rss = next(int(line.split()[1])*1024 for line in status.splitlines() if line.startswith('VmRSS:'))
        io = dict(line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())
        return dict(rss=rss,read_calls=int(io['syscr']),write_calls=int(io['syscw']),
                    read_bytes=int(io['read_bytes']),write_bytes=int(io['write_bytes']))
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes as w
        class Memory(ctypes.Structure):
            _fields_ = [('cb',w.DWORD),('faults',w.DWORD)]+[(n,ctypes.c_size_t) for n in (
                'peak','working','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile','private')]
        class IO(ctypes.Structure):
            _fields_ = [(n,ctypes.c_ulonglong) for n in ('reads','writes','other','read_bytes','write_bytes','other_bytes')]
        kernel = ctypes.WinDLL('kernel32',use_last_error=True);psapi = ctypes.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.restype = w.HANDLE;handle = kernel.GetCurrentProcess()
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE,ctypes.POINTER(Memory),w.DWORD]
        kernel.GetProcessIoCounters.argtypes = [w.HANDLE,ctypes.POINTER(IO)]
        mem=Memory();mem.cb=ctypes.sizeof(mem);io=IO()
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(mem),mem.cb) or not kernel.GetProcessIoCounters(handle,ctypes.byref(io)):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(rss=mem.working,read_calls=io.reads,write_calls=io.writes,read_bytes=io.read_bytes,write_bytes=io.write_bytes)
    return dict(rss=None)


def fixed_project():
    from modules.nesting.models import Project,Material,Part,Sheet,Placement,Result
    from shapely.geometry import mapping,box
    project=Project(materials=[Material('steel','Steel',7850)],
        sheets=[Sheet('sheet','Sheet',width=2000,height=2000,price_kg=35,material='steel')])
    project.options.margin=2;project.options.gap=2
    geometry=mapping(box(0,0,10,10))
    project.parts=[Part(str(i),str(i),geometry,'steel',2,quantity=4) for i in range(200)]
    placements=[Placement(part.id,k+1,'sheet',1,10+(n%40)*20,10+(n//40)*20,0)
        for n,(part,k) in enumerate((part,k) for part in project.parts for k in range(4))]
    result=Result(project.fingerprint(),placements,[],'benchmark','1',0,1,'2026-10-30T00:00:00+00:00')
    return project,result


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def startup(root, folder):
    start=time.perf_counter();cpu=time.process_time();before=resources()
    from solidworks.runtime import configure_libraries
    configure_libraries()
    from gui_qt.app import create_application,MainWindow,MODULES
    from PySide6.QtCore import QTimer,QEventLoop,QEvent,QCoreApplication
    from PySide6.QtWidgets import QWidget
    imported=time.perf_counter();app=create_application([])
    window=MainWindow(folder/'settings.json');constructed=time.perf_counter();window.show();app.processEvents()
    loop=QEventLoop();QTimer.singleShot(0,loop.quit);loop.exec()
    ready=time.perf_counter();after=resources()
    data=dict(import_s=imported-start,construction_s=constructed-imported,ready_s=ready-start,
        cpu_s=time.process_time()-cpu,resources=after,io_delta={k:after[k]-before[k] for k in after if k!='rss'},
        widgets=len(window.findChildren(QWidget)),
        imported_pages=[k for k,_,_ in MODULES if 'modules.'+k+'.ui' in sys.modules])
    if os.environ.get('GOKWORKS_PERF_TRACE'):
        import tracemalloc
        data['python_heap_ready']=tracemalloc.get_traced_memory()
    cpu=time.process_time();started=time.perf_counter()
    loop=QEventLoop();QTimer.singleShot(1000,loop.quit);loop.exec()
    data['idle_cpu_percent']=100*(time.process_time()-cpu)/(time.perf_counter()-started)
    first={}
    for key,_,_ in MODULES:
        started=time.perf_counter();window.navigate(key);app.processEvents();first[key]=time.perf_counter()-started
    data['first_navigation_s']=first;data['resources_all_modules']=resources()
    import gc
    gc.collect();data['rss_before_cycles']=resources()['rss'];warm=[]
    for _ in range(5):
        for key,_,_ in MODULES:
            started=time.perf_counter();window.navigate(key);app.processEvents();warm.append(time.perf_counter()-started)
    gc.collect();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    data['warm_navigation_median_s']=statistics.median(warm);data['warm_navigation_max_s']=max(warm)
    data['rss_after_cycles']=resources()['rss']
    if os.environ.get('GOKWORKS_PERF_TRACE'):
        data['python_heap_after_cycles']=tracemalloc.get_traced_memory()
    # Real JobManager/Qt queued delivery with a cooperative long task.
    import threading
    page=window.pages['pdf'];ticks=[];timer=QTimer();timer.setInterval(10)
    timer.timeout.connect(lambda:ticks.append(time.perf_counter()));timer.start()
    entered=threading.Event()
    def operation(sink,stop): entered.set();stop.wait(5)
    window.jobs.start(page,operation)
    QTimer.singleShot(80,lambda:window.navigate('weight'))
    QTimer.singleShot(250,window.jobs.cancel)
    loop=QEventLoop();guard=QTimer();guard.setSingleShot(True);guard.setInterval(5000)
    guard.timeout.connect(loop.quit);window.jobs.finished.connect(loop.quit);guard.start();loop.exec();timer.stop()
    assert entered.is_set() and not window.jobs.busy and len(ticks)>3
    data['heartbeat_max_gap_s']=max((b-a for a,b in zip(ticks,ticks[1:])),default=0)
    window.close();app.processEvents()
    return data


def accounting(root, folder):
    from modules.nesting.accounting import calculate
    project,result=fixed_project();before=resources();start=time.perf_counter();cpu=time.process_time()
    totals=calculate(project,result)
    return dict(elapsed_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
                resources=resources(),rss_before=before['rss'],result_sha256=digest(totals),parts=totals['part_count'])


def dxf(root, folder):
    import ezdxf
    from modules.nesting.dxf_import import read_dxf
    from dataclasses import asdict
    source=folder/'large.dxf';doc=ezdxf.new();doc.units=4
    for i in range(150):
        x=(i%15)*40;y=(i//15)*30
        doc.modelspace().add_lwpolyline([(x,y),(x+30,y),(x+30,y+20),(x,y+20)],close=True)
    doc.saveas(source);before=source.read_bytes();start=time.perf_counter();cpu=time.process_time()
    parts=read_dxf(source);elapsed=time.perf_counter()-start
    assert source.read_bytes()==before
    # Ignore unique part IDs, source path and generated DXF timestamps/handles.
    signature=[dict(code=p.code,geometry=p.geometry,area=p.area,quantity=p.quantity,thickness=p.thickness,
                    unit=p.source_unit,tolerance=p.curve_tolerance,endpoint_error=p.endpoint_error) for p in parts]
    data=dict(elapsed_s=elapsed,cpu_s=time.process_time()-cpu,resources=resources(),
              parts=len(parts),result_sha256=digest(signature),source_unchanged=True)
    # Also exercise the real UI/JobManager import path while its event loop ticks.
    from gui_qt.app import create_application,MainWindow
    from PySide6.QtCore import QTimer,QEventLoop
    app=create_application([]);window=MainWindow(folder/'settings.json');window.show()
    window.navigate('nesting');page=window.pages['nesting'];app.processEvents()
    ticks=[time.perf_counter()];timer=QTimer();timer.setInterval(10)
    timer.timeout.connect(lambda:ticks.append(time.perf_counter()));timer.start()
    started=time.perf_counter();page.import_files([source]);loop=QEventLoop()
    guard=QTimer();guard.setSingleShot(True);guard.setInterval(30000)
    guard.timeout.connect(loop.quit);window.jobs.finished.connect(loop.quit);guard.start();loop.exec();timer.stop()
    assert not window.jobs.busy and page.imports[0]['status']=='review' and len(ticks)>3
    ticks.append(time.perf_counter());data['ui_import_s']=ticks[-1]-started
    data['ui_heartbeat_max_gap_s']=max(b-a for a,b in zip(ticks,ticks[1:]))
    assert source.read_bytes()==before
    window.close();app.processEvents()
    return data


def worker(args):
    root=Path(args.root).resolve();sys.path.insert(0,str(root))
    if args.trace:
        import tracemalloc
        tracemalloc.start();os.environ['GOKWORKS_PERF_TRACE']='1'
    profile=cProfile.Profile() if args.profile else None
    with tempfile.TemporaryDirectory(prefix='gokworks-performance-') as name:
        if profile: profile.enable()
        result=globals()[args.worker](root,Path(name))
        if profile: profile.disable();profile.dump_stats(args.profile)
    if args.trace: result['python_heap_final']=tracemalloc.get_traced_memory()
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--baseline');parser.add_argument('--output',required=True)
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--scenarios',nargs='+',choices=('startup','accounting','dxf'),default=['startup','accounting','dxf'])
    parser.add_argument('--worker',choices=('startup','accounting','dxf'))
    parser.add_argument('--profile');parser.add_argument('--trace',action='store_true')
    args=parser.parse_args()
    if args.worker: return worker(args)
    if not 1<=args.repeat<=20: parser.error('--repeat must be 1–20')
    roots={'current':str(Path(args.root).resolve())}
    if args.baseline: roots={'baseline':str(Path(args.baseline).resolve()),**roots}
    results={label:{scenario:[] for scenario in args.scenarios} for label in roots}
    with tempfile.TemporaryDirectory(prefix='gokworks-benchmark-') as name:
        for scenario in args.scenarios:
            for iteration in range(args.repeat):
                for label,root in roots.items():
                    destination=Path(name)/'result.json'
                    command=[sys.executable,str(Path(__file__).resolve()),'--root',root,'--worker',scenario,'--output',str(destination)]
                    subprocess.run(command,cwd=root,check=True,timeout=180)
                    data=json.loads(destination.read_text());results[label][scenario].append(data)
                    print(f'{label} {scenario} {iteration+1}: {data.get("ready_s",data.get("elapsed_s")):.4f}s',flush=True)
    import platform
    Path(args.output).write_text(json.dumps(dict(schema=1,platform=platform.platform(),python=sys.version,
        qt_platform=os.environ.get('QT_QPA_PLATFORM','native default'),
        note='Fresh processes; OS disk cache not flushed. Tracemalloc/cProfile disabled in timed comparison.',
        roots=roots,results=results),indent=2),encoding='utf-8')


if __name__=='__main__': main()
