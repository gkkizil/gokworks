"""Runtime data files must be in the PyInstaller --add-data list (the EXE has no source tree)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'modules/weight/data/sections.json',
    'modules/iso_fits/tables.json',
    'modules/dfm_analyzer/profiles/geometry_basic.json',
    'modules/dfm_analyzer/profiles/laser_generic.json',
    'modules/belt_drive/catalog/data/tosyali-user-pdf.json',
    'modules/belt_drive/catalog/data/tosyali-import-audit.json',
    'modules/belt_drive/catalog/data/tosyali-v-reference.json',
    'modules/belt_drive/catalog/data/optibelt-sk-reference-2018.json',
    'modules/belt_drive/examples/automatic-synthetic-catalog.json',
    'docs/unfolding/source_inventory.json',
    'docs/unfolding/examples/source_models.json',
    'examples/ornek_pres_unitesi.gwhyd',
)


def packaged():
    text = (ROOT / 'packaging/build_windows.py').read_text(encoding='utf-8')
    return {source: target for source, target in re.findall(r'ROOT / "([^"]+)"\}\;([^\']+)\'', text)}


def test_runtime_data_files_are_packaged_next_to_their_module():
    files = packaged()
    for path in REQUIRED:
        assert path in files, f'{path} EXE paketine eklenmemiş'
        assert files[path] == str(Path(path).parent).replace('\\', '/'), path
        assert (ROOT / path).is_file(), path


def test_every_listed_file_exists():
    for path in packaged():
        assert (ROOT / path).exists(), path
