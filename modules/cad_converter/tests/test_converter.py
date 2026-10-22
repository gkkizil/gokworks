"""Mock COM integration verifies flow/state/file safety, not real CAD geometry."""

from dataclasses import replace
import math
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from modules.cad_converter import api
from modules.cad_converter.exporter import convert, inspect_configurations
from modules.cad_converter.formats import FORMATS
from modules.cad_converter.models import Options, Source
from modules.cad_converter.naming import safe_name
from modules.cad_converter.scanner import scan
from modules.cad_converter.validation import validate_output
from .fakes import App, FakeSession, Events, C, Component, content


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'interface', lambda obj, iid: obj)
    monkeypatch.setattr(api, 'out_int', lambda: SimpleNamespace(value=0))
    monkeypatch.setattr(api, 'null_dispatch', lambda: None)
    app = App(); model = app.add(tmp_path/'Part.SLDPRT', ('Default', 'Other', 'A/B', 'A:B'))
    return app, model, Options(str(tmp_path/'out')), Events()


def run(setup, *, sources=None, options=None, stop=None):
    app, model, base, events = setup
    convert(sources or [Source(model.path)], options or base, events, stop, session_factory=lambda: FakeSession(app))
    return events


@pytest.mark.parametrize('fmt', FORMATS, ids=lambda x: x.key)
def test_every_selected_format_has_its_own_folder_and_validated_file(setup, fmt):
    app, model, options, _ = setup
    before = dict(app.preferences)
    events = run(setup, options=replace(options, formats=(fmt.key,)))
    assert events.summary['succeeded'] == 1, events.rows
    assert events.summary['failed'] == 0
    target = Path(events.results[0]['output'])
    assert target.parent.name == fmt.folder and target.suffix == fmt.extension
    assert validate_output(target, fmt.key)
    assert app.preferences == before and model.active == 'Default' and model.SelectionManager.depth == 0
    assert not list(target.parent.glob('.gokworks-*'))
    assert Path(model.path).read_bytes() == b'source CAD fixture'


def test_one_part_all_eight_formats_in_one_batch_and_no_ap204(setup):
    app, model, options, _ = setup
    events = run(setup, options=replace(options, formats=tuple(f.key for f in FORMATS)))
    assert events.summary['succeeded'] == 8
    assert len({r['output'] for r in events.results}) == 8
    assert all(f.protocol != 204 for f in FORMATS)
    assert len(app.open_calls) == 1 and len(app.closed) == 1


def test_hundred_parts_recursive_scan_and_no_drawings_duplicates_or_lock_files(tmp_path):
    for i in range(100):
        p = tmp_path/('sub' if i%2 else '')/f'{i:03}.SLDPRT'
        p.parent.mkdir(exist_ok=True); p.write_text('cad')
    (tmp_path/'skip.SLDDRW').write_text('drawing'); (tmp_path/'~$lock.SLDPRT').write_text('lock')
    files, errors = scan([tmp_path, tmp_path/'sub', tmp_path/'000.SLDPRT'])
    assert len(files) == 100 and not errors
    assert len(scan([tmp_path], recursive=False)[0]) == 50
    assert not scan([tmp_path], existing=files)[0]
    alias = tmp_path/'alias.SLDPRT'
    try: alias.hardlink_to(tmp_path/'000.SLDPRT')
    except OSError: pytest.skip('Hardlinks unavailable')
    assert len(scan([tmp_path])[0]) == 100


def test_hundred_models_run_serially_without_reopening_or_changing_sources(setup, tmp_path):
    app, _, _, _ = setup
    models = [app.add(tmp_path/'batch'/f'Part-{i:03}.SLDPRT') for i in range(100)]
    events = run(setup, sources=[Source(m.path) for m in models])
    assert events.summary['succeeded'] == 100 and events.summary['processed'] == 100
    assert len(app.open_calls) == 100 and len(app.closed) == 100 and len(app.saves) == 100
    assert all(Path(m.path).read_bytes() == b'source CAD fixture' for m in models)


def test_duplicate_filenames_from_different_folders_are_not_overwritten(setup, tmp_path):
    app, model, options, _ = setup
    other = app.add(tmp_path/'another'/Path(model.path).name)
    events = run(setup, sources=[Source(model.path), Source(other.path)])
    assert events.summary['succeeded'] == 2
    assert len({r['output'] for r in events.results}) == 2
    assert all(Path(row['output']).is_file() for row in events.results)


@pytest.mark.parametrize('policy,selected,count', [('active', (), 1), ('all', (), 4), ('selected', ('Other', 'A/B', 'A:B'), 3)])
def test_configuration_outputs_are_distinct_and_original_is_restored(setup, policy, selected, count):
    app, model, options, _ = setup
    model.opened = True; app.ActiveDoc = model
    events = run(setup, options=replace(options, configurations=policy, selected_configurations=selected))
    assert events.summary['succeeded'] == count, events.rows
    assert len({r['output'] for r in events.results}) == count
    assert model.active == 'Default' and model.opened and not app.closed
    assert app.ActiveDoc is model and model.SelectionManager.depth == 0


def test_missing_selected_configuration_has_explicit_error_and_no_export(setup):
    _, _, options, _ = setup
    events = run(setup, options=replace(options, configurations='selected', selected_configurations=('missing',)))
    assert events.summary['failed'] == 1 and 'konfigürasyon' in events.results[0]['detail']
    assert not events.results[0]['output']


def test_multibody_part_uses_whole_model_with_selection_cleared(setup):
    app, model, _, _ = setup
    model.body_count = 4; model.selected = True
    events = run(setup)
    assert events.summary['succeeded'] == 1 and len(app.saves) == 1


def test_single_assembly_and_component_mode_deduplicate_file_configuration_pairs(setup, tmp_path):
    app, model, options, _ = setup
    assembly = app.add(tmp_path/'Top.SLDASM')
    child = app.add(tmp_path/'Child.SLDPRT', ('Default', 'Other'), opened=True)
    assembly.components = [Component(child), Component(child), Component(child, configuration='Other')]
    events = run(setup, sources=[Source(assembly.path)])
    assert events.summary['succeeded'] == 1 and len(app.saves) == 1
    app.saves.clear(); events.rows.clear()
    events = run(setup, sources=[Source(assembly.path)], options=replace(options, assembly_mode='components'))
    assert events.summary['succeeded'] == 2 and len(app.saves) == 2, events.rows
    assert {r['configuration'] for r in events.results} == {'Default', 'Other'}
    assert child.opened and 'Child.SLDPRT' not in app.closed


def test_components_report_suppressed_virtual_missing_and_export_resolvable_lightweight(setup, tmp_path):
    app, model, options, _ = setup
    assembly = app.add(tmp_path/'Top.SLDASM')
    child = app.add(tmp_path/'Lightweight.SLDPRT')
    assembly.components = [Component(child), Component(suppressed=True), Component(virtual=True), Component(path=str(tmp_path/'absent.SLDPRT'))]
    events = run(setup, sources=[Source(assembly.path)], options=replace(options, assembly_mode='components'))
    assert events.summary['succeeded'] == 1 and events.summary['skipped'] == 1 and events.summary['failed'] == 2
    assert child.path in app.open_calls


@pytest.mark.parametrize('include,expected', [(False, 1), (True, 2)])
def test_optional_subassembly_export(setup, tmp_path, include, expected):
    app, model, options, _ = setup
    assembly = app.add(tmp_path/'Top.SLDASM')
    sub = app.add(tmp_path/'Sub.SLDASM', opened=True)
    sub.components = [Component(model)]; model.opened = True
    assembly.components = [Component(sub), Component(model)]
    events = run(setup, sources=[Source(assembly.path)], options=replace(options, assembly_mode='components', include_subassemblies=include))
    assert events.summary['succeeded'] == expected, events.rows


@pytest.mark.parametrize('fault', ['missing_reference', 'unresolved'])
def test_incomplete_single_assembly_is_not_silently_exported(setup, tmp_path, fault):
    app, _, _, _ = setup
    assembly = app.add(tmp_path/'Top.SLDASM')
    if fault == 'missing_reference': assembly.dependencies = ['Absent', str(tmp_path/'absent.SLDPRT')]
    else: assembly.components = [Component(path=str(tmp_path/'unknown.SLDPRT'))]
    events = run(setup, sources=[Source(assembly.path)])
    assert events.summary['failed'] == 1 and not app.saves


def test_missing_source_and_invalid_destination_do_not_start_export(setup, tmp_path):
    app, model, options, _ = setup
    Path(model.path).unlink()
    events = run(setup)
    assert events.summary['failed'] == 1 and not app.saves
    file = tmp_path/'not-a-folder'; file.write_text('preserved')
    events.rows.clear()
    events = run(setup, options=replace(options, output=str(file)))
    assert events.summary['state'] == 'error' and file.read_text() == 'preserved'


def test_existing_output_skipped_by_default_then_atomically_replaced(setup):
    _, _, options, _ = setup
    events = run(setup); target = Path(events.results[0]['output']); target.write_bytes(b'old')
    events.rows.clear(); run(setup)
    assert events.summary['skipped'] == 1 and target.read_bytes() == b'old'
    events.rows.clear(); run(setup, options=replace(options, overwrite=True))
    assert events.summary['succeeded'] == 1 and target.read_bytes() != b'old'


def test_corrupt_export_never_replaces_existing_output_and_cleans_temporary(setup):
    app, _, options, _ = setup
    events = run(setup); target = Path(events.results[0]['output']); before = target.read_bytes()
    app.corrupt = True; events.rows.clear()
    run(setup, options=replace(options, overwrite=True))
    assert events.summary['failed'] == 1 and target.read_bytes() == before
    assert not list(target.parent.glob('.gokworks-*'))


def test_cancellation_after_save_discards_unpublished_output_and_stops_batch(setup):
    app, model, options, _ = setup
    stop = threading.Event(); before = dict(app.preferences)
    app.after_save = stop.set
    events = run(setup, options=replace(options, formats=('step203', 'xt')), stop=stop)
    assert events.summary['state'] == 'cancelled' and len(app.saves) == 1
    assert not list(Path(options.output).rglob('*.step')) and not list(Path(options.output).rglob('.gokworks-*'))
    assert app.preferences == before and model.SelectionManager.depth == 0


@pytest.mark.parametrize('fault', ['save', 'disconnect', 'mbd'])
def test_api_failures_and_licensing_are_not_success(setup, fault):
    app, model, options, _ = setup
    if fault == 'save': app.save_error = 16
    if fault == 'disconnect': app.disconnect = True
    if fault == 'mbd': app.mbd_error = C['swPublishStep242_MBDLicenseNotAvailable']
    events = run(setup, options=replace(options, formats=('step242',) if fault == 'mbd' else ('step203',)))
    assert events.summary['failed'] == 1 and events.summary['succeeded'] == 0
    assert not list(Path(options.output).rglob('.gokworks-*'))
    if fault == 'mbd': assert 'MBD lisansı' in events.results[0]['detail']


def test_save_warnings_remain_visible_with_raw_api_codes(setup):
    app, _, _, _ = setup
    app.save_warning = 2
    events = run(setup)
    assert events.summary['warned'] == 1 and events.results[0]['warnings'] == 2


def test_preopened_user_document_active_configuration_and_selection_stack_are_preserved(setup, tmp_path):
    app, model, options, _ = setup
    previous = app.add(tmp_path/'User.SLDPRT', opened=True); app.ActiveDoc = previous
    model.opened = True
    run(setup, options=replace(options, configurations='all'))
    assert previous.opened and model.opened and not app.closed and app.ActiveDoc is previous
    assert model.active == 'Default' and model.SelectionManager.depth == 0


def test_configuration_inspection_only_reads_and_restores_session(setup):
    app, model, options, events = setup
    inspect_configurations([Source(model.path)], events, session_factory=lambda: FakeSession(app))
    rows = [value for kind, value in events.rows if kind == 'cad_configurations']
    assert rows[0]['names'] == list(model.names) and not app.saves and len(app.closed) == 1


def test_custom_stl_units_deviation_and_angle_are_converted_to_metre_and_radian(setup):
    app, model, options, _ = setup
    observed = []
    app.after_save = lambda: observed.append(dict(app.preferences))
    before = dict(app.preferences)
    events = run(setup, options=replace(options, formats=('stl_binary',), stl_unit='inch', stl_quality='custom', deviation_mm=.05, angle_degrees=12))
    assert events.summary['succeeded'] == 1
    assert observed[0][C['swSTLDeviation']] == pytest.approx(.00005)
    assert observed[0][C['swSTLAngleTolerance']] == pytest.approx(math.radians(12))
    assert observed[0][C['swExportStlUnits']] == C['swINCHES']
    assert app.preferences == before


def test_settings_restoration_failure_aborts_batch_instead_of_claiming_success(setup, monkeypatch):
    app, _, options, _ = setup
    previous = app.preferences[C['swStepAP']]
    original = app.SetUserPreferenceIntegerValue
    monkeypatch.setattr(app, 'SetUserPreferenceIntegerValue', lambda key, val: False if key == C['swStepAP'] and val == previous else original(key, val))
    events = run(setup, options=replace(options, formats=('step203', 'xt')))
    assert events.summary['state'] == 'error' and 'geri yüklenemedi' in events.summary['error']
    assert events.summary['succeeded'] == 0 and len(app.saves) == 1


@pytest.mark.parametrize('raw', ['CON', 'PRN.txt', 'A/B:C*?', 'name. ', '', 'LPT1'])
def test_windows_names_are_safe(raw):
    value = safe_name(raw)
    assert value and all(char not in value for char in '<>:"/\\|?*') and not value.endswith(('.', ' '))


def test_no_cad_or_gui_dependency_for_scanner_models_or_validation_in_fresh_process():
    import subprocess, sys
    subprocess.run([sys.executable, '-c', "from modules.cad_converter.scanner import scan; from modules.cad_converter.validation import validate_output; import sys; assert not any(x in sys.modules for x in ('PySide6', 'pythoncom', 'win32com'))"], check=True, timeout=15)
