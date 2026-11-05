"""Product, evidence and declared rating contracts, separate from Stage 1 lists.

Imported metadata never grants official verification. There are currently no
reviewed manufacturer datasets in this distribution.
"""

from dataclasses import dataclass
from math import isclose, pi

from .._numbers import positive, integer, finite
from .profiles import get_profile

SOURCE_STATUSES = ('OFFICIAL_VERIFIED', 'USER_SUPPLIED', 'EXAMPLE', 'OUTDATED', 'INCOMPLETE')


def text(value, name, *, optional=False):
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(f'{name}: metin gerekli.')
    return value


def sequence(value, name, maximum=10000):
    if type(value) not in (tuple, list) or len(value) > maximum:
        raise ValueError(f'{name}: en çok {maximum} öğeli liste gerekli.')
    return tuple(value)


@dataclass(frozen=True, slots=True)
class ProductSource:
    identifier: str
    manufacturer: str
    document: str
    revision: str
    page: str
    url: str
    verification_status: str = 'USER_SUPPLIED'
    document_sha256: str = ''
    usage_permission: str = ''

    def __post_init__(self):
        for key in ('identifier', 'manufacturer'):
            text(getattr(self, key), key)
        for key in ('document', 'revision', 'page', 'url', 'document_sha256', 'usage_permission'):
            text(getattr(self, key), key, optional=True)
        if self.verification_status not in SOURCE_STATUSES:
            raise ValueError('Bilinmeyen kaynak doğrulama statüsü.')

    @property
    def effective_status(self):
        # No self-issued OFFICIAL_VERIFIED flag, even through the Python API.
        return 'USER_SUPPLIED' if self.verification_status == 'OFFICIAL_VERIFIED' else self.verification_status

    @property
    def officially_verified(self):
        return False  # Requires an independently reviewed, content-pinned dataset.


@dataclass(frozen=True, slots=True)
class BeltProduct:
    code: str
    series_id: str
    source_id: str
    profile: str
    compatibility_id: str
    datum_length_mm: float | None = None
    tooth_count: int | None = None
    pitch_mm: float | None = None
    pitch_length_mm: float | None = None
    inside_length_mm: float | None = None
    outside_length_mm: float | None = None
    width_mm: float | None = None
    material: str = ''

    def __post_init__(self):
        for key in ('code', 'series_id', 'source_id', 'compatibility_id'):
            text(getattr(self, key), key)
        text(self.material, 'material', optional=True)
        profile = get_profile(self.profile)
        if not profile.nominal_supported:
            raise ValueError(profile.limitation)
        for key in ('datum_length_mm', 'pitch_mm', 'pitch_length_mm', 'inside_length_mm', 'outside_length_mm', 'width_mm'):
            if getattr(self, key) is not None:
                positive(getattr(self, key), key)
        if profile.family == 'v':
            positive(self.datum_length_mm, 'V kayışında Ld gerekli; Li/La dönüşümü yapılmaz')
            if any(value is not None for value in (self.tooth_count, self.pitch_mm, self.pitch_length_mm)):
                raise ValueError('V kayışında triger-senkron diş/adım alanı olamaz.')
        else:
            integer(self.tooth_count, 'Kayış diş adedi')
            positive(self.width_mm, 'Triger-senkron kayış genişliği')
            if self.datum_length_mm is not None or self.pitch_mm != profile.pitch_mm:
                raise ValueError('Triger-senkron ürün profili/adımı veya referans çizgisi uyuşmuyor.')
            expected = positive(self.tooth_count * profile.pitch_mm, 'Bölüm uzunluğu')
            if self.pitch_length_mm is not None and not isclose(expected, self.pitch_length_mm, rel_tol=1e-12, abs_tol=1e-9):
                raise ValueError('Bölüm uzunluğu N×p ile uyuşmuyor.')

    @property
    def length_mm(self):
        return self.datum_length_mm if get_profile(self.profile).family == 'v' else self.tooth_count * self.pitch_mm


@dataclass(frozen=True, slots=True)
class PulleyProduct:
    code: str
    series_id: str
    source_id: str
    profile: str
    compatibility_id: str
    datum_diameter_mm: float | None = None
    teeth: int | None = None
    pitch_mm: float | None = None
    face_width_mm: float | None = None
    overall_width_mm: float | None = None
    outside_diameter_mm: float | None = None
    grooves: int | None = None
    material: str = ''
    nominal_belt_width_mm: float | None = None
    catalog_pitch_diameter_mm: float | None = None
    tooth_outside_diameter_mm: float | None = None
    flange_diameter_mm: float | None = None
    pilot_bore_mm: float | None = None
    catalog_face_dimension_f_mm: float | None = None
    construction_type: str = ''
    axial_min_mm: float | None = None  # Relative to aligned belt mid-plane, NOT a shaft datum.
    axial_max_mm: float | None = None

    def __post_init__(self):
        for key in ('code', 'series_id', 'source_id', 'compatibility_id'):
            text(getattr(self, key), key)
        text(self.material, 'material', optional=True)
        text(self.construction_type, 'construction_type', optional=True)
        profile = get_profile(self.profile)
        if not profile.nominal_supported:
            raise ValueError(profile.limitation)
        for key in ('datum_diameter_mm', 'pitch_mm', 'face_width_mm', 'overall_width_mm', 'outside_diameter_mm',
                    'nominal_belt_width_mm', 'catalog_pitch_diameter_mm', 'tooth_outside_diameter_mm',
                    'flange_diameter_mm', 'pilot_bore_mm', 'catalog_face_dimension_f_mm'):
            if getattr(self, key) is not None:
                positive(getattr(self, key), key)
        if self.grooves is not None:
            integer(self.grooves, 'Kanal adedi')
        if self.face_width_mm is not None and self.overall_width_mm is not None and self.overall_width_mm < self.face_width_mm:
            raise ValueError('Toplam kasnak genişliği yüz genişliğinden küçük olamaz.')
        if (self.axial_min_mm is None) != (self.axial_max_mm is None):
            raise ValueError('Eksenel zarfın iki sınırı birlikte verilmeli.')
        if self.axial_min_mm is not None:
            low=finite(self.axial_min_mm,'Eksenel alt sınır'); high=finite(self.axial_max_mm,'Eksenel üst sınır')
            span=positive(high-low,'Eksenel zarf genişliği')
            if self.overall_width_mm is not None and not isclose(span,self.overall_width_mm,abs_tol=1e-9,rel_tol=1e-12):
                raise ValueError('Eksenel zarf ile toplam kasnak genişliği uyuşmuyor.')
        if profile.family == 'v':
            positive(self.datum_diameter_mm, 'Datum çapı')
            if self.teeth is not None or self.pitch_mm is not None:
                raise ValueError('V kasnağında diş/adım verilmez.')
        else:
            integer(self.teeth, 'Kasnak diş sayısı')
            if self.datum_diameter_mm is not None or self.pitch_mm != profile.pitch_mm or self.grooves is not None:
                raise ValueError('Triger-senkron kasnak profil/adım/kanal uyuşmazlığı.')
            positive(self.teeth * self.pitch_mm / pi, 'Kasnak bölüm çapı')
            if self.catalog_pitch_diameter_mm is not None and abs(self.catalog_pitch_diameter_mm - self.diameter_mm) > .006:
                raise ValueError('Katalog Dp, z×p/π ile 0.01 mm tablo yuvarlama hassasiyetinde uyuşmuyor; kayıt karantinaya alınmalı.')

    @property
    def diameter_mm(self):
        return self.datum_diameter_mm if get_profile(self.profile).family == 'v' else self.teeth * self.pitch_mm / pi


@dataclass(frozen=True, slots=True)
class ProductCatalog:
    identifier: str
    revision: str
    sources: tuple[ProductSource, ...]
    belts: tuple[BeltProduct, ...]
    pulleys: tuple[PulleyProduct, ...]
    ratings: tuple = ()

    def __post_init__(self):
        from .rating_models import RatingTable
        text(self.identifier, 'Katalog kimliği'); text(self.revision, 'Katalog revizyonu')
        for key, cls in (('sources', ProductSource), ('belts', BeltProduct), ('pulleys', PulleyProduct), ('ratings', RatingTable)):
            items = sequence(getattr(self, key), key)
            if any(not isinstance(item, cls) for item in items):
                raise ValueError(f'{key}: yanlış kayıt türü.')
            object.__setattr__(self, key, items)
        source_ids = {source.identifier for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError('Mükerrer kaynak kimliği.')
        products = (*self.belts, *self.pulleys)
        keys = [(type(item).__name__, item.series_id, item.code) for item in products]
        if len(set(keys)) != len(keys):
            raise ValueError('Aynı seri içinde mükerrer ürün kodu.')
        for item in (*products, *self.ratings):
            if item.source_id not in source_ids:
                raise ValueError('Ürün/tablo kaynak kimliği bulunamadı: ' + item.source_id)
        rating_keys = [(item.series_id, item.profile) for item in self.ratings]
        if len(set(rating_keys)) != len(rating_keys):
            raise ValueError('Aynı seri/profil için belirsiz çoklu kapasite yöntemi.')
        series_manufacturers = {}
        for item in (*products, *self.ratings):
            manufacturer = self.source(item.source_id).manufacturer
            previous = series_manufacturers.setdefault(item.series_id, manufacturer)
            if manufacturer != previous:
                raise ValueError('Benzersiz seri kimliği farklı üreticilere atanamaz.')

    def source(self, identifier):
        return next(source for source in self.sources if source.identifier == identifier)
