"""QA (2026-11-03): a damaged settings.json never stops the app or a page opening.

Every key the application stores is overwritten with one hostile JSON type at a
time (all keys together, to keep the run short), then every page is opened.
Raw corruption (empty, truncated, binary, non-object root) is covered too.
"""

import json
import sys
import traceback

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QMessageBox

from gui_qt.app import MODULES, MainWindow, create_application

KEYS = ('appearance', 'bolt_pitch', 'bolt_unit', 'bolt_view', 'cad_converter_source_folder',
        'dxf_dwg_group_instances', 'dxf_dwg_preview_before_export', 'gdt_kind', 'inspector_visible',
        'inspector_width', 'kr_manual_rows', 'layout/bolt_inputs_hidden', 'layout/bolt_split',
        'layout/gdt_inputs_hidden', 'layout/gdt_split', 'layout/iso_inputs_hidden', 'layout/iso_split',
        'layout/weight_inputs_hidden', 'layout/weight_split', 'mode', 'naming_destination', 'naming_package',
        'naming_parent', 'navigation_groups', 'nesting_stock_library', 'page_transitions', 'pdf_options',
        'profile_cutting_scan_details', 'profile_property_mapping', 'sidebar_collapsed', 'torque_pitch',
        'weight_b', 'weight_category', 'weight_dims/Sac levha', 'weight_kind', 'weight_material',
        'weight_profile', 'weight_scrap', 'weight_t', 'weight_vat', 'weight_worklist')
HOSTILE = (None, 'x', 10**30, [0, 0], {'a': [1]}, True)


@pytest.fixture
def unhandled(monkeypatch):
    """Unhandled exceptions and any message box (e.g. 'Ayarlar kaydedilemedi' on close)."""
    seen = []
    monkeypatch.setattr(sys, 'excepthook', lambda kind, value, tb: seen.append(
        ''.join(traceback.format_exception(kind, value, tb))))
    for name in ('information', 'warning', 'critical', 'question'):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda parent, title, text, *a, **k: seen.append(f'{title}: {text}') or QMessageBox.No))
    return seen


def _open_every_page(qtbot, path):
    create_application([])
    window = MainWindow(path)
    window.resize(1366, 768)
    window.show()
    try:
        for key, _, _ in MODULES:
            window.navigate(key)
        assert window.isVisible()
    finally:
        qtbot.wait(20)            # let pending zero-delay layout timers run first
        window.close()
        qtbot.wait(20)
        window.deleteLater()
        # Free the window now; live windows from earlier cases would make every
        # later theme application (app-wide stylesheet) slower.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize('value', HOSTILE, ids=['none', 'text', 'huge_int', 'list', 'dict', 'bool'])
def test_every_key_with_a_wrong_type_still_opens_every_page(qtbot, tmp_path, unhandled, value):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({key: value for key in KEYS}), encoding='utf-8')
    _open_every_page(qtbot, path)
    assert not unhandled, unhandled[0]


@pytest.mark.parametrize('raw', [b'', b'{', b'[]', b'null', b'"x"', b'\xff\xfe\x00garbage', b'{"a":NaN}', b'1e999'],
                         ids=['empty', 'truncated', 'list_root', 'null_root', 'string_root', 'binary', 'nan', 'infinite'])
def test_raw_corruption_still_opens_every_page(qtbot, tmp_path, unhandled, raw):
    path = tmp_path / 'settings.json'
    path.write_bytes(raw)
    _open_every_page(qtbot, path)
    assert not unhandled, unhandled[0]


def test_nan_in_settings_is_backed_up_and_never_blocks_saving(qtbot, tmp_path, unhandled):
    """json.loads accepts NaN, save_settings refuses it: every exit used to warn
    'Ayarlar kaydedilemedi' and settings were never saved again."""
    path = tmp_path / 'settings.json'
    path.write_text('{"appearance": "light", "weight_scrap": NaN}', encoding='utf-8')
    _open_every_page(qtbot, path)
    assert not unhandled, unhandled[0]
    assert json.loads(path.read_text(encoding='utf-8'))                       # saved, valid JSON
    backups = list(tmp_path.glob('settings.invalid-*.json'))
    assert len(backups) == 1 and 'NaN' in backups[0].read_text(encoding='utf-8')
