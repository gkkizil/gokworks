"""Publish small build metadata; binaries remain in expiring Actions artifacts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


def git(*args, data=None):
    # Binary stdin keeps Windows newline translation out of mktree filenames.
    output = subprocess.check_output(['git', *args], input=data.encode('utf-8') if data is not None else None)
    return output.decode('utf-8').strip()


def main():
    branch = 'refs/heads/codex/windows-build-status'
    report = {'commit': os.environ['GITHUB_SHA'], 'status': os.environ['BUILD_STATUS'],
              'run_url': f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
              'download_url': os.environ.get('ARTIFACT_URL', '')}
    exe = Path('dist/GOKWORKS.exe')
    if exe.exists():
        report.update(bytes=exe.stat().st_size, sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    smoke = Path('dist/windows-smoke.json')
    if smoke.exists():
        report['smoke'] = json.loads(smoke.read_text(encoding='utf-8'))
    log = Path('windows-build.log')
    if report['status'] != 'success' and log.exists():
        report['build_log_tail'] = log.read_text(encoding='utf-8', errors='replace')[-12000:]
    data = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    parent = []
    if git('ls-remote', 'origin', branch):
        git('fetch', 'origin', branch)
        parent = ['-p', git('rev-parse', 'FETCH_HEAD')]
    blob = git('hash-object', '-w', '--stdin', data=data)
    tree = git('mktree', data=f'100644 blob {blob}\tlatest.json\n')
    commit = git('-c', 'user.name=github-actions[bot]', '-c',
                 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                 'commit-tree', tree, *parent, '-m', f'Windows build {report["commit"][:8]}: {report["status"]}')
    git('push', 'origin', f'{commit}:{branch}')
    print(data)


if __name__ == '__main__':
    main()
