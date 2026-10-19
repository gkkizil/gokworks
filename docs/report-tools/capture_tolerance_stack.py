"""Real Qt/manual example evidence. This script never connects to SolidWorks."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from gui_qt.app import MainWindow,create_application
from tolerance_stack.calculator import calculate
from tolerance_stack.report import export_excel,export_pdf
from tolerance_stack.storage import save_project


def capture(destination):
    destination.mkdir(parents=True,exist_ok=True)
    screenshots=destination/'screenshots';screenshots.mkdir(exist_ok=True)
    examples=Path(__file__).resolve().parents[2]/'tolerance_stack/examples';examples.mkdir(exist_ok=True)
    app=create_application([])
    with TemporaryDirectory() as folder:
        window=MainWindow(Path(folder)/'settings.json');window.resize(1440,1000);window.show()
        window.navigate('tolerance_stack');page=window.pages['tolerance_stack'];page.load_example()
        page.form.set_value('method','Worst-Case + RSS + Monte Carlo');page.form.set_value('samples','50000')
        page.confirm_box.setChecked(True)
        result=calculate(page.project)
        assert (str(result.nominal),str(result.minimum),str(result.maximum))==('0.20','0.02','0.38')
        page.show_result(result)
        for theme in ('dark','light'):
            window.set_theme(theme)
            for tab,name in ((0,'chain'),(2,'results'),(3,'drawing-output')):
                page.tabs.setCurrentIndex(tab);app.processEvents()
                assert window.grab().save(str(screenshots/(name+'-'+theme+'.png')))
        window.set_theme('dark');page.tabs.setCurrentIndex(2)
        page.histogram.parentWidget().parentWidget().setCurrentIndex(1)
        app.processEvents();window.grab().save(str(screenshots/'monte-carlo-dark.png'))
        window.resize(1024,700);page.tabs.setCurrentIndex(0);app.processEvents()
        window.grab().save(str(screenshots/'chain-compact.png'))
        save_project(page.project,examples/'A-B-C.gokstack.json',result=result,overwrite=True)
        export_excel(page.project,result,examples/'A-B-C.xlsx',overwrite=True)
        export_pdf(page.project,result,examples/'A-B-C.pdf',overwrite=True)
        summary=dict(geometry='manual example; no CAD source',solidworks_live_tested=False,qt_platform=app.platformName(),
            expected_wc=['0.20','0.02','0.38'],actual_wc=list(map(str,(result.nominal,result.minimum,result.maximum))),
            monte_carlo=result.monte_carlo,examples=['A-B-C.gokstack.json','A-B-C.xlsx','A-B-C.pdf'])
        (destination/'example-validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        window.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    capture(parser.parse_args().destination)
