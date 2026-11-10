"""Read active native sheet metal in one STA; restore flattening in finally.

Only published OneBend + FlatPattern APIs are accepted. Unsupported recognition
is an explicit error, never a fabricated 90-degree bend or radius. No Save or
ModifyDefinition is called. All COM references die before the worker returns.
"""
from contextlib import contextmanager
from math import degrees, isfinite, pi
from pathlib import Path
from hashlib import sha256
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, polygonize
from .models import Bend, Flange, Part, Region
from modules.cad_converter.api import ApiError, RestoreError, call, get
from modules.cad_converter.models import checkpoint
from modules.dxf_dwg.sheetmetal import Session
from modules.profile_cutting.solidworks import values
from modules.tolerance_stack.com import variant


def partition(name, configuration, material, thickness, outline, bands, fixed_point, fixed_face, source):
    """Pure-data adapter boundary, shared by real COM capture and contracts.

    bands: stable id, tangent endpoints, measured width, turn, R, direction.
    Tangents are oriented away from the component containing the fixed face.
    """
    from shapely.geometry import Point
    zones = []
    for row in bands:
        start, end = np.asarray(row['start'], float), np.asarray(row['end'], float)
        u = (end-start)/np.linalg.norm(end-start); n = np.array([-u[1], u[0]])
        zone = Polygon([start, end, end+n*row['width'], start+n*row['width']]).intersection(outline.polygon())
        if zone.geom_type != 'Polygon' or zone.area <= 0:
            raise ApiError(f"{row['id']}: büküm bölgesi tek bağlı kontur değil.")
        zones.append(zone)
    remaining = outline.polygon().difference(unary_union(zones))
    polygons = [remaining] if remaining.geom_type == 'Polygon' else list(remaining.geoms)
    polygons = [p for p in polygons if p.area > .001]
    roots = [i for i, p in enumerate(polygons) if p.buffer(.001).contains(Point(fixed_point))]
    if len(roots) != 1 or len(polygons) != len(bands)+1:
        raise ApiError('Sabit yüz / flanş bağlantısı belirsiz; kapalı veya desteklenmeyen sac topolojisi.')
    flanges = tuple(Flange(f'F{i}', Region.from_polygon(p)) for i, p in enumerate(polygons))
    graph = []
    for row, zone in zip(bands, zones):
        neighbours = [i for i, p in enumerate(polygons) if p.buffer(1e-4).intersection(zone).area > 1e-5]
        if len(neighbours) != 2:
            raise ApiError(f"{row['id']}: iki komşu flanş eşleştirilemedi.")
        graph.append((row, zone, neighbours))
    seen, pending, bends = {roots[0]}, graph[:], []
    while pending:
        ready = [item for item in pending if sum(i in seen for i in item[2]) == 1]
        if not ready:
            raise ApiError('Döngülü/ayrık flanş grafiği; doğrusal ağaç topolojisi gerekli.')
        for row, zone, neighbours in ready:
            parent = next(i for i in neighbours if i in seen); child = next(i for i in neighbours if i not in seen)
            a, b, width = np.asarray(row['start']), np.asarray(row['end']), row['width']
            u = (b-a)/np.linalg.norm(b-a); n = np.array([-u[1], u[0]])
            child_center = np.array(polygons[child].representative_point().coords[0])
            if np.dot(child_center-a, n) < width/2:
                a, b = b+n*width, a+n*width
                direction = -row['direction']
            else:
                direction = row['direction']
            bends.append(Bend(row['id'], f'F{parent}', f'F{child}', tuple(a), tuple(b), width,
                              180-row['turn'], row['radius'], direction, Region.from_polygon(zone), 'SolidWorks · OneBend / mm normalize', row.get('label', '')))
            seen.add(child); pending.remove((row, zone, neighbours))
    return Part(name, configuration, material or 'Bilinmiyor', thickness, f'F{roots[0]}', flanges,
                tuple(bends), fixed_face, source).validate()


# IOneBendFeatureData owners: OneBend (base/edge flange bends) and SketchBend (sketched bend).
BEND_KINDS = ('OneBend', 'SketchBend')
SHEET_KINDS = ('Bend', 'Flange', 'Flat', 'Hem', 'Jog', 'SheetMetal', 'SM')


def feature_inventory(session, features, limit=24):
    """'Name (TypeName2[, bastırılmış])' for the sheet-metal features seen, for a diagnosable error."""
    rows = []
    for feature, kind in features:
        if not any(token.casefold() in kind.casefold() for token in SHEET_KINDS):
            continue
        try:
            off = ', bastırılmış' if _suppressed(session, feature) else ''
        except Exception:
            off = ', durum okunamadı'
        rows.append(f'{get(feature, "Name")} ({kind}{off})')
    shown = '; '.join(rows[:limit]) + (f'; … +{len(rows)-limit}' if len(rows) > limit else '')
    return shown or 'sac unsuru bulunamadı'


def _suppressed(session, feature):
    try:
        state = values(call(feature, 'IsSuppressed2', session.c('swThisConfiguration'), variant(0, None)))
        if len(state) != 1:
            raise ApiError('Unsurun aktif konfigürasyondaki bastırma durumu okunamadı.')
        return bool(state[0])
    finally:
        feature = None


@contextmanager
def flattened(session, model, flat, features, stop=None):
    """Snapshot/restore exact active config, selection list and feature states."""
    configuration = session.active_configuration(model)
    before = [(f, _suppressed(session, f), str(get(f, 'Name'))) for f, _ in features]
    manager = get(model, 'SelectionManager')
    suspended = False
    try:
        call(manager, 'SuspendSelectionList'); suspended = True
        checkpoint(stop)
        if not call(flat, 'SetSuppression2', session.c('swUnSuppressFeature'), session.c('swThisConfiguration'), variant(0, None)):
            raise ApiError('Flat-Pattern açılamadı; kaynak parça kaydedilmedi.')
        if not call(model, 'EditRebuild3'):
            raise ApiError('Geçici açınım yeniden oluşturulamadı.')
        checkpoint(stop)
        yield
    finally:
        failures = []
        try:
            if session.active_configuration(model) != configuration:
                if not call(model, 'ShowConfiguration2', configuration):
                    raise RestoreError('Aktif konfigürasyon geri getirilemedi.')
            # First restore FlatPattern; dependencies normally restore with it.
            ordered = sorted(before, key=lambda item: 0 if item[0] is flat else 1)
            for feature, state, label in ordered:
                if _suppressed(session, feature) != state:
                    mode = session.c('swSuppressFeature' if state else 'swUnSuppressFeature')
                    if not call(feature, 'SetSuppression2', mode, session.c('swThisConfiguration'), variant(0, None)):
                        failures.append(label)
            if not call(model, 'EditRebuild3'):
                failures.append('kaynak yeniden oluşturma')
            for feature, state, label in before:
                if _suppressed(session, feature) != state:
                    failures.append(label)
            if session.active_configuration(model) != configuration:
                failures.append('aktif konfigürasyon')
        except Exception as error:
            failures.append(str(error))
        finally:
            if suspended:
                try:
                    call(manager, 'ResumeSelectionList2', False)
                except Exception as error:
                    failures.append('seçim listesi: '+str(error))
            before.clear(); ordered = []; features = []; manager = feature = model = flat = None
        if failures:
            raise RestoreError('Kaynak durum geri yükleme doğrulanamadı: '+', '.join(failures)+' · Parçayı kaydetmeden SolidWorks’te kontrol edin.')


def _xyz(obj):
    try:
        return np.array([float(get(obj, axis)) for axis in ('X', 'Y', 'Z')])
    finally:
        obj = None


def _cylinder(surface):
    """Published ISurface.CylinderParams: origin/axis/radius, metres to mm."""
    try:
        if not call(surface, 'IsCylinder'):
            return None
        data = np.asarray(get(surface, 'CylinderParams'), float)
        if data.size != 7 or not np.isfinite(data).all() or data[6] <= 0:
            return None
        length = np.linalg.norm(data[3:6])
        if length < 1e-12:
            return None
        return data[:3]*1000, data[3:6]/length, data[6]*1000
    except Exception:
        return None


def _coaxial(a, b):
    return (np.linalg.norm(np.cross(a[1], b[1])) < 1e-6
            and np.linalg.norm(np.cross(a[0]-b[0], b[1])) < .01)


def _sheet_sidewall(face, cylinder, thickness):
    """Rounded contour/hole walls join two parallel sheet skins, not a bend.

    Their cylinder axis is normal to both adjacent planar skins and the
    measured separation is the sheet thickness. A bend axis is tangent to
    its neighbouring flange planes and cannot pass this test.
    """
    if cylinder is None:
        return False
    try:
        offsets = []
        for edge in values(call(face, 'GetEdges')):
            for adjacent in values(call(edge, 'GetTwoAdjacentFaces2')):
                surface = call(adjacent, 'GetSurface')
                if not call(surface, 'IsPlane'):
                    continue
                plane = np.asarray(get(surface, 'PlaneParams'), float)
                if plane.size == 6 and np.isfinite(plane).all():
                    normal = plane[:3]/np.linalg.norm(plane[:3])
                    if abs(normal@cylinder[1]) > 1-1e-6:
                        offsets.append(float(plane[3:]@cylinder[1])*1000)
        return any(abs(abs(a-b)-thickness) <= .01 for a in offsets for b in offsets)
    except Exception:
        return False


def _band(row, lines, zones, thickness):
    """Measure tangents, or a feature-owned flat bend face around a centreline."""
    base = np.array(lines[0][1])-lines[0][0]; length = np.linalg.norm(base)
    if length <= .001:
        raise ApiError(row['id']+': sıfır boylu büküm ekseni.')
    u = base/length; n = np.array([-u[1], u[0]])
    if any(abs(np.dot(np.array(b)-a, n)) > .001 for a, b in lines):
        raise ApiError(row['id']+': paralel doğrusal büküm teğetleri bulunamadı.')
    offsets = [float(np.dot(a, n)) for a, _ in lines]
    low, high = min(offsets), max(offsets)
    points = [p for line in lines for p in line]
    if high-low <= .001:
        # A visible bend centreline is not itself the developed width. Read
        # the actual, feature-associated face; never infer width from K-factor.
        measured = []
        for zone in zones:
            vertices = np.asarray(zone.exterior.coords)
            lo, hi = min(vertices@n), max(vertices@n)
            if (row['radius']*row['turn']*pi/180-.001 <= hi-lo
                    <= (row['radius']+thickness)*row['turn']*pi/180+.001
                    and lo-.001 <= offsets[0] <= hi+.001):
                measured.append(zone)
        zone = unary_union(measured)
        if zone.is_empty or zone.geom_type != 'Polygon':
            raise ApiError(row['id']+': yalnız merkez çizgisi var; ölçülmüş büküm bölgesi genişliği eksik.')
        points = list(zone.exterior.coords)
        low, high = min(np.asarray(points)@n), max(np.asarray(points)@n)
    lo = min(np.dot(p, u) for p in points); hi = max(np.dot(p, u) for p in points)
    return dict(row, start=tuple(u*lo+n*low), end=tuple(u*hi+n*low), width=float(high-low))


class Capture(Session):
    def owners(self, model, feature):
        result = set()
        for _ in range(16):
            if feature is None:
                break
            ref = self.persistent_ref(model, feature)
            if not ref or ref in result:
                break
            result.add(ref)
            try:
                feature = call(feature, 'GetOwnerFeature')
            except Exception:
                break
        return result

    def face_label(self, model, face, reference):
        owner = None
        try:
            owner = call(face, 'GetFeature')
            label = str(get(owner, 'Name')) if owner is not None else ''
        except Exception:
            label = ''
        finally:
            owner = None
        short = sha256(reference.encode('utf-8')).hexdigest()[:10] if reference else 'referans-yok'
        return (label+' / ' if label else '')+'yüz #'+short

    def one_body(self, model):
        bodies = values(call(self.part(model), 'GetBodies2', self.c('swSolidBody'), False))
        if len(bodies) != 1 or not call(bodies[0], 'IsSheetMetal'):
            raise ApiError(f'{len(bodies)} gövde bulundu; yalnız tek sabit kalınlıklı sac gövde desteklenir.')
        return bodies[0]

    def line(self, segment):
        sketch = inverse = math = p = world = None
        try:
            if call(segment, 'GetType') != self.c('swSketchLINE'):
                raise ApiError('Eğrisel büküm ekseni desteklenmiyor.')
            # SketchPoint is in sketch coordinates; SW's own MathTransform is
            # used rather than guessing ArrayData rotation transposition.
            sketch = call(segment, 'GetSketch')
            inverse = call(get(sketch, 'ModelToSketchTransform'), 'Inverse')
            math = call(self.app, 'GetMathUtility')
            points = []
            for member in ('GetStartPoint2', 'GetEndPoint2'):
                local = _xyz(call(segment, member))
                p = call(math, 'CreatePoint', variant(0x2005, list(local)))
                world = call(p, 'MultiplyTransform', inverse)
                points.append(np.asarray(get(world, 'ArrayData'), float)*1000)
            return points
        finally:
            segment = sketch = inverse = math = p = world = None

    def capture(self, model, stop):
        body = flat = fixed = features = definition = None
        snapshot = None
        try:
            if call(model, 'GetType') != self.c('swDocPART'):
                raise ApiError('Aktif belge SLDPRT olmalı.')
            if get(get(model, 'Extension'), 'NeedsRebuild2'):
                raise ApiError('Aktif konfigürasyonun yeniden oluşturulması gerekiyor. SolidWorks’te Ctrl+Q yapıp yeniden alın; eski büküm verisi kullanılmadı.')
            configuration = self.active_configuration(model)
            source = str(call(model, 'GetPathName'))
            if source and Path(source).suffix.casefold() != '.sldprt':
                raise ApiError('Yerel SLDPRT belge gerekli; genel STEP tanıma bu sürümde yok.')
            stamp = (Path(source).stat().st_size, Path(source).stat().st_mtime_ns) if source else None
            body = self.one_body(model)
            body_name = str(get(body, 'Name'))
            features = list(self.features(model, stop))
            active = [(f, k) for f, k in features if not _suppressed(self, f)]
            flats = [f for f, k in features if k == 'FlatPattern']
            if len(flats) != 1:
                raise ApiError(body_name+': tam bir Flat-Pattern ve sabit yüz gerekli.')
            flat = flats[0]; definition = call(flat, 'GetDefinition')
            fixed = get(definition, 'FixedFace2')
            fixed_ref = self.persistent_ref(model, fixed)
            if not fixed_ref or not call(call(fixed, 'GetSurface'), 'IsPlane'):
                raise ApiError(body_name+': düz sabit yüz kararlı referansıyla okunamadı.')
            props = self.document_properties(model, configuration)
            thickness = self.thickness(model, body, props, features)
            material = self.material(model, body, configuration, props)
            rows, covered, bend_faces = [], set(), []
            for feature, kind in active:
                checkpoint(stop)
                if kind not in BEND_KINDS:
                    continue
                label = str(get(feature, 'Name'))
                definition = call(feature, 'GetDefinition')
                try:
                    turn = abs(degrees(float(get(definition, 'BendAngle'))))
                    radius = float(get(definition, 'BendRadius'))*1000
                    direction = int(get(definition, 'BendDirection'))
                    up, down = self.c('swBendDirection_UP'), self.c('swBendDirection_DOWN')
                    if direction not in (up, down) or not 0 < turn < 180 or not isfinite(radius) or radius <= 0:
                        raise ValueError('Doğrusal büküm açısı/iç R/yön geçersiz.')
                    ref = self.persistent_ref(model, feature)
                    if not ref:
                        raise ValueError('Kararlı unsur referansı yok.')
                    faces_for_bend = values(call(feature, 'GetFaces'))
                    if not faces_for_bend:
                        raise ValueError('Büküm yüzleri / unsur eşleşmesi yok.')
                    covered.update(face_reference for f in faces_for_bend if (face_reference := self.persistent_ref(model, f)))
                    cylinders = []
                    for face in faces_for_bend:
                        try:
                            cylinder = _cylinder(call(face, 'GetSurface'))
                        except Exception:
                            cylinder = None
                        if cylinder is not None:
                            cylinders.append(cylinder)
                    bend_faces.append((radius, turn, self.owners(model, feature), cylinders))
                    rows.append((feature, {'id': 'SWB-'+sha256(ref.encode('ascii')).hexdigest()[:16], 'label': label,
                                           'turn': turn, 'radius': radius, 'direction': 1 if direction == up else -1}))
                except Exception as error:
                    raise ApiError(f'{body_name} / {label}: açı, iç R veya yön okunamadı: {error}') from error
            if not rows:
                raise ApiError(f'Gövde «{body_name}»: etkin doğrusal büküm unsuru (OneBend/SketchBend) bulunamadı; '
                               f'açı/radyüs uydurulmadı. Okunan sac unsurları: {feature_inventory(self, features)}')
            # Every partial cylindrical face must belong to an imported bend.
            # Full cylinders can be through-hole walls. Other curved surfaces
            # require recognition that this first version does not provide.
            for face in values(call(body, 'GetFaces')):
                surface = call(face, 'GetSurface')
                if call(surface, 'IsPlane'):
                    continue
                reference = self.persistent_ref(model, face)
                face_label = self.face_label(model, face, reference)
                if not call(surface, 'IsCylinder'):
                    raise ApiError(f'{body_name} / {face_label}: doğrusal silindirik büküm dışı eğrisel yüz desteklenmiyor.')
                uv = values(call(face, 'GetUVBounds'))
                if len(uv) != 4:
                    raise ApiError(f'{body_name} / {face_label}: silindir açı sınırları okunamadı.')
                if abs(abs(uv[1]-uv[0])-2*pi) > 1e-5 and reference not in covered:
                    cylinder = _cylinder(surface)
                    if _sheet_sidewall(face, cylinder, thickness):
                        continue
                    # EdgeFlange owns faces which its OneBend subfeature may
                    # expose only on the inner skin. Verify the measured outer
                    # cylinder, or the owning feature, rather than equating two
                    # different persistent references.
                    owner = None
                    try:
                        owner = call(face, 'GetFeature')
                        owner_ref = self.persistent_ref(model, owner) if owner is not None else ''
                    except Exception:
                        owner_ref = ''
                    finally:
                        owner = None
                    matches = cylinder is not None and any(
                        min(abs(cylinder[2]-r), abs(cylinder[2]-r-thickness)) <= .01
                        and abs(degrees(abs(uv[1]-uv[0]))-turn) <= .01
                        and (any(_coaxial(cylinder, c) for c in cylinders) or owner_ref in owners)
                        for r, turn, owners, cylinders in bend_faces)
                    if not matches:
                        raise ApiError(f'{body_name} / {face_label}: büküm unsuruyla eşleştirilemedi; büküm atlanmadı.')
            with flattened(self, model, flat, features, stop):
                body = self.one_body(model)
                definition = call(flat, 'GetDefinition'); fixed = get(definition, 'FixedFace2')
                plane = np.asarray(get(call(fixed, 'GetSurface'), 'PlaneParams'), float)
                if plane.size != 6:
                    raise ApiError(body_name+': açınım sabit yüz düzlemi okunamadı.')
                normal, origin = plane[:3], plane[3:]*1000
                normal /= np.linalg.norm(normal)
                u = np.cross([0, 0, 1] if abs(normal[2]) < .9 else [0, 1, 0], normal); u /= np.linalg.norm(u)
                v = np.cross(normal, u)
                def project(p):
                    p = np.asarray(p)-origin
                    return (float(p@u), float(p@v))
                regions, face_regions = [], []
                fixed_point = None
                fixed_match = self.persistent_ref(model, fixed)
                for face in values(call(body, 'GetFaces')):
                    checkpoint(stop)
                    surface = call(face, 'GetSurface')
                    if not call(surface, 'IsPlane'):
                        continue
                    params = np.asarray(get(surface, 'PlaneParams'), float)
                    if abs(abs(params[:3]@normal)-1) > 1e-6 or abs((params[3:]*1000-origin)@normal) > .001:
                        continue
                    loops = []
                    for loop in values(call(face, 'GetLoops')):
                        lines = []
                        for edge in values(call(loop, 'GetEdges')):
                            curve = call(edge, 'GetCurve')
                            cp = call(edge, 'GetCurveParams3')
                            start, end = get(cp, 'StartPoint'), get(cp, 'EndPoint')
                            xyz = values(call(curve, 'GetTessPts', .00002, .00000001, variant(0x2005, start), variant(0x2005, end)))
                            if len(xyz) < 6 or len(xyz) % 3:
                                raise ApiError(body_name+': açınım kenarı tessellation verisi eksik.')
                            points = np.asarray(xyz, float).reshape(-1, 3)*1000
                            lines.extend(LineString([project(a), project(b)]) for a, b in zip(points, points[1:]))
                        from shapely import set_precision
                        rings = list(polygonize(unary_union([set_precision(line, 1e-6) for line in lines])))
                        if len(rings) != 1:
                            raise ApiError(body_name+': açınım yüz döngüsü kapanmadı.')
                        loops.append((bool(call(loop, 'IsOuter')), rings[0]))
                    outers = [p for is_outer, p in loops if is_outer]
                    if len(outers) != 1:
                        raise ApiError(body_name+': yüz dış konturu belirsiz.')
                    polygon = Polygon(outers[0].exterior.coords, [p.exterior.coords for outer, p in loops if not outer])
                    regions.append(polygon)
                    flat_reference = self.persistent_ref(model, face)
                    face_regions.append((flat_reference, polygon))
                    if flat_reference == fixed_match:
                        fixed_point = tuple(polygon.representative_point().coords[0])
                union = unary_union(regions)
                if union.geom_type != 'Polygon' or fixed_point is None:
                    raise ApiError(body_name+': gerçek açınım veya sabit yüz eşleştirmesi başarısız.')
                bands = []
                for feature, row in rows:
                    checkpoint(stop)
                    definition = call(feature, 'GetDefinition')
                    segments = values(get(definition, 'FlatPatternSketchSegments2'))
                    if not segments:
                        raise ApiError(row['id']+': büküm teğetleri / eksenleri eksik.')
                    lines = [tuple(project(p) for p in self.line(s)) for s in segments]
                    try:
                        flat_refs = {self.persistent_ref(model, f) for f in values(call(feature, 'GetFaces'))}
                    except Exception:
                        # Some SW releases hide the subfeature faces after
                        # flattening. Measured tangent pairs remain sufficient;
                        # a centreline alone still fails unless its face exists.
                        flat_refs = set()
                    zones = [polygon for ref, polygon in face_regions if ref and ref in flat_refs]
                    bands.append(_band(row, lines, zones, thickness))
                snapshot = partition(str(call(model, 'GetTitle')), configuration, material, thickness, Region.from_polygon(union), bands,
                                     fixed_point, fixed_ref, source or 'Kaydedilmemiş aktif SLDPRT')
            if stamp and (Path(source).stat().st_size, Path(source).stat().st_mtime_ns) != stamp:
                raise RestoreError('Kaynak dosya zaman damgası içe aktarma sırasında değişti; sonuç kullanılmadı.')
            checkpoint(stop)
            return snapshot
        finally:
            rows = []; active = []; features = []
            body = flat = fixed = definition = model = feature = face = surface = loop = edge = curve = cp = None
            flats = []; segments = []
            faces_for_bend = []


def read_active(stop=None, session_factory=Capture):
    checkpoint(stop)
    with session_factory() as session:
        model = None
        try:
            model = get(session.app, 'ActiveDoc')
            if model is None:
                raise ApiError('SolidWorks’te bir sac SLDPRT açın ve konfigürasyonunu etkinleştirin.')
            return session.capture(model, stop)
        finally:
            model = None
