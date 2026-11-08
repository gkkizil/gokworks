"""Pompa sürekliliği, enerji/moment dengesi ve nominal motor ön seçimi."""
import math
from dataclasses import replace
from .models import Pump
from .catalogs import MOTORS_KW, PUMP_CC, PUMP_DEFAULTS, select_up
from .validation import number, efficiency, choice, InputError


def validate_pump(p: Pump):
    choice(p.kind, PUMP_DEFAULTS, 'pump.kind')
    choice(p.control, ('fixed','pressure','power'), 'pump.control')
    if p.control != 'fixed' and p.kind != 'axial_variable':
        raise InputError('pump.control', 'Regülatör için değişken deplasmanlı pompa gerekli.')
    for key in ('displacement','angular_speed','max_pressure','compensator_pressure','power_limit'):
        number(getattr(p, key), 'pump.' + key)
    for key in ('leakage_flow','idle_pressure'):
        number(getattr(p, key), 'pump.' + key, zero=True)
    efficiency(p.volumetric_efficiency, 'pump.volumetric_efficiency')
    efficiency(p.mechanical_efficiency, 'pump.mechanical_efficiency')


def pump_flow(p: Pump) -> float:
    validate_pump(p)
    return p.displacement * p.angular_speed / (2 * math.pi) * p.volumetric_efficiency


def pump_for_type(kind: str, **overrides) -> Pump:
    """Açıkça örnek katsayılarla pompa oluşturur; ürün seçimi yapmaz."""
    choice(kind, PUMP_DEFAULTS, 'pump.kind')
    ev, em, limit = PUMP_DEFAULTS[kind]
    result = replace(Pump(kind=kind, volumetric_efficiency=ev, mechanical_efficiency=em,
                          max_pressure=limit), **overrides)
    validate_pump(result)
    return result


def available_flow(p: Pump, pressure: float) -> float:
    """Regülatörün nominal p–Q zarfı; transient/servo cevabı değildir."""
    number(pressure, 'pressure', zero=True)
    full = pump_flow(p)
    if pressure > p.max_pressure or (p.control == 'pressure' and pressure > p.compensator_pressure):
        return 0.
    if p.control == 'power' and pressure:
        return min(full, p.power_limit * p.volumetric_efficiency * p.mechanical_efficiency / pressure)
    return full


def required_displacement(flow: float, p: Pump) -> dict:
    number(flow, 'flow', zero=True); validate_pump(p)
    needed = flow * 2 * math.pi / (p.angular_speed * p.volumetric_efficiency)
    nominal = select_up(needed * 1e6, PUMP_CC)
    return dict(required=needed, nominal=None if nominal is None else nominal * 1e-6)


def shaft_power(pressure: float, flow: float, total_efficiency: float) -> float:
    number(pressure, 'pressure', zero=True); number(flow, 'flow', zero=True)
    efficiency(total_efficiency, 'total_efficiency')
    return pressure * flow / total_efficiency


def pump_torque(p: Pump, pressure: float) -> float:
    validate_pump(p); number(pressure, 'pressure', zero=True)
    return p.displacement * pressure / (2 * math.pi * p.mechanical_efficiency)


def select_motor(peak: float, rms: float, overload: float = .1) -> dict:
    number(peak, 'peak', zero=True); number(rms, 'rms', zero=True); number(overload, 'overload', zero=True)
    if overload > 1:
        raise InputError('overload', 'Aşırı yük oranı 0–1 aralığında olmalı.')
    required = max(rms, peak / (1 + overload))
    nominal = select_up(required / 1000, MOTORS_KW)
    return dict(required=required, nominal=None if nominal is None else nominal * 1000)
