"""ASME 2018 açık geometrik tolerans, datum ve toplam ölçülmüş hata kontrolü."""

from dataclasses import dataclass
from decimal import Decimal
import re

from modules.geometric_tolerances.catalog import CHARACTERISTICS, Characteristic

DATUM_CHOICES = ('Yok', 'A', 'A | B', 'A | B | C')


def number(value, label, *, zero=False, maximum=Decimal('10000')):
    text = str(value).strip().replace(',', '.')
    if isinstance(value, bool) or not re.fullmatch(r'\+?\d+(?:\.\d{1,6})?', text):
        raise ValueError(f'{label}: mm cinsinden sayı girin (en çok 6 ondalık).')
    result = Decimal(text)
    if result > maximum or result < 0 or (not zero and result == 0):
        lower = '0 dahil' if zero else '0’dan büyük'
        raise ValueError(f'{label}: {lower}, en çok {maximum} mm olmalı.')
    return result


def fmt_mm(value):
    """ASME 4.3.1/4.3.3 millimeter notation for technical frames."""
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def fmt(value):
    return fmt_mm(value).replace('.', ',')


@dataclass(frozen=True)
class Specification:
    characteristic: Characteristic
    size: Decimal
    tolerance: Decimal
    datums: tuple
    measured: Decimal | None
    size_tolerance: Decimal | None

    @property
    def accepted(self):
        return None if self.measured is None else self.measured <= self.tolerance

    @property
    def margin(self):
        return None if self.measured is None else self.tolerance - self.measured

    @property
    def frame(self):
        value = ('⌀' if self.characteristic.diametrical else '') + fmt_mm(self.tolerance)
        return ' | '.join((self.characteristic.name, value, *self.datums))


def specify(key, size, tolerance, datum='A', measured='', size_tolerance=''):
    try:
        characteristic = CHARACTERISTICS[key]
    except (KeyError, TypeError):
        raise ValueError('Geometrik tolerans türünü seçin.') from None
    if not characteristic.active:
        raise ValueError('Bu sembol ASME Y14.5-2018’de kaldırıldı; güncel çerçeve oluşturulmaz.')
    if datum not in DATUM_CHOICES:
        raise ValueError('Geçerli, sıralı bir datum sistemi seçin.')
    datums = () if datum == 'Yok' or characteristic.datum == 'none' else tuple(datum.split(' | '))
    if characteristic.datum == 'required' and not datums:
        raise ValueError('Bu örnek için datum referansı seçin (A, A | B veya A | B | C).')
    t = number(tolerance, 'Toplam tolerans t', maximum=Decimal('1000'))
    size_t = (number(size_tolerance, 'İlgili boyut toleransı', maximum=Decimal('1000'))
              if characteristic.group == 'Şekil' and str(size_tolerance).strip() else None)
    if size_t is not None and t >= size_t:
        raise ValueError('ASME 8.4: normal yüzey şekil toleransı ilgili boyut toleransından küçük olmalı.')
    return Specification(characteristic, number(size, 'Gösterim boyutu'), t,
                         datums, None if str(measured).strip() == '' else
                         number(measured, 'Toplam geometrik hata', zero=True, maximum=Decimal('1000')), size_t)
