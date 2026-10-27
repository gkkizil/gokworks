"""Preview-before-save workflow with real Qt and explicitly mocked CAD reads."""

from dataclasses import replace
import json
import threading

import pytest

from .test_preview_ui import page, payload, select  # noqa: F401
from .test_preview_source import source  # noqa: F401


def export_spy(monkeypatch):
    calls = []
    def export(*args, **kwargs):
        calls.append((args, kwargs))
        args[4].put(('done', dict(state='completed', succeeded=1)))
    monkeypatch.setattr('gui_qt.export.export_parts', export)
    return calls


@pytest.mark.parametrize('format', ['DXF', 'DWG'])
def test_first_start_shows_flat_without_saving_and_second_start_exports(page, qtbot, monkeypatch, format):
    p, w, files = page
    calls = export_spy(monkeypatch)
    p.source.setText(str(files[0].parent))
    p.output.setText(str(files[0].parent/'out'))
    p.form.fields['format'].setCurrentText(format)
    p.results.files([str(f) for f in files])
    assert p.form.value('preview_before_export') is True
    p.start_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview.flat_view.scene().items() and p.preview.flat_view.isVisible()
    assert not calls and not (files[0].parent/'out').exists()
    assert 'kontrol' in p.status_text.lower()
    p.start_button.click()
    qtbot.waitUntil(lambda: bool(calls) and not w.jobs.busy, timeout=4000)
    assert calls[0][1]['formats'] == (format.lower(),)


def test_preview_button_starts_a_read_even_without_a_selection_or_output_folder(page, qtbot):
    p, w, _ = page
    assert not p.results.table.currentIndex().isValid()
    p.preview_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.flat and p.preview.flat_view.isVisible()
    assert not p.output.text()


def test_scan_selects_first_source_and_shows_flat_before_any_save(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    p.source.setText(str(files[0].parent))
    p.output.setText(str(files[0].parent/'out'))
    p.start_button.click()  # no rows: read-only folder scan then preview
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.source == str(files[0])
    assert p.results.model.rowCount() == 2 and not calls
    assert not (files[0].parent/'out').exists()


def test_start_while_preview_is_running_waits_without_cancelling_or_auto_export(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    stopped = []
    def slow(request, cache, stop):
        entered.set()
        release.wait(4)
        stopped.append(stop.is_set())
        return payload(request.source)
    p._capture = slow
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files]); p.results.table.selectRow(0)
    qtbot.waitUntil(entered.is_set, timeout=4000)
    p.start_button.click()
    release.set()
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert stopped == [False] and not calls and not p._export_after_preview
    assert p.preview_payload.flat


def test_missing_flat_cannot_pass_the_preview_before_save_gate(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    p._capture = lambda request, cache, stop: replace(payload(request.source), flat=None,
        warnings=('Açınım önizlemesi okunamadı: test fixture failure',))
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files]); select(p, qtbot)
    assert p.preview_payload.mesh and not p.preview_payload.flat
    p.start_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy and p.preview_payload is not None, timeout=6000)
    assert not calls
    assert 'açınım' in p.status_text.lower() and 'okunamadı' in p.status_text.lower()


def test_setting_can_disable_review_and_is_persisted(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    p.form.fields['preview_before_export'].setChecked(False)
    assert p.settings.get('dxf_dwg_preview_before_export') is False
    assert p.settings.flush()
    assert json.loads(p.settings.path.read_text(encoding='utf-8'))['dxf_dwg_preview_before_export'] is False
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.start_button.click()
    qtbot.waitUntil(lambda: bool(calls) and not w.jobs.busy, timeout=4000)
    assert p.preview_payload is None


def test_bend_line_option_refreshes_flat_without_reusing_an_old_output(page, qtbot, tmp_path):
    p, w, files = page
    output = tmp_path/'old.dxf'; output.write_text('old production output')
    p.handle_events([('result', dict(source=str(files[0]), status='success', detail='old export',
        bend_lines=False, outputs=[dict(format='DXF', path=str(output), status='success')]))])
    select(p, qtbot)
    generation = p.preview_generation
    p.form.fields['bend_lines'].setChecked(True)
    qtbot.waitUntil(lambda: p.preview_generation > generation and not w.jobs.busy
                     and p.preview_payload is not None, timeout=6000)
    assert p.preview_request.bend_lines and not p.preview_request.output
    assert output.read_text() == 'old production output'


def test_changed_source_requires_a_new_preview_even_before_watcher_delivery(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files]); select(p, qtbot)
    p.watcher.blockSignals(True)
    files[0].write_text('changed source fixture')
    generation = p.preview_generation
    p.start_button.click()
    qtbot.waitUntil(lambda: p.preview_generation > generation and p.preview_payload is not None
                     and not w.jobs.busy, timeout=6000)
    assert not calls and p._flat_ready_for_export()


def test_stop_during_review_never_saves_and_explicit_preview_can_resume(page, qtbot, monkeypatch):
    from modules.cad_converter.models import Cancelled
    p, w, files = page
    calls = export_spy(monkeypatch)
    entered = threading.Event()
    def slow(request, cache, stop):
        entered.set(); stop.wait(4); raise Cancelled()
    p._capture = slow
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.start_button.click()
    qtbot.waitUntil(entered.is_set, timeout=4000)
    p.stop_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=5000)
    assert not calls and p._preview_cancelled and not p._preview_after_scan
    p._capture = lambda request, cache, stop: payload(request.source)
    p.preview_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.flat and not calls


def test_new_folder_is_scanned_instead_of_reviewing_a_row_from_the_old_folder(page, qtbot, monkeypatch, tmp_path):
    p, w, _ = page
    calls = export_spy(monkeypatch)
    folder = tmp_path/'different'; folder.mkdir()
    part = folder/'C.SLDPRT'; part.write_text('different fixture')
    p.source.setText(str(folder)); p.output.setText(str(tmp_path/'out'))
    p.start_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.source == str(part) and not calls


def test_ready_flat_in_hidden_compact_tab_is_revealed_before_export(page, qtbot, monkeypatch):
    p, w, files = page
    calls = export_spy(monkeypatch)
    w.resize(820, 560)
    qtbot.waitUntil(lambda: p.preview_compact, timeout=3000)
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files]); select(p, qtbot)
    assert p._flat_ready_for_export() and not p.preview.flat_view.isVisible()
    p.start_button.click()
    assert not calls and p.preview.flat_view.isVisible()
    p.start_button.click()
    qtbot.waitUntil(lambda: bool(calls) and not w.jobs.busy, timeout=4000)


@pytest.mark.parametrize('format', ['DXF', 'DWG'])
def test_preexport_panel_parses_native_adapter_temporary_dxf_without_saving(page, source, qtbot, monkeypatch, format):
    """Real UI -> capture -> export_one_part -> DXF parser; only CAD server is fake."""
    from pathlib import Path
    from types import SimpleNamespace as NS
    from support.solidworks import com_stubs
    from .test_preview_geometry import flat_file
    from modules.dxf_dwg.preview import solidworks as sw

    p, w, _ = page
    app, model, previous, _, _, session_type = source
    before = Path(model.path).read_bytes()
    native_outputs = []
    def native_export(path, *args):
        native_outputs.append(Path(path))
        flat_file(path)
        return True
    com, client = com_stubs('dxf')
    monkeypatch.setattr(sw.exporter, 'pythoncom', com)
    monkeypatch.setattr(sw.exporter, 'win32com', NS(client=client))
    model.Visible = False
    model.ExportToDWG2 = native_export
    p._capture_geometry = lambda request, cache, stop: sw.capture_geometry(request, cache, stop, session_factory=session_type)
    p._capture = lambda request, cache, stop: sw.capture(request, cache, stop, session_factory=session_type)
    p.source.setText(str(Path(model.path).parent))
    destination = Path(model.path).parent/'production-output'
    p.output.setText(str(destination))
    p.form.fields['format'].setCurrentText(format)
    p.results.files([model.path])
    p.start_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and p.preview_payload.flat is not None
                     and not w.jobs.busy, timeout=6000)
    assert p.preview.flat_view.scene().items() and p.preview.mesh_view.mesh
    assert native_outputs and all(path.suffix == '.dxf' and not path.exists() for path in native_outputs)
    assert not destination.exists() and not app.saves
    assert Path(model.path).read_bytes() == before and app.ActiveDoc is previous
