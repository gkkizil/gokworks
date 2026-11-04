"""Host response validation at the Python boundary; no live SOLIDWORKS calls."""

from contextlib import nullcontext
from types import SimpleNamespace
import sys

import pytest

from modules.shaft_generator.models import Project, Stage
from modules.shaft_generator.drawing import controller
from modules.shaft_generator.drawing.models import Datum, DrawingSettings, FinishSpec, GeometricTolerance
from modules.shaft_generator.drawing.planner import plan


REOPENED_GROUPS = (
    ('views', 'views'), ('dimensions', 'dimensions'), ('surface_symbols', 'finishes'),
    ('datums', 'datums'), ('frames', 'frames'),
)


def response(intent):
    result = dict(success=True, rebuild_success=True, part_unchanged=True, issues=[], layout_conflicts=[],
                  reopened=dict(references_ok=True, **{key: len(intent[group]) for key, group in REOPENED_GROUPS}))
    for group in ('views', 'dimensions', 'notes', 'finishes', 'datums', 'frames'):
        result[group] = [dict(id=item['id'], created=True, tolerance_ok=True) for item in intent[group]]
    for output, requested in intent['outputs'].items():
        if requested:
            result[output] = dict(verified=True)
    return result


@pytest.fixture
def drawing():
    project = Project('MIL_T', [Stage(25, 40), Stage(30, 60), Stage(40, 50)])
    first = f'stage:{project.stages[0].id}:cylinder'
    last = f'stage:{project.stages[-1].id}:cylinder'
    project.drawing = DrawingSettings(isometric=True, finishes={first: FinishSpec(.8)}, datums=[Datum('A', first)],
                                     geometric=[GeometricTolerance('circular_runout', .02, last, ['A'])])
    intent = plan(project)
    assert intent['ready'], intent['errors']
    assert all(intent[group] for _, group in REOPENED_GROUPS)
    return project, intent, response(intent)


def test_complete_native_evidence_is_accepted(drawing):
    _, intent, result = drawing
    assert controller.assess(result, intent) == ('complete', [])


@pytest.mark.parametrize('key,group', REOPENED_GROUPS)
@pytest.mark.parametrize('value', ['missing', 0, None, True, -1, '1', 1.0])
def test_reopened_content_requires_valid_counts(drawing, key, group, value):
    _, intent, result = drawing
    if value == 'missing':
        del result['reopened'][key]
    else:
        result['reopened'][key] = value
    state, problems = controller.assess(result, intent)
    assert state == 'partial' and problems


def test_reopened_dimension_count_must_cover_the_plan(drawing):
    _, intent, result = drawing
    result['reopened']['dimensions'] -= 1
    assert result['reopened']['dimensions'] > 0
    assert controller.assess(result, intent)[0] == 'partial'


def test_template_content_may_increase_reopened_counts(drawing):
    _, intent, result = drawing
    for key, _ in REOPENED_GROUPS:
        result['reopened'][key] += 2
    assert controller.assess(result, intent) == ('complete', [])


@pytest.mark.parametrize('evidence', [None, [], 'invalid'])
def test_malformed_reopened_evidence_is_partial(drawing, evidence):
    _, intent, result = drawing
    result['reopened'] = evidence
    assert controller.assess(result, intent)[0] == 'partial'


@pytest.mark.parametrize('rows', [[], None, [None]])
def test_view_creation_evidence_cannot_be_missing_or_malformed(drawing, rows):
    _, intent, result = drawing
    result['views'] = rows
    assert controller.assess(result, intent)[0] == 'partial'


@pytest.mark.parametrize('output', ['pdf', 'dwg'])
@pytest.mark.parametrize('evidence', ['missing', None, {}, {'verified': False}, {'verified': 1}])
def test_requested_export_requires_explicit_verification(drawing, output, evidence):
    _, intent, result = drawing
    intent['outputs'][output] = True
    if evidence == 'missing':
        result.pop(output, None)
    else:
        result[output] = evidence
    assert controller.assess(result, intent)[0] == 'partial'


def test_unrequested_exports_do_not_require_evidence(drawing):
    _, intent, result = drawing
    intent['outputs'] = dict(pdf=False, dwg=False)
    result.pop('pdf', None)
    result.pop('dwg', None)
    assert controller.assess(result, intent) == ('complete', [])


@pytest.mark.parametrize('output', ['pdf', 'dwg'])
@pytest.mark.parametrize('enabled', [False, True])
def test_execute_assesses_actual_export_path_overrides(drawing, tmp_path, monkeypatch, output, enabled):
    """Exercise the real request/assessment path with only the native boundary replaced."""
    from modules.naming import native
    from modules.shaft_generator import bridge
    from solidworks import connection

    project, _, _ = drawing
    project.drawing.pdf = project.drawing.dwg = not enabled
    source = tmp_path / 'MIL_T.SLDPRT'
    source.write_bytes(b'synthetic part; no live CAD')
    paths = dict(pdf_path='', dwg_path='')
    paths[output + '_path'] = str(tmp_path / ('MIL_T.' + output)) if enabled else ''
    payload = controller.request(project, source, **paths)
    result = response(payload['plan'])
    result.pop('pdf', None)
    result.pop('dwg', None)
    result['process_id'] = 123
    powershell = tmp_path / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    powershell.parent.mkdir(parents=True)
    powershell.touch()
    monkeypatch.setenv('SystemRoot', str(tmp_path))
    monkeypatch.setattr(controller, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setitem(sys.modules, 'pythoncom', SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None))
    monkeypatch.setattr(connection, 'connect_to_solidworks', lambda: SimpleNamespace(GetProcessID=lambda: 123))
    monkeypatch.setattr(native, '_installed_interop', lambda process_id: tmp_path / 'interop.dll')
    monkeypatch.setattr(controller.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    monkeypatch.setattr(controller.subprocess, 'Popen', lambda *args, **kwargs: nullcontext(SimpleNamespace()))
    monkeypatch.setattr(bridge, '_exchange', lambda *args, **kwargs: result)
    outcome = controller.execute(payload)
    assert outcome['state'] == ('partial' if enabled else 'complete')
    assert bool(outcome['problems']) is enabled
    assert source.read_bytes() == b'synthetic part; no live CAD'
