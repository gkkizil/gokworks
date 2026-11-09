from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from shapely.geometry import box

from gui_qt.app import MainWindow, create_application, MODULES
from gui_qt.workspace import WORKSPACES
from modules.nesting.models import Part
from modules.nesting.storage import load_project, save_project
from modules.nesting.dxf_import import read_dxf
from modules.smart_splitting.adapter import transfer_to_nesting
from modules.smart_splitting.models import SplitSettings
from modules.smart_splitting.splitter import split
from .test_geometry import circle_dxf


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]); w=MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1366,900); w.show(); w.navigate('smart_splitting')
    yield w
    if w.jobs.busy: w.jobs.cancel(); qtbot.waitUntil(lambda:not w.jobs.busy,timeout=15000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def finish(window,qtbot):
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=30000)


def test_navigation_is_directly_after_nesting_and_does_not_reset_page(window,qtbot,tmp_path):
    order=[key for key,_,_ in MODULES]; actual=list(window.browser.buttons)
    assert order[order.index('nesting')+1]=='smart_splitting'
    assert actual[actual.index('nesting')+1]=='smart_splitting'
    assert [k for _,keys in WORKSPACES for k in keys]==actual
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'source.dxf'))
    finish(window,qtbot); page.form.set_value('count','4'); page.run_split(); finish(window,qtbot)
    solution=page.solution; assert solution
    window.navigate('nesting'); window.navigate('smart_splitting')
    assert page.solution is solution and page.source is not None
    page.form.set_value('count','5'); assert page.solution is None and not page.export_button.isEnabled()


def test_required_full_d1800_bolt_holes_six_segments_export_transfer_and_nest(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; path=circle_dxf(tmp_path/'D1800.dxf',radius=900,bolts=True)
    source_bytes=path.read_bytes(); page.form.set_value('tolerance','.2')
    page.load_file(path); finish(window,qtbot)
    assert page.source is not None
    for key,value in dict(count=6,sheet_width=1500,sheet_height=3000,quantity=1,hole_clearance=5,profile='Hızlı').items():
        page.form.set_value(key,value)
    nesting=window.pages['nesting']; existing=Part.create('MEVCUT',box(0,0,20,10)); nesting.project.parts=[existing]; nesting.refresh()
    before_imports=deepcopy(nesting.imports); before_stock=deepcopy(nesting.project.sheets)
    page.run_split(optimize=True)
    # A real job remains navigable while geometry/NFP work runs.
    window.navigate('nesting'); window.navigate('smart_splitting')
    finish(window,qtbot)
    assert page.solution is not None,page.status_text
    assert page.optimization and len(page.optimization.solution.segments)==6
    assert page.candidate_table.rowCount()>=2
    output=tmp_path/'segments'; page.export_to(output); finish(window,qtbot)
    files=list(output.glob('*_SEG_*.dxf')); assert len(files)==6
    assert all(len(read_dxf(p,tolerance=.2))==1 for p in files)
    page.transfer(); assert window.mode=='nesting'
    assert existing.id in {p.id for p in nesting.project.parts}
    assert len(nesting.project.parts)==7 and sum(p.quantity for p in nesting.project.parts)==7
    assert nesting.imports==before_imports
    assert all(s in nesting.project.sheets for s in before_stock)
    assert any((s.width,s.height)==(1500,3000) for s in nesting.project.sheets)
    nesting.project.options.quality='Hızlı'; nesting.project.options.seconds=3
    nesting.start_nest(); finish(window,qtbot)
    assert nesting.result is not None and not nesting.result.unplaced
    assert len(nesting.result.placements)==7
    assert path.read_bytes()==source_bytes


def test_bidirectional_transfer_quantity_ids_and_existing_project_are_preserved(window,qtbot,tmp_path):
    nesting=window.pages['nesting']; source=Part.create('ORIGINAL',box(0,0,200,200),quantity=5)
    unrelated=Part.create('OTHER',box(0,0,10,10)); nesting.project.parts=[source,unrelated]; nesting.refresh()
    nesting.select_canvas_part(source.id)
    page=window.pages['smart_splitting']; page.from_nesting()
    assert page.source.id==source.id and page.form.value('quantity')=='5'
    page.form.set_value('count',6); page.run_split(); finish(window,qtbot)
    assert page.solution is not None
    ids={s.id for s in page.solution.segments}; page.transfer()
    assert ids<=set(p.id for p in nesting.project.parts)
    assert sum(p.quantity for p in nesting.project.parts if p.id in ids)==30
    page.transfer(); assert len(nesting.project.parts)==8  # Repeated transfer replaces only its own set.
    saved=tmp_path/'nest.goknest.json'; save_project(nesting.project,saved,imports=nesting.imports)
    nesting.project,_,nesting.imports=load_project(saved,with_imports=True)
    nesting._split_transfers={}
    solution=split(page.source,SplitSettings(count=4,quantity=5))
    transfer_to_nesting(nesting,solution)
    assert len(nesting.project.parts)==6 and {source.id,unrelated.id}<=set(p.id for p in nesting.project.parts)


def test_invalid_inputs_and_reset_do_not_mutate_nesting(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; nesting=window.pages['nesting']; before=nesting.project.fingerprint()
    page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    page.form.set_value('count','nan'); page.run_split()
    assert page.solution is None and not window.jobs.busy and page.status.property('role')=='error'
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot); assert page.solution
    page.clear(); assert page.source is None and page.solution is None
    assert nesting.project.fingerprint()==before


def test_both_themes_and_compact_workbench_keep_actions_visible(window,qtbot,tmp_path):
    page=window.pages['smart_splitting']; page.load_file(circle_dxf(tmp_path/'A.dxf',radius=100)); finish(window,qtbot)
    page.form.set_value('count',4); page.run_split(); finish(window,qtbot)
    for theme in ('dark','light'):
        window.set_theme(theme)
        for size in ((1366,900),(1024,700)):
            window.resize(*size); qtbot.wait(40)
            assert page.canvas.viewport().height()>=100
            assert page.transfer_button.isVisible() and page.export_button.isVisible()
            # QLayout.geometry() may be temporarily empty on native Windows;
            # verify the actual rendered widget bounds in the page coordinates.
            for action in (page.split_button,page.optimize_button,page.transfer_button,page.export_button):
                assert page.rect().contains(action.mapTo(page,action.rect().topLeft()))
                assert page.rect().contains(action.mapTo(page,action.rect().bottomRight()))
            assert not window.grab().isNull()
