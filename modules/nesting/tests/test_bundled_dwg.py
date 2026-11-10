"""DWG okuma ek indirme gerektirmez: ODA kuruluysa o, değilse paketteki LibreDWG dwg2dxf."""
import os
from pathlib import Path
import re
import stat
import sys
import textwrap

import ezdxf
from ezdxf import units
import pytest

from modules.nesting import dwg_import
from modules.nesting.dwg_import import LIBREDWG_VERSION, convert_dwg, converters, libredwg_path, read_dwg

ROOT = Path(__file__).resolve().parents[3]


def write_dxf(path):
    document = ezdxf.new('R2000'); document.units = units.MM
    document.modelspace().add_lwpolyline([(0, 0), (40, 0), (40, 15), (0, 15)], close=True)
    document.saveas(path)


def fake_tool(folder, name, body):
    """A tiny executable that behaves like a converter's command line."""
    script = folder/'fake_tool.py'
    script.write_text(textwrap.dedent(body), encoding='utf-8')
    if os.name == 'nt':
        tool = folder/(name+'.cmd'); tool.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding='utf-8')
    else:
        tool = folder/name; tool.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding='utf-8')
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


LIBREDWG = '''
import sys, ezdxf
from ezdxf import units
args = sys.argv[1:]
assert args[0] == '-y' and args[1] == '-o', args
out, src = args[2], args[3]
assert open(src, 'rb').read(4) == b'AC10'
d = ezdxf.new('R2000'); d.units = units.MM
d.modelspace().add_lwpolyline([(0, 0), (40, 0), (40, 15), (0, 15)], close=True)
d.saveas(out)
'''


@pytest.fixture
def no_oda(monkeypatch):
    def missing():
        raise ValueError('ODA File Converter kurulu değil.')
    monkeypatch.setattr(dwg_import, 'converter_path', missing)


def test_bundled_libredwg_reads_dwg_without_oda(tmp_path, monkeypatch, no_oda):
    tool = fake_tool(tmp_path, 'dwg2dxf', LIBREDWG)
    monkeypatch.setenv('GOKWORKS_LIBREDWG_DWG2DXF', str(tool))
    source = tmp_path/'Flans - 3 mm - 2 adet.dwg'; original = b'AC1032 test drawing'; source.write_bytes(original)
    parts = read_dwg(source, quantity=2)
    assert len(parts) == 1 and parts[0].polygon.area == pytest.approx(600) and parts[0].quantity == 2
    assert f'LibreDWG {LIBREDWG_VERSION}' in parts[0].notes[-1]
    assert source.read_bytes() == original


def test_installed_oda_is_preferred_and_libredwg_is_the_fallback(tmp_path, monkeypatch):
    lib = fake_tool(tmp_path, 'dwg2dxf', LIBREDWG)
    monkeypatch.setenv('GOKWORKS_LIBREDWG_DWG2DXF', str(lib))
    monkeypatch.setattr(dwg_import, 'converter_path', lambda: 'odafc')
    assert [kind for kind, _ in converters()] == ['oda', 'libredwg']
    calls = []
    real_run = dwg_import._run

    def run(command, stop, timeout, cwd=None):
        calls.append(command[0])
        if command[0] == 'odafc':
            return 1                         # ODA present but produced nothing
        return real_run(command, stop, timeout, cwd)
    monkeypatch.setattr(dwg_import, '_run', run)
    source = tmp_path/'p.dwg'; source.write_bytes(b'AC1032 x'); target = tmp_path/'out'/'p.dxf'; target.parent.mkdir()
    assert convert_dwg(source, target) == 'libredwg' and target.is_file()
    assert calls == ['odafc', str(lib)]


def test_failure_names_every_converter_and_suggests_dxf(tmp_path, monkeypatch, no_oda):
    tool = fake_tool(tmp_path, 'dwg2dxf', 'import sys; sys.exit(3)\n')
    monkeypatch.setenv('GOKWORKS_LIBREDWG_DWG2DXF', str(tool))
    source = tmp_path/'p.dwg'; source.write_bytes(b'AC1032 x')
    with pytest.raises(ValueError, match='LibreDWG.*kod 3.*DXF olarak'):
        convert_dwg(source, tmp_path/'p.dxf')


def test_missing_converters_explain_without_asking_for_a_download(monkeypatch, no_oda):
    monkeypatch.delenv('GOKWORKS_LIBREDWG_DWG2DXF', raising=False)
    monkeypatch.setattr(dwg_import, 'libredwg_path', lambda: (_ for _ in ()).throw(ValueError('yok')))
    with pytest.raises(ValueError, match='paketteki DWG okuyucu'):
        converters()


def test_frozen_package_finds_converter_inside_the_bundle(tmp_path, monkeypatch):
    monkeypatch.delenv('GOKWORKS_LIBREDWG_DWG2DXF', raising=False)
    bundle = tmp_path/'bundle'; tools = bundle/'tools'/'libredwg'; tools.mkdir(parents=True)
    name = 'dwg2dxf.exe' if os.name == 'nt' else 'dwg2dxf'
    (tools/name).write_bytes(b'')
    monkeypatch.setattr(sys, 'frozen', True, raising=False); monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    assert Path(libredwg_path()) == tools/name


def test_converter_dxf_with_structure_flaws_is_repaired_then_read_strictly(tmp_path, monkeypatch):
    good = tmp_path/'good.dxf'; write_dxf(good)
    calls = []

    def flaky(path, **kwargs):
        calls.append(Path(path).name)
        if len(calls) == 1:
            raise ValueError('DXF yapısı okunamadı')
        return ['parça']
    monkeypatch.setattr(dwg_import, 'read_dxf', flaky)
    assert dwg_import._read_converted(good, None, {}) == ['parça']
    assert calls == ['good.dxf', 'good-onarildi.dxf']


def test_windows_build_bundles_only_the_pinned_converter_with_its_notice():
    script = (ROOT/'packaging/build_windows.py').read_text(encoding='utf-8')
    assert f"LIBREDWG_VERSION = '{LIBREDWG_VERSION}'" in script
    assert re.search(r"LIBREDWG_SHA256 = '[0-9a-f]{64}'", script)
    added = re.findall(r"'--add-binary', f'\{libredwg / \"([^\"]+)\"\};tools/libredwg'", script)
    assert added == ['dwg2dxf.exe', 'libredwg-0.dll']           # dxf2dwg is build-time verification only
    assert 'verify_libredwg(libredwg)' in script
    notice = (ROOT/'packaging/licenses/LibreDWG-NOTICE.txt').read_text(encoding='utf-8')
    assert 'GPL-3.0-or-later' in notice and 'libredwg-0.13.3.tar.xz' in notice
    assert (ROOT/'packaging/licenses/GPL-3.0-only.txt').is_file()
    assert 'packaging/vendor/' in (ROOT/'.gitignore').read_text(encoding='utf-8')


def with_placeholder_objects(path, duplicate=False):
    """LibreDWG writes unconvertible objects (e.g. MLEADERSTYLE) with the invalid handle 0."""
    text = path.read_text(encoding='utf-8'); at = text.rindex('  0\nENDSEC')
    text = text[:at] + '  0\nMLEADERSTYLE\n  5\n0\n330\nC\n100\nAcDbMLeaderStyle\n' + text[at:]
    if duplicate:                                   # a second, unrelated object reusing an existing handle
        at = text.rindex('  0\nENDSEC')
        text = text[:at] + '  0\nDICTIONARYVAR\n  5\nC\n330\nC\n100\nDictionaryVariables\n280\n0\n  1\nx\n' + text[at:]
    path.write_text(text, encoding='utf-8')


@pytest.mark.parametrize('duplicate', [False, True])
def test_converter_placeholders_with_handle_zero_are_dropped_and_geometry_is_read(tmp_path, duplicate):
    dxf = tmp_path/'p.dxf'; write_dxf(dxf); with_placeholder_objects(dxf, duplicate)
    with pytest.raises(ValueError):
        ezdxf.readfile(dxf)                          # ezdxf alone rejects the whole file, even in recover mode
    parts = dwg_import._read_converted(dxf, None, {})
    assert len(parts) == 1 and parts[0].polygon.area == pytest.approx(600)


def test_a_dxf_without_placeholders_is_not_rewritten(tmp_path):
    dxf = tmp_path/'p.dxf'; write_dxf(dxf)
    assert dwg_import._drop_invalid_handles(dxf) is None


def test_bundled_converter_output_with_placeholders_reads_end_to_end(tmp_path, monkeypatch, no_oda):
    body = LIBREDWG + textwrap.dedent('''
        text = open(out, encoding='utf-8').read(); at = text.rindex('  0\\nENDSEC')
        open(out, 'w', encoding='utf-8').write(text[:at] + '  0\\nMLEADERSTYLE\\n  5\\n0\\n330\\nC\\n' + text[at:])
    ''')
    monkeypatch.setenv('GOKWORKS_LIBREDWG_DWG2DXF', str(fake_tool(tmp_path, 'dwg2dxf', body)))
    source = tmp_path/'Kapak - 2 mm - 1 adet.dwg'; source.write_bytes(b'AC1015 x')
    parts = read_dwg(source)
    assert len(parts) == 1 and parts[0].polygon.area == pytest.approx(600) and source.read_bytes() == b'AC1015 x'


def test_section_frames_are_kept_even_if_a_header_value_looks_like_handle_zero(tmp_path):
    dxf = tmp_path/'p.dxf'; write_dxf(dxf); with_placeholder_objects(dxf)
    text = dxf.read_text(encoding='utf-8').replace('$ACADVER\n  1\n', '$ACADVER\n  5\n0\n  1\n', 1)
    dxf.write_text(text, encoding='utf-8')
    cleaned = dwg_import._drop_invalid_handles(dxf).read_text(encoding='utf-8')
    assert '$ACADVER' in cleaned and 'MLEADERSTYLE\n  5\n0\n' not in cleaned and cleaned.rstrip().endswith('EOF')
