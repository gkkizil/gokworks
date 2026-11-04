"""CI reporting must preserve failure evidence without changing the merge gate."""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / '.github/scripts/report-agent-validation.py'
spec = importlib.util.spec_from_file_location('agent_validation_report', SOURCE)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_junit_reports_keep_test_identity_message_skips_and_native_exit(tmp_path):
    folder = tmp_path / 'agent-validation-18-head'
    folder.mkdir()
    (folder / 'windows-tests.xml').write_text('''<testsuites><testsuite>
      <testcase classname="module" name="pass"/>
      <testcase classname="module" name="skip"><skipped/></testcase>
      <testcase classname="module" name="assertion"><failure>expected 2, got 1</failure></testcase>
      <testcase classname="windows_test_process" name="batch_1"><failure message="exit 3221225477"/></testcase>
    </testsuite></testsuites>''')
    result, = report.evidence(tmp_path)
    assert result['total'] == 4 and result['skipped'] == 1
    assert result['path'] == 'agent-validation-18-head/windows-tests.xml'
    assert result['failures'] == [
        dict(test='module::assertion', detail='expected 2, got 1'),
        dict(test='windows_test_process::batch_1', detail='exit 3221225477'),
    ]


def test_native_crash_log_includes_stack_context(tmp_path):
    (tmp_path / 'windows-tests.log').write_text(
        'NATIVE_BATCH=7\nWindows fatal exception: access violation\nui.py, line 42\n')
    error, = report.native_errors(tmp_path)
    assert error['path'] == 'windows-tests.log'
    assert 'NATIVE_BATCH=7' in error['detail'] and 'ui.py, line 42' in error['detail']


def test_github_annotation_escapes_multiline_and_percent():
    assert report.escape('100%\r\n::notice::') == '100%25%0D%0A::notice::'
