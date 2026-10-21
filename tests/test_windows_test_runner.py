"""The native runner must retain every case and never turn a process crash green."""

import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET


spec = importlib.util.spec_from_file_location('native_test_runner',
    Path(__file__).resolve().parents[1]/'packaging/run_windows_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_reports_retain_passes_failures_and_missing_native_batch(tmp_path):
    passed = tmp_path/'pass.xml'
    passed.write_text('<testsuites><testsuite tests="1" failures="0">'
                      '<testcase name="passes"/></testsuite></testsuites>')
    failed = tmp_path/'fail.xml'
    failed.write_text('<testsuites><testsuite tests="1" failures="1">'
                      '<testcase name="fails"><failure message="bad layout"/>'
                      '</testcase></testsuite></testsuites>')
    target = tmp_path/'combined.xml'
    runner.merge_reports([(passed,0,['test_pass']), (failed,1,['test_fail']),
        (tmp_path/'missing.xml',3221226505,['test_native'])], target)
    suites = ET.parse(target).getroot()
    assert len(suites.findall('testsuite')) == 3
    assert [item.get('name') for item in suites.iter('testcase')] == ['passes','fails','batch_3']
    failures = list(suites.iter('failure'))
    assert len(failures) == 2
    assert 'C0000409' in failures[-1].get('message')
    assert failures[-1].text == 'test_native'


def test_incomplete_or_invalid_report_is_a_failure_even_with_zero_exit(tmp_path):
    report=tmp_path/'partial.xml';report.write_text('<testsuites>')
    target=tmp_path/'combined.xml'
    runner.merge_reports([(report,0,['test_interrupted'])],target)
    assert len(list(ET.parse(target).getroot().iter('failure'))) == 1


def test_runner_collects_all_cases_and_reports_failed_batch_without_skipping_following_cases(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_sample.py').write_text(
        'def test_first(): assert True\n'
        'def test_second(): assert False, "intentional test failure"\n'
        'def test_third(): assert True\n')
    assert runner.run_tests(tmp_path,[],batch_size=1) == 1
    report=ET.parse(tmp_path/'windows-tests.xml').getroot()
    assert [case.get('name') for case in report.iter('testcase')] == [
        'test_first','test_second','test_third']
    assert len(list(report.iter('failure'))) == 1
    log=(tmp_path/'windows-tests.log').read_text()
    assert log.count('NATIVE_BATCH=') == 3 and 'intentional test failure' in log


def test_collection_error_replaces_previous_success_report(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'windows-tests.xml').write_text('<testsuites/>')
    assert runner.run_tests(tmp_path,['missing_test.py']) == 1
    assert len(list(ET.parse(tmp_path/'windows-tests.xml').getroot().iter('failure'))) == 1


def test_display_selection_requires_real_wide_desktop_and_avoids_extreme_modes():
    spec = importlib.util.spec_from_file_location('native_display',
        Path(__file__).resolve().parents[1]/'packaging/configure_windows_display.py')
    display = importlib.util.module_from_spec(spec);spec.loader.exec_module(display)
    assert display.select_mode([(1024,768,32,60),(1280,1024,32,60)]) is None
    assert display.select_mode([(1024,768,32,60),(1920,1080,32,60),
        (3840,2160,32,60),(16384,8192,32,60)]) == (3840,2160,32,60)
    assert display.select_mode([(1920,1080,16,60)]) is None
