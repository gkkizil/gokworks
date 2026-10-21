"""Real Qt integration of the small torque tool; no CAD connection needed."""

import gc

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QGraphicsTextItem

from modules.bolt_torque.rules import calculate
from gui_qt.app import create_application, MainWindow


@pytest.fixture
def window(qtbot,tmp_path):
    create_application([])
    w=MainWindow(tmp_path/'settings.json');qtbot.addWidget(w)
    w.resize(1440,900);w.show();w.navigate('bolt_torque')
    yield w
    assert not w.jobs.busy
    assert w.settings.flush();w.close();w.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);gc.collect()


def test_new_navigation_is_cached_and_existing_bolt_calculation_unchanged(window):
    page=window.pages['bolt_torque']; previous=window.pages['bolt'].result
    assert page.result == calculate()
    assert '51,96 N·m' in page.torque_value.text()
    assert '25,98 kN' in page.preload_value.text()
    assert not page.form.fields['pitch'].isEnabled()
    assert '1,5 mm' in page.pitch_hint.text()
    assert page.copy_button.isEnabled()
    window.navigate('bolt');window.navigation['bolt_torque'].click()
    assert window.stack.currentWidget() is page
    assert window.pages['bolt'].result == previous


def test_condition_defaults_manual_override_and_reset(window,qtbot):
    page=window.pages['bolt_torque'];f=page.form
    f.set_value('condition','Hafif yağlı')
    qtbot.waitUntil(lambda:page.result.k==.15)
    assert f.value('k')=='0,15'
    assert page.result.torque_nm == pytest.approx(calculate().torque_nm*.75)
    f.set_value('k','0,18')
    qtbot.waitUntil(lambda:page.result.k==.18)
    assert 'Manuel K' in page.k_hint.text() and page.reset_k_button.isVisible()
    page.reset_k_button.click()
    qtbot.waitUntil(lambda:page.result.k==.15)
    assert not page.reset_k_button.isVisible()
    f.set_value('condition','Kuru')
    qtbot.waitUntil(lambda:page.result.k==.2)


def test_fine_pitch_grade_boundary_and_live_preload(window,qtbot):
    page=window.pages['bolt_torque'];f=page.form
    f.set_value('metric','M18');f.set_value('thread_series','İnce diş')
    box=f.fields['pitch'];box.setCurrentIndex(box.findData(1.5))
    f.set_value('preload_percent','60')
    qtbot.waitUntil(lambda:page.result.metric=='M18' and page.result.preload_percent==60)
    assert page.result.pitch_mm==1.5 and page.result.yield_strength_mpa==660
    assert 'Standart normal adım: 2,5 mm' == page.pitch_hint.text()
    f.set_value('metric','M16')
    qtbot.waitUntil(lambda:page.result.metric=='M16')
    assert page.result.pitch_mm==1.5 and page.result.yield_strength_mpa==640
    f.set_value('grade','12.9')
    qtbot.waitUntil(lambda:page.result.grade=='12.9')
    assert page.result.yield_strength_mpa==1100
    assert '12.9' in page.selection_label.text()


def test_copy_uses_current_fields_before_debounce_and_contains_assumptions(window):
    page=window.pages['bolt_torque']
    page.form.set_value('preload_percent','50')
    page.copy_button.click()
    text=QApplication.clipboard().text()
    assert page.result.preload_percent==50
    assert 'Tahmini Sıkma Torku: 37,11 N·m' in text
    assert 'Hesaplanan ön yük: 18,56 kN' in text
    assert 'yaklaşık varsayımlardır' in text and 'üretici şartnamesini' in text
    assert '%50' in text and 'ISO 898-1' in text


def test_invalid_input_clears_stale_result_and_cannot_copy(window,qtbot):
    page=window.pages['bolt_torque']
    QApplication.clipboard().setText('keep')
    page.form.set_value('k','nan');page.copy_result()
    assert page.result is None and page.torque_value.text()=='—'
    assert not page.copy_button.isEnabled()
    assert 'section_empty' in page.section_diagram.vector.tagged
    assert 'section_torque' not in page.section_diagram.vector.tagged
    assert 'bolt_shank' not in page.section_diagram.vector.tagged
    assert QApplication.clipboard().text()=='keep'
    page.form.set_value('k','0,20')
    qtbot.waitUntil(lambda:page.result is not None)
    assert page.copy_button.isEnabled()
    assert 'section_empty' not in page.section_diagram.vector.tagged
    assert 'bolt_shank' in page.section_diagram.vector.tagged


def test_section_follows_selected_thread_and_live_torque_without_changing_calculation(window,qtbot):
    page=window.pages['bolt_torque'];f=page.form
    original_bolt=window.pages['bolt'].result
    original_shank=page.section_diagram.vector.tagged['bolt_shank'][0].polygon()
    original_threads=len(page.section_diagram.vector.tagged['bolt_thread'])
    for key,value in dict(metric='M12',thread_series='İnce diş',condition='Hafif yağlı',
                          k='0,18',preload_percent='65',grade='10.9').items():f.set_value(key,value)
    f.fields['pitch'].setCurrentIndex(f.fields['pitch'].findData(1.25))
    qtbot.waitUntil(lambda:page.result.metric=='M12' and page.result.pitch_mm==1.25)
    tags=page.section_diagram.vector.tagged
    assert tags['section_selection'][0].toPlainText()=='M12 × 1,25 · 10.9'
    assert tags['section_dimensions'][0].toPlainText()=='d = 12 mm · P = 1,25 mm'
    assert tags['section_torque'][0].toPlainText()=='T ≈ '+page.torque_value.text()
    assert tags['section_preload'][0].toPlainText()=='Ön yük F = '+page.preload_value.text().split(': ',1)[1]
    assert tags['bolt_shank'][0].polygon()!=original_shank
    assert len(tags['bolt_thread'])!=original_threads
    assert tags['nut_profile'] and tags['clamped_parts']
    assert '1.25 mm' in page.section_diagram.accessibleDescription()
    assert page.result==calculate(metric='M12',thread_series='İnce diş',pitch=1.25,
                                  grade='10.9',condition='Hafif yağlı',k=.18,preload_percent=65)
    assert window.pages['bolt'].result==original_bolt


def test_zero_preload_is_a_valid_section_without_load_arrows(window,qtbot):
    page=window.pages['bolt_torque'];page.form.set_value('preload_percent','0')
    qtbot.waitUntil(lambda:page.result.preload_n==0)
    tags=page.section_diagram.vector.tagged
    assert tags['bolt_shank']
    assert tags['section_torque'][0].toPlainText()=='T ≈ 0,00 N·m'
    assert tags['section_preload'][0].toPlainText()=='Ön yük F = 0,00 kN'
    assert not tags.get('preload_arrow') and not tags.get('torque_arrow')


def test_settings_restart_preserves_custom_k_fine_pitch_and_percentage(window,qtbot,tmp_path):
    page=window.pages['bolt_torque'];f=page.form
    for key,value in dict(metric='M12',thread_series='İnce diş',condition='Hafif yağlı',k='0,18',
                          preload_percent='65',grade='10.9').items():f.set_value(key,value)
    f.fields['pitch'].setCurrentIndex(f.fields['pitch'].findData(1.25))
    page.copy_result();expected=page.result;assert window.settings.flush()
    other=MainWindow(tmp_path/'settings.json');qtbot.addWidget(other)
    assert other.pages['bolt_torque'].result == expected
    other.close()


@pytest.mark.parametrize('theme',('dark','light'))
def test_compact_wide_layout_and_copy_remain_accessible(window,qtbot,theme):
    window.set_theme(theme);page=window.pages['bolt_torque']
    for size, compact in (((1440,900),False),((1024,700),False),((820,620),True),((1366,768),False)):
        window.resize(*size);qtbot.wait(20)
        assert page.compact == compact
        if compact:
            assert page.output_card.geometry().top() > page.input_card.geometry().bottom()
        else:
            assert page.output_card.geometry().left() > page.input_card.geometry().right()
        assert page.form.fields['preload_percent'].width()>80
        assert page.torque_value.text().endswith('N·m')
        assert page.copy_button.isVisible() and page.copy_button.isEnabled()
        diagram=page.section_diagram
        for item in diagram.vector.items():
            if isinstance(item,QGraphicsTextItem):
                assert diagram.sceneRect().contains(item.sceneBoundingRect())
                assert diagram.viewport().rect().contains(diagram.mapFromScene(item.sceneBoundingRect()).boundingRect())
        assert window.stack.geometry().right()<window.width()
        assert not window.grab().isNull()
