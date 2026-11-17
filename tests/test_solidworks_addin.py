"""The C# SolidWorks add-in and GOKWORKS agree on tools, active actions, callbacks and icons."""
import re
from pathlib import Path

from gui_qt.app import MODULES
from gui_qt.remote import ACTIVE_ACTIONS

ADDIN = Path(__file__).resolve().parents[1]/'solidworks_addin'
TOOL = re.compile(r'new Tool\("([^"]*)", "([^"]*)", "([^"]*)", (true|false), (Needs\.\w+(?: \| Needs\.\w+)?), "([a-z_]+)"\)')


def tools():
    return TOOL.findall((ADDIN/'Tools.cs').read_text(encoding='utf-8'))


def test_every_addin_command_opens_a_real_tool_and_active_flags_match_the_allow_list():
    rows = tools()
    keys = {key for key, _, _ in MODULES}
    assert rows and rows[0][0] == ''                       # first command: main window
    for key, title, hint, active, needs, icon in rows[1:]:
        assert key in keys, key
        assert (active == 'true') == (key in ACTIVE_ACTIONS), key
        assert (needs != 'Needs.Nothing') == (active == 'true'), key   # a model is needed exactly when it is read
    assert set(ACTIVE_ACTIONS) <= {row[0] for row in rows}             # every allow-listed tool has a command


def test_each_command_has_its_callbacks_and_icon_column():
    count = len(tools())
    source = (ADDIN/'GokworksAddin.cs').read_text(encoding='utf-8')
    for i in range(count):
        assert f'public void Run{i}() => Run({i});' in source
        assert f'public int Enable{i}() => Enable({i});' in source
    assert f'public void Run{count}()' not in source
    from PySide6.QtGui import QImage
    for size in (20, 32, 40, 64, 96, 128):
        strip = QImage(str(ADDIN/'icons'/f'tools_{size}.png'))
        assert (strip.width(), strip.height()) == (size*count, size)
        main = QImage(str(ADDIN/'icons'/f'main_{size}.png'))
        assert (main.width(), main.height()) == (size, size)
