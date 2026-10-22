"""Explicit opt-in only: a saved test-copy Weldment in licensed SolidWorks."""

import hashlib
import os
from pathlib import Path
import pytest

from modules.profile_cutting.scanner import scan
from modules.profile_cutting.solidworks import Session, call


@pytest.mark.skipif(os.name!='nt' or not os.environ.get('GOKWORKS_WELDMENT_LIVE_SOURCE'),
                   reason='Windows, açık/lisanslı SolidWorks ve açıkça seçilmiş Weldment test kopyası gerekli.')
def test_live_weldment_read_keeps_source_and_active_configuration():
    source=Path(os.environ['GOKWORKS_WELDMENT_LIVE_SOURCE']).resolve()
    assert source.is_file() and source.suffix.lower() in ('.sldprt','.sldasm')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    with Session() as session:
        model=session.document()
        active=(call(model,'GetPathName'),session.active_configuration(model))
        model=None
    result=scan(str(source))
    assert result.rows and result.unscanned==0
    assert any(p.resolved and p.evaluated for row in result.rows for p in row.properties.values())
    expected=os.environ.get('GOKWORKS_WELDMENT_EXPECTED_COUNT')
    if expected:assert result.summary['profiles']==int(expected)
    with Session() as session:
        model=session.document()
        assert (call(model,'GetPathName'),session.active_configuration(model))==active
        model=None
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
