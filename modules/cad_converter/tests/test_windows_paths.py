"""Win32 device names must never become neutral CAD output basenames."""
import pytest

from modules.cad_converter.formats import FORMATS
from modules.cad_converter.models import Options, Source
from modules.cad_converter.naming import Destinations


@pytest.mark.parametrize('stem',['COM¹','LPT²','CONIN$','CONOUT$','CON .part','AUX .foo'])
def test_windows_reserved_input_names_get_safe_distinct_output_paths(tmp_path,stem):
    # Use plain Source values: Linux accepts these names, Windows rejects the
    # destination names regardless of the neutral CAD extension appended.
    source=Source(str(tmp_path/(stem+'.SLDPRT')))
    ordinary=Source(str(tmp_path/('_'+stem+'.SLDPRT')))
    planner=Destinations(Options(str(tmp_path/'out')),[source,ordinary])
    paths=[planner.path(s,'Default',FORMATS[1]) for s in (source,ordinary)]
    assert paths[0].name.startswith('_')
    assert len(set(paths))==2
    assert all(p.parent==tmp_path/'out'/FORMATS[1].folder for p in paths)
    assert not list(tmp_path.iterdir())  # Planning never touches source/destination files.


@pytest.mark.parametrize('stem',['COM¹-ready','LPT²_part','CONIN$_part','CONSOLE','AUXILIARY'])
def test_ordinary_names_containing_device_text_are_not_rewritten(tmp_path,stem):
    source=Source(str(tmp_path/(stem+'.SLDPRT')))
    planner=Destinations(Options(str(tmp_path/'out')),[source])
    assert planner.path(source,'Default',FORMATS[1]).stem==stem
