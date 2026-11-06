"""Sac Açınımı page on the real core.unfolding service (contract v1)."""

import math
import threading
import zipfile

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QPointF
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from gui_qt.app import MainWindow, create_application, MODULES
from modules.sheet_unfolding.numbers import parse
from modules.sheet_unfolding.service import EngineService
from modules.sheet_unfolding.ui import UnfoldPage

CIRCUMFERENCE = math.pi * 300                      # cylinder 300 × 200, mid surface: 942,477796 × 200 mm


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(w)
    w.resize(1600, 950); w.show(); yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=8000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def settle(qtbot, page):
    page.calculate_now()
    qtbot.waitUntil(lambda: not page.jobs.busy and page.state != 'running', timeout=20000)


@pytest.fixture
def page(window, qtbot):
    window.navigate('sheet_unfolding'); p = window.pages['sheet_unfolding']
    settle(qtbot, p); return p


def edit(page, key, text):
    page.fields[key]['edit'].setText(text); page.fields[key]['edit'].textEdited.emit(text)


class Gated(EngineService):
    """Real engine with a gate so tests can hold a calculation in flight."""
    def __init__(self):
        super().__init__(); self.gate = threading.Event(); self.gate.set()
    def calculate(self, request, cancel_token=None):
        self.gate.wait(5)
        return super().calculate(request, cancel_token)


@pytest.fixture
def gated(window, qtbot):
    service = Gated(); window.navigate('sheet_unfolding')
    p = UnfoldPage(window, service=service); qtbot.addWidget(p); p.resize(1500, 900); p.show(); settle(qtbot, p)
    return p, service


def test_menu_real_engine_and_reference_cylinder(page):
    assert ('sheet_unfolding', 'Sac Açınımı', 'ÜRETİM') in MODULES
    assert not page.service.is_fixture and not page.banner.isVisible()
    assert page.shape_id == 'cylinder' and set(page.fields) >= {'diameter', 'height', 'thickness'}
    assert page.state in ('ok', 'warning')
    m = page.result['parts'][0]['metrics']
    assert m['bbox_mm'][0] == pytest.approx(CIRCUMFERENCE) and m['bbox_mm'][1] == pytest.approx(200.)
    assert m['net_area_mm2'] == pytest.approx(CIRCUMFERENCE * 200.)
    assert page.metrics.values['size'].text() == '942,5 × 200 mm'
    assert 'Analitik' in page.method_label.text()
    for key in ('dxf', 'pdf', 'step', 'zip'):
        assert page.export_buttons[key].isEnabled()


def test_legacy_forms_calculate_and_source_catalogue_is_dynamic(page, qtbot):
    for shape in page.shapes:
        if shape['status'] != 'implemented' or shape.get('source_ids'):
            continue
        for variant in shape['variants']:
            page.choose_shape(shape['shape_id'], variant['variant_id']); settle(qtbot, page)
            assert page.state in ('ok', 'warning'), (shape['shape_id'], page.messages.toPlainText())
            assert page.part_table.rowCount() >= 1 and page.flat_view.parts
    page.shape_search.setText('pantolon')
    item = page.shape_tree.item(0)
    assert 'Planlanan' not in item.text() and (item.flags() & Qt.ItemIsEnabled)
    assert sum(len(s.get('source_ids', ())) for s in page.shapes) == 191
    page.choose_shape('unfoldo/Silindir','cylinder'); settle(qtbot,page)
    assert page.state in ('ok','warning') and page.result['parts'][0]['metrics']['bbox_mm'][0] == pytest.approx(math.pi*200.)
    page.shape_search.setText('kurtağzı')
    assert any(page.shape_tree.item(i).data(Qt.UserRole) == 'rect_to_round' for i in range(page.shape_tree.count()))


def test_capabilities_drive_outputs(page, qtbot):
    page.choose_shape('cylinder', 'bevel'); settle(qtbot, page)
    assert not page.export_buttons['step'].isEnabled() and 'STEP' in page.export_buttons['step'].toolTip()
    page.choose_shape('rectangular_reducer', 'centered'); settle(qtbot, page)
    assert page.part_table.rowCount() == 4 and not page.export_buttons['dxf'].isEnabled()
    assert 'ZIP' in page.export_buttons['dxf'].toolTip() and page.export_buttons['zip'].isEnabled()


def test_options_follow_the_schema(page, qtbot):
    assert page.fields['seam_angle']['edit'].isEnabled() and page.fields['split_count']['edit'].isEnabled()
    assert not page.fields['joint']['edit'].isEnabled()                   # overlap only with a lap joint
    page.joint_kind.setCurrentIndex(page.joint_kind.findData('lap')); edit(page, 'joint', '10')
    assert page.build_request()['joint_options'] == dict(kind='lap', overlap=10.)
    page.choose_shape('rect_to_round', 'centered_faceted')
    assert not page.fields['seam_angle']['edit'].isEnabled() and not page.joint_kind.isEnabled()
    assert page.reference.count() == 1 and page.reference.currentData() == 'mid'


def test_decimal_entry_and_ambiguous_numbers():
    assert parse('1,2') == parse('1.2') == pytest.approx(1.2)
    assert parse('1.234,5') == pytest.approx(1234.5)
    for text in ('1.234', '1,2,3', '1.2.3', 'abc', ''):
        with pytest.raises(ValueError):
            parse(text)


def test_inch_input_is_the_same_physical_part(page, qtbot):
    mm_width = page.result['parts'][0]['metrics']['bbox_mm'][0]
    page.unit.setCurrentIndex(page.unit.findData('inch')); settle(qtbot, page)
    assert page.values['diameter'] == pytest.approx(300.) and page.fields['diameter']['edit'].text() == '11,811024'
    request = page.build_request()
    assert request['input_units'] == 'inch' and request['parameters']['diameter'] * 25.4 == pytest.approx(300.)
    assert page.result['parts'][0]['metrics']['bbox_mm'][0] == pytest.approx(mm_width)   # service answers in mm
    assert page.metrics.values['size'].text().endswith('inch')


def test_field_errors_from_the_service_and_recovery(page, qtbot):
    edit(page, 'diameter', '0'); settle(qtbot, page)
    assert page.state == 'error' and page.fields['diameter']['error'].isVisible()
    edit(page, 'diameter', '1.234')
    assert 'belirsiz' in page.fields['diameter']['error'].text() and page.state == 'invalid_stale'
    edit(page, 'diameter', '320,5'); settle(qtbot, page)
    assert page.state in ('ok', 'warning') and not page.fields['diameter']['error'].isVisible()
    assert page.result['parts'][0]['metrics']['bbox_mm'][0] == pytest.approx(math.pi * 320.5)


def test_late_result_is_rejected_and_stale_blocks_outputs(gated, qtbot):
    page, service = gated
    service.gate.clear(); edit(page, 'diameter', '310'); page.calculate_now()
    assert page.jobs.busy
    edit(page, 'diameter', '320')
    assert page.state == 'stale' and not page.export_buttons['dxf'].isEnabled() and not page.add_part_button.isEnabled()
    service.gate.set(); qtbot.waitUntil(lambda: not page.jobs.busy, timeout=8000)
    assert page.result_request['parameters']['diameter'] != 310.          # the 310 answer was discarded
    settle(qtbot, page)
    assert page.result_request['parameters']['diameter'] == 320. and page.result_revision == page.revision


def test_cancel_is_reported(gated, qtbot):
    page, service = gated
    service.gate.clear(); edit(page, 'height', '210'); page.calculate_now()
    page.jobs.cancel(); service.gate.set()
    qtbot.waitUntil(lambda: not page.jobs.busy, timeout=8000)
    assert page.state == 'cancelled'


def test_mass_and_cost_come_from_the_service(page, qtbot):
    assert page.material.currentData() == 'Demir / Çelik'
    mass = page.result['parts'][0]['metrics']['mass_kg']
    assert mass == pytest.approx(CIRCUMFERENCE * 200 * 2 * 7850e-9, rel=1e-9)
    edit(page, 'price', '30'); settle(qtbot, page)
    assert page.part_table.item(0, 7).text() == f'{mass * 30:.2f}'.replace('.', ',')
    page.material.setCurrentIndex(0); settle(qtbot, page)                 # no material → no mass, never "0 kg"
    assert page.part_table.item(0, 6).text().startswith('Hesaplanamadı')
    assert page.metrics.values['mass'].text() == 'Hesaplanamadı'


def test_drawing_uses_service_vectors_and_measures_service_geometry(page):
    view = page.flat_view
    before = len([i for i in view.scene().items() if i.data(0)])
    page.layer_boxes['construction'].setChecked(False)
    assert len([i for i in view.scene().items() if i.data(0)]) < before
    received = []; view.measured.connect(received.append)
    view.add_measure_point((0., 0.)); view.add_measure_point((CIRCUMFERENCE, 0.))
    assert received[-1] == pytest.approx(CIRCUMFERENCE, abs=1e-6)
    assert view.nearest_snap(QPointF(0., 0.)) is not None
    assert page.mesh_view.mesh is not None and page.view_choice.count() == 3   # 3D + front + top views
    page.view_choice.setCurrentIndex(1); assert page.mesh_stack.currentIndex() == 1


def test_cone_arcs_are_real_arcs(page, qtbot):
    page.choose_shape('cone', 'frustum'); settle(qtbot, page)
    arcs = [e for e in page.result['parts'][0]['geometry_2d']['entities'] if e['type'] == 'arc']
    assert len(arcs) >= 2 and all(e['end_deg'] > e['start_deg'] for e in arcs)


def test_dimensions_edit_on_the_drawing_and_keyboard(page, qtbot):
    editor = page.sketch.editors['diameter']
    editor.setText('260'); editor.textEdited.emit('260')
    assert page.values['diameter'] == 260. and page.fields['diameter']['edit'].text() == '260'
    QCoreApplication.sendEvent(page.fields['height']['edit'], QFocusEvent(QEvent.FocusIn))
    assert page.sketch.active == 'height'
    field = page.fields['height']['edit']; field.selectAll(); QTest.keyClicks(field, '999')
    QTest.keyClick(field, Qt.Key_Escape)
    assert field.text() == '200' and page.values['height'] == 200.


def test_exports_are_written_by_the_service(page, qtbot, tmp_path, monkeypatch):
    for kind, name in (('dxf', 'c.dxf'), ('pdf', 'c.pdf'), ('zip', 'c.zip')):
        target = tmp_path / name
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, t=target, **k: (str(t), ''))
        page.export_buttons[kind].click()
        qtbot.waitUntil(lambda: not page.jobs.busy, timeout=60000)
        assert target.is_file() and target.stat().st_size > 0, page.status_text
        assert 'oluşturuldu' in page.status_text
    assert zipfile.is_zipfile(tmp_path / 'c.zip')
    assert (tmp_path / 'c.dxf').read_text(errors='ignore').count('CUT') >= 1


def test_project_save_open_and_zip(page, qtbot, tmp_path, monkeypatch):
    page.add_to_project()
    page.choose_shape('cone', 'frustum'); settle(qtbot, page); page.add_to_project()
    page.project_table.selectRow(1); page.part_quantity.setValue(3)
    assert page.project_parts[1]['quantity'] == 3 and page.dirty
    target = tmp_path / 'proje.gokunfold.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    page.save_project()
    assert target.is_file() and not page.dirty
    saved = page.service.load_project(str(target))
    assert [item.quantity for item in saved.items] == [1, 3] and saved.items[1].request.shape_id == 'cone'
    page.project_parts = []; page.refresh_project()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(target), ''))
    page.open_project(); settle(qtbot, page)
    assert len(page.project_parts) == 2 and page.project_parts[1]['quantity'] == 3
    assert page.shape_id == 'cylinder' and page.state in ('ok', 'warning')
    archive = tmp_path / 'proje.zip'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(archive), ''))
    page.project_zip_button.click(); qtbot.waitUntil(lambda: not page.jobs.busy, timeout=60000)
    assert zipfile.is_zipfile(archive), page.status_text


def test_send_to_nesting_transfers_real_contours(window, page, qtbot, monkeypatch):
    nesting = window.pages['nesting']
    assert nesting.project.materials
    material = nesting.project.materials[0]
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *a, **k: (a[3][0], True))
    before = len(nesting.project.parts)
    page.nesting_button.click()
    assert len(nesting.project.parts) == before + 1, page.status_text
    part = nesting.project.parts[-1]
    assert part.material == material.id and part.thickness == pytest.approx(2.) and part.quantity == 1
    assert part.polygon.area == pytest.approx(CIRCUMFERENCE * 200, rel=1e-6) and 'CUT_OUTER' in part.original_dxf
    page.nesting_button.click()
    assert len(nesting.project.parts) == before + 1 and 'zaten' in page.status_text


@pytest.mark.parametrize('size', [(1366, 768), (1920, 1080)])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_layouts(window, page, size, theme):
    window.set_theme(theme); window.resize(*size); QCoreApplication.processEvents()
    assert not page.grab().isNull() and page.flat_view.appearance == theme
    assert (page.view_stack.currentWidget() is page.view_tabs) == (page.width() < 1250)


def test_source_project_options_survive_form_recalculation_and_unit_change(page,qtbot):
    from core.unfolding import UnfoldRequest
    from core.unfolding.models import Material
    req=UnfoldRequest(shape_id='unfoldo/Oval boru',variant_id='oval-cylinder',parameters={'L':300.,'W':200.,'H':400.},
        thickness=2.,material=Material('Demir / Çelik',7850.),model_options={'cut_type':'2_parts_180_degrees','strip_lap':7.})
    page.load_request(EngineService.page_request(req));settle(qtbot,page)
    assert page.state in ('ok','warning') and len(page.result['parts'])==2
    area=page.result['metrics']['cutting_area_mm2']
    assert page.build_request()['model_options']['strip_lap']==7.
    page.unit.setCurrentIndex(page.unit.findData('inch'));settle(qtbot,page)
    assert page.build_request()['model_options']['strip_lap']==pytest.approx(7/25.4)
    assert page.result['metrics']['cutting_area_mm2']==pytest.approx(area)
    page.add_to_project()
    saved=page.service.project(page.project_parts,'Kaynak model')
    assert saved.items[0].request.model_options['cut_type']=='2_parts_180_degrees'
    assert saved.items[0].request.model_options['strip_lap']==pytest.approx(7/25.4)
