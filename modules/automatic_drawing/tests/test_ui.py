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


def test_sorted_result_rows_keep_their_own_status_and_open_their_own_pdf(window, tmp_path):
    from modules.automatic_drawing.models import DrawingResult, Finding
    page = window.pages['automatic_drawing']
    results = [DrawingResult(Source(str(tmp_path/'Zeta.SLDPRT'), 'Default'), 'PASS', sheets=['1']),
               DrawingResult(Source(str(tmp_path/'Alfa.SLDPRT'), 'Default'), 'WARNING',
                             findings=[Finding('WARNING', 'w', 'Alfa uyarısı')]),
               DrawingResult(Source(str(tmp_path/'Beta.SLDPRT'), 'Uzun'), 'FAIL',
                             findings=[Finding('FAIL', 'f', 'Beta hatası')])]
    for result in results:
        page.show_result(result)
    table = page.result_table
    rows = {table.item(r, 0).text(): (table.item(r, 2).text(), table.item(r, 4).text()) for r in range(3)}
    assert rows == {'Zeta.SLDPRT': ('Başarılı', 'Temel yapısal doğrulamalar geçti.'),
                    'Alfa.SLDPRT': ('Uyarılı', 'Alfa uyarısı'), 'Beta.SLDPRT': ('Hatalı', 'Beta hatası')}
    opened = []
    page.pdf_document.load = opened.append
    for r in range(3):
        name = table.item(r, 0).text()
        target = tmp_path/(name+'.pdf'); target.write_bytes(b'%PDF-1.4')
        next(x for x in results if x.source.path.endswith(name)).outputs['pdf'] = str(target)
        table.setCurrentCell(r, 0); page.select_result()
        assert opened[-1] == str(target)
    assert [page.tiles[k].text() for k in ('PASS', 'WARNING', 'FAIL', 'sheets')] == ['1', '1', '1', '1']
    assert page.tabs.tabText(3) == 'Sonuçlar · 3' and not page.results_empty.isVisible()


def test_dependent_options_follow_their_parent_and_the_summary_follows_the_options(window):
    page = window.pages['automatic_drawing']; f = page.fields
    assert page.tree_empty.isVisible() and page.source_count.text() == 'Boş'
    f['bom'].setChecked(False)
    assert not f['bom_type'].isEnabled() and not f['balloons'].isEnabled() and not page.browse['bom_template'].isEnabled()
    f['bom'].setChecked(True)
    assert f['bom_type'].isEnabled() and page.browse['bom_template'].isEnabled()
    f['flat_pattern'].setChecked(False); assert not f['bend_lines'].isEnabled()
    page.set_busy(True); page.set_busy(False)
    assert not f['bend_lines'].isEnabled()           # busy end must not re-enable a dependent option
    f['dxf'].setChecked(True); f['manual_scale_text'].setText('1:2')
    chips = [c.text() for c in page.summary_chips if not c.isHidden()]
    assert 'SLDDRW + PDF + DXF' in chips and 'Ölçek 1:2' in chips and 'A3 yatay' in chips
    page.options()                                   # dependent values still validate and save


def test_dropped_solidworks_files_are_added_and_other_files_ignored(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, QUrl
    from PySide6.QtGui import QDropEvent
    page = window.pages['automatic_drawing']
    part, note = tmp_path/'Flans.SLDPRT', tmp_path/'not.txt'
    part.write_bytes(b''); note.write_text('x')
    data = QMimeData(); data.setUrls([QUrl.fromLocalFile(str(part)), QUrl.fromLocalFile(str(note))])
    page.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, data, Qt.LeftButton, Qt.NoModifier))
    assert page.tree.topLevelItemCount() == 1 and page.tree.topLevelItem(0).text(0) == 'Flans.SLDPRT'
    assert not page.tree_empty.isVisible() and page.source_count.text() == '1 dosya · 1 seçili'


def test_draft_sheet_preview_uses_the_generation_plan_and_follows_the_settings(window, tmp_path):
    from modules.automatic_drawing.layout import plan_sheets
    from modules.automatic_drawing.rules import plan_views
    page = window.pages['automatic_drawing']
    assert page.preview_stack.currentIndex() == 0 and not page.sheet_preview.plans
    info = ModelInfo(Source(str(tmp_path/'Mil.SLDPRT'), 'Default'), 'part', 'Mil', (420, 30, 30),
                     classification='shaft')
    page._analysis_item(info)
    preview = page.sheet_preview
    expected = plan_sheets(plan_views(info, page.options()), page.options())
    assert [(p.paper, p.scale, [(v.role, v.center) for v in p.views]) for p in preview.plans] == \
        [(p.paper, p.scale, [(v.role, v.center) for v in p.views]) for p in expected]
    assert preview.plans[0].scale == .2                     # the conservative isometric box sets 1:5
    page.fields['isometric'].setChecked(False)
    assert preview.plans[0].scale == .5 and 'isometric' not in {v.role for v in preview.plans[0].views}
    page.fields['manual_scale_text'].setText('5:1')        # cannot fit: said, not drawn
    assert not preview.plans and preview.error and 'sığmıyor' in page.preview_caption.text()
    page.fields['manual_scale_text'].setText('1:0')
    assert 'Ayarlar geçersiz' in preview.message
    page.fields['manual_scale_text'].setText('')
    assert preview.plans and 'ölçek 1:2' in page.preview_caption.text()
    window.grab()                                            # paints in the current theme without error


def test_draft_preview_does_not_save_settings_and_a_result_switches_to_the_pdf(window, tmp_path):
    from modules.automatic_drawing.models import DrawingResult
    page = window.pages['automatic_drawing']
    before = window.settings.get('automatic_drawing', None)
    page._analysis_item(ModelInfo(Source(str(tmp_path/'P.SLDPRT'), 'Default'), 'part', 'P', (100, 50, 10)))
    page.fields['paper'].setCurrentIndex(page.fields['paper'].findData('A2'))
    assert page.sheet_preview.plans[0].paper == 'A2'
    assert window.settings.get('automatic_drawing', None) == before   # only Generate saves options
    page.show_result(DrawingResult(Source(str(tmp_path/'P.SLDPRT'), 'Default'), 'PASS'))
    page.result_table.setCurrentCell(0, 0); page.select_result()
    assert page.preview_stack.currentIndex() == 1 and page.pdf_button.isChecked()
    page.draft_button.click()
    assert page.preview_stack.currentIndex() == 0 and not page.preview_empty.isVisible()
