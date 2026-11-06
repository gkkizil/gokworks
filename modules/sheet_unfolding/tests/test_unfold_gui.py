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


# ---- engine 1.1.0 source catalogue: model options on screen ---------------------------
def test_source_gallery_has_category_thumbnails_and_basic_shapes_apart(page):
    source = [s for s in page.shapes if s.get('source_ids')]
    assert source and all(s['preview'] for s in source)
    assert {s['category'] for s in page.shapes if not s.get('source_ids')} == {'Temel şekiller · krokili','Şekillendirme'}
    assert [s['shape_id'] for s in page.shapes if s['category']=='Şekillendirme']==['bent_profile']
    page.shape_search.setText('pantolon')
    assert page.shape_tree.count() >= 2 and all(page.shape_tree.item(i).flags() & Qt.ItemIsEnabled for i in range(page.shape_tree.count()))


def test_cut_choice_changes_pieces_and_is_sent_to_the_engine(page, qtbot):
    page.choose_shape('unfoldo/Oval boru', 'oval-cylinder'); settle(qtbot, page)
    assert not page.sketch.isVisible() and page.model['cut'].count() > 1
    one = len(page.result['parts'])
    page.model['cut'].setCurrentIndex(page.model['cut'].findData('2_parts_180_degrees')); settle(qtbot, page)
    assert page.build_request()['model_options']['cut_type'] == '2_parts_180_degrees'
    assert page.state in ('ok', 'warning') and len(page.result['parts']) == 2 != one


def test_duct_shows_only_flange_and_end_lap_and_they_grow_the_blank(page, qtbot):
    page.choose_shape('unfoldo/Düz kanal', 'rectangular-duct-straight'); settle(qtbot, page)
    assert set(page.model['laps'].values()) == {'lap_top', 'lap_left'}
    assert 'flanş' in page.fields['opt.lap_top']['title']
    area = sum(p['metrics']['gross_area_mm2'] for p in page.result['parts'])
    edit(page, 'opt.lap_top', '15'); settle(qtbot, page)
    assert page.build_request()['model_options']['lap_top'] == pytest.approx(15.)
    assert page.state in ('ok', 'warning') and sum(p['metrics']['gross_area_mm2'] for p in page.result['parts']) > area
    page.unit.setCurrentIndex(page.unit.findData('inch')); settle(qtbot, page)
    assert page.build_request()['model_options']['lap_top'] == pytest.approx(15 / 25.4)
    page.unit.setCurrentIndex(page.unit.findData('mm'))


def test_discrete_parameter_is_a_list_and_numbering_follows_the_model(page, qtbot):
    page.choose_shape('unfoldo/Dikdörtgen redüksiyon', 'rectangle-to-rectangle-angled-top'); settle(qtbot, page)
    combo = page.fields['diagonal']['combo']
    assert [combo.itemText(i) for i in range(combo.count())] == ['Köşegen 1', 'Köşegen 2'] and not page.fields['diagonal']['edit'].isVisible()
    combo.setCurrentIndex(1); settle(qtbot, page)
    assert page.build_request()['parameters']['diagonal'] == 2 and page.state in ('ok', 'warning')
    page.model['divisions'].setCurrentIndex(page.model['divisions'].findData(48)); settle(qtbot, page)
    assert page.build_request()['model_options']['helper_divisions'] == 48 and page.state in ('ok', 'warning')
    page.choose_shape('unfoldo/Helezon kanat', 'helical-ramp-triangulated'); settle(qtbot, page)
    assert not page.model['numbering'].isEnabled() and not page.model['numbering'].isChecked()
    assert 'numbering' not in page.build_request()['model_options']
    assert page.state in ('ok', 'warning')


def test_model_info_and_validated_example(page, qtbot):
    page.choose_shape('unfoldo/Borudan eğik koniye', 'pipe-to-oblique-cone-vertical-trunk'); settle(qtbot, page)
    text = page.model['info'].text()
    assert 'İmalat onayı' in text and 'imalat/proses onayı değildir' in text and 'unfoldo.com' in text
    edit(page, 'thickness', '3')
    page.model['example'].click(); settle(qtbot, page)
    assert page.values['Xb'] == pytest.approx(-200.) and page.values['thickness'] == pytest.approx(3.)
    assert page.values['seam_angle'] == pytest.approx(180.)
    assert page.state in ('ok', 'warning'), (page.result.get('errors'), page.build_request())


def test_source_model_options_round_trip_through_a_project_part(page, qtbot):
    page.choose_shape('unfoldo/Düz kanal', 'rectangular-duct-straight')
    edit(page, 'opt.lap_left', '12'); settle(qtbot, page)
    page.add_to_project()
    page.choose_shape('unfoldo/Silindir', 'cylinder'); settle(qtbot, page)
    page.project_table.selectRow(0); settle(qtbot, page)
    assert page.shape_id == 'unfoldo/Düz kanal' and page.values['opt.lap_left'] == pytest.approx(12.)
    assert page.build_request()['model_options']['lap_left'] == pytest.approx(12.)


def test_opening_a_zero_thickness_unpriced_part_clears_previous_production_values(page,qtbot):
    from core.unfolding import UnfoldRequest
    edit(page,'thickness','4');edit(page,'price','30');settle(qtbot,page)
    edit(page,'price','hatalı')
    req=UnfoldRequest(parameters={'diameter':200.,'height':300.},thickness=0.)
    page.load_request(EngineService.page_request(req));settle(qtbot,page)
    restored=EngineService.engine_request(page.build_request())
    assert restored.thickness==0. and restored.material.density_kg_m3 is None
    assert restored.material.unit_price is None
    assert not page.errors and not page.fields['price']['error'].isVisible()
    assert page.result['metrics']['mass_kg'] is None


@pytest.mark.parametrize('name',['Özel denetim sacı','Demir / Çelik'])
def test_project_material_and_precision_survive_editing_and_units(page,qtbot,name):
    from core.unfolding import UnfoldRequest
    from core.unfolding.models import Material,DevelopmentOptions
    req=UnfoldRequest(parameters={'diameter':200.,'height':300.},thickness=1.5,
        material=Material(name,8100.,0.,price_unit='m2',currency='EUR'),
        development_options=DevelopmentOptions(chord_error_mm=.005,mesh_error_mm=.1,max_samples=8192))
    page.load_request(EngineService.page_request(req));settle(qtbot,page)
    restored=EngineService.engine_request(page.build_request())
    assert restored.material==req.material and restored.development_options==req.development_options
    assert '8100' in page.material.currentText()
    assert page.result['metrics']['material_cost']==0.
    assert 'EUR/m²' in page.fields['price']['label'].text()
    assert 'EUR' in page.part_table.horizontalHeaderItem(7).text()
    edit(page,'price','42');settle(qtbot,page)
    assert page.result['metrics']['material_cost']==pytest.approx(math.pi*200*300/1e6*42)
    page.unit.setCurrentIndex(page.unit.findData('inch'));settle(qtbot,page)
    assert EngineService.engine_request(page.build_request()).development_options==req.development_options
    assert page.result['metrics']['material_cost']==pytest.approx(math.pi*200*300/1e6*42)


def test_source_options_survive_switching_away_and_back(page,qtbot):
    from core.unfolding import UnfoldRequest
    req=UnfoldRequest(shape_id='unfoldo/Oval boru',variant_id='oval-cylinder',
        parameters={'L':300.,'W':200.,'H':400.},model_options={'cut_type':'2_parts_180_degrees','strip_lap':7.})
    page.load_request(EngineService.page_request(req));settle(qtbot,page)
    page.choose_shape('cylinder','straight');settle(qtbot,page)
    page.choose_shape(req.shape_id,req.variant_id);settle(qtbot,page)
    assert page.build_request()['model_options']==dict(req.model_options)
    assert len(page.result['parts'])==2


def test_stale_validation_does_not_clear_a_new_validation_error(page):
    old_request=page.build_request()
    page.revision+=1
    current=page.build_request()
    page.accept_validation(current,{'issues':[{'field_ids':['diameter'],'severity':'error','message':'Yeni çap hatası'}]})
    message=page.fields['diameter']['error'].text()
    assert message and old_request['revision']!=page.revision
    page.accept_validation(old_request,{'issues':[]})
    assert page.fields['diameter']['error'].text()==message


def test_source_output_default_is_a_filename_not_a_source_id_path(page,qtbot,monkeypatch):
    page.choose_shape('unfoldo/Silindir','cylinder');settle(qtbot,page)
    names=[]
    def picker(*args,**kwargs):names.append(args[2]);return ('','')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',picker)
    page.export_current('dxf')
    assert len(names)==1 and '/' not in names[0] and '\\' not in names[0]


def test_repeated_add_and_duplicate_make_distinct_valid_project_requests(page,tmp_path):
    page.add_to_project();page.add_to_project()
    page.project_table.selectRow(0);page.duplicate_part()
    project=page.project_object()
    assert len({v.request.request_id for v in project.items})==3
    page.service.save_project(project,tmp_path/'duplicates.json')


def test_open_save_preserves_project_quantity_code_and_revision(page,qtbot,tmp_path,monkeypatch):
    from core.unfolding import UnfoldProject,ProjectItem,UnfoldRequest
    project=UnfoldProject((ProjectItem('PARÇA',UnfoldRequest(parameters={'diameter':200.,'height':300.}),3),),
        name='Toplu proje',code='İŞ-001',revision='C',quantity=7)
    path=tmp_path/'project.json';page.service.save_project(project,path)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    page.open_project();settle(qtbot,page)
    again=page.project_object()
    assert (again.code,again.revision,again.quantity)==('İŞ-001','C',7)
    assert again.items[0].quantity==3


def test_pdf_text_is_black_even_in_the_dark_theme(window, tmp_path):
    """The printed report must not inherit the application's light-on-dark text palette."""
    from PySide6.QtCore import QSize
    from PySide6.QtPdf import QPdfDocument
    from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication
    window.set_theme('dark')
    palette = QApplication.palette()                     # as on Windows: light text for dark widgets
    for role in (QPalette.Text, QPalette.WindowText):
        palette.setColor(role, QColor('#e8e8e8'))
    QApplication.setPalette(palette)
    engine = UnfoldService()
    result = engine.calculate(UnfoldRequest(shape_id='cone', variant_id='frustum',
                                            parameters={'bottom_diameter': 300., 'top_diameter': 150., 'height': 200.}))
    path = tmp_path / 'report.pdf'
    assert engine.export(result, ExportOptions(path=str(path), format='pdf', overwrite=True)).status == 'complete'
    document = QPdfDocument(); document.load(str(path))
    image = document.render(0, QSize(600, 850))
    header = [image.pixelColor(x, y) for y in range(0, 150) for x in range(0, 600, 2)]
    darkest = min(c.lightness() for c in header if c.alpha() > 128)     # rendered page background is transparent
    assert darkest < 60, f'başlık metni okunmuyor (en koyu piksel açıklığı {darkest})'
