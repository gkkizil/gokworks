"""Polytropik pVⁿ=sabit gaz akümülatörü; bütün basınçlar içeride mutlak."""
from .models import Accumulator
from .catalogs import ACCUMULATORS_L, select_up
from .validation import number, InputError


def accumulator_result(a: Accumulator) -> dict:
    if not a.enabled:
        return dict(status='disabled')
    for key in ('minimum_pressure','maximum_pressure','delivery_volume','atmospheric_pressure','exponent'):
        number(getattr(a, key), 'accumulator.' + key)
    if not 1 <= a.exponent <= 1.4:
        raise InputError('accumulator.exponent', 'Polytropik üs 1–1.4 arasında olmalı.')
    p1 = a.minimum_pressure + a.atmospheric_pressure
    p2 = a.maximum_pressure + a.atmospheric_pressure
    p0 = .9 * p1 if a.precharge_pressure is None else a.precharge_pressure + a.atmospheric_pressure
    if not a.atmospheric_pressure < p0 < p1 < p2:
        raise InputError('accumulator.precharge_pressure', 'Mutlak basınçlarda atmosfer < p0 < p1 < p2 gerekli.')
    required = a.delivery_volume / ((p0 / p1)**(1 / a.exponent) - (p0 / p2)**(1 / a.exponent))
    nominal = select_up(required * 1000, ACCUMULATORS_L)
    return dict(status='calculated', required_volume=required,
                nominal_volume=None if nominal is None else nominal / 1000,
                precharge_absolute=p0, minimum_absolute=p1, maximum_absolute=p2)
