"""ISO and manual inputs must present the same engineering section and bands."""

import gc

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from gui_qt.app import MainWindow, create_application
from modules.iso_fits import rules
from modules.iso_fits.ui import SAMPLES, VIEWS


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    widget = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(widget)
    widget.resize(1440, 900)
    widget.show()
    widget.navigate('iso_fits')
    yield widget
    assert not widget.jobs.busy
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def set_fields(page, **values):
    page.loading = True
    try:
        for key, value in values.items():
            page.form.set_value(key, value)
    finally:
        page.loading = False
    page.update_timer.stop()
    page.update_result()
    QApplication.processEvents()


def geometry(diagram):
    """Snapshot live Qt item geometry, without retaining deleted scene items."""
    return {tag: [item.sceneBoundingRect().getRect() for item in items]
            for tag, items in diagram.vector.tagged.items()
            if tag not in ('hole_label', 'shaft_label')}


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_equivalent_iso_and_manual_limits_share_section_bands_and_sample_results(window, theme):
    window.set_theme(theme)
    page = window.pages['iso_fits']
    diagram = page.diagrams['fit']
    # Clearance, transition, interference, and exact contact at minimum gap.
    for shaft in ('g6', 'k6', 's6', 'h6'):
        reference = rules.calculate('50', 'H7', shaft)
        manual = {f'{feature}_{side}': rules.format_mm(rules.mm(getattr(band, side + '_nm')))
                  for feature, band in (('hole', reference.hole), ('shaft', reference.shaft))
                  for side in ('lower', 'upper')}
        for view in VIEWS:
            for sample in SAMPLES:
                set_fields(page, method='ISO seçimi', diameter='50', hole='H7', shaft=shaft,
                           view=view, sample=sample)
                iso_geometry = geometry(diagram)
                if view == 'Montaj kesiti':
                    tags = diagram.vector.tagged
                    assert tags['dimension_D'] and tags['dimension_d']
                    assert 'H7' in tags['hole_label'][0].toPlainText()
                    assert shaft in tags['shaft_label'][0].toPlainText()
                    results = {tag: tags[tag][0].toPlainText() for tag in
                               ('sample_state', 'diametral_result', 'radial_result', 'fit_kind')}
                    hole, shaft_diameter = reference.sample(sample)
                    difference = hole - shaft_diameter
                    state = ('BOŞLUK VAR' if difference > 0 else
                             'SIKILIK VAR' if difference < 0 else 'SINIRDA TEMAS')
                    assert results['sample_state'] == f'Seçilen örnek: {state}'
                    assert bool(tags.get('overlap')) == (difference < 0)
                    assert bool(tags.get('clearance')) == (difference > 0)
                    assert bool(tags.get('radial_dimension')) == bool(difference)
                else:
                    assert diagram.vector.tagged['hole_band']
                    assert diagram.vector.tagged['shaft_band']
                set_fields(page, method='Manuel kontrol', **manual)
                assert page.result.sample(sample) == reference.sample(sample)
                assert page.result.kind == reference.kind
                assert geometry(diagram) == iso_geometry
                if view == 'Montaj kesiti':
                    for tag, expected in results.items():
                        assert diagram.vector.tagged[tag][0].toPlainText() == expected
                    for tag in ('hole_label', 'shaft_label'):
                        assert 'Manuel' in diagram.vector.tagged[tag][0].toPlainText()
                assert page.view_tabs.tabText(page.view_tabs.currentIndex()) == view
                assert page.sample_tabs.tabText(page.sample_tabs.currentIndex()) == sample


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_section_dimensions_and_footer_remain_visible_at_small_and_large_sizes(window, qtbot, theme):
    window.set_theme(theme)
    page = window.pages['iso_fits']
    diagram = page.diagrams['fit']
    for method in ('ISO seçimi', 'Manuel kontrol'):
        set_fields(page, method=method, shaft='s6', sample='En az boşluk', view='Montaj kesiti',
                   diameter='60', hole_lower='-0,05', hole_upper='-0,01',
                   shaft_lower='-0,02', shaft_upper='0,03')
        for size in ((820, 560), (1024, 700), (1440, 900)):
            window.resize(*size)
            qtbot.wait(30)
            for tag in ('hole_label', 'shaft_label', 'dimension_D', 'dimension_d',
                        'sample_state', 'diametral_result', 'radial_result', 'fit_kind'):
                for item in diagram.vector.tagged[tag]:
                    assert diagram.sceneRect().contains(item.sceneBoundingRect()), tag
                    assert diagram.viewport().rect().adjusted(-1, -1, 1, 1).contains(
                        diagram.mapFromScene(item.sceneBoundingRect()).boundingRect()), tag
            assert page.view_tabs.isVisible() and page.sample_tabs.isVisible()
