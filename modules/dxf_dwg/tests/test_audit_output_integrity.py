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


@pytest.mark.parametrize('kind',['ELLIPSE','SPLINE','POLYLINE'])
@pytest.mark.parametrize('value',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_other_curve_types_are_not_published(tmp_path,kind,value):
    path=tmp_path/'invalid-curve.dxf';doc=ezdxf.new();space=doc.modelspace()
    if kind=='ELLIPSE':space.add_ellipse((value,0),major_axis=(10,0),ratio=.5)
    elif kind=='SPLINE':space.add_spline([(0,0),(value,10),(20,0)])
    else:space.add_polyline2d([(0,0),(20,0),(20,10)],dxfattribs={'elevation':(0,0,value)})
    doc.saveas(path);before=path.read_bytes()
    with pytest.raises(ValueError,match='sonlu olmayan'):
        validate_flat_geometry(path)
    assert path.read_bytes()==before


@pytest.mark.parametrize('kind',['ELLIPSE','SPLINE','POLYLINE'])
def test_finite_other_curve_types_remain_unchanged(tmp_path,kind):
    path=tmp_path/'finite.dxf';doc=ezdxf.new();space=doc.modelspace()
    if kind=='ELLIPSE':space.add_ellipse((10,0),major_axis=(10,0),ratio=.5)
    elif kind=='SPLINE':space.add_spline([(0,0),(10,10),(20,0)])
    else:space.add_polyline2d([(0,0),(20,0),(20,10)])
    doc.saveas(path);before=path.read_bytes()
    validate_flat_geometry(path)
    assert path.read_bytes()==before


def test_duplicate_cuts_cannot_hide_behind_layer_name_case(tmp_path):
    path=tmp_path/'duplicate.dxf';doc=ezdxf.new();doc.layers.new('CUT')
    doc.modelspace().add_line((0,0),(10,0),dxfattribs={'layer':'CUT'})
    doc.modelspace().add_line((0,0),(10,0),dxfattribs={'layer':'cut'})
    doc.saveas(path)
    with pytest.raises(ValueError,match='mükerrer'):
        validate_flat_geometry(path)
