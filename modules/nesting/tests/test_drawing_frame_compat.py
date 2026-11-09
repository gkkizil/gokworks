"""Framed CAD exports: separate edges, slight shears and view-caption blocks.

Minimal synthetic drawings only; the customer's original DXF is not a fixture.
"""
from io import StringIO

import ezdxf
from ezdxf.math import Matrix44
import pytest

from modules.nesting.dxf_import import read_dxf
from .test_drawing_import import cell, run


def source(tmp_path, *, corners=None, gap=0., unit=4, lines=False):
    doc=ezdxf.new();doc.units=unit;model=doc.modelspace()
    cell(model,0,0,2,hole=False)
    model.delete_entity(list(model.query('LWPOLYLINE'))[0])
    corners=corners or [(0,0),(100,0),(100,90),(0,90)]
    if lines:
        for index,(a,b) in enumerate(zip(corners,corners[1:]+corners[:1])):
            if index==3:b=(b[0],b[1]+gap)
            model.add_line(a,b)
    else:model.add_lwpolyline(corners,close=True)
    path=tmp_path/'framed.dxf';doc.saveas(path)
    return path


@pytest.mark.parametrize('gap',[2.9e-11,.0005,.001])
@pytest.mark.parametrize('unit,scale',[(4,1),(5,10),(1,25.4)])
def test_separate_border_edges_join_within_the_existing_millimetre_tolerance(tmp_path,gap,unit,scale):
    path=source(tmp_path,gap=gap/scale,unit=unit,lines=True)
    before=path.read_bytes();part=read_dxf(path,drawing_layout=True)[0]
    assert part.quantity==2 and part.area==pytest.approx(1500*scale**2)
    assert part.endpoint_error==0 and path.read_bytes()==before
    assert len(ezdxf.read(StringIO(part.original_dxf)).modelspace())==1


def test_a_border_gap_beyond_tolerance_is_not_closed(tmp_path):
    path=source(tmp_path,gap=.002,lines=True)
    with pytest.raises(ValueError,match='çerçeve bulunamadı'):read_dxf(path,drawing_layout=True)


@pytest.mark.parametrize('rotation',[0,27])
@pytest.mark.parametrize('shear',[.15,.5])
def test_slightly_sheared_frames_keep_the_actual_part_geometry(tmp_path,rotation,shear):
    path=source(tmp_path,corners=[(0,90),(100,90),(100+shear,0),(shear,0)])
    doc=ezdxf.readfile(path)
    transform=Matrix44.chain(Matrix44.z_rotate(rotation*3.141592653589793/180),Matrix44.translate(3200,1500,0))
    for entity in doc.modelspace():entity.transform(transform)
    doc.saveas(path);before=path.read_bytes()
    part=read_dxf(path,drawing_layout=True)[0]
    assert part.quantity==2 and part.area==pytest.approx(1500)
    assert len(ezdxf.read(StringIO(part.original_dxf)).modelspace())==1
    assert path.read_bytes()==before


@pytest.mark.parametrize('corners',[
    [(0,90),(100,90),(105,0),(5,0)],
    [(0,90),(100,90),(40,60),(0,0)],
    [(0,90),(100,90),(100,0),(60,0),(0,20)]])
def test_large_shears_concave_or_non_rectangular_borders_are_not_invented(tmp_path,corners):
    path=source(tmp_path,corners=corners)
    with pytest.raises(ValueError,match='çerçeve bulunamadı'):read_dxf(path,drawing_layout=True)


def heading(doc, *, title='DETAIL', tag='LETTER', circle=False, extra_line=False):
    block=doc.blocks.new('arbitrary-caption-name')
    block.add_mtext(title,dxfattribs={'char_height':2})
    block.add_attdef(tag,(10,0),dxfattribs={'height':2})
    block.add_line((10,-1),(18,-1))
    if circle:block.add_circle((0,0),3)
    if extra_line:block.add_line((18,-1),(18,3))
    insert=doc.modelspace().add_blockref(block.name,(20,80),dxfattribs={'xscale':1.5,'yscale':1.5})
    insert.add_auto_attribs({tag:'A'})


@pytest.mark.parametrize('title',['DETAIL','VIEW','SCALE',r'\LDETAIL\l'])
def test_standard_attribute_view_headings_exclude_only_their_underlines(tmp_path,title):
    path=source(tmp_path);doc=ezdxf.readfile(path);heading(doc,title=title);doc.saveas(path)
    before=path.read_bytes();part=read_dxf(path,drawing_layout=True)[0]
    assert part.quantity==2 and part.area==pytest.approx(1500)
    assert len(ezdxf.read(StringIO(part.original_dxf)).modelspace())==1
    assert path.read_bytes()==before


@pytest.mark.parametrize('options',[dict(title='PART'),dict(tag='COUNT'),dict(circle=True),dict(extra_line=True)])
def test_an_arbitrary_text_bearing_or_geometry_block_is_not_discarded(tmp_path,options):
    path=source(tmp_path);doc=ezdxf.readfile(path);heading(doc,**options);doc.saveas(path)
    with pytest.raises(ValueError,match='Açık|dallanan'):read_dxf(path,drawing_layout=True)


def test_skew_and_endpoint_frames_with_page_border_and_caption_blocks_require_review(tmp_path):
    doc=ezdxf.new();doc.units=4;model=doc.modelspace()
    cell(model,0,0,2,hole=False);cell(model,150,0,8,hole=False)
    for entity in list(model.query('LWPOLYLINE'))[::2]:model.delete_entity(entity)
    corners=[(0,0),(100,0),(100,90),(0,90)]
    for index,(a,b) in enumerate(zip(corners,corners[1:]+corners[:1])):
        if index==3:b=(0,2.9e-11)
        model.add_line(a,b)
    model.add_lwpolyline([(150,90),(250,90),(250.15,0),(150.15,0)],close=True)
    model.add_lwpolyline([(-20,-20),(300,-20),(300,120),(-20,120)],close=True)
    heading(doc);path=tmp_path/'mixed-frame-types_5mm_2adet.dxf';doc.saveas(path)
    row,_=run(path,thickness=5,quantity=99)
    assert row['status']=='review' and row['parts']==[]
    assert [p['quantity'] for p in row['contour_review']['drawing_parts']]==[2,8]
    approved,_=run(path,thickness=5,quantity=99,approval=row['contour_review'])
    assert approved['status']=='success' and sum(p.quantity for p in approved['parts'])==10
    assert all(p.area==pytest.approx(1500) and p.thickness==5 for p in approved['parts'])
