import ezdxf
import pytest
from modules.dxf_dwg.geometry_check import validate_flat_geometry


def test_reversed_duplicate_cut_is_rejected_without_repairing_the_file(tmp_path):
    path=tmp_path/'duplicate.dxf';doc=ezdxf.new();space=doc.modelspace()
    space.add_line((0,0),(10,0));space.add_line((10,0),(0,0));doc.saveas(path);before=path.read_bytes()
    with pytest.raises(ValueError,match='mükerrer'):validate_flat_geometry(path)
    assert path.read_bytes()==before


def test_distinct_bend_and_cut_layers_are_preserved(tmp_path):
    path=tmp_path/'layers.dxf';doc=ezdxf.new();space=doc.modelspace();doc.layers.new('BEND')
    space.add_line((0,0),(10,0));space.add_line((0,0),(10,0),dxfattribs={'layer':'BEND'});doc.saveas(path)
    validate_flat_geometry(path)
    assert set(e.dxf.layer for e in ezdxf.readfile(path).modelspace())=={'0','BEND'}


def test_zero_length_geometry_is_not_published(tmp_path):
    path=tmp_path/'zero.dxf';doc=ezdxf.new();doc.modelspace().add_line((0,0),(0,0));doc.saveas(path)
    with pytest.raises(ValueError,match='sıfır uzunluk'):validate_flat_geometry(path)
