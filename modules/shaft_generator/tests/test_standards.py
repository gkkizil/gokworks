"""Catalogue selection, range boundaries and the nominal CAD data contract."""

import pytest
from modules.shaft_generator.standards import (GROOVE_SIZES, KEYWAY_SIZES,
    groove_size, keyway_size, keyway_lengths)
from modules.shaft_generator.models import Project, Stage, Groove, Keyway
from modules.shaft_generator.validation import validate
from modules.shaft_generator.controller import request


@pytest.mark.parametrize('diameter,d2,width,thickness,margin',[
    (3,2.8,.5,.4,.3),(25,23.9,1.3,1.2,1.7),(30,28.6,1.6,1.5,2.1),
    (35,33,1.6,1.5,3),(45,42.5,1.85,1.75,3.8),
    (65,62,2.65,2.5,4.5),(100,96.5,3.15,3,5.3),
])
def test_din471_reference_rows_use_groove_width_not_ring_thickness(diameter,d2,width,thickness,margin):
    row=groove_size(diameter)
    assert row.groove_diameter==d2 and row.width==width
    assert row.ring_thickness==thickness and row.edge_margin==margin
    assert row.depth==pytest.approx((diameter-d2)/2)
    assert row.width>row.ring_thickness


@pytest.mark.parametrize('diameter',[0,2,30.2,49,53,99,101,float('nan'),float('inf'),True,'30',None])
def test_din471_never_interpolates_or_rounds_an_unlisted_diameter(diameter):
    assert groove_size(diameter) is None


@pytest.mark.parametrize('diameter,width,height,depth',[
    (6,2,2,1.2),(8,2,2,1.2),(8.0001,3,3,1.8),(10,3,3,1.8),
    (12,4,4,2.5),(17,5,5,3),(22,6,6,3.5),(22.0001,8,7,4),
    (30,8,7,4),(30.0001,10,8,5),(38,10,8,5),(44,12,8,5),
    (44.0001,14,9,5.5),(50,14,9,5.5),(65,18,11,7),(500,100,50,31),
])
def test_din6885_ranges_and_shaft_depth_not_key_height_or_hub_depth(diameter,width,height,depth):
    row=keyway_size(diameter)
    assert (row.width,row.key_height,row.depth)==(width,height,depth)
    assert row.depth!=row.key_height and row.depth!=row.hub_depth


@pytest.mark.parametrize('diameter',[0,5.9999,500.0001,float('nan'),float('inf'),True,'30',None])
def test_outside_keyway_catalogue_is_custom(diameter):
    assert keyway_size(diameter) is None


def test_keyway_length_suggestions_respect_section_limits_and_remaining_stage():
    row=keyway_size(45)
    assert keyway_lengths(row,60)==(36,40,45,50,56,60)
    assert keyway_lengths(row,35)==()
    assert keyway_lengths(keyway_size(30),22)==(18,20,22)
    assert keyway_lengths(row,float('nan'))==()
    assert keyway_lengths(row,-1)==()
    assert keyway_lengths(None,100)==()
    # No unverified length range is invented for large cross-sections.
    assert keyway_lengths(keyway_size(150),1000)==()


def test_every_published_preset_creates_valid_nominal_parameters_and_keeps_v1_contract():
    assert len(GROOVE_SIZES)==76 and len(KEYWAY_SIZES)==26
    assert len({s.diameter for s in GROOVE_SIZES})==len(GROOVE_SIZES)
    for row in GROOVE_SIZES:
        p=Project(stages=[Stage(row.diameter,40)])
        op=Groove(p.stages[0].id,width=row.width,depth=row.depth)
        p.operations=[op]
        assert not validate(p)
        assert p.stages[0].diameter-2*op.depth==pytest.approx(row.groove_diameter)
    for i,row in enumerate(KEYWAY_SIZES):
        diameter=row.diameter_over if i==0 else (row.diameter_over+row.diameter_to)/2
        length=row.length_min or row.width*2
        p=Project(stages=[Stage(diameter,length+10)])
        p.operations=[Keyway(p.stages[0].id,width=row.width,depth=row.depth,length=length)]
        assert not validate(p)
        data=request(p)['project']
        assert data['version']==1 and data['units']=='mm'
        assert set(data['operations'][0])=={'id','kind','stage_id','offset','width','depth','length','angle'}
        assert Project.from_dict(data)==p
