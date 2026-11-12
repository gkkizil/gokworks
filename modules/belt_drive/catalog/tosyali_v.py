"""Factual taper-bush V pulley rows from the user's Tosyalı catalogue.

Only the unambiguous leading columns are imported. F/L, bush and bore cells
are deliberately not guessed from shifted/empty columns. No belt rating is
attributed to this pulley catalogue.
"""
from collections import Counter
from dataclasses import dataclass, asdict
from functools import lru_cache
import json
from pathlib import Path
import re

PROFILES = ('SPZ', 'SPA', 'SPB', 'SPC')
DOCUMENT_SHA256 = '8399b6b5a123573e99e8a982afd6c7c1504e160edc845d6fc6218812461d689c'
MAX_SPEED_M_S = 35.
_ROW = re.compile(r'^\s*T\s+(SP[ZABC])\s+(\d+)-(\d+)\s+(\d+)\s+(\S+)\s+(\S+)')


@dataclass(frozen=True, slots=True)
class TosyaliVPulley:
    code: str
    profile: str
    datum_mm: float
    outside_mm: float
    grooves: int
    pdf_page: int


def parse_layout(content):
    """Return accepted rows and explicit quarantines; never repair SKU conflicts."""
    if not isinstance(content, str) or len(content) > 8*1024*1024:
        raise ValueError('Tosyalı metni en çok 8 MiB olabilir.')
    rows, problems, seen = [], [], set()
    for page, text in enumerate(content.split('\f'), 1):
        for line in text.splitlines():
            match = _ROW.match(line)
            if not match:
                continue
            profile, d, count, printed_count, printed_d, outside = match.groups()
            code = f'T {profile} {d}-{count}'
            try:
                if not all(re.fullmatch(r'\d+(?:[.,]\d+)?', value) for value in (printed_d, outside)):
                    raise ValueError('Belirsiz datum/dış çap hücresi.')
                datum, od = (float(v.replace(',', '.')) for v in (printed_d, outside))
                if int(d) != datum or int(count) != int(printed_count):
                    raise ValueError('Ürün kodu ile datum/kanal hücresi çelişiyor.')
                if not 0 < datum < od or int(count) < 1 or code in seen:
                    raise ValueError('Geçersiz boyut/adet veya mükerrer ürün.')
                rows.append(TosyaliVPulley(code, profile, datum, od, int(count), page))
                seen.add(code)
            except ValueError as error:
                problems.append(dict(code=code, pdf_page=page, reason=str(error)))
    if not rows:
        raise ValueError('Tosyalı dar V kasnak satırı bulunamadı.')
    return tuple(rows), tuple(problems)


@lru_cache(maxsize=1)
def catalog():
    data = json.loads((Path(__file__).parent/'data'/'tosyali-v-reference.json').read_text(encoding='utf-8'))
    if data['document_sha256'] != DOCUMENT_SHA256:
        raise ValueError('Tosyalı V katalog kaynak kimliği uyuşmuyor.')
    return tuple(TosyaliVPulley(**row) for row in data['pulleys'])


def import_facts(content):
    rows, problems = parse_layout(content)
    return dict(schema='gokworks.tosyali_v_reference', version=1,
                document_sha256=DOCUMENT_SHA256,
                document='Tosyalı Teknik Bilgi Kataloğu — kullanıcı PDF, tarihsiz',
                pulleys=[asdict(row) for row in rows], quarantined=problems,
                counts=dict(Counter(row.profile for row in rows)),
                notes=['PDF sayfa 48–74 / basılı 46–72; yalnız P, O ve kanal adedi.',
                       'PDF 47 / basılı 45: kasnak çevresel hızı en çok 35 m/s.',
                       'Kayış, güç tablosu, mil deliği ve toplam gövde genişliği bu veri kümesinde yoktur.'])
