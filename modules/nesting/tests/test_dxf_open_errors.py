"""Unreadable DXF files fail with a Turkish, per-file message (QA 2026-11-03)."""

import os

import ezdxf
import pytest

from modules.nesting.dxf_import import layers, read_dxf


def _rectangle(path):
    doc = ezdxf.new()
    doc.units = 4
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    doc.saveas(path)
    return path


@pytest.mark.parametrize('content, expected', [
    (b'', 'dosya boş'),
    (os.urandom(4096), 'geçerli bir DXF dosyası okunamadı'),
    (b'%PDF-1.7\n' + b'x' * 200, 'geçerli bir DXF dosyası okunamadı'),
])
def test_empty_or_non_dxf_content_is_a_turkish_value_error(tmp_path, content, expected):
    path = tmp_path / 'Çalışma ğüş (1) & #2' / 'parça.dxf'
    path.parent.mkdir()
    path.write_bytes(content)
    for reader in (read_dxf, layers):
        with pytest.raises(ValueError) as error:
            reader(path)
        assert expected in str(error.value) and 'parça.dxf' in str(error.value)
        assert 'is not a DXF' not in str(error.value)


def test_missing_file_keeps_its_os_error_type(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_dxf(tmp_path / 'yok.dxf')


def test_valid_file_under_a_turkish_special_character_path_still_reads(tmp_path):
    folder = tmp_path / 'Müşteri ğüşİ (test) & #1'
    folder.mkdir()
    parts = read_dxf(_rectangle(folder / 'P1_2mm_5adet.dxf'))
    assert len(parts) == 1 and parts[0].area == pytest.approx(5000)
