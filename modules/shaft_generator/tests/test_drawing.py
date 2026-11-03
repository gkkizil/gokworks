"""Drawing planner, tolerances, layout and project compatibility (no SOLIDWORKS).

These tests check the CAD-independent part of `create_shaft_drawing`: which
dimensions, notes, symbols and views are planned, against which real geometry,
with which verified tolerance values. Native SLDDRW creation is covered by the
Windows-only tests at the end and is NOT exercised on Linux.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from modules.shaft_generator import storage
from modules.shaft_generator.models import Bore, Chamfer, CosmeticThread, Fillet, Groove, Keyway, Project, Stage
from modules.shaft_generator.drawing import controller
from modules.shaft_generator.drawing.layout import Box, SCALES, build as build_layout, choose_sheet
from modules.shaft_generator.drawing.models import (Datum, DrawingSettings, FinishSpec, GeometricTolerance,
                                                     ToleranceSpec)
from modules.shaft_generator.drawing.planner import plan, segments
from modules.shaft_generator.drawing.targets import dimension_targets, surface_targets, thread_designation
from modules.shaft_generator.drawing.tolerances import resolve


def three_stage():
    return Project('MIL_T', [Stage(25, 40), Stage(30, 60), Stage(40, 50)])


def by_target(result, target):
    return [d for d in result['dimensions'] if d['target'] == target]


# ---- Test 1: simple shaft ---------------------------------------------------
@pytest.mark.parametrize('scheme', ['baseline', 'chain', 'mixed'])
def test_simple_shaft_diameters_lengths_and_total(scheme):
    p = three_stage()
    result = plan(p, DrawingSettings(scheme=scheme))
    assert result['ready'] and not result['errors']
    assert [v['id'] for v in result['views']] == ['main']
    diameters = [d for d in result['dimensions'] if d['kind'] == 'diameter']
    assert [d['nominal_mm'] for d in diameters] == [25, 30, 40]
    assert all(d['view'] == 'main' and d['prefix'] == 'Ø' for d in diameters)
    # Each diameter is bound to a circular model edge of that cylinder's radius and span.
    assert [d['refs'][0] for d in diameters] == [dict(type='circle_in', x0=0, x1=40, r=12.5),
                                                 dict(type='circle_in', x0=40, x1=100, r=15),
                                                 dict(type='circle_in', x0=100, x1=150, r=20)]
    lengths = [d for d in result['dimensions'] if d['kind'] == 'distance']
    total = [d for d in lengths if d['target'] == 'total']
    assert len(total) == 1 and total[0]['nominal_mm'] == 150
    if scheme == 'baseline':
        assert [d['nominal_mm'] for d in lengths if d['target'] != 'total'] == [40, 100]
        assert all(d['refs'][0] == dict(type='plane_x', x=0.) for d in lengths)
        assert not total[0]['reference']
    elif scheme == 'chain':
        assert [d['nominal_mm'] for d in lengths if d['target'] != 'total'] == [40, 60, 50]
        assert total[0]['reference'] and total[0]['text'] == '(150)'  # no closed chain
    else:
        assert [d['nominal_mm'] for d in lengths if d['target'] != 'total'] == [40, 60]
        assert not total[0]['reference']
    # The same physical dimension is never planned twice.
    keys = [(d['view'], json.dumps(d['refs'], sort_keys=True)) for d in result['dimensions']]
    assert len(keys) == len(set(keys))


def test_equal_diameter_stages_are_one_cylinder_without_fake_shoulder():
    p = Project('MIL', [Stage(30, 40), Stage(30, 20), Stage(40, 50)])
    assert [(s['x0'], s['x1'], s['r']) for s in segments(p)] == [(0, 60, 15), (60, 110, 20)]
    result = plan(p, DrawingSettings(scheme='chain'))
    assert [d['nominal_mm'] for d in result['dimensions'] if d['kind'] == 'diameter'] == [30, 40]
    assert [d['nominal_mm'] for d in result['dimensions'] if d['kind'] == 'distance' and d['target'] != 'total'] == [60, 50]
    assert any('fiziksel omuz değildir' in w for w in result['warnings'])


# ---- Test 2: toleranced shaft ------------------------------------------------
def test_toleranced_shaft_assigns_each_tolerance_to_its_own_dimension():
    p = three_stage()
    s = DrawingSettings(scheme='chain')
    a, b, c = (st.id for st in p.stages)
    s.tolerances = {f'stage:{a}:diameter': ToleranceSpec('iso_fit', fit='h6'),
                    f'stage:{b}:diameter': ToleranceSpec('symmetric', .02),
                    f'stage:{c}:diameter': ToleranceSpec('bilateral', 0., -.03)}
    result = plan(p, s)
    assert result['ready']
    h6, sym, bil = (by_target(result, f'stage:{x}:diameter')[0] for x in (a, b, c))
    assert h6['text'] == 'Ø25 h6' and h6['tolerance']['fit'] == 'h6'
    # ISO 286-2: Ø25 h6 (over 18 up to 30) = 0 / −13 µm, from the verified table.
    assert h6['tolerance']['upper_mm'] == 0 and h6['tolerance']['lower_mm'] == pytest.approx(-.013)
    assert h6['tolerance']['sw_type'] == 7
    assert sym['text'] == 'Ø30 ±0,02' and sym['tolerance']['sw_type'] == 4
    assert sym['tolerance']['upper_mm'] == .02 and sym['tolerance']['lower_mm'] == -.02
    assert bil['text'] == 'Ø40 +0,00 / −0,03' and bil['tolerance']['sw_type'] == 2


def test_iso_fit_never_invents_classes_or_out_of_table_diameters():
    with pytest.raises(ValueError, match='doğrulanmış ISO 286'):
        resolve(ToleranceSpec('iso_fit', fit='h4'), 25, 'shaft')
    with pytest.raises(ValueError, match='1–400'):
        resolve(ToleranceSpec('iso_fit', fit='h6'), 450, 'shaft')
    with pytest.raises(ValueError, match='çap'):
        resolve(ToleranceSpec('iso_fit', fit='h6'), 40, '')
    hole = resolve(ToleranceSpec('iso_fit', fit='H7', display='class_and_deviations'), 10, 'hole')
    assert (hole.upper, hole.lower, hole.sw_type) == (pytest.approx(.015), 0, 8)
    assert hole.text == 'H7 (+0,015 / +0,00)'
    p = three_stage(); s = DrawingSettings()
    s.tolerances[f'stage:{p.stages[0].id}:diameter'] = ToleranceSpec('iso_fit', fit='zz9')
    result = plan(p, s)
    assert not result['ready'] and any('zz9' in e for e in result['errors'])


def test_length_tolerance_is_not_silently_dropped_in_baseline_scheme():
    p = three_stage(); s = DrawingSettings(scheme='baseline')
    s.tolerances[f'stage:{p.stages[1].id}:length'] = ToleranceSpec('symmetric', .1)
    result = plan(p, s)
    assert any('tolerans uygulanmadı' in w for w in result['warnings'])
    chain = plan(p, DrawingSettings(scheme='chain', tolerances=dict(s.tolerances)))
    assert by_target(chain, f'stage:{p.stages[1].id}:length')[0]['text'] == '60 ±0,10'


# ---- Test 3: surface roughness ----------------------------------------------
def test_roughness_symbols_bind_to_the_selected_cylinders_and_only_when_requested():
    p = three_stage(); a, b, c = (st.id for st in p.stages)
    assert plan(p, DrawingSettings())['finishes'] == []  # nothing invented
    s = DrawingSettings(finishes={f'stage:{a}:cylinder': FinishSpec(3.2), f'stage:{b}:cylinder': FinishSpec(.8),
                                  f'stage:{c}:cylinder': FinishSpec(1.6, 'removal_required', 'taşlama', '=')})
    result = plan(p, s)
    rows = {f['target']: f for f in result['finishes']}
    assert rows[f'stage:{a}:cylinder']['surface'] == dict(type='cylinder', x0=0, x1=40, r=12.5)
    assert rows[f'stage:{b}:cylinder']['surface'] == dict(type='cylinder', x0=40, x1=100, r=15)
    assert [rows[f'stage:{x}:cylinder']['text'] for x in (a, b, c)] == ['Ra 3,2', 'Ra 0,8', 'Ra 1,6']
    assert rows[f'stage:{c}:cylinder']['method'] == 'taşlama' and rows[f'stage:{c}:cylinder']['lay'] == '='


def test_bulk_roughness_is_opt_in_and_overridden_per_surface():
    p = three_stage(); s = DrawingSettings(default_finish=FinishSpec(3.2),
                                            finishes={f'stage:{p.stages[1].id}:cylinder': FinishSpec(.8)})
    texts = {f['target']: f['text'] for f in plan(p, s)['finishes']}
    assert list(texts.values()).count('Ra 3,2') == 2 and texts[f'stage:{p.stages[1].id}:cylinder'] == 'Ra 0,8'
    assert all(key.endswith(':cylinder') for key in texts)


def test_surface_targets_list_real_faces_only():
    p = three_stage()
    kinds = [k for _, _, k in surface_targets(p)]
    # Each stage owns the faces where it is the larger step; stage 3 also has the right end face.
    keys = [key.split(':')[-1] for key, _, _ in surface_targets(p)]
    assert keys == ['cylinder', 'face_left', 'cylinder', 'face_left', 'cylinder', 'face_left', 'face_right']
    assert kinds.count('cylinder') == 3


# ---- Test 4: grooves and keyways --------------------------------------------
def test_groove_and_keyway_dimensions_use_true_geometry():
    p = three_stage(); b = p.stages[1]
    groove = Groove(b.id, offset=10, width=1.3, depth=.6)
    key = Keyway(b.id, offset=20, length=28, width=8, depth=4)
    p.operations = [groove, key]
    result = plan(p, DrawingSettings())
    width = by_target(result, f'op:{groove.id}:width')[0]
    bottom = by_target(result, f'op:{groove.id}:bottom_diameter')[0]
    position = by_target(result, f'op:{groove.id}:position')[0]
    assert bottom['nominal_mm'] == pytest.approx(30 - 2 * .6) and bottom['text'] == 'Ø28,8'
    assert width['refs'] == [dict(type='circle', x=50, r=14.4), dict(type='circle', x=51.3, r=14.4)]
    assert position['nominal_mm'] == 10 and position['refs'][0] == dict(type='plane_x', x=40)
    # A 1,3 mm groove is unreadable at 1:1 → detail view with an ISO enlargement.
    detail = next(v for v in result['views'] if v['kind'] == 'detail')
    assert width['view'] == detail['id'] and detail['enlargement'] in (2, 5, 10)
    kw = {d['target'].split(':')[-1]: d for d in result['dimensions'] if (d['target'] or '').startswith(f'op:{key.id}')}
    assert kw['length']['nominal_mm'] == 28 and kw['length']['view'] == 'top'  # overall length incl. ends
    assert [r['condition'] for r in kw['length']['refs']] == ['max', 'max']
    assert kw['length']['refs'][0]['x'] == 64 and kw['length']['refs'][1]['x'] == 84  # arc centres
    assert kw['width']['nominal_mm'] == 8 and kw['position']['nominal_mm'] == 20
    assert kw['depth']['nominal_mm'] == 26 and kw['depth']['text'] == '26'  # d − t1 from the floor edge
    assert kw['depth']['refs'][1] == dict(type='silhouette', x0=60, x1=88, y=-15)
    assert {'top', f'section:{key.id}'} <= {v['id'] for v in result['views']}


# ---- Test 5: chamfer, fillet, bore and thread --------------------------------
def test_chamfer_fillet_bore_and_thread_annotations():
    p = three_stage(); a, b, c = p.stages
    p.operations = [Chamfer(a.id, 'left', 1), Chamfer(c.id, 'right', 1), Fillet(a.id, 'right', 2),
                    CosmeticThread(b.id, 'left', 20, 1.5)]
    p.bore = Bore(10, 30, 'blind', 'left')
    result = plan(p, DrawingSettings())
    notes = {n['text']: n for n in result['notes']}
    assert '2× 1 × 45°' in notes  # identical chamfers grouped
    assert notes['2× 1 × 45°']['ref'] == dict(type='circle', x=0, r=11.5)
    # The fillet sits in the concave corner against the larger stage: edge on the shoulder face.
    assert notes['R2']['ref'] == dict(type='circle', x=40, r=14.5)
    assert 'M30×1,5 - 20' in notes
    assert by_target(result, 'bore:diameter')[0]['view'] == 'side_left'
    assert by_target(result, 'bore:depth')[0]['nominal_mm'] == 30
    assert result['views'][0]['hidden_lines'] is True


def test_unverifiable_thread_is_reported_not_drawn():
    assert thread_designation(30, 3.5) == 'M30' and thread_designation(30, 2) == 'M30×2'
    assert thread_designation(31, 1.5) is None
    p = Project('M', [Stage(31, 60)]); p.operations = [CosmeticThread(p.stages[0].id, 'left', 10, 1.5)]
    result = plan(p, DrawingSettings())
    assert result['notes'] == [] and any('doğrulanmış ISO metrik' in w for w in result['warnings'])


# ---- GD&T and datums ------------------------------------------------------------
def test_runout_requires_a_defined_datum_and_axis_datum_follows_the_diameter():
    p = three_stage(); a, b, _ = p.stages
    s = DrawingSettings(geometric=[GeometricTolerance('circular_runout', .02, f'stage:{b.id}:cylinder', ['A'])])
    assert any('tanımlanmamış datum' in e for e in s.basic_errors())
    s.datums = [Datum('A', f'stage:{a.id}:cylinder')]
    result = plan(p, s)
    assert result['ready']
    datum = result['datums'][0]
    diameter = by_target(result, f'stage:{a.id}:diameter')[0]
    assert datum['attach'] == diameter['id']  # ISO 5459 axis datum in line with Ø25
    frame = result['frames'][0]
    assert frame['datums'] == ['A'] and frame['surface'] == dict(type='cylinder', x0=40, x1=100, r=15)
    assert DrawingSettings(geometric=[GeometricTolerance('cylindricity', .01, 'x', ['A'])],
                           datums=[Datum('A', 'x')]).basic_errors()


# ---- Test 6: complex shaft ----------------------------------------------------------
def test_eight_stage_shaft_layout_fits_without_overlaps_or_duplicates():
    p = Project('MIL_8', [Stage(d, l) for d, l in ((20, 30), (25, 25), (30, 40), (35, 60), (40, 35), (35, 30), (30, 25), (25, 30))])
    st = p.stages
    p.operations = [Groove(st[2].id, 5, 1.6, 1), Keyway(st[3].id, 10, 40, 10, 5), Chamfer(st[0].id, 'left', 1),
                    Chamfer(st[7].id, 'right', 1), Fillet(st[4].id, 'left', 1), CosmeticThread(st[6].id, 'right', 15, 1.5)]
    for scheme in ('baseline', 'chain', 'mixed'):
        result = plan(p, DrawingSettings(scheme=scheme, title=dict(material='C45', drawing_number='1', revision='A')))
        assert result['ready'], result['errors']
        assert result['layout']['sheet']['fits']
        assert not [w for w in result['warnings'] if 'çakış' in w or 'sığmıyor' in w or 'taşıyor' in w], result['warnings']
        boxes = [Box(*v['box']) for k, v in result['layout']['placements'].items()]
        title = Box(*result['layout']['sheet']['title_block'])
        assert not any(b.overlaps(title) for b in boxes)
        keys = [(d['view'], json.dumps(d['refs'], sort_keys=True)) for d in result['dimensions']]
        assert len(keys) == len(set(keys))


def test_sheet_and_scale_prefer_readable_iso_5455_scales():
    assert choose_sheet(150, 40, ['main']).size == 'A4' or choose_sheet(150, 40, ['main']).scale == (1, 1)
    small = build_layout(30, 10, ['main'], [])
    assert small.sheet.scale in ((2, 1), (5, 1)) and small.sheet.scale in SCALES
    long = build_layout(1500, 80, ['main'], [])
    assert long.sheet.scale[0] < long.sheet.scale[1] and not long.conflicts
    fixed = build_layout(1500, 80, ['main'], [], size='A4', scale_mode='fixed', scale=(1, 1))
    assert not fixed.sheet.fits and fixed.conflicts and 'sığmıyor' in fixed.conflicts[0]


# ---- Test 8: project compatibility ----------------------------------------------------
def test_old_projects_load_and_save_unchanged_when_drawing_is_off(tmp_path):
    v1 = Project('ESKI'); data = v1.to_dict()
    assert data['version'] == 1 and 'drawing' not in data
    path = tmp_path / 'eski.gokshaft.json'; storage.save(v1, path)
    loaded = storage.load(path)
    assert loaded.drawing is None and loaded.to_dict() == data
    v2 = Project('DELIK', bore=Bore()); assert v2.to_dict()['version'] == 2
    loaded.drawing = DrawingSettings()  # untouched defaults keep the old format
    assert loaded.to_dict() == data


def test_v3_round_trip_keeps_requirements_bound_to_ids_after_reordering(tmp_path):
    p = three_stage(); a = p.stages[0].id
    p.drawing = DrawingSettings(tolerances={f'stage:{a}:diameter': ToleranceSpec('iso_fit', fit='k6')},
                                finishes={f'stage:{a}:cylinder': FinishSpec(.8)})
    path = tmp_path / 'yeni.gokshaft.json'; storage.save(p, path)
    q = storage.load(path)
    assert json.loads(path.read_text())['version'] == 3
    assert q.drawing.to_dict() == p.drawing.to_dict()
    q.move_stage(a, 1)
    result = plan(q)
    assert by_target(result, f'stage:{a}:diameter')[0]['text'] == 'Ø25 k6'
    assert by_target(result, f'stage:{a}:diameter')[0]['refs'][0]['x0'] == 60  # moved with its stage


def test_deleting_a_stage_or_operation_prunes_and_reports_requirements():
    p = three_stage(); a, b, _ = p.stages
    key = Keyway(b.id, 5, 20, 8, 4); p.operations = [key]
    p.drawing = DrawingSettings(tolerances={f'stage:{a.id}:diameter': ToleranceSpec('symmetric', .1),
                                            f'op:{key.id}:width': ToleranceSpec('symmetric', .02)},
                                datums=[Datum('A', f'stage:{a}:cylinder')],
                                geometric=[GeometricTolerance('circular_runout', .02, f'stage:{b.id}:cylinder', ['A'])])
    removed = p.remove_stage(a.id)
    assert f'stage:{a.id}:diameter' in removed and 'datum A' in removed
    assert any(r.startswith('geometrik tolerans') for r in removed)
    p.operations = []
    assert p.prune_drawing() == [f'op:{key.id}:width']
    assert plan(p)['ready']


def test_invalid_settings_files_are_rejected_with_a_reason():
    p = three_stage(); data = p.to_dict()
    data.update(version=3, bore=None, drawing=dict(DrawingSettings().to_dict(), sheet_size='A9'))
    with pytest.raises(ValueError, match='Sayfa boyutu'):
        Project.from_dict(data)
    data['drawing'] = dict(DrawingSettings().to_dict(), unknown=1)
    with pytest.raises(ValueError, match='bilinmeyen'):
        Project.from_dict(data)


# ---- command contract -------------------------------------------------------------------
def test_drawing_payload_refuses_overwrite_and_stale_plans(tmp_path):
    p = three_stage(); part = tmp_path / 'MIL_T.SLDPRT'; part.write_bytes(b'part')
    payload = controller.request(p, part)
    assert payload['drawing_path'] == str(part.with_suffix('.SLDDRW')) and payload['pdf_path'].endswith('.PDF')
    project, result = controller.checked_payload(json.loads(json.dumps(payload)))
    assert result['ready'] and project.name == 'MIL_T'
    stale = dict(payload, plan=dict(payload['plan'], dimensions=[]))
    with pytest.raises(ValueError, match='eşleşmiyor'):
        controller.checked_payload(stale)
    Path(payload['drawing_path']).write_bytes(b'old')
    with pytest.raises(FileExistsError):
        controller.checked_payload(payload)


def test_existing_create_shaft_contract_is_unchanged():
    from modules.shaft_generator import controller as part_controller
    p = three_stage(); p.drawing = DrawingSettings(enabled=True, tolerances={
        f'stage:{p.stages[0].id}:diameter': ToleranceSpec('symmetric', .1)})
    payload = part_controller.request(p)
    assert payload['operation'] == 'create_shaft' and set(payload) == {'operation', 'project', 'plan', 'output_path', 'verify_edit'}
    from modules.shaft_generator.bridge import checked_payload
    assert checked_payload(payload).stages[0].diameter == 25


def test_host_outcome_is_partial_when_anything_is_missing():
    p = three_stage(); result_plan = plan(p)
    ok_rows = {g: [dict(id=x['id'], created=True) for x in result_plan[g]] for g in ('dimensions', 'notes', 'finishes', 'datums', 'frames')}
    good = dict(success=True, views=[dict(id='main', created=True)], reopened=dict(references_ok=True),
                rebuild_success=True, part_unchanged=True, layout_conflicts=[], **ok_rows)
    assert controller.assess(good, result_plan) == ('complete', [])
    missing = dict(good, dimensions=ok_rows['dimensions'][:-1] + [dict(id='x', created=False)])
    state, problems = controller.assess(missing, result_plan)
    assert state == 'partial' and any('oluşturulamadı' in m for m in problems)
    state, problems = controller.assess(dict(good, part_unchanged=False), result_plan)
    assert state == 'partial'
    assert controller.assess(dict(success=False, errors=['x']), result_plan) == ('failed', ['x'])


# ---- UI ------------------------------------------------------------------------------------
def test_drawing_panel_edits_tolerance_and_finish_without_touching_geometry(qtbot, tmp_path):
    from gui_qt.app import MainWindow, create_application
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window); window.show()
    window.navigate('shaft_generator'); page = window.pages['shaft_generator']; panel = page.drawing_panel
    geometry = json.dumps([page.project.to_dict()['stages'], page.project.to_dict()['operations']])
    page.section_picker.setCurrentIndex(page.section_picker.findData(page.drawing_tab))
    assert page.tabs.currentIndex() == page.drawing_tab
    panel.dimension.setCurrentIndex(0)
    panel.tol_kind.setCurrentIndex(panel.tol_kind.findData('iso_fit')); panel.fit.setCurrentText('g6'); panel.store_tolerance()
    assert 'g6' in panel.tol_preview.text() and page.dirty
    panel.surface.setCurrentIndex(0); panel.finish_on.setChecked(True); panel.ra.setCurrentText('0,8'); panel.store_finish()
    assert '1 yüzey işareti' in panel.plan_summary.text()
    assert page.project.to_dict()['version'] == 3
    assert json.dumps([page.project.to_dict()['stages'], page.project.to_dict()['operations']]) == geometry
    page.dirty = False


# ---- native (Windows only) ------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_SHAFT_TEST_INTEROP'),
                    reason='Windows and explicitly staged interop compile references required; no live CAD.')
def test_drawing_host_compiles_through_the_shipping_loader():
    library = Path(os.environ['GOKWORKS_SHAFT_TEST_INTEROP']).resolve()
    marker = '[Gokworks.ShaftInterop.DrawingHost]::Run()'
    assert controller.LOADER.count(marker) == 1
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    probe = "[Console]::WriteLine('GOKWORKS_DRAWING_HOST_COMPILED ' + [Gokworks.ShaftInterop.DrawingHost].FullName)"
    result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-Command',
                             controller.LOADER.replace(marker, probe)], input='', encoding='utf-8', capture_output=True,
                            timeout=60, creationflags=subprocess.CREATE_NO_WINDOW,
                            env={**os.environ, 'GOKWORKS_SHAFT_INTEROP': str(library),
                                 'GOKWORKS_SHAFT_HOST': str(controller.HOST_SOURCE)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GOKWORKS_DRAWING_HOST_COMPILED Gokworks.ShaftInterop.DrawingHost' in result.stdout


@pytest.mark.skipif(sys.platform != 'win32' or os.environ.get('GOKWORKS_SHAFT_DRAWING_LIVE') != '1',
                    reason='Live SOLIDWORKS drawing test: Windows, open SOLIDWORKS and GOKWORKS_SHAFT_DRAWING_LIVE=1.')
def test_live_part_drawing_pdf_and_reopen(tmp_path):
    """Test 7 — real SLDPRT, SLDDRW and PDF, reopened and verified by the host."""
    from modules.shaft_generator import controller as part_controller
    from modules.shaft_generator.bridge import execute as create_part
    p = three_stage(); a, b, c = p.stages
    p.operations = [Groove(b.id, 10, 1.3, .6), Keyway(b.id, 20, 28, 8, 4), Chamfer(a.id, 'left', 1)]
    p.drawing = DrawingSettings(enabled=True, pdf=True, scheme='chain', tolerances={
        f'stage:{a.id}:diameter': ToleranceSpec('iso_fit', fit='h6'),
        f'stage:{b.id}:diameter': ToleranceSpec('symmetric', .02),
        f'stage:{c.id}:diameter': ToleranceSpec('bilateral', 0., -.03)},
        finishes={f'stage:{a.id}:cylinder': FinishSpec(3.2), f'stage:{b.id}:cylinder': FinishSpec(.8),
                  f'stage:{c.id}:cylinder': FinishSpec(1.6)})
    part = tmp_path / 'MIL_T.SLDPRT'
    create_part(part_controller.request(p, output_path=part))
    outcome = controller.execute(controller.request(p, part))
    assert outcome['state'] == 'complete', outcome['problems']
    assert Path(outcome['drawing_path']).is_file() and Path(outcome['pdf_path']).read_bytes()[:4] == b'%PDF'
