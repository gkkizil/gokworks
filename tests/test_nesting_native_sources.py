"""The distributed native core has matching source and original license notices."""
import hashlib
import json
from pathlib import Path
import tomllib


def test_sparrow_locked_sources_and_mpl_source_are_distributed_with_their_notices():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'packaging/licenses/nesting/sparrow'
    inventory = json.loads((folder / 'source-inventory.json').read_text())
    lock = tomllib.loads((folder / 'spyrrow-0.10.0-Cargo.lock').read_text())
    assert {(p['name'], p['version']) for p in inventory} == {(p['name'], p['version']) for p in lock['package']}
    for package in inventory:
        assert package['notices'], package['name']
        assert all((folder / name).is_file() for name in package['notices'])
    jagua = next(p for p in inventory if p['name'] == 'jagua-rs')
    source = folder / f"jagua-rs-{jagua['version']}-source.crate"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == jagua['sha256']
    wrapper = next(p for p in inventory if p['name'] == 'spyrrow')
    revision = wrapper['source'].rsplit('/', 1)[-1]
    requirements = (root / 'requirements.txt').read_text()
    assert '@'+revision in requirements and '--config-settings=build-args=--locked' in requirements
