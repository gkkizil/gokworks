from dataclasses import replace
import threading
import pytest
from modules.cad_converter.models import Cancelled
from modules.press_brake.demo import load_demo
from modules.press_brake.models import Mount
from modules.press_brake.service import run


@pytest.mark.timeout(120)
def test_missing_tool_geometry_and_generic_mount_cannot_return_clear():
    p = load_demo('L120')
    punch = replace(p.tools[0], section=None, holder_section=None, mount=Mount('WILA', 'WILA'))
    result = run(p.changed(tools=(punch,)+p.tools[1:]))
    assert result.status == 'unknown'
    assert any('kesit eksik' in note for note in result.steps[0].notes)
    assert any('bağlantısı' in note for note in result.steps[0].notes)
    assert any('tutucu' in note for note in result.steps[0].notes)


def test_cancel_before_geometry_and_during_native_sweep_returns_no_result():
    p = load_demo('L120'); stop = threading.Event(); stop.set()
    with pytest.raises(Cancelled):
        run(p, stop)
    stop.clear()
    def progress(index, phase, value):
        stop.set()
    with pytest.raises(Cancelled):
        run(p, stop, progress)


@pytest.mark.parametrize('a,b', [(0, 1), (1, 2), (16, 1)])
def test_invalid_sampling_intervals_rejected(a, b):
    with pytest.raises(ValueError):
        run(load_demo('L120'), max_angle=a, min_angle=b)
