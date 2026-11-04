"""Expose existing JUnit failures and native crashes in Actions annotations.

This only reports evidence. The test runner's exit status remains the merge gate.
"""

import argparse
from pathlib import Path
import re
from xml.etree import ElementTree as ET


def escape(message):
    return message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def evidence(folder):
    reports = []
    for path in sorted(folder.rglob('windows-tests.xml')):
        cases = list(ET.parse(path).getroot().iter('testcase'))
        failures = []
        skipped = 0
        for case in cases:
            skipped += case.find('skipped') is not None
            for tag in ('failure', 'error'):
                for item in case.findall(tag):
                    failures.append({'test': case.get('classname', '') + '::' + case.get('name', ''),
                                     'detail': item.text or item.get('message', '')})
        reports.append({'path': str(path.relative_to(folder)), 'total': len(cases), 'skipped': skipped,
                        'failures': failures})
    return reports


def native_errors(folder):
    errors = []
    for path in sorted(folder.rglob('windows-tests.log')):
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        for index, line in enumerate(lines):
            if re.search(r'Fatal Python error|Windows fatal exception|ERROR collecting', line):
                errors.append({'path': str(path.relative_to(folder)),
                               'detail': '\n'.join(lines[max(0, index-8):index+55])})
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    reports = evidence(args.folder)
    if not reports:
        print('::error::No windows-tests.xml evidence was found.')
        return 2
    for report in reports:
        failures = report['failures']
        summary = f"{report['path']}: {report['total']} cases, {len(failures)} failures/errors, {report['skipped']} skipped"
        print('::notice::' + escape(summary))
        if failures:
            text = summary + '\n\n' + '\n\n'.join(item['test'] + '\n' + item['detail'][:5000] for item in failures)
            print('::error::' + escape(text[:24000]))
    for error in native_errors(args.folder)[:4]:
        print('::error::' + escape((error['path'] + '\n' + error['detail'])[:16000]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
