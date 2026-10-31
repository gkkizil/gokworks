from hashlib import sha256
from pathlib import Path
from queue import Queue
from threading import Event

import ezdxf
import pytest
import os

from modules.nesting.folder_import import discover_sources
from modules.nesting.dwg_import import read_dwg,convert_dwg
from modules.nesting.filename_parser import parse_filename
from modules.nesting.batch_import import import_batch


def dxf(path):
    doc=ezdxf.new();doc.units=4
    doc.modelspace().add_lwpolyline([(0,0),(30,0),(30,20),(0,20)],close=True)
    doc.saveas(path)


def test_recursive_scan_prefers_only_same_directory_dxf_pairs(tmp_path):
    sub=tmp_path/'sub';sub.mkdir()
    for p in (tmp_path/'A.DXF',tmp_path/'a.dwg',sub/'A.dwg',sub/'B.dxf',tmp_path/'other.txt'):p.touch()
    files,paired=discover_sources(tmp_path)
    assert set(map(Path,files))=={tmp_path/'A.DXF',sub/'A.dwg',sub/'B.dxf'}
    assert paired==[str(tmp_path/'a.dwg')]
    assert len(discover_sources(tmp_path,recursive=False)[0])==1
    assert len(discover_sources(tmp_path,prefer_dxf=False)[0])==4


def test_scan_is_cancellable_and_does_not_follow_directory_symlinks(tmp_path):
    stop=Event();stop.set()
    with pytest.raises(InterruptedError):discover_sources(tmp_path,stop=stop)
    with pytest.raises(ValueError,match='bulunamadı'):discover_sources(tmp_path/'missing')
    try:(tmp_path/'loop').symlink_to(tmp_path,target_is_directory=True)
    except OSError:pytest.skip('Directory symlinks unavailable')
    (tmp_path/'one.dxf').touch()
    assert len(discover_sources(tmp_path)[0])==1


def test_dwg_uses_temporary_copy_preserves_source_and_original_provenance(tmp_path,monkeypatch):
    source=tmp_path/'Plate - 2 mm - 3 adet.DWG';original=b'AC1032 fixture DWG';source.write_bytes(original)
    paths=[]
    def convert(copy,target,stop):
        paths.extend((copy,target));assert copy!=source and copy.read_bytes()==original
        dxf(target)
    monkeypatch.setattr('modules.nesting.dwg_import.convert_dwg',convert)
    parts=read_dwg(source,quantity=3)
    assert len(parts)==1 and parts[0].quantity==3 and parts[0].polygon.area==600
    assert parts[0].source==str(source) and parts[0].source_sha256==sha256(original).hexdigest()
    assert source.read_bytes()==original and not any(p.exists() for p in paths)
    detected=parse_filename(source)
    assert detected.thickness==2 and detected.quantity==3


def test_dwg_conversion_failure_is_per_file_and_other_dxf_still_imports(tmp_path,monkeypatch):
    dwg=tmp_path/'bad.dwg';dwg.write_bytes(b'AC1032 fixture')
    good=tmp_path/'good.dxf';dxf(good)
    def missing(*args):raise ValueError('DWG için ODA File Converter gerekli')
    monkeypatch.setattr('modules.nesting.dwg_import.convert_dwg',missing)
    events=Queue();import_batch([dict(id='bad',source=str(dwg)),dict(id='good',source=str(good))],{},events,Event())
    summary=events.queue[-1][1]
    assert summary['errors']==1 and summary['ready']==1
    assert any(k=='nest_file' and v['status']=='error' and 'ODA' in v['detail'] for k,v in events.queue)


@pytest.mark.parametrize('stopped',[False,True])
def test_converter_timeout_or_stop_kills_only_its_own_process(tmp_path,monkeypatch,stopped):
    stop=Event();killed=[]
    class Process:
        returncode=None
        def poll(self):return None if not killed else -9
        def kill(self):killed.append(True)
        def wait(self,timeout):return -9
    def launch(*args,**kwargs):
        if stopped:stop.set()
        return Process()
    monkeypatch.setattr('modules.nesting.dwg_import.converter_path',lambda:'fake-oda')
    monkeypatch.setattr('modules.nesting.dwg_import.subprocess.Popen',launch)
    with pytest.raises(InterruptedError if stopped else TimeoutError):
        convert_dwg(tmp_path/'source.dwg',tmp_path/'source.dxf',stop,timeout=0)
    assert killed==[True]


@pytest.mark.skipif(not os.environ.get('GOKWORKS_NESTING_DWG_LIVE_SOURCE'),reason='Explicit DWG test copy and installed local ODA File Converter required.')
def test_live_dwg_conversion_preserves_original_source():
    source=Path(os.environ['GOKWORKS_NESTING_DWG_LIVE_SOURCE']);before=source.read_bytes()
    parts=read_dwg(source)
    assert parts and all(p.polygon.area>0 and p.original_dxf for p in parts)
    assert source.read_bytes()==before
