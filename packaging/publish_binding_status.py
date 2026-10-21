"""Record Windows binding checks; do not export an EXE or edit release metadata."""

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from publish_status import git


def main():
    report = dict(commit=os.environ['GITHUB_SHA'], status=os.environ['BINDING_STATUS'],
        run_url=f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        live_solidworks_tested=False, exe_built=False)
    results = Path('binding-tests.xml')
    if results.is_file():
        suites = ElementTree.parse(results).getroot()
        report['suites'] = [dict(suite.attrib) for suite in suites.iter('testsuite')]
        report['failures'] = [dict(name=case.get('name'), message=failure.get('message', '')[:1500])
                              for case in suites.iter('testcase') for failure in case.findall('failure')]
        report['skips'] = [dict(name=case.get('name'), reason=skip.get('message', ''))
                          for case in suites.iter('testcase') for skip in case.findall('skipped')]
    if report['status'] == 'failure' and Path('binding-tests.log').is_file():
        report['log_tail'] = Path('binding-tests.log').read_text(encoding='utf-8', errors='replace')[-12000:]
    branch = os.environ['GITHUB_REF']
    if not branch.startswith('refs/heads/'):
        raise RuntimeError('Kaynak dal gerekli.')
    content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    with TemporaryDirectory() as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE':str(Path(temporary)/'index')}
        for attempt in range(3):
            git('fetch', '--quiet', 'origin', branch)
            parent = git('rev-parse', 'FETCH_HEAD')
            git('read-tree', parent, env=env)
            blob = git('hash-object', '-w', '--stdin', data=content)
            git('update-index', '--add', '--cacheinfo', '100644', blob, 'modules/naming/examples/windows-bindings.json', env=env)
            tree = git('write-tree', env=env)
            commit = git('-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                'commit-tree', tree, '-p', parent, '-m', f'SolidWorks binding checks {report["commit"][:8]}: {report["status"]}')
            result = subprocess.run(['git', 'push', 'origin', f'{commit}:{branch}'], capture_output=True, text=True)
            if result.returncode == 0:
                print(content);return
            if git('ls-remote', 'origin', branch).split()[0] == parent or attempt == 2:
                raise RuntimeError(result.stderr)


if __name__ == '__main__':
    main()
