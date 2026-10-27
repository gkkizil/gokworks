"""Native Qt UX evidence: real manual optimization, explicitly synthetic CAD rows."""

from pathlib import Path
import argparse
import json
import sys
from tempfile import TemporaryDirectory
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from gui_qt.app import MainWindow, create_application
from modules.profile_cutting.dialogs import RowDialog
from modules.profile_cutting.models import ScanResult, ScanRow


def capture(destination):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    app = create_application([]); shots = []
    with TemporaryDirectory(prefix='gokworks-profile-ux-') as root:
        w = MainWindow(Path(root)/'settings.json'); w.resize(1440,900); w.show()
        w.navigate('profile_cutting'); p = w.pages['profile_cutting']
        def shot(name, widget=None):
            QTest.qWait(120)
            target = widget or w
            assert target.grab().save(str(destination/(name+'.png')))
            shots.append(dict(file=name+'.png', size=target.size().toTuple()))
        shot('01-empty-dark')
        dialog = RowDialog(p); dialog.show(); shot('02-add-part-dark',dialog); dialog.reject()
        p.load_example(); shot('03-parts-dark')
        p.calculate(); deadline = time.monotonic()+10
        while w.jobs.busy:
            QApplication.processEvents(); QTest.qWait(10)
            assert time.monotonic() < deadline
        assert p.plan and len(p.plan.bars)==2
        shot('04-plan-dark')
        example = 'ÖRNEK — gerçek CAD verisi değildir.SLDPRT'
        p.handle_events([('weldment_scan',ScanResult(example,'Örnek',[
            ScanRow('demo-ready',example,'Örnek','Kesim grubu 1','40×40×2','S235JR','1200',4,
                    thickness='2',geometry_verified=True),
            ScanRow('demo-review',example,'Örnek','Kesim grubu 2','40×40×2','S235JR','800',6,
                    thickness='2',issues=['Uç geometrisini ve gerekli ilave boyu kontrol edin.'])],
            scanned_parts=1,weldments=1))])
        p.set_status('Örnek tarama satırları · gerçek SolidWorks bağlantısı çalıştırılmadı.')
        shot('05-source-dark')
        w.set_theme('light'); p.tabs.setCurrentIndex(0); shot('06-parts-light')
        p.tabs.setCurrentIndex(2); shot('07-plan-light')
        w.resize(1024,700); p.tabs.setCurrentIndex(0); shot('08-parts-small-light')
        p.tabs.setCurrentIndex(2); shot('09-plan-small-light')
        w.set_theme('dark'); w.resize(820,560)
        p.tabs.setCurrentIndex(0); shot('10-parts-minimum-dark')
        p.tabs.setCurrentIndex(2); shot('11-plan-minimum-dark')
        w.close(); app.processEvents()
    (destination/'capture.json').write_text(json.dumps(dict(framework='PySide6 / Qt Widgets',
        platform=app.platformName(), screenshots=shots, source_data='Explicit manual example',
        optimizer='Actual existing Decimal optimizer, 2 bars / 10 parts / 2370 mm remaining / 30 mm kerf',
        cad_boundary='Source tab rows are labelled synthetic; no live SolidWorks scan.',
        live_solidworks_tested=False, windows_exe_built=False), ensure_ascii=False, indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('destination')
    capture(parser.parse_args().destination)
