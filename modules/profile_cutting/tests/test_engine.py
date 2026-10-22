from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from threading import Event

import pytest

from modules.profile_cutting.models import Project, Demand
from modules.profile_cutting.optimizer import optimize, validate_plan
from modules.profile_cutting.scanner import Cancelled
from modules.profile_cutting.properties import length_mm, angle_degrees, DEFAULT_MAPPING, evaluated, validate_mapping
from modules.profile_cutting.models import Property
from modules.profile_cutting.storage import save, load, export_report
from .test_scanner import read
from .fakes import Model, Folder


def test_exact_stock_conservation_counts_kerf_allowance_and_both_trim_ends():
    p=Project([Demand('a','40×40×2','S235JR','1000',5,allowance='5')],kerf='3',trim='10')
    plan=optimize(p)
    assert len(plan.bars)==1 and plan.bars[0].remaining=='940'
    assert Decimal('6000')==Decimal(20)+5*Decimal(1008)+Decimal(plan.bars[0].remaining)
    assert plan.optimal


def test_multiple_lengths_combine_but_material_thickness_standard_and_stock_do_not_mix():
    assert Demand('x','40 × 40 × 2','s235jr','500',1,thickness='2,00').group == Demand('y','40x40x2','S235JR','500',1,thickness='2').group
    rows=[Demand('a','40×40×2','S235JR','3000',1),Demand('b','40×40×2','S235JR','2000',1)]
    base=rows[0]
    rows += [replace(base,id='c',material='S355JR'), replace(base,id='d',thickness='3'),
             replace(base,id='e',standard='EN10219'),replace(base,id='f',stock_code='STK-2')]
    plan=optimize(Project(rows))
    assert len(plan.bars)==5 and len(plan.bars[0].cuts)==2


def test_exact_search_improves_a_best_fit_failure():
    # Capacity 10: best-fit decreasing uses 3 bins; optimum is 2.
    sizes=[6,5,3,2,2,2]
    p=Project([Demand(str(i),'bar','S235JR',str(n),1) for i,n in enumerate(sizes)],stock_length='10',kerf='0')
    plan=optimize(p)
    assert len(plan.bars)==2 and plan.optimal


def test_many_pieces_do_not_claim_unproved_optimality():
    sizes=[6,5,3,2,2,2]*4
    p=Project([Demand(str(i),'bar','S235JR',str(n),1) for i,n in enumerate(sizes)],stock_length='10',kerf='0')
    plan=optimize(p)
    assert not plan.optimal and 'garanti' in plan.method


@pytest.mark.parametrize('field,value',[('stock_length','0'),('kerf','-1'),('trim','3000')])
def test_invalid_stock_options_are_rejected(field,value):
    p=Project([Demand('a','40×40×2','S235JR','1000',1)])
    setattr(p,field,value)
    with pytest.raises(ValueError): optimize(p)


def test_oversize_piece_with_kerf_is_reported_and_no_partial_plan_is_returned():
    p=Project([Demand('a','bar','S235JR','6000',1)])
    with pytest.raises(ValueError,match='sığmıyor'): optimize(p)


def test_cancellation_and_tampered_quantity_or_material_are_rejected():
    p=Project([Demand('a','bar','S235JR','1000',2)])
    stop=Event();stop.set()
    with pytest.raises(Cancelled): optimize(p,stop=stop)
    plan=optimize(p);plan.bars[0].cuts.pop()
    with pytest.raises(ValueError):validate_plan(p,plan)
    plan=optimize(p);plan.bars[0].group=('different',)
    with pytest.raises(ValueError):validate_plan(p,plan)


@pytest.mark.parametrize('text,unit,expected',[('1,5 m','mm','1500'),('2 in','mm','50.8'),('10','in','254.0'),('1','m','1000'),('1000 mm','','1000')])
def test_document_text_and_explicit_property_units(text,unit,expected):
    assert length_mm(text,unit)==Decimal(expected)


@pytest.mark.parametrize('text',['','SW-Bounding Box Length@Part','1,234.56','NaN','-1'])
def test_invalid_or_unresolved_length_is_never_guessed(text):
    with pytest.raises(ValueError):length_mm(text)


def test_case_insensitive_property_mapping_uses_only_resolved_values_and_detects_conflicts():
    props={'length':Property('length','expression','500',True)}
    assert evaluated(props,['LENGTH'])=='500'
    props['length'].resolved=False
    assert evaluated(props,['LENGTH'])==''
    props['length'].resolved=True;props['boy']=Property('boy','','600',True)
    with pytest.raises(ValueError,match='çelişiyor'):evaluated(props,['LENGTH','BOY'])
    mapping=deepcopy(DEFAULT_MAPPING);mapping['length']=['CUSTOM-LENGTH']
    assert validate_mapping(mapping)==mapping
    mapping['profile']=['CUSTOM-LENGTH']
    with pytest.raises(ValueError):validate_mapping(mapping)
    assert angle_degrees('45°')==45
    assert evaluated({'açı1':Property('açı1','','45',True)},['AÇI1'])=='45'


def test_atomic_project_roundtrip_scan_properties_and_local_report(tmp_path):
    result,_=read(Model(tmp_path/'part.SLDPRT',[Folder()]))
    p=Project([Demand('manual','40×40×2','S235JR','1000',3)])
    path=tmp_path/'analysis.gokprofile';save(p,result,path)
    again,scan=load(path)
    assert again==p and scan==result
    target=tmp_path/'report.csv';export_report(p,result,optimize(p),target)
    text=target.read_text(encoding='utf-8-sig')
    assert '$PRP:LENGTH' in text and 'GOKWORKS' in text and 'Testere' in text
    assert not list(tmp_path.glob('*.tmp'))


def test_cancelled_report_preserves_previous_file_and_property_text_cannot_be_excel_formula(tmp_path):
    p=Project([Demand('m','=danger','S235JR','500',1)])
    target=tmp_path/'report.csv';target.write_text('previous')
    stop=Event();stop.set()
    with pytest.raises(Cancelled):export_report(p,None,None,target,stop=stop)
    assert target.read_text()=='previous'
    export_report(p,None,None,target)
    assert "'=danger" in target.read_text(encoding='utf-8-sig')
