"""Input validity is separate from strength, life or manufacturing approval."""

from ._numbers import finite, positive, integer
from .catalog.profiles import get_profile
from .models import (BeltDriveSpecification, BeltSpecification, PulleySpecification,
                     LoadSpecification, CenterSpecification, Issue, SpecificationError)


class CalculationCancelled(RuntimeError):
    pass


def issues(spec):
    errors = []

    def error(code, message, field):
        errors.append(Issue(code, message, field))

    def number(value, field, check=positive):
        try:
            check(value, field)
        except ValueError as caught:
            error('INPUT_NUMBER', str(caught), field)

    if not isinstance(spec, BeltDriveSpecification):
        return (Issue('INPUT_TYPE', 'BeltDriveSpecification gerekli.'),)
    for name, cls in (('belt', BeltSpecification), ('driver', PulleySpecification), ('driven', PulleySpecification),
                      ('load', LoadSpecification), ('center', CenterSpecification)):
        if not isinstance(getattr(spec, name), cls):
            error('INPUT_TYPE', f'{name}: {cls.__name__} gerekli.', name)
    if errors:
        return tuple(errors)
    if spec.drive_type != 'open':
        error('UNSUPPORTED_LAYOUT', 'Aşama 1 yalnız iki kasnaklı açık kayış destekler.', 'drive_type')
    if spec.rotation not in ('ccw', 'cw'):
        error('ROTATION', 'Dönüş yönü ccw veya cw olmalı.', 'rotation')
    belt, load, center = spec.belt, spec.load, spec.center
    profile = None
    try:
        profile = get_profile(belt.profile)
    except ValueError as caught:
        error('PROFILE', str(caught), 'belt.profile')
    if profile:
        if belt.family != profile.family:
            error('PROFILE_FAMILY', 'Profil ile kayış ailesi uyuşmuyor.', 'belt.family')
        if not profile.nominal_supported:
            error('UNSUPPORTED_PROFILE', profile.limitation, 'belt.profile')
    number(belt.count, 'belt.count', integer)
    if belt.family == 'v':
        if belt.pitch_mm is not None:
            error('REFERENCE_MISMATCH', 'V kayışı adımla değil datum çap/uzunlukla tanımlanır.', 'belt.pitch_mm')
        for name in ('driver', 'driven'):
            pulley = getattr(spec, name)
            number(pulley.datum_diameter_mm, name + '.datum_diameter_mm')
            if pulley.teeth is not None:
                error('REFERENCE_MISMATCH', 'V kasnağı için diş sayısı verilmez.', name + '.teeth')
    elif belt.family == 'timing':
        for name in ('driver', 'driven'):
            pulley = getattr(spec, name)
            number(pulley.teeth, name + '.teeth', integer)
            if pulley.datum_diameter_mm is not None:
                error('REFERENCE_MISMATCH', 'Triger-senkron kasnakta diş sayısı kullanın; datum çapı verilmez.', name + '.datum_diameter_mm')
        if belt.pitch_mm is not None:
            number(belt.pitch_mm, 'belt.pitch_mm')
            if profile and belt.pitch_mm != profile.pitch_mm:
                error('PROFILE_PITCH', 'Adım seçilen profil ile aynı olmalı; HTD/T/AT birbirinin yerine kullanılamaz.', 'belt.pitch_mm')
    elif belt.family != 'poly_v':
        error('FAMILY', 'Bilinmeyen kayış ailesi.', 'belt.family')
    number(load.input_rpm, 'load.input_rpm')
    if (load.power_kw is None) == (load.torque_nm is None):
        error('LOAD_BASIS', 'Güç veya torktan yalnız birini verin; ikisini bağımsız girmeyin.', 'load')
    for name in ('power_kw', 'torque_nm', 'service_factor', 'efficiency'):
        value = getattr(load, name)
        if value is not None:
            number(value, 'load.' + name)
    if type(load.efficiency) in (int, float) and load.efficiency > 1:
        error('EFFICIENCY', 'Verim 0 < η ≤ 1 aralığında olmalı.', 'load.efficiency')
    if center.mode == 'center':
        number(center.distance_mm, 'center.distance_mm')
        if center.length_mm is not None or center.belt_teeth is not None:
            error('CENTER_BASIS', 'Eksen mesafesi modunda bağımsız uzunluk/diş adedi verilmez.', 'center')
    elif center.mode == 'length':
        if center.distance_mm is not None:
            error('CENTER_BASIS', 'Uzunluktan çözümde bağımsız eksen mesafesini boş bırakın.', 'center.distance_mm')
        if belt.family == 'v':
            number(center.length_mm, 'center.length_mm')
            if center.belt_teeth is not None:
                error('REFERENCE_MISMATCH', 'V kayışı uzunluğu mm datum uzunluğudur.', 'center.belt_teeth')
        elif belt.family == 'timing':
            number(center.belt_teeth, 'center.belt_teeth', integer)
            if center.length_mm is not None:
                error('REFERENCE_MISMATCH', 'Triger-senkron kayışta tam N diş verin; bölüm uzunluğu N×p hesaplanır.', 'center.length_mm')
    else:
        error('CENTER_MODE', 'Eksen yöntemi center veya length olmalı.', 'center.mode')
    for name in ('driver_x_mm', 'driver_y_mm', 'axis_angle_deg'):
        number(getattr(center, name), 'center.' + name, finite)
    if spec.pretension_per_belt_n is not None:
        number(spec.pretension_per_belt_n, 'pretension_per_belt_n')
    return tuple(errors)


def require_valid(spec):
    result = issues(spec)
    if result:
        raise SpecificationError(result)
