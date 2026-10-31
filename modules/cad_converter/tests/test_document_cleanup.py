"""Document-window lifetime across all formats; COM doubles, not live CAD."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from modules.cad_converter import api
from modules.cad_converter.formats import FORMATS
from modules.cad_converter.models import Source
from .fakes import Component, FakeSession
from .test_converter import setup, run  # noqa: F401


@pytest.mark.parametrize('fmt', FORMATS, ids=lambda fmt: fmt.key)
def test_hidden_assembly_reference_loses_only_the_export_window_in_every_format(setup, tmp_path, fmt):
    app, model, options, _ = setup
    assembly = app.add(tmp_path/'User assembly.SLDASM', opened=True)
    assembly.components = [Component(model)]
    app.ActiveDoc = assembly
    model.opened = model.keep_loaded = True
    model.Visible = False
    before = Path(model.path).read_bytes()

    events = run(setup, options=replace(options, formats=(fmt.key,)))

    assert events.summary['state'] == 'completed' and events.summary['succeeded'] == 1
    assert app.closed == [model.GetTitle()]
    assert not model.Visible and model.opened  # The assembly still needs the B-Rep in memory.
    assert assembly.Visible and assembly.opened and app.ActiveDoc is assembly
    assert not app.open_calls and Path(model.path).read_bytes() == before


@pytest.mark.parametrize('fmt', FORMATS, ids=lambda fmt: fmt.key)
def test_preexisting_visible_user_windows_stay_open_in_every_format(setup, tmp_path, fmt):
    app, model, options, _ = setup
    previous = app.add(tmp_path/'User.SLDPRT', opened=True)
    app.ActiveDoc = previous
    model.opened = True

    events = run(setup, options=replace(options, formats=(fmt.key,)))

    assert events.summary['succeeded'] == 1
    assert model.Visible and model.opened and previous.Visible and previous.opened
    assert not app.closed and app.ActiveDoc is previous


def test_hundred_components_loaded_by_opening_an_assembly_have_bounded_export_windows(setup, tmp_path, monkeypatch):
    app, _, options, _ = setup
    assembly = app.add(tmp_path/'Batch.SLDASM')
    models = [app.add(tmp_path/'parts'/f'Part-{i:03}.SLDPRT') for i in range(100)]
    assembly.components = [Component(model) for model in models]
    original = app.OpenDoc6
    def opened(*args):
        root = original(*args)
        if root is assembly:
            for model in models:
                model.opened = model.keep_loaded = True
                model.Visible = False
        return root
    monkeypatch.setattr(app, 'OpenDoc6', opened)
    visible_during_save = []
    app.after_save = lambda: visible_during_save.append(sum(model.Visible for model in models))

    events = run(setup, sources=[Source(assembly.path)], options=replace(options, assembly_mode='components'))

    assert events.summary['succeeded'] == 100 and events.summary['state'] == 'completed'
    assert visible_during_save == [1]*100
    assert app.open_calls == [assembly.path] and len(app.closed) == 101
    assert app.closed[-1] == assembly.GetTitle()
    assert not assembly.opened and not any(model.Visible for model in models)


@pytest.mark.parametrize('preloaded', [False, True], ids=['opened-by-export', 'hidden-reference'])
@pytest.mark.parametrize('fault', ['save', 'invalid-output', 'cancel', 'activation'])
def test_cleanup_runs_after_errors_and_cancellation(setup, tmp_path, monkeypatch, preloaded, fault):
    app, model, _, _ = setup
    previous = app.add(tmp_path/'User.SLDPRT', opened=True)
    app.ActiveDoc = previous
    if preloaded:
        model.opened = model.keep_loaded = True
        model.Visible = False
    stop = Event()
    if fault == 'save': app.save_error = 16
    elif fault == 'invalid-output': app.corrupt = True
    elif fault == 'cancel': app.after_save = stop.set
    else:
        original = app.ActivateDoc3
        def activate(name, *args):
            activated = original(name, *args)
            return previous if name == model.path else activated
        monkeypatch.setattr(app, 'ActivateDoc3', activate)

    events = run(setup, stop=stop)

    assert events.summary['state'] == ('cancelled' if fault == 'cancel' else 'completed')
    assert events.summary['succeeded'] == 0
    assert events.summary['failed'] == (0 if fault == 'cancel' else 1)
    assert app.closed == [model.GetTitle()] and not model.Visible
    assert model.opened is preloaded and previous.Visible and app.ActiveDoc is previous
    assert not list(Path(setup[2].output).rglob('.gokworks-*'))


@pytest.mark.parametrize('preloaded', [False, True])
def test_a_silently_ignored_close_stops_the_queue_and_reports_the_document(setup, tmp_path, monkeypatch, preloaded):
    app, model, _, _ = setup
    other = app.add(tmp_path/'Next.SLDPRT')
    if preloaded:
        model.opened = model.keep_loaded = True
        model.Visible = False
    monkeypatch.setattr(app, 'CloseDoc', lambda title: None)  # CloseDoc returns void, not a success flag.

    events = run(setup, sources=[Source(model.path), Source(other.path)])

    assert events.summary['state'] == 'error'
    assert 'kapatılamadı' in events.summary['error'] and Path(model.path).name in events.summary['error']
    assert len(app.saves) == 1 and not other.opened


def test_close_failure_keeps_ownership_for_the_final_cleanup_retry(setup, monkeypatch):
    app, model, _, _ = setup
    original = app.CloseDoc
    attempts = []
    def close(title):
        attempts.append(title)
        if len(attempts) == 1: raise RuntimeError('temporary close failure')
        return original(title)
    monkeypatch.setattr(app, 'CloseDoc', close)

    events = run(setup)

    assert events.summary['state'] == 'error' and 'kapatılamadı' in events.summary['error']
    assert attempts == [model.GetTitle()]*2 and not model.opened


def test_cleanup_reads_the_current_window_title_instead_of_using_the_open_time_title(setup, monkeypatch):
    app, model, _, _ = setup
    title = model.GetTitle()
    app.after_save = lambda: monkeypatch.setattr(model, 'GetTitle', lambda: 'New display title')

    assert run(setup).summary['state'] == 'completed'
    assert app.closed == ['New display title'] and title not in app.closed and not model.opened


def test_an_unactivated_hidden_document_is_left_as_it_was(setup):
    app, model, _, _ = setup
    model.opened = model.keep_loaded = True
    model.Visible = False
    with FakeSession(app) as session:
        session.document(model.path)
        session.release(model.path)
    assert model.opened and not model.Visible and not app.closed


def test_temporary_window_is_closed_on_session_exit_even_without_an_explicit_release(setup):
    app, model, _, _ = setup
    model.opened = model.keep_loaded = True
    model.Visible = False
    with FakeSession(app) as session:
        session.activate(session.document(model.path))
        assert model.Visible
    assert not model.Visible and model.opened and session.app is None


def test_an_unreadable_visibility_state_never_closes_a_preexisting_user_document(setup, monkeypatch):
    app, model, _, _ = setup
    model.opened = True
    original = api.get
    def get(obj, name):
        if obj is model and name == 'Visible': raise RuntimeError('cannot read visibility')
        return original(obj, name)
    monkeypatch.setattr(api, 'get', get)

    events = run(setup)

    assert events.summary['failed'] == 1 and not app.saves
    assert model.opened and model.Visible and not app.closed


def test_an_empty_document_title_never_sends_close_active_document(setup, monkeypatch):
    app, model, _, _ = setup
    app.after_save = lambda: monkeypatch.setattr(model, 'GetTitle', lambda: '')

    events = run(setup)

    assert events.summary['state'] == 'error' and 'başlığı okunamadı' in events.summary['error']
    assert not app.closed and model.opened
