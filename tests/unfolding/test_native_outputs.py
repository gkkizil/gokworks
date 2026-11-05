import pytest
from core.unfolding import UnfoldService,ExportOptions
from .helpers import calculate


@pytest.mark.parametrize('shape,variant',[('cylinder','straight'),('cone','full'),('cone','frustum'),
    ('rectangular_reducer','centered'),('rect_to_round','centered_faceted')])
def test_actual_step_brep_surface_roundtrip_without_solid_or_mesh_conversion(tmp_path,shape,variant):
    pytest.importorskip('OCP')
    from core.unfolding.cad import read_step
    r=calculate(shape,variant);path=tmp_path/(shape+'.step')
    assert r.capabilities['step_surface'] and not r.capabilities['step_solid']
    report=UnfoldService().export(r,ExportOptions(str(path),'step'))
    assert report.status=='complete',report.errors
    _,stats=read_step(path)
    assert stats['solids']==0 and stats['faces']>=len(r.parts)
    assert stats['area_mm2']==pytest.approx(r.metrics['net_area_mm2'],rel=1e-7)
    assert path.read_bytes().startswith(b'ISO-10303-21;')


@pytest.mark.parametrize('shape,variant',[('cylinder','bevel'),('segmented_elbow','constant_diameter')])
def test_unimplemented_trimmed_step_is_disabled(tmp_path,shape,variant):
    r=calculate(shape,variant);path=tmp_path/'not-supported.step'
    assert not r.capabilities['step_surface']
    report=UnfoldService().export(r,ExportOptions(str(path),'step'))
    assert report.status=='error' and not path.exists()


def test_corrupt_step_fails_closed(tmp_path):
    pytest.importorskip('OCP')
    from core.unfolding.cad import read_step
    path=tmp_path/'bad.step';path.write_text('ISO-10303-21; not a real STEP file')
    with pytest.raises(ValueError):read_step(path)


@pytest.mark.parametrize('page_size',['A4','A3'])
def test_real_pdf_contains_turkish_text_parts_scale_and_true_lengths(qapp,tmp_path,page_size):
    from PySide6.QtPdf import QPdfDocument
    r=calculate('cone','frustum');path=tmp_path/(page_size+'.pdf')
    report=UnfoldService().export(r,ExportOptions(str(path),'pdf',page_size=page_size,project_name='Türkçe sac açınımı',project_code='İŞ-ÇĞÖÜŞ'))
    assert report.status=='complete',report.errors
    doc=QPdfDocument()
    assert doc.load(str(path))==QPdfDocument.Error.None_
    try:
        text=''.join(doc.getAllText(i).text() for i in range(doc.pageCount()))
        assert 'Türkçe sac açınımı' in text and 'İŞ-ÇĞÖÜŞ' in text
        assert 'sığdırıldı' in text and '1:1 değildir' in text and 'Gerçek uzunluk' in text
        assert 'cone-1.G1' in text and '213.600094' in text
        assert doc.pageCount()==2
        size=doc.pagePointSize(0)
        assert size.width()==pytest.approx(595. if page_size=='A4' else 842.,abs=2)
    finally:doc.close()
