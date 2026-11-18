"""README, the last good package record and the tool registry tell the same story (Ö3)."""
import importlib.util
import json
import re
from pathlib import Path

from gui_qt.app import MODULES

ROOT = Path(__file__).resolve().parents[1]
TURKISH_NUMBERS = {3: 'üç', 4: 'dört', 5: 'beş', 6: 'altı'}


def publisher():
    spec = importlib.util.spec_from_file_location('gokworks_publish', ROOT/'packaging/publish_status.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_readme_download_block_is_generated_from_the_last_good_package_record():
    module = publisher()
    record = json.loads((ROOT/'packaging/latest-windows.json').read_text(encoding='utf-8'))
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    block = re.search(re.escape(module.RELEASE_START)+r'.*?'+re.escape(module.RELEASE_END), readme, flags=re.S).group(0)
    assert block == module.release_block(record)
    assert record['status'] == 'success' and record['smoke']['status'] == 'passed'
    assert re.fullmatch(r'[0-9a-f]{64}', record['sha256']) and record['sha256'] in block
    assert record['source_commit'][:7] in block and record['download_url'] in block
    assert f"Paketteki araç sayısı: {len(record['smoke']['pages'])}" in block
    assert 'regresyon test paketi bu EXE üzerinde çalıştırılmadı' in block       # package-only, said plainly


def test_readme_tool_count_and_groups_come_from_the_module_registry():
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    groups = list(dict.fromkeys(group for _, _, group in MODULES))
    expected = f'Kaynak kodda sol menüde {TURKISH_NUMBERS[len(groups)]} grupta {len(MODULES)} araç bulunur'
    assert expected in readme
    assert not re.search(r'\b(21|22) araç bulunur', readme)


def test_package_facts_do_not_claim_checks_that_were_not_recorded():
    module = publisher()
    bare = dict(commit='a'*40, download_url='https://example.invalid/GOKWORKS.exe', run_url='run', distribution='onefile')
    text = module.release_block(bare)
    assert 'SHA256:' not in text and 'EXE doğrulaması' not in text and 'araç sayısı' not in text
