"""Validate an explicitly confirmed, continuous 1D functional chain."""

from .models import KINDS, DISTRIBUTIONS, UNITS, number


class ChainIssue(ValueError):
    """An actionable validation failure, usable by Qt and headless clients."""

    def __init__(self, message, *, action='', target='settings', term_index=None, dimension_id=''):
        super().__init__(message)
        self.action = action
        self.target = target
        self.term_index = term_index
        self.dimension_id = dimension_id


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
        raise ChainIssue('Analize bir ad verin ve hesaplamak istediğiniz mesafeyi belirtin.', action='Analiz ayarlarını aç')
    if not project.terms or len(project.terms) > 1000:
        raise ChainIssue('Henüz ölçü eklenmedi. Soldan bir ölçü seçip + Topla veya − Çıkar düğmesine basın.'
                         if not project.terms else 'Bir analizde en fazla 1.000 ölçü kullanılabilir.', target='library')
    if not project.start.strip() or not project.end.strip() or project.start == project.end:
        raise ChainIssue('Zincirin başlangıç ve bitişi aynı veya eksik. Bağlantıları yeniden sıraya bağlayın.',
                         action='Bağlantıları düzelt', target='relink')
    if project.axis not in ('X', 'Y', 'Z') or not project.datum.strip():
        raise ChainIssue('Ölçüm doğrultusu veya ortak referans eksik. Gelişmiş ayarlardan tamamlayın.',
                         action='Ölçüm doğrultusunu aç', target='frame')
    if project.method not in ('worst_case', 'rss', 'all') or project.distribution not in DISTRIBUTIONS:
        raise ValueError('Analiz yöntemi veya dağılım tanınmıyor.')
    if not isinstance(project.samples, int) or isinstance(project.samples, bool) or not 1000 <= project.samples <= 1000000:
        raise ChainIssue('Benzetim sayısı 1.000–1.000.000 arasında tam sayı olmalı.', action='İstatistik ayarlarını aç', target='statistics')
    if project.seed is not None and (not isinstance(project.seed, int) or isinstance(project.seed, bool)):
        raise ChainIssue('Rastgelelik anahtarı (seed) tam sayı olmalı. Rastgele sonuç için alanı boş bırakabilirsiniz.', action='İstatistik ayarlarını aç', target='statistics')
    if not 1 <= number(project.input_sigma) <= 8 or not 1 <= number(project.output_sigma) <= 8:
        raise ChainIssue('İstatistiksel bant katsayıları 1–8 arasında olmalı.', action='İstatistik ayarlarını aç', target='statistics')
    if project.method != 'worst_case' and not project.independent:
        raise ChainIssue('RSS ve Monte Carlo, ölçülerin birbirinden bağımsız olmasını gerektirir. '
                         'Korelasyon hesabı desteklenmiyor; yalnız Worst-Case yöntemini seçebilirsiniz.', action='Hesap yöntemini değiştir')
    low, high = project.acceptance_min, project.acceptance_max
    for value in (low, high):
        if value is not None:
            number(value, 'Kabul sınırı')
    if low is not None and high is not None and low > high:
        raise ChainIssue('İstenen en küçük sonuç, en büyük sonuçtan büyük olamaz. Kabul aralığını düzeltin.', action='Kabul aralığını düzelt')
    for item in project.dimensions:validate_dimension(item)
    dimensions = {item.id: item for item in project.dimensions}
    if len(dimensions) != len(project.dimensions):
        raise ValueError('Çift ölçü kimliği var; ölçüleri yeniden okuyun.')
    used = set()
    points={project.start}
    previous = project.start
    for index, term in enumerate(project.terms, 1):
        dimension = dimensions.get(term.dimension_id)
        def problem(message, action='Ölçü ayarlarını aç', target='term'):
            name = '' if dimension is None else ' (' + dimension.name.split('@', 1)[0] + ')'
            return ChainIssue(f'L{index}{name}: {message}', action=action, target=target,
                              term_index=index-1, dimension_id=term.dimension_id)
        if dimension is None:
            raise problem('kaynak ölçü bulunamadı. Teknik resmi yeniden okuyun veya bu satırı zincirden çıkarın.',
                          'Teknik resimleri yeniden oku', 'scan')
        validate_dimension(dimension)
        identity = dimension.physical_id or dimension.id
        if identity in used:
            raise problem('aynı fiziksel ölçü iki kez eklenmiş. Tekrarlanan satırı çıkarın; iki ayrı parça ölçüsüyse bağımsız ölçüler tanımlayın.',
                          'Tekrarlanan satırı seç', 'select_term')
        used.add(identity)
        if dimension.kind=='reference':
            raise problem('bu bir referans ölçü. Değerini ve toleransını analiz için kontrol edip doğrulayın.',
                          'Referans ölçüyü kontrol et', 'dimension')
        if dimension.kind in ('angle', 'gdt', 'basic', 'arc', 'chamfer', 'unknown'):
            raise problem('bu ölçü türü doğrusal mesafe hesabında kullanılamıyor. Açısal, BASIC ve geometrik kontrolleri bu zincire eklemeyin.',
                          'İlgili satırı seç', 'select_term')
        if dimension.kind in ('diameter', 'radius') and not term.relation.strip():
            raise problem('çap veya radyüsün hangi mesafeyi temsil ettiğini seçin. Örneğin çap için 1, yarıçap etkisi için 0,5 katsayısı kullanılır.',
                          'Çap / radyüs ilişkisini seç')
        if not isinstance(term.alignment_confirmed, bool):
            raise problem('ölçüm doğrultusu kontrolü geçersiz. Bu ölçünün ayarlarını yeniden kaydedin.')
        if dimension.source and not term.relation.strip() and not term.alignment_confirmed:
            raise problem('bu ölçünün zincirle aynı doğrultuda ve ortak referansa göre alındığını kontrol edin. '
                          'Zincirin altındaki doğrulama kutusunu işaretleyin; açıklama yazmanız gerekmez.',
                          'Doğrulama kutusuna git', 'confirm')
        if dimension.nominal is None or dimension.lower is None or dimension.upper is None:
            raise problem('ölçü değeri veya toleransı eksik. Teknik resimdeki gerçek değerlerle tamamlayın; otomatik tolerans atanmaz.',
                          'Eksik ölçüyü tamamla', 'dimension')
        if dimension.display_unit in ('rad', 'deg', 'unknown'):
            raise problem('uzunluk birimi okunamadı. Ölçüyü açıp doğru birimi ve değerleri girin.', 'Ölçü birimini düzelt', 'dimension')
        if not isinstance(term.direction,int) or isinstance(term.direction, bool) or term.direction not in (-1, 1):
            raise problem('işlem yönü geçersiz. Topla (+) veya Çıkar (−) seçin.')
        if not 0 < number(term.factor) <= 1000:
            raise problem('ölçü katsayısı sıfırdan büyük, en fazla 1.000 olmalı. Ölçüyü doğrudan kullanmak için 1 girin.')
        if term.factor != 1 and not term.relation.strip():
            raise problem('1 dışında bir katsayı seçilmiş. Ölçünün nasıl dönüştürüldüğünü ölçü ayarlarında belirtin.')
        if term.axis != project.axis or term.datum != project.datum:
            raise problem(f'bu satırın doğrultusu veya referansı zincirden farklı. Zincir: {project.axis} / {project.datum}; '
                          f'bu ölçü: {term.axis} / {term.datum}. Ölçü ayarlarında eşleştirin.')
        if term.start != previous or not term.end.strip() or term.start == term.end:
            raise problem('bağlantı süreksiz: bu ölçü önceki ölçünün bittiği noktadan başlamıyor. Sırayı kontrol edip bağlantıları düzeltin.',
                          'Bağlantıları düzelt', 'relink')
        if term.end in points:
            raise problem('zincir aynı noktaya dönüyor. Başlangıç/bitiş noktalarını ve sırayı düzeltin.', 'Bağlantıları düzelt', 'relink')
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
        raise ChainIssue('Zincirin son noktası analiz bitişiyle eşleşmiyor. Bağlantıları yeniden sıraya bağlayın.', action='Bağlantıları düzelt', target='relink')
    if confirmed and project.confirmed_digest != project.fingerprint():
        raise ChainIssue('Ölçüleri ve + / − yönlerini doğrulayın: zincirin altındaki kontrol kutusunu işaretleyin. '
                         'Bir değer değiştiğinde bu kontrol yeniden gerekir.', action='Doğrulama kutusuna git', target='confirm')
    return dimensions
