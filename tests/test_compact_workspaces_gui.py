"""Compact UI controls preserve inputs, source safety and persistent page state."""

import gc
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,Qt,QPoint,QTimer
from PySide6.QtWidgets import QWidget,QLineEdit,QVBoxLayout,QApplication,QComboBox,QCheckBox

from gui_qt.app import MainWindow,create_application,MODULES
from gui_qt.components import Disclosure


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([]);w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1440,900);w.show()
    yield w
    if w.jobs.busy:
        w.jobs.cancel();qtbot.waitUntil(lambda:not w.jobs.busy,timeout=8000)
    w.settings.flush();w.close();w.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_disclosure_keeps_values_and_announces_programmatic_state(qtbot):
    content=QWidget();body=QVBoxLayout(content);entry=QLineEdit('125,4');body.addWidget(entry)
    section=Disclosure('Teknik seçenekler',content);qtbot.addWidget(section);section.show()
    events=[];section.expandedChanged.connect(events.append)
    section.set_expanded(True);assert section.toggle.isChecked() and entry.isVisible()
    entry.setText('200');section.toggle.click()
    assert not section.is_expanded() and not entry.isVisible()
    section.toggle.click();assert entry.text()=='200' and entry.isVisible()
    assert events==[True,False,True]


@pytest.mark.parametrize('theme',('dark','light'))
def test_all_modules_keep_header_actions_inside_minimum_and_wide_windows(window,qtbot,theme):
    window.set_theme(theme)
    for size in ((820,560),(1024,700),(1440,900)):
        window.resize(*size)
        for mode,_,_ in MODULES:
            window.navigate(mode);qtbot.wait(15);page=window.pages[mode]
            assert page.isVisible() and window.stack.geometry().right()<window.width()
            for index in range(page.actions.count()):
                control=page.actions.itemAt(index).widget()
                if control.isVisible():
                    assert page.rect().contains(control.mapTo(page,control.rect().bottomRight())),(mode,size,control.text())
            assert not window.grab().isNull()


def test_sidebar_toggle_preserves_cached_pages_and_uses_labeled_icons(window,qtbot):
    original=dict(window.pages);page=window.pages['weight'];page.form.set_value('length','1500')
    window.menu_toggle.click();qtbot.wait(30)
    assert window.sidebar.width()==64
    for mode,title,_ in MODULES:
        nav=window.navigation[mode]
        assert nav.text()=='' and nav.toolTip()==title and nav.accessibleName()==title
        nav.click();assert window.stack.currentWidget() is original[mode]
    window.menu_toggle.click();assert window.sidebar.width()==232
    assert page.form.value('length')=='1500' and window.pages==original
    window.set_theme('light');assert window.theme_picker.currentData()=='light'
    assert window.settings.get('sidebar_collapsed') is False


@pytest.mark.parametrize('mode',('pdf','dxf_dwg'))
def test_visible_transfer_options_are_used_and_retained(window,mode):
    page=window.pages[mode];window.navigate(mode)
    assert page.options.is_expanded()
    page.form.set_value('recursive',False);page.form.set_value('overwrite',True)
    page.options.set_expanded(True);assert page.options_form.fields['overwrite'].isChecked()
    page.options.set_expanded(False);assert page.form.values()['overwrite'] is True
    assert page.form.values()['recursive'] is False
    if mode=='dxf_dwg':
        page.form.set_value('format','DWG');page.form.set_value('bend_lines',True)
        assert page.form.value('format')=='DWG'
        assert page.form.values()['group_by_thickness'] is True
        assert page.form.values()['bend_lines'] is True


def test_naming_rules_survive_disclosure_and_numbering_switches(window):
    window.navigate('naming');page=window.pages['naming']
    page.form.set_value('prefix','DRM-');page.rules_options.set_expanded(True)
    page.form.set_value('mode','Numaralı')
    assert page.name_left.fields['start'].isVisible() and page.name_right.fields['digits'].isVisible()
    page.form.set_value('start','12');page.form.set_value('digits','4')
    page.rules_options.set_expanded(False);page.rules_options.set_expanded(True)
    assert page.form.value('prefix')=='DRM-' and page.form.value('start')=='12'
    page.form.set_value('mode','Ön / son ek')
    assert page.name_left.fields['start'].isHidden() and page.form.value('digits')=='4'


def test_small_stack_measurement_picker_preserves_chain_across_resize(window,qtbot):
    window.resize(820,560);window.navigate('tolerance_stack');page=window.pages['tolerance_stack']
    page.load_example();qtbot.wait(60);terms=list(page.project.terms)
    assert page.compact_library and page.library_button.isVisible()
    assert page.tabs.width()>450
    page.library_button.click();qtbot.wait(30)
    assert page.library_dialog.isVisible() and page.library.isVisible()
    page.library_dialog.reject();window.resize(1440,900);qtbot.wait(60)
    assert not page.compact_library and page.library.isVisible()
    assert page.project.terms==terms and page.splitter.count()==2
    assert page.calculate_button.isVisible()


def test_bom_technical_columns_are_optional_without_losing_data_model(window):
    window.navigate('bom');page=window.pages['bom']
    assert page.parts.isColumnHidden(4) and page.tree.isColumnHidden(4)
    page.columns_action.setChecked(True)
    assert not page.parts.isColumnHidden(4) and not page.tree.isColumnHidden(4)
    page.columns_action.setChecked(False)
    assert page.parts_model.columnCount()==7 and page.tree_model.columnCount()==6


def test_settings_exposes_live_theme_and_navigation_without_resetting_inputs(window):
    window.pages['weight'].form.set_value('length','1750')
    def choose():
        dialog=QApplication.activeModalWidget()
        dialog.findChild(QComboBox,'appearancePreference').setCurrentIndex(1)
        dialog.findChild(QCheckBox,'compactNavigationPreference').setChecked(True)
        dialog.reject()
    QTimer.singleShot(60,choose);window.show_settings()
    assert window.appearance=='light' and window.sidebar_collapsed
    assert window.pages['weight'].form.value('length')=='1750'


def test_naming_multiple_found_assemblies_requires_an_explicit_selection(window):
    page=window.pages['naming'];page.handle_events([('assemblies',['A.SLDASM','B.SLDASM'])])
    assert page.assemblies.currentIndex()==-1
    page.scan();assert not window.jobs.busy and 'listesinden' in page.status_text


@pytest.mark.parametrize('mode',('pdf','dxf_dwg','bom','naming'))
def test_transfer_columns_keep_sources_left_results_right_and_commands_visible(window,qtbot,mode):
    page=window.pages[mode];window.navigate(mode)
    for width,height in ((1440,900),(820,560),(1440,900)):
        window.resize(width,height);qtbot.wait(30)
        workspace=page.splitter
        left,right=workspace.widget(0),workspace.widget(1)
        geometry=(mode,(width,height),window.size().toTuple(),workspace.size().toTuple(),
                  workspace.sizes(),left.geometry().getRect(),right.geometry().getRect(),
                  page.source_scroll.geometry().getRect(),page.scan_button.geometry().getRect())
        assert workspace.orientation()==Qt.Horizontal
        assert 220<=left.width()<=400,geometry
        assert right.width()>=320,geometry
        assert left.geometry().right()<right.geometry().left()
        assert abs(left.height()-right.height())<2
        assert page.source_scroll.horizontalScrollBar().maximum()==0
        assert page.command_bar.isVisible()
        assert page.scan_button.mapTo(page,QPoint()).y()+page.scan_button.height()<workspace.mapTo(page,QPoint()).y(),geometry
        assert abs(page.source_scroll.height()-left.height())<2,geometry
        if width==1440:
            assert left.width()==330 and right.width()>left.width()*2,geometry
        for number in range(page.actions.count()):
            control=page.actions.itemAt(number).widget()
            if control.isVisible():
                assert page.command_bar.isAncestorOf(control)
                assert page.rect().contains(control.mapTo(page,control.rect().bottomRight()))
    workspace.moveSplitter(385,1)
    assert workspace.sizes()[0]==385,(mode,window.size().toTuple(),workspace.sizes())
    window.resize(820,560);qtbot.wait(30)
    assert workspace.sizes()[1]>=320
    window.resize(1440,900);qtbot.wait(30)
    assert workspace.sizes()[0]==385,(mode,window.size().toTuple(),workspace.sizes())


@pytest.mark.parametrize('mode',('pdf','dxf_dwg'))
def test_source_inventory_selection_filters_and_clear_share_the_export_model(window,qtbot,mode):
    page=window.pages[mode];window.navigate(mode)
    paths=['C:/Çizimler/Üst sac.SLDPRT','C:/Çizimler/Alt sac.SLDPRT']
    page.handle_events([('files',paths),('result',dict(source=paths[0],status='success',detail='Aktarıldı'))])
    inventory=page.source_files;results=page.results
    assert inventory.proxy.sourceModel() is results.model
    assert inventory.proxy.rowCount()==2
    assert inventory.proxy.index(0,0).data()=='Üst sac.SLDPRT'
    assert inventory.proxy.index(0,0).data(Qt.ToolTipRole)==paths[0]
    results.filter.setCurrentIndex(results.filter.findData('success'))
    assert results.proxy.rowCount()==1 and inventory.proxy.rowCount()==2
    # Clicking an input reveals its result even if a prior output filter hid it.
    inventory.view.clicked.emit(inventory.proxy.index(1,0))
    assert results.table.currentIndex().data(Qt.UserRole)['source']==paths[1]
    assert results.filter.currentData() is None
    inventory.search.setText('Üst');qtbot.wait(130)
    assert inventory.proxy.rowCount()==1
    page.set_busy(True);results.clear_button.click()
    assert inventory.proxy.rowCount()==1 and results.model.rowCount()==2
    page.set_busy(False);results.clear_button.click()
    assert inventory.proxy.rowCount()==results.model.rowCount()==0
    assert inventory.search.text()=='' and results.results==[]
    assert inventory.counter.text()==('Sac gövdeleri · 0' if mode=='dxf_dwg' else 'Kaynak dosyalar · 0')


def test_bom_source_selection_shows_part_or_assembly_results_and_clear(window):
    from modules.bom.exporter import Part,Node,Result
    page=window.pages['bom'];window.navigate('bom')
    page.load_result(Result('C:/Ana.SLDASM','Default',
        (Part('Kapak','C:/Kapak.SLDPRT','Default',2,1.5,3.),),
        (Node('1','',1,'Ana','Ana','Montaj','C:/Ana.SLDASM','Default'),
         Node('1.1','1',2,'Kapak','Kapak-1','Parça','C:/Kapak.SLDPRT','Default',1.5)),0,0,False))
    root=page.tree_proxy.index(0,0)
    page.source_tree.setCurrentIndex(root)
    assert page.tabs.currentWidget() is page.tree and page.tree.currentIndex()==root
    child=page.tree_proxy.index(0,0,root)
    page.source_tree.setCurrentIndex(child)
    assert page.tabs.currentWidget() is page.parts
    assert page.parts.currentIndex().data(Qt.UserRole)['name']=='Kapak'
    page.clear_button.click()
    assert page.source_tree.model().rowCount()==page.parts_model.rowCount()==0
    assert not page.export_button.isEnabled()
