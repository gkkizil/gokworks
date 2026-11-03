"""Count native work and exercise invalidation, without a licensed SW server."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import threading

import pytest

from modules.cad_converter.api import ApiError, RestoreError
from modules.cad_converter.models import Cancelled
from modules.dxf_dwg.preview import solidworks as sw
from modules.dxf_dwg.preview.models import Request, MeshCache
from modules.dxf_dwg.sheetmetal import scan_inventory
from .sheet_fakes import environment, part


@pytest.fixture
def native(tmp_path, monkeypatch):
    app, Base, _ = environment(monkeypatch)
    model = part(app, tmp_path/'Multi.SLDPRT', count=24)
    model.GetBendState = lambda: 3
    model.GetSaveFlag = lambda: False
    app.ActiveDoc = model
    with Base() as session:
        rows, _ = scan_inventory(session)
    monkeypatch.setattr(sw, 'interface', lambda obj, iid: obj)
    calls = Counter()

    class Session(sw.Session):
        def __enter__(self):
            calls['sessions'] += 1
            Base.__enter__(self)
            self.constants.update(swSMBendStateNone=0, swSMBendStateSharps=1,
                                  swSMBendStateFlattened=2, swSMBendStateFolded=3)
            return self

        def metadata(self, *args, **kwargs):
            calls['metadata'] += 1
            return super().metadata(*args, **kwargs)

        def features(self, *args, **kwargs):
            calls['tree_walks'] += 1
            yield from super().features(*args, **kwargs)

        def cut_folders(self, *args, **kwargs):
            calls['cut_list_walks'] += 1
            yield from super().cut_folders(*args, **kwargs)

        def triangles(self, *args, **kwargs):
            calls['tessellations'] += 1
            return super().triangles(*args, **kwargs)

    def request(index=-1, **changes):
        row = rows[index]
        return replace(Request(row['source'], row['configuration'], row['body_ref'],
                               source_stamp=tuple(row['source_stamp']), update_stamp=row['update_stamp'],
                               flat_ref=row['flat_ref'], flat_pattern=row['flat_pattern'], cut_list=row['cut_list']),
                       **changes)

    def capture(req=None, cache=None, **kwargs):
        return sw.capture(req or request(), cache or MeshCache(), session_factory=Session, **kwargs)

    return app, model, calls, request, capture, Session


def test_one_native_read_and_no_global_tree_walk_for_known_multibody(native):
    app, model, calls, _, capture, _ = native
    before = Path(model.path).read_bytes()
    result = capture()
    assert result.flat.bounds == (0, 0, 240, 20)
    assert dict(result.info)['Sac kalınlığı'] == '24 mm'
    assert calls == dict(sessions=1, metadata=1, tessellations=1)
    assert len(model.export_calls) == 1
    assert model.selection == ['user selection'] and app.ActiveDoc is model
    assert Path(model.path).read_bytes() == before and not app.saves
    timings = dict(result.timings)
    assert set(timings) == {'açınım', '3D', 'bilgiler', 'toplam'}
    assert timings['toplam'] >= sum(v for k, v in timings.items() if k != 'toplam') >= 0


@pytest.mark.parametrize('hint', ['missing', 'other_body'])
def test_wrong_feature_name_hints_fall_back_to_verified_persistent_identity(native, hint):
    _, _, calls, request, capture, _ = native
    other = request(0)
    req = request(flat_pattern=other.flat_pattern if hint == 'other_body' else 'renamed flat',
                  cut_list=other.cut_list if hint == 'other_body' else 'renamed folder')
    result = capture(req)
    assert result.flat.bounds == (0, 0, 240, 20)
    assert dict(result.info)['Cut List'] == request().cut_list
    assert dict(result.info)['Sac kalınlığı'] == '24 mm'
    assert calls['tree_walks'] == calls['cut_list_walks'] == 1


def test_flat_stage_precedes_mesh_and_metadata_but_follows_selection_restoration(native):
    _, model, calls, _, capture, _ = native
    stages = []

    def ready(flat):
        assert model.selection == ['user selection']
        assert not calls['tessellations'] and not calls['metadata']
        stages.append(flat)

    result = capture(on_flat=ready)
    assert stages == [result.flat]


def test_cancel_after_early_flat_never_publishes_or_caches_partial_capture(native):
    app, model, _, _, capture, _ = native
    stop, cache = threading.Event(), MeshCache()
    with pytest.raises(Cancelled):
        capture(cache=cache, stop=stop, on_flat=lambda flat: stop.set())
    assert not cache.items and not app.saves and model.selection == ['user selection']


def test_revision_change_after_early_flat_invalidates_entire_capture(native):
    _, model, _, _, capture, _ = native
    cache = MeshCache()
    def changed(flat):
        body = model.by_config['Default'][-1]
        original = body.GetFaces
        def faces():
            model.GetUpdateStamp = lambda: 11
            model.GetSaveFlag = lambda: True      # a real (unsaved) edit, not an internal recompute
            return original()
        body.GetFaces = faces
    with pytest.raises(ApiError, match='sırasında değişti'):
        capture(cache=cache, on_flat=changed)
    assert not cache.items


def test_live_flat_cache_reuses_geometry_but_refreshes_body_metadata(native):
    _, model, calls, request, capture, _ = native
    cache = MeshCache()
    first = capture(cache=cache)
    model.features_by_config['Default'][-2].CustomPropertyManager.values['MATERIAL'] = 'S355JR'
    second = capture(request(quantity=9), cache)
    assert len(model.export_calls) == calls['tessellations'] == 1
    assert calls['metadata'] == 2 and second.flat is first.flat and second.mesh is first.mesh
    assert dict(second.info)['Malzeme'] == 'S355JR' and dict(second.info)['Adet'] == '9'
    assert not calls['tree_walks'] and not calls['cut_list_walks']


@pytest.mark.parametrize('change', ['revision', 'file', 'body', 'bends', 'force', 'unknown_revision',
                                    'unsaved', 'unknown_save_state'])
def test_live_flat_cache_invalidates_on_each_geometry_input(native, change):
    _, model, _, request, capture, _ = native
    cache = MeshCache()
    first = capture(cache=cache)
    req = request()
    if change == 'revision': model.GetUpdateStamp = lambda: 11
    elif change == 'file': Path(model.path).write_bytes(b'changed source')
    elif change == 'body': req = request(0)
    elif change == 'bends': req = request(bend_lines=True)
    elif change == 'force': cache.clear()
    elif change == 'unknown_revision': model.GetUpdateStamp = lambda: None
    elif change == 'unsaved': model.GetSaveFlag = lambda: True
    elif change == 'unknown_save_state': model.GetSaveFlag = lambda: None
    second = capture(req, cache)
    assert len(model.export_calls) == 2 and second.flat is not first.flat
    if change == 'body': assert second.flat.bounds == (0, 0, 10, 20)
    if change == 'bends': assert any(s.bend for s in second.flat.strokes)


def test_cached_flat_still_rechecks_native_flat_ownership(native):
    _, model, _, _, capture, _ = native
    cache = MeshCache()
    capture(cache=cache)
    model.features_by_config['Default'][-1].body = model.by_config['Default'][0]
    result = capture(cache=cache)
    assert result.flat is None and len(model.export_calls) == 1
    assert any('gövdeye ait değil' in w for w in result.warnings)


def test_configuration_separates_cache_even_when_persistent_ids_are_shared(native):
    _, model, _, request, capture, _ = native
    cache = MeshCache()
    first = capture(cache=cache)
    model.names += ('Alternate',)
    model.by_config['Alternate'] = model.by_config['Default']
    model.features_by_config['Alternate'] = model.features_by_config['Default']
    second = capture(request(configuration='Alternate'), cache)
    assert second.flat is not first.flat and len(model.export_calls) == 2
    assert second.configuration == 'Alternate' and model.active == 'Default'


def test_flat_cache_uses_post_export_revision_and_keeps_stale_output_warning(native):
    _, model, _, _, capture, _ = native
    cache = MeshCache()
    model.after_export = lambda: setattr(model, 'GetUpdateStamp', lambda: 11)
    first = capture(cache=cache)
    second = capture(cache=cache)
    assert first.revision[-1] == 11 and second.flat is first.flat
    assert len(model.export_calls) == 1
    assert any('Kaynak çıktıdan sonra değişmiş' in w for w in second.warnings)


def test_pending_rebuild_fails_before_native_export_or_provisional_display(native):
    _, model, _, _, capture, _ = native
    cache, stages = MeshCache(), []
    capture(cache=cache)
    model.Extension.NeedsRebuild2 = True
    with pytest.raises(ApiError, match='güncelliği doğrulanamadı'):
        capture(cache=cache, on_flat=stages.append)
    assert not stages and len(model.export_calls) == 1


def test_unsaved_source_is_displayed_live_and_not_retained_in_worker_cache(native):
    _, model, calls, _, capture, _ = native
    model.GetSaveFlag = lambda: True
    cache = MeshCache()
    first = capture(cache=cache)
    second = capture(cache=cache)
    assert not cache.items and first.flat is not second.flat and not second.cached
    assert calls['tessellations'] == len(model.export_calls) == 2
    assert any('kaydedilmemiş güncel geometri' in w for w in second.warnings)


def test_cache_is_not_published_on_outer_session_restore_failure(native):
    _, _, _, request, _, Session = native
    class BrokenSession(Session):
        def __exit__(self, *args):
            super().__exit__(*args)
            raise RestoreError('restore failed')
    cache = MeshCache()
    with pytest.raises(RestoreError):
        sw.capture(request(), cache, session_factory=BrokenSession)
    assert not cache.items


def test_mesh_and_flat_share_one_bounded_lru_budget(native):
    _, _, _, _, capture, _ = native
    result = capture()
    cache = MeshCache(maximum=result.mesh.size + result.flat.size - 1)
    cache.put(('mesh',), result.mesh)
    cache.put_flat(('flat',), result.flat)
    assert cache.get(('mesh',)) is None and cache.get_flat(('flat',)) is result.flat
    assert cache.size <= cache.maximum
    cache.clear()
    assert not cache.items and cache.size == 0
