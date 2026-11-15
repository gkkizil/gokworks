"""Recorded/raw IDispatch boundary tests; these are NOT live SolidWorks tests."""

from dataclasses import replace
from threading import Event, Thread, get_ident
from types import SimpleNamespace

import pytest

from modules.cad_converter.api import ApiError, RestoreError
from modules.automatic_drawing.models import ModelInfo, Options, Source
from modules.automatic_drawing.models import DrawingResult
from modules.automatic_drawing.layout import plan_sheet
from modules.automatic_drawing.rules import plan_views
from modules.automatic_drawing.solidworks import Session, prop
from modules.automatic_drawing.native import NativeDrawing, view_position


class RawDispatch:
    """Mimic PyIDispatch: no Python attribute access to API methods is possible."""
    def __init__(self, name, methods=None, properties=None):
        self.name = name
        self.methods, self.properties = methods or {}, properties or {}
        self.calls = []

    def GetIDsOfNames(self, lcid, name):
        if name not in self.methods and name not in self.properties:
            raise AttributeError(self.name+'.'+name)
        return name

    def Invoke(self, member, lcid, flags, result_wanted, *args):
        self.calls.append((member, flags, args))
        if flags == 1:
            return self.methods[member](*args)
        if flags == 2:
            value = self.properties[member]
            return value(*args) if callable(value) else value
        if flags == 4:
            self.properties[member] = getattr(args[0], 'value', args[0])
            return
        raise AssertionError('Unexpected dispatch flags')


@pytest.fixture
def case(tmp_path):
    constants = {name: index+100 for index, name in enumerate((
        'swMM', 'swDECIMAL', 'swDwgPapersUserDefined', 'swDwgTemplateCustom', 'swDwgTemplateNone',
        'swInsertDimensionsMarkedForDrawing', 'swInsertHoleWizardProfileDimensions',
        'swInsertHoleWizardLocationDimensions', 'swInsertDimensionsNotMarkedForDrawing',
        'swImportModelItemsFromAssemblyOnly', 'swImportModelItemsFromEntireModel',
        'swAutodimEntitiesAll', 'swAutodimSchemeBaseline', 'swAutodimHorizontalPlacementAbove',
        'swAutodimVerticalPlacementRight', 'swAutodimStatusSuccess', 'swAlignDimensionType_AutoArrange',
        'swExportPdfData', 'swExportData_ExportAllSheets', 'swSaveAsOptions_Silent',
        'swSaveAsOptions_Copy', 'swSaveAsCurrentVersion'))}
    state = {'name': 'Sheet1', 'props': [0, 0, 1., 1., True, .420, .297, False]}
    sheet = RawDispatch('ISheet', methods={
        'GetTemplateName': lambda: '', 'SetName': lambda name: state.update(name=name),
        'GetName': lambda: state['name'], 'GetProperties2': lambda: state['props'],
        'SetScale': lambda n, d, positions, text: state['props'].__setitem__(slice(2, 4), [n, d]) is None},
        properties={'CustomPropertyView': ''})
    views, selected = {}, {'name': ''}
    extension = RawDispatch('IModelDocExtension', methods={
        'SelectByID2': lambda name, kind, *args: selected.update(name=name) is None,
        'AlignDimensions': lambda *args: True,
        'SaveAs': lambda *args: True})
    model = RawDispatch('IModelDoc2', methods={'SetUnits': lambda *args: None,
        'GetUnits': lambda: (constants['swMM'], 0, 0, 3, 0),
        'ForceRebuild3': lambda top_only: True, 'ClearSelection2': lambda all: None},
        properties={'Extension': extension})

    def add_view(path, model_view, x, y, z, parent=None):
        name = 'View'+str(len(views)+1)
        reference = RawDispatch('IModelDoc2', methods={'GetPathName': lambda: path})
        props = {'ReferencedDocument': reference,
                 'ReferencedConfiguration': parent.properties['ReferencedConfiguration'] if parent else '',
                 'UseSheetScale': False, 'Position': (x, y)}
        def get_outline():
            px, py = props['Position']; scale = state['props'][2]/state['props'][3]
            return px-.025*scale, py-.015*scale, px+.025*scale, py+.015*scale
        view = RawDispatch('IView', methods={'GetName2': lambda: name,
            'GetOutline': get_outline, 'GetReferencedModelName': lambda: path,
            'GetBaseView': lambda: parent, 'GetFirstDisplayDimension5': lambda: None,
            'GetTableAnnotations': lambda: None}, properties=props)
        views[name] = view
        return view

    def setup_sheet(*args):
        assert len(args) == 17, 'SetupSheet6 requires all zone parameters'
        state['name'] = args[0]
        state['props'] = [args[1], args[2], args[3], args[4], args[5], args[7], args[8], False]
        return True

    drawing = RawDispatch('IDrawingDoc', methods={'GetCurrentSheet': lambda: sheet,
        'ActivateSheet': lambda name: True, 'SetupSheet6': setup_sheet,
        'CreateDrawViewFromModelView3': add_view,
        'CreateUnfoldedViewAt3': lambda x, y, z, flip: add_view('C:/p.sldprt', '', x, y, z, views[selected['name']]),
        'ActivateView': lambda name: True, 'InsertModelAnnotations3': lambda *args: (),
        'AutoDimension': lambda *args: constants['swAutodimStatusSuccess']})
    pdf = RawDispatch('IExportPdfData', methods={'SetSheets': lambda *args: True},
                      properties={'ViewPdfAfterSaving': True})
    app = RawDispatch('ISldWorks', methods={'GetExportFileData': lambda kind: pdf})
    session = SimpleNamespace(constants=constants, c=lambda key: constants[key],
                              new_drawing=lambda *args: (model, drawing), app=app,
                              activate=lambda model: None)
    info = ModelInfo(Source('C:/p.sldprt', 'Default'), 'part', 'p', (100, 50, 10), body_count=1)
    options = Options(main_view='front')
    result = DrawingResult(info.source)
    native = NativeDrawing(session, info, options, result, Event())
    return SimpleNamespace(**locals())


def test_raw_dual_interfaces_route_drawing_calls_without_python_method_attributes(case):
    assert not hasattr(case.model, 'SetupSheet6') and not hasattr(case.drawing, 'GetUnits')
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('C:/company.drwdot', plan)
    case.native.create_views(plan)
    assert any(name == 'SetUnits' for name, flags, args in case.model.calls)
    setup = next(args for name, flags, args in case.drawing.calls if name == 'SetupSheet6')
    assert len(setup) == 17 and setup[5] is True
    assert setup[7:9] == (.420, .297)
    projected = [args for name, flags, args in case.drawing.calls if name == 'CreateUnfoldedViewAt3']
    assert len(projected) == 2 and all(len(args) == 4 for args in projected)
    actual = case.native.actual_views(plan.name)
    assert all(v['configuration'] == 'Default' for v in actual)
    assert all(v['parent'] == 'View1' for v in actual if v['role'] in ('top', 'side'))
    assert all(view.properties['UseSheetScale'] is True for view in case.views.values())


def test_parameterized_custom_property_manager_uses_propertyget_not_method():
    manager = object()
    extension = RawDispatch('IModelDocExtension', properties={'CustomPropertyManager': lambda name: manager})
    assert prop(extension, 'CustomPropertyManager', 'Configured') is manager
    assert extension.calls == [('CustomPropertyManager', 2, ('Configured',))]


def test_native_refit_uses_two_coordinate_view_position_safearray(case):
    options = replace(case.options, top=False, side=False, isometric=False)
    case.native.options = options
    plan = plan_sheet(plan_views(case.info, options), options)
    case.native.create('fake.drwdot', plan)
    case.native.create_views(plan)
    case.native.fit(plan.name)
    writes = [args[0] for view in case.views.values() for name, flags, args in view.calls
              if name == 'Position' and flags == 4]
    assert writes and all(len(getattr(value, 'value', value)) == 2 for value in writes)
    assert all(plan.usable.contains(view['outline']) for view in case.native.actual_views(plan.name))


@pytest.mark.parametrize('position', [(0.,), (0., 0., 0.), (float('nan'), 0.)])
def test_native_view_position_rejects_invalid_api_coordinates(position):
    view = RawDispatch('IView', properties={'Position': position})
    with pytest.raises(ApiError, match='iki boyutlu'):
        view_position(view)


def test_model_dimensions_use_native_duplicate_elimination_and_skip_isometric(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    case.native.import_dimensions(plan.name)
    calls = [args for name, flags, args in case.drawing.calls if name == 'InsertModelAnnotations3']
    assert len(calls) == 3
    assert all(len(args) == 6 and args[2:] == (False, True, False, False) for args in calls)
    assert all(args[0] == case.constants['swImportModelItemsFromEntireModel'] for args in calls)
    case.native.info.kind = 'assembly'
    case.drawing.calls.clear(); case.native.import_dimensions(plan.name)
    assert all(args[0] == case.constants['swImportModelItemsFromAssemblyOnly']
               for name, flags, args in case.drawing.calls if name == 'InsertModelAnnotations3')


def test_pdf_export_uses_all_native_sheets_and_copy_does_not_rename_drawing(case, tmp_path):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan)
    case.native.save(tmp_path/'drawing.pdf', 'pdf')
    args = next(args for name, flags, args in case.extension.calls if name == 'SaveAs')
    assert len(args) == 6
    assert args[2] == case.constants['swSaveAsOptions_Silent'] | case.constants['swSaveAsOptions_Copy']
    assert any(name == 'SetSheets' and args[0] == case.constants['swExportData_ExportAllSheets']
               for name, flags, args in case.pdf.calls)
    assert case.pdf.properties['ViewPdfAfterSaving'] is False


def test_optional_geometric_dimensions_use_documented_success_enum_and_real_view_selection(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    case.native.options = replace(case.options, geometry_dimensions=True)
    case.native.geometry_dimensions(plan.name)
    args = next(args for name, flags, args in case.drawing.calls if name == 'AutoDimension')
    assert len(args) == 5 and args[0] == case.constants['swAutodimEntitiesAll']
    assert any(f.code == 'reference_dimensions' for f in case.result.findings)


def configured_session(*, fail_restore=False):
    state = {'name': 'Original', 'events': []}
    active = RawDispatch('IConfiguration', properties={'Name': lambda: state['name']})
    manager = RawDispatch('IConfigurationManager', properties={'ActiveConfiguration': active})
    selection = RawDispatch('ISelectionMgr', methods={
        'SuspendSelectionList': lambda: state['events'].append('suspend'),
        'ResumeSelectionList2': lambda unused: state['events'].append('resume')})
    def show(name):
        state['events'].append(name)
        if fail_restore and name == 'Original':
            return False
        state['name'] = name
        return True
    model = RawDispatch('IModelDoc2', methods={'GetConfigurationNames': lambda: ('Original', 'Variant'),
        'ShowConfiguration2': show, 'GetSaveFlag': lambda: False},
        properties={'ConfigurationManager': manager, 'SelectionManager': selection})
    session = Session(); session.owner_thread = get_ident()
    return session, model, state


def test_source_configuration_and_suspended_selection_restore_after_creation_exception():
    session, model, state = configured_session()
    with pytest.raises(ValueError, match='simulated'):
        with session.configuration(model, 'Variant'):
            assert state['name'] == 'Variant'
            raise ValueError('simulated drawing failure')
    assert state['name'] == 'Original'
    assert state['events'] == ['suspend', 'Variant', 'Original', 'resume']
    assert not any('Save' in name for name, flags, args in model.calls)


def test_failed_source_restore_is_fatal_and_selection_is_still_resumed():
    session, model, state = configured_session(fail_restore=True)
    with pytest.raises(RestoreError):
        with session.configuration(model, 'Variant'): pass
    assert state['events'][-1] == 'resume'


def test_com_owner_thread_guard_fails_before_any_model_api_access():
    session = Session(); session.owner_thread = get_ident()
    errors = []
    def run():
        try: session.source(Source('C:/part.sldprt'))
        except RuntimeError as error: errors.append(str(error))
    thread = Thread(target=run); thread.start(); thread.join()
    assert len(errors) == 1 and 'STA' in errors[0]


def test_dirty_or_unknown_source_status_never_autosaves_or_proceeds():
    session = Session()
    for dirty in (True, None):
        model = RawDispatch('IModelDoc2', methods={'GetSaveFlag': lambda: dirty})
        with pytest.raises(ApiError, match='kaydet'):
            session.source_ready(model)
        assert [name for name, flags, args in model.calls] == ['GetSaveFlag']


def test_center_marks_are_on_iview_with_ten_arguments_and_actual_count_readback(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    case.constants['swAutoInsertCenterMarkType_Hole'] = 1
    for view in case.views.values():
        view.methods['AutoInsertCenterMarks2'] = lambda *args: True
        view.methods['GetCenterMarkCount2'] = lambda: 4
    case.native.center_marks(plan.name)
    calls = [(view.name, args) for view in case.views.values() for name, flags, args in view.calls
             if name == 'AutoInsertCenterMarks2']
    assert len(calls) == 3 and all(owner == 'IView' and len(args) == 10 for owner, args in calls)
    assert case.result.measurements['center_marks'][plan.name] == 12


def test_saved_path_string_is_not_enough_when_referenced_model_cannot_be_resolved(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    case.views['View1'].properties['ReferencedDocument'] = None
    findings, snapshots = case.native.validate()
    assert any(f.code == 'resolved_source' and f.severity == 'FAIL' for f in findings)


def test_missing_model_title_property_clears_stale_template_value_instead_of_reusing_it(case):
    case.constants.update(swCustomInfoText=30, swCustomPropertyReplaceValue=2,
                          swCustomInfoAddResult_AddedOrChanged=0)
    written = {}
    manager = RawDispatch('ICustomPropertyManager', methods={
        'Add3': lambda name, kind, value, options: written.__setitem__(name, value) or 0})
    case.extension.properties['CustomPropertyManager'] = lambda config: manager
    case.native.options = replace(case.options, property_map=(('PartNo', 'PartNumber'),))
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    case.native.title_properties()
    assert written == {'PartNumber': ''}
    assert any(f.code == 'title_property' for f in case.result.findings)


def test_rejected_reads_retry_in_sta_but_mutating_calls_never_retry(monkeypatch):
    import sys
    from modules.automatic_drawing import solidworks as sw
    class BusyError(Exception):
        hresult = -2147418111
    attempts, pumps = [], []
    def read():
        attempts.append('read')
        if len(attempts) < 3:
            raise BusyError()
        return 'C:/part.sldprt'
    def write():
        attempts.append('write'); raise BusyError()
    monkeypatch.setitem(sys.modules, 'pythoncom', SimpleNamespace(PumpWaitingMessages=lambda: pumps.append(get_ident())))
    monkeypatch.setattr(sw.time, 'sleep', lambda seconds: None)
    model = RawDispatch('IModelDoc2', methods={'GetPathName': read, 'SaveAs': write})
    assert sw.call(model, 'GetPathName') == 'C:/part.sldprt'
    assert len(pumps) == 2 and len(attempts) == 3
    with pytest.raises(RuntimeError):
        sw.call(model, 'SaveAs')
    assert attempts.count('write') == 1 and len(pumps) == 2


@pytest.mark.parametrize('extra', (False, True))
def test_native_reopen_enumerates_all_saved_views_and_rejects_extra_template_view(case, extra):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    findings, snapshots = case.native.validate()
    assert not findings
    closed = []
    case.session.close_created = lambda model: closed.append(model)
    case.session.open_drawing = lambda path: (case.model, case.drawing)
    case.native.close()
    if extra:
        case.add_view('C:/p.sldprt', '*Front', .2, .2, 0.)
    ordered = list(case.views.values())
    for index, view in enumerate(ordered):
        view.methods['GetNextView'] = lambda index=index: ordered[index+1] if index+1 < len(ordered) else None
    sheet_view = RawDispatch('IView-sheet', methods={'GetNextView': lambda: ordered[0]})
    case.drawing.methods['GetFirstView'] = lambda: sheet_view
    case.drawing.methods['GetSheetNames'] = lambda: (case.state['name'],)
    if extra:
        with pytest.raises(ApiError, match='ek görünüş'):
            case.native.verify_saved('fake.SLDDRW', snapshots)
    else:
        new_findings, reread = case.native.verify_saved('fake.SLDDRW', snapshots)
        assert not new_findings and len(reread[0]['views']) == 4
    assert len(closed) == 2  # initial close, then the separately reopened checker


@pytest.mark.parametrize('refuses', (False, True))
def test_created_drawing_close_is_owned_and_verified_without_closing_user_documents(refuses):
    model = RawDispatch('IModelDoc2', methods={'GetTitle': lambda: 'Generated',
        'GetPathName': lambda: 'C:/out/Generated.SLDDRW'})
    app = RawDispatch('ISldWorks', methods={'CloseDoc': lambda name: None,
        'GetOpenDocumentByName': lambda path: model if refuses else None})
    session = Session(); session.owner_thread = get_ident(); session.app = app
    session.created = [model]
    user = RawDispatch('IModelDoc2')
    with pytest.raises(RestoreError):
        session.close_created(user)
    assert not app.calls
    if refuses:
        with pytest.raises(RestoreError, match='kapatmadı'):
            session.close_created(model)
        assert session.created == [model]
    else:
        session.close_created(model)
        assert not session.created
