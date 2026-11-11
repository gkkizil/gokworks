"""Malformed manufacturing inputs must fail whole, bounded and unchanged."""
from threading import Event

import ezdxf
import pytest

from modules.nesting import dxf_import, dwg_import
from modules.nesting.drawing_import import read_drawing
from modules.nesting.dxf_import import flatten_entity, read_dxf


def drawing(path):
    doc = ezdxf.new(); doc.units = 4
    space = doc.modelspace()
    space.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    space.add_text('2 adet', dxfattribs={'height': 2, 'insert': (10, 40)})
    space.add_lwpolyline([(10, 10), (30, 10), (30, 20), (10, 20)], close=True)
    return doc, space


@pytest.mark.parametrize('reader', [read_dxf, read_drawing])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('kind', ['LINE', 'LWPOLYLINE', 'POLYLINE', 'ELLIPSE', 'SPLINE'])
def test_nonfinite_cut_coordinates_fail_before_geos(tmp_path, reader, value, kind):
    path = tmp_path/'invalid.dxf'; doc, space = drawing(path)
    if kind == 'LINE': space.add_line((0, 0, value), (10, 0, value))
    elif kind == 'LWPOLYLINE': space[0].dxf.elevation = value
    elif kind == 'POLYLINE': space.add_polyline2d([(0, 0), (10, 0), (10, 10)], dxfattribs={'elevation': (0, 0, value)})
    elif kind == 'ELLIPSE': space.add_ellipse((value, 0), major_axis=(10, 0), ratio=.5)
    else: space.add_spline([(0, 0), (value, 10), (20, 0)])
    doc.saveas(path); before = path.read_bytes()
    with pytest.raises(ValueError, match='sonlu olmayan'):
        reader(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize('reader', [read_dxf, read_drawing])
def test_huge_circle_fails_before_numpy_allocation(tmp_path, monkeypatch, reader):
    path = tmp_path/'huge.dxf'; doc, space = drawing(path)
    space.add_circle((0, 0), 1e12); doc.saveas(path)
    from ezdxf.entities import Circle
    monkeypatch.setattr(Circle, 'flattening', lambda *a: pytest.fail('unbounded circle allocation'))
    with pytest.raises(ValueError, match='20000'):
        reader(path)


@pytest.mark.parametrize('kind', ['ELLIPSE', 'SPLINE', 'LWPOLYLINE'])
def test_adaptive_curves_and_polylines_obey_the_vertex_budget(monkeypatch, kind):
    doc = ezdxf.new(); space = doc.modelspace()
    if kind == 'ELLIPSE': entity = space.add_ellipse((0, 0), major_axis=(100, 0), ratio=.5)
    elif kind == 'SPLINE': entity = space.add_spline([(0, 0), (50, 100), (100, 0)])
    else: entity = space.add_lwpolyline([(i, i % 2) for i in range(100)])
    monkeypatch.setattr(dxf_import, 'POINT_LIMIT', 20)
    with pytest.raises(ValueError, match='20000'):
        flatten_entity(entity, .0001)


@pytest.mark.parametrize('reader', [read_dxf, read_drawing])
def test_excessive_insert_arrays_are_rejected_before_expansion(tmp_path, reader):
    path = tmp_path/'array.dxf'; doc, space = drawing(path)
    block = doc.blocks.new('CELL'); block.add_circle((0, 0), 2)
    insert = space.add_blockref('CELL', (0, 0))
    insert.grid((1001, 1), (10, 10)); doc.saveas(path)
    with pytest.raises(ValueError, match='BLOCK tekrar'):
        reader(path)


@pytest.mark.parametrize('reader', [read_dxf, read_drawing])
def test_pre_cancel_does_not_even_open_the_source(tmp_path, reader):
    stop = Event(); stop.set()
    with pytest.raises(InterruptedError):
        reader(tmp_path/'not-opened.dxf', stop=stop)


def test_cancellation_during_curve_evaluation_is_not_wrapped_as_bad_geometry(monkeypatch):
    doc = ezdxf.new(); entity = doc.modelspace().add_ellipse((0, 0), major_axis=(100, 0), ratio=.5)
    stop = Event()
    from ezdxf.entities import Ellipse
    real = Ellipse.flattening
    def interrupt(self, *args, **kwargs):
        for index, vertex in enumerate(real(self, *args, **kwargs)):
            if index == 12: stop.set()
            yield vertex
    monkeypatch.setattr(Ellipse, 'flattening', interrupt)
    with pytest.raises(InterruptedError):
        flatten_entity(entity, .0001, stop=stop)


@pytest.mark.parametrize('where', ['ENTITIES', 'BLOCKS'])
def test_dwg_recovery_cannot_discard_a_hole_with_handle_zero(tmp_path, where):
    path = tmp_path/'converted.dxf'; doc = ezdxf.new(); doc.units = 4
    space = doc.modelspace() if where == 'ENTITIES' else doc.blocks.new('PART')
    space.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    hole = space.add_circle((40, 25), 5)
    if where == 'BLOCKS': doc.modelspace().add_blockref('PART', (0, 0))
    doc.saveas(path)
    path.write_text(path.read_text().replace('CIRCLE\n  5\n'+hole.dxf.handle+'\n', 'CIRCLE\n  5\n0\n'))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='geçersiz geometri kaydı'):
        dwg_import._read_converted(path, None, {})
    assert path.read_bytes() == before


def test_libredwg_handle_zero_endblk_is_preserved_with_a_fresh_handle(tmp_path):
    path = tmp_path/'converted.dxf'; doc = ezdxf.new(); doc.units = 4
    block = doc.blocks.new('PART')
    block.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    block.add_circle((40, 25), 5)
    doc.modelspace().add_blockref('PART', (0, 0)); doc.saveas(path)
    old = block.endblk.dxf.handle
    path.write_text(path.read_text().replace('ENDBLK\n  5\n'+old+'\n', 'ENDBLK\n  5\n0\n'))
    before = path.read_bytes()
    parts = dwg_import._read_converted(path, None, {})
    assert len(parts) == 1 and len(parts[0].polygon.interiors) == 1
    assert parts[0].area == pytest.approx(5000-25*3.141592653589793, abs=.5)
    cleaned = dwg_import._drop_invalid_handles(path)
    assert ezdxf.readfile(cleaned).blocks.get('PART').endblk.is_alive
    assert path.read_bytes() == before


def test_dwg_recovery_cannot_remove_invalid_cut_entities(tmp_path, monkeypatch):
    from ezdxf.audit import AuditError, Auditor
    from ezdxf import recover
    path = tmp_path/'converted.dxf'; doc, _ = drawing(path); doc.saveas(path)
    auditor = Auditor(doc)
    auditor.fixed_error(AuditError.REMOVED_INVALID_GRAPHIC_ENTITY, 'Removed invalid CIRCLE')
    calls = []
    def fail(path, **kwargs):
        calls.append(path)
        raise ValueError('broken source')
    monkeypatch.setattr(dwg_import, 'read_dxf', fail)
    monkeypatch.setattr(recover, 'readfile', lambda *args: (doc, auditor))
    with pytest.raises(ValueError, match='broken source'):
        dwg_import._read_converted(path, None, {})
    assert calls == [path]


def test_unstartable_oda_does_not_disable_the_available_fallback(tmp_path, monkeypatch):
    from modules.nesting.tests.test_bundled_dwg import write_dxf
    source = tmp_path/'source.dwg'; source.write_bytes(b'AC1032 source')
    target = tmp_path/'source.dxf'; calls = []
    monkeypatch.setattr(dwg_import, 'converters', lambda: [('oda', 'oda'), ('libredwg', 'libre')])
    def run(command, *args, **kwargs):
        calls.append(command[0])
        if command[0] == 'oda': raise PermissionError('cannot start')
        write_dxf(target)
        return 1  # LibreDWG may return nonzero for skipped non-geometric objects.
    monkeypatch.setattr(dwg_import, '_run', run)
    assert dwg_import.convert_dwg(source, target) == 'libredwg'
    assert calls == ['oda', 'libre']
    assert read_dxf(target)[0].area == pytest.approx(600)
    assert source.read_bytes() == b'AC1032 source'


@pytest.mark.parametrize('reader', [read_dxf, read_drawing])
@pytest.mark.parametrize('state', ['off', 'frozen', 'excluded'])
@pytest.mark.parametrize('in_block', [False, True])
def test_layer_names_ignore_case_including_inherited_block_layers(tmp_path, reader, state, in_block):
    path = tmp_path/'layers.dxf'; doc, space = drawing(path)
    layer = doc.layers.new('HELPER')
    if state == 'off': layer.off()
    elif state == 'frozen': layer.freeze()
    if in_block:
        block = doc.blocks.new('HELP'); block.add_line((200, 0), (220, 20))
        space.add_blockref('HELP', (0, 0), dxfattribs={'layer': 'helper'})
    else: space.add_line((200, 0), (220, 20), dxfattribs={'layer': 'helper'})
    doc.saveas(path)
    kwargs = {'excluded_layers': ['hElPeR']} if state == 'excluded' else {}
    parts = reader(path, **kwargs)
    if reader is read_drawing:
        assert len(parts) == 1 and parts[0].quantity == 2 and parts[0].area == 200
    else:
        assert len(parts) == 1 and parts[0].area == 4800 and len(parts[0].polygon.interiors) == 1


@pytest.mark.parametrize('cancel', [False, True])
def test_external_converter_is_killed_and_reaped_on_timeout_or_cancel(monkeypatch, cancel):
    import subprocess
    import sys
    from threading import Timer
    processes = []; real = subprocess.Popen
    def start(*args, **kwargs):
        process = real(*args, **kwargs); processes.append(process)
        return process
    monkeypatch.setattr(subprocess, 'Popen', start)
    stop = Event(); timer = Timer(.08, stop.set) if cancel else None
    if timer: timer.start()
    try:
        with pytest.raises(InterruptedError if cancel else TimeoutError):
            dwg_import._run([sys.executable, '-c', 'import time; time.sleep(30)'], stop, 5 if cancel else .08)
    finally:
        if timer: timer.cancel(); timer.join()
    assert len(processes) == 1 and processes[0].poll() is not None


@pytest.mark.parametrize('error', [InterruptedError, TimeoutError])
def test_cancel_or_timeout_never_launches_a_fallback_converter(tmp_path, monkeypatch, error):
    source = tmp_path/'source.dwg'; source.write_bytes(b'AC1032 source'); calls = []
    monkeypatch.setattr(dwg_import, 'converters', lambda: [('oda', 'oda'), ('libredwg', 'libre')])
    def run(command, *args, **kwargs):
        calls.append(command[0]); raise error('stopped')
    monkeypatch.setattr(dwg_import, '_run', run)
    with pytest.raises(error):
        dwg_import.convert_dwg(source, tmp_path/'out.dxf')
    assert calls == ['oda']


@pytest.mark.parametrize('header', [b'', b'AC10', b'AC10xx', b'AC103x', b'%PDF-1.7', b'PK\x03\x04'])
def test_invalid_dwg_header_never_starts_a_converter(tmp_path, monkeypatch, header):
    source = tmp_path/'broken.dwg'; source.write_bytes(header)
    monkeypatch.setattr(dwg_import, 'convert_dwg', lambda *args: pytest.fail('invalid header reached converter'))
    with pytest.raises(ValueError, match='DWG dosya başlığı'):
        dwg_import.read_dwg(source)
    assert source.read_bytes() == header


def test_thousands_of_loose_segments_report_the_real_gap_without_partial_parts(tmp_path):
    path = tmp_path/'loose-lines.dxf'; doc = ezdxf.new(); doc.units = 4
    for index in range(5000):
        doc.modelspace().add_line((index*3, 0), (index*3+1, 0))
    doc.saveas(path); before = path.read_bytes()
    with pytest.raises(dxf_import.OpenContour) as caught:
        read_dxf(path)
    assert caught.value.gap == 1 and not caught.value.branching
    assert '10000 açık uç' in str(caught.value)
    assert path.read_bytes() == before


def test_indexed_gap_diagnostic_matches_an_independent_exhaustive_oracle():
    import math
    import random
    from collections import Counter
    rng = random.Random(20261111)
    points = [(rng.uniform(-500, 500), rng.uniform(-500, 500)) for _ in range(80)]
    expected = max(min(math.dist(a, b) for b in points if a != b) for a in points)
    diagnostic = dxf_import._open_contour(Counter(dict.fromkeys(points, 1)), [])
    assert diagnostic.gap == pytest.approx(expected, abs=1e-12)


def test_oversized_converted_dxf_cannot_bypass_the_limit_via_recovery(tmp_path, monkeypatch):
    path = tmp_path/'large-converted.dxf'
    with path.open('wb') as stream:
        stream.truncate(100*1024*1024+1)
    monkeypatch.setattr(dwg_import, '_drop_invalid_handles', lambda *args: pytest.fail('oversized recovery scan'))
    monkeypatch.setattr(dwg_import, 'read_dxf', lambda *args, **kwargs: pytest.fail('oversized parser'))
    with pytest.raises(ValueError, match='100 MB'):
        dwg_import._read_converted(path, None, {})
