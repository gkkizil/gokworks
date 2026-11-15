import json
from pathlib import Path

import pytest

from modules.automatic_drawing.models import ModelInfo, Options, Source, DrawingResult
from modules.automatic_drawing.outputs import (ExistingOutput, OutputTransaction, check_file,
                                              fingerprint, output_stem, safe_name, write_batch_report)


def info(tmp_path):
    source = tmp_path/'Kaynak.SLDPRT'; source.write_bytes(b'original model bytes')
    return ModelInfo(Source(str(source), 'Default'), 'part', 'Kaynak', (100, 50, 10))


def stage(transaction):
    for kind, path in transaction.staged.items():
        path.write_bytes(b'unit-test-artifact-'+kind.encode())


def test_package_is_hidden_until_committed_and_sources_unchanged(tmp_path):
    model = info(tmp_path); original = fingerprint(model.source.path)
    options = Options(output_dir=str(tmp_path/'Output'))
    with OutputTransaction(model, options) as tx:
        stage(tx)
        assert not any(path.exists() for path in tx.targets.values())
        outputs = tx.commit()
        assert all(Path(path).is_file() for path in outputs.values())
    assert fingerprint(model.source.path) == original
    assert not list((tmp_path/'Output').glob('.gokworks*'))
    assert not list((tmp_path/'Output').glob('*.lock'))


def test_failed_generation_preserves_existing_outputs_and_removes_staged_files(tmp_path):
    model = info(tmp_path)
    with pytest.raises(RuntimeError):
        with OutputTransaction(model, Options()) as tx:
            stage(tx)
            raise RuntimeError('simulated COM failure')
    assert sorted(p.name for p in tmp_path.iterdir()) == ['Kaynak.SLDPRT']


def test_case_insensitive_skip_and_unique_name_policies(tmp_path):
    model = info(tmp_path)
    existing = tmp_path/'kaynak-default.slddrw'; existing.write_bytes(b'keep this exact drawing')
    with pytest.raises(ExistingOutput):
        with OutputTransaction(model, Options(existing='skip')):
            pass
    with OutputTransaction(model, Options()) as tx:
        assert tx.targets['slddrw'].name == 'Kaynak-Default-01.SLDDRW'
    assert existing.read_bytes() == b'keep this exact drawing'


def test_publication_race_never_overwrites_even_after_preflight(tmp_path):
    model = info(tmp_path)
    with OutputTransaction(model, Options()) as tx:
        stage(tx)
        target = tx.targets['slddrw']; target.write_bytes(b'another process owns this file')
        with pytest.raises(ExistingOutput):
            tx.commit()
        assert target.read_bytes() == b'another process owns this file'
        assert not tx.targets['report'].exists()
        assert not tx.targets['pdf'].exists()


def test_empty_native_file_blocks_pdf_only_success(tmp_path):
    with OutputTransaction(info(tmp_path), Options()) as tx:
        tx.staged['pdf'].write_bytes(b'PDF only')
        with pytest.raises(RuntimeError, match='SLDDRW'):
            tx.commit()


@pytest.mark.parametrize('name', ('CON', 'COM1', 'aux.txt', 'bad/name:*?', '../..', 'A. '))
def test_windows_names_are_usable_and_cannot_escape_output_directory(name):
    cleaned = safe_name(name)
    assert not any(c in cleaned for c in '<>:"/\\|?*')
    assert cleaned and not cleaned.endswith((' ', '.'))
    assert cleaned.split('.')[0].upper() not in ('CON', 'COM1', 'AUX')


def test_naming_fields_cannot_access_python_attributes_or_format_expressions(tmp_path):
    model = info(tmp_path)
    for pattern in ('{name.__class__}', '{other}', '{name!r}', '{name:1000000000}'):
        with pytest.raises(ValueError): output_stem(model, pattern)
    assert output_stem(model, '{name}-{configuration}') == 'Kaynak-Default'


@pytest.mark.parametrize('kind,content', (('slddrw', b'%PDF-1.7 fake drawing' * 4),
                                        ('pdf', b'not PDF'*10), ('pdf', b'%PDF-1.7 incomplete')))
def test_invalid_or_incomplete_output_headers_are_rejected(tmp_path, kind, content):
    path = tmp_path/('output.'+kind); path.write_bytes(content)
    with pytest.raises(RuntimeError): check_file(path, kind)


def test_batch_report_keeps_failure_stage_and_distinguishes_structural_pass(tmp_path):
    result = DrawingResult(Source('C:/part.sldprt', 'A'), stage='Model açılıyor')
    result.fail('load', 'Missing reference')
    path = tmp_path/'report.json'; write_batch_report(path, [result])
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['summary']['FAIL'] == 1
    assert data['results'][0]['stage'] == 'Model açılıyor'
    assert 'serbest bırakma' in data['scope']


def test_disk_full_while_claiming_output_removes_own_lock(tmp_path, monkeypatch):
    from modules.automatic_drawing import outputs
    model = info(tmp_path)
    fdopen = outputs.os.fdopen
    class FullStream:
        def __init__(self, fd, *args, **kwargs): self.real = fdopen(fd, *args, **kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): self.real.close()
        def write(self, text): raise OSError('simulated disk full')
    monkeypatch.setattr(outputs.os, 'fdopen', FullStream)
    with pytest.raises(OSError, match='disk full'):
        with OutputTransaction(model, Options()): pass
    assert [p.name for p in tmp_path.iterdir()] == ['Kaynak.SLDPRT']
