"""Opt-in read-only native Pack and Go acceptance test on a real workstation."""

import hashlib
import os
from pathlib import Path
import sys

import pytest


@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_TEST_PACKANDGO_ASSEMBLY'),
                    reason='Gerçek Windows/SolidWorks ve açıkça seçilmiş Pack and Go montajı yok.')
def test_live_typed_pack_reads_dependencies_without_saving_or_renaming_sources():
    from naming import exporter as engine, native
    from solidworks.connection import connect_to_solidworks
    import pythoncom

    source = Path(os.environ['GOKWORKS_TEST_PACKANDGO_ASSEMBLY']).resolve()
    assert source.is_file() and source.suffix.casefold() == '.sldasm'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    pythoncom.CoInitialize()
    try:
        app = engine._late_bound(connect_to_solidworks())
        with engine._source_document(app, str(source)) as model:
            pack = native.open_pack(app, str(source))
            try:
                snapshot = engine._snapshot(app, model, pack, str(source), str(source), True, None, None)
                assert snapshot.documents and snapshot.root == str(source)
            finally:
                pack.close()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        assert all(engine._stamp(doc.path) == doc.stamp for doc in snapshot.documents)
    finally:
        pythoncom.CoUninitialize()
