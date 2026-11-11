"""Cross-platform Win32-name oracle and non-destructive real DXF checks."""
import ntpath

import ezdxf
import pytest

from modules.dxf_dwg.geometry_check import validate_flat_geometry
from modules.dxf_dwg.inventory import plan_destinations,safe_name


@pytest.mark.parametrize('name',['CON .part','AUX .body','COM¹','LPT²','conin$','CONOUT$','NUL.ext'])
def test_property_codes_cannot_produce_reserved_windows_destinations(tmp_path,name):
    source=tmp_path/'Panel.SLDPRT';source.touch()
    item=dict(sheet_id='1234567890abcdef',source=str(source),configuration='Default',body_name='Body',
              body_count=1,thickness_mm=2,quantity=3,code=name)
    paths=plan_destinations([item],tmp_path,tmp_path/'out',('dxf','dwg'),naming=('code',))
    assert safe_name(name).startswith('_')
    for path in paths[item['sheet_id']]:
        assert not ntpath.isreserved(path.name)
        assert '2 mm - 3 adet' in path.stem


@pytest.mark.parametrize('elevation',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_polyline_elevation_is_rejected_without_rewriting_source(tmp_path,elevation):
    path=tmp_path/'invalid.dxf';document=ezdxf.new()
    document.modelspace().add_lwpolyline([(0,0),(20,0),(20,10)],dxfattribs={'elevation':elevation})
    document.saveas(path);original=path.read_bytes()
    with pytest.raises(ValueError,match='sonlu olmayan'):
        validate_flat_geometry(path)
    assert path.read_bytes()==original


def test_finite_polyline_elevation_remains_valid_and_unchanged(tmp_path):
    path=tmp_path/'valid.dxf';document=ezdxf.new()
    document.modelspace().add_lwpolyline([(0,0),(20,0),(20,10)],dxfattribs={'elevation':3.5})
    document.saveas(path);original=path.read_bytes()
    validate_flat_geometry(path)
    assert path.read_bytes()==original
