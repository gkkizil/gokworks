"""Offline raw COM contracts. No fixture here is a real SolidWorks model."""

from dataclasses import asdict
import json
from threading import Event, get_ident
from types import SimpleNamespace

import pytest

from modules.cad_converter.api import ApiError
from modules.automatic_drawing.models import (Box, Cancelled, DrawingResult, ModelInfo, Options, Source)
from modules.automatic_drawing.sheetmetal import inspect_bodies, thickness, verify_unfolded
from modules.automatic_drawing.solidworks import Session, hresult
from modules.automatic_drawing.manufacturing import flat_page
from modules.automatic_drawing.validation import validate_views
from .test_native_boundary import RawDispatch, case as case


@pytest.fixture(autouse=True)
def offline_dispatch_array(monkeypatch):
    # pywin32 correctly refuses Python RawDispatch doubles in VT_DISPATCH
    # arrays on Windows. This suite records the boundary, without live COM.
    from modules.automatic_drawing import manufacturing
    original = manufacturing.variant
    monkeypatch.setattr(manufacturing, 'variant', lambda kind, value:
        SimpleNamespace(varianttype=kind, value=value) if kind == 0x2009 else original(kind, value))


def inventory_case(*, fallback=False, reverse=False, wrong_parent=False):
    state = SimpleNamespace(configuration='Default', version=0, accesses=[], configs=tuple(
        ['Default']+[f'Body{i}-SM-FLAT-PATTERN' for i in range(1, 4)]), suppressed={})
    session = Session(); session.owner_thread = get_ident()
    session.constants = dict(swSolidBody=0, swSpecifyConfiguration=3, swThisConfiguration=1,
                             swCustomInfoGetResult_ResolvedValue=2)
    session.revision = 'FAKE:offline-body-contract'
    bodies, features, properties, notes = {}, {}, {}, []

    def body(index):
        version = state.version
        result = RawDispatch('IBody2', methods={'IsSheetMetal': lambda: True,
            'GetBodyBox': lambda: (0., 0., 0., .1*index, .05, .02),
            'GetFeatures': lambda: (), 'GetMaterialPropertyName2': lambda *args: ''},
            properties={'Name': 'same-display-name'})
        result.token = b'body'+bytes([index]); result.version = version
        return result

    def persistent(obj):
        if hasattr(obj, 'version') and obj.version != state.version:
            raise ApiError('stale body handle: reacquire after ReleaseSelectionAccess')
        return obj.token

    extension = RawDispatch('IModelDocExtension', methods={'GetPersistReference3': persistent})
    config = RawDispatch('IConfiguration', properties={'Name': lambda: state.configuration})
    config_manager = RawDispatch('IConfigurationManager', properties={'ActiveConfiguration': config})
    selection = RawDispatch('ISelectionMgr', methods={'SuspendSelectionList': lambda: None,
                                                    'ResumeSelectionList2': lambda *args: None})
    parent = RawDispatch('IConfiguration', properties={'Name': 'Other' if wrong_parent else 'Default'})
    derived = RawDispatch('IConfiguration', methods={'GetParent': lambda: parent})

    def get_bodies(*args):
        indexes = (3, 2, 1) if reverse else (1, 2, 3)
        return [body(i) for i in indexes]

    def show(name):
        state.configuration = name
        return True

    model = RawDispatch('IModelDoc2', methods={'GetPathName': lambda: 'C:/ORHAN.SLDPRT',
        'GetConfigurationNames': lambda: state.configs, 'GetConfigurationByName': lambda name: derived,
        'FeatureByName': lambda name: features.get(name), 'GetBodies2': get_bodies,
        'ShowConfiguration2': show}, properties={'Extension': extension,
        'ConfigurationManager': config_manager, 'SelectionManager': selection})
    descriptors = []
    for index, thick in enumerate((1.2, 2., 3.), 1):
        props = {'Sheet Metal Thickness': f'{thick} mm', 'Material': f'STEEL-{index}'}
        properties[index] = props
        def get6(name, cached, raw, resolved, good, linked, props=props):
            resolved.value, good.value = props[name], True
            return 2
        manager = RawDispatch('ICustomPropertyManager', methods={
            'GetNames': lambda props=props: tuple(props), 'Get6': get6})
        folder = RawDispatch('IBodyFolder', methods={'GetBodies': lambda i=index: [body(i)]})
        cut = RawDispatch('IFeature', methods={'GetTypeName2': lambda: 'CutListFolder',
            'GetSpecificFeature2': lambda folder=folder: folder}, properties={'CustomPropertyManager': manager})
        cut.token = b'cut'+bytes([index]); features[f'Cut{index}'] = cut
        def definition(i=index):
            scope = {'accessed': False}
            def access(*args):
                state.accesses.append('enter'); scope['accessed'] = True; state.version += 1
                return True
            def release():
                state.accesses.append('exit'); scope['accessed'] = False; state.version += 1
            def fixed():
                if fallback and not scope['accessed']:
                    return None
                return RawDispatch('IFace2', methods={'GetBody': lambda: body(i)})
            return RawDispatch('IFlatPatternFeatureData', methods={'AccessSelections': access,
                'ReleaseSelectionAccess': release}, properties={'FixedFace2': fixed})
        def suppression(option, configs, i=index):
            names = getattr(configs, 'value', configs)
            return tuple(state.suppressed.get((i, name), name != f'Body{i}-SM-FLAT-PATTERN') for name in names)
        flat = RawDispatch('IFeature', methods={'GetTypeName2': lambda: 'FlatPattern',
            'GetDefinition': definition, 'IsSuppressed2': suppression})
        flat.token = b'flat'+bytes([index]); features[f'Flat{index}'] = flat
        for name, kind, feature in ((f'Cut{index}', 'CutListFolder', cut), (f'Flat{index}', 'FlatPattern', flat)):
            descriptors.append((name, kind, session.persistent_ref(model, feature)))
    info = ModelInfo(Source('C:/ORHAN.SLDPRT', 'Default'), 'part', 'ORHAN', (300., 50., 20.),
        body_count=3, sheet_body_count=3, flat_configurations=state.configs[1:], source_unit='mm',
        properties={'Material': 'GLOBAL-DO-NOT-ASSIGN', 'Thickness': '9 mm'})
    return SimpleNamespace(**locals())


def test_three_equal_named_bodies_have_distinct_persistent_identity_thickness_material_and_flat_configuration():
    c = inventory_case()
    rows = inspect_bodies(c.session, c.model, c.info, c.descriptors, Event())
    assert [r.label for r in rows] == ['ORHAN-01', 'ORHAN-02', 'ORHAN-03']
    assert [r.thickness_mm for r in rows] == [1.2, 2., 3.]
    assert [r.material for r in rows] == ['STEEL-1', 'STEEL-2', 'STEEL-3']
    assert all(r.ready and r.cut_list_quantity == 1 and not r.warnings for r in rows)
    assert len({r.body_ref for r in rows}) == 3
    assert [r.configurations for r in rows] == [(name,) for name in c.state.configs[1:]]
    other = inventory_case(reverse=True)
    reordered = inspect_bodies(other.session, other.model, other.info, other.descriptors, Event())
    assert [(r.label, r.body_ref) for r in rows] == [(r.label, r.body_ref) for r in reordered]


def test_production_session_analysis_wires_body_inventory_and_caches_only_plain_independent_records(tmp_path):
    c = inventory_case()
    path = tmp_path/'ORHAN.SLDPRT'; path.write_bytes(b'FAKE offline native model fixture')
    c.model.methods.update(GetPathName=lambda: str(path), GetTitle=lambda: path.name,
        GetType=lambda: 1, GetPartBox=lambda accurate: (0., 0., 0., .3, .05, .02),
        GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 1, GetUnits=lambda: (4,))
    c.session.constants.update(swDocASSEMBLY=2, swDocPART=1, swMM=4)
    c.session.analysis_cache = {}
    original_body = c.body
    def body(index):
        item = original_body(index)
        item.methods['GetFaces'] = lambda: ()
        return item
    c.model.methods['GetBodies2'] = lambda *args: [body(i) for i in (1, 2, 3)]
    handles = list(c.features.items())
    for index, (name, feature) in enumerate(handles):
        following = handles[index+1][1] if index+1 < len(handles) else None
        feature.properties['Name'] = name
        feature.methods.update(GetFirstSubFeature=lambda: None, GetNextFeature=lambda nxt=following: nxt)
    c.model.methods['FirstFeature'] = lambda: handles[0][1]
    result = c.session.inspect(c.model, Source(str(path), 'Default'))
    assert len(result.sheet_bodies) == 3 and all(row.ready for row in result.sheet_bodies)
    assert result.sheet_bodies[0].thickness_mm == 1.2
    assert any('antet' in text for text in result.warnings)
    assert 'same-display-name' in json.dumps(asdict(result), allow_nan=False)
    assert c.session.analysis_cache
    result.sheet_bodies[0].label = 'Changed only in this plain UI record'
    again = c.session.inspect(c.model, result.source)
    assert again.sheet_bodies[0].label == 'ORHAN-01'


def test_suppressed_flat_definition_scope_is_balanced_and_every_body_is_reacquired_after_rollback():
    c = inventory_case(fallback=True)
    rows = inspect_bodies(c.session, c.model, c.info, c.descriptors, Event())
    assert all(r.ready and not r.warnings for r in rows)
    assert c.state.accesses == ['enter', 'exit']*3 and c.state.version == 6
    assert c.state.configuration == 'Default'
    assert not any(name.startswith(('Save', 'SetSuppression', 'ModifyDefinition'))
                   for feature in c.features.values() for name, flags, args in feature.calls)


@pytest.mark.parametrize('wrong_parent,ambiguous', [(True, False), (False, True)])
def test_unrelated_or_ambiguous_existing_flat_configuration_never_qualifies_for_body_output(wrong_parent, ambiguous):
    c = inventory_case(wrong_parent=wrong_parent)
    if ambiguous:
        c.state.suppressed[(1, 'Body2-SM-FLAT-PATTERN')] = False
    rows = inspect_bodies(c.session, c.model, c.info, c.descriptors)
    assert not rows[0].ready and rows[0].warnings


def test_duplicate_flat_binding_blocks_only_the_ambiguous_body():
    c = inventory_case()
    original = c.features['Flat1']
    extra = RawDispatch('IFeature', methods=original.methods)
    extra.token = b'otherflat'; c.features['DuplicateFlat'] = extra
    c.descriptors.append(('DuplicateFlat', 'FlatPattern', c.session.persistent_ref(c.model, extra)))
    rows = inspect_bodies(c.session, c.model, c.info, c.descriptors)
    assert not rows[0].ready and rows[1].ready and rows[2].ready


def test_missing_body_material_and_thickness_do_not_borrow_document_defaults():
    c = inventory_case(); c.properties[2].clear()
    row = inspect_bodies(c.session, c.model, c.info, c.descriptors)[1]
    assert row.ready and row.thickness_mm is None and row.material == ''
    assert any('kalınlığı' in text for text in row.warnings)


def test_renamed_turkish_derived_configuration_is_detected_by_feature_state_instead_of_english_name():
    c = inventory_case()
    renamed = 'Sac Açınımı-01'
    c.state.configs = ('Default', renamed, *c.state.configs[2:])
    c.state.suppressed[(1, renamed)] = False
    c.info.configurations = c.state.configs
    c.info.flat_configurations = ()
    rows = inspect_bodies(c.session, c.model, c.info, c.descriptors)
    assert rows[0].ready and rows[0].configurations == (renamed,)


@pytest.mark.parametrize('text,unit,expected', [('0,12 cm', 'mm', 1.2), ('0.05 in', 'mm', 1.27),
    ('2', 'mm', 2.), ('2', '', None), ('2.000,5 mm', 'mm', None), ('-2 mm', 'mm', None)])
def test_cut_list_thickness_has_explicit_units_and_never_guesses_ambiguous_numbers(text, unit, expected):
    body = RawDispatch('IBody2', methods={'GetFeatures': lambda: ()})
    assert thickness(None, body, {'THICKNESS': text}, unit) == expected


def test_cancelled_body_inventory_stops_before_feature_access():
    c = inventory_case(); stop = Event(); stop.set()
    with pytest.raises(Cancelled):
        inspect_bodies(c.session, c.model, c.info, c.descriptors, stop)
    assert not c.state.accesses


def test_lost_com_connection_during_identity_read_is_not_swallowed_as_missing_body_data():
    c = inventory_case()
    class Disconnected(Exception):
        hresult = -2147023174
    def disconnected(obj):
        raise Disconnected('server unavailable')
    c.extension.methods['GetPersistReference3'] = disconnected
    with pytest.raises(RuntimeError, match='server unavailable') as failure:
        inspect_bodies(c.session, c.model, c.info, c.descriptors)
    assert hresult(failure.value) == -2147023174


def test_property_read_configuration_drift_stops_analysis_and_outer_scope_restores_original():
    c = inventory_case()
    manager = c.features['Cut1'].properties['CustomPropertyManager']
    original = manager.methods['Get6']
    def drift(*args):
        c.state.configuration = c.state.configs[1]
        return original(*args)
    manager.methods['Get6'] = drift
    with pytest.raises(ApiError, match='konfigürasyonu değişti'):
        with c.session.configuration(c.model, 'Default'):
            inspect_bodies(c.session, c.model, c.info, c.descriptors)
    assert c.state.configuration == 'Default'


def test_last_minute_flat_suppression_is_rechecked_before_native_view_creation():
    c = inventory_case()
    row = inspect_bodies(c.session, c.model, c.info, c.descriptors)[0]
    c.state.suppressed[(1, row.configurations[0])] = True
    with pytest.raises(ApiError, match='bastırılmış'):
        verify_unfolded(c.session, c.model, row, row.configurations[0])


def native_flat_case(case, *, ignore_body_filter=False, new_config=False, wrong_config=False, bodies=1,
                     no_body_filter=False, note_on_view=False):
    """Recorded DrawingDoc/ModelDoc2 protocol, deliberately no real CAD geometry."""
    c = inventory_case()
    info = c.info
    info.sheet_bodies = inspect_bodies(c.session, c.model, info, c.descriptors)[:bodies]
    native = case.native
    native.info, native.session = info, c.session
    c.session.constants['swAttachAnnotationOption_Sheet'] = 0
    native.options, native.result = Options(), DrawingResult(info.source)
    native.model, native.drawing = case.model, case.drawing
    pages, views, sheet_properties, source_calls = {}, {}, {}, []

    def activate(name):
        case.state['name'], case.state['props'] = name, sheet_properties[name]
        return True

    def setup(plan, *, new=False):
        props = [0, 0, plan.scale, 1., True, plan.width_mm/1000., plan.height_mm/1000., False]
        sheet_properties[plan.name] = props
        pages[plan.name] = []
        native.pages[plan.name] = dict(plan=plan, views={}, tables=[], notes=[], format='')
        activate(plan.name)
    native.setup = setup
    case.drawing.methods['ActivateSheet'] = activate
    pending = []                 # notes that SolidWorks put on a view, not on the sheet
    def attach(option):
        if option == 0 and pending:
            pages[case.state['name']].append(pending.pop())
        return True              # recorded: True even when nothing is selected/attached
    case.drawing.methods['AttachAnnotation'] = attach
    c.session.open_drawing = lambda path: (case.model, case.drawing)
    c.session.close_created = lambda model: source_calls.append('close-owned-drawing')
    c.session.activate = lambda model: source_calls.append('activate-owned-drawing')
    selected = []
    def delete_configuration(name):
        if name not in c.state.configs:
            return False
        c.state.configs = tuple(n for n in c.state.configs if n != name); return True
    c.model.methods.update(DeleteConfiguration2=delete_configuration, ClearSelection2=lambda all: selected.clear())
    original_body = c.body
    def selectable(index):
        body = original_body(index)
        body.methods['Select2'] = lambda append, data, body=body: selected.append(body.token) is None
        return body
    c.model.methods['GetBodies2'] = lambda *args: [selectable(i) for i in (1, 2, 3)]

    def create(path, config, x, y, z, hide, flip):
        # Recorded on SolidWorks 2025 SP5 (single sheet body, part reopened from disk): the
        # PARENT configuration resolves to its existing derived flat configuration; naming the
        # flat configuration itself yields a folded view that references the parent.
        if new_config:
            c.state.configs += ('UNEXPECTED',)
        resolved = info.sheet_bodies[0].configurations[0] if config == 'Default' else 'Default'
        multibody = len(info.sheet_bodies) > 1
        if multibody:
            # Recorded on SolidWorks 2025 SP5 (multibody, reopened part): a NEW temporary
            # '<parent>SM-FLAT-PATTERN<n>' is created for the selected body; no body filter.
            resolved = f'DefaultSM-FLAT-PATTERN-TEMP{len(views)+1}'
            c.state.configs += (resolved,)
        props = dict(Position=(x, y), UseSheetScale=False, ReferencedDocument=c.model,
                     Bodies=() if (no_body_filter or multibody) else c.get_bodies(),
                     ReferencedConfiguration='Default' if wrong_config else resolved)
        def bounds():
            vx, vy = props['Position']; scale = case.state['props'][2]
            return vx-.04*scale, vy-.02*scale, vx+.04*scale, vy+.02*scale
        class View(RawDispatch):
            def Invoke(self, member, lcid, flags, result_wanted, *args):
                if (ignore_body_filter or multibody) and member == 'Bodies' and flags == 4:
                    self.calls.append((member, flags, args)); return None
                return super().Invoke(member, lcid, flags, result_wanted, *args)
        name = 'Flat'+str(len(views)+1)
        view = View('IView', methods={'GetName2': lambda: name, 'GetOutline': bounds,
            'IsFlatPatternView': lambda: True, 'GetReferencedModelName': lambda: info.source.path,
            'GetBodiesCount': lambda: len(props['Bodies']), 'GetFirstDisplayDimension5': lambda: None,
            'GetTableAnnotations': lambda: None, 'GetNextView': lambda: None}, properties=props)
        views[case.state['name']] = view
        return view
    case.drawing.methods['CreateFlatPatternViewFromModelView3'] = create

    def insert(text):
        position = {'xyz': (0., 0., 0.)}
        current_notes = pages[case.state['name']]
        note_state = {'text': text}
        display = RawDispatch('IDisplayData', methods={
            'GetTextCount': lambda: len(note_state['text'].splitlines()),
            'GetTextPositionAtIndex': lambda i: (position['xyz'][0], position['xyz'][1]-i*.004, 0.),
            'GetTextInBoxWidthAtIndex': lambda i: len(note_state['text'].splitlines()[i])*.0015,
            'GetTextHeightAtIndex': lambda i: .003, 'GetTextAngleAtIndex': lambda i: 0.})
        font = RawDispatch('ITextFormat', properties={'CharHeight': .006})
        annotation = RawDispatch('IAnnotation', methods={'GetTextFormat': lambda i: font,
            'SetTextFormat': lambda *args: True, 'GetDisplayData': lambda: display,
            'Select3': lambda append, data: note_on_view,     # recorded False for a sheet note
            'SetPosition2': lambda *args: position.update(xyz=args) is None})
        name = 'BodyHeading'+str(sum(len(notes) for notes in pages.values())+1)
        note = RawDispatch('INote', methods={'GetName': lambda: name,
            'GetText': lambda: note_state['text'], 'GetAnnotation': lambda: annotation})
        note.state = note_state
        # Recorded on SolidWorks 2025 SP5: with the sheet active the note is the sheet's own.
        (pending if note_on_view else current_notes).append(note)
        return note
    case.model.methods['InsertNote'] = insert

    def first_view():
        name = case.state['name']
        return RawDispatch('IView(sheet)', methods={'GetNextView': lambda: views[name],
                                                  'GetNotes': lambda: tuple(pages[name]),
                                                  'GetTableAnnotations': lambda: None})
    case.drawing.methods['GetFirstView'] = first_view
    case.drawing.methods['GetSheetNames'] = lambda: tuple(pages)
    return SimpleNamespace(**locals())


def test_native_page_requests_the_parent_configuration_restores_source_and_reopens_with_identifiers(case):
    c = native_flat_case(case)
    flat_page(c.native, c.c.model)
    assert len(c.native.pages) == 1
    assert c.c.state.configuration == 'Default'
    findings, snapshots = c.native.validate()
    assert not [f for f in findings if f.severity == 'FAIL']
    assert [s['views'][0]['body_label'] for s in snapshots] == ['ORHAN-01']
    assert [s['notes'][0]['text'] for s in snapshots] == ['ORHAN-01\nt = 1.2 mm\nSTEEL-1']
    writes = [args[0] for view in c.views.values() for name, flags, args in view.calls
              if name == 'Bodies' and flags == 4]
    assert len(writes) == 1
    assert all(w.varianttype == 0x2009 and len(w.value) == 1 for w in writes)
    calls = [args for name, flags, args in case.drawing.calls if name == 'CreateFlatPatternViewFromModelView3']
    assert [args[1] for args in calls] == ['Default']          # parent, never the flat configuration
    assert all(len(args) == 7 and args[5] is False for args in calls)
    assert c.views[next(iter(c.views))].properties['ReferencedConfiguration'] == 'Body1-SM-FLAT-PATTERN'
    assert not any(name == 'AttachAnnotation' for name, flags, args in case.drawing.calls)   # already on sheet
    assert not any(name == 'ActivateView' and args == ('',) for name, flags, args in case.drawing.calls)
    c.native.close()
    findings, reread = c.native.verify_saved('FAKE-not-a-native-file.SLDDRW', snapshots)
    assert not [f for f in findings if f.severity == 'FAIL']
    assert len(reread) == 1 and c.c.state.configuration == 'Default'
    assert not any('Save' in name or 'SetSuppression' in name for name, flags, args in c.c.model.calls)


@pytest.mark.parametrize('kind', ['body', 'configuration', 'heading', 'missing_heading', 'suppressed',
                                  'thickness', 'material', 'membership'])
def test_saved_native_flat_recheck_rejects_foreign_body_wrong_configuration_or_changed_heading(case, kind):
    c = native_flat_case(case); flat_page(c.native, c.c.model)
    findings, snapshots = c.native.validate()
    first = snapshots[0]['name']
    c.native.close()
    if kind == 'body':
        c.views[first].properties['Bodies'] = (c.c.body(2),)
    elif kind == 'configuration':
        c.views[first].properties['ReferencedConfiguration'] = c.c.state.configs[2]
    elif kind == 'heading':
        c.pages[first][0].state['text'] = 'WRONG-PART-01'
    elif kind == 'suppressed':
        c.c.state.suppressed[(1, c.c.state.configs[1])] = True
    elif kind == 'thickness':
        c.c.properties[1]['Sheet Metal Thickness'] = '99 mm'
    elif kind == 'material':
        c.c.properties[1]['Material'] = 'WRONG-STEEL'
    elif kind == 'membership':
        folder = c.c.features['Cut1'].methods['GetSpecificFeature2']()
        folder.methods['GetBodies'] = lambda: [c.c.body(2)]
    else:
        c.pages[first].clear()
    try:
        after, reread = c.native.verify_saved('FAKE-not-a-native-file.SLDDRW', snapshots)
    except (ApiError, RuntimeError):
        return
    assert any(f.severity == 'FAIL' for f in after)


@pytest.mark.parametrize('problem', ['ignored_filter', 'new_config', 'wrong_config'])
def test_unsafe_native_creation_never_reports_a_flat_package_as_completed(case, problem):
    c = native_flat_case(case, ignore_body_filter=problem == 'ignored_filter',
                         new_config=problem == 'new_config', wrong_config=problem == 'wrong_config')
    with pytest.raises((ApiError, RuntimeError)):
        flat_page(c.native, c.c.model)
    assert not c.native.result.measurements.get('flat_pattern')
    assert c.c.state.configuration == 'Default'


@pytest.mark.parametrize('solids', (1, 3))
def test_a_flat_view_without_body_filter_is_the_only_body_of_a_single_body_part(case, solids):
    # Recorded on SolidWorks 2025 SP5: single-body flat pattern view → GetBodiesCount 0 and
    # Bodies empty, also after Bodies is written. It is accepted only when one solid body exists.
    c = native_flat_case(case, ignore_body_filter=True, no_body_filter=True)
    c.c.model.methods['GetBodies2'] = lambda *args: [c.c.body(i) for i in range(1, solids+1)]
    if solids == 1:
        flat_page(c.native, c.c.model)
        actual = c.native.actual_views(next(iter(c.native.pages)))[0]
        assert actual['body_count'] == 1 and actual['body_references'] == (c.info.sheet_bodies[0].body_ref,)
    else:
        with pytest.raises(ApiError, match='başka veya birden fazla gövde'):
            flat_page(c.native, c.c.model)


def test_an_unavailable_single_flat_body_is_reported_and_no_view_is_requested(case):
    c = native_flat_case(case)
    c.info.sheet_bodies[0].configurations = ()
    flat_page(c.native, c.c.model)
    assert not c.native.pages
    assert any(f.code == 'body_flat_unavailable' and 'ORHAN-01' in f.text for f in c.native.result.findings)


def test_multibody_flat_views_are_retargeted_to_saved_configurations_and_temporaries_removed(case):
    # Recorded on SolidWorks 2025 SP5: on a reopened multibody part each selected-body request
    # created a NEW in-memory '<parent>SM-FLAT-PATTERN<n>'; a drawing bound to it lost the unfolded
    # geometry on reopen. Retargeted to the SAVED per-body configuration it survived the reopen.
    c = native_flat_case(case, bodies=3)
    saved = c.c.state.configs
    flat_page(c.native, c.c.model)
    assert c.c.state.configs == saved                     # every temporary configuration removed
    assert len(c.native.pages) == 3
    configs = [page['views']['flat'].properties['ReferencedConfiguration'] for page in c.native.pages.values()]
    assert configs == ['Body1-SM-FLAT-PATTERN', 'Body2-SM-FLAT-PATTERN', 'Body3-SM-FLAT-PATTERN']
    findings, snapshots = c.native.validate()
    assert not [f for f in findings if f.severity == 'FAIL']
    assert [s['views'][0]['body_references'] for s in snapshots] == [(row.body_ref,) for row in c.info.sheet_bodies]
    assert c.native.result.measurements['flat_pattern']['body_count'] == 3


def test_multibody_flat_view_whose_saved_configuration_also_unfolds_another_body_is_rejected(case):
    c = native_flat_case(case, bodies=3)
    c.c.state.suppressed[(2, 'Body1-SM-FLAT-PATTERN')] = False   # body 2 also unfolds there
    with pytest.raises(ApiError, match='başka veya birden fazla gövde'):
        flat_page(c.native, c.c.model)


def test_body_heading_must_be_attached_to_sheet_and_cannot_silently_follow_a_model_view(case):
    # Ownership is read back from the sheet's notes; AttachAnnotation's True is not trusted.

    c = native_flat_case(case, note_on_view=True)       # the note landed on a view
    case.drawing.methods['AttachAnnotation'] = lambda option: True   # recorded: True proves nothing
    with pytest.raises(ApiError, match='paftaya bağlanamadı'):
        flat_page(c.native, c.c.model)
    assert not c.native.result.measurements.get('flat_pattern')


def test_body_heading_on_a_view_is_moved_to_the_sheet_and_read_back(case):
    c = native_flat_case(case, note_on_view=True)
    flat_page(c.native, c.c.model)
    assert sum(name == 'AttachAnnotation' for name, flags, args in case.drawing.calls) == 1
    findings, snapshots = c.native.validate()
    assert snapshots[0]['notes'][0]['text'] == 'ORHAN-01\nt = 1.2 mm\nSTEEL-1'


def test_foreign_resolved_document_is_rejected_before_configuration_or_selection_access(case):
    c = native_flat_case(case); flat_page(c.native, c.c.model)
    first = next(iter(c.views.values()))
    foreign = RawDispatch('IModelDoc2(other source)', methods=dict(c.c.model.methods),
                          properties=dict(c.c.model.properties))
    foreign.methods['GetPathName'] = lambda: 'C:/UNRELATED.SLDPRT'
    first.properties['ReferencedDocument'] = foreign
    with pytest.raises(ApiError, match='farklı belgeye işlem uygulanmadı'):
        c.native.validate()
    assert [name for name, flags, args in foreign.calls] == ['GetPathName']


def test_flat_body_validator_rejects_foreign_body_multiple_bodies_and_wrong_flat_configuration():
    source = Source('C:/ORHAN.SLDPRT', 'Default')
    sheet = dict(name='Flat', expected=['flat'], width_mm=420., height_mm=297.)
    good = dict(role='flat', name='View1', outline=Box(20, 50, 100, 50), path=source.path,
                configuration='Flat-A', flat=True, expected_body='A', body_references=('A',),
                expected_flat_configuration='Flat-A', body_count=1)
    assert not validate_views(sheet, [good], source, flat_configurations=('Flat-A', 'Flat-B'))
    for bad in (dict(body_references=('B',)), dict(body_references=('A', 'B'), body_count=2),
                dict(configuration='Flat-B'), dict(body_references=())):
        findings = validate_views(sheet, [dict(good, **bad)], source, flat_configurations=('Flat-A', 'Flat-B'))
        assert any(f.code == 'flat_body' and f.severity == 'FAIL' for f in findings)
