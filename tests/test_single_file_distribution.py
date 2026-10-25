"""Single-file runtime notices and backward-compatible release instructions."""

import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest

from gui_qt.licenses import LicensesDialog, license_files, export_licenses
from solidworks.runtime import configure_libraries


def test_embedded_notice_view_and_archive_include_complete_text(qtbot, tmp_path):
    dialog = LicensesDialog()
    qtbot.addWidget(dialog)
    assert dialog.picker.currentText() == 'THIRD_PARTY_NOTICES.md'
    assert 'LGPL' in dialog.text.toPlainText()
    files = license_files()
    archive = tmp_path/'notices.zip'
    export_licenses(archive, files)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None and set(bundle.namelist()) == set(files)
        for name, source in files.items():assert bundle.read(name) == source.read_bytes()


def test_user_selected_compatible_libraries_precede_bundle_without_changing_default(tmp_path, monkeypatch):
    monkeypatch.delenv('GOKWORKS_LIBRARY_DIR', raising=False)
    original = list(sys.path)
    configure_libraries()
    assert sys.path == original
    monkeypatch.setenv('GOKWORKS_LIBRARY_DIR', str(tmp_path))
    with pytest.raises(RuntimeError, match='PySide6'):configure_libraries()
    for name in ('PySide6', 'shiboken6'):
        (tmp_path/name).mkdir();(tmp_path/name/'__init__.py').write_text('')
    monkeypatch.setattr(sys, 'path', list(sys.path))
    configure_libraries()
    assert sys.path[0] == str(tmp_path.resolve())


def test_onefile_release_instructions_do_not_require_external_folder():
    spec = importlib.util.spec_from_file_location('gokworks_publish', Path(__file__).resolve().parents[1]/'packaging/publish_status.py')
    publisher = importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
    report = dict(commit='a'*40, download_url='https://github.com/gkkizil/gokworks/releases/download/test/GOKWORKS.exe',run_url='run',distribution='onefile')
    text = publisher.release_block(report)
    assert 'GOKWORKS.exe' in text and 'tek başına' in text and '_internal' not in text
    report['distribution'] = 'onedir'
    assert '_internal' in publisher.release_block(report)


def test_optional_shapely_geos_replacement_and_embedded_license(tmp_path,monkeypatch):
    monkeypatch.delenv('GOKWORKS_LIBRARY_DIR',raising=False)
    monkeypatch.setenv('GOKWORKS_GEOMETRY_DIR',str(tmp_path))
    with pytest.raises(RuntimeError,match='GEOS'): configure_libraries()
    (tmp_path/'shapely').mkdir(); (tmp_path/'shapely/__init__.py').write_text('')
    monkeypatch.setattr(sys,'path',list(sys.path)); configure_libraries()
    assert sys.path[0] == str(tmp_path.resolve())
    assert 'nesting/Shapely-LICENSE_GEOS' in license_files()


def test_native_failure_status_keeps_crash_context_even_when_tail_has_moved_on(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('gokworks_failure_publish',
        Path(__file__).resolve().parents[1]/'packaging/publish_status.py')
    publisher = importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
    monkeypatch.chdir(tmp_path)
    for key, value in dict(GITHUB_SHA='a'*40, BUILD_STATUS='failure',
                           GITHUB_REPOSITORY='gkkizil/gokworks', GITHUB_RUN_ID='123').items():
        monkeypatch.setenv(key, value)
    (tmp_path/'windows-tests.log').write_text(
        'NATIVE_BATCH=7 TARGETS=["test_background_preview"]\n'
        'test_background_preview PASSED\n'
        'PYTEST_PROCESS_EXIT_CODE=3221226505 (0xC0000409)\n' +
        'later successful batch\n'*1500, encoding='utf-8')
    reports = []
    monkeypatch.setattr(publisher, 'publish', reports.append)
    publisher.main()
    assert len(reports) == 1
    assert 'test_background_preview' in reports[0]['native_failure_context']
    assert '0xC0000409' in reports[0]['native_failure_context']
    assert 'test_background_preview' not in reports[0]['test_log_tail']
