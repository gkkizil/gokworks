"""Offline orchestration tests. Test artifacts and the CAD adapter below are FAKE."""

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from threading import Event, get_ident

import pytest

from modules.cad_converter.api import ApiError, RestoreError
from modules.automatic_drawing import pipeline
from modules.automatic_drawing.models import ModelInfo, Options, Source, STAGES


class Sink:
    def __init__(self): self.events = []
    def put(self, event): self.events.append(event)


class FakeModel:
    def __init__(self, source): self.source = source; self.configuration = 'Default'
    def GetPathName(self): return self.source.path


class FakeSession:
    """No COM, geometry, SolidWorks or native CAD file generation occurs here."""
    revision = 'FAKE:offline-contract-test'

    def __init__(self, template, *, restore_failure=False):
        self.template = template
        self.models, self.released, self.inspections = {}, [], []
        self.configuration_entries = 0
        self.restore_failure = restore_failure
        self.owner = get_ident()
        self.exited = False
        self.app = self

    def GetUserPreferenceStringValue(self, key): return str(self.template)
    def c(self, key): return 0
    def assert_thread(self): assert self.owner == get_ident()
    def __enter__(self): return self
    def __exit__(self, *args): self.exited = True
    def source(self, source):
        self.models.setdefault(source.path, FakeModel(source))
        return self.models[source.path]
    def source_ready(self, model): pass
    def active_configuration(self, model): return model.configuration
    def memory_stamp(self, model): return getattr(model, 'update_stamp', 1)
    def release(self, path): self.released.append(path)
    def restore_before_publish(self, source): self.release(source.path)

    @contextmanager
    def configuration(self, model, name):
        previous = model.configuration
        model.configuration = name
        self.configuration_entries += 1
        try:
            yield
        finally:
            model.configuration = previous
            if self.restore_failure and self.configuration_entries == 2:
                raise RestoreError('simulated configuration restore failure')

    def inspect(self, model, source, stop=None):
        self.inspections.append(source)
        return ModelInfo(source, 'part', Path(source.path).stem, (100., 50., 10.), body_count=1)


class FakeNative:
    calls = []
    change_source = False
    fail_reopen = False
    cancel_at_save = False
    change_memory = False

    def __init__(self, session, info, options, result, stop):
        self.session, self.info, self.result, self.stop = session, info, result, stop
        self.options = options
        self.closed = False
        self.snapshots = [{'name': 'FAKE offline sheet'}]
    def create(self, template, plan):
        if Path(self.info.source.path).stem == 'bad':
            raise ApiError('simulated document creation failure')
    def setup(self, *args, **kwargs): pass
    def create_views(self, *args): pass
    def fit(self, *args, **kwargs): pass
    def import_dimensions(self, *args): pass
    def dimensions(self, *args): return []
    def geometry_dimensions(self, *args): pass
    def arrange_dimensions(self, *args): pass
    def center_marks(self, *args): pass
    def title_properties(self): pass
    def rebuild(self): pass
    def validate(self): return [], self.snapshots
    def close(self): self.closed = True

    def save(self, path, kind):
        if kind == 'slddrw':
            Path(path).write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+b'FAKE NOT A SOLIDWORKS DRAWING'*8)
        else:
            Path(path).write_bytes(b'%PDF-1.7\nFAKE PDF NOT RENDERABLE\n%%EOF\n')
        if self.cancel_at_save:
            self.stop.set()

    def verify_saved(self, path, snapshots):
        assert self.closed, 'Native handle must close before the reopen check'
        self.calls.append(('reopen', self.info.source.key))
        if self.fail_reopen:
            raise ApiError('simulated saved drawing with a broken model reference')
        if self.change_source:
            Path(self.info.source.path).write_bytes(b'externally modified source')
        if self.change_memory:
            self.session.models[self.info.source.path].update_stamp = 2
        return [], snapshots


@pytest.fixture
def setup(tmp_path, monkeypatch):
    template = tmp_path/'test.drwdot'; template.write_bytes(b'FAKE template')
    options = Options(template=str(template), output_dir=str(tmp_path/'out'), model_dimensions=False,
                      geometry_dimensions=False, center_marks=False, flat_pattern=False, bom=False)
    for name in ('change_source', 'fail_reopen', 'cancel_at_save', 'change_memory'):
        monkeypatch.setattr(FakeNative, name, False)
    monkeypatch.setattr(FakeNative, 'calls', [])
    return options, template


def source(tmp_path, name):
    path = tmp_path/(name+'.SLDPRT'); path.write_bytes(b'fake source, unchanged by unit adapter')
    return Source(str(path), 'Default')


def test_twenty_documents_isolate_one_failure_keep_sources_and_finish_actual_phase_ledger(tmp_path, setup):
    options, template = setup
    sources = [source(tmp_path, 'bad' if i == 8 else f'part-{i:02d}') for i in range(20)]
    original = {s.path: Path(s.path).read_bytes() for s in sources}
    sink, session = Sink(), FakeSession(template)
    results = pipeline.generate(sources, options, sink, Event(), session_factory=lambda: session,
                                native_factory=FakeNative)
    assert len(results) == 20
    assert sum(r.status == 'PASS' for r in results) == 19
    assert sum(r.status == 'FAIL' for r in results) == 1
    assert session.exited and len(FakeNative.calls) == 19
    for result in results:
        if result.status == 'PASS':
            assert result.completed_stages == list(STAGES)
            report = json.loads(Path(result.outputs['report']).read_text(encoding='utf-8'))
            assert report['completed_stages'] == list(STAGES)
            assert report['api_revision'].startswith('FAKE')
        else:
            assert not result.outputs and result.stage == STAGES[6]
    assert {s.path: Path(s.path).read_bytes() for s in sources} == original
    assert all(model.configuration == 'Default' for model in session.models.values())
    assert sink.events[-1][0] == 'drawing_done'
    assert not list((tmp_path/'out').glob('.gokworks*'))


def test_failed_native_reopen_prevents_publication_even_with_existing_staged_files(tmp_path, setup, monkeypatch):
    options, template = setup
    monkeypatch.setattr(FakeNative, 'fail_reopen', True)
    result = pipeline.generate([source(tmp_path, 'part')], options, Sink(), Event(),
        session_factory=lambda: FakeSession(template), native_factory=FakeNative)[0]
    assert result.status == 'FAIL' and not result.outputs and result.stage == STAGES[16]
    assert list((tmp_path/'out').iterdir()) == []


def test_active_document_restore_failure_prevents_publication(tmp_path, setup, monkeypatch):
    options, template = setup
    session = FakeSession(template)

    def failed_restore(_):
        raise RestoreError('Önceki aktif belge geri getirilemedi.')

    monkeypatch.setattr(session, 'restore_before_publish', failed_restore)
    results = pipeline.generate([source(tmp_path, 'a'), source(tmp_path, 'b')], options, Sink(), Event(),
                                session_factory=lambda: session, native_factory=FakeNative)
    assert len(results) == 1 and results[0].status == 'FAIL' and results[0].stage == STAGES[17]
    assert not results[0].outputs and list((tmp_path/'out').iterdir()) == []


def test_external_model_change_invalidates_previously_generated_drawing(tmp_path, setup, monkeypatch):
    options, template = setup
    monkeypatch.setattr(FakeNative, 'change_source', True)
    result = pipeline.generate([source(tmp_path, 'part')], options, Sink(), Event(),
        session_factory=lambda: FakeSession(template), native_factory=FakeNative)[0]
    assert result.status == 'FAIL' and 'Kaynak dosya' in result.findings[-1].text
    assert not result.outputs and list((tmp_path/'out').iterdir()) == []


def test_cancellation_removes_incomplete_package_and_does_not_run_next_document(tmp_path, setup, monkeypatch):
    options, template = setup
    monkeypatch.setattr(FakeNative, 'cancel_at_save', True)
    session, sink = FakeSession(template), Sink()
    results = pipeline.generate([source(tmp_path, 'a'), source(tmp_path, 'b')], options, sink, Event(),
        session_factory=lambda: session, native_factory=FakeNative)
    assert len(results) == 1 and results[0].status == 'CANCELLED'
    assert len(session.inspections) == 1
    assert list((tmp_path/'out').iterdir()) == []


def test_unsaved_model_change_invalidates_output_even_when_file_timestamp_did_not_change(tmp_path, setup, monkeypatch):
    options, template = setup
    item = source(tmp_path, 'part'); original = Path(item.path).read_bytes()
    monkeypatch.setattr(FakeNative, 'change_memory', True)
    result = pipeline.generate([item], options, Sink(), Event(),
        session_factory=lambda: FakeSession(template), native_factory=FakeNative)[0]
    assert result.status == 'FAIL' and not result.outputs
    assert any('bellekteki geometrisi' in f.text for f in result.findings)
    assert Path(item.path).read_bytes() == original


def test_restore_failure_stops_the_entire_batch_and_never_commits_pass_report(tmp_path, setup):
    options, template = setup
    session = FakeSession(template, restore_failure=True)
    results = pipeline.generate([source(tmp_path, 'a'), source(tmp_path, 'b')], options, Sink(), Event(),
        session_factory=lambda: session, native_factory=FakeNative)
    assert len(results) == 1 and results[0].status == 'FAIL'
    assert results[0].measurements['stop_batch'] is True
    assert list((tmp_path/'out').iterdir()) == []


def test_file_configuration_identity_prevents_twenty_repeated_part_drawings(tmp_path, setup):
    options, template = setup
    part = source(tmp_path, 'screw')
    session = FakeSession(template)
    results = pipeline.generate([part]*20+[replace(part, configuration='Variant')], options, Sink(), Event(),
        session_factory=lambda: session, native_factory=FakeNative)
    assert len(results) == 2 and len(session.inspections) == 2
    assert {r.source.configuration for r in results} == {'Default', 'Variant'}
    assert all(model.configuration == 'Default' for model in session.models.values())


def test_missing_session_has_per_file_failures_instead_of_fake_success(tmp_path, setup):
    options, template = setup
    def missing():
        raise RuntimeError('SolidWorks is unavailable in this offline test')
    sink = Sink()
    results = pipeline.generate([source(tmp_path, 'part')], options, sink, Event(), session_factory=missing)
    assert len(results) == 1 and results[0].status == 'FAIL'
    assert not results[0].outputs
    assert 'SolidWorks is unavailable' in results[0].findings[0].text


def test_failed_report_write_does_not_falsely_complete_final_stage(tmp_path, setup, monkeypatch):
    options, template = setup
    def fail_report(self, result):
        raise OSError('simulated report disk full')
    monkeypatch.setattr(pipeline.OutputTransaction, 'write_report', fail_report)
    result = pipeline.generate([source(tmp_path, 'part')], options, Sink(), Event(),
        session_factory=lambda: FakeSession(template), native_factory=FakeNative)[0]
    assert result.status == 'FAIL' and not result.outputs
    assert result.stage == STAGES[17] and STAGES[17] not in result.completed_stages
    assert list((tmp_path/'out').iterdir()) == []


def test_folder_scan_handles_uppercase_extensions_skips_solidworks_lock_files_and_can_cancel(tmp_path):
    source(tmp_path, 'Part')
    (tmp_path/'ASM.SLDASM').write_bytes(b'fake assembly')
    (tmp_path/'~$Part.SLDPRT').write_bytes(b'lock')
    (tmp_path/'not.step').write_bytes(b'not a native source')
    child = tmp_path/'child'; child.mkdir(); source(child, 'Sub')
    assert len(pipeline.scan_folder(tmp_path)) == 3
    assert len(pipeline.scan_folder(tmp_path, recursive=False)) == 2
    stopped = Event(); stopped.set()
    with pytest.raises(pipeline.Cancelled):
        pipeline.scan_folder(tmp_path, stop=stopped)
