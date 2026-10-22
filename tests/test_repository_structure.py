"""Protect canonical feature locations and bundled resources after relocation."""

import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from gui_qt.app import MainWindow, MODULES, create_application
from gui_qt.icons import ASSETS
from modules.naming.native import HOST_SOURCE
from modules.pdf.process import _command

ROOT=Path(__file__).resolve().parents[1]


def test_each_navigation_module_owns_its_ui_tests_and_documentation(qtbot,tmp_path):
    create_application([])
    window=MainWindow(tmp_path/'settings.json');qtbot.addWidget(window)
    for key,_,_ in MODULES:
        folder=ROOT/'modules'/key
        assert Path(inspect.getfile(type(window.pages[key])))==folder/'ui.py'
        assert (folder/'README.md').is_file()
        assert list((folder/'tests').glob('test_*.py'))
        assert not (ROOT/key).exists(),f'Duplicate feature directory: {key}'
    window.close()


def test_pure_engines_import_in_a_fresh_process_without_gui_or_cad_dependencies():
    code='''
import sys
from modules.bolt.rules import calculate
from modules.bolt_torque.rules import calculate as torque
from modules.weight.rules import calculate as weight
from modules.iso_fits.rules import calculate as fit
from modules.tolerance_stack.calculator import calculate as stack
from modules.nesting.accounting import mass
from modules.profile_cutting.optimizer import optimize as profile_cutting
assert not any(name in sys.modules for name in ('PySide6', 'tkinter', 'customtkinter', 'pythoncom'))
'''
    subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True,timeout=20)


def test_pdf_worker_source_entry_and_module_resources_follow_new_paths(tmp_path):
    assert Path(_command(tmp_path/'request.json')[1])==ROOT/'main.py'
    assert ASSETS==ROOT/'assets' and (ASSETS/'GOK_app_windows.ico').is_file()
    assert HOST_SOURCE==ROOT/'modules/naming/interop/PackAndGoHost.cs'
    assert HOST_SOURCE.is_file()


@pytest.mark.parametrize('mode',('onefile','onedir'))
def test_windows_builder_copies_resources_to_their_actual_runtime_locations(mode):
    spec=importlib.util.spec_from_file_location('gokworks_windows_builder',ROOT/'packaging/build_windows.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    class CapturedBuild(Exception):pass
    calls=[]
    def capture(command,**kwargs):
        calls.append(command)
        raise CapturedBuild()
    argv=['build_windows.py']+(['--onedir'] if mode=='onedir' else [])
    with patch.object(builder.sys,'platform','win32'),patch.object(builder.sys,'argv',argv), \
         patch.object(builder,'collect_licenses'),patch.object(builder.subprocess,'run',side_effect=capture):
        with pytest.raises(CapturedBuild):builder.main()
    command=calls[0]
    assert '--'+mode in command
    assert Path(command[command.index('--icon')+1])==ASSETS/'GOK_app_windows.ico'
    resources=[command[i+1].split(';',1) for i,v in enumerate(command) if v=='--add-data']
    for source,destination in resources:
        assert Path(source).exists()
        if destination!='licenses':
            assert Path(source).parent.relative_to(ROOT).as_posix()==destination
    assert any(dest=='modules/iso_fits' for _,dest in resources)
    assert any(dest=='modules/naming/interop' for _,dest in resources)
    assert 'modules.k_factor.standalone' in command
