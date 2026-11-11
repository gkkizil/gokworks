"""Physical radius and finite-data guards before entering the CAD kernel."""
from dataclasses import replace
from math import radians

import pytest
from shapely.geometry import box

from modules.press_brake.demo import load_demo, tools
from modules.press_brake.models import Bend, Flange, Part, Plan, Region, Segment, Step


def shallow_bend():
    thickness, inner, k, turn = 2., .2, .5, 30.
    width = (inner+k*thickness)*radians(turn)
    bend = Bend('B','F0','F1',(0,0),(50,0),width,180-turn,inner,1,
                Region.from_polygon(box(0,0,50,width)))
    part = Part('Shallow','A','Steel',thickness,'F0',
                (Flange('F0',Region.from_polygon(box(0,-20,50,0))),
                 Flange('F1',Region.from_polygon(box(0,width,50,width+20)))),
                (bend,),'F0','fixture')
    return Plan(part,(Step('B'),),tools()).validate()


@pytest.mark.parametrize('target',[1,90,120,144])
def test_target_rejects_nonpositive_inner_radius_even_when_mid_radius_is_positive(target):
    p = shallow_bend()
    # Independent bend-allowance relation BA=(R_i + K*t)*turn.
    neutral = p.part.bends[0].width/radians(180-target)
    assert neutral > 0 and neutral-.5*p.part.thickness <= 1e-12
    with pytest.raises(ValueError,match='iç R'):
        replace(p,steps=(replace(p.steps[0],target=target),)).validate()


@pytest.mark.parametrize('target',[145,150,160,179])
def test_target_with_positive_inner_radius_keeps_measured_developed_width(target):
    p = shallow_bend()
    result = replace(p,steps=(replace(p.steps[0],target=target),)).validate()
    assert result.part == p.part


@pytest.mark.parametrize('field',['punch_segments','die_segments'])
@pytest.mark.parametrize('segment',[Segment(float('nan'),10),Segment(float('inf'),10),
                                    Segment(0,float('nan')),Segment(0,float('inf')),
                                    Segment(0,0),Segment(0,-1),Segment(None,10),
                                    Segment(0,'bad'),Segment(10**1000,10),Segment(False,10)])
def test_nonfinite_or_nonpositive_override_segments_are_rejected_before_geometry(field,segment):
    p=load_demo('L120')
    with pytest.raises(ValueError,match='segment'):
        replace(p,steps=(replace(p.steps[0],**{field:(segment,)}),)).validate()


def test_empty_segment_override_remains_a_diagnosable_missing_assignment():
    p=load_demo('L120')
    replace(p,steps=(replace(p.steps[0],punch_segments=()),)).validate()
