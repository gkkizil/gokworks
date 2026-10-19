r"""Opt-in real SolidWorks tests. Never run source overwrite tests on user CAD.

Windows PowerShell:
  $env:GOKWORKS_TEST_SLDDRW='C:\test\disposable-drawing.SLDDRW'
  python -m pytest tests/test_tolerance_stack_live.py -v
  $env:GOKWORKS_TEST_WRITE_COPY='1'  # explicitly opt into a separate copy only
"""

import os
import sys
from pathlib import Path
import pytest

from tolerance_stack import solidworks_reader as reader,drawing_writer,storage,com
from tolerance_stack.models import Project,Term
from tolerance_stack.calculator import calculate


pytestmark=pytest.mark.skipif(sys.platform!='win32' or not os.environ.get('GOKWORKS_TEST_SLDDRW'),
    reason='Gerçek SolidWorks/Windows ve GOKWORKS_TEST_SLDDRW seçimi yok; canlı CAD testi çalıştırılmadı.')


def live_project():
    path=Path(os.environ['GOKWORKS_TEST_SLDDRW']).resolve()
    dims,sources=reader.read_sources([str(path)])
    eligible=[d for d in dims if d.kind in ('linear','horizontal','vertical','ordinate') and
              d.nominal is not None and d.lower is not None and d.upper is not None]
    if not eligible:pytest.skip('Test çiziminde açık toleranslı uygun 1D ölçü yok; başarılı sayılmaz.')
    dimension=eligible[0]
    project=Project(name='GOKWORKS canlı API kabul kontrolü',dimensions=dims,sources=sources,end='P1',method='worst_case',
        terms=[Term(dimension.id,start='P0',end='P1',datum='A',relation='Yalnız API test zinciri; üretim montaj analizi değildir.')])
    project.confirm()
    return path,project


def test_live_read_all_sheets_is_readonly_and_revision_matches():
    path,project=live_project();before=storage.fingerprint(path)
    reader.verify_live(project)
    assert storage.fingerprint(path).sha256==before.sha256
    assert all(d.source and d.sheet and d.view for d in project.dimensions)
    assert calculate(project).minimum is not None


@pytest.mark.skipif(os.environ.get('GOKWORKS_TEST_WRITE_COPY')!='1',reason='Ayrı analizli kopya kaydı için açık opt-in yok.')
def test_live_native_analysis_copy_preserves_original_and_model_references(tmp_path):
    path,project=live_project();before=storage.fingerprint(path)
    target=tmp_path/'GOKWORKS-Analiz.SLDDRW'
    result=drawing_writer.write_drawing(project,calculate(project),str(path),mode='copy',destination=target,new_sheet=True,labels=True)
    assert result['saved'] and target.is_file() and target.stat().st_size>0
    assert storage.fingerprint(path).sha256==before.sha256
    with com.Session() as session:
        original=session.document(str(path));copy=session.document(str(target))
        assert drawing_writer.dependencies(original)==drawing_writer.dependencies(copy)
        names=com.call(copy,'GetSheetNames')
        assert any(str(name).startswith('GOKWORKS-') for name in names)
