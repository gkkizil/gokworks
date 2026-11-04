"""Unreadable DXF files fail with a Turkish, per-file message (QA 2026-11-03)."""

import random

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
    (random.Random(20261103).randbytes(4096), 'geçerli bir DXF dosyası okunamadı'),
    (b'%PDF-1.7\n' + b'x' * 200, 'geçerli bir DXF dosyası okunamadı'),
], ids=['empty', 'binary', 'pdf'])   # readable ids: Windows CI passes node ids on the command line
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


def _gapped(path, gap, extra=None):
    """100 x 50 rectangle drawn as four lines, the last one ending ``gap`` mm short."""
    doc = ezdxf.new(); doc.units = 4; msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50)); msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, gap))
    if extra: extra(doc, msp)
    doc.saveas(path)
    return path


def test_micrometre_end_gaps_from_cad_exports_are_joined_and_reported(tmp_path):
    """Reported 2026-11-04: SOLIDWORKS flat-pattern DXFs 'Okunamadı · Açık veya dallanan kontur'."""
    parts = read_dxf(_gapped(tmp_path / 'p.dxf', .005))
    assert len(parts) == 1 and parts[0].area == pytest.approx(5000, abs=1)
    assert 'otomatik birleştirildi' in parts[0].notes[0] and parts[0].endpoint_error == pytest.approx(.005, abs=1e-6)


def test_real_gap_is_refused_with_its_size_and_location(tmp_path):
    with pytest.raises(ValueError) as error:
        read_dxf(_gapped(tmp_path / 'p.dxf', 1.))
    text = str(error.value)
    assert 'açık uç' in text and '1.0000 mm' in text and 'x=0.000' in text


def test_bend_line_touching_the_outline_names_its_layer_and_reads_once_excluded(tmp_path):
    def bend(doc, msp):
        doc.layers.add('BUKUM'); msp.add_line((40, 0), (40, 50), dxfattribs={'layer': 'BUKUM'})
    with pytest.raises(ValueError) as error:
        read_dxf(_gapped(tmp_path / 'p.dxf', 0., bend))
    # It meets the outline mid-edge, so its two ends are loose: never joined automatically (50 mm apart).
    assert 'açık uç' in str(error.value) and 'İlgili katmanlar: BUKUM' in str(error.value)
    assert len(read_dxf(tmp_path / 'p.dxf', excluded_layers=['BUKUM'])) == 1
