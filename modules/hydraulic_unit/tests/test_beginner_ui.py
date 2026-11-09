"""Teknik olmayan kullanıcı akışı ve görünüm geçişlerinde veri bütünlüğü."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit.core.models import Project,Cylinder
from modules.hydraulic_unit.core.service import calculate_project
from modules.hydraulic_unit.serialization import save,load
from modules.hydraulic_unit.ui import HydraulicPage


@pytest.fixture
def easy(qtbot,tmp_path):
    create_application([])
    context=SimpleNamespace(settings=SettingsStore(tmp_path/'settings.json'),jobs=JobManager(),appearance='dark')
    page=HydraulicPage(context);qtbot.addWidget(page);page.resize(1366,900);page.show();qtbot.wait(10)
    yield page
    page.cancel_pdf();page.settings.flush()


def edit(widget,text):
    widget.setText(text);widget.textEdited.emit(text)


def test_new_users_start_with_three_plain_language_steps(easy):
    assert easy.view_mode.currentText()=='Kolay kullanım'
    assert easy.simple.steps.count()==3
    assert not easy.summary_panel.isVisible() and not easy.guide_widget.isVisible()
    assert easy.result.input_fingerprint==calculate_project(Project()).input_fingerprint


def test_simple_edits_roundtrip_between_views_without_changing_advanced_settings(easy):
    original=easy.project
    edit(easy.simple.inputs['cylinder.bore'],'80');easy.recalculate()
    assert easy.project.cylinders[0].bore==.08
    assert easy.project.pump==original.pump and easy.project.oil==original.oil
    assert easy.project.thermal==original.thermal and easy.project.accumulator==original.accumulator
    edited=easy.project
    easy.open_detailed(0)
    assert easy.project==edited and easy.cylinder_table.item(0,1).text()=='80'
    easy.view_mode.setCurrentIndex(0)
    assert easy.project==edited and easy.simple.inputs['cylinder.bore'].text()=='80'


def test_view_switch_keeps_independent_cylinder_check_inputs(easy):
    easy.open_detailed(0);widget=easy.fields['point.force'][0]
    widget.setText('42');easy.recalculate()
    easy.view_mode.setCurrentIndex(0);easy.open_detailed(0)
    assert widget.text()=='42'


def test_time_input_uses_core_and_preserves_non_edited_speed_phases(easy):
    original=easy.project
    edit(easy.simple.phase_inputs[0]['duration'],'5');easy.recalculate()
    assert easy.project.phases[0].speed is None and easy.project.phases[0].duration==5.
    assert easy.result.cycle['phases'][0].speed==pytest.approx(.25/5)
    assert easy.project.phases[1:]==original.phases[1:]


def test_force_unit_switch_preserves_force_and_pending_user_edits(easy):
    original=easy.project
    easy.simple.force_unit.setCurrentIndex(easy.simple.force_unit.findData('tonf'));easy.recalculate()
    assert easy.project==original
    assert 'Ton-kuvvet' in easy.simple.phase_inputs[0]['force']._force_label.text()
    edit(easy.simple.phase_inputs[0]['force'],'2')
    easy.simple.force_unit.setCurrentIndex(easy.simple.force_unit.findData('kN'));easy.recalculate()
    assert easy.project.phases[0].force==pytest.approx(19613.3)


def test_bad_force_does_not_partially_convert_other_rows(easy):
    first=easy.simple.phase_inputs[0]['force'];second=easy.simple.phase_inputs[1]['force']
    original=first.text();edit(second,'bad')
    easy.simple.force_unit.setCurrentIndex(easy.simple.force_unit.findData('tonf'))
    assert easy.simple.force_unit.currentData()=='kN' and first.text()==original and second.text()=='bad'


@pytest.mark.parametrize('text',['bad','0','-5','1e308'])
def test_bad_dimensions_mark_visible_field_and_disable_reports(easy,text):
    widget=easy.simple.inputs['cylinder.bore'];edit(widget,text);easy.recalculate()
    assert easy.result is None and widget.property('invalid')
    assert easy.simple.error_notice.isVisible() and not easy.simple.pdf_button.isEnabled()
    assert easy.simple.results.rowCount()==0


def test_typing_invalid_draft_then_switching_views_preserves_text(easy):
    widget=easy.simple.inputs['cylinder.bore'];edit(widget,'unfinished')
    easy.view_mode.setCurrentIndex(1)
    assert easy.input_stack.currentIndex()==0 and widget.text()=='unfinished'
    assert easy.view_mode.currentIndex()==0


def test_basic_cycle_is_reversible_and_does_not_revert_other_inputs(easy):
    original=easy.project.phases;easy.use_basic_cycle()
    assert len(easy.project.phases)==3 and easy.result.cycle['repeatable_geometry']
    edit(easy.simple.inputs['cylinder.bore'],'80');easy.recalculate();easy.undo_basic_cycle()
    assert easy.project.phases==original and easy.project.cylinders[0].bore==.08


def test_pump_recommendation_does_not_silently_raise_pressure_rating(easy):
    original=easy.project.pump;nominal=easy.result.cycle['displacement']['nominal']
    easy.use_pump_recommendation()
    assert easy.project.pump.displacement==nominal
    assert easy.project.pump.max_pressure==original.max_pressure


def test_complex_file_opens_in_detailed_mode_without_dropping_cylinders(easy,tmp_path):
    project=replace(Project(),cylinders=(Cylinder(),Cylinder(id='C2')))
    path=tmp_path/'complex.gwhyd';save(project,path);easy.load_path(path)
    assert easy.input_stack.currentIndex()==1 and easy.project==project
    easy.view_mode.setCurrentIndex(0)
    assert easy.simple.unsupported.isVisible() and not easy.simple.steps.isEnabled()
    assert easy.build_project().cylinders==project.cylinders


def test_simple_project_saves_identical_si_data(easy,tmp_path,monkeypatch):
    target=tmp_path/'simple.gwhyd';edit(easy.simple.phase_inputs[1]['force'],'40');easy.recalculate()
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    easy.save_project()
    assert load(target)==easy.project and load(target).phases[1].force==40000.


def test_simple_result_keeps_critical_warnings_visible_and_reports_work(easy,qtbot,tmp_path,monkeypatch):
    easy.simple.steps.setCurrentIndex(2)
    assert 'soğutma' in easy.simple.verdict.text()
    assert 'Önemli' in easy.simple.warnings.text() and easy.simple.results.rowCount()==6
    qtbot.wait(20)
    assert easy.simple.results.verticalScrollBar().maximum()==0
    target=tmp_path/'report.pdf';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    qtbot.mouseClick(easy.simple.pdf_button,Qt.LeftButton)
    qtbot.waitUntil(lambda:easy.pdf_job is None,timeout=10000)
    assert target.read_bytes().startswith(b'%PDF-')
