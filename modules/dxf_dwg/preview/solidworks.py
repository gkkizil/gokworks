"""Read the exact source in one STA; no Save, feature suppression or new SW instance."""

from contextlib import contextmanager, ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.cad_converter.api import call, get, interface, invoke, PART_IID, ApiError
from modules.cad_converter.models import checkpoint
from modules.profile_cutting.solidworks import Session as ReadSession, optional, values
from modules.tolerance_stack.com import variant
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

    def metadata(self, model, configuration, request, body_reference=''):
        properties = {}
        extension = manager = wrapper = part = None
        thicknesses = []
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
                    for feature in self.cut_folders(model):
                        if call(feature, 'GetTypeName2') != 'CutListFolder':
                            continue
                        folder = call(feature, 'GetSpecificFeature2')
                        members = values(call(folder, 'GetBodies'))
                        if any(self.persistent_ref(model, member) == body_reference for member in members):
                            for key, prop in self.properties(feature).items():
                                if prop.resolved and prop.evaluated:
                                    properties[key.casefold()] = prop.evaluated
                            break
                except Exception:
                    pass
                finally:
                    folder = members = member = feature = None
            def field(names):
                return next((properties[n.casefold()] for n in names if n.casefold() in properties), 'Okunamadı')
            material = field(('MATERIAL', 'SW-MATERIAL', 'MALZEME'))
            if material == 'Okunamadı':
                try:
                    part = interface(model, PART_IID)
                    database = variant(0x4008, '')
                    value = call(part, 'GetMaterialPropertyName2', configuration, database)
                    if isinstance(value, str) and value:
                        material = value
                except Exception:
                    pass
            # Traverse both feature-link contexts, as in the existing exporter.
            feature = definition = None
            pending, seen = [(call(model, 'FirstFeature'), False)], set()
            try:
                while pending:
                    feature, sub = pending.pop()
                    if feature is None:
                        continue
                    kind, name = call(feature, 'GetTypeName2'), str(get(feature, 'Name'))
                    token = name, kind, sub
                    if token in seen:
                        continue
                    seen.add(token)
                    if len(seen) > 20000:
                        break
                    pending.append((call(feature, 'GetNextSubFeature' if sub else 'GetNextFeature'), sub))
                    pending.append((call(feature, 'GetFirstSubFeature'), True))
                    if kind == 'SheetMetal':
                        suppressed = call(feature, 'IsSuppressed2', self.c('swThisConfiguration'), variant(0, None))
                        if suppressed is not None and not any(values(suppressed)):
                            definition = call(feature, 'GetDefinition')
                            thicknesses.append(float(get(definition, 'Thickness')) * 1000)
            except Exception:
                thicknesses = []
            finally:
                feature = definition = None
                pending = []
            thickness = (f'{thicknesses[0]:g} mm' if thicknesses and all(abs(t-thicknesses[0]) < 1e-6 for t in thicknesses)
                         and thicknesses[0] > 0 else 'Okunamadı')
            code = field(('PART NUMBER', 'PARTNO', 'KOD', 'PARÇA KODU'))
            if code == 'Okunamadı': code = Path(request.source).stem + ' (dosya adı)'
            return [('Parça kodu', code),
                    ('Açıklama', field(('DESCRIPTION', 'AÇIKLAMA', 'TANIM'))),
                    ('Dosya', Path(request.source).name), ('Konfigürasyon', configuration),
                    ('Malzeme', material), ('Sac kalınlığı', thickness),
                    ('Adet', str(request.quantity) if request.quantity is not None else 'Henüz montajdan okunmadı'),
                    ('Büküm sayısı', field(('BENDS', 'BEND COUNT', 'BENDCOUNT', 'NUMBER OF BENDS', 'NUMBEROFBENDS', 'BÜKÜM SAYISI')))]
        finally:
            model = extension = manager = wrapper = part = None


def flat_for_source(session, model, request, before, update, body_count, stop):
    """Work in the exported configuration, before taking the folded snapshot."""
    warnings = []
    changed = bool(request.source_stamp and tuple(request.source_stamp) != before)
    changed |= request.update_stamp is not None and update != request.update_stamp
    output = Path(request.output) if request.output else None
    if output and output.suffix.casefold() == '.dxf' and not changed and output.is_file():
        flat = read_flat(output, 'Oluşturulmuş DXF çıktısı', stop)
        if request.output_status == 'skipped':
            warnings.append('Mevcut DXF yeniden oluşturulmadı; kaynakla güncelliği doğrulanmadı.')
    else:
        if changed:
            warnings.append('Kaynak çıktıdan sonra değişmiş; çıktı yeniden alınmalı. Açınım güncel kaynaktan önizleniyor.')
        if body_count != 1:
            raise ApiError('Çok gövdeli kaynak için güvenilir açınım önizlemesi yok; gövdeye özel çıktı gerekli.')
        checkpoint(stop)
        # Same source/configuration and native export path. Never an inferred
        # DXF->3D model, never save a native source or replace the user's output.
        with TemporaryDirectory(prefix='gokworks-flat-preview-') as folder:
            temporary = Path(folder) / 'preview.dxf'
            status, detail = exporter.export_one_part(session.app, request.source, [temporary],
                                                     bend_lines=request.bend_lines)
            if status != 'success':
                raise ApiError(detail)
            description = ('DWG kaynağından geçici DXF · DWG dosyası okunmadı' if output and output.suffix.casefold() == '.dwg'
                           else 'Geçici açınım önizlemesi · üretim çıktısı değil')
            flat = read_flat(temporary, description, stop)
    warnings.extend(flat.warnings)
    return flat, warnings


def capture(request, cache, stop=None, *, session_factory=Session):
    """Attach to the existing SW and publish only after state restoration."""
    if Path(request.source).suffix.casefold() != '.sldprt':
        raise ValueError('Önizleme için bir SLDPRT kaynağı seçin.')
    before = file_stamp(request.source)
    warnings = []
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
            with session.configuration(model, exported_configuration):
                body, body_count = session.body(model, request.body_ref)
                body = None
                try:
                    flat, notes = flat_for_source(session, model, request, before,
                                                  optional(model, 'GetUpdateStamp'), body_count, stop)
                    warnings.extend(notes)
                except Exception as error:
                    from modules.cad_converter.models import Cancelled
                    if isinstance(error, Cancelled):
                        raise
                    warnings.append('Açınım önizlemesi okunamadı: ' + str(error))
            with session.folded(model, exported_configuration) as (configuration, _):
                if session.rebuild_pending(model) is not False:
                    raise ApiError('Modelin güncelliği doğrulanamadı. SolidWorks’te yeniden oluşturup Yenile’ye basın.')
                body, _ = session.body(model, request.body_ref if configuration == exported_configuration else '')
                reference = session.persistent_ref(model, body)
                update = optional(model, 'GetUpdateStamp')
                update = update if type(update) is int else None
                revision = (str(Path(request.source).resolve()), before, configuration, reference, update)
                mesh = cache.get(revision) if update is not None else None
                cached = mesh is not None
                if mesh is None:
                    mesh = session.triangles(body, stop)
                body = None
                info = session.metadata(model, configuration, request, reference)
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
                checkpoint(stop)
                if file_stamp(request.source) != before or optional(model, 'GetUpdateStamp') != update:
                    raise ApiError('Kaynak önizleme sırasında değişti; eski geometri gösterilmedi. Yenileyin.')
                if update is not None:
                    cache.put(revision, mesh)
                payload = Payload(request.source, configuration, mesh, flat, tuple(info), revision, tuple(warnings), cached)
        finally:
            # Drop all CAD pointers while still inside the owning STA.
            model = body = None
    return payload
