"""Assembly method and typical uses for an ISO 286 fit (guidance, not a calculation).

The fit *type* comes from the verified limits (``rules.Fit.kind``). The assembly
method is derived only from that type and from whether the minimum clearance is
zero; no press force, temperature or interference capacity is computed here.
Usage examples are common design-guide examples for the curated preset pairs
and are shown as suggestions that must be checked for the application.
"""

from dataclasses import dataclass

from . import rules as r
from .manual import closest_preset

TONES = {'clearance': 'success', 'transition': 'warning', 'interference': 'danger'}
GROUP_TITLES = {'clearance': 'BOŞLUKLU GEÇMELER (ELLE MONTAJ)',
                'transition': 'ARA GEÇMELER (HAFİF ÇAKMA)',
                'interference': 'SIKI GEÇMELER (PRES / ISIL)'}
USAGE_NOTE = 'genel tasarım örnekleridir; yük, malzeme ve çalışma koşuluna göre doğrulayın.'

# Common examples from general machine-design guidance, per curated preset.
USAGE = {
    'H11/c11': 'Gevşek çalışma: tarım ve inşaat makinelerinde pim ve mafsallar, kirli ortamdaki yataklar.',
    'H9/d9': 'Serbest dönme: avara kasnaklar, gevşek yataklar, sıcaklık farkı büyük yataklar.',
    'H8/e8': 'Boşluklu kılavuzlama: çok yataklı miller, düşük hassasiyetli kayar kılavuzlar.',
    'H8/f7': 'Hareketli eşleşme: dişli kutusu ve pompa mili yatakları, kayar burçlar.',
    'H7/g6': 'Hassas kayar geçme: kılavuz pimleri, kayar dişliler, hassas mil yatakları.',
    'H7/h6': 'Konumlandırma: sökülebilir merkezleme, değiştirilebilir burç ve flanşlar.',
    'H8/h7': 'Kayar eşleşme: makine kızakları, sökülebilir kılavuz parçalar.',
    'H7/js6': 'Konumlandırma: kolay sökülen kasnak ve dişliler, hafif yüklü rulman iç bilezikleri.',
    'H7/k6': 'Konumlandırma: kamalı dişli, kasnak ve kaplin göbekleri; rulman iç bilezikleri.',
    'H7/m6': 'Dar ara geçme: çakılarak takılan dişliler ve kaplinler, seyrek sökülen göbekler.',
    'H7/n6': 'Hafif pres: rulman dış bilezikleri, burçlar, seyrek sökülen göbekler.',
    'H7/p6': 'Pres geçme: yatak burçları, kalıcı konum pimleri, dişli/mil sıkı geçmesi.',
    'H7/r6': 'Orta pres: çelik göbekler, kalıcı burçlar.',
    'H7/s6': 'Kalıcı montaj: sıcak/soğuk geçme, dökme demir göbekte çelik bilezik.',
    'H6/h5': 'Hassas konumlandırma: ölçü aletleri, hassas yataklar.',
    'H6/k6': 'Dar toleranslı konumlandırma: hassas dişli ve kaplin göbekleri.',
    'H8/k6': 'Geniş delik toleranslı konumlandırma: kasnak ve dişli göbekleri.',
    'G7/h6': 'Mil esaslı küçük boşluk: çekme mil üzerinde hassas kayar parçalar.',
    'F8/h6': 'Mil esaslı hareketli eşleşme: ortak mil üzerinde dönen parçalar.',
    'JS7/h6': 'Mil esaslı konumlandırma: simetrik delik bölgesi, kolay sökülen göbekler.',
    'K7/h6': 'Mil esaslı konumlandırma: rulman dış bilezik yuvaları, kaplin göbekleri.',
    'N7/h6': 'Mil esaslı dar ara geçme: burçlar, çakılarak takılan göbekler.',
    'P7/h6': 'Mil esaslı sıkılık: kalıcı burçlar ve konum pimleri.',
}


@dataclass(frozen=True)
class Assembly:
    icon: str        # slide / push / hammer / press
    title: str
    detail: str
    tone: str


def assembly(fit):
    """Assembly method from the computed fit type (no force or temperature model)."""
    if fit.kind == 'interference':
        return Assembly('press', 'PRES / ISIL MONTAJ',
                        'Hidrolik pres veya sıcak/soğuk geçme. Sıkılık kuvveti ve sıcaklık hesabı bu ekranda yapılmaz.',
                        'danger')
    if fit.kind == 'transition':
        return Assembly('hammer', 'HAFİF ÇAKMA',
                        'Tokmak veya el presi; gerçekleşen ölçüye göre küçük boşluk ya da sıkılık oluşur.', 'warning')
    if fit.minimum_clearance_nm == 0:
        return Assembly('push', 'ELLE İTME',
                        'Sınırda temas: elle itme veya plastik tokmakla takılır; yağlama önerilir.', 'success')
    return Assembly('slide', 'ELLE MONTAJ', 'Boşluklu: parça elle takılır ve kayar; yağlama önerilir.', 'success')


def usage(fit):
    """(text, source code, exact) — examples of the same or nearest curated preset."""
    code = f'{fit.hole.code}/{fit.shaft.code}'
    if code in USAGE:
        return USAGE[code], code, True
    nearest = closest_preset(fit)
    key = nearest.code.replace(' ', '')
    return USAGE.get(key, ''), key, False


def preset_rows(diameter, basis):
    """Grouped preset rows for the list: category header rows, then cards with their fit type."""
    rows = [dict(id=kind, parent='', name=title, kind=kind, header=True) for kind, title in GROUP_TITLES.items()]
    for preset in r.PRESETS:
        if basis not in ('Tümü', preset.basis):
            continue
        try:
            kind = r.calculate(diameter, preset.hole, preset.shaft).kind
        except ValueError:
            kind = 'clearance'
        rows.append(dict(id=preset.code, parent=kind, name=f'{preset.code} · {preset.label}', title=f'{preset.hole} / {preset.shaft}',
                         label=preset.label, kind=kind, hole=preset.hole, shaft=preset.shaft))
    return rows
