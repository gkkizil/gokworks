"""Valid DXF annotations alone do not constitute a flat cut."""
from pathlib import Path
import pytest
import ezdxf
from modules.dxf_dwg.exporter import _validate_output
from modules.dxf_dwg.geometry_check import validate_flat_geometry
from .test_autosave import case as _legacy_case

legacy_case = _legacy_case

@pytest.mark.parametrize('annotation',['text','point','empty-block'])
def test_annotation_only_file_cannot_be_accepted_as_a_flat_cut(tmp_path,annotation):
    path=tmp_path/'empty-cut.dxf';doc=ezdxf.new();model=doc.modelspace()
    if annotation=='text':model.add_text('NOT A CUT',dxfattribs={'height':5})
    elif annotation=='point':model.add_point((10,20))
    else:doc.blocks.new('Empty');model.add_blockref('Empty',(0,0))
    doc.saveas(path);_validate_output(path)
    with pytest.raises(ValueError,match='çizgi|eğri|geometri'):validate_flat_geometry(path)


def test_labels_alongside_real_curves_remain_valid_and_unchanged(tmp_path):
    path=tmp_path/'cut.dxf';doc=ezdxf.new();model=doc.modelspace()
    model.add_lwpolyline([(0,0),(20,0),(20,30),(0,30)],close=True)
    model.add_text('CUT LABEL',dxfattribs={'height':5});doc.saveas(path)
    before=path.read_bytes();_validate_output(path);validate_flat_geometry(path)
    assert path.read_bytes()==before



@pytest.mark.parametrize('annotation',['text','point','empty-block'])
def test_annotation_only_native_export_cannot_replace_an_existing_cut(legacy_case,tmp_path,annotation):
    from modules.dxf_dwg import exporter as ex
    app,part,_,_=legacy_case
    target=tmp_path/'production.dxf';target.write_bytes(b'ORIGINAL OUTPUT')
    source_before=Path(part.path).read_bytes()
    def export(path,*args):
        doc=ezdxf.new();model=doc.modelspace()
        if annotation=='text':model.add_text('LABEL',dxfattribs={'height':3})
        elif annotation=='point':model.add_point((1,2))
        else:doc.blocks.new('Empty');model.add_blockref('Empty',(0,0))
        doc.saveas(path);return True
    part.ExportToDWG2=export
    status,detail=ex.export_one_part(app,part.path,[target],overwrite=True)
    assert status=='error' and 'çizgisi veya eğrisi' in detail
    assert target.read_bytes()==b'ORIGINAL OUTPUT'
    assert Path(part.path).read_bytes()==source_before
    assert not list(tmp_path.glob('.gokworks-*'))
