"""Ardışık direnç yükü çevrimi: Q=Av, p=F/A, E=∑PΔt.

Sabit pompa: hız kısılırsa fazla debi emniyet valfinden geçer; beklemede
tüm debi valfe gider. Değişken pompa: kompansatör veya sabit mil gücü sınırı.
Yükün hareketi sürüklediği (overrunning), transient ve eşzamanlı fazlar yoktur.
"""
import math
from dataclasses import dataclass
from .models import Project
from .cylinder import areas, required_pressure, effective_area, buckling
from .pump_motor import pump_flow, required_displacement, select_motor, available_flow
from .piping import pipe_result
from .validation import Issue, InputError, number, choice
from .catalogs import MAX_PHASES


@dataclass(frozen=True)
class PhaseResult:
    name: str
    cylinder_id: str
    kind: str
    duration: float
    flow: float
    return_flow: float
    pressure: float
    supply_pressure: float
    supply_flow: float
    shaft_power: float
    useful_power: float
    heat_power: float
    speed: float
    feasible: bool
    available_flow: float
    cylinder_pressure: float
    line_pressure_drop: float
    start_position: float
    end_position: float


def calculate_cycle(project: Project) -> dict:
    if not project.cylinders or not 1 <= len(project.phases) <= MAX_PHASES:
        raise InputError('phases', f'En az bir silindir ve 1–{MAX_PHASES} faz gerekli.')
    cylinders = {}
    for c in project.cylinders:
        if not isinstance(c.id, str) or not c.id.strip() or c.id in cylinders:
            raise InputError('cylinders', 'Silindir kimlikleri boş veya tekrarlı olamaz.')
        areas(c); buckling(c, 0); cylinders[c.id] = c
    positions = {key: c.initial_position for key,c in cylinders.items()}
    pump = project.pump; capacity = pump_flow(pump)
    if pump.leakage_flow > capacity:
        raise InputError('pump.leakage_flow', 'Kaçak debisi pompa debisini aşamaz.')
    eta = pump.volumetric_efficiency * pump.mechanical_efficiency
    demands = []; issues = []
    for index, f in enumerate(project.phases):
        field = f'phases.{index}'
        if not isinstance(f.name, str) or not f.name.strip():
            raise InputError(field + '.name', 'Faz adı boş olamaz.')
        choice(f.kind, ('extend','retract','regenerate','hold','idle'), field + '.kind')
        number(f.force, field + '.force', zero=True); number(f.back_pressure, field + '.back_pressure', zero=True)
        if f.cylinder_id not in cylinders:
            raise InputError(field + '.cylinder_id', 'Fazın silindiri bulunamadı.')
        c = cylinders[f.cylinder_id]
        start = positions[c.id]
        speed = 0.; q = 0.; qr = 0.; useful = 0.; pressure = 0.
        if f.kind in ('hold','idle'):
            if f.speed is not None:
                raise InputError(field + '.speed', 'Bekleme/boşta fazında yalnız süre girin.')
            duration = number(f.duration, field + '.duration')
            if f.kind == 'hold':
                pressure = required_pressure(c, f.force, 'extend', f.back_pressure)
            elif f.force != 0:
                raise InputError(field + '.force', 'Boşta fazında kuvvet sıfır olmalı.')
        else:
            number(f.stroke, field + '.stroke')
            if f.stroke > c.stroke:
                raise InputError(field + '.stroke', 'Faz stroku silindir strokunu aşamaz.')
            if (f.speed is None) == (f.duration is None):
                raise InputError(field + '.speed', 'Hız veya süreden yalnız birini girin.')
            speed = number(f.speed, field + '.speed') if f.speed is not None else f.stroke / number(f.duration, field + '.duration')
            duration = f.stroke / speed
            area, opposite = effective_area(c, f.kind)
            q = area * speed
            qr = opposite * speed
            pressure = required_pressure(c, f.force, f.kind, f.back_pressure)
            useful = f.force * speed
            end = start + (-f.stroke if f.kind == 'retract' else f.stroke)
            if end < -1e-12 or end > c.stroke + 1e-12:
                raise InputError(field + '.stroke', f'{f.name}: ardışık hareket silindirin fiziksel strok sınırını aşıyor.')
            positions[c.id] = min(c.stroke,max(0.,end))
        if f.kind in ('extend','regenerate','hold') and not buckling(c, f.force)['passed']:
            issues.append(Issue('BUCKLING', f'{f.name}: Euler emniyeti 3.5 altında.', field, 'critical'))
        # Yalnız tanımlı basınç hattı çevrim kaybına eklenir. Diğer hatların
        # hesabı ayrı ön seçimdir; emiş basıncı/NPSH uygunluğu bundan çıkmaz.
        cylinder_pressure = pressure
        piping = pipe_result(project.pipe, q, project.oil)
        if project.pipe.role == 'pressure' and q > 0:
            if piping['pressure_drop'] is None:
                raise InputError('pipe.diameter', 'Basınç hattı için nominal seri yetersiz; çap girin.')
            pressure += piping['pressure_drop']
        demands.append((f, duration, speed, q, qr, pressure, useful, cylinder_pressure, start, positions[c.id]))
    peak_pressure = max(d[5] for d in demands)
    number(project.relief_factor, 'relief_factor')
    if project.relief_factor < 1:
        raise InputError('relief_factor', 'Emniyet valfi katsayısı en az 1 olmalı.')
    setting_base = max(peak_pressure, pump.compensator_pressure if pump.control == 'pressure' else 0.)
    relief = project.relief_pressure if project.relief_pressure is not None else setting_base * project.relief_factor
    number(relief, 'relief_pressure', zero=True)
    results = []
    for index, (f, duration, speed, q, qr, pressure, useful, cylinder_pressure, start, end) in enumerate(demands):
        if f.kind == 'idle':
            supplied_q, supplied_p = capacity, pump.idle_pressure
        elif pump.control == 'fixed':
            supplied_q = capacity
            supplied_p = relief if f.kind == 'hold' or q < capacity * (1 - 1e-9) else pressure
        else:
            supplied_q = q + pump.leakage_flow
            supplied_p = max(pressure, pump.compensator_pressure) if pump.control == 'pressure' else pressure
        power = supplied_p * supplied_q / eta
        available = available_flow(pump, max(pressure, supplied_p))
        feasible = (q + (pump.leakage_flow if pump.control != 'fixed' else 0) <= available * (1 + 1e-9)
                    and pressure <= relief and supplied_p <= pump.max_pressure
                    and (f.kind == 'idle' or supplied_p <= relief)
                    and (pump.control != 'pressure' or pressure <= pump.compensator_pressure)
                    and (pump.control != 'power' or power <= pump.power_limit))
        if not feasible:
            issues.append(Issue('CAPACITY', f'{f.name}: pompa debisi/basıncı/regülatör sınırı ihtiyacı karşılamıyor.', f'phases.{index}', 'critical'))
        # İhtiyaç karşılanmıyorsa bu değerler erişilmiş performans değildir.
        heat = max(0., power - useful)
        results.append(PhaseResult(f.name, f.cylinder_id, f.kind, duration, q, qr, pressure,
                                   supplied_p, supplied_q, power, useful, heat, speed, feasible,
                                   available, cylinder_pressure, pressure - cylinder_pressure, start, end))
    total = sum(r.duration for r in results)
    peak_power = max(r.shaft_power for r in results)
    rms = math.sqrt(sum(r.shaft_power**2 * r.duration for r in results) / total)
    loss_energy = sum(r.heat_power * r.duration for r in results)
    repeatable = all(abs(positions[c.id] - c.initial_position) <= 1e-12 for c in cylinders.values())
    if not repeatable:
        issues.append(Issue('CYCLE_NOT_CLOSED', 'Silindirler başlangıç konumuna dönmüyor; bu hareket dizisi doğrudan tekrarlanamaz.', 'phases'))
    return dict(phases=tuple(results), duration=total, repeatable_geometry=repeatable,
                max_flow=max(r.flow for r in results),
                max_pressure=peak_pressure, peak_power=peak_power, rms_power=rms,
                loss_energy=loss_energy, average_loss=loss_energy / total, relief_pressure=relief,
                motor=select_motor(peak_power, rms, project.overload),
                displacement=required_displacement(max(r.flow for r in results) + (pump.leakage_flow if pump.control != 'fixed' else 0), pump), issues=issues)
