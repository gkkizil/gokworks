"""Real Qt jobs/navigation; the CAD boundary remains mocked on Linux."""

import gc
from pathlib import Path
import threading

import pytest
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QAbstractItemView

from gui_qt.app import MainWindow, create_application
from modules.cad_converter.models import Source


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(window)
    window.resize(1440, 900); window.show(); window.navigate('cad_converter')
    yield window.pages['cad_converter'], window
    if window.jobs.busy:
        window.jobs.cancel(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=8000)
    window.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); gc.collect()


def test_multiple_files_folder_duplicates_filter_remove_and_clear_use_same_queue(page, qtbot, tmp_path):
    p, w = page
    files = [tmp_path/'A.SLDPRT', tmp_path/'B.SLDASM', tmp_path/'C.SLDDRW']
    for file in files: file.write_text('fixture')
    p.add_paths([str(f) for f in files]); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert len(p.sources) == 2 and p.files_proxy.rowCount() == 2
    p.add_paths([str(tmp_path)]); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert len(p.sources) == 2
    p.type_filter.setCurrentIndex(1); assert p.files_proxy.rowCount() == 1
    p.files_view.selectRow(0); p.remove_button.click(); assert len(p.sources) == 1
    p.results.clear_button.click(); assert not p.sources and not p.results.model.rows and not p.results.results
    p.type_filter.setCurrentIndex(0); assert p.files_proxy.rowCount() == 0


def test_source_file_button_opens_multiselect_and_does_not_change_output_folder(page, qtbot, tmp_path, monkeypatch):
    p, w = page
    sources = [tmp_path/'First.SLDPRT', tmp_path/'Second.SLDASM']
    for path in sources: path.write_text('source fixture')
    output = str(tmp_path/'CAD_EXPORT'); p.form.set_value('output', output)
    dialogs = []
    def choose(*args):
        dialogs.append(args)
        return [str(path) for path in sources], 'SolidWorks 3D'
    monkeypatch.setattr('modules.cad_converter.ui.QFileDialog.getOpenFileNames', choose)
    qtbot.mouseClick(p.scan_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert dialogs and 'Kaynak' in dialogs[0][1]
    assert [source.path for source in p.sources] == [str(path) for path in sources]
    assert p.form.value('output') == output
    assert not p.empty_hint.isVisible()


def test_source_folder_button_scans_folder_and_remembers_it_separately_from_output(page, qtbot, tmp_path, monkeypatch):
    p, w = page
    source = tmp_path/'Models'; source.mkdir()
    (source/'Part.SLDPRT').write_text('source fixture')
    output = str(tmp_path/'CAD_EXPORT'); p.form.set_value('output', output)
    monkeypatch.setattr('modules.cad_converter.ui.QFileDialog.getExistingDirectory', lambda *args: str(source))
    qtbot.mouseClick(p.folder_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert len(p.sources) == 1 and Path(p.sources[0].path).parent == source
    assert p.settings.get('cad_converter_source_folder') == str(source)
    assert p.form.value('output') == output


def test_multiple_formats_persist_and_advanced_values_are_used_without_hidden_validation_error(page, tmp_path):
    p, _ = page
    p.form.set_value('output', str(tmp_path/'out'))
    p.format_checks['xt'].setChecked(True); p.format_checks['stl_binary'].setChecked(True)
    p.stl_options.set_expanded(True); p.stl_form.set_value('stl_quality', 'Özel')
    p.stl_form.set_value('deviation', '0,05'); p.stl_form.set_value('angle', '12')
    p.model_form.set_value('configurations', 'Seçilen konfigürasyonlar')
    p.model_form.set_value('selected', 'Default; Other')
    p.naming_form.set_value('prefix', 'TEST-')
    options = p.options()
    assert options.formats == ('step214','xt','stl_binary') and options.selected_configurations == ('Default','Other')
    assert options.deviation_mm == .05 and options.angle_degrees == 12 and options.prefix == 'TEST-'
    p.format_checks['stl_binary'].setChecked(False); p.stl_form.set_value('angle', '')
    assert p.options().angle_degrees == 15
    assert p.settings.get('cad_converter_format_xt') is True


def test_real_worker_uses_snapshot_keeps_navigation_responsive_and_cancel_cooperative(page, qtbot, tmp_path, monkeypatch):
    p, w = page
    file = tmp_path/'A.SLDPRT'; file.write_text('fixture')
    p.sources = [Source(str(file))]; p.refresh_sources(); p.form.set_value('output', str(tmp_path/'out'))
    started = threading.Event(); cancelled = threading.Event(); ui_thread = threading.get_ident(); observed = []
    def fake_convert(sources, options, sink, stop):
        observed.append((threading.get_ident(), sources, options)); started.set()
        if stop.wait(5): cancelled.set()
        sink.put(('cad_done', dict(state='cancelled', processed=0, succeeded=0, warned=0, skipped=0, failed=0)))
    monkeypatch.setattr('modules.cad_converter.ui.convert', fake_convert)
    p.start_button.click(); qtbot.waitUntil(started.is_set, timeout=3000)
    assert w.jobs.busy and not p.scan_button.isEnabled() and not p.results.clear_button.isEnabled()
    assert p.stop_button.isVisible()
    w.navigate('weight'); assert w.pages['weight'].isVisible()
    w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert cancelled.is_set() and observed[0][0] != ui_thread and observed[0][1][0].path == str(file)
    assert 'Durduruldu' in p.status_text and p.scan_button.isEnabled()


def test_results_keep_separate_rows_for_same_file_different_configuration_and_format(page):
    p, _ = page
    rows = [dict(source='A.SLDPRT', configuration=c, format=f, status='success', detail='OK', output=f'{c}.{f}')
            for c in ('Default','Other') for f in ('STEP AP214','X_T')]
    p.handle_events([('cad_result', r) for r in rows])
    assert p.results.model.rowCount() == 4 and len(p.results.results) == 4
    assert {row['configuration'] for row in p.results.results} == {'Default','Other'}
    p.results.clear_button.click(); assert not p.results.results and p.results.model.rowCount() == 0


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_left_source_right_results_and_actions_fit_small_and_large_windows(page, qtbot, theme):
    p, w = page; w.set_theme(theme)
    for size in ((820,560),(1024,700),(1440,900)):
        w.resize(*size); qtbot.wait(30)
        assert p.splitter.sizes()[0] >= 220 and p.splitter.sizes()[1] >= 320
        assert p.source_scroll.horizontalScrollBar().maximum() == 0
        assert p.rect().contains(p.start_button.mapTo(p, p.start_button.rect().bottomRight()))
        # Source selection is the first step and stays fixed above the long
        # options form, even when that form is scrolled to the bottom.
        p.source_scroll.verticalScrollBar().setValue(0)
        first = p.scan_button.mapTo(p, p.scan_button.rect().topLeft())
        assert p.scan_button.isVisible() and p.folder_button.isVisible()
        for control in (p.scan_button, p.folder_button):
            assert p.rect().contains(control.mapTo(p, control.rect().bottomRight()))
            assert control.mapTo(p, control.rect().bottomRight()).y() < p.source_scroll.mapTo(p, p.source_scroll.rect().topLeft()).y()
        output = p.form.fields['output']
        assert first.y() < output.mapTo(p, output.rect().topLeft()).y()
        p.source_scroll.verticalScrollBar().setValue(p.source_scroll.verticalScrollBar().maximum())
        qtbot.wait(10)
        assert p.scan_button.mapTo(p, p.scan_button.rect().topLeft()) == first
        assert not w.grab().isNull()


def test_validation_shows_plain_error_before_starting_any_job(page):
    p, w = page
    p.start_export()
    assert not w.jobs.busy and 'çıktı klasörü' in p.status_text
    p.form.set_value('output', '/tmp/out')
    for widget in p.format_checks.values(): widget.setChecked(False)
    p.start_export()
    assert not w.jobs.busy and 'format' in p.status_text
