"""Nominal two-pulley calculation, independent from GUI/CAD/product ratings."""

import math
from ._numbers import checked, positive
from .catalog.profiles import get_profile
from .engineering.belt_length import solve_center_distance
from .engineering.kinematics import pitch_diameter_mm, transmission_ratio, belt_speed_m_s, torque_nm, power_kw
from .engineering.forces import effective_force_delta_n, simplified_shaft_forces
from .geometry import Point, open_belt_path
from .models import BeltDriveResult, Issue, SpecificationError
from .validation import require_valid, CalculationCancelled


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise CalculationCancelled('Kayış hesabı durduruldu.')


def _checks(spec, theoretical_teeth, shaft_forces):
    result = [Issue('NOMINAL_MODEL', 'İdeal, rijit ve kaymasız iki kasnaklı kinematik modeldir.', severity='INFO')]
    missing = (
        ('POWER_CAPACITY', 'Üretici güç tablosu ve çap/sarılma/uzunluk düzeltme katsayıları doğrulanmadı.'),
        ('BELT_COUNT_SIZING', 'Kayış adedi kullanıcı girdisidir; gerekli adet güç kapasitesinden seçilmedi.'),
        ('CATALOG_DIMENSION', 'Tamsayı diş veya hesaplanan uzunluk tek başına katalog ürünü olduğunu göstermez.'),
        ('MANUFACTURER_TENSION', 'Üretici germe prosedürü ve izin verilen kayış gerilmeleri bilinmiyor.'),
        ('BEARING_REACTIONS', 'Yatak konumları, mil modeli, ağırlık ve diğer yükler olmadan yatak reaksiyonu bulunamaz.'),
        ('SPEED_LIMIT', 'Bu profil/ürün için doğrulanmış izin verilen hız aralığı yok.'),
        ('MINIMUM_PULLEY', 'Üreticiye özgü minimum kasnak/diş sayısı doğrulanmadı.'),
        ('WRAP_CAPACITY', 'Sarılma açısının güç kapasitesine etkisi üretici katsayıları olmadan değerlendirilmedi.'),
        ('LIFE_AND_MATERIAL', 'Ömür, malzeme dayanımı, sıcaklık ve çalışma koşulları değerlendirilmedi.'),
        ('MANUFACTURING', 'Kanal/diş profili, dış çap boşluğu ve CAD geometrisi doğrulanmadı.'),
    )
    result += [Issue(code, message, severity='NOT_EVALUATED') for code, message in missing]
    if spec.belt.family == 'v':
        result.append(Issue('ACTUAL_OUTPUT_SPEED', 'V kayışında kayma ve sürünme bilinmiyor; çıkış devri yalnız idealdir.', severity='NOT_EVALUATED'))
    if spec.load.efficiency is None:
        result.append(Issue('EFFICIENCY', 'Verim verilmedi; gerçek çıkış gücü/torku tahmin edilmedi.', severity='NOT_EVALUATED'))
    else:
        result.append(Issue('USER_EFFICIENCY', 'η kullanıcı girdisidir; η ile tork nominal çıkış devrinde hesaplandı.', severity='INFO'))
    if spec.load.service_factor is None:
        result.append(Issue('SERVICE_FACTOR', 'Doğrulanmış servis faktörü verilmedi; tasarım gücü hesaplanmadı.', severity='NOT_EVALUATED'))
    else:
        result.append(Issue('USER_SERVICE_FACTOR', 'Servis faktörü kullanıcı girdisidir; çalışma koşullarından otomatik seçilmedi.', severity='INFO'))
        if spec.load.service_factor < 1:
            result.append(Issue('REDUCED_DESIGN_POWER', 'Servis faktörü 1’den küçük; nominal gücü azaltıyor.', severity='WARNING'))
    if shaft_forces is None:
        result.append(Issue('SHAFT_FORCE', 'F₀ bilinmiyor; yalnız Ft=F₁−F₂ bilinir. Mil bileşkesi hesaplanmadı.', severity='NOT_EVALUATED'))
    else:
        result.append(Issue('SIMPLIFIED_TENSION', 'F₁/F₂ ve mil bileşkesi nominal güçte, sabit ortalama germe/eşit yük paylaşımı tahminidir.', severity='INFO'))
    if theoretical_teeth is not None and spec.center.mode == 'center':
        result.append(Issue('UNSELECTED_TIMING_LENGTH', 'Teorik N=L/p kesirli olabilir; katalog seçimi yapılmadı ve N yuvarlanmadı.', severity='WARNING'))
    return tuple(result)


def calculate(spec, *, stop=None):
    checkpoint(stop)
    require_valid(spec)
    profile = get_profile(spec.belt.profile)
    timing = spec.belt.family == 'timing'
    pitch = profile.pitch_mm if timing else None
    try:
        d1 = pitch_diameter_mm(spec.driver.teeth, pitch) if timing else spec.driver.datum_diameter_mm
        d2 = pitch_diameter_mm(spec.driven.teeth, pitch) if timing else spec.driven.datum_diameter_mm
        selected_length = residual = selected_teeth = None
        if spec.center.mode == 'length':
            selected_teeth = spec.center.belt_teeth if timing else None
            selected_length = positive(selected_teeth * pitch if timing else spec.center.length_mm, 'Seçilen uzunluk')
            solution = solve_center_distance(d1, d2, selected_length, stop=stop)
            center, residual = solution.center_mm, solution.residual_mm
        else:
            center = spec.center.distance_mm
        geometry = open_belt_path(d1, d2, center,
            origin=Point(spec.center.driver_x_mm, spec.center.driver_y_mm),
            angle_rad=math.radians(math.remainder(spec.center.axis_angle_deg, 360.)))
        metric = geometry.metrics
        ratio = (spec.driven.teeth / spec.driver.teeth) if timing else transmission_ratio(d1, d2)
        ratio = positive(ratio, 'Aktarma oranı')
        output_rpm = positive(spec.load.input_rpm / ratio, 'Nominal çıkış devri')
        power = spec.load.power_kw if spec.load.power_kw is not None else power_kw(spec.load.torque_nm, spec.load.input_rpm)
        torque = spec.load.torque_nm if spec.load.torque_nm is not None else torque_nm(power, spec.load.input_rpm)
        output_torque = positive(torque * ratio, 'İdeal çıkış torku')
        speed = belt_speed_m_s(d1, spec.load.input_rpm)
        effective = effective_force_delta_n(power, speed)
        eta, service = spec.load.efficiency, spec.load.service_factor
        output_power_eta = positive(power * eta, 'η ile çıkış gücü') if eta is not None else None
        output_torque_eta = positive(output_torque * eta, 'η ile nominal devirde çıkış torku') if eta is not None else None
        design_power = positive(power * service, 'Tasarım gücü') if service is not None else None
        design_force = positive(effective * service, 'Tasarım etkin kuvvet farkı') if service is not None else None
        shaft = simplified_shaft_forces(geometry, effective, spec.pretension_per_belt_n, spec.belt.count, spec.rotation) \
            if spec.pretension_per_belt_n is not None else None
        teeth = positive(metric.exact_mm / pitch, 'Teorik kayış diş sayısı') if timing else None
        engaged1 = spec.driver.teeth * (metric.driver_wrap_rad / (2. * math.pi)) if timing else None
        engaged2 = spec.driven.teeth * (metric.driven_wrap_rad / (2. * math.pi)) if timing else None
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise SpecificationError((Issue('GEOMETRY_OR_LOAD', str(error), 'geometry/load'),)) from error
    checkpoint(stop)
    assumptions = (
        f'Çaplar ve uzunluklar aynı {profile.reference_line} referans çizgisindedir; birimler mm.',
        'İki paralel eksen, dış ortak teğetler; kayış kalınlığı, elastik uzama, titreşim ve dinamik geçişler yok.',
        'Referans çemberleri ayrıdır; gerçek dış çap/flanş boşluğu ve üretim uygunluğu onaylanmaz.',
        'Ft nominal güçteki toplam etkin kuvvet F₁−F₂ farkıdır; F₀, F₁+F₂ veya yatak yükü değildir.',
        'η uygulanmış tork nominal kaymasız devir içindir; ölçülmüş gerçek performans değildir.',
    )
    return BeltDriveResult(spec, profile.reference_line, float(d1), float(d2), pitch, ratio, output_rpm,
        float(power), float(torque), output_torque, output_power_eta, output_torque_eta, design_power, speed,
        effective, design_force, metric.center_mm, metric.exact_mm, metric.approximate_mm,
        checked(metric.approximate_mm - metric.exact_mm, 'Yaklaşım farkı'), selected_length, residual,
        math.degrees(metric.driver_wrap_rad), math.degrees(metric.driven_wrap_rad), teeth, selected_teeth,
        engaged1, engaged2, shaft, geometry, _checks(spec, teeth, shaft), assumptions)
