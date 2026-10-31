"""Fast BOM defaults, worker options and explicit skipped-weight presentation."""

from dataclasses import replace
import pytest
from PySide6.QtWidgets import QFileDialog
from gui_qt.app import MainWindow, create_application
from modules.bom import ui
from modules.bom.exporter import Result, Part, Node


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    w = MainWindow(tmp_path/'settings.json')
    def before_close(window):
        window.closing = True
        if window.jobs.busy:
            window.jobs.cancel(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=8000)
    qtbot.addWidget(w, before_close_func=before_close)
    w.resize(1024, 700); w.show(); w.navigate('bom')
    return w.pages['bom'], w


def example(mass_included=False):
    return Result('assembly.SLDASM', 'Default',
                  (Part('Bolt', 'bolt.SLDPRT', 'Default', 4),),
                  (Node('1', '', 1, 'Bolt', 'Bolt-1', 'Parça', 'bolt.SLDPRT', 'Default'),),
                  0, 0, False, mass_included)


@pytest.mark.parametrize('mode,masses,resolve', [
    ('Hızlı liste · ağırlıksız', False, False),
    ('Tam çözümleme · ağırlıksız', False, True),
    ('Ağırlıklarla birlikte', True, True),
])
def test_read_mode_reaches_real_worker_and_complete_results_preserve_counts(page, qtbot, monkeypatch,
                                                                          mode, masses, resolve):
    p, w = page
    assert p.form.value('read_mode') == 'Hızlı liste · ağırlıksız'
    assert p.include_images.isChecked()
    observed = []
    def scan(events, stop, **options):
        observed.append(options)
        events.put(('bom_done', dict(state='completed', result=example(masses))))
    monkeypatch.setattr(ui, 'scan_worker', scan)
    p.form.set_value('read_mode', mode); p.form.set_value('include_excluded', True)
    p.scan(); qtbot.waitUntil(lambda: not w.jobs.busy)
    assert observed == [dict(include_excluded=True, include_mass=masses, resolve_lightweight=resolve)]
    assert p.parts_model.rows[0]['quantity'] == 4 and p.export_button.isEnabled()
    assert p.parts.isColumnHidden(2) is not masses
    assert p.tree.isColumnHidden(3) is not masses
    if not masses:
        assert 'Ağırlık hesaplanmadı' in p.summary.text() and 'Okunamadı' not in p.summary.text()


def test_excel_images_follow_existing_choice_and_weighted_results_restore_columns(page, qtbot, monkeypatch, tmp_path):
    p, w = page; p.load_result(example())
    assert p.parts.isColumnHidden(2)
    p.load_result(replace(example(True), parts=(Part('Bolt','bolt.SLDPRT','Default',4, .1, .4),)))
    assert not p.parts.isColumnHidden(2) and '0,400000' in p.summary.text()
    target = str(tmp_path/'bom.xlsx'); captured = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (target, 'Excel'))
    def write(result, path, events, stop, **options):
        captured.append(options)
        events.put(('bom_done', dict(state='exported', path=path)))
    monkeypatch.setattr(ui, 'export_worker', write)
    for include in (False, True):
        p.include_images.setChecked(include); p.export()
        qtbot.waitUntil(lambda: not w.jobs.busy)
    assert captured == [dict(include_images=False), dict(include_images=True)]
