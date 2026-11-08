"""Arayüz ve raporun ortak, Qt'siz sonuç tablosu ve formül açıklamaları."""
from .core.units import convert


def result_rows(project, result):
    c = result.cycle; p = result.pipe; t = result.thermal
    pressure = 'psi' if project.display_units == 'us' else 'bar'
    flow = 'gpm' if project.display_units == 'us' else 'L/min'
    rows = []
    def add(label, value, source, unit, formula):
        rows.append((label, None if value is None else convert(value, source, unit), unit, formula))
    add('Maksimum gerekli debi', c['max_flow'], 'm3/s', flow, 'Q = A etkin × v')
    add('Maksimum gerekli basınç', c['max_pressure'], 'Pa', pressure, 'p = (F/η + p karşı × A karşı) / A etkin + Δp hat')
    add('Emniyet valfi ayarı', c['relief_pressure'], 'Pa', pressure, 'max(p ihtiyaç, p kompansatör) × katsayı veya kullanıcı ayarı')
    add('Tepe mil gücü', c['peak_power'], 'W', 'kW', 'P = p besleme × Q besleme / (ηv × ηhm)')
    add('RMS mil gücü', c['rms_power'], 'W', 'kW', '√(Σ P²t / Σt)')
    add('Seçilen motor', c['selected_motor'], 'W', 'kW', 'Pnom ≥ Prms; Pnom(1+aşırı yük) ≥ Ptepe')
    add('Gerekli deplasman', c['displacement']['required'] * 1e6, 'cm3/rev', 'cm3/rev', 'Vg = Q / (n × ηv)')
    add('Nominal deplasman adayı', None if c['displacement']['nominal'] is None else c['displacement']['nominal'] * 1e6,
        'cm3/rev', 'cm3/rev', 'Nominal seride yukarı seçim; ürün garantisi değil')
    add('Çevrim süresi', c['duration'], 's', 's', 'Σt faz')
    rows.append(('Çevrim kayıp enerjisi', c['loss_energy'] / 1000, 'kJ', 'Σ(Pmil − Fv)t; sağlanamayan fazda yalnız senaryo'))
    add('Boru/hortum iç çapı', p['diameter'], 'm', 'mm', 'd = √(4Q / πv), nominal seride yukarı seçim')
    add('Gerçek hat hızı', p['velocity'], 'm/s', 'm/s', 'v = 4Q / πd²')
    rows.append(('Reynolds', p['reynolds'], '—', 'Re = vd / ν'))
    add('Hat basınç kaybı', p['pressure_drop'], 'Pa', pressure, 'Δp = (λL/d + Σζ)ρv²/2')
    add('Gerekli kullanılabilir tank', t['required_volume'], 'm3', 'L', 'V = Q pompa × kalma süresi')
    add('Mevcut kullanılabilir tank', t['usable_volume'], 'm3', 'L', 'L × W × H × doluluk')
    add('Çevrim ortalama ısı yükü', t['average_loss'], 'W', 'kW', 'ΣE kayıp / Σt')
    rows.append(('Soğutucusuz denge', convert(t['equilibrium_temperature'], 'K', '°C'), '°C', 'Tamb + Pkayıp / kA'))
    add('Gerekli soğutucu', t['cooler_power'], 'W', 'kW', 'max(0, Pkayıp − kA(T hedef − T ortam))')
    if result.accumulator.get('status') == 'calculated':
        add('Gerekli akümülatör', result.accumulator['required_volume'], 'm3', 'L', 'ΔV / [(p0/p1)^(1/n) − (p0/p2)^(1/n)], mutlak basınç')
        add('Nominal akümülatör', result.accumulator['nominal_volume'], 'm3', 'L', 'Nominal seride yukarı seçim')
    return rows
