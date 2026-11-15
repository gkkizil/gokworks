"""Offline manufacturing contracts; no simulated output is a CAD acceptance test."""

from threading import Event
from types import SimpleNamespace

import pytest

from modules.cad_converter.api import ApiError, RestoreError
from modules.automatic_drawing.models import DrawingResult, ModelInfo, Node, Options, Source
from modules.automatic_drawing.manufacturing import bom_page, flat_page
from .test_native_boundary import RawDispatch


@pytest.mark.parametrize('bodies,flat_configs', ((3, ('DefaultSM-FLAT-PATTERN',)), (1, ())))
def test_multibody_or_missing_existing_flat_is_reported_without_modifying_source(bodies, flat_configs):
    source = Source('C:/sheet.sldprt', 'Default')
    info = ModelInfo(source, 'part', 'Sheet', (100, 50, 20), body_count=bodies,
                     sheet_body_count=bodies, flat_configurations=flat_configs)
    result = DrawingResult(source)
    native = SimpleNamespace(info=info, options=Options(), result=result)
    model = RawDispatch('IModelDoc2')
    flat_page(native, model)
    assert result.findings and not model.calls
    assert result.findings[0].code in ('multibody_flat', 'flat_configuration')


def test_native_flat_requires_correct_parent_and_detects_unexpected_configuration_creation():
    source = Source('C:/sheet.sldprt', 'Default')
    flat = 'DefaultSM-FLAT-PATTERN'
    info = ModelInfo(source, 'part', 'Sheet', (100, 50, 20), body_count=1,
                     sheet_body_count=1, flat_configurations=(flat,))
    calls = []
    parent = RawDispatch('IConfiguration', properties={'Name': 'Default'})
    config = RawDispatch('IConfiguration', methods={'GetParent': lambda: parent})
    def configurations():
        calls.append('read')
        return ('Default', flat) if len(calls) == 1 else ('Default', flat, 'unexpected-new-config')
    model = RawDispatch('IModelDoc2', methods={'GetConfigurationByName': lambda name: config,
                                             'GetConfigurationNames': configurations})
    view = RawDispatch('IView', methods={'IsFlatPatternView': lambda: True},
                       properties={'ReferencedConfiguration': flat, 'UseSheetScale': False})
    drawing = RawDispatch('IDrawingDoc', methods={'CreateFlatPatternViewFromModelView3': lambda *args: view})
    pages = {}
    native = SimpleNamespace(info=info, options=Options(), result=DrawingResult(source), drawing=drawing,
        pages=pages, setup=lambda plan, new=False: pages.update({plan.name: {'views': {}}}),
        set_scale=lambda *args: None, fit=lambda *args: None)
    with pytest.raises(RestoreError, match='yeni bir konfigürasyon'):
        flat_page(native, model)
    assert not any('Save' in name or 'Suppress' in name for name, flags, args in model.calls)


def bom_case(mode='parts', quantity=12, returned_components=12, display=None):
    source, part = Source('C:/assembly.sldasm', 'Default'), Source('C:/screw.sldprt', 'M8')
    root = Node('Assembly', source, 'assembly',
                children=[Node(f'Bolt-{i}', part) for i in range(12)])
    info = ModelInfo(source, 'assembly', 'Assembly', (100, 50, 20), tree=root)
    options = Options(bom_type=mode, model_dimensions=False, center_marks=False, flat_pattern=False)
    result = DrawingResult(source)
    constants = {name: i+1 for i, name in enumerate(('swBomType_PartsOnly', 'swBomType_TopLevelOnly',
        'swBomType_Indented', 'swBOMConfigurationAnchor_TopLeft', 'swNumberingType_Detailed',
        'swNumberingType_None'))}
    constants.update(swColumnTypeStatus_Success=0, swBomTableColumnType_Quantity=203)
    feature = RawDispatch('IBomFeature', methods={'SetConfigurations': lambda *args: True},
                          properties={'Configuration': 'Default'})
    annotation = RawDispatch('IAnnotation', methods={'GetPosition': lambda: (.010, .287, 0)})
    generic = RawDispatch('ITableAnnotation', methods={'GetAnnotation': lambda: annotation,
        'GetColumnWidth': lambda index: .020, 'GetRowHeight': lambda index: .006,
        'GetColumnType3': lambda index, hidden, data, status: 203 if index == 3 else 0},
        properties={'RowCount': 2, 'ColumnCount': 4,
                    'DisplayedText2': lambda row, col, hidden: str(quantity) if display is None else display})
    component = RawDispatch('IComponent2', methods={'GetPathName': lambda: part.path},
                            properties={'ReferencedConfiguration': part.configuration})
    def counts(row, configuration, item, part_number):
        if row == 0:
            return 0
        item.value, part_number.value = '1', 'SCREW-M8'
        return quantity
    bom = RawDispatch('IBomTableAnnotation', methods={'GetComponentsCount2': counts,
        'GetComponents2': lambda *args: [component]*returned_components}, properties={'BomFeature': feature})
    view = RawDispatch('IView', methods={'InsertBomTable4': lambda *args: bom})
    pages = {}
    session = SimpleNamespace(c=lambda key: constants[key], named_interface=lambda obj, name: generic)
    def setup(plan, new=False):
        pages[plan.name] = {'plan': plan, 'views': {'main': view}, 'tables': []}
    native = SimpleNamespace(info=info, options=options, result=result, session=session,
        pages=pages, stop=Event(), setup=setup, create_views=lambda plan: None,
        fit=lambda name: None, rebuild=lambda: None)
    return native, view, feature


@pytest.mark.parametrize('mode', ('parts', 'top'))
@pytest.mark.parametrize('returned', (1, 12))
def test_native_bom_has_ten_arguments_and_proves_twelve_repeated_components(mode, returned):
    native, view, feature = bom_case(mode, returned_components=returned)
    bom_page(native)
    args = next(args for name, flags, args in view.calls if name == 'InsertBomTable4')
    assert len(args) == 10
    assert args[5] == ('' if mode == 'top' else 'Default')
    assert native.result.measurements['bom']['quantities_verified'] is True
    assert native.result.measurements['bom']['rows'][0]['quantity'] == 12
    if mode == 'top':
        assert any(name == 'SetConfigurations' for name, flags, args in feature.calls)


def test_mismatched_bom_quantity_is_a_critical_failure_not_a_warning_or_pass():
    native, view, feature = bom_case(quantity=11, returned_components=11)
    with pytest.raises(ApiError, match='adetleri'):
        bom_page(native)


def test_indented_bom_does_not_claim_unverified_quantity_equivalence():
    native, view, feature = bom_case('indented')
    bom_page(native)
    assert native.result.measurements['bom']['quantities_verified'] is False
    assert any(f.code == 'indented_bom' for f in native.result.findings)


def test_bom_quantity_override_cannot_pass_just_because_component_counts_match():
    native, view, feature = bom_case(display='25')
    with pytest.raises(ApiError, match='görünen adet'):
        bom_page(native)


def test_custom_bom_quantity_units_are_not_treated_as_verified_instance_counts():
    native, view, feature = bom_case(display='12 m')
    bom_page(native)
    assert native.result.measurements['bom']['quantities_verified'] is False
    assert native.result.measurements['bom']['rows'][0]['quantity'] is None


def test_ambiguous_thousands_or_decimal_format_does_not_certify_twelve_thousand_as_twelve():
    native, view, feature = bom_case(display='12,000')
    bom_page(native)
    assert native.result.measurements['bom']['quantities_verified'] is False
