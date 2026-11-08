"""Alan kimliği taşıyan, sonlu değer ve fiziksel sınır kontrolleri."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    field: str = ''
    severity: str = 'warning'


class InputError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def number(value: float, field: str, *, zero: bool = False) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise InputError(field, f'{field}: sonlu, {"sıfır veya pozitif" if zero else "pozitif"} sayı gerekli.')
    return float(value)


def efficiency(value: float, field: str) -> float:
    number(value, field)
    if value > 1:
        raise InputError(field, f'{field}: verim 0–1 aralığında olmalı (sıfır hariç).')
    return value


def choice(value: str, values, field: str):
    if value not in values:
        raise InputError(field, f'{field}: geçersiz seçenek.')


def finite(value: float, field: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise InputError(field, f'{field}: sonlu sayı gerekli.')
    return float(value)
