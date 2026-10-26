"""Exercise real preview adapter/ownership/restore logic with a mock COM server."""

from dataclasses import replace
from pathlib import Path
import threading
from types import SimpleNamespace as NS

import pytest

from modules.cad_converter import api
from modules.cad_converter.tests.fakes import App, C
from modules.dxf_dwg.preview import solidworks as sw
from modules.dxf_dwg.preview.models import Request, MeshCache
from modules.cad_converter.models import Cancelled
from .test_preview_geometry import flat_file


@pytest.fixture
def source(tmp_path, monkeypatch):
    app = App(); model = app.add(tmp_path/'Part.SLDPRT', ('Bent', 'Flat'), opened=True)
    previous = app.add(tmp_path/'Other.SLDPRT', opened=True); app.ActiveDoc = previous
    model.GetUpdateStamp = lambda: 10
    model.GetSaveFlag = lambda: False
    model.GetBendState = lambda: 2 if model.active == 'Flat' else 3
    model.GetConfigurationByName = lambda name: NS(Name=name, IsDerived=lambda: name == 'Flat', GetParent=lambda: NS(Name='Bent'))
    body = NS(IsSheetMetal=lambda: True, GetFaces=lambda: (NS(GetTessTriangles=lambda no_conversion:
        (0, 0, 0, .01, 0, 0, 0, .02, 0)),))
    model.GetBodies2 = lambda *args: (body,)
    model.FirstFeature = lambda: None
    model.Extension.GetPersistReference3 = lambda obj: b'body-A' if obj is body else b'other'
    monkeypatch.setattr(api, 'interface', lambda obj, iid: obj)
    monkeypatch.setattr(sw, 'interface', lambda obj, iid: obj)
    monkeypatch.setattr(api, 'out_int', lambda: NS(value=0))
    constants = dict(C, swSMBendStateNone=0, swSMBendStateSharps=1, swSMBendStateFlattened=2,
                     swSMBendStateFolded=3, swModelRebuildStatus_FullyRebuilt=0, swThisConfiguration=1)
    class Session(sw.Session):
        def __enter__(self):
            self.app, self.constants = app, constants
            self.owned, self.load_warnings, self.previous = {}, {}, previous.path
            self.pythoncom = NS(CoUninitialize=lambda: None)
            return self
    output = flat_file(tmp_path/'part.dxf')
    request = Request(model.path, 'Bent', output=str(output), output_status='success', quantity=5)
    return app, model, previous, body, request, Session


def capture(source, request=None, cache=None, stop=None):
    return sw.capture(request or source[4], cache or MeshCache(), stop, session_factory=source[5])


def test_exact_document_not_active_doc_is_meshed_and_sources_unchanged(source):
    app, model, previous, _, _, _ = source
    before = Path(model.path).read_bytes()
    result = capture(source)
    assert result.source == model.path and result.configuration == 'Bent' and result.mesh.triangles == 1
    assert dict(result.info)['Adet'] == '5' and result.flat
    assert app.ActiveDoc is previous and model.opened and not app.closed
    assert Path(model.path).read_bytes() == before and not app.saves


def test_requested_config_and_flat_derived_parent_are_restored(source):
    app, model, previous, body, request, _ = source
    model.active = 'Flat'
    result = capture(source, replace(request, configuration='Flat'))
    assert result.configuration == 'Bent' and model.active == 'Flat'
    assert app.ActiveDoc is previous and not app.saves
    assert any('üst konfigürasyonu' in w for w in result.warnings)


def test_unrelated_flat_config_is_not_guessed_from_its_name(source):
    _, model, _, _, request, _ = source
    model.active = 'Flat'; model.GetConfigurationByName = lambda n: NS(IsDerived=lambda: False)
    with pytest.raises(api.ApiError, match='açınım halinde'):
        capture(source, replace(request, configuration='Flat'))
    assert model.active == 'Flat'


def test_revision_cache_hits_only_after_live_source_config_body_validation(source):
    _, model, _, body, _, _ = source; calls = []
    face = NS(GetTessTriangles=lambda *args: calls.append(True) or (0, 0, 0, .01, 0, 0, 0, .02, 0))
    body.GetFaces = lambda: (face,)
    cache = MeshCache()
    assert not capture(source, cache=cache).cached
    assert capture(source, cache=cache).cached and len(calls) == 1
    model.GetUpdateStamp = lambda: 11
    assert not capture(source, cache=cache).cached and len(calls) == 2


def test_wrong_document_returned_by_sw_is_rejected(source):
    app, model, previous, _, _, _ = source
    app.GetOpenDocumentByName = lambda p: previous
    with pytest.raises(api.ApiError, match='başka bir belge'):
        capture(source)
    assert app.ActiveDoc is previous


@pytest.mark.parametrize('fault', ['not_sheet', 'empty_faces', 'empty_triangles', 'missing_body', 'multi_body'])
def test_no_fake_or_partial_mesh_for_unverified_source(source, fault):
    _, model, _, body, request, _ = source
    if fault == 'not_sheet': body.IsSheetMetal = lambda: False
    if fault == 'empty_faces': body.GetFaces = lambda: ()
    if fault == 'empty_triangles': body.GetFaces = lambda: (NS(GetTessTriangles=lambda _: ()),)
    if fault == 'missing_body': request = replace(request, body_ref='persist:missing')
    if fault == 'multi_body': model.GetBodies2 = lambda *args: (body, NS(IsSheetMetal=lambda: True))
    with pytest.raises(api.ApiError): capture(source, request)


def test_explicit_persistent_reference_can_select_only_the_matching_body(source):
    _, model, _, body, request, _ = source
    model.GetBodies2 = lambda *args: (NS(IsSheetMetal=lambda: True), body)
    request = replace(request, body_ref='persist:Ym9keS1B')
    assert capture(source, request).mesh.triangles == 1


def test_change_during_mesh_read_prevents_publication_and_restores_session(source):
    app, model, previous, body, _, _ = source
    def changed(*args):
        model.GetUpdateStamp = lambda: 11
        return (0, 0, 0, .01, 0, 0, 0, .02, 0)
    body.GetFaces = lambda: (NS(GetTessTriangles=changed),)
    with pytest.raises(api.ApiError, match='sırasında değişti'): capture(source)
    assert app.ActiveDoc is previous and not app.saves


def test_cancel_restores_session_without_save(source):
    stop = threading.Event(); stop.set()
    with pytest.raises(Cancelled): capture(source, stop=stop)
    assert not source[0].saves and source[0].ActiveDoc is source[2]


def test_native_dwg_preview_uses_disposable_dxf_and_keeps_original_outputs(source, monkeypatch, tmp_path):
    app, model, previous, _, request, _ = source
    dwg = tmp_path/'part.dwg'; dwg.write_bytes(b'original DWG'); temporary_paths = []
    def export(app_arg, path, targets, **kwargs):
        assert path == model.path and app_arg is app and model.active == 'Bent'
        temporary_paths.extend(targets); flat_file(targets[0]); return 'success', ''
    monkeypatch.setattr(sw.exporter, 'export_one_part', export)
    result = capture(source, replace(request, output=str(dwg)))
    assert 'DWG dosyası okunmadı' in result.flat.description
    assert temporary_paths and not Path(temporary_paths[0]).exists()
    assert dwg.read_bytes() == b'original DWG' and app.ActiveDoc is previous


@pytest.mark.parametrize('output_kind', ['', 'dwg'])
def test_raw_com_session_reaches_real_export_path_for_flat_preview(source, monkeypatch, tmp_path, output_kind):
    """Do not mock export_one_part: cross its raw-to-late-bound COM boundary."""
    from support.solidworks import com_stubs
    app, model, previous, _, request, session_type = source
    model.Visible = False
    exported = []
    def export_to_dwg(path, *args):
        exported.append(Path(path))
        flat_file(path)
        return True
    model.ExportToDWG2 = export_to_dwg
    class RawDispatch:
        # A raw PyIDispatch exposes these methods, not ActiveDoc as an attribute.
        def GetIDsOfNames(self, lcid, name): return name
        def Invoke(self, name, lcid, flags, want_result, *args):
            value = getattr(app, name)
            return value(*args) if flags == 1 else value
    raw = RawDispatch()
    wrapped = []
    com, client = com_stubs('dxf')
    def dumb_dispatch(value):
        assert value is raw
        wrapped.append(value)
        return app
    client.dynamic = NS(DumbDispatch=dumb_dispatch)
    monkeypatch.setattr(sw.exporter, 'pythoncom', com)
    monkeypatch.setattr(sw.exporter, 'win32com', NS(client=client))
    class RawSession(session_type):
        def __enter__(self):
            super().__enter__()
            self.app = raw
            return self
    original = tmp_path/'original.dwg'
    original.write_bytes(b'Existing production drawing')
    request = replace(request, output=str(original) if output_kind else '')
    result = sw.capture(request, MeshCache(), session_factory=RawSession)
    assert result.flat and result.flat.strokes and result.mesh.triangles == 1
    assert not any('okunamadı:' in warning for warning in result.warnings)
    assert wrapped == [raw] and exported and all(not path.exists() for path in exported)
    assert original.read_bytes() == b'Existing production drawing'
    assert app.ActiveDoc is previous and not app.closed and not app.saves
    assert model.active == 'Bent' and model.Visible is False


def test_broken_flat_does_not_hide_valid_3d_and_is_reported(source, tmp_path):
    output = tmp_path/'broken.dxf'; output.write_text('not a DXF')
    result = capture(source, replace(source[4], output=str(output)))
    assert result.mesh.triangles == 1 and result.flat is None
    assert any('Açınım önizlemesi okunamadı' in w for w in result.warnings)


def test_rebuild_or_unknown_revision_is_not_silently_shown_as_current(source):
    source[1].Extension.NeedsRebuild2 = 1
    with pytest.raises(api.ApiError, match='güncelliği'): capture(source)


def test_private_tessellation_fallback_when_display_triangles_do_not_exist(source, monkeypatch):
    app, model, _, body, _, _ = source
    body.GetFaces = lambda: ()
    points = ((0., 0., 0.), (.01, 0., 0.), (0., .02, 0.))
    tess = NS(NeedVertexNormal=True, ImprovedQuality=True, Tessellate=lambda: True,
              GetFacetCount=lambda: 1, GetFacetFins=lambda i: (0, 1, 2),
              GetFinVertices=lambda i: ((0, 1), (1, 2), (2, 0))[i],
              GetVertexPoint=lambda i: points[i])
    body.GetTessellation = lambda faces: tess if faces is None else None
    def put(obj, name, flags, value):
        assert flags == 4; setattr(obj, name, value)
    monkeypatch.setattr(sw, 'invoke', put)
    result = capture(source)
    assert result.mesh.triangles == 1 and tess.NeedVertexNormal is False and tess.ImprovedQuality is False
    assert not app.saves


def test_only_preview_owned_document_is_closed_and_opened_readonly(source):
    app, model, previous, _, _, _ = source
    model.opened = False; options = []; original = app.OpenDoc6
    def opened(path, kind, flags, configuration, errors, warnings):
        options.append(flags)
        return original(path, kind, flags, configuration, errors, warnings)
    app.OpenDoc6 = opened
    capture(source)
    assert options[0] & C['swOpenDocOptions_ReadOnly']
    assert app.closed == [Path(model.path).name] and previous.opened and app.ActiveDoc is previous


def test_stale_export_is_regenerated_for_preview_without_replacing_output(source, monkeypatch):
    _, model, _, _, request, _ = source
    before = Path(request.output).read_bytes()
    generated = []
    def export(app, path, targets, **kwargs):
        generated.extend(targets); flat_file(targets[0]); return 'success', ''
    monkeypatch.setattr(sw.exporter, 'export_one_part', export)
    result = capture(source, replace(request, update_stamp=9))
    assert generated and any('çıktıdan sonra değişmiş' in w for w in result.warnings)
    assert Path(request.output).read_bytes() == before and not Path(generated[0]).exists()


def test_configuration_restore_failure_is_never_reported_as_preview_success(source):
    _, model, _, _, request, _ = source
    model.active = 'Flat'
    original = model.ShowConfiguration2
    model.ShowConfiguration2 = lambda name: False if name == 'Flat' else original(name)
    with pytest.raises(api.RestoreError): capture(source, replace(request, configuration='Bent'))


def test_missing_source_has_actionable_message_and_never_opens_cad(source):
    app, model, _, _, _, _ = source
    Path(model.path).unlink()
    with pytest.raises(api.ApiError, match='Kaynak parça bulunamadı'):
        capture(source)
    assert not app.open_calls and not app.saves
