"""Run every collected test in bounded processes and preserve native failures.

The desktop normally creates one QApplication and one main window. A single
pytest process instead constructs hundreds of complete application windows;
native Qt state from earlier tests can then abort the process before pytest
writes its failure report. Collect once, run all node IDs in small fresh
processes, and combine their JUnit reports without losing failed/crashed batches.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET


MAX_TESTS_PER_PROCESS = 32
MAX_GUI_TESTS_PER_PROCESS = 8
# An ordinary assertion/timeout failure (pytest exit 1 with a complete report) is
# re-run once in a fresh process: timing-sensitive Qt/file-system tests on shared
# Windows runners can fail without a product fault. Native exits are never retried.
# More than a few failing batches is a real regression, not noise: those stay failed.
MAX_RETRIED_BATCHES = 3


def complete_report(report):
    try:
        root = ET.parse(report).getroot()
    except (ET.ParseError, OSError):
        return False
    return bool([root] if root.tag == 'testsuite' else root.findall('testsuite'))


def test_batches(nodeids, batch_size):
    """Keep all tests in order; bound repeated complete Qt window lifetimes.

    Native Windows Qt can fast-fail during teardown after repeated complete
    application windows in one QApplication. Full-app workflow cases therefore
    get their own process; other GUI cases remain in bounded small batches.
    The product creates one main window per process. Fresh processes avoid
    accumulating state from unrelated full-app workflow cases;
    native exits still fail the gate and are never retried or ignored.
    """
    selected = []; gui = False
    for nodeid in nodeids:
        filename = nodeid.split('::', 1)[0].rsplit('/', 1)[-1]
        if filename == 'test_qt_workflows.py':
            if selected:
                yield selected; selected = []; gui = False
            yield [nodeid]
            continue
        heavy = any(token in filename for token in ('gui', '_ui', '_qt', 'compact', 'workbench', 'repository_structure'))
        limit = min(batch_size, MAX_GUI_TESTS_PER_PROCESS) if gui or heavy else batch_size
        if selected and len(selected) >= limit:
            yield selected; selected = []; gui = False
        selected.append(nodeid); gui |= heavy
    if selected: yield selected


def test_weight(nodeid):
    """Rough relative cost: full-app workflows get their own process, GUI tests build windows."""
    filename = nodeid.split('::', 1)[0].rsplit('/', 1)[-1]
    if filename == 'test_qt_workflows.py':
        return 6
    return 3 if any(token in filename for token in ('gui', '_ui', '_qt', 'compact', 'workbench')) else 1


def select_shard(nodeids, shard, shards):
    """Deterministic part ``shard`` of ``shards``: whole test files, balanced by weight.

    Files are assigned heaviest first to the currently lightest part (ties by name), so
    every part is reproducible from the same inventory, no file is split between
    processes of different parts and every collected test lands in exactly one part.
    The original collection order is kept inside each part.
    """
    if not 1 <= shard <= shards:
        raise ValueError(f'Invalid shard {shard}/{shards}.')
    weights = {}
    for nodeid in nodeids:
        filename = nodeid.split('::', 1)[0]
        weights[filename] = weights.get(filename, 0) + test_weight(nodeid)
    loads = [0] * shards; owner = {}
    for filename in sorted(weights, key=lambda name: (-weights[name], name)):
        part = min(range(shards), key=lambda index: (loads[index], index))
        owner[filename] = part; loads[part] += weights[filename]
    return [nodeid for nodeid in nodeids if owner[nodeid.split('::', 1)[0]] == shard - 1]


def parse_shard(text):
    try:
        shard, shards = (int(value) for value in text.split('/'))
    except ValueError:
        raise ValueError(f'Shard must look like 2/3, not {text!r}.') from None
    if not 1 <= shard <= shards:
        raise ValueError(f'Invalid shard {text}.')
    return shard, shards


def pytest_command(targets, report):
    command = [sys.executable, '-X', 'faulthandler', '-m', 'pytest', '-vv',
               '--capture=tee-sys',
               '--timeout=60', '--timeout-method=thread',
               '-o', 'faulthandler_timeout=60', '-o', 'faulthandler_exit_on_timeout=true',
               f'--junitxml={report}', *targets]
    return command


def collect_inventory(destination, targets):
    import pytest

    class Inventory:
        def pytest_collection_finish(self, session):
            destination.write_text(json.dumps([item.nodeid for item in session.items],
                                               ensure_ascii=False), encoding='utf-8')

    return int(pytest.main(['--collect-only', '-q', *targets], plugins=[Inventory()]))


def merge_reports(batches, destination):
    result = ET.Element('testsuites')
    for index, (report, code, targets) in enumerate(batches, 1):
        valid = False
        if report.exists():
            try:
                parsed = ET.parse(report).getroot()
                suites = [parsed] if parsed.tag == 'testsuite' else list(parsed.findall('testsuite'))
                for suite in suites:
                    result.append(suite)
                valid = bool(suites)
            except ET.ParseError:
                pass
        # A fatal native exit can leave no XML, or XML containing only passes.
        # It must remain a failed gate and appear in the downloadable report.
        if not valid or code not in (0, 1):
            suite = ET.SubElement(result, 'testsuite', name=f'native-batch-{index}',
                                  tests='1', failures='1', errors='0', skipped='0')
            case = ET.SubElement(suite, 'testcase', classname='windows_test_process',
                                 name=f'batch_{index}')
            failure = ET.SubElement(case, 'failure',
                message=f'pytest exit {code} (0x{code & 0xffffffff:08X}); complete report: {valid}')
            failure.text = '\n'.join(targets)
    ET.ElementTree(result).write(destination, encoding='utf-8', xml_declaration=True)


def run_tests(root, targets, batch_size=MAX_TESTS_PER_PROCESS, shard=(1, 1)):
    if batch_size < 1:
        raise ValueError('Test batch size must be positive.')
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONFAULTHANDLER': '1',
           'PYTHONUNBUFFERED': '1',
           'GOKWORKS_NATIVE_TEST_LOG': str(root/'windows-qt-native.log')}
    final_report = root/'windows-tests.xml'
    final_report.unlink(missing_ok=True)
    with (root/'windows-tests.log').open('w', encoding='utf-8') as log:
        with TemporaryDirectory(prefix='gokworks-pytest-') as folder:
            temporary = Path(folder)
            inventory = temporary/'inventory.json'
            collection = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                '--collect-inventory', str(inventory), *targets], cwd=root, stdout=log,
                stderr=subprocess.STDOUT, env=env)
            if collection.returncode or not inventory.exists():
                merge_reports([(temporary/'missing.xml', collection.returncode or 2,
                                targets or ['full collection'])], final_report)
                print('Windows pytest collection failed; see windows-tests.log.', flush=True)
                return 1
            nodeids = json.loads(inventory.read_text(encoding='utf-8'))
            total = len(nodeids)
            if shard[1] > 1:
                nodeids = select_shard(nodeids, *shard)
                log.write(f'\nSHARD={shard[0]}/{shard[1]} TESTS={len(nodeids)} OF={total}\n')
            print(f'Collected {total} tests; part {shard[0]}/{shard[1]} runs {len(nodeids)}, '
                  f'at most {batch_size} per native process.', flush=True)
            batches = []; flaky = []; retried = 0
            for selected in test_batches(nodeids, batch_size):
                report = temporary/f'batch-{len(batches)+1}.xml'
                log.write(f'\nNATIVE_BATCH={len(batches)+1} TARGETS={json.dumps(selected)}\n')
                log.flush()
                result = subprocess.run(pytest_command(selected, report), cwd=root,
                                        stdout=log, stderr=subprocess.STDOUT, env=env)
                code = result.returncode
                log.write(f'\nPYTEST_PROCESS_EXIT_CODE={code} (0x{code & 0xffffffff:08X})\n')
                log.flush()
                if code == 1 and complete_report(report) and retried < MAX_RETRIED_BATCHES:
                    retried += 1
                    retry = temporary/f'batch-{len(batches)+1}-retry.xml'
                    log.write(f'\nRETRY_BATCH={len(batches)+1} TARGETS={json.dumps(selected)}\n'); log.flush()
                    second = subprocess.run(pytest_command(selected, retry), cwd=root,
                                            stdout=log, stderr=subprocess.STDOUT, env=env).returncode
                    log.write(f'\nRETRY_PROCESS_EXIT_CODE={second}\n'); log.flush()
                    if second == 0 and complete_report(retry):
                        flaky.append(selected); report, code = retry, 0
                        print(f'::warning::Windows batch {len(batches)+1} passed only on retry (unstable test): '
                              + ', '.join(selected), flush=True)
                batches.append((report, code, selected))
                # Keep completed evidence even if a later process is interrupted.
                merge_reports(batches, final_report)
                print(f'Windows batch {len(batches)}: {len(selected)} tests, '
                      f'exit {code} (0x{code & 0xffffffff:08X})', flush=True)
            (root/'windows-flaky.json').write_text(json.dumps(flaky, ensure_ascii=False, indent=1), encoding='utf-8')
            if not batches:
                # An empty part is legitimate (fewer files than parts) but must still leave a valid report.
                merge_reports([], final_report)
                return 0 if shard[1] > 1 and total else 1
            return 0 if all(code == 0 for _, code, _ in batches) else 1


def main():
    if sys.argv[1:2] == ['--collect-inventory']:
        return collect_inventory(Path(sys.argv[2]), sys.argv[3:])
    arguments = sys.argv[1:]; shard = (1, 1)
    if arguments[:1] == ['--shard']:
        shard = parse_shard(arguments[1]); arguments = arguments[2:]
    return run_tests(Path(__file__).resolve().parents[1], arguments, shard=shard)


if __name__ == '__main__':
    raise SystemExit(main())
