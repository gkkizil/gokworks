"""Novice inputs remain physical, lossless and backed by the existing core."""
from dataclasses import asdict, replace
import math
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit.core.models import Cylinder, Project
from modules.hydraulic_unit.core.service import calculate_project
from modules.hydraulic_unit.practical import PracticalInputs, practical_project, practical_values
from modules.hydraulic_unit.serialization import load, save
from modules.hydraulic_unit.ui import HydraulicPage


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path/'settings.json'), jobs=JobManager(), appearance='dark')
    page = HydraulicPage(context); qtbot.addWidget(page); page.resize(1366, 850); page.show(); qtbot.wait(10)
    yield page
    page.cancel_pdf(); page.settings.flush()


def edit(page, **values):
    for key, value in values.items():
        w = page.quick.inputs[key]; w.setText(str(value)); w.textEdited.emit(str(value))


def test_new_default_is_one_screen_without_replacing_the_original_project(page):
    assert page.view_mode.currentText() == 'Pratik hesap' and page.input_stack.currentIndex() == 2
    assert page.project == Project()
    assert page.quick.allowed and not page.quick.ready
    assert not page.summary_panel.isVisible() and not page.guide_widget.isVisible()
    assert not page.quick.pdf_button.isEnabled() and not page.save_button.isEnabled()
    assert all(not c.isVisible() for c in page.quick.cards.values())
    assert page.settings.get('hydraulic_unit_project') is None


def test_an_uncalculated_form_cannot_save_or_export_the_hidden_example(page,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('uncalculated draft reached a file dialog')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',forbidden)
    page.save_project();page.export_pdf();page.export('excel');page.export('json')
    assert page.quick.ready is False


def test_form_completes_a_closed_cycle_and_matches_analytic_flow_and_core(page):
    edit(page, bore='80', rod='45', stroke='400', force='5', extend_time='4', return_time='4', hold_time='2')
    page.quick.calculate_button.click()
    p, r = page.project, page.result
    assert page.quick.ready and r.input_fingerprint == calculate_project(p).input_fingerprint
    assert [phase.kind for phase in p.phases] == ['extend', 'hold', 'retract']
    assert [phase.force for phase in p.phases] == pytest.approx([49033.25, 49033.25, 0])
    assert p.cylinders[0].stroke == .4 and r.cycle['duration'] == 10
    assert r.cycle['max_flow'] == pytest.approx(math.pi * .08**2 / 4 * .4 / 4)
    assert r.cycle['phases'][-1].end_position == 0 and r.cycle['repeatable_geometry']
    assert r.cycle['demand_met'] and p.pump.displacement == r.cycle['displacement']['nominal']
    assert page.quick.pdf_button.isEnabled() and all(c.isVisible() for c in page.quick.cards.values())
    assert any(i.severity == 'critical' for i in r.issues)  # Cooling remains visible and does not stop a scenario report.


def test_automatic_pump_choice_changes_only_displacement(page):
    original = page.project
    edit(page, bore=80, stroke=400, extend_time=4)
    page.quick.calculate()
    assert replace(page.project.pump, displacement=original.pump.displacement) == original.pump
    for name in ('pipe','oil','thermal','accumulator','relief_factor','selected_motor'):
        assert getattr(page.project,name) == getattr(original,name)
    page.open_detailed()
    assert page.cylinder_table.item(0,1).text() == '80'
    page.view_mode.setCurrentIndex(2)
    assert page.project.cylinders[0].bore == .08 and page.quick.ready


def test_existing_pump_is_preserved_when_automatic_sizing_is_off(page):
    original = page.project.pump; page.quick.auto_pump.setChecked(False)
    edit(page, bore=80, stroke=400, extend_time=1)
    page.quick.calculate()
    assert page.project.pump == original and not page.result.cycle['demand_met']
    assert 'kritik' in page.quick.state.text()


@pytest.mark.parametrize('key,value', [('bore',''),('bore','nan'),('bore','1e308'),('rod','63'),
    ('stroke','-2'),('force','-1'),('force','1e308'),('extend_time','0'),('return_time','inf'),('hold_time','-1'),('return_force','-1')])
def test_invalid_inputs_preserve_the_project_and_block_reports(page,key,value):
    original = page.project; edit(page, **{key:value}); page.quick.calculate()
    assert page.result is None and page.project == original
    assert page.quick.error.isVisible() and not page.quick.pdf_button.isEnabled()
    assert not page.save_button.isEnabled() and not page.quick.ready
    assert all(not c.isVisible() for c in page.quick.cards.values())
    if key == 'return_force':assert page.quick.return_section.is_expanded()


def test_edits_wait_for_calculate_and_never_leave_old_results_visible(page,qtbot):
    page.quick.calculate(); original = page.project
    edit(page, stroke='450')
    qtbot.wait(450)
    assert page.result is None and page.project == original and not page.timer.isActive()
    assert not page.quick.pdf_button.isEnabled() and not page.save_button.isEnabled()
    assert all(not c.isVisible() for c in page.quick.cards.values())
    assert '450' == page.quick.inputs['stroke'].text()


def test_invalid_draft_cannot_be_lost_by_switching_view(page):
    edit(page,bore='unfinished'); page.open_detailed()
    assert page.input_stack.currentIndex() == 2 and page.view_mode.currentIndex() == 2
    assert page.quick.inputs['bore'].text() == 'unfinished'


def test_unit_conversion_preserves_a_pending_force_and_is_atomic(page):
    q=page.quick; edit(page,force='2,5',return_force='0,5')
    q.force_unit.setCurrentIndex(q.force_unit.findData('kN'))
    q.calculate()
    assert [p.force for p in page.project.phases] == pytest.approx([24516.625, 4903.325])
    first=q.inputs['force'].text(); edit(page,return_force='bad')
    q.force_unit.setCurrentIndex(q.force_unit.findData('tonf'))
    assert q.force_unit.currentData() == 'kN' and q.inputs['force'].text() == first
    assert q.inputs['return_force'].text() == 'bad' and q.return_section.is_expanded()


def test_complex_loaded_plan_is_never_silently_flattened(page,tmp_path):
    original = replace(Project(),name='Özel plan')
    path=tmp_path/'custom.gwhyd';save(original,path);page.load_path(path)
    assert page.project == original and not page.quick.allowed
    assert page.quick.existing.isVisible() and not page.quick.calculate_button.isEnabled()
    page.quick.new_button.click()
    assert page.project == original and page.result is None
    page.quick.calculate_button.click()
    assert len(page.project.phases) == 2 and page.project.name == original.name
    assert page.project.thermal == original.thermal


def test_multiple_cylinders_cannot_be_replaced_by_a_single_cylinder_form(page,tmp_path):
    project=replace(Project(),cylinders=(Cylinder(),Cylinder(id='C2')))
    path=tmp_path/'multi.gwhyd';save(project,path);page.load_path(path)
    page.view_mode.setCurrentIndex(2)
    assert page.project == project and not page.quick.allowed and not page.quick.new_button.isVisible()
    assert page.build_project() == project


def test_existing_simple_file_keeps_advanced_settings_and_exact_force_on_roundtrip(page,tmp_path):
    base=Project();base=replace(base,pump=replace(base.pump,max_pressure=230e5),selected_motor=11000.)
    project=practical_project(base,PracticalInputs(force=1.2345678901234,hold_time=1.1))
    path=tmp_path/'simple.gwhyd';save(project,path);page.load_path(path)
    assert page.quick.allowed and page.quick.ready and not page.quick.auto_pump.isChecked()
    page.open_detailed();page.view_mode.setCurrentIndex(2)
    assert asdict(page.project) == asdict(project)
    edit(page,hold_time='2');page.quick.calculate()
    assert page.project.phases[0].force == project.phases[0].force
    assert page.project.pump == project.pump and page.project.selected_motor == project.selected_motor


def test_practical_project_save_and_pdf_use_the_calculated_inputs(page,tmp_path,monkeypatch,qtbot):
    edit(page,stroke='400',hold_time='2');page.quick.calculate()
    path=tmp_path/'saved.gwhyd';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    page.save_project();assert load(path) == page.project
    pdf=tmp_path/'simple.pdf';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(pdf),''))
    page.quick.pdf_button.click();qtbot.waitUntil(lambda:page.pdf_job is None,timeout=20000)
    assert pdf.read_bytes().startswith(b'%PDF-')


def test_novice_completes_the_small_screen_flow_using_visible_questions(page,qtbot):
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtWidgets import QLabel
    page.resize(790,640)
    for title,value in [('Silindirin iç çapı','80'),('Parlak milin çapı','45'),('Gideceği yol (strok)','400'),
                        ('İleri ne kadar kuvvet uygulasın?','5'),('İleri kaç saniyede gitsin?','4'),
                        ('Geri kaç saniyede dönsün?','4'),('Uçta kaç saniye beklesin?','0')]:
        heading=next(l for l in page.quick.findChildren(QLabel) if l.text()==title and l.buddy())
        field=heading.buddy();page.quick.workspace.ensureWidgetVisible(field);qtbot.wait(5)
        qtbot.mouseClick(field,Qt.LeftButton);field.selectAll();qtbot.keyClicks(field,value)
    qtbot.mouseClick(page.quick.calculate_button,Qt.LeftButton)
    qtbot.wait(30)
    assert page.quick.ready and page.result.cycle['demand_met']
    assert page.project.phases[0].force == 49033.25 and len(page.project.phases) == 2
    assert page.result.cycle['repeatable_geometry']
    assert page.quick.workspace.verticalScrollBar().value() > 0
    assert 0 <= page.quick.state.mapTo(page.quick.workspace.viewport(),QPoint()).y() < 80


@pytest.mark.parametrize('width',[790,1130,1690])
def test_form_and_result_need_no_horizontal_scroll(page,qtbot,width):
    page.resize(width,700);qtbot.wait(40)
    assert page.width() == width and page.quick.workspace.horizontalScrollBar().maximum() == 0
    control=page.quick.calculate_button
    assert page.rect().contains(control.mapTo(page,control.rect().bottomRight()))
    page.quick.calculate();qtbot.wait(40)
    assert page.quick.workspace.horizontalScrollBar().maximum() == 0


def test_quick_adapter_roundtrip_preserves_full_precision_and_advanced_cylinder_fields():
    base=replace(Project(),cylinders=(replace(Cylinder(),efficiency=.89,effective_length=1.02),))
    values=PracticalInputs(bore=80,rod=45,stroke=456.789,force=2.345678901234,hold_time=3.21)
    project=practical_project(base,values)
    restored=practical_values(project)
    assert restored == values
    assert project.cylinders[0].efficiency == .89 and project.cylinders[0].effective_length == 1.02
    assert project.pump == base.pump and project.thermal == base.thermal


def test_editing_only_time_cannot_round_unedited_native_dimensions_or_forces(page,tmp_path):
    p=practical_project(Project(),PracticalInputs(hold_time=1))
    force=123.45678901234567
    cylinder=replace(p.cylinders[0],bore=.06312345678912345,rod=.03612345678912345,stroke=.30012345678912345)
    p=replace(p,cylinders=(cylinder,),phases=tuple(replace(f,stroke=cylinder.stroke,
        force=force if f.kind!='retract' else 0.) for f in p.phases))
    path=tmp_path/'precision.gwhyd';save(p,path);page.load_path(path)
    edit(page,hold_time='2');page.quick.calculate()
    assert page.project.cylinders == p.cylinders
    assert page.project.phases[0].force == force and page.project.phases[1].force == force


def test_legacy_easy_preference_migrates_once_and_deliberate_choice_is_retained(qtbot,tmp_path):
    settings=SettingsStore(tmp_path/'preferences.json');settings.set('hydraulic_view_mode',0)
    context=SimpleNamespace(settings=settings,jobs=JobManager(),appearance='dark')
    first=HydraulicPage(context);qtbot.addWidget(first)
    assert first.view_mode.currentIndex() == 2
    assert settings.get('hydraulic_view_mode') == 2
    first.view_mode.setCurrentIndex(0)
    second=HydraulicPage(context);qtbot.addWidget(second)
    assert second.view_mode.currentIndex() == 0 and second.project == first.project


def test_detailed_preference_and_loaded_special_cycle_are_kept(qtbot,tmp_path):
    from modules.hydraulic_unit.serialization import dumps
    settings=SettingsStore(tmp_path/'detailed.json');settings.set('hydraulic_view_mode',1)
    settings.set('hydraulic_unit_project',dumps(Project()))
    context=SimpleNamespace(settings=settings,jobs=JobManager(),appearance='dark')
    page=HydraulicPage(context);qtbot.addWidget(page)
    assert page.view_mode.currentIndex() == 1 and page.project == Project()
    page.view_mode.setCurrentIndex(2)
    assert not page.quick.allowed and page.project == Project()
