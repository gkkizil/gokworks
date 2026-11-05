"""Legacy-project, complete-record and source-quarantine regression tests."""

from dataclasses import replace
import json
from pathlib import Path
from queue import Queue
from threading import Event
import subprocess
import sys
import os
import re

import pytest

from modules.belt_drive import BeltDriveSpecification
from modules.belt_drive.serialization import dumps as legacy_dumps, loads as legacy_loads
from modules.belt_drive.design_search import search_drives
from modules.belt_drive.design_pairs import search_pulley_pairs
from modules.belt_drive.design_serialization import (DesignProject, project_dumps, project_loads,
    project_to_dict, project_from_dict, request_to_dict, request_from_dict, report_to_dict, recalculate_project)
from modules.belt_drive.controller import automatic_design_job
from modules.belt_drive.catalog.importers import catalog_dumps, load_catalog
from modules.belt_drive.catalog.manufacturers import GATES, OPTIBELT, TOSYALI
from modules.belt_drive.catalog.tosyali import parse_tosyali_layout
from .design_fixtures import request, timing_catalog

ROOT=Path(__file__).resolve().parents[3]
PDF_SHA='8399b6b5a123573e99e8a982afd6c7c1504e160edc845d6fc6218812461d689c'


def test_new_project_roundtrip_and_old_stage1_contract_unchanged():
    spec=BeltDriveSpecification()
    old=legacy_dumps(spec)
    assert legacy_loads(old)==spec
    assert project_loads(old)==DesignProject(manual=spec)
    assert recalculate_project(project_loads(old))[0].ratio==2.
    req,cat=request(),timing_catalog(rated=True)
    result=search_drives(req,cat)
    selected=(result.unverified[0].identifier,)
    project=DesignProject(req,cat,spec,selected)
    assert project_loads(project_dumps(project))==project
    rerun,selection=recalculate_project(project_loads(project_dumps(project)))
    assert rerun==result and selection==selected


def test_project_tampering_unknown_fields_and_stale_selection():
    project=DesignProject(request(),timing_catalog(),selected_ids=('stale-identifier',))
    report,selected=recalculate_project(project)
    assert not selected and report.unverified
    data=project_to_dict(project)
    data['catalog']['pulleys'][0]['teeth']=27
    with pytest.raises(ValueError,match='özeti'):
        project_from_dict(data)
    data=project_to_dict(project);data['computed_capacity']=999
    with pytest.raises(ValueError):
        project_from_dict(data)
    data=request_to_dict(request());data['unknown']=1
    with pytest.raises(ValueError):
        request_from_dict(data)
    with pytest.raises(ValueError):
        DesignProject()


def test_selected_comparison_report_preserves_inputs_scope_and_warnings():
    report=search_drives(request(),timing_catalog(widths=(10.,20.)))
    chosen=[report.unverified[1].identifier]
    data=report_to_dict(report,selected_ids=chosen)
    assert len(data['unverified'])==1 and data['unverified'][0]['identifier']==chosen[0]
    assert data['request']['target_rpm']==700. and data['catalog_revision']=='test-1'
    assert data['unverified'][0]['checks'] and not data['unverified'][0]['engineering_approved']
    assert data['sources'][0]['document']=='Test arithmetic contract' and not data['sources'][0]['officially_verified']
    json.dumps(data,allow_nan=False)
    with pytest.raises(ValueError):report_to_dict(report,selected_ids=['missing'])
    with pytest.raises(ValueError):report_to_dict(report,selected_ids=[{}])


def test_worker_protocol_and_controlled_cancelled_report():
    events=Queue();stop=Event()
    automatic_design_job(request(),timing_catalog())(events,stop)
    kind,report=events.get_nowait()
    assert kind=='belt_design_result' and report.search_complete and events.empty()
    stop.set()
    automatic_design_job(request(),timing_catalog())(events,stop)
    kind,report=events.get_nowait()
    assert kind=='belt_design_cancelled' and report.cancelled and not report.search_complete


def test_manufacturer_adapters_do_not_certify_user_claimed_official_metadata(tmp_path):
    cat=timing_catalog()
    for adapter in (GATES,OPTIBELT,TOSYALI):
        source=replace(cat.sources[0],manufacturer=adapter.name,verification_status='OFFICIAL_VERIFIED',url='https://'+adapter.official_domains[0])
        assert source.effective_status=='USER_SUPPLIED' and not source.officially_verified
        assert any(x.code=='SOURCE_AUTHENTICITY' for x in adapter.review(source))
        path=tmp_path/'catalog.json';path.write_text(catalog_dumps(replace(cat,sources=(source,))),encoding='utf-8')
        assert adapter.load(path).sources[0]==source
    with pytest.raises(ValueError):GATES.load(path)  # last file is Tosyalı, not Gates.


def tos_layout(rows,*,header='Dp De Df Dm F L Pilot Delik Kg',table_heading=None):
    # A few factual rows from supplied PDF page 20, printed page 18. Not a full PDF copy.
    if table_heading is None:
        parts=rows.split('-')
        profile=parts[1];width=re.match(r'\d+',parts[2]).group()
        pitch={'3M':3,'5M':5,'8M':8,'T5':5,'T10':10,'AT5':5,'AT10':10}[profile]
        title=('HTD '+profile) if profile.endswith('M') else profile
        table_heading=f'{title} - {width} Hatve: {pitch}mm Kayış Genişliği: {width}mm'
    return 'Tosyalı Teknik Bilgi Kataloğu\f'+'\f'*18+'Triger Dişliler\n'+table_heading+'\nSipariş Kodu Tip Diş Sayısı '+header+'\n'+rows+'\n18\f'


def test_actual_tosyali_factual_rows_reference_units_and_no_invented_belts():
    rows='T 10-3M-09F-AL 1F 10 9,55 8,79 13 6 10,2 17,5 4 0,004\nT 28-3M-09F-AL 6F 28 26,74 25,98 32 18 12,8 20,6 6 0,024'
    imported=parse_tosyali_layout(tos_layout(rows),document_sha256=PDF_SHA)
    assert imported.complete and imported.accepted_rows==2 and not imported.catalog.belts and not imported.catalog.ratings
    first=imported.catalog.pulleys[0]
    assert first.code=='T 10-3M-09F-AL' and first.teeth==10 and first.pitch_mm==3.
    assert first.nominal_belt_width_mm==9. and first.overall_width_mm==17.5
    assert first.face_width_mm is None and first.catalog_face_dimension_f_mm==10.2
    assert first.pilot_bore_mm==4 and first.outside_diameter_mm==13
    source=imported.catalog.sources[0]
    assert source.page=='PDF page 20; printed page 18' and source.effective_status=='USER_SUPPLIED'


@pytest.mark.parametrize('row',[
    # Real T5 table cell Dp=16.05 conflicts with 10*5/pi=15.915494309..., no silent repair.
    'T 10-T5-16F-AL 6F 10 16,05 15,05 20 8 21 27 4 0,016',
    # Synthetic corruption variants isolate row identity and column integrity.
    'T 10-3M-09F-AL 1F 12 9,55 8,79 13 6 10,2 17,5 4 0,004',
    'T 10-3M-09F-AL 1F 10 9,55 8,79 13 6 10,2 17,5 0,004',
])
def test_contradictory_or_ambiguous_pdf_rows_are_quarantined(row):
    result=parse_tosyali_layout(tos_layout(row),document_sha256=PDF_SHA)
    assert not result.complete and len(result.quarantined)==1 and not result.catalog.pulleys
    with pytest.raises(ValueError):
        parse_tosyali_layout(tos_layout(row),document_sha256=PDF_SHA,strict=True)


def test_tosyali_unsupported_bushed_table_and_at5_without_printed_dp():
    row='T 12-AT5-16F-AL 6F 12 17,85 23 11 21 27 4 0,022'
    report=parse_tosyali_layout(tos_layout(row,header='De Df Dm F L Pilot Delik Kg'),document_sha256=PDF_SHA)
    assert report.accepted_rows==1 and report.catalog.pulleys[0].catalog_pitch_diameter_mm is None
    skipped=parse_tosyali_layout(tos_layout(row,header='Burç De Df Dm F L Pilot Delik Kg'),document_sha256=PDF_SHA)
    assert skipped.unsupported_rows==1 and not skipped.catalog.pulleys
    wrong=parse_tosyali_layout(tos_layout(row,header='De Df Dm F L Pilot Delik Kg',
        table_heading='HTD 5M - 16 Hatve: 5mm Kayış Genişliği: 16mm'),document_sha256=PDF_SHA)
    assert not wrong.catalog.pulleys and wrong.quarantined
    with pytest.raises(ValueError):parse_tosyali_layout('not a manufacturer document',document_sha256=PDF_SHA)


def test_bundled_real_dimensions_and_pair_only_search_are_not_complete_drives():
    path=ROOT/'modules/belt_drive/catalog/data/tosyali-user-pdf.json'
    cat=load_catalog(path)
    assert len(cat.pulleys)==342 and not cat.belts and not cat.ratings
    assert {p.profile for p in cat.pulleys}=={'HTD_3M','HTD_5M','HTD_8M','AT5','AT10'}
    assert all(x.document_sha256==PDF_SHA and not x.officially_verified for x in cat.sources)
    req=request(rpm_error_max_percent=2.)
    pairs=search_pulley_pairs(req,cat)
    assert pairs.search_complete and pairs.matching_count==32
    best=pairs.alternatives[0]
    assert (best.driver_teeth,best.driven_teeth)==(12,25) and best.nominal_output_rpm==696.
    assert best.rpm_error_percent==pytest.approx(4/700*100)
    assert not best.complete_drive and not best.capacity_verified
    assert not search_drives(req,cat).unverified  # no belt SKU inferred from pulley width heading.
    assert not search_pulley_pairs(replace(req,include_unverified=False),cat).alternatives


def test_automatic_cli_and_pure_api_without_site_packages(tmp_path):
    req=tmp_path/'request.json';cat=tmp_path/'catalog.json'
    req.write_text(json.dumps(request_to_dict(request())),encoding='utf-8')
    cat.write_text(catalog_dumps(timing_catalog()),encoding='utf-8')
    command=[sys.executable,'-m','modules.belt_drive.design_cli',str(req),'--catalog',str(cat)]
    process=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert process.returncode==0,process.stderr
    assert len(json.loads(process.stdout)['unverified'])==1
    bad=subprocess.run(command[:-1]+[str(tmp_path/'absent')],cwd=ROOT,capture_output=True,timeout=20)
    assert bad.returncode==2 and b'Traceback' not in bad.stderr
    script='''
import sys
from modules.belt_drive.design_models import DesignRequest
from modules.belt_drive.design_search import search_drives
from modules.belt_drive.design_serialization import request_to_dict
from modules.belt_drive.catalog.products import ProductCatalog
from modules.belt_drive.catalog.tosyali import parse_tosyali_layout
assert search_drives(DesignRequest(1.5,1450,700),ProductCatalog('empty','1',(),(),())).search_complete
assert not {'PySide6','OCP','win32com','numpy','shapely','ezdxf'} & sys.modules.keys()
'''
    pure=subprocess.run([sys.executable,'-S','-c',script],cwd=ROOT,capture_output=True,timeout=20)
    assert pure.returncode==0,pure.stderr
