"""Opt-in real SOLIDWORKS test: keep the source drawing open and unsaved."""

import hashlib
import os
from pathlib import Path
import sys

import pytest

from modules.pdf import exporter as ex


@pytest.mark.skipif(sys.platform!='win32' or os.environ.get('GOKWORKS_PDF_LIVE_TEST')!='1',
                   reason='Requires an explicitly enabled live Windows/SOLIDWORKS session with an active saved drawing.')
def test_live_pdf_contains_every_sheet_and_preserves_source_and_active_document(qapp,tmp_path):
    import pythoncom
    from PySide6.QtPdf import QPdfDocument
    from solidworks.connection import connect_to_solidworks
    app=model=drawing_api=pdf=None
    pythoncom.CoInitialize()
    try:
        app=connect_to_solidworks();model=ex.read_com_value(app,'ActiveDoc')
        assert model is not None and ex.read_com_value(model,'GetType')==ex.DRAWING
        source=Path(ex.read_com_value(model,'GetPathName'))
        assert source.is_file(), 'Open a saved drawing before enabling the live test.'
        drawing_api=ex._drawing_api(model);names=ex.read_com_value(drawing_api,'GetSheetNames')
        count=1 if isinstance(names,str) else len(names)
        dirty=ex.read_com_value(model,'GetSaveFlag')
        before=hashlib.sha256(source.read_bytes()).digest()
        target=tmp_path/'Tüm sayfalar.pdf'
        status,detail=ex.export_one_drawing(app,str(source),target,False)
        assert status=='success',detail
        pdf=QPdfDocument();assert pdf.load(str(target))==QPdfDocument.Error.None_
        assert pdf.pageCount()==count
        assert hashlib.sha256(source.read_bytes()).digest()==before
        assert ex.read_com_value(model,'GetSaveFlag')==dirty
        assert ex._path_key(ex.read_com_value(ex.read_com_value(app,'ActiveDoc'),'GetPathName'))==ex._path_key(source)
    finally:
        if pdf is not None:pdf.close()
        app=model=drawing_api=pdf=None
        pythoncom.CoUninitialize()
