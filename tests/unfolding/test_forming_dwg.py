"""ODA is optional. Doubles verify failures; live round trip requires an installed converter."""
import pytest

from core.unfolding import UnfoldService,ExportOptions
from core.unfolding import dwg
from .test_forming_integration import profile


def test_missing_converter_never_claims_a_dwg_export(monkeypatch,tmp_path):
    def missing():raise ValueError('ODA not installed')
    monkeypatch.setattr(dwg,'converter_path',missing)
    s=UnfoldService();r=s.calculate(profile())
    assert r.capabilities['dwg'] is False
    result=s.export(r,ExportOptions(str(tmp_path/'part.dwg'),'dwg'))
    assert result.status=='error' and not (tmp_path/'part.dwg').exists()


def test_failed_dwg_readback_never_publishes_a_fake_header_only_file(monkeypatch,tmp_path):
    def fake_convert(source,directory,kind,token=None,timeout=120):
        directory.mkdir();path=directory/(source.stem+'.'+kind.lower())
        path.write_bytes(b'AC1032_FAKE' if kind=='DWG' else b'invalid dxf')
        return path
    monkeypatch.setattr(dwg,'available',lambda:True);monkeypatch.setattr(dwg,'_convert',fake_convert)
    r=UnfoldService().calculate(profile())
    result=UnfoldService().export(r,ExportOptions(str(tmp_path/'part.dwg'),'dwg'))
    assert result.status=='error'
    assert not (tmp_path/'part.dwg').exists()


def test_readback_dimension_change_is_rejected(monkeypatch,tmp_path):
    import ezdxf
    saved={}
    def fake_convert(source,directory,kind,token=None,timeout=120):
        directory.mkdir();path=directory/(source.stem+'.'+kind.lower())
        if kind=='DWG':saved['dxf']=source.read_bytes();path.write_bytes(b'AC1032_FAKE')
        else:
            path.write_bytes(saved['dxf']);doc=ezdxf.readfile(path)
            entity=next(iter(doc.modelspace().query('LWPOLYLINE')))
            entity.scale_uniform(2.);doc.saveas(path)
        return path
    monkeypatch.setattr(dwg,'_convert',fake_convert)
    r=UnfoldService().calculate(profile())
    with pytest.raises(ValueError,match='alan veya ana boyutlar'):dwg.write_dwg(r.parts[0],tmp_path/'part.dwg',r)
    assert not (tmp_path/'part.dwg').exists()


@pytest.mark.skipif(not dwg.available(),reason='Live ODA File Converter is not installed; no live DWG validation.')
def test_live_oda_roundtrip(tmp_path):
    s=UnfoldService();r=s.calculate(profile())
    e=s.export(r,ExportOptions(str(tmp_path/'part.dwg'),'dwg',development='compensated'))
    assert e.status=='complete',e.errors
    assert (tmp_path/'part.dwg').read_bytes().startswith(b'AC10')
