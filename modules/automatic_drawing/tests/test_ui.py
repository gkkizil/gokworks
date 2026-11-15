import json
from threading import get_ident

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget

from gui_qt.app import MODULES, PAGE_TYPES, MainWindow, create_application
from modules.automatic_drawing import ui
from modules.automatic_drawing.models import ModelInfo, Node, Source


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1366, 768); w.show(); w.navigate('automatic_drawing')
    yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=5000)
    w.close()


def test_one_registered_module_one_source_tree_and_no_com_on_open(window):
    page = window.pages['automatic_drawing']
    assert sum(key == 'automatic_drawing' for key, title, category in MODULES) == 1
    assert PAGE_TYPES['automatic_drawing'][0] == 'modules.automatic_drawing.ui'
    assert window.browser.buttons['automatic_drawing'].text() == 'Otomatik Teknik Resim'
    assert len(page.findChildren(QTreeWidget)) == 1
    assert not window.jobs.busy
    assert page.options().projection == 'first'
    assert page.options().paper == 'A3'
    assert page.options().pdf and not page.options().geometry_dimensions


@pytest.mark.parametrize('size', ((820, 560), (1024, 700), (1440, 900)))
@pytest.mark.parametrize('theme', ('dark', 'light'))
def test_header_actions_visible_and_options_accessible_in_both_themes(window, qtbot, size, theme):
    window.set_theme(theme); window.resize(*size); qtbot.wait(25)
    page = window.pages['automatic_drawing']
    for index in range(page.actions.count()):
        control = page.actions.itemAt(index).widget()
        if control.isVisible():
            assert page.rect().contains(control.mapTo(page, control.rect().bottomRight()))
    assert not window.grab().isNull()
    assert page.tree.isVisible() and page.tabs.isVisible()


def test_tree_preserves_assembly_instances_and_selected_file_config_identity(window, tmp_path):
    page = window.pages['automatic_drawing']
    source = Source(str(tmp_path/'Assembly.SLDASM'), 'Product')
    part = Source(str(tmp_path/'Bolt.SLDPRT'), 'M8')
    root = Node('Assembly', source, 'assembly', children=[Node(f'Bolt-{i}', part) for i in range(12)])
    info = ModelInfo(source, 'assembly', 'Assembly', (100, 50, 20), tree=root)
    page._analysis_item(info)
    assert page.tree.topLevelItemCount() == 1
    item = page.tree.topLevelItem(0)
    assert item.childCount() == 12 and item.text(1) == 'Product'
    for i in range(12): item.child(i).setCheckState(0, Qt.Checked)
    assert page.selected_sources() == (source, part)
    assert page.tree.currentItem().data(0, Qt.UserRole+1) == info


def test_manual_configuration_edit_is_not_replaced_by_the_active_model_configuration(window, tmp_path):
    page = window.pages['automatic_drawing']
    source = Source(str(tmp_path/'part.SLDPRT'), 'Default')
    page.add_sources([source])
    page.tree.topLevelItem(0).setText(1, 'Machined')
    assert page.selected_sources() == (Source(source.path, 'Machined'),)
    page._analysis_item(ModelInfo(Source(source.path, 'Machined'), 'part', 'Part', (100, 50, 10)))
    assert page.tree.topLevelItemCount() == 1


def test_options_validation_reports_bad_scale_without_starting_a_com_job(window):
    page = window.pages['automatic_drawing']
    page.fields['manual_scale_text'].setText('1:0')
    page.start()
    assert not window.jobs.busy and 'pozitif' in page.status_text
    page.fields['manual_scale_text'].setText('1:2,5')
    assert page.options().manual_scale == .4


def test_analysis_operation_uses_existing_background_queue_and_only_plain_events(window, qtbot, monkeypatch, tmp_path):
    page, main_thread = window.pages['automatic_drawing'], get_ident()
    source = Source(str(tmp_path/'part.SLDPRT'))
    page.add_sources([source])
    seen = []
    def operation_factory(kind, sources=(), *args, **kwargs):
        def run(events, stop):
            seen.append((kind, get_ident()))
            events.put(('drawing_analysis', ModelInfo(Source(source.path, 'Default'), 'part',
                'Part', (100, 50, 10), body_count=1)))
        return run
    monkeypatch.setattr(ui, 'worker', operation_factory)
    page.analyze()
    qtbot.waitUntil(lambda: not window.jobs.busy, timeout=5000)
    assert seen[0][0] == 'analyze' and seen[0][1] != main_thread
    assert page.tree.topLevelItem(0).text(1) == 'Default'
    assert '100 × 50 × 10' in page.analysis_text.toPlainText()


@pytest.mark.parametrize('raw', (None, True, 'bad', [], {'paper': [], 'pdf': 'false',
    'property_map': [1, {}, None], 'custom_width_mm': float('inf'), 'template': {'bad': 1}}))
def test_corrupt_module_settings_still_open_without_com(qtbot, tmp_path, raw):
    create_application([])
    path = tmp_path/'settings.json'; path.write_text(json.dumps({'automatic_drawing': raw}))
    w = MainWindow(path); qtbot.addWidget(w); w.navigate('automatic_drawing')
    page = w.pages['automatic_drawing']
    assert page.fields['paper'].currentData() == 'A3'
    assert page.fields['pdf'].isChecked()
    assert not w.jobs.busy
    w.close()
