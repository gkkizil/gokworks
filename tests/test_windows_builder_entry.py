"""Exercise script-style imports outside the checkout, without building an EXE."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
PROBE=r'''
import json,runpy,subprocess,sys
from pathlib import Path
builder=Path(sys.argv[1]);mode=sys.argv[2]
# Direct Python script execution searches the script directory, not its parent.
# -I removes inherited PYTHONPATH and the working directory from this probe.
sys.path.insert(0,str(builder.parent))
assert str(builder.parents[1]) not in sys.path
namespace=runpy.run_path(str(builder))
main=namespace['main']
main.__globals__['collect_licenses']=lambda:None
sys.platform='win32'
sys.argv=[str(builder)]+(['--onedir'] if mode=='onedir' else [])
class CapturedBuild(Exception):pass
calls=[]
def capture(command,**kwargs):
    calls.append(command)
    raise CapturedBuild()
subprocess.run=capture
try:main()
except CapturedBuild:pass
assert len(calls)==1 and calls[0][1:3]==['-m','PyInstaller']
assert '--'+mode in calls[0]
assert 'PyInstaller' not in sys.modules and 'PySide6' not in sys.modules
info=json.loads((builder.parents[1]/'build/application-info.json').read_text(encoding='utf-8'))
assert info==dict(schema=1,revision='a'*40),info
print(json.dumps(dict(mode=mode,revision=info['revision'],build_started=False)))
'''


@pytest.mark.parametrize('mode',['onefile','onedir'])
def test_builder_script_finds_its_project_without_pythonpath_from_another_folder(tmp_path,mode):
    project=tmp_path/'Proje kökü boşluklu'
    builder=project/'packaging/build_windows.py'
    builder.parent.mkdir(parents=True);shutil.copy2(ROOT/'packaging/build_windows.py',builder)
    shared=project/'shared';shared.mkdir()
    for name in ('__init__.py','app_info.py'):shutil.copy2(ROOT/'shared'/name,shared/name)
    (project/'.git').mkdir();(project/'.git/HEAD').write_text('a'*40,encoding='utf-8')
    outside=tmp_path/'Başka klasör';outside.mkdir()
    environment=os.environ.copy();environment.pop('PYTHONPATH',None);environment.pop('PYTHONHOME',None)
    result=subprocess.run([sys.executable,'-I','-c',PROBE,str(builder),mode],cwd=outside,env=environment,
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert json.loads(result.stdout.strip())==dict(mode=mode,revision='a'*40,build_started=False)
