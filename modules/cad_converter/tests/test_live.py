"""Opt-in test on a real Windows SolidWorks session; never enabled by CI mocks."""

import hashlib
import os
from pathlib import Path
import sys

import pytest


@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_CAD_LIVE_SOURCE'),
                    reason='Requires Windows, open SolidWorks and explicit GOKWORKS_CAD_LIVE_SOURCE test copy')
def test_real_solidworks_export_from_explicit_test_copy(tmp_path):
    from modules.cad_converter.models import Options, Source
    from modules.cad_converter.exporter import convert
    from .fakes import Events
    source = Path(os.environ['GOKWORKS_CAD_LIVE_SOURCE']).resolve()
    assert source.suffix.lower() in ('.sldprt', '.sldasm') and source.is_file()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    formats = tuple(os.environ.get('GOKWORKS_CAD_LIVE_FORMATS', 'step214').split(','))
    events = Events()
    convert([Source(str(source))], Options(str(tmp_path/'real-export'), formats), events)
    assert events.summary['state'] == 'completed', events.rows
    assert events.summary['succeeded'] + events.summary['warned'] == len(formats), events.rows
    assert not events.summary['failed']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
