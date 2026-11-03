"""Drawing requirements bound to stable stage/operation identities.

Nothing here is invented: a tolerance, roughness, datum or geometric tolerance
exists only when the user entered it. Missing title-block data stays empty.

Target keys
-----------
Dimensions (``ToleranceSpec`` targets):
    ``stage:<id>:diameter``  ``stage:<id>:length``
    ``op:<id>:width`` ``op:<id>:position`` ``op:<id>:bottom_diameter`` (groove)
    ``op:<id>:width`` ``op:<id>:length`` ``op:<id>:position`` ``op:<id>:depth`` (keyway)
    ``op:<id>:size`` (chamfer / fillet)   ``bore:diameter`` ``bore:depth``
Surfaces (finish, datum and geometric tolerance targets):
    ``stage:<id>:cylinder`` ``stage:<id>:face_left`` ``stage:<id>:face_right``
    ``op:<id>:floor`` (groove bottom / keyway floor)  ``bore:surface``
"""

from dataclasses import dataclass, field, fields
import math

TOLERANCE_KINDS = ('none', 'symmetric', 'bilateral', 'limit', 'iso_fit')
FIT_DISPLAYS = ('class', 'deviations', 'class_and_deviations')
PROCESSES = ('basic', 'removal_required', 'removal_prohibited')
LAYS = ('', '=', '⊥', 'X', 'M', 'C', 'R', 'P')
CHARACTERISTICS = {
    'circular_runout': ('Dairesel salgı', True),
    'total_runout': ('Toplam salgı', True),
    'cylindricity': ('Silindiriklik', False),
    'perpendicularity': ('Diklik', True),
    'parallelism': ('Paralellik', True),
    'position': ('Konum', True),
}
SHEET_SIZES = {'A4': (297., 210.), 'A3': (420., 297.), 'A2': (594., 420.), 'A1': (841., 594.), 'A0': (1189., 841.)}
SCHEMES = ('baseline', 'chain', 'mixed')
PROJECTIONS = ('first', 'third')
DATUM_LABELS = tuple('ABCDEFGHJK')
TITLE_FIELDS = ('drawing_number', 'revision', 'material', 'general_tolerance', 'drawn_by', 'notes')


def _finite(value, *, positive=False, minimum=None, maximum=1e6):
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value):
        return False
    if positive and value <= 0:
        return False
    if minimum is not None and value < minimum:
        return False
    return abs(value) <= maximum


@dataclass
class ToleranceSpec:
    """Dimension tolerance. Deviations are signed millimetres (upper ≥ lower)."""
    kind: str = 'none'
    upper: float = 0.
    lower: float = 0.
    fit: str = ''
    display: str = 'class'

    def errors(self, where):
        if self.kind not in TOLERANCE_KINDS:
            return [f'{where}: tolerans türü geçersiz.']
        if self.display not in FIT_DISPLAYS:
            return [f'{where}: geçme gösterimi geçersiz.']
        if not _finite(self.upper, maximum=100) or not _finite(self.lower, maximum=100):
            return [f'{where}: sapmalar sonlu ve ±100 mm içinde olmalı.']
        if self.kind == 'symmetric' and not self.upper > 0:
            return [f'{where}: simetrik tolerans sıfırdan büyük olmalı.']
        if self.kind in ('bilateral', 'limit') and not self.upper > self.lower:
            return [f'{where}: üst sapma alt sapmadan büyük olmalı.']
        if self.kind == 'iso_fit' and not (isinstance(self.fit, str) and self.fit.strip()):
            return [f'{where}: ISO geçme sınıfı seçin.']
        return []


@dataclass
class FinishSpec:
    """Surface texture requirement (ISO 21920-1 Ra parameter, user supplied)."""
    ra: float = 1.6
    process: str = 'removal_required'
    method: str = ''
    lay: str = ''

    def errors(self, where):
        if not _finite(self.ra, positive=True, maximum=100):
            return [f'{where}: Ra 0 ile 100 µm arasında olmalı.']
        if self.process not in PROCESSES or self.lay not in LAYS:
            return [f'{where}: işleme sembolü veya iz yönü geçersiz.']
        if not isinstance(self.method, str) or len(self.method) > 40:
            return [f'{where}: işleme yöntemi en fazla 40 karakter olmalı.']
        return []


@dataclass
class Datum:
    label: str
    target: str


@dataclass
class GeometricTolerance:
    characteristic: str
    value: float
    target: str
    datums: list[str] = field(default_factory=list)
    id: str = ''


@dataclass
class DrawingSettings:
    enabled: bool = False
    template: str = ''          # .drwdot; empty → SOLIDWORKS default drawing template
    sheet_format: str = ''      # optional .slddrt
    sheet_size: str = 'auto'    # auto, A4 … A0
    projection: str = 'first'
    scale_mode: str = 'auto'
    scale: list[int] = field(default_factory=lambda: [1, 1])
    scheme: str = 'baseline'
    total_length_reference: bool = True
    isometric: bool = False
    detail_views: bool = True
    keyway_section: bool = True
    centerlines: bool = True
    fit_display: str = 'class'
    pdf: bool = True
    dwg: bool = False
    tolerances: dict[str, ToleranceSpec] = field(default_factory=dict)
    finishes: dict[str, FinishSpec] = field(default_factory=dict)
    default_finish: FinishSpec | None = None   # bulk value for machined cylinders, opt-in only
    datums: list[Datum] = field(default_factory=list)
    geometric: list[GeometricTolerance] = field(default_factory=list)
    title: dict[str, str] = field(default_factory=dict)

    def is_default(self):
        return self.to_dict() == DrawingSettings().to_dict()

    def to_dict(self):
        return dict(
            enabled=self.enabled, template=self.template, sheet_format=self.sheet_format,
            sheet_size=self.sheet_size, projection=self.projection, scale_mode=self.scale_mode,
            scale=list(self.scale), scheme=self.scheme, total_length_reference=self.total_length_reference,
            isometric=self.isometric, detail_views=self.detail_views, keyway_section=self.keyway_section,
            centerlines=self.centerlines, fit_display=self.fit_display, pdf=self.pdf, dwg=self.dwg,
            tolerances={k: _plain(v) for k, v in sorted(self.tolerances.items())},
            finishes={k: _plain(v) for k, v in sorted(self.finishes.items())},
            default_finish=None if self.default_finish is None else _plain(self.default_finish),
            datums=[_plain(d) for d in self.datums],
            geometric=[_plain(g) for g in self.geometric],
            title={k: self.title[k] for k in TITLE_FIELDS if self.title.get(k)})

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != set(cls().to_dict()):
            raise ValueError('Teknik resim ayarları eksik veya bilinmeyen alan içeriyor.')
        try:
            settings = cls(**{k: data[k] for k in data if k not in
                              ('tolerances', 'finishes', 'default_finish', 'datums', 'geometric', 'title')})
            settings.tolerances = {str(k): _build(ToleranceSpec, v) for k, v in _mapping(data['tolerances']).items()}
            settings.finishes = {str(k): _build(FinishSpec, v) for k, v in _mapping(data['finishes']).items()}
            settings.default_finish = None if data['default_finish'] is None else _build(FinishSpec, data['default_finish'])
            settings.datums = [_build(Datum, v) for v in _sequence(data['datums'])]
            settings.geometric = [_build(GeometricTolerance, v) for v in _sequence(data['geometric'])]
            title = _mapping(data['title'])
            if set(title) - set(TITLE_FIELDS) or any(not isinstance(v, str) for v in title.values()):
                raise ValueError('Antet alanları geçersiz.')
            settings.title = dict(title)
        except TypeError as error:
            raise ValueError('Teknik resim ayarlarının alan türleri geçersiz.') from error
        errors = settings.basic_errors()
        if errors:
            raise ValueError('\n'.join(errors))
        return settings

    def basic_errors(self):
        """Checks that do not need the shaft geometry."""
        errors = []
        flags = ('enabled', 'total_length_reference', 'isometric', 'detail_views', 'keyway_section', 'centerlines', 'pdf', 'dwg')
        if any(type(getattr(self, name)) is not bool for name in flags):
            errors.append('Teknik resim seçenekleri doğru/yanlış olmalı.')
        for name, suffix in (('template', '.drwdot'), ('sheet_format', '.slddrt')):
            value = getattr(self, name)
            if not isinstance(value, str) or (value and not value.lower().endswith(suffix)) or len(value) > 400:
                errors.append(f'Şablon yolu geçersiz: {suffix} dosyası seçin.')
        if self.sheet_size not in ('auto', *SHEET_SIZES) or self.projection not in PROJECTIONS:
            errors.append('Sayfa boyutu veya izdüşüm yöntemi geçersiz.')
        if self.scale_mode not in ('auto', 'fixed') or not (isinstance(self.scale, list) and len(self.scale) == 2
                                                           and all(type(v) is int and 1 <= v <= 100 for v in self.scale)):
            errors.append('Ölçek 1–100 arasında iki tam sayı olmalı (ör. 1:2).')
        if self.scheme not in SCHEMES or self.fit_display not in FIT_DISPLAYS:
            errors.append('Ölçülendirme yöntemi veya geçme gösterimi geçersiz.')
        for key, spec in self.tolerances.items():
            errors += spec.errors(key)
        for key, spec in self.finishes.items():
            errors += spec.errors(key)
        if self.default_finish is not None:
            errors += self.default_finish.errors('Toplu yüzey pürüzlülüğü')
        labels = [d.label for d in self.datums]
        if len(set(labels)) != len(labels) or any(label not in DATUM_LABELS for label in labels):
            errors.append('Datum harfleri benzersiz olmalı (A, B, C …; I ve O kullanılmaz).')
        for g in self.geometric:
            if g.characteristic not in CHARACTERISTICS or not _finite(g.value, positive=True, maximum=10):
                errors.append('Geometrik tolerans türü veya değeri (0–10 mm) geçersiz.')
                continue
            needs = CHARACTERISTICS[g.characteristic][1]
            if needs and not g.datums:
                errors.append(f'{CHARACTERISTICS[g.characteristic][0]}: referans datum gerekli.')
            if not needs and g.datums:
                errors.append(f'{CHARACTERISTICS[g.characteristic][0]}: datum referansı almaz.')
            if any(label not in labels for label in g.datums):
                errors.append(f'{CHARACTERISTICS[g.characteristic][0]}: tanımlanmamış datum kullanılıyor.')
        if any(len(v) > 120 for v in self.title.values()):
            errors.append('Antet alanları en fazla 120 karakter olabilir.')
        return errors


def _plain(value):
    return {f.name: (list(getattr(value, f.name)) if isinstance(getattr(value, f.name), list) else getattr(value, f.name))
            for f in fields(value)}


def _mapping(value):
    if not isinstance(value, dict) or len(value) > 2000:
        raise ValueError('Teknik resim eşlemesi geçersiz.')
    return value


def _sequence(value):
    if not isinstance(value, list) or len(value) > 200:
        raise ValueError('Teknik resim listesi geçersiz.')
    return value


def _build(kind, value):
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(kind)}:
        raise ValueError(f'{kind.__name__} alanları eksik veya bilinmeyen.')
    return kind(**value)
