"""Typed transport and unchanged reference checks; no live SolidWorks claims."""

import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from modules.naming import exporter as engine, native
from tests.support.solidworks import Variant
from modules.naming.tests.test_naming import App, Pack


class MissingParameter(Exception):
    hresult = -2147352561


class FakeClient:
    def __init__(self, app):
        self.app, self.pack = app, Pack(app)
        self.calls, self.closes = [], 0

    def request(self, operation, **values):
        self.calls.append((operation, values))
        if operation == 'get_flag':return getattr(self.pack, values['name'])
        if operation in ('set_flag', 'set_text'):
            setattr(self.pack, values['name'], values['value']);return True
        if operation == 'count':return self.pack.GetDocumentNamesCount()
        if operation == 'get_names':return list(self.pack.GetDocumentNames()[1])
        if operation == 'get_targets':return [list(part) for part in self.pack.GetDocumentSaveToNames()[1:]]
        if operation == 'set_folder':return self.pack.SetSaveToName(values['override'], values['path'])
        if operation == 'set_targets':return self.pack.SetDocumentSaveToNames(values['paths'])
        if operation == 'save':return list(self.app.save(self.pack))
        raise AssertionError(operation)

    def close(self):self.closes += 1


@pytest.fixture
def broken_automation(tmp_path, monkeypatch):
    app = App(tmp_path)
    ole = NS(GetIDsOfNames=Mock(return_value=207),
             GetTypeInfo=Mock(side_effect=RuntimeError('Invalid index')),
             InvokeTypes=Mock(side_effect=MissingParameter('Parametre seçime bağlı değil.')))
    app.extension._oleobj_ = ole
    app.extension._FlagAsMethod = Mock()
    com = NS(VT_ARRAY=8192, VT_BSTR=8, VT_BYREF=16384, VT_VARIANT=12,
             VT_I4=3, VT_DISPATCH=9, DISPATCH_METHOD=1)
    client = NS(VARIANT=Variant, dynamic=NS(DumbDispatch=lambda obj:obj))
    monkeypatch.setattr(engine, 'pythoncom', com)
    monkeypatch.setattr(engine, 'win32com', NS(client=client))
    clients = []
    def start(application, root):
        assert application is app and root == app.paths[0]
        client = FakeClient(app);clients.append(client)
        return native.Pack(client)
    monkeypatch.setattr(native, 'open_pack', start)
    return app, ole, clients


def test_exact_reported_automation_error_uses_typed_pack_and_preserves_file_order(broken_automation):
    app, ole, clients = broken_automation
    before = {path:Path(path).read_bytes() for path in app.paths}
    snapshot = engine.scan(app)
    assert [doc.path for doc in snapshot.documents] == app.paths
    assert clients[0].closes == 1 and app.saves == 0
    ole.InvokeTypes.assert_called_once_with(207, 0, 1, (9, 0), ())
    assert {path:Path(path).read_bytes() for path in app.paths} == before


def test_native_save_uses_own_extension_and_verifies_assembly_and_drawing_references(broken_automation, tmp_path):
    app, ole, clients = broken_automation
    before = {path:Path(path).read_bytes() for path in app.paths}
    snapshot = engine.scan(app)
    destination = tmp_path/'Yeni paket'
    entries = engine.plan_names(snapshot, destination, engine.Rules(prefix='BHV-', numbered=True))
    report = engine.execute(app, snapshot, entries, destination)
    assert report['file_references_verified'] is True and app.saves == 1
    assert [client.closes for client in clients] == [1, 1]
    assert [item for item in clients[1].calls if item[0]=='save'] == [('save', {})]
    for entry in entries:
        expected = [app.last_mapping[path] for path in json.loads(before[entry.source])['refs']]
        assert json.loads(Path(entry.destination).read_text(encoding='utf-8'))['refs'] == expected
    assert {path:Path(path).read_bytes() for path in app.paths} == before


@pytest.mark.parametrize('failure', ['virtual', 'cancel', 'bad_mapping', 'bad_references'])
def test_native_failure_and_cancel_release_client_without_publishing_package(broken_automation, tmp_path, failure):
    app, ole, clients = broken_automation
    if failure == 'virtual':
        app.states[0] = 1
        with pytest.raises(RuntimeError, match='Sanal'):engine.scan(app)
    else:
        snapshot = engine.scan(app)
        destination = tmp_path/'Çıktı'
        entries = engine.plan_names(snapshot, destination, engine.Rules(prefix='P-'))
        stop = threading.Event()
        if failure == 'cancel':app.on_save = stop.set;error = engine.Cancelled;match = None
        elif failure == 'bad_mapping':app.reject_names = True;error = RuntimeError;match = 'kabul etmedi'
        else:app.corrupt = True;error = RuntimeError;match = 'referansları doğrulanamadı'
        with pytest.raises(error, match=match):engine.execute(app, snapshot, entries, destination, stop)
        assert not destination.exists()
    assert all(client.closes == 1 for client in clients)


def test_real_api_failure_is_not_retried_with_native_host(broken_automation):
    app, ole, clients = broken_automation
    ole.InvokeTypes.side_effect = RuntimeError('CAD operation failed')
    with pytest.raises(RuntimeError, match='CAD operation failed'):engine.scan(app)
    assert clients == []


def test_unavailable_native_host_keeps_original_binding_error(broken_automation, monkeypatch):
    app, ole, clients = broken_automation
    monkeypatch.setattr(native, 'open_pack', Mock(side_effect=RuntimeError('Interop DLL missing')))
    with pytest.raises(RuntimeError, match='Interop DLL missing') as caught:engine.scan(app)
    assert isinstance(caught.value.__cause__, MissingParameter)
    assert 'Parametre seçime bağlı değil' in str(caught.value)
    assert app.saves == 0


def test_proxy_only_allows_supported_properties_and_unwraps_typed_target_array():
    client = NS(request=Mock(return_value=True), close=Mock())
    pack = native.Pack(client)
    pack.FlattenToSingleFolder = True
    pack.SetDocumentSaveToNames(Variant(8192 | 8, ('C:/İmalat/A.sldasm',)))
    assert client.request.call_args.kwargs['paths'] == ['C:/İmalat/A.sldasm']
    with pytest.raises(AttributeError):pack.UnknownMember = True
    with pytest.raises(TypeError):pack.IncludeDrawings = 'True'
    with pytest.raises(TypeError):pack.AddPrefix = 12


@pytest.mark.parametrize('response,match', [(None,'kapandı'), ({'ok':False,'error':'COM failure'},'COM failure'),
    ({'ok':1},'Geçersiz'), (ValueError('bad JSON'),'okunamadı')])
def test_transport_rejects_eof_failed_or_malformed_reply(response, match):
    client = object.__new__(native.Client)
    client.responses = queue.Queue();client.responses.put(response)
    with pytest.raises(RuntimeError, match=match):client._response()


def test_transport_request_escapes_turkish_paths_and_reports_pipe_failure():
    client = object.__new__(native.Client)
    client.closed = False
    client.process = NS(stdin=io.StringIO())
    client.responses = queue.Queue();client.responses.put({'ok':True,'result':True})
    path = 'C:/Yaptığım işler/"$script"/Parça.sldasm'
    assert client.request('set_folder', path=path) is True
    assert json.loads(client.process.stdin.getvalue()) == dict(operation='set_folder', path=path)
    client.process.stdin = NS(write=Mock(side_effect=BrokenPipeError()))
    with pytest.raises(RuntimeError, match='koptu'):client.request('get_names')


def test_transport_close_stops_only_owned_process_and_is_idempotent():
    client = object.__new__(native.Client)
    client.closed = False
    client.process = NS(stdin=io.StringIO(), stdout=io.StringIO(), poll=Mock(return_value=None),
                        wait=Mock(return_value=0), terminate=Mock())
    client.reader = NS(join=Mock())
    client.close();client.close()
    client.process.wait.assert_called_once_with(timeout=5)
    client.process.terminate.assert_not_called()
    client.reader.join.assert_called_once_with(timeout=2)


@pytest.mark.parametrize('value', [1234, lambda:1234])
def test_native_start_uses_exact_server_pid_for_both_dispatch_getter_shapes(value, monkeypatch, tmp_path):
    library = tmp_path/'SolidWorks.Interop.sldworks.dll'
    locate = Mock(return_value=library)
    client = Mock()
    construct = Mock(return_value=client)
    monkeypatch.setattr(native.sys, 'platform', 'win32')
    monkeypatch.setattr(native, '_installed_interop', locate)
    monkeypatch.setattr(native, 'Client', construct)
    root = 'C:/İmalat/Montaj.sldasm'
    pack = native.open_pack(NS(GetProcessID=value), root)
    locate.assert_called_once_with(1234)
    construct.assert_called_once_with(1234, root, library)
    pack.close();client.close.assert_called_once()


@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_INTEROP_TEST_DLL'),
                    reason='Windows PowerShell ve doğrulanmış test interop DLL’si seçilmedi.')
def test_windows_powershell_compiles_real_typed_host_without_starting_solidworks():
    library = Path(os.environ['GOKWORKS_INTEROP_TEST_DLL']).resolve()
    assert library.is_file()
    powershell = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    # Use the real loader and compiler, replacing only its final server entry.
    # There is no ROT lookup, CAD launch or CAD document in this test.
    marker = '[Gokworks.PackAndGoInterop.Host]::Run()'
    assert native.LOADER.count(marker) == 1
    script = native.LOADER.replace(marker, "[Console]::WriteLine('GOKWORKS_INTEROP_COMPILED')")
    result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-Command', script],
        env={**os.environ, 'GOKWORKS_PACKANDGO_INTEROP':str(library), 'GOKWORKS_PACKANDGO_HOST':str(native.HOST_SOURCE)},
        input='', encoding='utf-8', capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'GOKWORKS_INTEROP_COMPILED', result.stdout

