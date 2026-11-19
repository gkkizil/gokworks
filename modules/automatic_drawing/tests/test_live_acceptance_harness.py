"""The REAL-SolidWorks acceptance harness itself (no CAD verdict is produced here).

These tests only check that the harness reports missing fixtures as "çalıştırılmadı"
and that it fails a scenario when the user's source folder changes. The fake
``generate`` below is a harness double, not a SolidWorks result.
"""
import os
from types import SimpleNamespace

import pytest

from modules.automatic_drawing import live_acceptance as acceptance


def test_eight_named_scenarios_cover_the_requested_cases():
    assert [s.key for s in acceptance.SCENARIOS] == [
        'stepped_shaft', 'holed_plate', 'single_body_sheet', 'multibody_sheet', 'assembly_configurations',
        'assembly_suppressed_component', 'missing_reference', 'company_templates']
    assert len({s.env for s in acceptance.SCENARIOS}) == 8


def test_without_solidworks_or_fixtures_every_scenario_is_reported_not_run(tmp_path):
    called = []
    report = acceptance.run(tmp_path, environ={}, generate=lambda *a: called.append(a))
    assert not called
    assert {row['status'] for row in report['scenarios']} == {acceptance.NOT_RUN}
    assert report['summary'] == {acceptance.PASSED: 0, acceptance.FAILED: 0, acceptance.NOT_RUN: 8}
    assert all(row['reason'] for row in report['scenarios'])


def test_unavailable_session_is_not_run_not_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, 'missing_requirements', lambda scenario, environ=None: [])
    source = tmp_path/'fixture'/'mil.SLDPRT'; source.parent.mkdir(); source.write_bytes(b'model')
    environ = {'GOKWORKS_LIVE_SHAFT': str(source), acceptance.TEMPLATE_ENV: str(tmp_path/'a.drwdot')}
    def no_session(*args):
        raise RuntimeError('Otomatik Teknik Resim için Windows, pywin32 ve açık bir SolidWorks oturumu gerekli.')
    row = acceptance.run_scenario(acceptance.SCENARIOS[0], tmp_path/'out', environ, generate=no_session)
    assert row['status'] == acceptance.NOT_RUN and 'SolidWorks' in row['reason']


def test_a_changed_source_folder_fails_the_scenario_whatever_the_drawing_said(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, 'missing_requirements', lambda scenario, environ=None: [])
    source = tmp_path/'fixture'/'mil.SLDPRT'; source.parent.mkdir(); source.write_bytes(b'model')
    environ = {'GOKWORKS_LIVE_SHAFT': str(source), acceptance.TEMPLATE_ENV: str(tmp_path/'a.drwdot')}
    def saves_the_source(sources, options, events, stop):
        source.write_bytes(b'saved by mistake')
        return [SimpleNamespace(status='FAIL', outputs={}, findings=[], analysis=None, sheets=[], source=sources[0],
                                api_revision='harness')]
    row = acceptance.run_scenario(acceptance.SCENARIOS[0], tmp_path/'out', environ, generate=saves_the_source)
    assert row['status'] == acceptance.FAILED
    assert any('kaynak klasörde dosya değişti' in p for p in row['problems'])


def test_missing_reference_scenario_requires_a_refusal_and_no_published_drawing(tmp_path):
    scenario = next(s for s in acceptance.SCENARIOS if s.key == 'missing_reference')
    finding = SimpleNamespace(severity='FAIL', code='tree', text='Eksik bileşen')
    refused = SimpleNamespace(status='FAIL', outputs={}, findings=[finding])
    assert acceptance.check(scenario, refused, {}) == []
    accepted = SimpleNamespace(status='PASS', outputs={}, findings=[])
    assert acceptance.check(scenario, accepted, {})


@pytest.mark.parametrize('rows,ok', [([{'quantity': 2}], True), ([], False)])
def test_assembly_bom_is_judged_from_the_recorded_native_bom_rows(tmp_path, rows, ok):
    # The BOM sheet's view role is 'main'; a 'bom' role never exists in result.sheets.
    pdf = tmp_path/'a.pdf'; pdf.write_bytes(b'%PDF-1.7')
    slddrw = tmp_path/'a.slddrw'; slddrw.write_bytes(b'x')
    scenario = next(s for s in acceptance.SCENARIOS if s.key == 'assembly_suppressed_component')
    root = SimpleNamespace(state='', children=[SimpleNamespace(state='suppressed', children=[])])
    result = SimpleNamespace(status='WARNING', outputs={'pdf': str(pdf), 'slddrw': str(slddrw)}, findings=[],
                             analysis=SimpleNamespace(kind='assembly', tree=root),
                             sheets=[{'expected': ['main']}], measurements={'bom': {'rows': rows}})
    assert ('BOM tablosu yok' not in acceptance.check(scenario, result, {})) is ok


@pytest.mark.skipif(os.name == 'nt', reason='Linux/macOS harness check only')
def test_non_windows_is_always_a_missing_requirement():
    assert 'Windows değil' in acceptance.missing_requirements(acceptance.SCENARIOS[0], {})
