"""Real pywin32 VARIANTs on Windows; these checks do not claim live CAD export."""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from modules.pdf import exporter as ex

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Native pywin32 VARIANT checks require Windows.')


@pytest.mark.parametrize('fail_modern',[False,True])
def test_native_variants_preserve_unicode_sheets_byref_errors_and_null_dispatch(monkeypatch,tmp_path,fail_modern):
    import pythoncom
    import win32com.client
    monkeypatch.setattr(ex,'pythoncom',pythoncom)
    monkeypatch.setattr(ex,'win32com',win32com)
    names=('Sayfa 1','Büküm – İmalat')
    scopes=[];calls=[]
    class Data:
        def SetSheets(self,scope,sheets):
            assert sheets.varianttype==pythoncom.VT_ARRAY|pythoncom.VT_BSTR
            assert tuple(sheets.value)==names
            scopes.append(scope)
            return True
    data=Data()
    def legacy(path,version,options,export,errors,warnings):
        assert export is data and (version,options)==(0,1)
        assert errors.varianttype==pythoncom.VT_BYREF|pythoncom.VT_I4
        assert warnings.varianttype==pythoncom.VT_BYREF|pythoncom.VT_I4
        assert not export.ViewPdfAfterSaving and not export.ExportAs3D
        errors.value=0;warnings.value=8
        calls.append('SaveAs')
        return True
    def modern(path,version,options,export,advanced,errors,warnings):
        assert advanced.varianttype==pythoncom.VT_DISPATCH and advanced.value is None
        calls.append('SaveAs3')
        if fail_modern:
            errors.value=1;Path(path).write_bytes(b'partial PDF');return False
        calls.pop()
        assert legacy(path,version,options,export,errors,warnings)
        calls[-1]='SaveAs3'
        return True
    source=tmp_path/'Çizim.SLDDRW'
    model=SimpleNamespace(GetPathName=lambda:str(source),Extension=SimpleNamespace(SaveAs3=modern,SaveAs=legacy))
    app=SimpleNamespace(ActiveDoc=model,GetExportFileData=lambda kind:data)
    warning,retried=ex._save_pdf(app,model,str(source),tmp_path/'temporary.pdf',names,lambda *a,**kw:None,None)
    assert warning==8 and retried==fail_modern
    assert scopes==([1,3] if fail_modern else [1])
    assert calls==(['SaveAs3','SaveAs'] if fail_modern else ['SaveAs3'])
