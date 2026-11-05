"""Manufacturer identity adapters for the normalized local contract.

These validate declared source identity/metadata, not authenticity or a brand's
closed rating algorithm. No scraped/verified Gates or Optibelt tables ship here.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from .importers import load_catalog
from ..models import Issue


@dataclass(frozen=True, slots=True)
class ManufacturerAdapter:
    name: str
    official_domains: tuple[str, ...]

    def accepts(self, source):
        return source.manufacturer.casefold() == self.name.casefold()

    def review(self, source):
        checks = []
        if not self.accepts(source):
            return (Issue('MANUFACTURER_MISMATCH', 'Kaynak üreticisi adaptörle uyuşmuyor.'),)
        try:
            host = (urlparse(source.url).hostname or '').lower()
        except ValueError:
            host = ''
        if host not in self.official_domains:
            checks.append(Issue('SOURCE_DOMAIN', 'Beyan edilen URL kayıtlı üretici alanına ait değil.', severity='WARNING'))
        if not all((source.document, source.revision, source.page, source.document_sha256)):
            checks.append(Issue('SOURCE_EVIDENCE', 'Belge/revizyon/sayfa/içerik özeti eksik.', severity='NOT_EVALUATED'))
        checks.append(Issue('SOURCE_AUTHENTICITY', 'Alan adı ve metadata tek başına resmî doğrulama sağlamaz; güncel kaynak ve tablo bağımsız kontrol edilmeli.', severity='NOT_EVALUATED'))
        return tuple(checks)

    def load(self, path):
        catalog = load_catalog(path)
        if not catalog.sources or any(not self.accepts(source) for source in catalog.sources):
            raise ValueError('Üretici adaptörü yalnız aynı üreticiye ait normalize yerel katalog kabul eder.')
        return catalog


GATES = ManufacturerAdapter('Gates', ('gates.com', 'www.gates.com'))
OPTIBELT = ManufacturerAdapter('Optibelt', ('optibelt.com', 'www.optibelt.com', 'web.optibelt.com'))
TOSYALI = ManufacturerAdapter('Tosyalı', ('tosyalimakina.com', 'www.tosyalimakina.com'))


def manufacturer_adapter(name):
    for adapter in (GATES, OPTIBELT, TOSYALI):
        if adapter.name.casefold() == name.casefold():
            return adapter
    raise ValueError('Bu üretici için kayıtlı kaynak adaptörü yok; genel yerel katalog sözleşmesini kullanın.')
