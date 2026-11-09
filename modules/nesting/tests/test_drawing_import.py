"""Real multi-part CAD drawings: quantities, frame isolation and exact cut export."""

from io import StringIO
from threading import Event

import ezdxf
from ezdxf.enums import TextEntityAlignment
import pytest

from modules.nesting.batch_import import import_batch
from modules.nesting.dxf_import import read_dxf
from modules.nesting.import_plan import normalize_options
from modules.nesting.materials import new_project
from modules.nesting.storage import load_project, save_project
from .test_filename_import import Sink


def cell(model, x, y, quantity, *, color=1, frame_lines=False, mtext=False, hole=True):
    corners = [(x,y),(x+100,y),(x+100,y+90),(x,y+90)]
    if frame_lines:
        for a,b in zip(corners,corners[1:]+corners[:1]):
            model.add_line(a,b,dxfattribs={'color':color})
    else:
        model.add_lwpolyline(corners,close=True,dxfattribs={'color':color})
    model.add_lwpolyline([(x+20,y+10),(x+70,y+10),(x+70,y+40),(x+20,y+40)],close=True)
    if hole:
        model.add_circle((x+40,y+25),5)
    if quantity is not None:
        if mtext:
            model.add_mtext(r'{\C2;'+str(quantity)+r' adet}',dxfattribs={'insert':(x+35,y+65),'char_height':3})
        else:
            model.add_text(str(quantity)+' adet',dxfattribs={'height':3}).set_placement(
                (x+50,y+65),align=TextEntityAlignment.MIDDLE_CENTER)
    model.add_text('DETAIL 123 / SCALE 1:5',dxfattribs={'height':2,'insert':(x+20,y+80)})


def drawing(tmp_path, counts=(1,7,20), *, name='Toplu_T2_99AD.dxf', **kwargs):
    path=tmp_path/name; doc=ezdxf.new(); doc.units=4
    for i,quantity in enumerate(counts):
        cell(doc.modelspace(),(i%4)*130,-(i//4)*120,quantity,**kwargs)
    doc.saveas(path)
    return path


def run(path, *, approval=None, existing_quantity=0, **options):
    entry=dict(id='drawing',source=str(path),options=normalize_options(dict(drawing_layout=True,**options)),
               part_code='FILENAME_MUST_NOT_REPLACE_DRAWING_CODES')
    if approval is not None: entry['contour_approval']=approval
    sink=Sink(); import_batch([entry],{},sink,Event(),existing_quantity=existing_quantity)
    return sink.finished[0],entry


@pytest.mark.parametrize('color,frame_lines,mtext',[(1,False,False),(3,True,True),(7,False,True),(256,True,False)])
def test_arbitrary_frames_text_positions_and_native_holes(tmp_path,color,frame_lines,mtext):
    path=drawing(tmp_path,color=color,frame_lines=frame_lines,mtext=mtext)
    before=path.read_bytes()
    parts=read_dxf(path,drawing_layout=True,quantity=99)
    assert [p.quantity for p in parts]==[1,7,20]
    assert [p.code for p in parts]==[path.stem+f'-{i:02d}' for i in (1,2,3)]
    assert all(p.polygon.bounds==(0,0,50,30) and len(p.polygon.interiors)==1 for p in parts)
    assert all(1420<p.area<1423 for p in parts)
    for part in parts:
        entities=list(ezdxf.read(StringIO(part.original_dxf)).modelspace())
        assert sorted(e.dxftype() for e in entities)==['CIRCLE','LWPOLYLINE']
    assert path.read_bytes()==before


def test_example_quantity_distribution_is_reviewed_before_import_and_not_multiplied(tmp_path):
    counts=(1,7,1,2,1,2,1,1,2,8,20,6,2,2)
    path=drawing(tmp_path,counts)
    row,_=run(path,quantity=99)
    assert row['status']=='review' and row['parts']==[]
    review=row['contour_review']
    assert [p['quantity'] for p in review['drawing_parts']]==list(counts)
    assert '56 adet' in row['detail']
    row,_=run(path,approval=review,quantity=99)
    assert row['status']=='success' and sum(p.quantity for p in row['parts'])==56
    # Approval is invalid after any source edit, even when frame count agrees.
    doc=ezdxf.readfile(path); list(doc.modelspace().query('TEXT'))[0].dxf.text='3 adet'; doc.saveas(path)
    assert run(path,approval=review,quantity=99)[0]['status']=='review'


@pytest.mark.parametrize('counts,message',[(('0',),'pozitif|tam sayı|sonlu'),(('1,5',),'tam sayı'),
    (('10001',),'tam sayı'),(('1.000',),'tam sayı'),(('7 adet 2',),'birden fazla'),((1,None),'atanamadı'),((None,),'adet yazısı bulunamadı')])
def test_missing_invalid_and_multiple_quantities_never_silently_fall_back(tmp_path,counts,message):
    path=drawing(tmp_path,counts)
    with pytest.raises(ValueError,match=message): read_dxf(path,drawing_layout=True)


def test_duplicate_text_and_multiple_cut_parts_in_one_cell_are_rejected(tmp_path):
    path=drawing(tmp_path,(1,)); doc=ezdxf.readfile(path)
    doc.modelspace().add_text('1 adet',dxfattribs={'insert':(30,55),'height':2}); doc.saveas(path)
    with pytest.raises(ValueError,match='birden fazla adet'): read_dxf(path,drawing_layout=True)
    path=drawing(tmp_path,(1,)); doc=ezdxf.readfile(path)
    doc.modelspace().add_circle((85,25),4); doc.saveas(path)
    with pytest.raises(ValueError,match='2 bağımsız parça'): read_dxf(path,drawing_layout=True)


def test_helpers_are_explicitly_excluded_and_closed_page_border_is_removed(tmp_path):
    path=drawing(tmp_path,(2,3)); doc=ezdxf.readfile(path)
    doc.layers.new('AUX'); doc.layers.new('OFF',dxfattribs={'flags':1})
    doc.modelspace().add_line((-10,-10),(300,-10),dxfattribs={'layer':'AUX'})
    doc.modelspace().add_line((-20,-20),(300,-20),dxfattribs={'layer':'OFF'})
    doc.modelspace().add_lwpolyline([(-30,-30),(300,-30),(300,110),(-30,110)],close=True)
    doc.saveas(path)
    with pytest.raises(ValueError,match='atanamadı'): read_dxf(path,drawing_layout=True)
    parts=read_dxf(path,drawing_layout=True,excluded_layers=['AUX'])
    assert [p.quantity for p in parts]==[2,3] and all(p.area<1500 for p in parts)


def test_blocks_rotation_attributes_units_and_layer_zero_inheritance(tmp_path):
    path=tmp_path/'blocks.dxf'; doc=ezdxf.new(); doc.units=5  # cm
    block=doc.blocks.new('CELL'); cell(block,0,0,None,hole=False)
    block.add_attdef('COUNT',(40,65),dxfattribs={'height':3})
    doc.layers.new('CELLS')
    insert=doc.modelspace().add_blockref('CELL',(10,20),dxfattribs={'rotation':25,'layer':'CELLS'})
    insert.add_auto_attribs({'COUNT':'QTY: 8'})
    doc.saveas(path)
    parts=read_dxf(path,drawing_layout=True)
    assert len(parts)==1 and parts[0].quantity==8 and parts[0].area==pytest.approx(150000)
    with pytest.raises(ValueError,match='adet yazısı bulunamadı'):
        read_dxf(path,drawing_layout=True,excluded_layers=['CELLS'])


def test_strict_reader_still_rejects_open_or_crossing_cut_geometry(tmp_path):
    path=drawing(tmp_path,(1,)); doc=ezdxf.readfile(path)
    doc.modelspace().add_line((25,12),(55,35)); doc.saveas(path)
    with pytest.raises(ValueError,match='Çerçeve 1.*Açık'): read_dxf(path,drawing_layout=True)


def test_unitless_source_requires_unit_and_preserves_native_arcs(tmp_path):
    from modules.nesting.dxf_import import MissingUnits
    path=drawing(tmp_path,(4,)); doc=ezdxf.readfile(path); doc.units=0
    model=doc.modelspace()
    for e in list(model.query('CIRCLE')): model.delete_entity(e)
    for e in list(model.query('LWPOLYLINE'))[1:]: model.delete_entity(e)
    model.add_arc((45,20),20,0,180); model.add_line((25,20),(65,20)); doc.saveas(path)
    with pytest.raises(MissingUnits): read_dxf(path,drawing_layout=True)
    parts=read_dxf(path,drawing_layout=True,unit='mm')
    assert parts[0].quantity==4 and 627<parts[0].area<629
    assert sorted(e.dxftype() for e in ezdxf.read(StringIO(parts[0].original_dxf)).modelspace())==['ARC','LINE']


def test_dwg_conversion_passes_layout_option_and_retains_original_provenance(tmp_path,monkeypatch):
    import hashlib
    source=tmp_path/'toplu.dwg'; source.write_bytes(b'AC1032 simulated conversion input')
    fixture=drawing(tmp_path,(2,8))
    def convert(copy,target,stop):
        assert copy.read_bytes()==source.read_bytes() and copy!=source
        target.write_bytes(fixture.read_bytes())
    monkeypatch.setattr('modules.nesting.dwg_import.convert_dwg',convert)
    row,_=run(source)
    review=row['contour_review']
    assert review['sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert [p['quantity'] for p in review['drawing_parts']]==[2,8]
    row,_=run(source,approval=review)
    assert all(p.source==str(source.resolve()) for p in row['parts'])


def test_limits_cancellation_and_project_review_roundtrip(tmp_path):
    path=drawing(tmp_path,(5000,5001))
    assert run(path)[0]['status']=='error'
    path=drawing(tmp_path,(2,3))
    row,entry=run(path)
    review=row['contour_review']
    entry.update(status='review',detail=row['detail'],contour_review=review)
    project=new_project(); target=tmp_path/'pending.goknest.json'
    save_project(project,target,imports=[entry])
    _,_,entries=load_project(target,with_imports=True)
    assert entries==[entry]
    row,_=run(path,approval=review,existing_quantity=9996)
    assert row['status']=='error' and '10000' in row['detail']
    stop=Event(); stop.set()
    with pytest.raises(InterruptedError): read_dxf(path,drawing_layout=True,stop=stop)
    with pytest.raises(ValueError,match='tek grup'): normalize_options(dict(drawing_layout=True,grouped=True))


def test_end_to_end_nesting_export_uses_cut_geometry_only(tmp_path):
    from modules.nesting.engine import nest
    from modules.nesting.dxf_export import export_dxf
    from modules.nesting.validation import validate_result
    path=drawing(tmp_path,(1,2))
    project=new_project(); project.parts=read_dxf(path,drawing_layout=True)
    project.options.quality='Hızlı'
    result=nest(project); assert validate_result(project,result)
    assert len(result.placements)==3
    outputs=export_dxf(project,result,tmp_path/'cut')
    entities=list(ezdxf.readfile(outputs[0]).modelspace())
    assert len([e for e in entities if e.dxftype()=='CIRCLE'])==3
    assert len([e for e in entities if e.dxf.layer=='PART_OUTER'])==3
    target=tmp_path/'ready.goknest.json'; save_project(project,target,result)
    assert [p.quantity for p in load_project(target)[0].parts]==[1,2]
