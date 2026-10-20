"""Capture the integrated local torque tool with actual calculated results."""

import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from gui_qt.app import create_application,MainWindow


def main():
    app=create_application([])
    output=ROOT/'bolt_torque/examples';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gokworks-torque-capture-') as folder:
        w=MainWindow(Path(folder)/'settings.json');w.show();w.navigate('bolt_torque')
        page=w.pages['bolt_torque'];records=[]
        for name,theme,size,values in (
            ('torque-dark','dark',(1440,900),{}),
            ('torque-small','dark',(1024,700),{}),
            ('torque-light','light',(1440,900),dict(metric='M18',thread_series='İnce diş',
                condition='Hafif yağlı',k='0,18',preload_percent='65',grade='10.9')),
        ):
            w.set_theme(theme);w.resize(*size)
            for key,value in values.items():page.form.set_value(key,value)
            if values:
                box=page.form.fields['pitch'];box.setCurrentIndex(box.findData(1.5))
            page.update_result();app.processEvents()
            assert page.result is not None
            assert w.grab().save(str(output/(name+'.png')))
            records.append(dict(name=name,theme=theme,size=size,result=vars(page.result)))
        (output/'captures.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        assert w.settings.flush();w.close()


if __name__=='__main__':main()
