"""Assembly method, usage examples and the card-style preset list."""

import pytest

from modules.iso_fits import guidance as g
from modules.iso_fits import rules as r


@pytest.mark.parametrize('hole,shaft,kind,icon', [
    ('H11', 'c11', 'clearance', 'slide'), ('H7', 'h6', 'clearance', 'push'),
    ('H7', 'k6', 'transition', 'hammer'), ('H7', 'n6', 'transition', 'hammer'),
    ('H7', 's6', 'interference', 'press')])
def test_assembly_method_follows_the_computed_fit_type(hole, shaft, kind, icon):
    fit = r.calculate('50', hole, shaft)
    assert fit.kind == kind  # e.g. Ø50 H7/n6 is a transition fit per ISO 286-2
    method = g.assembly(fit)
    assert method.icon == icon and method.tone == g.TONES[kind]
    if kind == 'interference':
        assert 'hesabı bu ekranda yapılmaz' in method.detail  # no invented force/temperature


def test_every_curated_preset_has_usage_examples_and_unknown_pairs_use_the_nearest():
    assert {f'{p.hole}/{p.shaft}' for p in r.PRESETS} <= set(g.USAGE)
    text, code, exact = g.usage(r.calculate('50', 'H7', 'k6'))
    assert exact and code == 'H7/k6' and 'kaplin' in text
    text, code, exact = g.usage(r.calculate('50', 'H8', 'g6'))
    assert not exact and code in g.USAGE and text == g.USAGE[code]


def test_preset_rows_group_by_the_real_fit_type_at_the_chosen_diameter():
    rows = g.preset_rows('50', 'Tümü')
    headers = [row for row in rows if row.get('header')]
    assert [row['kind'] for row in headers] == ['clearance', 'transition', 'interference']
    cards = {row['id']: row for row in rows if not row.get('header')}
    assert len(cards) == len(r.PRESETS)
    assert cards['H7 / n6']['parent'] == 'transition' and cards['H7 / s6']['parent'] == 'interference'
    assert cards['H7 / h6']['title'] == 'H7 / h6' and cards['H7 / h6']['label']
    shaft_basis = g.preset_rows('50', 'Mil esaslı')
    assert all(row['id'].endswith('h6') for row in shaft_basis if not row.get('header'))


def test_iso_page_shows_cards_assembly_and_usage(qtbot, tmp_path):
    from gui_qt.app import MainWindow, create_application
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window); window.show()
    window.navigate('iso_fits'); page = window.pages['iso_fits']
    page.form.set_value('hole', 'H7'); page.form.set_value('shaft', 's6')
    qtbot.waitUntil(lambda: page.assembly_card.title.text() == 'PRES / ISIL MONTAJ', timeout=2000)
    assert '(sıkılık)' in page.insight.metric_labels['min'].text()
    assert 'Kalıcı montaj' in page.insight.examples.text()
    assert page.presets.currentIndex().data().startswith('H7 / s6')
    assert page.preset_section.isVisible() and page.presets.isVisible()
    page.form.set_value('method', 'Manuel kontrol')
    qtbot.waitUntil(lambda: not page.presets.isVisible(), timeout=2000)
    page.form.set_value('diameter', 'abc')
    qtbot.waitUntil(lambda: page.assembly_card.title.text() == '—', timeout=2000)
