"""Run an independent Qt gear workbench or a headless CAD export."""

import argparse
import json
from .models import GearSpecification,GearPairSpecification,LoadSpecification


def main():
    parser=argparse.ArgumentParser(description='GOKWORKS · Bağımsız düz evolvent dişli çifti')
    parser.add_argument('--output',help='Başsız .dxf/.step; verilmezse Qt ekranı açılır')
    parser.add_argument('--target',choices=('pinion','wheel','pair'),default='pair')
    for flag,default in (('module',2.),('angle',20.),('width',15.),('bore1',8.),('bore2',12.),('rpm',1500.)):
        parser.add_argument('--'+flag,type=float,default=default)
    parser.add_argument('--z1',type=int,default=20);parser.add_argument('--z2',type=int,default=40)
    load=parser.add_mutually_exclusive_group();load.add_argument('--power',type=float);load.add_argument('--torque',type=float)
    args=parser.parse_args()
    if args.output:
        from pathlib import Path
        from .service import execute
        common=dict(module_mm=args.module,pressure_angle_deg=args.angle,face_width_mm=args.width)
        spec=GearPairSpecification(GearSpecification(teeth=args.z1,bore_mm=args.bore1,**common),
            GearSpecification(teeth=args.z2,bore_mm=args.bore2,**common),
            LoadSpecification(mode='torque' if args.torque is not None else 'power',input_rpm=args.rpm,
                power_kw=None if args.torque is not None else args.power if args.power is not None else 1.5,torque_nm=args.torque))
        mode='dxf' if Path(args.output).suffix.lower()=='.dxf' else 'step'
        print(json.dumps(execute(spec,mode,target=args.target,path=args.output),ensure_ascii=False))
        return 0
    from solidworks.runtime import configure_libraries
    configure_libraries()
    from PySide6.QtWidgets import QApplication,QMainWindow
    from gui_qt.theme import apply_theme,COLORS
    from gui_qt.settings import SettingsStore
    from gui_qt.workers import JobManager
    from .ui import GearPage

    class GearWindow(QMainWindow):
        def __init__(self):
            super().__init__();self.settings=SettingsStore(parent=self)
            self.appearance=self.settings.get('appearance','dark')
            if self.appearance not in COLORS:self.appearance='dark'
            self.jobs=JobManager(self);self.closing=False
            self.page=GearPage(self);self.setCentralWidget(self.page)
            self.page.statusChanged.connect(lambda text,error:self.statusBar().showMessage(text))
            self.jobs.finished.connect(self.finish_close)
            self.resize(1450,900);self.setMinimumSize(600,500);self.setWindowTitle('GOKWORKS · Dişli Hesaplama')
        def finish_close(self):
            if self.closing:self.close()
        def closeEvent(self,event):
            if self.jobs.busy:
                self.closing=True;self.jobs.cancel();event.ignore();return
            self.page.canvas.pause()
            if self.page.mesh_view:self.page.mesh_view.cancel_render()
            super().closeEvent(event)

    app=QApplication([]);window=GearWindow();apply_theme(app,window.appearance);window.show()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
