"""Central bounds and engineering scope checks; no ISO/AGMA strength claim."""

from dataclasses import asdict
from math import isfinite, radians, sin
from .models import GearSpecification, GearPairSpecification, FutureGearData, LoadSpecification, Issue

MAX_TEETH = 300
MAX_DIAMETER_MM = 6000.0
PREFERRED_MODULES = (.1,.12,.15,.2,.25,.3,.4,.5,.6,.8,1.,1.25,1.5,2.,2.5,3.,4.,5.,6.,8.,10.,12.,16.,20.)


class SpecificationError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__('\n'.join(i.message for i in self.issues))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def gear_issues(spec, prefix=''):
    if not isinstance(spec, GearSpecification):
        return [Issue('specification', 'Tip güvenli GearSpecification gerekli.', prefix)]
    issues = []
    def error(code, message, key):
        issues.append(Issue(code, message, prefix+key))
    limits = [('module_mm', .1, 20., 'Modül m'), ('pressure_angle_deg', 14.5, 30., 'Basınç açısı α'),
              ('face_width_mm', .1, 500., 'Diş genişliği b'), ('bore_mm', 0., 5999., 'Delik çapı')]
    for key, low, high, title in limits:
        v = getattr(spec, key)
        if not finite(v) or not low <= v <= high:
            error('range', f'{title}, {low:g}–{high:g} aralığında sonlu bir sayı olmalı.', key)
    if type(spec.teeth) is not int or not 6 <= spec.teeth <= MAX_TEETH:
        error('teeth', f'Diş sayısı tam sayı ve 6–{MAX_TEETH} aralığında olmalı.', 'teeth')
    if spec.gear_type != 'external_spur':
        error('unsupported', 'Bu sürüm yalnız dıştan kavraşan düz dişliyi destekler.', 'gear_type')
    for key in ('profile_shift', 'helix_angle_deg', 'backlash_mm'):
        if not finite(getattr(spec, key)) or getattr(spec, key) != 0:
            error('unsupported', 'Profil kaydırma, helis açısı ve diş boşluğu bu sürümde sıfır olmalı.', key)
    if not isinstance(spec.future, FutureGearData) or any(v is not None for v in asdict(spec.future).values()):
        error('unsupported', 'İleri malzeme/kalite/normal düzlem alanları bu sürümde etkin değildir.', 'future')
    if issues:
        return issues
    if spec.module_mm*(spec.teeth+2) > MAX_DIAMETER_MM:
        error('diameter_limit', 'Diş üstü çapı 6000 mm model sınırını aşıyor.', 'module_mm')
    # Leave at least a small positive web below the entire tooth root.
    root = spec.module_mm*(spec.teeth-2.5)
    if spec.bore_mm > 0 and root-spec.bore_mm < max(.2, .1*spec.module_mm)*2:
        error('bore', 'Delik, diş dibi altında en az max(0,2 mm; 0,1 m) radyal et bırakmalı.', 'bore_mm')
    critical = 2 / sin(radians(spec.pressure_angle_deg))**2
    if spec.teeth < critical:
        issues.append(Issue('undercut', f'z = {spec.teeth}; alttan kesilme riski var (x=0 için sınır ≈ {critical:.2f}). '
            'Trokoidal dip modellenmediğinden CAD ve hareket bu değerlerde kapalıdır.', prefix+'teeth', 'warning'))
    if not any(abs(spec.pressure_angle_deg-a)<1e-9 for a in (14.5,20.,25.)):
        issues.append(Issue('custom_angle', 'Standart seri dışı basınç açısı; kesici takım uygunluğu ayrıca doğrulanmalı.', prefix+'pressure_angle_deg', 'warning'))
    if not any(abs(spec.module_mm-m)<1e-9 for m in PREFERRED_MODULES):
        issues.append(Issue('custom_module', 'Tercih edilen modül listesinin dışında; kesici takım tedarikini doğrulayın.', prefix+'module_mm', 'warning'))
    return issues


def pair_issues(spec):
    if not isinstance(spec, GearPairSpecification):
        return [Issue('specification', 'Tip güvenli GearPairSpecification gerekli.')]
    issues = gear_issues(spec.pinion,'pinion.') + gear_issues(spec.wheel,'wheel.')
    if not any(i.severity=='error' for i in issues):
        if abs(spec.pinion.module_mm-spec.wheel.module_mm) > 1e-10:
            issues.append(Issue('module_mismatch', 'Kavraşan dişlilerin modülleri aynı olmalı.', 'wheel.module_mm'))
        if abs(spec.pinion.pressure_angle_deg-spec.wheel.pressure_angle_deg) > 1e-10:
            issues.append(Issue('angle_mismatch', 'Kavraşan dişlilerin basınç açıları aynı olmalı.', 'wheel.pressure_angle_deg'))
        if abs(spec.pinion.face_width_mm-spec.wheel.face_width_mm) > 1e-10:
            issues.append(Issue('width_mismatch', 'MVP dişli çiftinde diş genişlikleri aynı olmalı.', 'wheel.face_width_mm'))
    load = spec.load
    if not isinstance(load, LoadSpecification):
        return issues+[Issue('load', 'Tip güvenli yük verisi gerekli.', 'load')]
    for key,low,high in (('application_factor',1.,10.),('design_life_hours',1.,1e7)):
        v=getattr(load,key)
        if not finite(v) or not low<=v<=high:
            issues.append(Issue('load', 'Uygulama faktörü/ömür sonlu ve izin verilen aralıkta olmalı.', 'load.'+key))
    if not finite(load.input_rpm) or not .001<=abs(load.input_rpm)<=100000:
        issues.append(Issue('speed', 'Giriş devrinin büyüklüğü 0,001–100.000 dev/dak olmalı.', 'load.input_rpm'))
    if load.mode not in ('power','torque'):
        issues.append(Issue('load_mode','Birincil yük olarak güç veya tork seçin.','load.mode'))
    else:
        primary,other=('power_kw','torque_nm') if load.mode=='power' else ('torque_nm','power_kw')
        v=getattr(load,primary)
        if not finite(v) or not 0<v<=1e7:
            issues.append(Issue('load','Seçilen güç/tork sıfırdan büyük ve sonlu olmalı.','load.'+primary))
        if getattr(load,other) is not None:
            issues.append(Issue('conflicting_load','Güç ve tork birlikte girilemez; tek bir birincil yük seçin.','load.'+other))
    return issues


def require_valid(issues):
    errors=[i for i in issues if i.severity=='error']
    if errors:
        raise SpecificationError(errors)


def require_manufacturable(result):
    """MVP cannot generate a credible undercut root: reject instead of faking it."""
    unsupported=[i for i in result.warnings if i.code in ('undercut','interference','contact_ratio')]
    if unsupported:
        raise SpecificationError(unsupported)
