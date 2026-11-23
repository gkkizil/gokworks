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
        'swExportPdfData', 'swExportData_ExportAllSheets', 'swExportData_ExportSpecifiedSheets', 'swSaveAsOptions_Silent',
        'swSaveAsOptions_Copy', 'swSaveAsCurrentVersion'))}
    state = {'name': 'Sheet1', 'props': [0, 0, 1., 1., True, .420, .297, False]}
    sheet = RawDispatch('ISheet', methods={
        'GetTemplateName': lambda: '', 'SetName': lambda name: state.update(name=name),
        'GetName': lambda: state['name'], 'GetProperties2': lambda: state['props'],
        'SetScale': lambda n, d, positions, text: state['props'].__setitem__(slice(2, 4), [n, d]) is None,
        # Real SolidWorks: changes size/scale/projection and keeps the template's own sheet format.
        'SetProperties2': lambda paper, template, n, d, first, w, h, same:
            state.update(props=[paper, template, n, d, first, w, h, same]) is None},
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
        'GetFirstView': lambda: RawDispatch('IView-sheet'),
        'GetSheetNames': lambda: (state['name'],),
        'ActivateSheet': lambda name: True, 'SetupSheet6': setup_sheet,
        'CreateDrawViewFromModelView3': add_view,
        'CreateUnfoldedViewAt3': lambda x, y, z, flip: add_view('C:/p.sldprt', '', x, y, z, views[selected['name']]),
        'ActivateView': lambda name: True, 'InsertModelAnnotations3': lambda *args: (),
        'AutoDimension': lambda *args: constants['swAutodimStatusSuccess']})
    def set_sheets(which, sheets):
        # Recorded on SolidWorks 2025 SP5: ExportAllSheets is refused with any Sheets
        # argument; ExportSpecifiedSheets with the sheet names is accepted.
        names = getattr(sheets, 'value', sheets)
        return which == constants['swExportData_ExportSpecifiedSheets'] and bool(names)
    pdf = RawDispatch('IExportPdfData', methods={'SetSheets': set_sheets},
                      properties={'ViewPdfAfterSaving': True})
    app = RawDispatch('ISldWorks', methods={'GetExportFileData': lambda kind: pdf})
    session = SimpleNamespace(constants=constants, c=lambda key: constants[key],
                              new_drawing=lambda *args, **kwargs: (model, drawing), app=app,
                              activate=lambda model: None)
    info = ModelInfo(Source('C:/p.sldprt', 'Default'), 'part', 'p', (100, 50, 10), body_count=1)
    options = Options(main_view='front')
    result = DrawingResult(info.source)
    native = NativeDrawing(session, info, options, result, Event())
    return SimpleNamespace(**locals())


def refuse_template_sheet(case):
    """Fallback path: SolidWorks refuses ISheet.SetProperties2, SetupSheet6 rebuilds the sheet."""
    case.sheet.methods['SetProperties2'] = lambda *args: False


def test_template_sheet_keeps_its_own_format_and_only_changes_scale_and_projection(case):
    case.sheet.methods['GetTemplateName'] = lambda: 'C:/formats/a3 - iso.slddrt'
    case.constants['swDwgPaperA3size'] = 7
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('C:/company.drwdot', plan)
    assert not any(name == 'SetupSheet6' for name, flags, args in case.drawing.calls)
    sent = next(args for name, flags, args in case.sheet.calls if name == 'SetProperties2')
    scale1, scale2 = sent[2:4]
    assert sent[0] == 7 and sent[4] is True and sent[7] is True and plan.scale == pytest.approx(scale1/scale2)
    assert case.result.measurements['sheet_setup'][plan.name] == 'template'
    assert not case.result.findings                     # the template's title block stays: no warning


def test_template_sheet_refused_falls_back_to_setupsheet6(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('C:/company.drwdot', plan)
    assert any(name == 'SetupSheet6' for name, flags, args in case.drawing.calls)


def test_raw_dual_interfaces_route_drawing_calls_without_python_method_attributes(case):
    refuse_template_sheet(case)
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
    assert all(view.properties['UseSheetScale'] == 1 for view in case.views.values())


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
    set_sheets = [args for name, flags, args in case.pdf.calls if name == 'SetSheets']
    assert len(set_sheets) == 1 and set_sheets[0][0] == case.constants['swExportData_ExportSpecifiedSheets']
    assert tuple(getattr(set_sheets[0][1], 'value', set_sheets[0][1])) == (plan.name,)
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


@pytest.mark.parametrize('owned,warning,expected', [
    (True, 32, 'rebuilt'),          # opened here, SolidWorks asked for a regeneration on load
    (False, 32, 'refused'),         # the user's own open document is never rebuilt here
    (True, 0, 'refused')])          # opened here, but no load request: a stale saved model
def test_a_rebuild_requested_on_load_is_done_only_for_a_read_only_document_opened_here(owned, warning, expected):
    # Recorded on SolidWorks 2025 SP5 ('rebuild assembly on load: always'): a fully rebuilt and
    # saved assembly reopens with load warning 32 and NeedsRebuild2 = 1.
    state = {'pending': 1, 'dirty': False}
    def rebuild(top_only):
        state.update(pending=0, dirty=True); return True
    extension = RawDispatch('IModelDocExtension', properties={'NeedsRebuild2': lambda: state['pending']})
    model = RawDispatch('IModelDoc2', methods={'GetSaveFlag': lambda: state['dirty'],
        'GetPathName': lambda: 'C:/A.SLDASM', 'ForceRebuild3': rebuild}, properties={'Extension': extension})
    session = Session()
    session.constants = {'swFileLoadWarning_NeedsRegen': 32, 'swModelRebuildStatus_FullyRebuilt': 0,
                         'swModelRebuildStatus_NonFrozenFeatureNeedsRebuild': 1}
    from modules.cad_converter.api import path_key
    session.owned = {path_key('C:/A.SLDASM'): 'A.SLDASM'} if owned else {}
    session.load_warnings = {path_key('C:/A.SLDASM'): warning}
    if expected == 'rebuilt':
        session.source_ready(model)
        assert state == {'pending': 0, 'dirty': True}
    else:
        with pytest.raises(ApiError, match='yeniden oluşturulmalı'):
            session.source_ready(model)
        assert not any(name == 'ForceRebuild3' for name, flags, args in model.calls)


def annotated_views(case, existing):
    """Views whose annotation chain holds ``existing`` center marks (swCenterMarkSym) and a note."""
    case.constants.update(swAutoInsertCenterMarkType_Hole=1, swCenterMarkSym=13)
    def chain_of(chain):
        def annotation(index):
            if index >= len(chain):
                return None
            return RawDispatch('IAnnotation', methods={'GetType': lambda: chain[index],
                                                       'GetNext3': lambda: annotation(index+1)})
        def insert(*args):
            chain.extend([13]*4); return True        # SolidWorks returns True and appends 4 marks
        return dict(GetFirstAnnotation3=lambda: annotation(0), AutoInsertCenterMarks2=insert,
                    GetCenterMarkCount2=lambda size: 0)    # recorded: 0 even with marks present
    for view in case.views.values():
        view.methods.update(chain_of([6] + [13]*existing))   # 6: a note, never counted


def test_center_marks_are_inserted_on_iview_with_ten_arguments_and_counted_as_annotations(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    annotated_views(case, existing=0)
    case.native.center_marks(plan.name)
    calls = [(view.name, args) for view in case.views.values() for name, flags, args in view.calls
             if name == 'AutoInsertCenterMarks2']
    assert len(calls) == 3 and all(owner == 'IView' and len(args) == 10 for owner, args in calls)
    assert case.result.measurements['center_marks'][plan.name] == 12


def test_center_marks_already_inserted_with_the_view_are_not_duplicated(case):
    # Recorded on SolidWorks 2025 SP5: the document option inserts hole center marks when the
    # view is created; a further AutoInsertCenterMarks2 stacked a duplicate on every hole.
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    annotated_views(case, existing=5)
    case.native.center_marks(plan.name)
    assert not [name for view in case.views.values() for name, flags, args in view.calls
                if name == 'AutoInsertCenterMarks2']
    assert case.result.measurements['center_marks'][plan.name] == 15


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
    sheet_view = RawDispatch('IView-sheet', methods={'GetNextView': lambda: ordered[0],
                                                     'GetTableAnnotations': lambda: None})
    case.drawing.methods['GetFirstView'] = lambda: sheet_view
    case.drawing.methods['GetSheetNames'] = lambda: (case.state['name'],)
    if extra:
        with pytest.raises(ApiError, match='ek görünüş'):
            case.native.verify_saved('fake.SLDDRW', snapshots)
    else:
        new_findings, reread = case.native.verify_saved('fake.SLDDRW', snapshots)
        assert not new_findings and len(reread[0]['views']) == 4
    assert len(closed) == 2  # initial close, then the separately reopened checker


def test_saved_bom_listed_under_the_sheet_entry_is_found_on_reopen(case):
    # Recorded on SolidWorks 2025 SP5: after save/reopen the BOM inserted on a model view is
    # returned by the SHEET entry's GetTableAnnotations, and by no model view.
    from modules.automatic_drawing.manufacturing import table_box
    from modules.automatic_drawing.models import to_m
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    findings, snapshots = case.native.validate()
    usable = snapshots[0]['usable']
    case.constants.update(swTableAnnotation_BillOfMaterials=7, swColumnTypeStatus_Success=0,
                          swBomTableColumnType_Quantity=203)
    annotation = RawDispatch('IAnnotation', methods={'GetPosition': lambda: (to_m(usable.x+1), to_m(usable.top-1), 0.),
                                                     'GetName': lambda: 'BOM'})
    table = RawDispatch('ITableAnnotation', methods={'GetAnnotation': lambda: annotation,
        'GetColumnWidth': lambda i: .01, 'GetRowHeight': lambda i: .003, 'GetColumnType3': lambda *args: 0},
        properties={'Type': 7, 'RowCount': 2, 'ColumnCount': 1})
    case.native.pages[plan.name]['tables'].append(table_box(table))
    case.session.named_interface = lambda obj, name: obj
    case.session.close_created = lambda model: None
    case.session.open_drawing = lambda path: (case.model, case.drawing)
    case.native.close()
    ordered = list(case.views.values())
    for index, view in enumerate(ordered):
        view.methods['GetNextView'] = lambda index=index: ordered[index+1] if index+1 < len(ordered) else None
    sheet_view = RawDispatch('IView-sheet', methods={'GetNextView': lambda: ordered[0],
                                                     'GetTableAnnotations': lambda: (table,)})
    case.drawing.methods['GetFirstView'] = lambda: sheet_view
    case.drawing.methods['GetSheetNames'] = lambda: (case.state['name'],)
    new_findings, reread = case.native.verify_saved('fake.SLDDRW', snapshots)
    assert not [f for f in new_findings if f.severity == 'FAIL']


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


def test_isometric_with_its_own_scale_leaves_the_sheet_scale_and_reads_back(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    plan.view_scales = {'isometric': plan.scale/2}
    create = case.drawing.methods['CreateDrawViewFromModelView3']
    def with_ratio(path, model_view, *args):
        view = create(path, model_view, *args)
        view.properties.setdefault('ScaleRatio', (1., 1.))
        return view
    case.drawing.methods['CreateDrawViewFromModelView3'] = with_ratio
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    views = case.native.pages[plan.name]['views']
    iso = views['isometric']
    assert iso.properties['UseSheetScale'] == 0
    ratio = iso.properties['ScaleRatio']; assert ratio[0]/ratio[1] == pytest.approx(plan.scale/2)
    assert all(views[r].properties['UseSheetScale'] == 1 for r in ('main', 'top', 'side'))
    assert case.native.sheet_state(plan.name)['scale'] == pytest.approx(plan.scale)
    assert not [f for f in case.result.findings if f.code == 'view_scale']


def test_rejected_view_scale_falls_back_to_the_sheet_scale_with_a_warning(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    plan.view_scales = {'isometric': plan.scale/2}          # the mock view has no ScaleRatio: SolidWorks refuses
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    iso = case.native.pages[plan.name]['views']['isometric']
    assert iso.properties['UseSheetScale'] == 1 and plan.view_scales == {}
    assert [f.severity for f in case.result.findings if f.code == 'view_scale'] == ['WARNING']


def test_sheet_scale_is_sent_as_the_whole_number_ratio_solidworks_stores():
    from modules.automatic_drawing.native import scale_ratio
    assert scale_ratio(.5) == (1., 2.) and scale_ratio(.4) == (2., 5.) and scale_ratio(2.5) == (5., 2.)
    assert scale_ratio(1.) == (1., 1.) and scale_ratio(.02) == (1., 50.)


def test_whole_number_ratio_reaches_setupsheet6_and_setscale(case):
    refuse_template_sheet(case)
    options = replace(case.options, manual_scale=.4); case.native.options = options
    plan = plan_sheet(plan_views(case.info, options), options)
    case.native.create('fake.drwdot', plan)
    setup = next(args for name, flags, args in case.drawing.calls if name == 'SetupSheet6')
    assert setup[3:5] == (2., 5.)
    case.native.set_scale(plan.name, .5)
    assert case.native.sheet_state(plan.name)['scale'] == .5
    assert case.state['props'][2:4] == [1., 2.]


def test_a_refused_sheet_setup_tries_the_next_combination_and_reports_it(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    accept = case.drawing.methods['SetupSheet6']; seen = []
    def refuse_empty_view_name(*args):
        seen.append(args[9])
        return accept(*args) if args[9] == 'Default' else False
    case.drawing.methods['SetupSheet6'] = refuse_empty_view_name
    case.native.create('fake.drwdot', plan)
    assert seen == ['', 'Default']
    assert case.result.measurements['sheet_setup'] == {plan.name: 'default_view'}
    assert [f.code for f in case.result.findings if f.severity == 'WARNING'].count('sheet_setup') == 1


def test_a_sheet_setup_refused_every_way_names_the_refused_values(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.drawing.methods['SetupSheet6'] = lambda *args: False
    with pytest.raises(ApiError, match=r'reddedildi\. Pafta "Genel görünüşler", 420 × 297 mm, ölçek \d+:\d+, 1\. açı'):
        case.native.create('fake.drwdot', plan)


def localized(case, names, accepted):
    """SolidWorks in another UI language: only `accepted` standard view names exist."""
    create = case.drawing.methods['CreateDrawViewFromModelView3']
    case.drawing.methods['CreateDrawViewFromModelView3'] = (
        lambda path, name, *args: create(path, name, *args) if name in accepted else None)
    model = RawDispatch('IModelDoc2', methods={'GetModelViewNames': lambda: tuple(names)})
    case.app.methods['GetOpenDocumentByName'] = lambda path: model


def test_turkish_standard_view_names_are_used_when_the_english_name_is_refused(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    localized(case, ('*Ön', '*Arka', '*Sol', '*Sağ', '*Üst', '*Alt', '*İzometrik'), {'*Ön', '*İzometrik'})
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    assert set(case.native.pages[plan.name]['views']) == {v.role for v in plan.views}
    assert case.result.measurements['model_view_names'] == {'*Front': '*Ön', '*Isometric': '*İzometrik'}


def test_any_language_falls_back_to_the_models_standard_view_order(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    german = ('*Vorderseite', '*Rückseite', '*Links', '*Rechts', '*Oben', '*Unten', '*Isometrisch', 'Benutzer 1')
    localized(case, german, {'*Vorderseite', '*Isometrisch'})
    case.native.create('fake.drwdot', plan); case.native.create_views(plan)
    assert case.result.measurements['model_view_names'] == {'*Front': '*Vorderseite', '*Isometric': '*Isometrisch'}


def test_an_unknown_view_name_reports_the_models_view_names(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    localized(case, ('*A', '*B'), set())
    case.native.create('fake.drwdot', plan)
    with pytest.raises(ApiError, match=r'main \(\*Front\)\. Modelin görünüş adları: \*A, \*B\.'):
        case.native.create_views(plan)


def test_sheet_format_is_kept_at_its_own_size_only_when_that_is_the_planned_paper(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.sheet.methods['GetTemplateName'] = lambda: 'C:/formats/a3 - iso.slddrt'
    accept = case.drawing.methods['SetupSheet6']; widths = []
    def custom_size_refused(*args):
        widths.append(args[7])
        if args[6] and args[7]:
            return False                       # a format with a forced size is refused
        accept(*args)
        if not args[7]:                        # the format keeps its own (A3) size
            case.state['props'][5:7] = [.420, .297]
        return True
    case.drawing.methods['SetupSheet6'] = custom_size_refused
    case.native.create('fake.drwdot', plan)
    assert case.result.measurements['sheet_setup'] == {plan.name: 'format_size'}
    assert case.native.pages[plan.name]['format'] == 'C:/formats/a3 - iso.slddrt'


def test_a_sheet_format_of_another_size_falls_back_to_no_format_and_names_it(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.sheet.methods['GetTemplateName'] = lambda: 'C:/formats/a4 - iso.slddrt'
    accept = case.drawing.methods['SetupSheet6']
    def a4_format(*args):
        if args[6] and args[7]:
            return False
        accept(*args)
        case.state['props'][5:7] = [.297, .210] if args[6] else [args[7], args[8]]
        return True
    case.drawing.methods['SetupSheet6'] = a4_format
    case.native.create('fake.drwdot', plan)
    assert case.result.measurements['sheet_setup'] == {plan.name: 'no_format'}
    assert any('a4 - iso.slddrt' in f.text for f in case.result.findings if f.code == 'sheet_setup')


def test_a_template_without_sheet_format_is_set_up_without_a_refused_first_attempt(case):
    refuse_template_sheet(case)
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.sheet.methods['GetTemplateName'] = lambda: '*.drt'       # SolidWorks: no sheet format
    accept = case.drawing.methods['SetupSheet6']; sent = []
    def setup(*args):
        sent.append(args[6]); return accept(*args) if not args[6] else False
    case.drawing.methods['SetupSheet6'] = setup
    case.native.create('fake.drwdot', plan)
    assert sent == [''] and case.result.measurements['sheet_setup'] == {plan.name: 'standard'}
    assert not [f for f in case.result.findings if f.code == 'sheet_setup']


def test_standard_sheet_format_is_found_in_the_installation_when_the_setting_names_a_removed_release(tmp_path, monkeypatch):
    # Recorded on SolidWorks 2025 SP5 (Turkish): swFileLocationsSheetFormat named
    # '...\SOLIDWORKS 2024\lang\turkish\sheetformat' (absent); the formats were under 2025.
    monkeypatch.setenv('ProgramData', str(tmp_path/'ProgramData'))     # no real installation is consulted
    release = tmp_path/'SOLIDWORKS 2025'
    template = release/'templates'/'Teknik Resim.drwdot'
    formats = release/'lang'/'turkish'/'sheetformat'
    formats.mkdir(parents=True); template.parent.mkdir(parents=True); template.write_bytes(b'x')
    (formats/'a3 - iso.slddrt').write_bytes(b'x')
    app = RawDispatch('ISldWorks', methods={
        'GetUserPreferenceStringValue': lambda key: str(tmp_path/'SOLIDWORKS 2024'/'lang'/'turkish'/'sheetformat'),
        'GetCurrentLanguage': lambda: 'turkish'})
    session = object.__new__(Session)
    session.app, session.constants, session.revision = app, {'swFileLocationsSheetFormat': 1}, '33.5.0'
    assert session.standard_sheet_format('A3', str(template)) == str(formats/'a3 - iso.slddrt')
    assert session.standard_sheet_format('A2', str(template)) == ''
    assert session.standard_sheet_format('custom', str(template)) == ''


def test_a_template_without_sheet_format_gets_the_installed_iso_format_of_its_paper(case):
    plan = plan_sheet(plan_views(case.info, case.options), case.options)
    case.sheet.methods['GetTemplateName'] = lambda: '*.drt'       # recorded for 'Teknik Resim.drwdot'
    standard = r'C:\ProgramData\SolidWorks\SOLIDWORKS 2025\lang\turkish\sheetformat\a3 - iso.slddrt'
    case.session.standard_sheet_format = lambda paper, template: standard if paper == 'A3' else ''
    case.native.create('C:/templates/Teknik Resim.drwdot', plan)
    setup = next(args for name, flags, args in case.drawing.calls if name == 'SetupSheet6')
    assert setup[2] == case.constants['swDwgTemplateCustom'] and setup[6] == standard
    assert case.result.measurements['sheet_format_file'] == {plan.name: standard}
    assert case.result.measurements['sheet_setup'] == {plan.name: 'standard'}
    assert case.native.pages[plan.name]['format'] == standard
