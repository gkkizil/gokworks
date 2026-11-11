"""Independent manufacturing-boundary rejection for saved/manual layouts."""
import pytest
from shapely.geometry import box

from modules.nesting.materials import new_project
from modules.nesting.models import Part,Placement,Result
from modules.nesting.validation import validate_result
from modules.nesting.storage import save_project,load_project


def layout(width=100,height=100):
    p=new_project();p.parts=[Part.create('Bracket',box(0,0,10,10))]
    p.sheets[0].width=width;p.sheets[0].height=height
    p.options.margin=p.options.kerf=0
    r=Result('',[Placement(p.parts[0].id,1,p.sheets[0].id,1,width/2-5,height/2-5,0)],[],
             'fixture','1',0.,0,'')
    return p,r


@pytest.mark.parametrize('size',[(100,100),(100,300),(300,100)])
@pytest.mark.parametrize('allowance',['margin','kerf','curve','join'])
def test_reversed_usable_bounds_cannot_validate_a_false_central_pocket(size,allowance):
    p,r=layout(*size)
    if allowance=='margin':p.options.margin=60
    elif allowance=='kerf':p.options.kerf=120
    elif allowance=='curve':p.parts[0].curve_tolerance=60
    else:p.parts[0].endpoint_error=60
    r.digest=p.fingerprint()
    with pytest.raises(ValueError,match='kenar payı'):
        validate_result(p,r)


def test_valid_exact_edge_clearance_round_trips_and_oversized_margin_cannot_be_saved(tmp_path):
    p,r=layout();p.options.margin=45;r.digest=p.fingerprint()
    assert validate_result(p,r)
    path=tmp_path/'layout.json';save_project(p,path,r)
    loaded,got=load_project(path);assert validate_result(loaded,got)
    before=path.read_bytes();p.options.margin=60;r.digest=p.fingerprint()
    with pytest.raises(ValueError,match='kenar payı'):
        save_project(p,path,r,overwrite=True)
    assert path.read_bytes()==before


@pytest.mark.parametrize('kind',['area','perimeter','sheet','error_sum'])
def test_finite_inputs_with_nonfinite_derived_geometry_are_rejected(kind):
    import numpy as np
    p,_=layout()
    if kind=='area':p.parts[0]=Part.create('Huge area',box(0,0,1e200,1e200))
    elif kind=='perimeter':p.parts[0]=Part.create('Huge perimeter',box(0,0,1e200,1))
    elif kind=='sheet':p.sheets[0].width=p.sheets[0].height=1e200
    else:p.parts[0].curve_tolerance=p.parts[0].endpoint_error=1e308
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError,match='hesaplama aralığını'):
            p.validate()
