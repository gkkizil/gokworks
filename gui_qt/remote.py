"""Open a tool from outside (SolidWorks add-in, shortcut): ``GOKWORKS --open <tool> [--active]``.

One GOKWORKS per user session. A second start with ``--open`` hands its command to the
running window over a local socket and exits; without a running window it starts normally
and applies the command itself. Only known tool keys and the allow-listed "read the active
SolidWorks model" actions below are accepted; nothing else is executed from a message.
"""
import getpass
import json
import re

from PySide6.QtCore import QObject, QTimer

# Tool key -> page method (and keyword arguments) that reads the model open in SolidWorks.
ACTIVE_ACTIONS = {
    'weight': ('read_cad', {}),
    'dxf_dwg': ('scan_active', {}),
    'tolerance_stack': ('scan', {'active': True}),
    'naming': ('read_active', {}),
    'bom': ('scan', {}),
    'automatic_drawing': ('use_active', {}),
    'press_brake': ('read_sw', {}),
}
KEY = re.compile(r'^[a-z_]{1,40}$')
MAX_MESSAGE = 4096


def server_name():
    """Per-user name: a named pipe on Windows, a socket file elsewhere."""
    try:
        user = re.sub(r'[^A-Za-z0-9_.-]', '_', getpass.getuser())[:40]
    except Exception:       # no user name available: still one instance per session
        user = 'user'
    return f'GOKWORKS-commands-{user}'


def parse(argv):
    """``--open <tool> [--active]`` → {'module': tool, 'active': bool}; anything else → None."""
    args = list(argv[1:])
    if '--open' not in args:
        return None
    index = args.index('--open')
    if index+1 >= len(args) or not KEY.match(args[index+1]):
        raise SystemExit('Kullanım: GOKWORKS --open <araç> [--active]')
    return {'module': args[index+1], 'active': '--active' in args}


def send(command, timeout_ms=1500):
    """Give ``command`` to a running GOKWORKS. True only when it was delivered."""
    from PySide6.QtNetwork import QLocalSocket
    socket = QLocalSocket()
    socket.connectToServer(server_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    socket.write((json.dumps(command)+'\n').encode('utf-8'))
    delivered = socket.waitForBytesWritten(timeout_ms)
    socket.disconnectFromServer()
    return delivered


def validated(raw, modules):
    """The command if it is well formed and names a known tool, else None."""
    try:
        command = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(command, dict) or set(command) - {'module', 'active'}:
        return None
    module, active = command.get('module'), command.get('active', False)
    if not isinstance(module, str) or module not in modules or not isinstance(active, bool):
        return None
    return {'module': module, 'active': active}


def apply(window, command):
    """Show the tool; with ``active`` run its allow-listed "read active model" action."""
    window.navigate(command['module'])
    if window.isMinimized():
        window.showNormal()
    window.show(); window.raise_(); window.activateWindow()
    action = ACTIVE_ACTIONS.get(command['module']) if command['active'] else None
    if action is not None:
        page = window.pages[command['module']]
        method, kwargs = action
        # After the page is shown, through the page's own command (same checks as a click).
        QTimer.singleShot(0, lambda: getattr(page, method)(**kwargs))


def _answers(name):
    from PySide6.QtNetwork import QLocalSocket
    socket = QLocalSocket(); socket.connectToServer(name)
    alive = socket.waitForConnected(300)
    socket.abort()
    return alive


class CommandServer(QObject):
    """Receives commands from later starts (see ``send``) for ``window``."""

    def __init__(self, window, modules):
        super().__init__(window)
        from PySide6.QtNetwork import QLocalServer
        self.window, self.modules = window, frozenset(modules)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        name = server_name()
        # A live window keeps its channel: Qt would otherwise replace the socket of the first
        # window (Unix listens via rename). A second window then simply receives no commands.
        if not _answers(name):
            QLocalServer.removeServer(name)     # socket file left by a crash (no-op on Windows)
            self.server.listen(name)
        self.server.newConnection.connect(self._accept)

    @property
    def listening(self):
        return self.server.isListening()

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            buffer = bytearray()
            def read(socket=socket, buffer=buffer):
                buffer.extend(bytes(socket.readAll()))
                if len(buffer) > MAX_MESSAGE:
                    socket.abort(); return
                if b'\n' in buffer:
                    command = validated(bytes(buffer.split(b'\n', 1)[0]), self.modules)
                    socket.disconnectFromServer()
                    if command is not None:
                        apply(self.window, command)
            socket.readyRead.connect(read)
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                read()
