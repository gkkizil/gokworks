"""Plain data crossing the worker/UI boundary; never COM interfaces."""

from dataclasses import dataclass, asdict
import math
from pathlib import Path


@dataclass(frozen=True)
class Source:
    path: str
    root: str = ''


@dataclass(frozen=True)
class Options:
    output: str
    formats: tuple[str, ...] = ('step214',)
    configurations: str = 'active'
    selected_configurations: tuple[str, ...] = ()
    assembly_mode: str = 'single'
    include_subassemblies: bool = False
    naming: str = 'original'
    prefix: str = ''
    suffix: str = ''
    preserve_folders: bool = False
    overwrite: bool = False
    stl_unit: str = 'mm'
    stl_quality: str = 'medium'
    deviation_mm: float = .1
    angle_degrees: float = 15

    def validate(self):
        from .formats import BY_KEY
        if not str(self.output).strip():
            raise ValueError('Bir çıktı klasörü seçin.')
        if Path(self.output).exists() and not Path(self.output).is_dir():
            raise ValueError('Çıktı konumu bir klasör olmalı.')
        if not self.formats or len(set(self.formats)) != len(self.formats) or any(k not in BY_KEY for k in self.formats):
            raise ValueError('En az bir geçerli çıktı formatı seçin.')
        if self.configurations not in ('active', 'all', 'selected'):
            raise ValueError('Konfigürasyon seçimi geçersiz.')
        if self.configurations == 'selected' and not self.selected_configurations:
            raise ValueError('Aktarılacak konfigürasyon adlarını girin veya listeden seçin.')
        if self.assembly_mode not in ('single', 'components') or self.naming not in ('original', 'configuration', 'format'):
            raise ValueError('Montaj veya isimlendirme seçimi geçersiz.')
        if self.stl_unit not in ('mm', 'inch') or self.stl_quality not in ('coarse', 'medium', 'fine', 'custom'):
            raise ValueError('STL birimi veya çözünürlüğü geçersiz.')
        if any(not math.isfinite(v) or v <= 0 for v in (self.deviation_mm, self.angle_degrees)) or self.angle_degrees > 90:
            raise ValueError('STL sapması pozitif, açı toleransı 0–90° arasında olmalı.')


@dataclass(frozen=True)
class Outcome:
    source: str
    configuration: str
    format: str
    status: str
    detail: str
    output: str = ''
    size: int = 0
    seconds: float = 0
    errors: int = 0
    warnings: int = 0
    protocol: int | None = None
    open_warnings: int = 0

    def row(self):
        return asdict(self)


class Cancelled(Exception):
    """Cooperative boundary only; a live COM call is never interrupted."""


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()
