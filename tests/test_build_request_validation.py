"""A faster EXE may reuse tests only for exactly matching application sources."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('gokworks_build_validation',
    Path(__file__).resolve().parents[1]/'packaging/verify_build_request.py')
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


def valid_run():
    return dict(head_sha='a'*40, head_branch='main', status='completed', conclusion='success',
                repository=dict(full_name='gkkizil/gokworks'), name='Windows BOM and shaft UI')


def test_matching_successful_run_and_documentation_only_delta_are_reusable():
    validation.validate_run(valid_run(), 'a'*40, 'gkkizil/gokworks')
    validation.validate_changes(['docs/bugfixes/result.json', 'README.md',
                                 'packaging/windows-build-request.json'])


@pytest.mark.parametrize('change', ['modules/bom/images.py', 'gui_qt/app.py', 'main.py',
                                    'requirements.txt', 'packaging/build_windows.py', 'assets/logo.png'])
def test_application_dependency_or_builder_changes_require_fresh_tests(change):
    with pytest.raises(RuntimeError, match='tam doğrulama'):
        validation.validate_changes([change])


@pytest.mark.parametrize('field,value', [('head_sha','b'*40), ('head_branch','release'),
                                        ('status','in_progress'), ('conclusion','failure'),
                                        ('name','Unknown workflow'),
                                        ('repository',dict(full_name='someone/else'))])
def test_failed_unfinished_other_branch_or_other_source_run_is_rejected(field, value):
    run = valid_run(); run[field] = value
    with pytest.raises(RuntimeError):
        validation.validate_run(run, 'a'*40, 'gkkizil/gokworks')
