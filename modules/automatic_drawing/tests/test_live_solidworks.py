"""REAL native acceptance: opt in on Windows with licensed, running SolidWorks.

These tests are deliberately separate from every offline/mock test in this folder.
GOKWORKS_DRAWING_LIVE_SOURCE: a saved, fully rebuilt SLDPRT or SLDASM fixture.
GOKWORKS_DRAWING_LIVE_TEMPLATE: a matching DRWDOT template.
"""

import os
from pathlib import Path
from queue import SimpleQueue
from threading import Event

import pytest

from modules.automatic_drawing.models import Options, Source
from modules.automatic_drawing.pipeline import generate


@pytest.mark.skipif(os.name != 'nt' or not os.environ.get('GOKWORKS_DRAWING_LIVE_SOURCE') or
                   not os.environ.get('GOKWORKS_DRAWING_LIVE_TEMPLATE'),
                    reason='REAL SolidWorks acceptance requires explicit Windows/SolidWorks fixture opt-in.')
def test_real_saved_model_generates_reopenable_native_drawing_and_pdf_without_source_save(tmp_path):
    source = Path(os.environ['GOKWORKS_DRAWING_LIVE_SOURCE'])
    template = Path(os.environ['GOKWORKS_DRAWING_LIVE_TEMPLATE'])
    before = source.read_bytes()
    options = Options(template=str(template), output_dir=str(tmp_path),
                      flat_pattern=False, bom=False, geometry_dimensions=False)
    results = generate([Source(str(source))], options, SimpleQueue(), Event())
    assert len(results) == 1
    result = results[0]
    assert result.status in ('PASS', 'WARNING'), result.as_dict()
    assert Path(result.outputs['slddrw']).stat().st_size > 1024
    assert Path(result.outputs['pdf']).read_bytes().startswith(b'%PDF-')
    assert result.sheets and result.api_revision
    assert source.read_bytes() == before


@pytest.mark.skipif(os.name != 'nt' or not os.environ.get('GOKWORKS_DRAWING_LIVE_MULTIBODY_SOURCE') or
                   not os.environ.get('GOKWORKS_DRAWING_LIVE_TEMPLATE'),
                   reason='REAL multibody acceptance requires existing per-body flat configurations and opt-in.')
def test_real_multibody_sheet_has_individual_reopened_flat_scopes_and_visible_body_headings(tmp_path):
    source = Path(os.environ['GOKWORKS_DRAWING_LIVE_MULTIBODY_SOURCE'])
    before = source.read_bytes()
    options = Options(template=os.environ['GOKWORKS_DRAWING_LIVE_TEMPLATE'], output_dir=str(tmp_path),
                      flat_pattern=True, bom=False, geometry_dimensions=False)
    result, = generate([Source(str(source))], options, SimpleQueue(), Event())
    assert result.status in ('PASS', 'WARNING'), result.as_dict()
    assert result.analysis.sheet_body_count >= 2
    rows = result.analysis.sheet_bodies
    assert len(rows) == result.analysis.sheet_body_count and all(row.ready for row in rows)
    pages = [s for s in result.sheets if s['expected'] == ['flat']]
    assert len(pages) == len(rows)
    assert {s['views'][0]['body_references'][0] for s in pages} == {row.body_ref for row in rows}
    for row, sheet in zip(rows, pages):
        assert sheet['views'][0]['body_count'] == 1
        assert sheet['notes'][0]['text'].splitlines()[0] == row.label
    assert Path(result.outputs['slddrw']).stat().st_size > 1024
    assert Path(result.outputs['pdf']).read_bytes().startswith(b'%PDF-')
    assert source.read_bytes() == before
