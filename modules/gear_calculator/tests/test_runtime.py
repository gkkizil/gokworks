import sys
import pytest
from solidworks.runtime import configure_libraries


def test_explicit_compatible_occt_replacement_is_available_without_changing_default(tmp_path,monkeypatch):
    monkeypatch.delenv('GOKWORKS_LIBRARY_DIR',raising=False)
    monkeypatch.delenv('GOKWORKS_GEOMETRY_DIR',raising=False)
    monkeypatch.setenv('GOKWORKS_CAD_DIR',str(tmp_path))
    with pytest.raises(RuntimeError,match='OCCT'):configure_libraries()
    for name in ('OCP','cadquery_ocp_proxy'):
        (tmp_path/name).mkdir();(tmp_path/name/'__init__.py').write_text('')
    monkeypatch.setattr(sys,'path',list(sys.path));configure_libraries()
    assert sys.path[0]==str(tmp_path.resolve())
