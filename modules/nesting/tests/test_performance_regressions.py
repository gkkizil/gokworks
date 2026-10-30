"""Exact domain behavior around local caches and spatial broad phases."""
from dataclasses import replace
from decimal import Decimal
from io import StringIO
from threading import Event

import ezdxf
import pytest
from shapely.geometry import Polygon,mapping

from modules.nesting.models import Project,Material,Sheet,Part,Placement,Result
from modules.nesting.accounting import calculate
from modules.nesting.dxf_import import read_dxf


def test_repeated_part_metrics_preserve_holes_weights_costs_and_instance_order():
    polygon=Polygon([(0,0),(30,0),(30,20),(0,20)],holes=[[(10,5),(14,5),(14,9),(10,9)]])
    p=Project(materials=[Material('steel','Steel',7850)],
              parts=[Part('p','P',mapping(polygon),'steel',2,quantity=3)],
              sheets=[Sheet('s','Sheet',width=300,height=100,material='steel',pricing='sheet',price_sheet=100)])
    p.options.margin=1;p.operations.cut_price_m=30;p.operations.piercing_price=2
    def plan():
        return Result(p.fingerprint(),[Placement('p',i+1,'s',1,10+i*70,10,0) for i in range(3)],[],
                      'test','1',0,1,'2026-10-30T00:00:00Z')
    result=calculate(p,plan())
    assert [row['instance'] for row in result['parts']]==[1,2,3]
    assert [row['allocation'] for row in result['parts']]==[33.33,33.33,33.34]
    assert result['net_area']==3*(600-16) and result['net_weight']==pytest.approx(3*584*2*7850/1e9)
    assert result['piercing_count']==6 and result['cut_length_m']==pytest.approx(3*(100+16)/1000)
    assert Decimal(str(result['cut_cost']))==Decimal('10.44')
    assert result['part_summary'][0]['total_weight']==pytest.approx(result['net_weight'])
    # A second call after both geometry and prices change must not reuse old metrics.
    p.parts[0].geometry=mapping(Polygon([(0,0),(20,0),(20,20),(0,20)]))
    p.sheets[0].price_sheet=120
    changed=calculate(p,plan())
    assert changed['net_area']==1200 and changed['piercing_count']==3
    assert changed['material_cost']==120 and changed['cut_length_m']==pytest.approx(.24)
    assert changed['parts'][0]['holes']==0


def test_indexed_dxf_classification_preserves_nested_holes_islands_and_original_entities(tmp_path):
    source=tmp_path/'nested.dxf';doc=ezdxf.new();doc.units=4
    # Outer, hole, island, island hole; plus a disjoint part, in deliberate source order.
    for x,y,w,h in ((0,0,100,100),(10,10,80,80),(20,20,60,60),(30,30,40,40),(200,0,30,20)):
        doc.modelspace().add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],close=True)
    doc.saveas(source);before=source.read_bytes();parts=read_dxf(source)
    assert sorted(p.area for p in parts)==[600,2000,3600]
    assert sorted(len(p.polygon.interiors) for p in parts)==[0,1,1]
    assert sorted(len(ezdxf.read(StringIO(p.original_dxf)).modelspace()) for p in parts)==[1,2,2]
    assert source.read_bytes()==before
    grouped=read_dxf(source,grouped=True)
    assert len(grouped)==1 and grouped[0].area==6200
    stop=Event();stop.set()
    with pytest.raises(InterruptedError): read_dxf(source,stop=stop)


def test_touching_contours_remain_rejected_after_spatial_indexing(tmp_path):
    path=tmp_path/'touch.dxf';doc=ezdxf.new();doc.units=4
    for x,y in ((0,0),(20,20)):
        doc.modelspace().add_lwpolyline([(x,y),(x+20,y),(x+20,y+20),(x,y+20)],close=True)
    doc.saveas(path)
    with pytest.raises(ValueError): read_dxf(path)


def test_spatial_source_selection_retains_the_legacy_short_line_rule(tmp_path):
    path=tmp_path/'short.dxf';doc=ezdxf.new();doc.units=4;m=doc.modelspace()
    m.add_lwpolyline([(0,0),(20,0),(20,20),(0,20)],close=True)
    points=[(100,0),(100.0015,0),(100.00075,.001299038106)]
    for a,b in zip(points,points[1:]+points[:1]): m.add_line(a,b)
    doc.saveas(path);parts=read_dxf(path)
    big=next(p for p in parts if p.area>100)
    original=ezdxf.read(StringIO(big.original_dxf))
    assert len(list(original.modelspace().query('LINE')))==3
