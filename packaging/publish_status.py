"""Publish build results only to the source branch; never cross-write main."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

RELEASE_START = '<!-- windows-release:start -->'
RELEASE_END = '<!-- windows-release:end -->'


def git(*args, data=None, env=None):
    output = subprocess.check_output(['git', *args], env=env,
        input=data.encode('utf-8') if data is not None else None)
    return output.decode('utf-8').strip()


def release_block(report):
    single = report.get('distribution') == 'onefile'
    instructions = ('**GOKWORKS.exe** tek başına çalışır; yanında klasör gerekmez. ' if single else
                    'ZIP dosyasının tamamını çıkartıp **GOKWORKS/GOKWORKS.exe** dosyasını açın. '
                    '`_internal` klasörü EXE yanında kalmalıdır. ')
    return (f'{RELEASE_START}\n'
            f'**Son başarılı Windows EXE:** [GOKWORKS{(".exe" if single else " paketini")} indir]({report["download_url"]})\n\n'
            +instructions+'Windows 10/11 x64; Python kurulumu gerekmez.\n\n'+
            f'Uygulama kodu: `{report.get("source_commit", report["commit"])[:7]}` · '
            f'[Derleme kaydı]({report["run_url"]}) · '
            '[Paket bilgisi ve SHA256](packaging/latest-windows.json)\n'
            f'{RELEASE_END}')


def publish(report):
    """Add metadata to the latest source-branch tree; preserve unrelated files."""
    branch = os.environ.get('GITHUB_REF', '')
    if not branch.startswith('refs/heads/'):
        raise RuntimeError('Derleme kaydı için kaynak dal refs/heads/ biçiminde gerekli.')
    payload = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    with TemporaryDirectory() as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temporary)/'index')}
        for attempt in range(3):
            git('fetch', '--quiet', 'origin', branch)
            parent = git('rev-parse', 'FETCH_HEAD')
            git('read-tree', parent, env=env)
            files = {'packaging/windows-build-status.json': payload}
            if report['status'] == 'success':
                if not report.get('download_url') or report.get('smoke', {}).get('status') != 'passed':
                    raise RuntimeError('Başarılı paket için indirme bağlantısı ve açılış kontrolü gerekli.')
                readme = git('show', f'{parent}:README.md')
                pattern = re.escape(RELEASE_START)+r'.*?'+re.escape(RELEASE_END)
                readme, count = re.subn(pattern, lambda match: release_block(report), readme, flags=re.S)
                if count != 1:
                    raise RuntimeError('README güncel sürüm alanı bulunamadı veya yinelenmiş.')
                files.update({'packaging/latest-windows.json': payload, 'README.md': readme+'\n'})
            for path, content in files.items():
                blob = git('hash-object', '-w', '--stdin', data=content)
                git('update-index', '--add', '--cacheinfo', '100644', blob, path, env=env)
            tree = git('write-tree', env=env)
            commit = git('-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                'commit-tree', tree, '-p', parent, '-m',
                f'Windows build {report["commit"][:8]}: {report["status"]}')
            push = subprocess.run(['git', 'push', 'origin', f'{commit}:{branch}'], capture_output=True, text=True)
            if push.returncode == 0:
                # Status files retain Unicode; console output must also work on
                # Windows legacy code pages when a diagnostic includes a BOM.
                print(json.dumps(report, ensure_ascii=True, indent=2))
                return
            # Retry only when someone advanced main while this result was saved.
            latest = git('ls-remote', 'origin', branch).split()[0]
            if latest == parent or attempt == 2:
                raise RuntimeError(push.stderr.strip() or 'Derleme kaydı main dalına gönderilemedi.')


def main():
    report = {'commit': os.environ['GITHUB_SHA'], 'status': os.environ['BUILD_STATUS'],
              'run_url': f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
              'download_url': os.environ.get('DIRECT_EXE_URL') or os.environ.get('ARTIFACT_URL', ''),
              'artifact_url': os.environ.get('ARTIFACT_URL', '')}
    report['setup_steps'] = {name: os.environ[key] for name,key in (
        ('checkout','CHECKOUT_OUTCOME'),('python','PYTHON_SETUP_OUTCOME'),('dependencies','DEPENDENCIES_OUTCOME')) if os.environ.get(key)}
    display = Path('windows-display.json')
    if display.exists():
        report['display'] = json.loads(display.read_text(encoding='utf-8'))
    for filename,key in (('windows-previous-failure.log','previous_failure_log_tail'),
                         ('windows-setup.log','setup_log_tail'),('windows-test-setup.log','test_setup_log_tail')):
        path = Path(filename)
        if path.is_file() and (filename == 'windows-previous-failure.log' or report['status'] == 'failure'):
            report[key] = path.read_text(encoding='utf-8',errors='replace')[-16000:]
    exe = Path('dist/GOKWORKS.exe')
    if not exe.exists():exe = Path('dist/GOKWORKS/GOKWORKS.exe')
    if exe.exists():
        report.update(bytes=exe.stat().st_size, sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    smoke = Path('dist/windows-smoke.json')
    if smoke.exists():
        report['smoke'] = json.loads(smoke.read_text(encoding='utf-8'))
        report['distribution'] = report['smoke'].get('distribution', 'onedir')
        report['smoke_scales'] = [json.loads(path.read_text(encoding='utf-8'))
                                  for path in sorted(Path('dist').glob('windows-smoke*.json'))]
    log = Path('windows-build.log')
    if report['status'] != 'success' and log.exists():
        report['build_log_tail'] = log.read_text(encoding='utf-8', errors='replace')[-12000:]
    release_log = Path('windows-release.log')
    if report['status'] != 'success' and release_log.exists():
        report['release_log_tail'] = release_log.read_text(encoding='utf-8', errors='replace')[-4000:]
    tests = Path('windows-tests.xml')
    if tests.exists():
        from xml.etree import ElementTree
        suites = ElementTree.parse(tests).getroot()
        report['regressions'] = [dict(suite.attrib) for suite in suites.iter('testsuite')]
        report['test_failures'] = [dict(name=case.get('classname','')+'.'+case.get('name',''),
                                       message=failure.get('message','')[:600])
                                  for case in suites.iter('testcase') for failure in case.findall('failure')]
        report['test_skips'] = [dict(name=case.get('classname','')+'.'+case.get('name',''),reason=skip.get('message',''))
                               for case in suites.iter('testcase') for skip in case.findall('skipped')]
    tests_log = Path('windows-tests.log')
    if report['status'] == 'failure' and tests_log.exists():
        report['test_log_tail'] = tests_log.read_text(encoding='utf-8', errors='replace')[-22000:]
    publish(report)


if __name__ == '__main__':
    main()
