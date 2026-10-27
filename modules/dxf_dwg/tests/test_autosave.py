"""Save All without UI prompts; CAD calls are explicit test doubles."""

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from support.solidworks import FakePart, FakeAssembly, FakeApp, FakeComponent, com_stubs
from modules.dxf_dwg import exporter as ex


@pytest.fixture
def case(tmp_path, monkeypatch):
    com, client = com_stubs('dxf', dynamic=True)
    monkeypatch.setattr(ex, 'pythoncom', com)
    monkeypatch.setattr(ex, 'win32com', NS(client=client))
    part = FakePart(tmp_path/'part.SLDPRT')
    assembly = FakeAssembly(tmp_path/'root.SLDASM', [FakeComponent(part.path)])
    for model in (part, assembly):
        Path(model.path).write_bytes(b'native fixture')
        model.dirty = False
    app = FakeApp(part, previous=assembly)
    calls = []
    def save(model):
        def operation(options, errors, warnings):
            calls.append((model.path, options))
            model.dirty = False
            if model is part:
                assembly.dirty = True  # Documented parent dirty propagation.
            Path(model.path).write_bytes(b'saved native fixture')
            return True
        return operation
    for model in (part, assembly):
        model.Save3 = save(model)
    return app, part, assembly, calls


def test_all_modified_documents_and_late_dirtied_parent_saved_silently(case):
    app, part, assembly, calls = case
    part.dirty = True
    saved, warnings = ex.save_modified_documents(app)
    assert saved == [part.path, assembly.path]
    assert [options for _, options in calls] == [5, 5]
    assert not part.dirty and not assembly.dirty and not warnings
    assert app.ActiveDoc is assembly and not app.closed


def test_clean_documents_are_not_written(case):
    app, _, _, calls = case
    assert ex.save_modified_documents(app) == ([], []) and not calls


@pytest.mark.parametrize('mode', ['readonly', 'unnamed', 'foreign'])
def test_preflight_rejects_unsavable_files_before_writing_any_document(case, mode):
    app, part, assembly, calls = case
    part.dirty = assembly.dirty = True
    if mode == 'readonly':
        part.readonly = True
    else:
        part.path = '' if mode == 'unnamed' else str(Path(part.path).with_suffix('.stp'))
    with pytest.raises(ex.SaveDocumentsError):
        ex.save_modified_documents(app)
    assert not calls and not app.closed


@pytest.mark.parametrize('mode', ['false', 'error', 'tuple_error', 'dirty'])
def test_failed_save_never_silently_succeeds(case, mode):
    app, part, _, calls = case
    part.dirty = True
    def failed(options, errors, warnings):
        if mode == 'error': errors.value = 4
        if mode == 'tuple_error': return True, 4, 0
        return mode != 'false'
    part.Save3 = failed
    with pytest.raises(ex.SaveDocumentsError):
        ex.save_modified_documents(app)
    assert part.dirty and not app.closed


def test_save_warning_is_reported(case):
    app, part, _, _ = case
    part.dirty = True
    def warning(options, errors, warnings):
        part.dirty = False; warnings.value = 2
        return True
    part.Save3 = warning
    saved, warnings = ex.save_modified_documents(app)
    assert saved == [part.path] and part.path in warnings[0] and '2' in warnings[0]


def test_production_export_saves_after_native_export_and_refreshes_provenance(case, tmp_path):
    app, part, assembly, calls = case
    part.on_export = lambda path: setattr(part, 'dirty', True)
    metadata = {}
    status, detail = ex.export_one_part(app, part.path, [tmp_path/'part.dxf'],
                                      save_modified=True, output_identity=metadata)
    assert status == 'success', detail
    assert calls == [(part.path, 5), (assembly.path, 5)]
    stat = Path(part.path).stat()
    assert metadata['source_stamp'] == (stat.st_size, stat.st_mtime_ns)
    assert app.ActiveDoc is assembly


def test_default_preview_export_never_saves_sources(case, tmp_path):
    app, part, _, calls = case
    part.on_export = lambda path: setattr(part, 'dirty', True)
    status, detail = ex.export_one_part(app, part.path, [tmp_path/'preview.dxf'])
    assert status == 'success', detail
    assert part.dirty and not calls


def test_cleanup_save_error_keeps_owned_document_open_and_reports_partial_output(case, tmp_path):
    app, part, assembly, _ = case
    app.existing = False
    part.on_export = lambda path: setattr(part, 'dirty', True)
    part.Save3 = lambda *args: False
    metadata = {}
    target = tmp_path/'part.dxf'
    status, detail = ex.export_one_part(app, part.path, [target], save_modified=True, output_identity=metadata)
    assert status == 'partial' and target.is_file()
    assert metadata['native_save_error'] and 'kapatılmadı' in detail
    assert not app.closed and app.ActiveDoc is part


def test_stop_during_native_export_discards_temp_and_does_not_export_next_format(case, tmp_path):
    import threading
    app, part, _, _ = case
    stop = threading.Event()
    part.on_export = lambda path: stop.set()
    targets = [tmp_path/'cancel.dxf', tmp_path/'cancel.dwg']
    status, detail = ex.export_one_part(app, part.path, targets, stop_event=stop)
    assert status == 'skipped' and 'Durduruldu' in detail
    assert len(part.calls) == 1
    assert not any(p.exists() for p in targets)
    assert not list(tmp_path.glob('.gokworks-*'))


def test_configuration_is_restored_between_formats_and_before_source_save(case, tmp_path):
    app, part, _, calls = case
    observed = []
    def export(path):
        observed.append(part.ConfigurationManager.ActiveConfiguration.Name)
        part.ConfigurationManager.ActiveConfiguration.Name = 'Flat'
        part.dirty = True
    def restore(name):
        part.ConfigurationManager.ActiveConfiguration.Name = name
        return True
    save = part.Save3
    def save_original(*args):
        assert part.ConfigurationManager.ActiveConfiguration.Name == 'Default'
        return save(*args)
    part.on_export, part.ShowConfiguration2, part.Save3 = export, restore, save_original
    status, detail = ex.export_one_part(app, part.path, [tmp_path/'a.dxf', tmp_path/'a.dwg'], save_modified=True)
    assert status == 'success', detail
    assert observed == ['Default', 'Default'] and calls


def test_failed_configuration_restore_never_saves_or_closes_source(case, tmp_path):
    app, part, _, calls = case
    def export(path):
        part.ConfigurationManager.ActiveConfiguration.Name = 'Flat'
        part.dirty = True
    part.on_export = export
    part.ShowConfiguration2 = lambda name: False
    with pytest.raises(ex.SourceRestoreError):
        ex.export_one_part(app, part.path, [tmp_path/'a.dxf'], save_modified=True)
    assert part.dirty and not calls and not app.closed
    assert not (tmp_path/'a.dxf').exists()


@pytest.mark.parametrize('mode', ['load_error', 'invalid_bodies'])
def test_newly_opened_unverified_model_is_not_saved_in_cleanup(case, tmp_path, mode):
    app, part, _, calls = case
    app.existing = False
    opened = app.OpenDoc6
    def open_dirty(*args):
        model = opened(*args)
        model.dirty = True  # Older-version/load side effect; not a verified model.
        return model
    app.OpenDoc6 = open_dirty
    if mode == 'load_error':
        app.open_error = 64
    else:
        part.bodies *= 2
    original = Path(part.path).read_bytes()
    status, detail = ex.export_one_part(app, part.path, [tmp_path/'a.dxf'], save_modified=True)
    assert status == 'error', detail
    assert not calls and Path(part.path).read_bytes() == original
