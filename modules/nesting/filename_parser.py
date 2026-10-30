"""Conservative filename metadata detection. No Qt, CAD reader or engine imports."""

from dataclasses import dataclass
import math
from pathlib import PureWindowsPath
import re


MAX_QUANTITY = 10000
_NUMBER = r'[+-]?(?:[0-9]+(?:[.,][0-9]+)?(?:[eE][+-]?[0-9]+)?|nan|inf(?:inity)?)'
_LEFT = r'(?<![^\W_])(?<![.,])'
_RIGHT = r'(?![^\W_])(?![.,][0-9])'
_SEP = r'[\s_:=\-]*'


@dataclass(frozen=True)
class Rule:
    name: str
    field: str
    pattern: re.Pattern


# Rules are data: additional explicit naming conventions can be added here.
RULES = (
    Rule('T / THK / KALINLIK', 'thickness', re.compile(
        _LEFT + r'(?:KALINLIK|THK|T)' + _SEP + r'(?P<value>' + _NUMBER + r')'
        + r'(?:[\s_]*MM)?' + _RIGHT, re.I)),
    Rule('mm', 'thickness', re.compile(
        _LEFT + r'(?P<value>' + _NUMBER + r')[\s_]*MM' + _RIGHT, re.I)),
    Rule('AD / ADET / QTY / QUANTITY', 'quantity', re.compile(
        _LEFT + r'(?:QUANTITY|ADET|QTY|AD)' + _SEP + r'(?P<value>' + _NUMBER + r')' + _RIGHT, re.I)),
    Rule('sayı + AD / ADET', 'quantity', re.compile(
        _LEFT + r'(?P<value>' + _NUMBER + r')' + _SEP + r'(?:ADET|AD)' + _RIGHT, re.I)),
)


@dataclass(frozen=True)
class FilenameInfo:
    filename: str
    code: str
    thickness: float | None
    quantity: int | None
    status: str
    rules: tuple[str, ...]
    thickness_issue: str = ''
    quantity_issue: str = ''

    @property
    def detail(self):
        return ' '.join(filter(None, (self.thickness_issue, self.quantity_issue)))


def parse_filename(path) -> FilenameInfo:
    """Read only explicit metadata, preserving unknown fields as None.

    Both Windows and POSIX input paths are accepted on every host. Directories
    never contribute metadata. No source file is opened or renamed.
    """
    filename = PureWindowsPath(str(path)).name
    stem = filename[:-4] if filename.lower().endswith('.dxf') else filename
    values = {'thickness': [], 'quantity': []}
    issues = {'thickness': [], 'quantity': []}
    spans = []; rules = []
    for rule in RULES:
        for match in rule.pattern.finditer(stem):
            start, end = match.span()
            # Do not re-read the unit suffix of an explicit T/THK match.
            if any(start >= a and end <= b for a, b in spans):
                continue
            if rule.name == 'mm':
                before = stem[:start]
                after = stem[end:]
                # Dimension, diameter, radius and hole annotations aren't thickness.
                if (re.search(r'(?:[x×Ø⌀φ]|\b(?:DIA|ÇAP|CAP|R|BOY|EN|UZUNLUK|DELİK|DELIK))[\s_:=]*$', before, re.I)
                        or re.match(r'[\s_]*[x×][\s_]*[0-9]',after,re.I)):
                    continue
                # A hyphen after a code is a delimiter; a separately signed
                # value ("_-2mm" or " -2mm") is invalid metadata.
                if start and stem[start-1] in '.,':
                    continue
            raw = match['value']
            # Never turn an explicitly negative labeled value into a positive
            # thickness/count by treating its sign as a separator.
            prefix = stem[start:match.start('value')]
            if prefix.endswith('-'):
                raw = '-' + raw.lstrip('+')
            try:
                n = float(raw.replace(',', '.'))
                if not math.isfinite(n) or n <= 0:
                    raise ValueError
                if rule.field == 'quantity':
                    if not re.fullmatch(r'\+?[0-9]+', raw) or n > MAX_QUANTITY:
                        raise ValueError
                    n = int(raw)
            except (ValueError, OverflowError):
                title = 'Kalınlık' if rule.field == 'thickness' else 'Adet'
                issues[rule.field].append(f'{title} geçersiz: {match.group()}.')
            else:
                values[rule.field].append(n)
            spans.append((start, end)); rules.append(rule.name)
    resolved = {}
    for field, items in values.items():
        distinct = set(items)
        if len(distinct) > 1:
            title = 'sac kalınlığı' if field == 'thickness' else 'adet'
            issues[field].append(f'Birden fazla farklı {title} tespit edildi.')
        resolved[field] = items[0] if len(distinct) == 1 and not issues[field] else None
    code = stem
    for start, end in sorted(spans, reverse=True):
        code = code[:start] + ' ' + code[end:]
    code = re.sub(r'[\s_]+', ' ', code).strip(' -=:') or stem
    count = sum(value is not None for value in resolved.values())
    status = ('Kontrol gerekli' if any(issues.values()) else
              'Algılandı' if count == 2 else 'Kısmen algılandı' if count else 'Varsayılan değer')
    return FilenameInfo(filename, code, **resolved, status=status, rules=tuple(dict.fromkeys(rules)),
                        thickness_issue=' '.join(issues['thickness']), quantity_issue=' '.join(issues['quantity']))
