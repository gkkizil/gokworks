"""Qt-free presentation helpers for the belt page: labels, numbers, job factories.

Nothing here decides engineering suitability; it only names backend states
without upgrading them (PROVISIONAL is never "manufacturer verified",
NOT_EVALUATED is never zero or passed).
"""

import json
from pathlib import Path

from .catalog.importers import load_catalog
from .catalog.profiles import PROFILES, get_profile

HERE = Path(__file__).resolve().parent
BUNDLED_CATALOGS = (
    ('tosyali', 'Tosyalı · kullanıcı PDF\'inden 342 kasnak kaydı', HERE / 'catalog/data/tosyali-user-pdf.json'),
    ('synthetic', 'Sentetik örnek katalog (gerçek ürün değil)', HERE / 'examples/automatic-synthetic-catalog.json'),
)
TOSYALI_AUDIT = HERE / 'catalog/data/tosyali-import-audit.json'

FAMILY_TITLES = {'v': 'V kayışı', 'timing': 'Triger-senkron kayış'}
SEVERITY_TITLES = {'ERROR': 'Hata', 'WARNING': 'Uyarı', 'INFO': 'Bilgi', 'NOT_EVALUATED': 'Değerlendirilmedi'}
SEVERITY_TOKENS = {'ERROR': 'danger', 'WARNING': 'warning', 'INFO': 'muted', 'NOT_EVALUATED': 'muted'}
CAPACITY_TITLES = {
    'PROVISIONAL': 'Geçici (beyan edilen tablo; üretici doğrulaması yok)',
    'NOT_EVALUATED': 'Değerlendirilmedi',
}
CANDIDATE_TITLES = {'UNVERIFIED': 'Doğrulanmamış', 'CAPACITY_VERIFIED': 'Kapasite kaynağı doğrulanmış'}
SOURCE_TITLES = {
    'OFFICIAL_VERIFIED': 'Resmî doğrulanmış (beyan)', 'USER_SUPPLIED': 'Kullanıcı tarafından sağlanan',
    'EXAMPLE': 'Örnek / sentetik', 'OUTDATED': 'Eski', 'INCOMPLETE': 'Eksik',
}
PRIORITY_TITLES = (
    ('speed', 'Devir sapması en küçük'), ('compact', 'En küçük referans alanı'), ('fewest_belts', 'En az kayış adedi'),
    ('capacity', 'En yüksek kapasite oranı'), ('center', 'Hedef C\'ye en yakın'), ('balanced', 'Dengeli (ağırlıklı)'),
)
METRIC_TITLES = (
    ('speed', 'Devir sapması'), ('center', 'C sapması'), ('area', 'Referans alanı'), ('belts', 'Kayış adedi'),
    ('width', 'Toplam genişlik'), ('capacity', 'Kapasite (1/oran)'), ('source', 'Kaynak durumu'),
)
REJECTION_TITLES = {
    'PULLEY_DIAMETER': 'Kasnak çapı sınır dışında', 'OUTSIDE_DIAMETER': 'Dış çap sınır dışında',
    'PULLEY_TEETH': 'Diş sayısı sınır dışında', 'PAIR_CALCULATION': 'Çift hesaplanamadı',
    'RPM_TOLERANCE': 'Devir sapması sınırı aşıldı', 'CENTER_GEOMETRY': 'C üst sınırı kasnaklar için çok küçük',
    'PAIR_GEOMETRY': 'Çift geometrisi çözülemedi', 'GROOVE_COMPATIBILITY': 'Kanal adetleri farklı',
    'BELT_COUNT': 'Kayış adedi sınırı aşıldı', 'LENGTH_CENTER_BOUNDS': 'Kayış boyu C sınırlarına uymuyor',
    'FACE_WIDTH': 'Kayış kasnak genişliğine sığmıyor', 'SYSTEM_WIDTH': 'Toplam genişlik sınırı aşıldı',
    'AXIAL_BELT_PLANE': 'Kayış düzlemi kasnak eksenel zarfı dışında', 'CENTER_BOUNDS': 'Gerçekleşen C sınır dışında',
    'OUTER_BODY_CLEARANCE': 'Kasnak dış gövdeleri çakışıyor', 'DECLARED_MINIMUM_PULLEY': 'Beyan edilen minimum kasnak altında',
    'DECLARED_SPEED_LIMIT': 'Beyan edilen hız sınırı aşıldı', 'DECLARED_INSUFFICIENT_CAPACITY': 'Beyan edilen kapasite yetersiz',
    'ADJUSTMENT_TRAVEL': 'Ayar mesafesi yetersiz', 'CALCULATION': 'Hesap hatası',
}


def number(value, digits=3):
    """Turkish decimal comma; None is shown as an em dash, never as 0."""
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'evet' if value else 'hayır'
    if isinstance(value, int):
        return str(value)
    text = f'{value:.{digits}f}'
    if '.' in text:
        text=text.rstrip('0').rstrip('.')
    return (text if text not in ('-0', '') else '0').replace('.', ',')


def profiles(family):
    """Supported profiles of one family, in catalogue order."""
    return tuple(p for p in PROFILES if p.family == family and p.nominal_supported)


def profile_title(profile):
    if profile.family == 'v':
        return f'{profile.key} · {"klasik" if profile.series == "classical" else "dar"}'
    return f'{profile.key.replace("_", " ")} · p = {number(profile.pitch_mm)} mm'


def load_bundled(key):
    for identifier, title, path in BUNDLED_CATALOGS:
        if identifier == key:
            return load_catalog(path)
    raise ValueError('Bilinmeyen yerleşik katalog.')


def tosyali_audit():
    data = json.loads(TOSYALI_AUDIT.read_text(encoding='utf-8'))
    return data


def pulley_pairs_job(request, catalog):
    """JobManager operation for the partial pulley-pair search (no Qt objects)."""
    def run(events, stop):
        from .design_pairs import search_pulley_pairs
        report = search_pulley_pairs(request, catalog, stop=stop)
        events.put(('belt_pairs_cancelled' if report.cancelled else 'belt_pairs_result', report))
    return run


def project_job(project):
    """Recalculate an opened project; saved numbers are never shown as current."""
    def run(events, stop):
        from .design_serialization import recalculate_project
        outcome, selected = recalculate_project(project, stop=stop)
        events.put(('belt_project_result', (project, outcome, selected)))
    return run


def get_family(profile_key):
    return get_profile(profile_key).family
