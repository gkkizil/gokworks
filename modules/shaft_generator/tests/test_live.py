"""Opt-in native CAD acceptance: never run against an existing document."""

import os
import math
from pathlib import Path
import pytest
from modules.shaft_generator.models import Project,Stage,Groove,Keyway,Chamfer,Fillet
from modules.shaft_generator.controller import request
from modules.shaft_generator.bridge import execute


@pytest.mark.skipif(os.name!='nt' or os.environ.get('GOKWORKS_SHAFT_LIVE')!='1',
                   reason='Windows, açık SOLIDWORKS ve GOKWORKS_SHAFT_LIVE=1 gerekli; Linux CAD çalıştırmaz.')
@pytest.mark.parametrize('case',['single','stages','equal','groove','zero_groove','keyway','zero_keyway',
                               'single_groove','single_keyway','wide_keyway','short_keyway','two_keyways','two_grooves','two_grooves_keyway',
                               'chamfer','fillet','operations'])
def test_native_driving_dimensions_features_rebuild_save_and_reopen(tmp_path,case):
    p=Project()
    if case=='single':p.stages=[Stage(30,80)]
    if case in ('single_groove','single_keyway'):p.stages=[Stage(30,40)]
    if case=='equal':p.stages=[Stage(30,40),Stage(30,40)]
    if case in ('groove','zero_groove'):p.operations=[Groove(p.stages[0].id,offset=0 if case=='zero_groove' else 5)]
    if case in ('keyway','zero_keyway'):p.operations=[Keyway(p.stages[0].id,offset=0 if case=='zero_keyway' else 5)]
    if case=='single_groove':p.operations=[Groove(p.stages[0].id)]
    if case=='single_keyway':p.operations=[Keyway(p.stages[0].id)]
    if case=='wide_keyway':p.operations=[Keyway(p.stages[2].id,offset=5,length=30,width=12,depth=4)]
    if case=='short_keyway':p.operations=[Keyway(p.stages[0].id,offset=5,length=8.1,width=8,depth=3)]
    if case=='two_keyways':p.operations=[Keyway(p.stages[0].id,offset=0),Keyway(p.stages[2].id,offset=5,width=10,depth=4)]
    if case=='chamfer':p.operations=[Chamfer(p.stages[0].id)]
    if case=='fillet':p.operations=[Fillet(p.stages[-1].id)]
    if case in ('two_grooves','two_grooves_keyway'):
        p.operations=[Groove(p.stages[0].id,offset=5),Groove(p.stages[1].id,offset=5)]
        if case=='two_grooves_keyway':p.operations.append(Keyway(p.stages[2].id,offset=5))
    if case=='operations':
        p.operations=[Groove(p.stages[1].id,offset=8),Keyway(p.stages[2].id,offset=10,length=25,width=8,depth=3),
                      Chamfer(p.stages[0].id),Fillet(p.stages[-1].id)]
    output=tmp_path/f'{case}.SLDPRT'
    result=execute(request(p,output_path=output,verify_edit=True))
    assert result['edit_verified'] and result['fully_defined'] and result['single_body'] and result['rebuild_success']
    assert output.is_file() and output.stat().st_size>0
    assert result['feature_count']==len(p.stages)+len(p.operations)
    assert result['volume_m3']>0
    if case.startswith('zero_'):assert result['zero_offset_verified']
    if case in ('single','equal','stages','groove','zero_groove','keyway','zero_keyway',
                'single_groove','single_keyway','wide_keyway','short_keyway','two_keyways','two_grooves','two_grooves_keyway'):
        # Independent slice integration, not a mock return value.
        volume=sum(math.pi*(s.diameter/2)**2*s.length for s in p.stages)
        for op in p.operations:
            r=p.stage(op.stage_id).diameter/2
            if isinstance(op,Groove):volume-=math.pi*(r*r-(r-op.depth)**2)*op.width
            else:
                from modules.shaft_generator.tests.volume_reference import rounded_keyway_volume
                volume-=rounded_keyway_volume(p.stage(op.stage_id).diameter,op.length,op.width,op.depth)
        assert result['volume_m3']==pytest.approx(volume*1e-9,rel=1e-6)
