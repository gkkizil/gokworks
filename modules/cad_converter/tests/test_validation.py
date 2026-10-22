"""Fail closed on wrong protocol, broken records and wrong binary/text type."""

from dataclasses import replace
from pathlib import Path
import struct

import pytest

from modules.cad_converter.formats import FORMATS
from modules.cad_converter.models import Options
from modules.cad_converter.validation import validate_output
from modules.cad_converter.naming import Destinations, publish
from modules.cad_converter.models import Source
from modules.cad_converter.report import write_report
from .fakes import content


@pytest.mark.parametrize('fmt', FORMATS, ids=lambda f: f.key)
@pytest.mark.parametrize('damage', ['truncated', 'empty', 'html'])
def test_broken_or_wrong_export_is_never_valid(tmp_path, fmt, damage):
    path = tmp_path/('out' + fmt.extension)
    path.write_bytes(content(fmt.key)[:20] if damage == 'truncated' else b'' if damage == 'empty' else b'<html>Access denied</html>')
    with pytest.raises((ValueError, UnicodeError)): validate_output(path, fmt.key)


@pytest.mark.parametrize('key,wrong', [('step203','step214'), ('step214','step242'), ('step242','step203'),
    ('stl_binary','stl_ascii'), ('stl_ascii','stl_binary'), ('xt','xb'), ('xb','xt')])
def test_file_must_really_be_the_requested_protocol_and_encoding(tmp_path, key, wrong):
    path = tmp_path/'wrong'; path.write_bytes(content(wrong))
    with pytest.raises((ValueError, UnicodeError)): validate_output(path, key)


@pytest.mark.parametrize('damage', ['count', 'nonfinite', 'zeroarea'])
def test_stl_triangle_records_are_checked(tmp_path, damage):
    b = bytearray(content('stl_binary'))
    if damage == 'count': b[80:84] = struct.pack('<I', 2)
    if damage == 'nonfinite': b[84:88] = struct.pack('<f', float('nan'))
    if damage == 'zeroarea': b[96:132] = b'\x00'*36
    path = tmp_path/'bad.stl'; path.write_bytes(b)
    with pytest.raises(ValueError): validate_output(path, 'stl_binary')


@pytest.mark.parametrize('changes', [dict(formats=()), dict(formats=('ap204',)), dict(configurations='selected'),
    dict(stl_unit='metres'), dict(deviation_mm=float('nan')), dict(angle_degrees=91), dict(assembly_mode='unknown')])
def test_invalid_options_cannot_start(tmp_path, changes):
    with pytest.raises(ValueError): replace(Options(str(tmp_path)), **changes).validate()


def test_preserved_source_subfolders_stay_inside_format_root(tmp_path):
    source = Source(str(tmp_path/'root'/'sub'/'part.SLDPRT'), str(tmp_path/'root'))
    options = Options(str(tmp_path/'out'), preserve_folders=True)
    target = Destinations(options, [source]).path(source, 'Default', FORMATS[1])
    assert target == tmp_path/'out'/'STEP_AP214'/'sub'/'part.step'


def test_atomic_no_overwrite_publication_survives_racing_destination(tmp_path):
    temporary = tmp_path/'temp'; temporary.write_bytes(b'new')
    target = tmp_path/'output'; target.write_bytes(b'existing')
    with pytest.raises(FileExistsError): publish(temporary, target, False)
    assert target.read_bytes() == b'existing' and temporary.read_bytes() == b'new'


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_reports_keep_all_outcomes_codes_counts_and_turkish_text(tmp_path, extension):
    row = dict(source='Üst sac.SLDPRT', configuration='=danger', format='STEP AP214', protocol=214,
               output='Çıktı.step', status='success', detail='Doğrulandı', size=200, seconds=.5, errors=0, warnings=2)
    path = tmp_path/('report.' + extension); write_report([row], path)
    assert path.is_file() and not list(tmp_path.glob('.gokworks-*'))
    if extension == 'csv':
        data = path.read_text(encoding='utf-8-sig'); assert 'Üst sac' in data and 'success=1' in data and "'=danger" in data
    else:
        from openpyxl import load_workbook
        workbook = load_workbook(path); sheet = workbook.active
        assert sheet['A2'].value == 'Üst sac.SLDPRT' and sheet['B2'].data_type == 's'
        assert workbook['Özet']['B1'].value == 1
        workbook.close()
