"""Testleri çalıştır, Word raporu için makine tarafından okunabilir kanıt kaydet."""

from collections import Counter
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import tkinter
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.subcases = []

    def startTest(self, test):
        super().startTest(test)
        self.started = time.perf_counter()
        self.outcome, self.detail = 'passed', ''

    def stopTest(self, test):
        self.records.append({'id': test.id(), 'status': self.outcome, 'detail': self.detail,
                             'seconds': round(time.perf_counter()-self.started, 6)})
        super().stopTest(test)

    def addFailure(self, test, error):
        self.outcome, self.detail = 'failed', self._exc_info_to_string(error, test)
        super().addFailure(test, error)

    def addError(self, test, error):
        self.outcome, self.detail = 'error', self._exc_info_to_string(error, test)
        super().addError(test, error)

    def addSkip(self, test, reason):
        self.outcome, self.detail = 'skipped', reason
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, error):
        self.outcome, self.detail = 'expected_failure', self._exc_info_to_string(error, test)
        super().addExpectedFailure(test, error)

    def addUnexpectedSuccess(self, test):
        self.outcome = 'unexpected_success'
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, error):
        status = 'passed'
        if error is not None:
            status = 'failed' if issubclass(error[0], test.failureException) else 'error'
            self.outcome, self.detail = status, self._exc_info_to_string(error, test)
        self.subcases.append({'test': test.id(), 'parameters': dict(subtest.params), 'status': status})
        super().addSubTest(test, subtest, error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs/reports')
    folder = parser.parse_args().output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    files = [ROOT/'main.py'] + [file for name in ('gui', 'pdf', 'dxf_dwg', 'solidworks', 'k_factor', 'iso_fits')
                              for file in (ROOT/name).rglob('*.py')]
    test_files = list((ROOT/'tests').rglob('*.py'))
    files.append(ROOT/'iso_fits/tables.json')
    data = {
        'started_utc': started.isoformat(), 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(), 'python': platform.python_version(),
        'tk': tkinter.Tcl().call('info', 'patchlevel'),
        'packages': {name: version(name) for name in ('customtkinter', 'Pillow', 'ezdxf', 'python-docx')},
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_modified': True,
        'tests_run': result.testsRun, 'successful': result.wasSuccessful(),
        'outcomes': dict(Counter(item['status'] for item in result.records)),
        'modules': dict(Counter(item['id'].split('.')[0] for item in result.records)),
        'tests': result.records, 'subcases': result.subcases,
        'sha256': {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                   for file in files + test_files},
        'lines': {label: sum(len(file.read_text().splitlines()) for file in selected if file.suffix == '.py')
                  for label, selected in [('application', files), ('tests', test_files)]},
    }
    (folder/'gui-verification-results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
