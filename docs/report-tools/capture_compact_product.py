"""Real native UI evidence. CAD records are explicitly illustrative; engines run locally."""

import argparse,json,sys,time
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from gui_qt.app import create_application,MainWindow,MODULES
from modules.bom.exporter import Part,Node,Result
from modules.naming.exporter import Document,Snapshot
from modules.nesting.storage import load_project
from modules.tolerance_stack.calculator import calculate


def main(destination):
    destination.mkdir(parents=True,exist_ok=True);app=create_application([])
    with TemporaryDirectory(prefix='GOKWORKS-UI-') as folder:
        folder=Path(folder);window=MainWindow(folder/'settings.json');window.resize(1440,900);window.show()
        def wait():
            limit=time.monotonic()+15
            while window.jobs.busy:
                app.processEvents();time.sleep(.005)
                if time.monotonic()>limit:raise TimeoutError('UI evidence job timed out')
            QTest.qWait(80)
        def shot(name,widget=None):
            QTest.qWait(80)
            assert (widget or window).grab().save(str(destination/(name+'.png')))
        for mode in ('pdf','dxf_dwg'):
            page=window.pages[mode];page.source.setText('C:/GOKWORKS/Ornek montaj');page.output.setText('C:/GOKWORKS/Ciktilar')
            page.results.files(['Panel.SLDDRW' if mode=='pdf' else 'Panel.SLDPRT',
                                'Kapak.SLDDRW' if mode=='pdf' else 'Kapak.SLDPRT'])
            page.set_status('Örnek dosya listesi · Aktarım çalıştırılmadı.')
        bom=window.pages['bom']
        bom.load_result(Result('Ornek montaj.SLDASM','Varsayılan',
            (Part('Panel','Panel.SLDPRT','Varsayılan',2,1.5,3),Part('Kapak','Kapak.SLDPRT','Varsayılan',4,.25,1)),
            (Node('1','',0,'Örnek montaj','Ana','Montaj','Ornek montaj.SLDASM','Varsayılan'),
             Node('1.1','1',1,'Panel','Panel-1','Parça','Panel.SLDPRT','Varsayılan',1.5)),0,0,False))
        source=folder/'source';source.mkdir();files=[source/name for name in ('Montaj.SLDASM','Panel.SLDPRT','Panel.SLDDRW')]
        for file in files:file.write_text('Illustrative CAD boundary; not a SolidWorks document.')
        naming=window.pages['naming'];naming.source_folder.setText(str(source));naming.destination.setText(str(folder/'Yeni paket'))
        naming.form.set_value('prefix','DRM-');naming.handle_events([('assemblies',[str(files[0])])])
        naming.load_snapshot(Snapshot(str(files[0]),tuple(Document(str(f),(() if i else (str(files[1]),)),(0,0)) for i,f in enumerate(files))))
        wait();assert naming.valid_plan
        kr=window.pages['k_factor']
        for i,value in enumerate(('2','0,274','1,5')):kr.rows_model.setData(kr.rows_model.index(0,i),value)
        kr.add_assignment()
        for i,value in enumerate(('3','0,33','3')):kr.rows_model.setData(kr.rows_model.index(1,i),value)
        stack=window.pages['tolerance_stack'];stack.load_example();stack.confirm_box.setChecked(True)
        result=calculate(stack.project);assert tuple(map(str,(result.nominal,result.minimum,result.maximum)))==('0.20','0.02','0.38')
        stack.show_result(result);stack.tabs.setCurrentIndex(0)
        nesting=window.pages['nesting'];nesting.project,result=load_project(ROOT/'docs/nesting-example/Ornek.goknest.json')
        nesting.sync_forms();nesting.refresh();nesting.show_result(result)
        for theme in ('dark','light'):
            window.set_theme(theme);window.resize(1440,900)
            canvas=Image.new('RGB',(1440,1300),'#101620' if theme=='dark' else '#eff4fa');draw=ImageDraw.Draw(canvas)
            font=ImageFont.truetype('DejaVuSans.ttf',14)
            for index,(mode,title,_) in enumerate(MODULES):
                window.navigate(mode);shot(f'{mode}-{theme}')
                image=Image.open(destination/f'{mode}-{theme}.png').convert('RGB').resize((480,300))
                x=index%3*480;y=index//3*325;canvas.paste(image,(x,y+25));draw.text((x+8,y+4),title,font=font,fill='white' if theme=='dark' else 'black')
            canvas.save(destination/f'overview-{theme}.png')
        window.set_theme('dark');window.resize(820,560)
        for mode,_,_ in MODULES:window.navigate(mode);shot(f'{mode}-minimum')
        window.navigate('tolerance_stack');stack.library_button.click();shot('stack-measurement-picker',stack.library_dialog);stack.library_dialog.reject()
        window.set_sidebar_collapsed(True);window.navigate('nesting');shot('collapsed-navigation')
        def preferences():
            dialog=QApplication.activeModalWidget();shot('application-settings',dialog);dialog.reject()
        QTimer.singleShot(60,preferences);window.show_settings()
        window.close()
    (destination/'capture.json').write_text(json.dumps(dict(
        platform=app.platformName(),framework='PySide6',modules=12,themes=['dark','light'],sizes=[[1440,900],[820,560]],
        example_math=['0.20','0.02','0.38'],nesting='Existing real DXF example loaded with validated placements',
        cad_boundary='BOM/PDF/DXF/naming CAD records illustrative; no live SolidWorks',
        windows_exe_built=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    main(parser.parse_args().destination)
