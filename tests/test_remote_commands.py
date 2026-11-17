"""`GOKWORKS --open <tool> [--active]`: forwarded to the running window, allow-listed only."""
import json

import pytest

from gui_qt import remote
from gui_qt.app import MODULES, MainWindow, create_application

KEYS = {key for key, _, _ in MODULES}


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(remote, 'server_name', lambda: f'GOKWORKS-test-{tmp_path.name}')
    create_application([])
    w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w); w.show()
    w.command_server = remote.CommandServer(w, KEYS)
    yield w
    w.close()


def test_command_line_parsing():
    assert remote.parse(['GOKWORKS.exe']) is None
    assert remote.parse(['GOKWORKS.exe', '--open', 'weight']) == {'module': 'weight', 'active': False}
    assert remote.parse(['x', '--open', 'automatic_drawing', '--active']) == {'module': 'automatic_drawing', 'active': True}
    for bad in (['x', '--open'], ['x', '--open', 'Weight; rm'], ['x', '--open', '../etc']):
        with pytest.raises(SystemExit):
            remote.parse(bad)


@pytest.mark.parametrize('raw', [b'not json', b'[]', b'{"module": "nope"}', b'{"module": "weight", "active": "yes"}',
                                 b'{"module": "weight", "run": "rm -rf"}', '{"module": "ağırlık"}'.encode()])
def test_malformed_or_unknown_commands_are_rejected(raw):
    assert remote.validated(raw, KEYS) is None
    assert remote.validated(b'{"module": "weight", "active": true}', KEYS) == {'module': 'weight', 'active': True}


def test_every_active_action_is_a_real_page_method_of_a_known_tool(window):
    for key, (method, _) in remote.ACTIVE_ACTIONS.items():
        assert key in KEYS and callable(getattr(window.pages[key], method))


def test_second_start_hands_its_command_to_the_running_window(window, qtbot, monkeypatch):
    assert window.command_server.listening
    called = []
    page = window.pages['automatic_drawing']
    monkeypatch.setattr(page, 'use_active', lambda: called.append('use_active'))
    assert remote.send({'module': 'automatic_drawing', 'active': True})
    qtbot.waitUntil(lambda: window.mode == 'automatic_drawing' and called == ['use_active'], timeout=3000)
    assert remote.send({'module': 'weight', 'active': False})
    qtbot.waitUntil(lambda: window.mode == 'weight', timeout=3000)
    assert called == ['use_active']                       # no action without --active


def test_unknown_tool_over_the_socket_changes_nothing(window, qtbot):
    window.navigate('weight')
    from PySide6.QtNetwork import QLocalSocket
    socket = QLocalSocket(); socket.connectToServer(remote.server_name())
    assert socket.waitForConnected(1000)
    socket.write(json.dumps({'module': 'nope', 'active': True}).encode()+b'\n'); socket.waitForBytesWritten(1000)
    qtbot.wait(200)
    assert window.mode == 'weight'


def test_no_running_window_means_send_reports_failure(monkeypatch, tmp_path):
    create_application([])
    monkeypatch.setattr(remote, 'server_name', lambda: f'GOKWORKS-none-{tmp_path.name}')
    assert remote.send({'module': 'weight', 'active': False}, timeout_ms=200) is False


def test_a_second_window_never_takes_over_the_first_windows_channel(window, qtbot, monkeypatch):
    second = remote.CommandServer(window, KEYS)
    assert window.command_server.listening and not second.listening
    called = []
    monkeypatch.setattr(window, 'navigate', lambda key: called.append(key))
    assert remote.send({'module': 'weight', 'active': False})
    qtbot.waitUntil(lambda: called == ['weight'], timeout=3000)
