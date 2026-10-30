"""Opt-in licensed SOLIDWORKS acceptance with user-supplied disposable fixtures.

Manifest format is documented in MULTIBODY_DXF_DWG_RAPORU.md. Default CI never
pretends synthetic DXF data is an actual SOLIDWORKS geometry acceptance test.
"""
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import sys
import pytest


@pytest.mark.skipif(sys.platform!='win32' or not os.environ.get('GOKWORKS_DXF_MULTIBODY_MANIFEST'),
                   reason='Windows, licensed running SOLIDWORKS and an explicit disposable fixture manifest required.')
@pytest.mark.parametrize('format',['dxf','dwg'])
def test_live_body_inventory_native_outputs_and_source_preservation(tmp_path,format):
    from modules.cad_converter.api import call,get,interface,ASSEMBLY_IID
    from modules.profile_cutting.solidworks import values
    from modules.dxf_dwg.sheetmetal import Session,scan_inventory
    from modules.dxf_dwg.exporter import export_selection
    from modules.dxf_dwg.preview.flat import read_flat
    from modules.dxf_dwg.preview.solidworks import capture
    from modules.dxf_dwg.preview.models import Request,MeshCache
    manifest=json.loads(Path(os.environ['GOKWORKS_DXF_MULTIBODY_MANIFEST']).read_text(encoding='utf-8-sig'))
    source=str(Path(manifest['source']).resolve());expected=manifest['expected']
    paths={source,*(str(Path(row['source']).resolve()) for row in expected)}
    before={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
    def state():
        with Session() as session:
            model=session.document();kind=call(model,'GetType');components=()
            try:
                if kind==session.c('swDocASSEMBLY'):
                    assembly=interface(model,ASSEMBLY_IID)
                    components=values(call(assembly,'GetComponents',False))
                    suppressed=sorted((str(get(c,'Name2')),call(c,'GetSuppression2')) for c in components)
                else:suppressed=[]
                return call(model,'GetPathName'),session.active_configuration(model),suppressed
            finally:model=assembly=None;components=()
    previous=state()
    with Session() as session:rows,warnings=scan_inventory(session,source,mode='file')
    assert not warnings and len(rows)==len(expected) and all(row['exportable'] for row in rows)
    reference={(str(Path(r['source']).resolve()).lower(),r['configuration'],r['body_name']):r for r in expected}
    for row in rows:
        e=reference[(str(Path(row['source']).resolve()).lower(),row['configuration'],row['body_name'])]
        assert row['quantity']==e['quantity'] and row['thickness_mm']==pytest.approx(e['thickness_mm'])
        result=capture(Request(row['source'],row['configuration'],row['body_ref'],quantity=row['quantity'],
                               flat_ref=row['flat_ref'],body_name=row['body_name']),MeshCache())
        assert result.mesh.triangles>0 and result.flat and result.flat.strokes
    events=Queue()
    export_selection(rows,Path(source).parent,tmp_path,(format,),events)
    assert events.queue[-1][1]['succeeded']==len(expected) and events.queue[-1][1]['failed']==0
    for kind,row in events.queue:
        if kind!='sheet_result':continue
        assert len(row['outputs'])==1 and row['outputs'][0]['status']=='success'
        if format=='dxf':
            flat=read_flat(row['outputs'][0]['path'])
            e=reference[(str(Path(row['source']).resolve()).lower(),row['configuration'],row['body_name'])]
            assert not any('birimi tanımlı değil' in w for w in flat.warnings)
            x0,y0,x1,y1=flat.bounds
            assert sorted((x1-x0,y1-y0))==pytest.approx(sorted(e['bounds_mm']),abs=.05)
    assert state()==previous
    assert {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}==before
