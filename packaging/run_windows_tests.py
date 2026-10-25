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


def run_tests(root, targets, batch_size=MAX_TESTS_PER_PROCESS):
    if batch_size < 1:
        raise ValueError('Test batch size must be positive.')
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONFAULTHANDLER': '1'}
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
            print(f'Collected {len(nodeids)} tests; at most {batch_size} per native process.', flush=True)
            batches = []
            for selected in test_batches(nodeids, batch_size):
                report = temporary/f'batch-{len(batches)+1}.xml'
                log.write(f'\nNATIVE_BATCH={len(batches)+1} TARGETS={json.dumps(selected)}\n')
                log.flush()
                result = subprocess.run(pytest_command(selected, report), cwd=root,
                                        stdout=log, stderr=subprocess.STDOUT, env=env)
                code = result.returncode
                log.write(f'\nPYTEST_PROCESS_EXIT_CODE={code} (0x{code & 0xffffffff:08X})\n')
                log.flush()
                batches.append((report, code, selected))
                # Keep completed evidence even if a later process is interrupted.
                merge_reports(batches, final_report)
                print(f'Windows batch {len(batches)}: {len(selected)} tests, '
                      f'exit {code} (0x{code & 0xffffffff:08X})', flush=True)
            return 0 if batches and all(code == 0 for _, code, _ in batches) else 1


def main():
    if sys.argv[1:2] == ['--collect-inventory']:
        return collect_inventory(Path(sys.argv[2]), sys.argv[3:])
    return run_tests(Path(__file__).resolve().parents[1], sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
