"""Real Qt selection/threads/cameras; SolidWorks capture is explicitly mocked."""

import gc
from pathlib import Path
import threading

import pytest
from PySide6.QtCore import Qt, QCoreApplication, QEvent, QThread, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from gui_qt.app import MainWindow, create_application
from modules.dxf_dwg.preview.models import Payload, Flat, Stroke
from modules.dxf_dwg.preview.viewer import VIEWS
from .test_preview_geometry import ring_mesh


def payload(path, configuration='Bent'):
    flat = Flat((Stroke(((0, 0), (10, 0), (10, 10), (0, 0)), '#338855', 'CUT'),),
                (0, 0, 10, 10), 'Synthetic DXF test fixture', 34.14)
    return Payload(str(path), configuration, ring_mesh(), flat,
                   (('Dosya', Path(path).name), ('Malzeme', 'S235JR'), ('Sac kalınlığı', '2 mm')),
                   (str(path), configuration, 1))


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(window)
    window.resize(1600, 1000); window.show(); window.navigate('dxf_dwg')
    p = window.pages['dxf_dwg']
    p.preview.mesh_view.fallback()  # deterministic software path on every test OS
    files = [tmp_path/'A.SLDPRT', tmp_path/'B.SLDPRT']
    for file in files: file.write_text('source fixture')
    p.results.files([str(f) for f in files])
    p._capture = lambda request, cache, stop: payload(request.source)
    yield p, window, files
    p.preview_timer.stop(); p.preview_pending = None
    if window.jobs.busy:
        window.jobs.cancel(); qtbot.waitUntil(lambda: not window.jobs.busy, timeout=8000)
    p.preview.mesh_view.cancel_render()
    window.close(); window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); gc.collect()


def select(p, qtbot, row=0):
    p.results.table.selectRow(row)
    qtbot.waitUntil(lambda: p.preview_payload is not None and not p.jobs.busy, timeout=6000)


def test_source_selection_displays_all_three_panes_and_software_depth_frame(page, qtbot):
    p, w, files = page
    p.source_files.view.setCurrentIndex(p.source_files.proxy.index(0, 0))
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    p.show_preview()
    view = p.preview.mesh_view
    qtbot.waitUntil(lambda: not view.software.image.isNull(), timeout=6000)
    assert p.preview_payload.source == str(files[0])
    assert p.preview.flat_view.scene().items() and p.preview.info.rowCount() == 3
    assert 'A.SLDPRT' in p.preview.source_label.text() and view.mesh.triangles == 8
    assert not p.preview.flat_view.sceneRect().isEmpty()


def test_selection_change_immediately_clears_previous_mesh_flat_and_information(page, qtbot):
    p, w, files = page
    select(p, qtbot)
    p.results.table.selectRow(1)
    assert p.preview_payload is None and p.preview.mesh_view.mesh is None
    assert not p.preview.flat_view.scene().items() and p.preview.info.rowCount() == 0
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.source == str(files[1])


def test_late_previous_selection_is_discarded_and_capture_runs_off_gui_thread(page, qtbot):
    p, w, files = page
    started, release = threading.Event(), threading.Event(); observed = []
    gui_thread_id = threading.get_ident()
    def delayed(request, cache, stop):
        observed.append((request.source, threading.get_ident()))
        if request.source == str(files[0]): started.set(); release.wait(4)
        return payload(request.source)
    p._capture = delayed; p.results.table.selectRow(0)
    qtbot.waitUntil(started.is_set, timeout=4000)
    p.results.table.selectRow(1)
    generation = p.preview_generation
    p.handle_events([('dxf_preview', (generation-1, payload(files[0])))])
    assert p.preview_payload is None and p.preview.mesh_view.mesh is None
    w.navigate('weight'); assert w.pages['weight'].isVisible()
    release.set()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview_payload.source == str(files[1])
    assert all(thread_id != gui_thread_id for _, thread_id in observed)


def test_preview_defers_to_existing_export_job_instead_of_starting_parallel_com(page, qtbot):
    p, w, files = page; calls = []; release = threading.Event()
    p._capture = lambda request, cache, stop: calls.append(request.source) or payload(request.source)
    w.jobs.start(w.pages['pdf'], lambda sink, stop: release.wait(3))
    p.results.table.selectRow(0); qtbot.wait(250)
    assert not calls and p.preview_pending is not None
    release.set(); qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert calls == [str(files[0])]


def test_connection_error_clears_stale_preview_and_refresh_can_recover(page, qtbot):
    p, w, _ = page
    select(p, qtbot)
    def unavailable(*args): raise RuntimeError('SolidWorks bağlantısı koptu')
    p._capture = unavailable; p.refresh_preview()
    qtbot.waitUntil(lambda: 'bağlantısı koptu' in p.status_text and not w.jobs.busy, timeout=6000)
    assert p.preview.mesh_view.mesh is None and p.preview_payload is None
    p._capture = lambda request, cache, stop: payload(request.source)
    p.preview.refresh_button.click()
    qtbot.waitUntil(lambda: p.preview_payload is not None and not w.jobs.busy, timeout=6000)
    assert p.preview.mesh_view.mesh is not None


def test_output_result_provenance_updates_the_selected_request(page, qtbot, tmp_path):
    p, w, files = page
    select(p, qtbot)
    output = tmp_path/'A.dxf'; output.write_text('test output')
    p.handle_events([('result', dict(source=str(files[0]), configuration='Cfg-A', status='success',
        detail='exported', quantity=4, thickness_mm=2., update_stamp=7, source_stamp=(14, 20),
        body_ref='persist:abc', outputs=[dict(format='DXF',path=str(output),status='success')]))])
    request = p.preview_request
    assert request.configuration == 'Cfg-A' and request.quantity == 4 and request.update_stamp == 7
    assert request.output == str(output) and request.body_ref == 'persist:abc'
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)


def test_all_camera_controls_fit_rotate_pan_zoom_projection_and_edges(page, qtbot):
    p, _, _ = page; select(p, qtbot); p.show_preview(); view = p.preview.mesh_view
    for name, expected in VIEWS.items():
        p.preview.views.setCurrentText(name)
        assert (view.camera.yaw, view.camera.pitch) == expected
    p.preview.perspective.setChecked(True); assert view.camera.perspective
    p.preview.edges.setChecked(False); assert not view.camera.edges
    qtbot.mousePress(view, Qt.LeftButton, pos=QPoint(10, 10))
    from PySide6.QtGui import QMouseEvent
    event = QMouseEvent(QEvent.MouseMove, QPointF(60, 40), QPointF(60, 40), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(view, event); qtbot.mouseRelease(view, Qt.LeftButton, pos=QPoint(60, 40))
    assert (view.camera.yaw, view.camera.pitch) != VIEWS['Alt']
    qtbot.mousePress(view, Qt.RightButton, pos=QPoint(10, 10))
    event = QMouseEvent(QEvent.MouseMove, QPointF(30, 30), QPointF(30, 30), Qt.NoButton, Qt.RightButton, Qt.NoModifier)
    QApplication.sendEvent(view, event); qtbot.mouseRelease(view, Qt.RightButton, pos=QPoint(30, 30))
    assert view.camera.pan_x and view.camera.pan_y
    event = QWheelEvent(QPointF(30, 30), QPointF(30, 30), QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(view, event); assert view.camera.zoom > 1
    p.preview.fit_button.click(); assert view.camera.zoom > 0 and view.camera.pan_x == view.camera.pan_y == 0


def test_small_and_wide_windows_keep_export_results_and_preview_accessible(page, qtbot):
    p, w, _ = page
    for width, height in ((1920, 1080), (820, 560), (1440, 900)):
        w.resize(width, height); qtbot.wait(50)
        assert p.splitter.count() == 2 and p.splitter.widget(1) is p.results
        assert p.results.tabs.tabText(1) == 'Günlük'
        p.show_preview(); assert p.preview.isVisible() and p.preview.height() > 100
        assert p.preview.mesh_view.height() >= 80
        if p.preview_compact:
            assert p.results.tabs.indexOf(p.preview) == 2
        else:
            assert p.preview_splitter.widget(1) is p.preview
            assert p.results.table.isVisible() and p.results.table.width() >= 200
        assert p.start_button.isVisible()


def test_clear_empties_preview_as_well_as_existing_results(page, qtbot):
    p, w, _ = page; select(p, qtbot)
    p.results.clear_button.click()
    assert p.preview_payload is None and p.preview.mesh_view.mesh is None
    assert not p.preview.flat_view.scene().items() and not p.results.model.rowCount()
    assert p.preview_request is None and p.preview_pending is None


def test_export_results_and_log_remain_unchanged_by_preview_failures(page):
    p, _, files = page
    p.handle_events([('result', dict(source=str(files[0]),status='success', detail='Original export success', output='out.dxf'))])
    previous = p.results.log.toPlainText()
    p.handle_events([('dxf_preview_error', (p.preview_generation, 'preview-only error'))])
    assert len(p.results.results) == 1 and p.results.results[0]['status'] == 'success'
    assert p.results.log.toPlainText() == previous


def test_preview_callbacks_are_delivered_on_the_gui_thread(page, qtbot):
    p, _, _ = page; threads = []
    original = p.preview.show_payload
    def display(value):
        threads.append(QThread.currentThread() is QApplication.instance().thread()); original(value)
    p.preview.show_payload = display
    select(p, qtbot)
    assert threads == [True]


@pytest.mark.parametrize('fatal', [False, True])
def test_export_preempts_capture_after_safe_cleanup_and_stops_on_restore_error(page, qtbot, monkeypatch, fatal):
    from modules.cad_converter.models import Cancelled
    from modules.cad_converter.api import RestoreError
    p, w, files = page; started = threading.Event(); calls = []
    def capture(request, cache, stop):
        started.set()
        assert stop.wait(5)
        calls.append('capture-cleaned')
        if fatal: raise RestoreError('test restore failure')
        raise Cancelled()
    def export(*args, **kwargs):
        calls.append('export')
        args[4].put(('done', dict(state='completed',succeeded=1)))
    p._capture = capture
    p.source.setText(str(files[0].parent)); p.output.setText(str(files[0].parent/'out'))
    p.results.files([str(f) for f in files])
    monkeypatch.setattr('gui_qt.export.export_parts', export)
    p.results.table.selectRow(0); qtbot.waitUntil(started.is_set, timeout=4000)
    assert p.start_button.isEnabled()
    p.start_button.click()
    qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    qtbot.wait(150)
    if fatal:
        assert calls == ['capture-cleaned'] and 'geri alınamadı' in p.status_text
    else:
        assert calls == ['capture-cleaned', 'export']


def test_stop_cancels_preview_without_restart_and_reports_cancelled_state(page, qtbot):
    from modules.cad_converter.models import Cancelled
    p, w, _ = page; started = threading.Event()
    def capture(request, cache, stop):
        started.set(); stop.wait(4); raise Cancelled()
    p._capture = capture; p.results.table.selectRow(0)
    qtbot.waitUntil(started.is_set, timeout=4000)
    p.stop_button.click(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=6000)
    assert not p._export_after_preview and p.preview_pending is None
    assert 'durduruldu' in p.preview.message.text()
