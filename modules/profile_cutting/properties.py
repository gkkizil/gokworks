"""Case-insensitive mappings and explicit units for evaluated cut-list text."""

import re
from decimal import Decimal
from .models import number


DEFAULT_MAPPING = {
    'profile': ['DESCRIPTION', 'PROFILE', 'KESİT', 'PROFİL', 'AÇIKLAMA', 'TANIM'],
    'length': ['LENGTH', 'SW-LENGTH', 'BOY', 'UZUNLUK'],
    'material': ['MATERIAL', 'SW-MATERIAL', 'MALZEME'],
    'count': ['QUANTITY', 'ADET', 'MİKTAR'],
    'angle1': ['Angle1', 'ANGLE 1', 'AÇI 1', 'AÇI1'],
    'angle2': ['Angle2', 'ANGLE 2', 'AÇI 2', 'AÇI2'],
    'total_length': ['TOTAL LENGTH', 'TOPLAM BOY'],
    'thickness': ['THICKNESS', 'ET KALINLIĞI'],
    'standard': ['STANDARD', 'STANDART'],
    'stock_code': ['STOCK CODE', 'STOK KODU'],
}


def key(value):
    return str(value).strip().casefold().replace('\u0307', '').replace('ı','i')


def validate_mapping(mapping):
    if not isinstance(mapping, dict) or set(mapping) != set(DEFAULT_MAPPING):
        raise ValueError('Property eşleştirme alanları eksik veya geçersiz.')
    if any(not isinstance(v, list) or not v or any(not isinstance(n, str) or not n.strip() for n in v)
           for v in mapping.values()):
        raise ValueError('Her alan için en az bir property adı girin.')
    names = [key(name) for values in mapping.values() for name in values]
    if len(names) != len(set(names)):
        raise ValueError('Bir property adı birden fazla alana eşleştirilemez.')
    return mapping


def evaluated(properties, aliases):
    candidates = {key(name): prop for name, prop in properties.items()}
    found = [candidates[key(alias)] for alias in aliases if key(alias) in candidates]
    values = {prop.evaluated.strip() for prop in found if prop.resolved and prop.evaluated.strip()}
    if len(values) > 1:
        raise ValueError('Eşleştirilen property değerleri çelişiyor: ' + ', '.join(p.name for p in found))
    return next(iter(values), '')


def length_mm(text, unit='mm'):
    # A bare custom-property string follows document display units; it is
    # not an SI API double. Explicit suffixes always take precedence.
    match = re.fullmatch(r'\s*([+]?(?:\d+(?:[.,]\d*)?|[.,]\d+))\s*(mm|cm|m|in|inch|ft|"|\')?\s*', str(text), re.I)
    if not match:
        raise ValueError('Çözümlenmiş boy boş/geçersiz veya sayı biçimi belirsiz.')
    suffix = (match[2] or unit).lower()
    factors = {'mm':'1', 'cm':'10', 'm':'1000', 'in':'25.4', 'inch':'25.4', '"':'25.4', 'ft':'304.8', "'":'304.8'}
    if suffix not in factors:
        raise ValueError('Doküman uzunluk birimi okunamadı; boy için birim içeren property kullanın.')
    return number(match[1], 'Boy', positive=True)*Decimal(factors[suffix])


def angle_degrees(text):
    match = re.fullmatch(r'\s*([+]?(?:\d+(?:[.,]\d*)?|[.,]\d+))\s*(°|deg|rad)?\s*', str(text), re.I)
    if not match: raise ValueError('Açı özelliği çözümlenemedi.')
    value = number(match[1], 'Açı')
    if match[2] and match[2].lower() == 'rad':
        value *= Decimal('57.2957795130823208768')
    if value > 180: raise ValueError('Açı 0–180° aralığında değil.')
    return value


def section_thickness(text):
    value = re.sub(r'\s+', '', str(text)).replace('×','x').lower()
    scalar = r'(?:\d+(?:[.,]\d+)?|[.,]\d+)'
    if re.fullmatch(fr'{scalar}x{scalar}x{scalar}', value) or re.fullmatch(fr'[ø⌀]{scalar}x{scalar}',value):
        return number(value.rsplit('x',1)[1], 'Et kalınlığı', positive=True)
    return None


def identifiable_section(text, thickness='', stock_code=''):
    """Do not pool generic descriptions such as 'Profile' across unrelated bodies."""
    if stock_code.strip(): return bool(text.strip())
    value = str(text).upper().replace('×','X')
    scalar = r'(?:\d+(?:[.,]\d+)?|[.,]\d+)'
    if re.search(fr'{scalar}\s*X\s*{scalar}\s*X\s*{scalar}',value): return True
    if re.search(fr'[Ø⌀]\s*{scalar}\s*X\s*{scalar}',value): return True
    if re.search(r'\b(?:IPE|IPN|HEA|HEB|HEM|UPN|UPE)\s*\d',value): return True
    if thickness and re.search(fr'{scalar}\s*X\s*{scalar}',value): return True
    return bool(re.search(r'\b(?:FLAT|YASSI|DOLU|ROUND BAR|SQUARE BAR)\b',value) and re.search(scalar,value))
