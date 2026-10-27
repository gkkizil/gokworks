"""Reuse successful Windows checks only when their application source is unchanged."""

import json
import os
from pathlib import Path
import re
import subprocess

REQUIRED = {'Windows BOM and shaft UI', 'Windows shaft bridge'}
METADATA = {
    'README.md', '.github/workflows/windows-exe.yml',
    'packaging/windows-build-request.json', 'packaging/windows-build-status.json',
    'packaging/latest-windows.json', 'packaging/publish_status.py',
    'packaging/verify_build_request.py', 'tests/test_build_request_validation.py',
    # Human-readable verification and its CI receipt; neither is bundled or loaded.
    'docs/dxf-3d-preview/preview-before-save.md',
    'docs/dxf-3d-preview/before-save-windows-check.json',
}


def validate_run(run, source, repository):
    if (run.get('head_sha') != source or run.get('head_branch') != 'main'
        or run.get('status') != 'completed' or run.get('conclusion') != 'success'
        or run.get('repository', {}).get('full_name', '').lower() != repository.lower()
        or run.get('name') not in REQUIRED):
        raise RuntimeError('Windows doğrulaması kaynak sürümüyle eşleşmiyor veya başarılı değil.')


def validate_changes(paths):
    changed = [p for p in paths if p not in METADATA and not p.startswith('docs/bugfixes/')]
    if changed:
        raise RuntimeError('Test edilen kaynak değişmiş; tam doğrulama gerekli: '+', '.join(changed[:8]))


def main():
    root = Path(__file__).resolve().parents[1]
    request = json.loads((root/'packaging/windows-build-request.json').read_text(encoding='utf-8'))
    profile = request.get('validation_profile', 'full')
    if profile not in ('full', 'verified-source'):
        raise RuntimeError('Bilinmeyen Windows doğrulama profili.')
    reuse = profile == 'verified-source'
    if reuse:
        source = request.get('verified_source_commit', '')
        if not re.fullmatch(r'[0-9a-f]{40}', source):
            raise RuntimeError('Doğrulanmış kaynak commit kimliği gerekli.')
        repository = os.environ['GITHUB_REPOSITORY']
        runs = []
        for run_id in request.get('validation_runs', []):
            if type(run_id) is not int or run_id <= 0:
                raise RuntimeError('Geçersiz Windows doğrulama kaydı.')
            run = json.loads(subprocess.check_output(
                ['gh', 'api', f'repos/{repository}/actions/runs/{run_id}'], text=True, encoding='utf-8'))
            validate_run(run, source, repository)
            runs.append({k: run[k] for k in ('id', 'name', 'head_sha', 'conclusion', 'html_url')})
        if {r['name'] for r in runs} != REQUIRED or len(runs) != len(REQUIRED):
            raise RuntimeError('İki bağımsız başarılı Windows doğrulaması gerekli.')
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', source], cwd=root, check=True)
        changes = subprocess.check_output(['git', 'diff', '--name-only', source, 'HEAD'], cwd=root, text=True).splitlines()
        validate_changes(changes)
        evidence = dict(profile=profile, verified_source_commit=source, runs=runs,
                        note='Unchanged application source; focused packaging/DXF tests and frozen EXE smoke run again.')
        (root/'windows-reused-validation.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
        print('Doğrulanmış uygulama kaynağı aynı; önceki Windows testleri yeniden kullanılacak.')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('reuse='+str(reuse).lower()+'\n')


if __name__ == '__main__':
    main()
