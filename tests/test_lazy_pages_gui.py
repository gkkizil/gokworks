"""Persistent on-demand workbenches retain API, themes and CAD job lifecycles."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading

import pytest
from PySide6.QtCore import QCoreApplication,QEvent

from gui_qt.app import MainWindow,create_application,MODULES,PAGE_TYPES
from gui_qt.pages import PageRegistry

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.show();yield w
    if w.jobs.busy: w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_startup_and_closing_only_construct_the_restored_module_in_a_fresh_process(tmp_path):
    script='''
import sys,json
from pathlib import Path
from gui_qt.app import create_application,MainWindow
app=create_application([]);w=MainWindow(Path(sys.argv[1]));w.show();app.processEvents()
assert len(w.pages)==16 and list(w.pages)==list(w.pages.keys())
assert w.mode=='pdf' and w.stack.count()==1
assert [k for k in sys.modules if k.startswith('modules.') and k.endswith('.ui')]==['modules.pdf.ui']
assert not any(k in sys.modules for k in ('ezdxf','numpy','shapely','OCP','pythoncom'))
assert not w.jobs.busy
w.set_theme('light');assert w.stack.count()==1
w.close();app.processEvents();assert w.stack.count()==1
'''
    subprocess.run([sys.executable,'-c',script,str(tmp_path/'settings.json')],cwd=ROOT,
                   env={**os.environ,'QT_QPA_PLATFORM':os.environ.get('QT_QPA_PLATFORM','offscreen')},check=True,timeout=30)


def test_mapping_membership_and_iteration_do_not_construct_but_explicit_values_keep_compatibility():
    calls=[]
    registry=PageRegistry({'a':1,'b':2},lambda key,factory:(calls.append(key),object())[1])
    assert len(registry)==2 and list(registry)==['a','b'] and 'a' in registry and 'missing' not in registry
    assert registry.peek('a') is None and not registry.loaded_values() and not calls
    a=registry['a'];assert registry['a'] is a and calls==['a']
    assert dict(registry)=={'a':a,'b':registry['b']} and calls==['a','b']
    with pytest.raises(KeyError): registry['missing']


def test_failed_factory_is_not_cached_or_allowed_to_corrupt_other_modules():
    attempts=[]
    def create(key,value):
        attempts.append(key)
        if key=='bad': raise ValueError('fixture')
        return value
    registry=PageRegistry({'bad':1,'good':2},create)
    for _ in range(2):
        with pytest.raises(ValueError): registry['bad']
    assert registry['good']==2 and registry.peek('bad') is None and attempts==['bad','bad','good']


def test_restored_heavy_module_is_ready_without_constructing_others(qtbot,tmp_path):
    path=tmp_path/'restore.json';path.write_text(json.dumps(dict(mode='nesting',appearance='light',extra='retained')))
    create_application([]);w=MainWindow(path);qtbot.addWidget(w);w.show()
    assert w.mode=='nesting' and w.stack.count()==1 and w.pages.peek('pdf') is None
    assert w.pages['nesting'].canvas.theme=='light'
    assert w.settings.get('extra')=='retained' and w.property_dock.widget() is w.inspector_stack
    w.close()


def test_page_created_after_theme_change_keeps_parameters_and_widget_identity(window,qtbot):
    w=window;w.set_theme('light');w.navigate('weight')
    p=w.pages['weight'];p.form.set_value('length','2350')
    w.navigate('pdf');w.set_theme('dark');w.navigate('weight')
    assert w.pages['weight'] is p and p.form.value('length')=='2350' and w.stack.count()==2
    w.navigate('nesting');assert w.pages['nesting'].canvas.theme=='dark'
    assert w.pages['nesting'].inspector is w.inspectors['nesting']


def test_new_inspector_respects_existing_background_job_without_changing_owner(window,qtbot):
    w=window;owner=w.pages['pdf'];waiting=threading.Event()
    def operation(sink,stop):
        waiting.set();stop.wait(3);sink.put(('log','finished'))
    assert w.jobs.start(owner,operation);qtbot.waitUntil(waiting.is_set)
    w.navigate('nesting');p=w.pages['nesting']
    assert w.jobs.owner is owner and not p.inspector.isEnabled()
    assert not p.can_start() and w.stack.count()==2
    w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy)
    assert p.inspector.isEnabled() and w.jobs.owner is None


def test_pyinstaller_hook_collects_the_complete_lazy_catalog_without_importing_qt():
    hook=runpy.run_path(str(ROOT/'packaging/hooks/hook-gui_qt.app.py'))
    assert set(hook['hiddenimports'])=={f'modules.{key}.ui' for key,_,_ in MODULES}
    assert set(PAGE_TYPES)=={key for key,_,_ in MODULES}
