"""Reproducible UI evidence using labelled synthetic meshes, not live CAD."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, Point
from PySide6.QtCore import QEventLoop, QTimer

from gui_qt.app import MainWindow, create_application
from modules.dxf_dwg.preview.geometry import make_mesh
from modules.dxf_dwg.preview.models import Payload, Flat, Stroke


def sample_mesh():
    coordinates = []
    def extrude(polygon, depth, transform):
        def add(points): coordinates.extend(transform(x, y, z) for x, y, z in points)
        for triangle in constrained_delaunay_triangles(polygon).geoms:
            p = list(triangle.exterior.coords)[:3]
            add([(x, y, 0) for x, y in reversed(p)])
            add([(x, y, depth) for x, y in p])
        for ring in (polygon.exterior, *polygon.interiors):
            p = list(ring.coords)
            for (x, y), (a, b) in zip(p, p[1:]):
                add([(x, y, 0), (a, b, 0), (a, b, depth)])
                add([(x, y, 0), (a, b, depth), (x, y, depth)])
    plate = Polygon([(-.06, -.04), (.06, -.04), (.06, .04), (-.06, .04)]).difference(Point(0, 0).buffer(.018, quad_segs=24))
    extrude(plate, .002, lambda x, y, z: (x, y, z))
    flange = Polygon([(-.06, 0), (.06, 0), (.06, .035), (-.06, .035)])
    for side in (-1, 1):
        extrude(flange, .002, lambda x, y, z, side=side: (x, side*(.04-z), y))
    return make_mesh(np.asarray(coordinates).ravel())


def sample_payload(source):
    ring = tuple((18*np.cos(a), 18*np.sin(a)) for a in np.linspace(0, 2*np.pi, 100))
    flat = Flat((Stroke(((-60, -75), (60, -75), (60, 75), (-60, 75), (-60, -75)), '#334155', 'CUT'),
                 Stroke(ring, '#334155', 'CUT'),
                 Stroke(((-60, -40), (60, -40)), '#b65b46', 'BEND-UP', True),
                 Stroke(((-60, 40), (60, 40)), '#b65b46', 'BEND-UP', True)),
                (-60, -75, 60, 75), 'ÖRNEK açınım · canlı SolidWorks verisi değil', None)
    return Payload(str(source), 'Örnek bükülmüş', sample_mesh(), flat,
                   (('Veri kaynağı', 'SENTETİK TEST VERİSİ'), ('Parça kodu', 'DEMO-001'),
                    ('Açıklama', 'Örnek braket'), ('Malzeme', 'Örnek S235JR'),
                    ('Sac kalınlığı', 'Örnek 2 mm'), ('Adet', 'Örnek 5'), ('Büküm sayısı', 'Örnek 2')),
                   ('synthetic',), ('Bu görsel gerçek CAD kabul testi değildir.',))


def capture(folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    app = create_application([])
    with TemporaryDirectory() as temporary:
        root = Path(temporary); source = root/'Ornek_braket.SLDPRT'; source.write_text('synthetic fixture')
        window = MainWindow(root/'settings.json'); window.resize(1920, 1080); window.show(); window.navigate('dxf_dwg')
        page = window.pages['dxf_dwg']; page._capture = lambda request, cache, stop: sample_payload(request.source)
        page.results.files([str(source)]); page.results.table.selectRow(0)
        loop = QEventLoop(); QTimer.singleShot(2000, loop.quit); loop.exec()
        for theme in ('dark', 'light'):
            window.set_theme(theme)
            for width, height, suffix in ((1920, 1080, 'wide'), (820, 560, 'small')):
                window.resize(width, height)
                loop = QEventLoop(); QTimer.singleShot(150, loop.quit); loop.exec()
                page.show_preview()
                loop = QEventLoop(); QTimer.singleShot(500, loop.quit); loop.exec()
                window.grab().save(str(folder/f'{theme}-{suffix}.png'))
        page.preview.mesh_view.cancel_render(); window.close(); app.processEvents()


if __name__ == '__main__':
    capture(sys.argv[1])
