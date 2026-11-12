"""Finite catalogue search reusing Stage 1 geometry, never inventing SKUs.

Hard filters precede ranking. Unknown engineering checks stay in a separate
opt-in group. Search coverage and returned-result limits are independent.
"""

from bisect import insort
from collections import Counter, defaultdict
import json
from math import isclose, cos, radians, inf

from ._numbers import positive
from .calculation import calculate
from .catalog.importers import fingerprint
from .catalog.products import ProductCatalog
from .catalog.profiles import get_profile
from .design_models import DesignRequest, DesignCandidate, RejectedCombination, DesignSearchReport
from .design_ranking import ranking_key
from .engineering.belt_length import length_metrics
from .engineering.ratings import TabulatedRatingProvider
from .models import (BeltDriveSpecification, BeltSpecification, PulleySpecification,
                     CenterSpecification, LoadSpecification, SpecificationError, Issue)
from .validation import CalculationCancelled


def outside(value, minimum, maximum):
    """1e-9 in the reported unit / 1e-12 relative absorbs floating-point noise."""
    return (minimum is not None and value < minimum and not isclose(value, minimum, abs_tol=1e-9, rel_tol=1e-12)) or \
           (maximum is not None and value > maximum and not isclose(value, maximum, abs_tol=1e-9, rel_tol=1e-12))


def _center_bounds(request):
    if request.mode == 'fixed':
        return request.center_target_mm - request.center_tolerance_mm, request.center_target_mm + request.center_tolerance_mm
    return request.center_min_mm, request.center_max_mm


def _fits_product(request, catalog, product):
    return get_profile(product.profile).family == request.family and \
        (request.profile is None or product.profile == request.profile) and \
        (request.series_id is None or product.series_id == request.series_id) and \
        (request.manufacturer is None or catalog.source(product.source_id).manufacturer.casefold() == request.manufacturer.casefold())


def compatibility_group(catalog, product):
    """Explicit compatibility is separate from a commercial belt/pulley series.

    A common pitch alone never establishes compatibility. Cross-manufacturer
    combinations remain outside this search's declared compatibility contract.
    """
    return (catalog.source(product.source_id).manufacturer.casefold(),
            product.profile, product.compatibility_id)


def operating_limit_failure(request, result):
    if outside(result.speed_m_s, None, request.maximum_belt_speed_m_s):
        return 'BELT_SPEED_LIMIT'
    if outside(min(result.driver_wrap_deg, result.driven_wrap_deg), request.minimum_wrap_deg, None):
        return 'MINIMUM_WRAP'
    if request.minimum_engaged_teeth is not None and outside(
            min(result.engaged_driver_teeth_estimate, result.engaged_driven_teeth_estimate),
            request.minimum_engaged_teeth, None):
        return 'MINIMUM_ENGAGED_TEETH'
    return None


def minimum_center_for_limits(request, d1, d2, z1=None, z2=None):
    """Invert the small-pulley wrap constraint, without an assumed default.

    beta = pi - 2 asin(|D2-D1|/(2C)); engaged teeth = z*beta/(2pi).
    """
    wrap = request.minimum_wrap_deg or 0.
    if request.minimum_engaged_teeth is not None:
        wrap = max(wrap, 360.*request.minimum_engaged_teeth/min(z1,z2))
    if wrap > 180 or wrap == 180 and d1 != d2:
        return inf
    if d1 == d2:
        return 0.
    return abs(d2-d1)/2/cos(radians(wrap/2))


def candidate_specification(request, driver, driven, belt, count):
    timing = request.family == 'timing'
    return BeltDriveSpecification(
        belt=BeltSpecification(request.family, belt.profile, count=count or 1),
        driver=PulleySpecification(None, driver.teeth) if timing else PulleySpecification(driver.datum_diameter_mm),
        driven=PulleySpecification(None, driven.teeth) if timing else PulleySpecification(driven.datum_diameter_mm),
        load=LoadSpecification(request.input_rpm, request.power_kw, service_factor=request.service_factor),
        center=CenterSpecification('length', None, None if timing else belt.datum_length_mm, belt.tooth_count if timing else None))


def search_drives(request, catalog, *, stop=None, progress=None):
    if not isinstance(request, DesignRequest) or not isinstance(catalog, ProductCatalog):
        raise ValueError('DesignRequest ve ProductCatalog gerekli.')
    lower, upper = _center_bounds(request)
    if upper is not None:
        positive(upper, 'C üst sınırı')
    counts = Counter()
    rejections, verified, unverified = [], [], []
    pairs = evaluated = solved = verified_count = unverified_count = work = 0
    cancelled = limited = False
    stop_reason = ''

    def stopped():
        nonlocal cancelled, limited, stop_reason
        if stop is not None and stop.is_set():
            cancelled = True; stop_reason = 'Kullanıcı iptali; arama tamamlanmadı.'
            return True
        if work >= request.work_limit:
            limited = True; stop_reason = 'İş adımı sınırı; arama kapsamı tamamlanmadı.'
            return True
        return False

    def reject(driver, driven, belt, reason, detail=''):
        counts[reason] += 1
        if len(rejections) < request.result_limit:
            rejections.append(RejectedCombination(driver.code, driven.code, belt.code if belt else None, reason + (': ' + detail if detail else '')))

    def retain(bucket, candidate):
        insort(bucket, (candidate.ranking_key, candidate))
        if len(bucket) > request.result_limit:
            bucket.pop()

    groups = defaultdict(lambda: ([], []))
    excluded = 0
    if stop is not None and stop.is_set():
        cancelled = True; stop_reason = 'Kullanıcı iptali; arama tamamlanmadı.'
    for product in (*catalog.belts, *catalog.pulleys):
        if stop is not None and stop.is_set():
            cancelled = True; stop_reason = 'Kullanıcı iptali; arama tamamlanmadı.'; break
        if not _fits_product(request, catalog, product):
            excluded += 1
            continue
        key = compatibility_group(catalog, product)
        groups[key][0 if hasattr(product, 'length_mm') else 1].append(product)
    provider = TabulatedRatingProvider()
    tables = {(item.series_id, item.profile): item for item in catalog.ratings}
    for group in sorted(groups):
        if cancelled:
            break
        belts, pulleys = groups[group]
        belts = sorted(belts, key=lambda x: (x.length_mm, x.code))
        pulleys = sorted(pulleys, key=lambda x: (x.diameter_mm, x.code))
        if not belts:
            excluded += len(pulleys)
            continue
        if not pulleys:
            excluded += len(belts)
            continue
        for driver in pulleys:
            for driven in pulleys:
                if stopped():
                    break
                work += 1; pairs += 1
                if progress is not None and work % 100 == 0:
                    progress(pairs, evaluated)
                d1, d2 = driver.diameter_mm, driven.diameter_mm
                if any(outside(d, request.diameter_min_mm, request.diameter_max_mm) for d in (d1, d2)):
                    reject(driver, driven, None, 'PULLEY_DIAMETER'); continue
                if any(d is not None and outside(d, None, request.outside_diameter_max_mm) for d in
                        (driver.outside_diameter_mm, driven.outside_diameter_mm)):
                    reject(driver, driven, None, 'OUTSIDE_DIAMETER'); continue
                if request.family == 'timing' and any(outside(z, request.teeth_min, request.teeth_max) for z in (driver.teeth, driven.teeth)):
                    reject(driver, driven, None, 'PULLEY_TEETH'); continue
                try:
                    ratio = positive(driven.teeth / driver.teeth if request.family == 'timing' else d2 / d1, 'Aday oranı')
                    n2 = positive(request.input_rpm / ratio, 'Aday çıkış devri')
                    deviation = n2 - request.target_rpm
                    error = positive(abs(deviation) / request.target_rpm * 100., 'Devir hatası') if deviation else 0.
                except (ValueError, OverflowError, ZeroDivisionError) as caught:
                    reject(driver, driven, None, 'PAIR_CALCULATION', str(caught)); continue
                if outside(error, None, request.rpm_error_max_percent):
                    reject(driver, driven, None, 'RPM_TOLERANCE'); continue
                physical_min = d1/2 + d2/2
                if upper is not None and upper <= physical_min:
                    reject(driver, driven, None, 'CENTER_GEOMETRY'); continue
                # Cheap length bounds eliminate impossible catalogue lengths before inverse solving.
                try:
                    min_length = length_metrics(d1, d2, max(physical_min, lower or physical_min)).exact_mm
                    max_length = length_metrics(d1, d2, upper).exact_mm if upper is not None else None
                    target_length = length_metrics(d1, d2, request.center_target_mm).exact_mm \
                        if request.center_target_mm is not None and request.center_target_mm > physical_min else None
                except (ValueError, OverflowError, ZeroDivisionError) as caught:
                    reject(driver, driven, None, 'PAIR_GEOMETRY', str(caught)); continue
                count = 1 if request.family == 'timing' else driver.grooves if driver.grooves == driven.grooves else None
                if request.family == 'v' and driver.grooves is not None and driven.grooves is not None and driver.grooves != driven.grooves:
                    reject(driver, driven, None, 'GROOVE_COMPATIBILITY'); continue
                if count is not None and request.max_belts is not None and count > request.max_belts:
                    reject(driver, driven, None, 'BELT_COUNT'); continue
                for belt in belts:
                    if stopped():
                        break
                    work += 1; evaluated += 1
                    # Ratings belong to the BELT series, never the pulley series.
                    table = tables.get((belt.series_id, belt.profile))
                    if progress is not None and work % 100 == 0:
                        progress(pairs, evaluated)
                    if outside(belt.length_mm, min_length, max_length):
                        reject(driver, driven, belt, 'LENGTH_CENTER_BOUNDS'); continue
                    if request.family == 'timing' and any(width is not None and belt.width_mm > width for width in
                            (driver.face_width_mm, driven.face_width_mm, driver.nominal_belt_width_mm, driven.nominal_belt_width_mm,
                             driver.overall_width_mm, driven.overall_width_mm)):
                        reject(driver, driven, belt, 'FACE_WIDTH'); continue
                    widths = (driver.overall_width_mm, driven.overall_width_mm)
                    known_widths = tuple(x for x in (*widths, belt.width_mm) if x is not None)
                    width_lower_bound = max(known_widths) if known_widths else None
                    width = None
                    if known_widths and outside(max(known_widths), None, request.system_width_max_mm):
                        reject(driver, driven, belt, 'SYSTEM_WIDTH'); continue
                    try:
                        if request.family=='timing' and any(p.axial_min_mm is not None and
                                (outside(-belt.width_mm/2,p.axial_min_mm,p.axial_max_mm) or
                                 outside(belt.width_mm/2,p.axial_min_mm,p.axial_max_mm)) for p in (driver,driven)):
                            reject(driver,driven,belt,'AXIAL_BELT_PLANE');continue
                        if all(p.axial_min_mm is not None for p in (driver,driven)):
                            lower_z=min(driver.axial_min_mm,driven.axial_min_mm,-belt.width_mm/2 if belt.width_mm else 0.)
                            upper_z=max(driver.axial_max_mm,driven.axial_max_mm,belt.width_mm/2 if belt.width_mm else 0.)
                            width=positive(upper_z-lower_z,'Gerçek beyan edilen eksenel zarf')
                            if outside(width,None,request.system_width_max_mm):
                                reject(driver,driven,belt,'SYSTEM_WIDTH');continue
                        result = calculate(candidate_specification(request, driver, driven, belt, count), stop=stop)
                        solved += 1
                        failed_limit = operating_limit_failure(request, result)
                        if failed_limit:
                            reject(driver, driven, belt, failed_limit); continue
                        if outside(result.center_mm, lower, upper):
                            reject(driver, driven, belt, 'CENTER_BOUNDS'); continue
                        outer = (driver.outside_diameter_mm, driven.outside_diameter_mm)
                        if all(x is not None for x in outer) and result.center_mm <= outer[0]/2 + outer[1]/2:
                            reject(driver, driven, belt, 'OUTER_BODY_CLEARANCE'); continue
                        small = min(driver.teeth, driven.teeth) if request.family == 'timing' else min(d1, d2)
                        if table and table.minimum_pulley is not None and outside(small, table.minimum_pulley, None):
                            reject(driver, driven, belt, 'DECLARED_MINIMUM_PULLEY'); continue
                        if table and table.maximum_speed_m_s is not None and outside(result.speed_m_s, None, table.maximum_speed_m_s):
                            reject(driver, driven, belt, 'DECLARED_SPEED_LIMIT'); continue
                        capacity = provider.evaluate(catalog, belt, result, count)
                        if capacity.meets_declared_demand is False:
                            reject(driver, driven, belt, 'DECLARED_INSUFFICIENT_CAPACITY'); continue
                        travel_rejected = False
                        for supplied, required in ((request.available_installation_travel_mm, capacity.installation_allowance_mm),
                                                   (request.available_tensioning_travel_mm, capacity.tensioning_allowance_mm)):
                            if supplied is not None and required is not None and outside(required, None, supplied):
                                reject(driver, driven, belt, 'ADJUSTMENT_TRAVEL'); travel_rejected = True; break
                        if travel_rejected:
                            continue
                        offset = result.center_mm - request.center_target_mm if request.center_target_mm is not None else None
                        area = positive((result.center_mm + d1/2 + d2/2) * max(d1, d2), 'Referans çizgisi alanı')
                        source_ids = {driver.source_id, driven.source_id, belt.source_id}
                        if capacity.source_id:
                            source_ids.add(capacity.source_id)
                        sources = tuple(catalog.source(x) for x in sorted(source_ids))
                        statuses = tuple(x.effective_status for x in sources)
                        checks = [Issue('CATALOG_COMPATIBILITY', 'Ürünler aynı üretici, profil ve açık uyumluluk kimliğinde beyan edildi; ticari seri adı ürün uygunluğu onayı değildir.', severity='NOT_EVALUATED'),
                                  Issue('TENSION', 'Germe prosedürü, gerçek mil/yatak yükleri ve tasarım ömrü doğrulanmadı.', severity='NOT_EVALUATED')]
                        for missing, code, message in (
                            (width is None, 'SYSTEM_WIDTH', 'Toplam eksenel genişlik bilinmiyor.'),
                            (driver.outside_diameter_mm is None or driven.outside_diameter_mm is None, 'OUTSIDE_CLEARANCE', 'Dış çap/flanş zarfı ve gövde boşluğu tamamen doğrulanmadı.'),
                            (count is None, 'BELT_COUNT', 'Kasnak kanal adedi bilinmiyor; nominal geometri tek kayışla temsil edildi.'),
                            (table is None or table.minimum_pulley is None, 'MINIMUM_PULLEY', 'Üretici minimum kasnak sınırı yok.'),
                            (table is None or table.maximum_speed_m_s is None, 'SPEED_LIMIT', 'Üretici hız sınırı yok.'),
                            (capacity.installation_allowance_mm is None or capacity.tensioning_allowance_mm is None, 'ADJUSTMENT_TRAVEL', 'Kurulum/germe için gerekli ayar mesafesi bilinmiyor.'),
                            (request.service_factor is None, 'SERVICE_FACTOR', 'Servis faktörü çalışma koşullarından otomatik seçilmedi.'),
                        ):
                            if missing:
                                checks.append(Issue(code, message, severity='NOT_EVALUATED'))
                        if request.family == 'v':
                            checks.append(Issue('SLIP', 'Çıkış devri idealdir; V kayışında kayma/sürünme bilinmiyor.', severity='NOT_EVALUATED'))
                        checks.extend(capacity.checks)
                        legacy_group = (group[0], belt.series_id, belt.profile, belt.compatibility_id)
                        identity = (legacy_group, driver.code, driven.code, belt.code)
                        identifiers = (group[0], belt.series_id, driver.code, driven.code, belt.code)
                        if driver.series_id != belt.series_id or driven.series_id != belt.series_id:
                            identity += (driver.series_id, driven.series_id)
                            identifiers += (driver.series_id, driven.series_id)
                        key = ranking_key(request, error=error, center_deviation=offset, area=area, count=count, width=width,
                            margin=capacity.capacity_margin, source_statuses=statuses,
                            identifiers=identifiers)
                        # An evaluated sufficient capacity takes precedence over
                        # an unknown capacity; neither is manufacturer approval.
                        key = (0 if capacity.meets_declared_demand is True else 1, *key)
                        power_verified = capacity.manufacturer_verified and all(x.officially_verified for x in sources)
                        candidate = DesignCandidate(json.dumps(identity, ensure_ascii=False),
                            catalog.source(belt.source_id).manufacturer, belt.series_id, driver, driven, belt, result,
                            deviation, error, target_length, offset, count, width, area, capacity, statuses, tuple(checks),
                            'CAPACITY_VERIFIED' if power_verified else 'UNVERIFIED', key,
                            system_width_lower_bound_mm=width_lower_bound)
                    except CalculationCancelled:
                        cancelled = True; stop_reason = 'Kullanıcı iptali; arama tamamlanmadı.'; break
                    except (SpecificationError, ValueError, OverflowError) as caught:
                        reject(driver, driven, belt, 'CALCULATION', str(caught)); continue
                    if power_verified:
                        verified_count += 1; retain(verified, candidate)
                    else:
                        unverified_count += 1
                        if request.include_unverified:
                            retain(unverified, candidate)
                if cancelled or limited:
                    break
            if cancelled or limited:
                break
        if cancelled or limited:
            break
    return DesignSearchReport(request, catalog.identifier, catalog.revision, fingerprint(catalog),
        request.input_rpm / request.target_rpm, tuple(x[1] for x in verified), tuple(x[1] for x in unverified),
        tuple(rejections), pairs, evaluated, solved, verified_count, unverified_count, tuple(sorted(counts.items())), excluded,
        not (cancelled or limited), verified_count > len(verified) or request.include_unverified and unverified_count > len(unverified) or sum(counts.values()) > len(rejections),
        cancelled, stop_reason, (
            'Yalnız katalogda beyan edilen SKU/diş/çap/uzunluklar taranır; stok veya fiyat verisi yoktur.',
            'Üretici onayı olmayan adaylar ayrı gruptadır; tam mühendislik uygunluğu verilmez.',
            'Sıralama sert kısıtlardan sonra uygulanır; referans alanı gerçek dış zarf değildir.',
            'Aralık karşılaştırmaları yalnız sayısal hassasiyet için ilgili birimde 1e-9 mutlak / 1e-12 bağıl tolerans kullanır.',
            'Koşullar saklanır; doğrulanmış servis faktörü tablosu olmadığından otomatik katsayı seçilmez.',
        ), sources=catalog.sources)
