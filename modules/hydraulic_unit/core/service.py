"""Bütün HPU hesaplarını birleştiren, UI'dan bağımsız servis."""
from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import json
import logging
import math
from .models import Project
from .validation import Issue, number, choice, InputError
from .cycle import calculate_cycle
from .pump_motor import pump_flow
from .piping import pipe_result
from .tank_thermal import thermal_result
from .accumulator import accumulator_result
from .catalogs import PUMP_DEFAULTS, SOURCE_NOTE


@dataclass(frozen=True)
class ProjectResult:
    cycle: dict
    pipe: dict
    thermal: dict
    accumulator: dict
    issues: tuple[Issue, ...]
    assumptions: tuple[str, ...]
    feasible: bool
    input_fingerprint: str


def _calculate_project(project: Project) -> ProjectResult:
    try:
        fingerprint = hashlib.sha256(json.dumps(asdict(project), sort_keys=True, allow_nan=False,
                                                ensure_ascii=False).encode('utf-8')).hexdigest()
    except (ValueError, TypeError) as exc:
        raise InputError('project', 'Proje sonlu, serileştirilebilir SI girdileri içermeli.') from exc
    if not isinstance(project.name, str) or not project.name.strip():
        raise InputError('name', 'Proje adı boş olamaz.')
    choice(project.display_units, ('metric','us'), 'display_units')
    cycle = calculate_cycle(project)
    q = pump_flow(project.pump)
    # Ortak tank dönüşü: silindir dönüşü + valften/by-pass'tan dönen fazla
    # pompa debisi. Yalnız silindir dönüşüyle boyutlandırmak beklemede eksiktir.
    tank_return = max(r.return_flow + max(0., r.supply_flow - r.flow) for r in cycle['phases'])
    cycle['max_tank_return_flow'] = tank_return
    cycle['demand_met'] = all(r.feasible for r in cycle['phases'])
    line_q = q if project.pipe.role == 'suction' else tank_return if project.pipe.role == 'return' else cycle['max_flow']
    pipe = pipe_result(project.pipe, line_q, project.oil)
    thermal = thermal_result(project.thermal, q, cycle['average_loss'])
    thermal['status'] = 'calculated' if cycle['demand_met'] and cycle['repeatable_geometry'] else 'scenario_only'
    accumulator = accumulator_result(project.accumulator)
    issues = list(cycle.pop('issues'))
    if cycle['relief_pressure'] > project.pump.max_pressure:
        issues.append(Issue('RELIEF_LIMIT', 'Emniyet valfi ayarı pompanın tanımlı azami basıncını aşıyor.', 'relief_pressure', 'critical'))
    issues.append(Issue('MANUFACTURER_NOT_EVALUATED',
        'Üretici pompa eğrisi, motor görev sınıfı ve boru/hortum basınç dayanımı doğrulanmadı.', '', 'info'))
    if pipe['diameter'] is None:
        issues.append(Issue('PIPE_SERIES', 'Boru çapı nominal seri dışında.', 'pipe.diameter', 'critical'))
    elif line_q and not project.pipe.min_velocity <= pipe['velocity'] <= project.pipe.max_velocity:
        issues.append(Issue('VELOCITY', 'Hat hızı kullanıcı sınırlarının dışında.', 'pipe', 'warning'))
    if pipe['regime'] in ('transition','outside_blasius'):
        issues.append(Issue('FRICTION_MODEL', 'Akış modeli doğrulanmış aralığın dışında; kayıp yaklaşık ön tahmindir.', 'pipe'))
    if project.pipe.role == 'suction':
        issues.append(Issue('CAVITATION', 'Kavitasyon uygunluğu değerlendirilmedi: giriş mutlak basıncı, kot ve üretici emiş limiti gerekli.', 'pipe', 'warning'))
    if not 313.15 <= project.oil.temperature <= 373.15:
        issues.append(Issue('OIL_EXTRAPOLATION', 'Viskozite 40–100 °C dışında ekstrapole edildi.', 'oil.temperature'))
    if thermal['usable_volume'] < thermal['required_volume']:
        issues.append(Issue('TANK_VOLUME', 'Kullanılabilir tank hacmi seçilen kalma süresine göre yetersiz.', 'thermal'))
    low, high = (180.,300.) if project.thermal.installation == 'stationary' else (60.,120.)
    if not low <= project.thermal.residence_time <= high:
        issues.append(Issue('TANK_RESIDENCE', 'Kalma süresi tipik ön tasarım aralığının dışında; montaj koşullarını doğrulayın.', 'thermal.residence_time'))
    if thermal['equilibrium_temperature'] > project.thermal.target:
        issues.append(Issue('COOLER', 'Hedef sıcaklık için soğutucu gerekiyor.', 'thermal'))
    if thermal['equilibrium_temperature'] > 333.15:
        issues.append(Issue('HOT_OIL', 'Soğutucusuz denge sıcaklığı 60 °C üzerinde.', 'thermal', 'critical'))
    if project.pump.max_pressure > PUMP_DEFAULTS[project.pump.kind][2]:
        issues.append(Issue('PUMP_TYPE', 'Pompa ayarı tipik ön tasarım basıncını aşıyor; üretici doğrulaması gerekli.', 'pump.max_pressure'))
    motor = cycle['motor']['nominal'] if project.selected_motor is None else number(project.selected_motor, 'selected_motor')
    if motor is None:
        issues.append(Issue('MOTOR_SERIES', 'Gerekli motor gücü nominal seri dışında.', 'selected_motor', 'critical'))
    elif motor < cycle['rms_power'] or motor * (1 + project.overload) < cycle['peak_power']:
        issues.append(Issue('MOTOR_SMALL', 'Motor RMS veya tepe yükünü karşılamıyor.', 'selected_motor', 'critical'))
    cycle['selected_motor'] = motor
    if cycle['displacement']['nominal'] is None:
        issues.append(Issue('PUMP_SERIES', 'Gerekli deplasman nominal seri dışında.', 'pump.displacement'))
    if accumulator.get('status') == 'calculated' and accumulator['nominal_volume'] is None:
        issues.append(Issue('ACC_SERIES', 'Akümülatör ihtiyacı nominal hacim serisinin dışında.', 'accumulator'))
    assumptions = (SOURCE_NOTE, 'Ardışık, direnç yükü altında nominal statik hesap; dinamik/servo çözümü değildir.',
        'Sabit pompada kısılmış harekette ve beklemede fazla debi emniyet valfinden geçer.',
        'Isı ve güç: mil girişi eksi faydalı mekanik iş; kayıplar iki kez sayılmaz.',
        'Seçili basınç hattı valf-sonrası silindir hattıdır. Bunun kaybı çevrime eklenir; diğer hatlar ayrıca tasarlanmalıdır.',
        'Ortak tank dönüş hesabı silindir çıkışı ve valften/by-pass hattından gelen fazla debiyi içerir.',
        'Pompa ihtiyacı karşılamıyorsa ısı sonuçları scenario_only: erişilmiş performans değildir.',
        'Kaçak sıfırsa bekleme ideal kabul edilir; gerçek pompa standby kaybı ve yağ verileri üreticiden alınmalıdır.',
        'Euler yalnız ideal elastik kolon ön kontrolüdür; motor RMS hesabı üretici görev sınıfı onayı değildir.',
        'Nominal boru iç çapı seçimi basınç dayanımı, et kalınlığı veya hortum ürün seçimi değildir.',
        'Tankın altı kapalı, üstü ve dört yanı ısı atar; doğrusal ısı atımı yüksek sıcaklıklarda yalnız ekstrapolasyondur.',
        project.oil.source)
    return ProjectResult(cycle, pipe, thermal, accumulator, tuple(issues), assumptions,
                         not any(i.severity == 'critical' for i in issues), fingerprint)


def calculate_project(project: Project) -> ProjectResult:
    """Doğrulanmış sonuç veya alan kimlikli hata; sayısal taşma yayımlanmaz."""
    logger = logging.getLogger(__name__)
    try:
        result = _calculate_project(project)
        def check(value):
            if isinstance(value, dict):
                for item in value.values(): check(item)
            elif isinstance(value, (list, tuple)):
                for item in value: check(item)
            elif isinstance(value, float) and not math.isfinite(value):
                raise InputError('project', 'Hesap sonucu sonlu değil; girdi büyüklüklerini kontrol edin.')
        check(asdict(result))
        return result
    except InputError as exc:
        logger.info('Hidrolik girdi kontrolü: %s: %s', exc.field, exc)
        raise
    except ArithmeticError as exc:
        logger.warning('Hidrolik hesap sayısal sınırı aşıldı: %s', type(exc).__name__)
        raise InputError('project', 'Hesap sayısal sınırı aştı; boyutları ve çalışma koşullarını kontrol edin.') from exc
