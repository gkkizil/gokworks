"""Strict finite SI/mm scalar guards shared by the mathematical functions."""

import math


def finite(value, name):
    if type(value) not in (int, float):
        raise ValueError(f'{name}: sonlu bir sayı girin; bool/metin kabul edilmez.')
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f'{name}: sayı hesaplama aralığının dışında.') from error
    if not math.isfinite(result):
        raise ValueError(f'{name}: NaN/sonsuzluk kabul edilmez.')
    return result


def positive(value, name):
    result = finite(value, name)
    if result <= 0:
        raise ValueError(f'{name}: sıfırdan büyük olmalı.')
    return result


def integer(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f'{name}: pozitif tam sayı olmalı.')
    positive(value, name)
    return value


def checked(value, name):
    """Reject numerical overflow rather than returning a plausible-looking inf."""
    return finite(value, name)
