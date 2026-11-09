"""The native runner must retain every case and never turn a process crash green."""

import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET


spec = importlib.util.spec_from_file_location('native_test_runner',
    Path(__file__).resolve().parents[1]/'packaging/run_windows_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_gui_isolation_preserves_every_node_once_in_original_order():
    nodes=[f'tests/test_pure.py::test_{i}' for i in range(20)]
    nodes += [f'tests/test_qt_workflows.py::test_{i}' for i in range(35)]
    nodes += [f'modules/iso_fits/tests/test_diagram_ui.py::test_{i}' for i in range(11)]
    nodes += [f'tests/test_fusion_workbench.py::test_{i}' for i in range(15)]
    nodes += [f'tests/test_engine.py::test_{i}' for i in range(50)]
    batches=list(runner.test_batches(nodes,32))
    assert [node for batch in batches for node in batch]==nodes
    assert all(len(batch)<=32 for batch in batches)
    assert all(len(batch)<=8 for batch in batches if any('_qt' in n or '_ui' in n or 'workbench' in n for n in batch))
    assert list(runner.test_batches(nodes,1))==[[node] for node in nodes]


def test_full_application_workflows_each_get_a_fresh_process():
    before = 'tests/test_engine.py::test_before'
    workflows = [f'tests/test_qt_workflows.py::test_window[{i}]' for i in range(12)]
    after = 'modules/shaft_generator/tests/test_ui.py::test_after'
    nodes = [before, *workflows, after]
    batches = list(runner.test_batches(nodes, 32))
    assert [node for batch in batches for node in batch] == nodes
    assert batches == [[before], *[[node] for node in workflows], [after]]


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


def test_a_test_failing_once_is_retried_once_and_recorded_as_unstable(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_sample.py').write_text(
        'from pathlib import Path\n'
        'def test_steady(): assert True\n'
        'def test_unstable():\n'
        '    marker = Path(__file__).with_name("seen")\n'
        '    first = not marker.exists(); marker.write_text("1")\n'
        '    assert not first, "fails only the first time"\n')
    assert runner.run_tests(tmp_path,[]) == 0
    report=ET.parse(tmp_path/'windows-tests.xml').getroot()
    assert not list(report.iter('failure')) and len(list(report.iter('testcase'))) == 2
    import json
    assert json.loads((tmp_path/'windows-flaky.json').read_text()) == [['test_sample.py::test_steady','test_sample.py::test_unstable']]
    assert 'RETRY_BATCH=1' in (tmp_path/'windows-tests.log').read_text()


def test_a_consistent_failure_still_fails_after_its_single_retry(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_sample.py').write_text('def test_broken(): assert False\n')
    assert runner.run_tests(tmp_path,[]) == 1
    log=(tmp_path/'windows-tests.log').read_text()
    assert log.count('RETRY_BATCH=') == 1 and len(list(ET.parse(tmp_path/'windows-tests.xml').getroot().iter('failure'))) == 1


def test_shards_split_whole_files_deterministically_and_cover_every_test_once():
    nodes = [f'tests/test_qt_workflows.py::test_{i}' for i in range(30)]
    nodes += [f'modules/m{k}/tests/test_ui.py::test_{i}' for k in range(8) for i in range(12)]
    nodes += [f'modules/m{k}/tests/test_engine.py::test_{i}' for k in range(8) for i in range(25)]
    parts = [runner.select_shard(nodes, shard, 3) for shard in (1, 2, 3)]
    assert sorted(node for part in parts for node in part) == sorted(nodes)
    assert parts == [runner.select_shard(nodes, shard, 3) for shard in (1, 2, 3)]
    for part in parts:
        assert part == [node for node in nodes if node in part]                 # collection order kept
    owners = {node.split('::')[0]: index for index, part in enumerate(parts) for node in part}
    assert all(owners[node.split('::')[0]] == index for index, part in enumerate(parts) for node in part)
    loads = [sum(runner.test_weight(node) for node in part) for part in parts]
    assert max(loads) - min(loads) <= max(runner.test_weight(n) for n in nodes) * 30
    assert runner.select_shard(nodes, 1, 1) == nodes


def test_shard_arguments_are_validated():
    assert runner.parse_shard('2/3') == (2, 3)
    for text in ('0/3', '4/3', 'x', '1-3'):
        try:
            runner.parse_shard(text)
        except ValueError:
            continue
        raise AssertionError(text)


def test_runner_runs_only_its_part_and_an_empty_part_still_reports(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_a.py').write_text('def test_a(): assert True\n')
    (tmp_path/'test_b.py').write_text('def test_b1(): assert True\ndef test_b2(): assert True\n')
    names = []
    for shard in (1, 2, 3):
        assert runner.run_tests(tmp_path, [], shard=(shard, 3)) == 0
        names.append([case.get('name') for case in ET.parse(tmp_path/'windows-tests.xml').getroot().iter('testcase')])
    assert sorted(sum(names, [])) == ['test_a', 'test_b1', 'test_b2'] and [] in names


def test_failing_retries_also_count_towards_the_retry_limit(tmp_path):
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    for index in range(runner.MAX_RETRIED_BATCHES + 2):
        (tmp_path/f'test_{index}.py').write_text('def test_broken(): assert False\n')
    assert runner.run_tests(tmp_path, [], batch_size=1) == 1
    assert (tmp_path/'windows-tests.log').read_text().count('RETRY_BATCH=') == runner.MAX_RETRIED_BATCHES
