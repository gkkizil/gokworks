"""Capture Qt fatal messages before Qt aborts a windowless Windows EXE."""

import atexit
import re
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QtMsgType, qInstallMessageHandler, qVersion

from solidworks import diagnostics


_handler = None
_previous = None
_RUNTIME_PREFIXES = ('QThread:', 'QObject::', 'QBasicTimer::', 'QTimer::',
                     'QSocketNotifier:', 'QCoreApplication::', 'QApplication:',
                     'QWidget::', 'QPainter::', 'ASSERT:')


def install():
    global _handler, _previous
    if _handler is not None:
        return

    def handler(kind, context, message):
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            # Keep runtime diagnoses, not arbitrary widget text/image paths that
            # may include customer data. Further redact paths in runtime messages.
            text = message.splitlines()[0][:1000] if message.startswith(_RUNTIME_PREFIXES) else '(runtime category only)'
            text = re.sub(r'"[^"]*"|\'[^\']*\'', '<object>', text)
            text = re.sub(r'[A-Za-z]:[\\/][^\s\"\']*', '<path>', text)
            text = re.sub(r'(?<!\w)/[^\s\"\']+', '<path>', text)
            diagnostics.record(f'qt_message level={kind.name} category={context.category or "default"} message={text}')
            if kind in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                diagnostics.snapshot('qt_native_failure_stack')
        if _previous is not None:
            _previous(kind, context, message)
        elif sys.stderr is not None:
            try:
                sys.stderr.write(message+'\n')
                sys.stderr.flush()
            except (OSError, ValueError):
                pass

    _handler = handler
    _previous = qInstallMessageHandler(handler)
    diagnostics.record(f'qt_runtime pyside={pyside_version} qt={qVersion()}')
    # Restore Qt's original handler while Python is still alive, before the
    # earlier diagnostics.close / PySide teardown callbacks run.
    atexit.register(uninstall)


def uninstall():
    global _handler, _previous
    if _handler is not None:
        qInstallMessageHandler(_previous)
        _handler = _previous = None
