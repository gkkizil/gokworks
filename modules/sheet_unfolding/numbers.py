"""Controlled number entry: '1,2' and '1.2' are 1.2; ambiguous thousands groups are refused."""

import math
import re

INCH = 25.4
METHOD_TITLES = {
    'analytic_developable': 'Analitik geliştirilebilir yüzey',
    'faceted': 'Fasetli / üçgenlemeli açınım',
    'faceted_developable': 'Fasetli / üçgenlemeli açınım',
    'triangulated': 'Fasetli / üçgenlemeli açınım',
    'forming_approximation': 'Şekillendirme için yaklaşık hesap',
    None: 'Yöntem bildirilmedi',
}
REFERENCE_TITLES = {'inner': 'İç yüzey', 'mid': 'Orta (nötr) yüzey', 'outer': 'Dış yüzey'}


def parse(text, label='Değer'):
    """Return a float or raise ValueError with a Turkish message. Never guesses."""
    value = str(text).strip().replace(' ', '').replace(' ', '')
    if not value:
        raise ValueError(f'{label} boş.')
    if ',' in value and '.' in value:
        if re.fullmatch(r'[+-]?\d{1,3}(\.\d{3})+,\d+', value):
            value = value.replace('.', '').replace(',', '.')            # 1.234,5
        else:
            raise ValueError(f'{label}: “{text}” anlaşılamadı; ondalık için tek ayırıcı kullanın (ör. 1234,5).')
    elif value.count(',') > 1 or value.count('.') > 1:
        raise ValueError(f'{label}: “{text}” belirsiz; binlik ayırıcı yazmayın.')
    elif re.fullmatch(r'[+-]?\d{1,3}\.\d{3}', value):
        raise ValueError(f'{label}: “{text}” belirsiz (bin mi, ondalık mı?). Ondalık için virgül kullanın: '
                         f'{value.replace(".", ",")}')
    value = value.replace(',', '.')
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f'{label}: “{text}” sayı değil.') from None
    if not math.isfinite(number):
        raise ValueError(f'{label} sonlu bir sayı olmalı.')
    return number


def fmt(value, digits=3, unit=''):
    """Display only: rounds the shown text, never the stored value."""
    if value is None:
        return '—'
    if isinstance(value, float):
        text = f'{value:.{digits}f}'
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
    else:
        text = str(value)
    text = (text if text not in ('-0', '') else '0').replace('.', ',')
    return f'{text} {unit}'.strip()


def to_display(mm, unit):
    return mm / INCH if unit == 'inch' else mm


def to_mm(value, unit):
    return value * INCH if unit == 'inch' else value
