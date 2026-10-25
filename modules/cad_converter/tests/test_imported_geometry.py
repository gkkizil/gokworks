"""Real Automation return shapes and cached geometry of imported native parts."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from .test_converter import setup, run
from modules.cad_converter.models import Source
from .fakes import C, Component


@pytest.mark.parametrize('key', ['step203', 'step214', 'iges', 'stl_binary', 'stl_ascii'])
def test_void_toggle_setters_are_verified_by_readback_and_restore(setup, monkeypatch, key):
    app, model, options, _ = setup
    before = dict(app.preferences)
    def set_toggle(key, value):
        app.preferences[key] = value  # ISldWorks.SetUserPreferenceToggle returns void.
    monkeypatch.setattr(app, 'SetUserPreferenceToggle', set_toggle)
    events = run(setup, options=replace(options, formats=(key,)))
    assert events.summary['succeeded'] == 1, events.rows
    assert app.preferences == before and model.SelectionManager.depth == 0
    assert Path(events.results[0]['output']).is_file()


def test_void_setter_that_does_not_apply_setting_is_still_rejected(setup, monkeypatch):
    app, _, _, _ = setup
    app.preferences[C['swStepExportConfigurationData']] = True
    monkeypatch.setattr(app, 'SetUserPreferenceToggle', lambda key, value: None)
    events = run(setup)
    assert events.summary['failed'] == 1 and not app.saves
    assert 'doğrulanamadı' in events.results[0]['detail']
    assert events.summary['state'] == 'completed'  # Unchanged original state is safe.


def test_actual_toggle_restore_mismatch_still_stops_batch(setup, monkeypatch, tmp_path):
    app, model, _, _ = setup
    other = app.add(tmp_path/'Next.SLDPRT')
    app.preferences[C['swStepExportConfigurationData']] = True
    def no_restore(key, value):
        if value is False:
            app.preferences[key] = value
    monkeypatch.setattr(app, 'SetUserPreferenceToggle', no_restore)
    events = run(setup, sources=[Source(model.path), Source(other.path)])
    assert events.summary['state'] == 'error' and '403' in events.summary['error']
    assert len(app.saves) == 1 and not list(tmp_path.rglob('*.step'))
    assert other.path not in app.open_calls


def cached_bodies(model, kind=0, count=1):
    calls = []
    def bodies(requested, visible_only):
        calls.append((requested, visible_only))
        return tuple(NS(GetType=lambda: kind, GetFaceCount=lambda: 6)
                     for _ in range(count)) if requested == kind else ()
    model.GetBodies2 = bodies
    return calls


@pytest.mark.parametrize('suffix', ['.stp', '.STEP', '.iges', '.x_t'])
@pytest.mark.parametrize('body_type', [0, 1], ids=['solid', 'surface'])
def test_missing_import_source_exports_saved_brep_with_explicit_warning(setup, tmp_path, suffix, body_type):
    app, model, _, _ = setup
    model.dependencies = ['Imported', str(tmp_path/('Unavailable'+suffix))]
    calls = cached_bodies(model, body_type)
    before = Path(model.path).read_bytes()
    events = run(setup)
    assert events.summary['warned'] == 1 and events.summary['failed'] == 0, events.rows
    row = events.results[0]
    assert row['status'] == 'partial' and 'güncelliği doğrulanmadı' in row['detail']
    assert 'Unavailable'+suffix in row['detail'] and row['warnings'] == 0
    assert Path(row['output']).is_file() and Path(model.path).read_bytes() == before
    assert calls and all(visible is False for _, visible in calls)


@pytest.mark.parametrize('fault', ['empty', 'mesh', 'no_faces', 'api_error'])
def test_missing_import_without_verified_brep_is_not_exported(setup, tmp_path, fault):
    app, model, _, _ = setup
    model.dependencies = ['Imported', str(tmp_path/'Unavailable.stp')]
    if fault == 'api_error':
        def broken(*args): raise RuntimeError('geometry unavailable')
        model.GetBodies2 = broken
    elif fault == 'no_faces':
        model.GetBodies2 = lambda *args: (NS(GetType=lambda: 0, GetFaceCount=lambda: 0),)
    else:
        cached_bodies(model, kind=6 if fault == 'mesh' else 0, count=1 if fault == 'mesh' else 0)
    events = run(setup)
    assert events.summary['failed'] == 1 and not app.saves


@pytest.mark.parametrize('suffix', ['.sldprt', '.sldasm', '.unknown', ''])
def test_missing_native_or_unknown_references_are_not_relaxed(setup, tmp_path, suffix):
    app, model, _, _ = setup
    model.dependencies = ['Missing', str(tmp_path/('Unavailable'+suffix))]
    cached_bodies(model)
    assert run(setup).summary['failed'] == 1 and not app.saves


def test_mixed_missing_native_and_imported_refs_still_block_export(setup, tmp_path):
    app, model, _, _ = setup
    model.dependencies = ['Import', str(tmp_path/'Old.stp'), 'Native', str(tmp_path/'Missing.sldprt')]
    cached_bodies(model)
    assert run(setup).summary['failed'] == 1 and not app.saves


def test_single_assembly_never_ignores_missing_import_refs(setup, tmp_path):
    app, model, _, _ = setup
    assembly = app.add(tmp_path/'Assembly.SLDASM')
    assembly.dependencies = ['Import', str(tmp_path/'Missing.stp')]
    assembly.components = [Component(model)]
    assert run(setup, sources=[Source(assembly.path)]).summary['failed'] == 1 and not app.saves


def test_component_batch_continues_after_cached_import_warning(setup, tmp_path):
    app, model, options, _ = setup
    imported = app.add(tmp_path/'Bearing.SLDPRT')
    imported.dependencies = ['Import', str(tmp_path/'Old.stp')]
    cached_bodies(imported)
    assembly = app.add(tmp_path/'Assembly.SLDASM')
    assembly.components = [Component(imported), Component(model)]
    before = dict(app.preferences)
    events = run(setup, sources=[Source(assembly.path)], options=replace(options, assembly_mode='components'))
    assert events.summary['succeeded'] == 1 and events.summary['warned'] == 1, events.rows
    assert events.summary['state'] == 'completed' and app.preferences == before
