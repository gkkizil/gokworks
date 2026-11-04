"""Reference-line/pitch identity only; no groove, tooth-form or rating tables."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Profile:
    key: str
    family: str
    series: str
    reference_line: str
    pitch_mm: float | None = None
    nominal_supported: bool = True
    limitation: str = 'Diş/kanal geometrisi ve üretici güç kapasitesi doğrulanmadı.'


PROFILES = (
    *(Profile(key, 'v', 'classical', 'datum') for key in ('Z', 'A', 'B', 'C', 'D')),
    *(Profile(key, 'v', 'narrow', 'datum') for key in ('SPZ', 'SPA', 'SPB', 'SPC')),
    *(Profile(key, 'timing', series, 'pitch', pitch) for key, series, pitch in (
        ('HTD_3M', 'HTD', 3.), ('HTD_5M', 'HTD', 5.), ('HTD_8M', 'HTD', 8.),
        ('T5', 'T', 5.), ('T10', 'T', 10.), ('AT5', 'AT', 5.), ('AT10', 'AT', 10.))),
    *(Profile(key, 'timing', 'proprietary', 'pitch', nominal_supported=False,
              limitation='GT nesil adı adımı tanımlamaz; üretici, ürün serisi ve gerçek adım gerekli.')
      for key in ('GT2', 'GT3')),
    *(Profile(key, 'poly_v', 'ribbed', 'not_defined', nominal_supported=False,
              limitation='Poly-V Aşama 1 kapsamında değildir.') for key in ('PJ', 'PK', 'PL')),
)


def get_profile(key):
    if not isinstance(key, str):
        raise ValueError('Kayış profili metin olmalı.')
    for profile in PROFILES:
        if profile.key == key:
            return profile
    raise ValueError('Bilinmeyen kayış profili: ' + key)
