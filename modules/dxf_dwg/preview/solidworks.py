"""Read the exact source in one STA; no Save, feature suppression or new SW instance."""

from contextlib import contextmanager, ExitStack
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from modules.cad_converter.api import call, get, interface, invoke, PART_IID, ApiError, RestoreError
from modules.cad_converter.models import checkpoint
from modules.profile_cutting.solidworks import optional, values
from modules.dxf_dwg.sheetmetal import Session as ReadSession
from modules.dxf_dwg import exporter
from .flat import read_flat
from .geometry import make_mesh, MAX_TRIANGLES
from .models import Payload


def file_stamp(path):
    try:
        info = Path(path).stat()
    except OSError as error:
        raise ApiError('Kaynak parça bulunamadı veya okunamıyor: ' + Path(path).name) from error
    return info.st_size, info.st_mtime_ns


class Session(ReadSession):
    @contextmanager
    def folded(self, model, requested):
        """Only follow an actual derived-config parent; never guess from names."""
        config = parent = None
        try:
            with ExitStack() as stack:
                current = requested or self.active_configuration(model)
                original = current
                seen = set()
                for _ in range(12):
                    if current in seen:
                        raise ApiError('Konfigürasyon üst ilişkisi döngülü; önizleme durduruldu.')
                    seen.add(current)
                    stack.enter_context(self.configuration(model, current))
                    state = call(model, 'GetBendState')
                    if state != self.c('swSMBendStateFlattened'):
                        if state not in tuple(self.c(n) for n in ('swSMBendStateNone', 'swSMBendStateSharps', 'swSMBendStateFolded')):
                            raise ApiError('Parçanın bükülmüş durumu doğrulanamadı.')
                        yield current, original
                        return
                    config = call(model, 'GetConfigurationByName', current)
                    if config is None or not call(config, 'IsDerived'):
                        raise ApiError('Parça açınım halinde. Bükülmüş konfigürasyonu SolidWorks’te etkinleştirip Yenile’ye basın.')
                    parent = call(config, 'GetParent')
                    if parent is None:
                        raise ApiError('Açınım konfigürasyonunun bükülmüş üst konfigürasyonu bulunamadı.')
                    current = str(get(parent, 'Name'))
                    config = parent = None
                raise ApiError('Konfigürasyon üst ilişkisi sınırı aşıldı.')
        finally:
            model = config = parent = None

    def body(self, model, reference):
        part = bodies = body = None
        matches = ()
        try:
            part = interface(model, PART_IID)
            bodies = values(call(part, 'GetBodies2', self.c('swSolidBody'), False))
            if reference:
                matches = [b for b in bodies if self.persistent_ref(model, b) == reference]
                if len(matches) != 1:
                    raise ApiError('Çıktının sac gövdesi artık bulunamıyor; DXF/DWG aktarımını yenileyin.')
                body = matches[0]
            elif len(bodies) == 1:
                body = bodies[0]
            else:
                raise ApiError('Bu aktarım tek sac gövdesi kullanır. Birden fazla gövdede çıktı-gövde eşleşmesi olmadan önizleme gösterilmez.')
            if not call(body, 'IsSheetMetal'):
                raise ApiError('Seçili kaynak gövdesi sac metal değil.')
            return body, len(bodies)
        finally:
            model = part = bodies = body = None
            matches = ()

    def triangles(self, body, stop):
        faces = face = None
        coordinates = []
        try:
            faces = values(call(body, 'GetFaces'))
            if not faces:
                return self.body_tessellation(body, stop)
            for face in faces:
                checkpoint(stop)
                try:
                    triangles = call(face, 'GetTessTriangles', True)
                except Exception:
                    triangles = None
                if triangles is None or len(triangles) == 0:
                    # Hidden/read-only documents need not have display triangles.
                    # Generate a private tessellation, without changing image
                    # quality preferences, suppressing features or saving CAD.
                    return self.body_tessellation(body, stop)
                if len(triangles) % 9 or len(coordinates) + len(triangles) > MAX_TRIANGLES * 9:
                    raise ApiError('SolidWorks tessellation verisi geçersiz veya 120.000 üçgen sınırını aşıyor.')
                coordinates.extend(triangles)
            return make_mesh(coordinates, stop)
        finally:
            body = faces = face = None

    def body_tessellation(self, body, stop):
        tessellation = None
        try:
            checkpoint(stop)
            tessellation = call(body, 'GetTessellation', None)
            if tessellation is None:
                raise ApiError('SolidWorks gövde tessellation nesnesi oluşturulamadı.')
            invoke(tessellation, 'NeedVertexNormal', 4, False)
            invoke(tessellation, 'ImprovedQuality', 4, False)
            if not call(tessellation, 'Tessellate'):
                raise ApiError('SolidWorks gövdeyi üçgenlere ayıramadı.')
            count = call(tessellation, 'GetFacetCount')
            if type(count) is not int or not 0 < count <= MAX_TRIANGLES:
                raise ApiError('Tessellation yüz sayısı geçersiz veya 120.000 sınırını aşıyor.')
            coordinates, vertices = [], {}
            for facet in range(count):
                checkpoint(stop)
                fins = values(call(tessellation, 'GetFacetFins', facet))
                ids = []
                for fin in fins:
                    for vertex in values(call(tessellation, 'GetFinVertices', fin)):
                        if vertex not in ids: ids.append(vertex)
                if len(ids) != 3:
                    raise ApiError('SolidWorks üçgen olmayan bir tessellation yüzü döndürdü.')
                for vertex in ids:
                    if vertex not in vertices:
                        point = values(call(tessellation, 'GetVertexPoint', vertex))
                        if len(point) != 3: raise ApiError('Tessellation köşe koordinatı geçersiz.')
                        vertices[vertex] = point
                    coordinates.extend(vertices[vertex])
            return make_mesh(coordinates, stop)
        except ApiError:
            raise
        except Exception as error:
            from modules.cad_converter.models import Cancelled
            if isinstance(error, Cancelled): raise
            raise ApiError('SolidWorks yüz/gövde üçgen verisi alınamadı; bağlantıyı kontrol edip Yenile’ye basın.') from error
        finally:
            body = tessellation = None

    def metadata(self, model, configuration, request, body_reference='', *, selected=None):
        properties = {}
        body_properties = {}
        body_name = request.body_name
        cut_list_name = ''
        extension = manager = wrapper = None
        try:
            extension = get(model, 'Extension')
            for scope in ('', configuration):
                try:
                    manager = invoke(extension, 'CustomPropertyManager', 2, scope)
                    # Reuse the established Get6/BYREF/resolved-value contract.
                    from types import SimpleNamespace
                    wrapper = SimpleNamespace(CustomPropertyManager=manager)
                    for key, prop in self.properties(wrapper).items():
                        if prop.resolved and prop.evaluated:
                            properties[key.casefold()] = prop.evaluated
                except Exception:
                    pass  # Unknown is displayed as unknown, never a raw expression.
            # Sheet-metal Cut Lists can carry body-specific material/bend data.
            # Only use a folder that actually contains this persistent body.
            if body_reference:
                folder = members = member = feature = None
                try:
                    def matches(feature, kind):
                        if feature is None or kind != 'CutListFolder':
                            return False
                        folder = call(feature, 'GetSpecificFeature2')
                        members = values(call(folder, 'GetBodies'))
                        return any(self.persistent_ref(model, member) == body_reference for member in members)
                    # Names are hints only: membership must still match the
                    # live persistent body. Renames fall back to tree traversal.
                    if request.cut_list:
                        try:
                            feature = call(model, 'FeatureByName', request.cut_list)
                        except Exception:
                            feature = None
                    if not matches(feature, optional(feature, 'GetTypeName2')):
                        feature = next((f for f, kind in self.cut_folders(model) if matches(f, kind)), None)
                    if feature is not None:
                        cut_list_name = str(get(feature,'Name'))
                        for key, prop in self.properties(feature).items():
                            if prop.resolved and prop.evaluated:
                                properties[key.casefold()] = prop.evaluated
                                body_properties[key.upper()] = prop.evaluated
                except Exception:
                    pass
                finally:
                    folder = members = member = feature = None
            def field(names):
                return next((properties[n.casefold()] for n in names if n.casefold() in properties), 'Okunamadı')
            if body_reference and selected is None:
                try:
                    selected, _ = self.body(model, body_reference)
                except Exception:
                    pass
            material = self.material(model, selected, configuration, {k.upper():v for k,v in properties.items()},
                                     body_props=body_properties) or 'Okunamadı'
            thickness = 'Okunamadı'
            try:
                body_name = str(optional(selected, 'Name', prop=True, default=body_name) or body_name)
                # Use body-linked sheet features first. The whole-tree fallback
                # remains lazy, so known body thickness costs no global walk.
                thickness = f'{self.thickness(model, selected, {k.upper():v for k,v in properties.items()}, self.features(model)):g} mm'
            except Exception:
                pass
            code = field(('PART NUMBER', 'PARTNO', 'KOD', 'PARÇA KODU'))
            if code == 'Okunamadı': code = Path(request.source).stem + ' (dosya adı)'
            return ([('Gövde',body_name)] if body_name else []) + ([('Cut List',cut_list_name)] if cut_list_name else []) + [('Parça kodu', code),
                    ('Açıklama', field(('DESCRIPTION', 'AÇIKLAMA', 'TANIM'))),
                    ('Dosya', Path(request.source).name), ('Konfigürasyon', configuration),
                    ('Malzeme', material), ('Sac kalınlığı', thickness),
                    ('Adet', str(request.quantity) if request.quantity is not None else 'Henüz montajdan okunmadı'),
                    ('Büküm sayısı', field(('BENDS', 'BEND COUNT', 'BENDCOUNT', 'NUMBER OF BENDS', 'NUMBEROFBENDS', 'BÜKÜM SAYISI')))]
        finally:
            model = extension = manager = wrapper = selected = None


def source_changes(request, before, update):
    return (bool(request.source_stamp and tuple(request.source_stamp) != before)
            or request.update_stamp is not None and update != request.update_stamp)


def flat_for_source(session, model, request, before, update, body_count, stop):
    """Work in the exported configuration, before taking the folded snapshot."""
    warnings = []
    changed = source_changes(request, before, update)
    output = Path(request.output) if request.output else None
    if output and output.suffix.casefold() == '.dxf' and not changed and output.is_file():
        flat = read_flat(output, 'Oluşturulmuş DXF çıktısı', stop)
        if request.output_status == 'skipped':
            warnings.append('Mevcut DXF yeniden oluşturulmadı; kaynakla güncelliği doğrulanmadı.')
    else:
        if changed:
            warnings.append('Kaynak çıktıdan sonra değişmiş; çıktı yeniden alınmalı. Açınım güncel kaynaktan önizleniyor.')
        if body_count != 1 and not (request.body_ref and request.flat_ref):
            raise ApiError('Çok gövdeli kaynak için güvenilir açınım önizlemesi yok; gövdeye özel çıktı gerekli.')
        checkpoint(stop)
        # Same source/configuration and native export path. Never an inferred
        # DXF->3D model, never save a native source or replace the user's output.
        with TemporaryDirectory(prefix='gokworks-flat-preview-') as folder:
            temporary = Path(folder) / 'preview.dxf'
            try:
                status, detail = exporter.export_one_part(session.app, request.source, [temporary],
                    bend_lines=request.bend_lines, stop_event=stop,
                    sheet=dict(configuration=request.configuration, body_ref=request.body_ref,
                               flat_ref=request.flat_ref, flat_pattern=request.flat_pattern) if request.flat_ref else None,
                    selection_session=session if request.flat_ref else None)
            except exporter.SourceRestoreError as error:
                raise RestoreError(str(error)) from error
            checkpoint(stop)
            if status != 'success':
                raise ApiError(detail)
            description = ('DWG kaynağından geçici DXF · DWG dosyası okunmadı' if output and output.suffix.casefold() == '.dwg'
                           else 'Geçici açınım önizlemesi · üretim çıktısı değil')
            flat = read_flat(temporary, description, stop)
    warnings.extend(flat.warnings)
    return flat, warnings


def capture(request, cache, stop=None, *, session_factory=Session, geometry_only=False, on_flat=None):
    """One native read; final payload is published only after state restoration.

    on_flat receives immutable, provisional geometry after flat-export/config
    restoration. It is for early display only; live validation, folded capture
    and session restoration must succeed before production review is allowed.
    """
    if Path(request.source).suffix.casefold() != '.sldprt':
        raise ValueError('Önizleme için bir SLDPRT kaynağı seçin.')
    before = file_stamp(request.source)
    warnings = []
    started, timings = perf_counter(), []
    flat_cache_key = None
    with session_factory() as session:
        model = body = None
        try:
            checkpoint(stop)
            model = session.document(request.source)
            if call(model, 'GetType') != session.c('swDocPART'):
                raise ApiError('Önizleme kaynağı parça değil.')
            # Do not take the mesh stamp before a temporary native flat export:
            # ShowConfiguration2 may itself advance SW's update counter.
            exported_configuration = request.configuration or session.active_configuration(model)
            flat = None
            if not geometry_only:
                flat_started = perf_counter()
                with session.configuration(model, exported_configuration):
                    if session.rebuild_pending(model) is not False:
                        raise ApiError('Modelin güncelliği doğrulanamadı. SolidWorks’te yeniden oluşturup Yenile’ye basın.')
                    body, body_count = session.body(model, request.body_ref)
                    update = optional(model, 'GetUpdateStamp')
                    # Cache only native, body-specific flat geometry with a
                    # known live revision. Existing DXFs retain their own read
                    # path. Metadata and native ownership are always refreshed.
                    cache_flat = (type(update) is int and request.body_ref and request.flat_ref
                                  and Path(request.output).suffix.casefold() != '.dxf'
                                  and optional(model, 'GetSaveFlag') is False)
                    def flat_key(stamp):
                        return (str(Path(request.source).resolve()), before, exported_configuration,
                                request.body_ref, request.flat_ref, stamp, request.bend_lines,
                                Path(request.output).suffix.casefold())
                    body = None
                    try:
                        flat = cache.get_flat(flat_key(update)) if cache_flat else None
                        if flat is None:
                            flat, notes = flat_for_source(session, model, request, before, update, body_count, stop)
                        else:
                            with session.selected_flat(model, request.body_ref, request.flat_ref, stop,
                                                       feature_name=request.flat_pattern):
                                checkpoint(stop)
                            notes = list(flat.warnings)
                            if source_changes(request, before, update):
                                notes.append('Kaynak çıktıdan sonra değişmiş; çıktı yeniden alınmalı. Açınım güncel kaynaktan önizleniyor.')
                        warnings.extend(notes)
                        after_flat = optional(model, 'GetUpdateStamp')
                        if cache_flat and type(after_flat) is int:
                            flat_cache_key = flat_key(after_flat)
                    except Exception as error:
                        from modules.cad_converter.models import Cancelled
                        if isinstance(error, (Cancelled, RestoreError)):
                            raise
                        flat = None
                        flat_cache_key = None
                        warnings.append('Açınım önizlemesi okunamadı: ' + str(error))
                checkpoint(stop)
                timings.append(('açınım', perf_counter()-flat_started))
                if flat is not None and on_flat is not None:
                    on_flat(flat)
            with session.folded(model, exported_configuration) as (configuration, _):
                if session.rebuild_pending(model) is not False:
                    raise ApiError('Modelin güncelliği doğrulanamadı. SolidWorks’te yeniden oluşturup Yenile’ye basın.')
                # SOLIDWORKS can advance its own update counter while a clean (saved,
                # unmodified) document is tessellated or its cut list is read. That is
                # not a user change: re-read once and publish only a read during which
                # the counter stayed put. A dirty document or a changed file is refused.
                for attempt in range(2):
                    body, _ = session.body(model, request.body_ref)
                    reference = session.persistent_ref(model, body)
                    update = optional(model, 'GetUpdateStamp')
                    update = update if type(update) is int else None
                    revision = (str(Path(request.source).resolve()), before, configuration, reference, update)
                    # Update counters can restart when a document is reopened.
                    # Unsaved geometry cannot rely on file revision + counter to
                    # identify its contents across document lifetimes.
                    cache_mesh = update is not None and optional(model, 'GetSaveFlag') is False
                    mesh = cache.get(revision) if cache_mesh else None
                    cached = mesh is not None
                    mesh_started = perf_counter()
                    if mesh is None:
                        mesh = session.triangles(body, stop)
                    timings.append(('3D', perf_counter()-mesh_started))
                    metadata_started = perf_counter()
                    info = session.metadata(model, configuration, request, reference, selected=body)
                    timings.append(('bilgiler', perf_counter()-metadata_started))
                    body = None
                    checkpoint(stop)
                    if file_stamp(request.source) != before:
                        raise ApiError('Kaynak dosya önizleme sırasında değişti (diskte kaydedildi); '
                                       'eski geometri gösterilmedi. Yenileyin.')
                    if optional(model, 'GetUpdateStamp') == update:
                        break
                    if attempt == 0 and optional(model, 'GetSaveFlag') is False:
                        # Same saved file, clean document: an internal recompute. The
                        # flat came from that same file; only 3D/metadata are re-read.
                        continue
                    raise ApiError('Kaynak önizleme sırasında değişti: SOLIDWORKS modeli güncellendi'
                                   + (' (kaydedilmemiş değişiklik var)' if optional(model, 'GetSaveFlag') else '')
                                   + '; eski geometri gösterilmedi. Yenileyin.')
                if configuration != exported_configuration:
                    warnings.append(f'3D: türetilmiş açınımın üst konfigürasyonu {configuration}; çıktı: {exported_configuration}.')
                if optional(model, 'GetSaveFlag', default=False):
                    warnings.append('SolidWorks oturumundaki kaydedilmemiş güncel geometri gösteriliyor.')
                if flat:
                    if not any('birimi tanımlı değil' in w for w in flat.warnings):
                        a, b, c, d = flat.bounds
                        info.append(('Açınım sınırları', f'{c-a:.2f} × {d-b:.2f} mm'))
                    if flat.cut_length is not None:
                        info.append(('DXF çizgi toplamı ≈', f'{flat.cut_length:.2f} mm · katman sınıflamasıyla'))
                cache_mesh &= optional(model, 'GetSaveFlag') is False
                payload = Payload(request.source, configuration, mesh, flat, tuple(info), revision, tuple(warnings), cached)
        finally:
            # Drop all CAD pointers while still inside the owning STA.
            model = body = None
    if cache_mesh:
        cache.put(revision, mesh)
    if (cache_mesh and flat is not None and flat_cache_key is not None and configuration == exported_configuration
            and update == flat_cache_key[5]):
        cache.put_flat(flat_cache_key, flat)
    return replace(payload, timings=tuple(timings) + (('toplam', perf_counter()-started),))


def capture_geometry(request, cache, stop=None, *, session_factory=Session):
    """Publish a restored 3D snapshot without waiting for temporary DXF export."""
    return capture(request, cache, stop, session_factory=session_factory, geometry_only=True)
