import threading
from unittest.mock import patch
import pytest
from modules.shaft_generator.models import Project
from modules.shaft_generator.controller import request,create
from modules.shaft_generator.bridge import checked_payload,execute,HOST_SOURCE


def test_invalid_geometry_cannot_connect_to_solidworks():
    p=Project();p.stages[0].diameter=-10
    with patch('modules.shaft_generator.bridge.execute') as bridge:
        with pytest.raises(ValueError):create(p,None,threading.Event())
        bridge.assert_not_called()


def test_tampered_or_stale_plan_rejected():
    payload=request(Project());payload['project']['stages'][0]['length']=100
    with pytest.raises(ValueError,match='eşleşmiyor'):checked_payload(payload)


def test_output_must_be_new_part_and_existing_file_is_preserved(tmp_path):
    target=tmp_path/'existing.SLDPRT';target.write_bytes(b'CAD user data')
    with pytest.raises(FileExistsError):checked_payload(request(Project(),output_path=target))
    assert target.read_bytes()==b'CAD user data'
    with pytest.raises(ValueError):checked_payload(request(Project(),output_path=tmp_path/'model.step'))
    assert checked_payload(request(Project(),output_path=tmp_path/'new.SLDPRT'))


def test_cancellation_before_launch_and_result_delivery():
    class Sink:
        def __init__(self):self.items=[]
        def put(self,value):self.items.append(value)
    stop=threading.Event();stop.set();events=Sink()
    with patch('modules.shaft_generator.bridge.execute') as bridge:
        create(Project(),events,stop);bridge.assert_not_called()
    assert events.items==[('shaft_cancelled',None)]
    stop.clear()
    with patch('modules.shaft_generator.bridge.execute',return_value={'success':True}):create(Project(),events,stop)
    assert events.items[-1]==('shaft_created',{'success':True})


def test_linux_reports_platform_limit_without_simulating_cad():
    with patch('modules.shaft_generator.bridge.sys.platform','linux'):
        with pytest.raises(RuntimeError,match='Windows'):execute(request(Project()))
    assert HOST_SOURCE.is_file()
