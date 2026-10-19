"""Validate an explicitly confirmed, continuous 1D functional chain."""

from .models import KINDS, DISTRIBUTIONS, UNITS, number


def validate_dimension(dimension):
    if not isinstance(dimension.id,str) or not dimension.id or not isinstance(dimension.name,str) or not dimension.name.strip() or dimension.kind not in KINDS:
        raise ValueError('Ölçü kimliği, adı veya türü geçersiz.')
    if dimension.display_unit not in (*UNITS, 'rad', 'deg', 'unknown'):
        raise ValueError(f'{dimension.name}: birim tanınmıyor.')
    if not isinstance(dimension.geometry_kind,str) or dimension.geometry_kind and dimension.geometry_kind not in KINDS:
        raise ValueError(f'{dimension.name}: kaynak ölçünün geometrik türü tanınmıyor.')
    for value in (dimension.nominal, dimension.lower, dimension.upper):
        if value is not None:
            number(value, dimension.name)
    if dimension.lower is not None and dimension.upper is not None and dimension.lower > dimension.upper:
        raise ValueError(f'{dimension.name}: alt sapma üst sapmadan büyük.')
    if len(dimension.position) not in (0, 2, 3):
        raise ValueError(f'{dimension.name}: anotasyon konumu geçersiz.')
    for coordinate in dimension.position:number(coordinate,'Anotasyon konumu')


def validate(project, *, confirmed=True):
    for key in ('independent','truncate_normal','offline_snapshot'):
        if not isinstance(getattr(project,key),bool):raise ValueError(f'{key}: mantıksal değer olmalı.')
    if not project.name.strip() or not project.critical.strip():
        raise ValueError('Analiz adını ve kritik fonksiyonel ölçüyü belirtin.')
    if not project.terms or len(project.terms) > 1000:
        raise ValueError('Zincirde 1–1000 ölçü bulunmalı.')
    if not project.start.strip() or not project.end.strip() or project.start == project.end:
        raise ValueError('Zincirin farklı başlangıç ve bitiş noktalarını tanımlayın.')
    if project.axis not in ('X', 'Y', 'Z') or not project.datum.strip():
        raise ValueError('Ortak doğrusal eksen ve datum/konum referansını belirtin.')
    if project.method not in ('worst_case', 'rss', 'all') or project.distribution not in DISTRIBUTIONS:
        raise ValueError('Analiz yöntemi veya dağılım tanınmıyor.')
    if not isinstance(project.samples, int) or isinstance(project.samples, bool) or not 1000 <= project.samples <= 1000000:
        raise ValueError('Monte Carlo örnek sayısı 1.000–1.000.000 arasında tam sayı olmalı.')
    if project.seed is not None and (not isinstance(project.seed, int) or isinstance(project.seed, bool)):
        raise ValueError('Seed tam sayı veya boş olmalı.')
    if not 1 <= number(project.input_sigma) <= 8 or not 1 <= number(project.output_sigma) <= 8:
        raise ValueError('Giriş/sonuç σ katsayısı 1–8 aralığında olmalı.')
    if project.method != 'worst_case' and not project.independent:
        raise ValueError('RSS/Monte Carlo için bağımsızlık kabulü gerekli. Korelasyon modeli bu sürümde desteklenmiyor; Worst-Case seçilebilir.')
    low, high = project.acceptance_min, project.acceptance_max
    for value in (low, high):
        if value is not None:
            number(value, 'Kabul sınırı')
    if low is not None and high is not None and low > high:
        raise ValueError('Minimum kabul sınırı maksimumdan büyük.')
    for item in project.dimensions:validate_dimension(item)
    dimensions = {item.id: item for item in project.dimensions}
    if len(dimensions) != len(project.dimensions):
        raise ValueError('Çift ölçü kimliği var; ölçüleri yeniden okuyun.')
    used = set()
    points={project.start}
    previous = project.start
    for index, term in enumerate(project.terms, 1):
        dimension = dimensions.get(term.dimension_id)
        if dimension is None:
            raise ValueError(f'L{index}: kaynak ölçü silinmiş veya bulunamadı; yeniden tarayın.')
        validate_dimension(dimension)
        identity = dimension.physical_id or dimension.id
        if identity in used:
            raise ValueError(f'{dimension.name}: aynı kaynak ölçü iki kez kullanılmış. Bağımsız kabul edilemez; zinciri düzeltin.')
        used.add(identity)
        if dimension.kind=='reference':
            raise ValueError(f'{dimension.name}: referans ölçü. Ölçüyü düzenle ile nominal/tolerans değerlerini '
                             've analizde kullanımını doğrulayın; üretim ölçüsü değiştirilmez.')
        if dimension.kind in ('angle', 'gdt', 'basic', 'arc', 'chamfer', 'unknown'):
            raise ValueError(f'{dimension.name}: {dimension.kind} türü doğrudan 1D uzunluk zincirine alınamaz. Ayrı matematiksel model gerekli.')
        if dimension.kind in ('diameter', 'radius') and not term.relation.strip():
            raise ValueError(f'{dimension.name}: çap/radyüsün doğrusal fonksiyonel ilişkisini ve katsayısını açıkça tanımlayın.')
        if dimension.source and not term.relation.strip():
            raise ValueError(f'{dimension.name}: kaynak görünümün ortak fonksiyonel datum/eksene eşlemesini İlişki alanında açıklayın; çizim konumundan yön çıkarılmaz.')
        if dimension.nominal is None or dimension.lower is None or dimension.upper is None:
            raise ValueError(f'{dimension.name}: nominal veya tolerans bilinmiyor; manuel tamamlayın. Genel tolerans atanmadı.')
        if dimension.display_unit in ('rad', 'deg', 'unknown'):
            raise ValueError(f'{dimension.name}: uzunluk birimi doğrulanamadı.')
        if not isinstance(term.direction,int) or isinstance(term.direction, bool) or term.direction not in (-1, 1):
            raise ValueError(f'L{index}: yön +1 veya −1 olmalı.')
        if not 0 < number(term.factor) <= 1000:
            raise ValueError(f'L{index}: izdüşüm/ilişki katsayısı 0–1000 aralığında ve sıfırdan büyük olmalı.')
        if term.factor != 1 and not term.relation.strip():
            raise ValueError(f'L{index}: farklı katsayının fonksiyonel ilişkisini açıklayın.')
        if term.axis != project.axis or term.datum != project.datum:
            raise ValueError(f'L{index}: ortak eksen/datum ile eşleşmiyor. Farklı çizim referanslarını kullanıcı eşlemeli.')
        if term.start != previous or not term.end.strip() or term.start == term.end:
            raise ValueError(f'L{index}: zincir süreksiz; başlangıç/bitiş noktalarını ve sıralamayı düzeltin.')
        if term.end in points:raise ValueError(f'L{index}: zincir aynı noktaya dönüyor; 1D fonksiyonel zincirde döngüyü düzeltin.')
        points.add(term.end)
        previous = term.end
        if term.distribution not in (*DISTRIBUTIONS, 'inherit'):
            raise ValueError(f'L{index}: dağılım tanınmıyor.')
        for value in (term.mean, term.sigma, term.mode):
            if value is not None:
                number(value, f'L{index} dağılım parametresi')
        if term.sigma is not None and term.sigma < 0:
            raise ValueError('Standart sapma negatif olamaz.')
    if previous != project.end:
        raise ValueError('Zincirin son noktası analiz bitişiyle eşleşmiyor.')
    if confirmed and project.confirmed_digest != project.fingerprint():
        raise ValueError('Zincirin yönlerini, başlangıç/bitişini ve fonksiyonel datum ilişkisini doğrulayın. Değişiklik sonrası yeniden onay gerekir.')
    return dimensions
