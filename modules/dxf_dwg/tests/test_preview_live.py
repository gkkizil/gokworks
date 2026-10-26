"""Explicit real-SolidWorks acceptance; skipped without a disposable test model."""

import hashlib
import os
from pathlib import Path
import sys

import pytest


@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_DXF_PREVIEW_LIVE_SOURCE'),
                   reason='Windows, licensed open SolidWorks and explicit DXF preview test-copy source required.')
def test_live_preview_reads_folded_mesh_flat_and_preserves_native_source():
    from modules.dxf_dwg.preview.solidworks import Session, capture, call
    from modules.dxf_dwg.preview.models import Request, MeshCache
    source = Path(os.environ['GOKWORKS_DXF_PREVIEW_LIVE_SOURCE']).resolve()
    assert source.is_file() and source.suffix.casefold() == '.sldprt'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    def active():
        with Session() as session:
            model = session.document()
            try: return call(model, 'GetPathName'), session.active_configuration(model)
            finally: model = None
    previous = active()
    request = Request(str(source), os.environ.get('GOKWORKS_DXF_PREVIEW_LIVE_CONFIG', ''))
    result = capture(request, MeshCache())
    assert result.source == str(source) and result.mesh.triangles > 0 and result.flat and result.flat.strokes
    assert active() == previous
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows renderer requires a real desktop; not a SolidWorks test.')
def test_native_windows_renderer_shows_real_mesh_and_open_hole(qtbot):
    from gui_qt.app import create_application
    from PySide6.QtWidgets import QApplication
    from modules.dxf_dwg.preview.viewer import MeshView
    from .test_preview_geometry import ring_mesh
    create_application([])
    if QApplication.platformName() != 'windows':
        pytest.skip('Native Qt Windows platform not selected.')
    widget = MeshView(); qtbot.addWidget(widget); widget.resize(600, 400)
    frames = []; widget.frameReady.connect(lambda: frames.append(True))
    widget.set_mesh(ring_mesh()); widget.view('Ön'); widget.show()
    qtbot.waitUntil(lambda: bool(frames), timeout=10000)
    image = widget.grab().toImage()
    assert image.pixelColor(image.width()//2, image.height()//2).red() > 230
    assert image.pixelColor(int(image.width()/2-image.height()*.3), image.height()//2).red() < 220
    backend = 'OpenGL' if widget.hardware and widget.stack.currentWidget() is widget.hardware else 'CPU fallback'
    print('Native DXF mesh renderer:', backend)
    widget.cancel_render(); widget.close()
