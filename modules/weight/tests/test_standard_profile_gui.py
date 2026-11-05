"""Standard profiles in the weight page: the section really follows the chosen family.

Regression: the EXE shipped without data/sections.json, so choosing HP/UPN left the
previous section (Boru, U sac) on screen. A missing catalogue must now be reported.
"""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from gui_qt.app import MainWindow, create_application
from modules.weight import catalog


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(w); w.show()
    w.navigate('weight'); yield w.pages['weight']
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def choose(page, category, kind):
    page.form.fields['category'].setCurrentText(category)
    page.form.fields['kind'].setCurrentText(kind)
    page.update_result()


@pytest.mark.parametrize('kind, prefix', [('IPE', 'IPE '), ('HEA', 'HEA '), ('HP', 'HP '), ('UPN (NPU)', 'UPN '),
                                          ('Eşit kollu köşebent · EN 10056-1', 'L ')])
def test_each_standard_family_replaces_the_previous_section(page, kind, prefix):
    choose(page, 'İçi boş kesit', 'Boru')
    assert page.result.section_text.startswith('Boru')
    choose(page, 'Standart profil', kind)
    assert page.result.section_text.startswith(prefix), page.result.section_text
    assert page.form.fields['profile'].isVisibleTo(page) and not page.form.fields['method'].isVisibleTo(page)
    assert page.headline.text() != 'Değerleri kontrol edin'


def test_missing_catalogue_is_reported_instead_of_a_stale_section(page, monkeypatch, tmp_path):
    choose(page, 'İçi boş kesit', 'Boru')
    monkeypatch.setattr(catalog, 'DATA', tmp_path / 'missing.json')
    catalog.load.cache_clear()
    try:
        choose(page, 'Standart profil', 'HP')
        assert page.result is None and page.headline.text() == 'Değerleri kontrol edin'
        assert 'kataloğu okunamadı' in page.status_text
    finally:
        catalog.load.cache_clear()
