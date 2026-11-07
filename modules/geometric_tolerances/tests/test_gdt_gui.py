"""Geometrik toleranslar sayfasının düzeni: tür seçimi, form grupları, alan hataları, çerçeve."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication

from gui_qt.app import MainWindow, create_application
from modules.geometric_tolerances.catalog import CATALOG
from modules.geometric_tolerances.catalog_view import LEGACY_GROUP, symbol_icon


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window)
    window.resize(1400, 900); window.show(); window.navigate('geometric_tolerances')
    yield window.pages['geometric_tolerances']
    window.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def rows(page):
    proxy, out = page.catalog_proxy, []
    for g in range(proxy.rowCount()):
        group = proxy.index(g, 0)
        out.append((group.data(), [proxy.index(c, 0, group).data(Qt.UserRole)['key'] for c in range(proxy.rowCount(group))]))
    return out


def test_kind_picker_is_first_grouped_with_symbols_and_legacy_closed(page):
    panel = page.input_card.layout()
    order = [panel.itemAt(i).widget() for i in range(panel.count()) if panel.itemAt(i).widget()]
    assert order.index(page.catalog) < order.index(page.form) and order.index(page.search) < order.index(page.catalog)
    groups = rows(page)
    assert [title for title, _ in groups] == ['Şekil', 'Yönelim', 'Konum', 'Salgı', 'Profil',
                                              'Kaldırılmış semboller (ASME 2018)']
    assert sorted(k for _, keys in groups for k in keys) == sorted(item.key for item in CATALOG)
    legacy = page.catalog_proxy.index(5, 0)
    assert not page.catalog.isExpanded(legacy) and page.catalog.isExpanded(page.catalog_proxy.index(0, 0))
    for item in CATALOG:
        assert not symbol_icon(item.key, 'Dark').isNull()
    selected = page.catalog.selectionModel().selectedRows()
    assert len(selected) == 1 and selected[0].data(Qt.UserRole)['key'] == page.kind
    assert not (page.catalog_proxy.flags(page.catalog_proxy.index(0, 0)) & Qt.ItemIsSelectable)
    page.search.setText('simetri')
    assert page.catalog.isExpanded(page.catalog_proxy.index(0, 0))         # matches inside the legacy group are shown


def test_choosing_a_kind_updates_and_resets_inspection_values(page):
    page.form.set_value('size_tolerance', '0,2'); page.form.set_value('measured', '0,01')
    index = page.catalog_proxy.mapFromSource(page.catalog_model.index_of('position'))
    page.catalog.setCurrentIndex(index)
    assert page.kind == 'position' and page.settings.get('gdt_kind') == 'position'
    assert page.form.value('measured') == '' and page.form.value('size_tolerance') == ''
    assert page.result is not None and 'Konum' in page.headline.text()


def test_form_groups_labels_and_datum_states(page):
    f = page.form
    assert f.form.labelForField(f.fields['size']).text() == 'Parça boyutu (şema için) · mm'
    assert page.measure_form.labelForField(f.fields['measured']).text() == 'Ölçülen sapma · mm'
    assert page.measure_form.indexOf(f.fields['size_tolerance']) >= 0 and f.form.indexOf(f.fields['measured']) < 0
    assert page.measure_section.toggle.text() == 'Ölçüm kontrolü (isteğe bağlı)' and not page.measure_section.is_expanded()
    page.kind = 'flatness'; page.update_result()
    assert f.fields['datum'].isVisibleTo(page) and not f.fields['datum'].isEnabled()
    assert 'datum) kullanılmaz' in page.notes['datum'].text()
    page.kind = 'position'; page.update_result()
    assert f.form.labelForField(f.fields['datum']).text().endswith('*') and f.fields['datum'].isEnabled()
    assert not page.measure_form.isRowVisible(f.fields['size_tolerance'])
    page.kind = 'line_profile'; page.update_result()
    assert not f.form.labelForField(f.fields['datum']).text().endswith('*')


@pytest.mark.parametrize('kind,key,value,text', [
    ('flatness', 'size_tolerance', '0,04', 'ASME 8.4'),
    ('flatness', 'tolerance', 'abc', 'mm cinsinden'),
    ('flatness', 'size', '0', 'büyük'),
    ('flatness', 'measured', '-1', 'mm cinsinden'),
    ('position', 'datum', 'Yok', 'datum referansı'),
])
def test_rule_message_is_shown_under_its_field_in_red(page, kind, key, value, text):
    page.kind = kind; page.form.set_value(key, value); page.update_result()
    assert page.result is None
    note, field = page.notes[key], page.form.fields[key]
    assert text in note.text() and note.property('role') == 'error' and field.property('invalid') is True
    assert not note.text().startswith(('Toplam tolerans t:', 'Gösterim boyutu:'))
    if key in ('measured', 'size_tolerance'):
        assert page.measure_section.is_expanded()
    others = [k for k in page.notes if k != key]
    assert all(page.notes[k].property('role') == 'muted' for k in others)
    page.form.set_value(key, {'size_tolerance': '', 'tolerance': '0,05', 'size': '100', 'measured': '', 'datum': 'A'}[key])
    page.update_result()
    assert page.result is not None and note.property('role') == 'muted' and not field.property('invalid')


def test_frame_is_on_top_and_explanations_are_a_summary_with_details(page):
    right = page.right
    assert right.indexOf(page.frame_view) < right.indexOf(page.diagram_tabs)
    assert page.diagrams['frame'] is page.frame_view and page.frame_view.scene().items()
    assert page.diagram_tabs.count() == 1 and page.diagram_tabs.currentWidget() is page.diagrams['zone']
    assert page.frame_view.height() >= 84
    assert page.details.text() and 'Bölge:' in page.details.text()
    assert set(page.explanations) == {'measure', 'note', 'size'}
    assert not any(d.is_expanded() for d in page.explanations.values())
    page.kind = 'position'; page.update_result()
    assert page.explanations['size'].isHidden()
    page.kind = 'cylindricity'; page.update_result()
    assert not page.explanations['size'].isHidden()


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_theme_change_redraws_symbols_and_frame(page, theme):
    window = page.window(); window.set_theme(theme); QApplication.processEvents()
    assert page.catalog.delegate.appearance == page.appearance
    assert page.frame_view.scene().items() and not page.grab().isNull()
