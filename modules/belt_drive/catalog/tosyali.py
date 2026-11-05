"""Local Tosyalı catalogue adapter. Factual rows, no belt/rating invention.

The supplied PDF has pilot-pulley tables with decimal commas and sometimes
conflicting printed Dp. Ambiguous rows are quarantined, never repaired. The
full PDF/database is not bundled; the user can import their own document.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from .._numbers import positive, finite
from .products import ProductSource, PulleyProduct, ProductCatalog
from .profiles import get_profile

SUPPORTED_PROFILES = {'3M': 'HTD_3M', '5M': 'HTD_5M', '8M': 'HTD_8M',
                      'T5': 'T5', 'T10': 'T10', 'AT5': 'AT5', 'AT10': 'AT10'}
_ROW = re.compile(r'^\s*T\s+(\d+)-(3M|5M|8M|T5|T10|AT5|AT10)-(\d+)(F)?(-AL)?\s+(\S+)\s+(\d+)\s+(.+)$')


@dataclass(frozen=True, slots=True)
class ImportProblem:
    pdf_page: int
    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class TosyaliImportReport:
    catalog: ProductCatalog
    document_sha256: str
    recognized_rows: int
    accepted_rows: int
    unsupported_rows: int
    quarantined: tuple[ImportProblem, ...]
    page_counts: tuple[tuple[int, int], ...]
    complete: bool
    limitations: tuple[str, ...]


def _number(value, name, *, optional=False):
    if value == '-' and optional:
        return None
    if not re.fullmatch(r'\d+(?:,\d+)?', value):
        raise ValueError(name + ': belirsiz sayı/sütun.')
    number = float(value.replace(',', '.'))
    if name == 'Kg' and number == 0:
        return finite(number, name)  # Printed mass may round to zero; not used in geometry or loads.
    return positive(number, name)


def parse_tosyali_layout(content, *, document_sha256, document_name='Tosyalı Teknik Bilgi Kataloğu', strict=False):
    if type(strict) is not bool:
        raise ValueError('strict bool olmalı.')
    if not isinstance(content, str) or len(content) > 8*1024*1024:
        raise ValueError('PDF metni en çok 8 MiB/karakter olabilir.')
    if not re.fullmatch('[0-9a-f]{64}', document_sha256):
        raise ValueError('Kaynak PDF SHA-256 kimliği gerekli.')
    normalized = content.lower().replace('ı', 'i')
    if 'tosyali' not in normalized or 'triger' not in normalized:
        raise ValueError('Tosyalı/triger kaynak kimliği metinde bulunamadı.')
    products, sources, problems, page_counts = [], {}, [], Counter()
    recognized = unsupported = 0
    revision = 'undated-user-pdf-' + document_sha256[:12]
    seen = set()
    for page, text in enumerate(content.split('\f'), 1):
        columns = ()
        heading_profile = heading_pitch = heading_width = None
        nonempty = [line.strip() for line in text.splitlines() if line.strip()]
        footer = nonempty[-1] if nonempty and nonempty[-1].isdigit() else 'not identified'
        for line in text.splitlines():
            if 'Hatve' in line and 'Genişli' in line:
                pitch_match = re.search(r'Hatve\s*:\s*(\d+(?:,\d+)?)\s*mm', line)
                width_match = re.search(r'Genişli\S*\s*:\s*(\d+(?:,\d+)?)\s*mm', line)
                htd = re.search(r'HTD\s*®?\s*(3M|5M|8M|14M)', line)
                metric = re.search(r'\b(AT|T)\s*(5|10|20)\s*-', line)
                heading_profile = SUPPORTED_PROFILES.get(htd.group(1)) if htd else \
                    SUPPORTED_PROFILES.get(metric.group(1)+metric.group(2)) if metric else None
                heading_pitch = float(pitch_match.group(1).replace(',', '.')) if pitch_match else None
                heading_width = float(width_match.group(1).replace(',', '.')) if width_match else None
            if 'Sipariş' in line and 'Kodu' in line:
                columns = () if 'Burç' in line else tuple('PilotDelik' if match.group().startswith('Pilot') else match.group()
                    for match in re.finditer(r'\b(?:Dp|De|Df|Dm|Di|F|L|Kg)\b|Pilot\s+Delik', line))
                continue
            match = _ROW.match(line)
            if match is None:
                continue
            recognized += 1
            teeth_code, raw_profile, width, flange_suffix, material_suffix, construction, teeth_cell, values = match.groups()
            code = f'T {teeth_code}-{raw_profile}-{width}' + (flange_suffix or '') + (material_suffix or '')
            if not columns:
                unsupported += 1
                continue
            try:
                if not {'De', 'Df', 'Dm', 'F', 'L', 'PilotDelik'} <= set(columns):
                    raise ValueError('Gerekli sütun başlıkları eksik.')
                if teeth_code != teeth_cell:
                    raise ValueError('SKU diş sayısı ile tablo hücresi çelişiyor.')
                profile = SUPPORTED_PROFILES[raw_profile]
                if heading_profile != profile or heading_pitch != get_profile(profile).pitch_mm or heading_width != float(width):
                    raise ValueError('SKU profil/adım/genişliği tablo başlığıyla uyuşmuyor veya başlık belirsiz.')
                tokens = values.split()
                if len(tokens) != len(columns):
                    raise ValueError('Sütun/hücre sayısı uyuşmuyor; boş hücre tahmin edilmedi.')
                numbers = {name: _number(value, name, optional=name in ('Df', 'Di')) for name, value in zip(columns, tokens)}
                if numbers['F'] > numbers['L'] or float(width) > numbers['F']:
                    raise ValueError('F/L/nominal kayış genişliği çelişiyor.')
                if numbers['Df'] is not None and numbers['Df'] < numbers['De']:
                    raise ValueError('Flanş çapı diş dış çapından küçük.')
                if numbers['PilotDelik'] >= numbers['De']:
                    raise ValueError('Pilot delik diş dış çapından küçük olmalı.')
                series = f'tosyali:{profile}:{width}' + (':AL' if material_suffix else ':catalog')
                source_id = f'tosyali:{document_sha256[:12]}:pdf-{page}'
                product = PulleyProduct(code, series, source_id, profile, series,
                    teeth=int(teeth_code), pitch_mm=get_profile(profile).pitch_mm,
                    # F is preserved as printed. It is not silently equated to usable face width.
                    face_width_mm=None, overall_width_mm=numbers['L'],
                    outside_diameter_mm=max(numbers['De'], numbers['Dm'], numbers['Df'] or 0.),
                    nominal_belt_width_mm=float(width), catalog_pitch_diameter_mm=numbers.get('Dp'),
                    tooth_outside_diameter_mm=numbers['De'], flange_diameter_mm=numbers['Df'],
                    pilot_bore_mm=numbers['PilotDelik'], catalog_face_dimension_f_mm=numbers['F'],
                    construction_type=construction)
                if (series, code) in seen:
                    raise ValueError('Mükerrer ürün kodu; ikinci kayıt otomatik birleştirilmedi.')
                seen.add((series, code))
                products.append(product); page_counts[page] += 1
                if source_id not in sources:
                    sources[source_id] = ProductSource(source_id, 'Tosyalı', document_name, revision,
                        f'PDF page {page}; printed page {footer}',
                        'http://www.tosyalimakina.com', 'USER_SUPPLIED', document_sha256,
                        'User supplied for local analysis; full PDF/catalogue redistribution not established.')
            except (ValueError, OverflowError) as error:
                problems.append(ImportProblem(page, code, str(error)))
    if not recognized:
        raise ValueError('Desteklenen metrik pilot triger-senkron kasnak satırı bulunamadı.')
    if strict and problems:
        raise ValueError(f'{len(problems)} belirsiz/çelişkili katalog satırı; karantina raporunu inceleyin.')
    catalog = ProductCatalog('tosyali-user-pdf', revision, tuple(sources.values()), (), tuple(products))
    return TosyaliImportReport(catalog, document_sha256, recognized, len(products), unsupported,
        tuple(problems), tuple(sorted(page_counts.items())), not problems, (
            'Yalnız desteklenen metrik pilot kasnak tabloları; burçlu/imperial/14M/T20 tabloları kapsam dışıdır.',
            'Bölüm çapı hesapta z×p/π kullanılır; basılı Dp ile >0.006 mm çelişen kayıt karantinadadır.',
            'PDF metadata tarihi yayımlanmış katalog revizyonu sayılmadı; güncellik bağımsız doğrulanmadı.',
            'Bu katalogda kayış SKU/standart uzunluk veya güç/servis tablosu üretilmedi.',
            'F, nominal kayış genişliği, toplam L ve pilot delik ayrı büyüklüklerdir; imalat profili doğrulanmadı.',
        ))


def import_tosyali_pdf(path, *, strict=False, timeout=45):
    """Optional Poppler adapter. Numerical engine/JSON/CSV need no PDF dependency."""
    path = Path(path).resolve()
    before = path.stat()
    if before.st_size > 32*1024*1024:
        raise ValueError('PDF en çok 32 MiB olabilir.')
    if positive(timeout, 'PDF zaman sınırı') > 60:
        raise ValueError('PDF zaman sınırı en çok 60 saniye.')
    executable = shutil.which('pdftotext')
    if executable is None:
        raise ValueError('PDF içe aktarma için Poppler pdftotext gerekli; JSON/CSV ve matematik motoru bağımsız çalışır.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    with TemporaryDirectory(prefix='gokworks-tosyali-') as directory:
        output = Path(directory) / 'layout.txt'
        try:
            process = subprocess.run([executable, '-layout', str(path), str(output)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError('PDF metin çıkarımı çalıştırılamadı veya zaman aşımı.') from error
        if process.returncode or not output.exists() or output.stat().st_size > 8*1024*1024:
            raise ValueError('PDF metni çıkarılamadı veya boyut sınırını aştı.')
        content = output.read_text(encoding='utf-8')
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('Kaynak PDF içe aktarma sırasında değişti; tekrar deneyin.')
    return parse_tosyali_layout(content, document_sha256=digest.hexdigest(), document_name=path.name, strict=strict)
