"""Kalma süresi hacmi ve kararlı P=kAΔT tank ısı bilançosu.

Alt yüzey kapalı kabul edilir: açık üst + dört yan yüzey. Gerçek montaj,
boya, havalandırma ve yağ özellikleri için kullanıcı katsayısı gerekir.
"""
from .models import Thermal
from .validation import number, choice, InputError


def thermal_result(t: Thermal, pump_flow: float, average_loss: float) -> dict:
    choice(t.installation, ('stationary','mobile'), 'thermal.installation')
    for key in ('residence_time','length','width','height','heat_transfer','ambient','target'):
        number(getattr(t, key), 'thermal.' + key)
    number(pump_flow, 'pump_flow', zero=True); number(average_loss, 'average_loss', zero=True)
    number(t.fill_fraction, 'thermal.fill_fraction')
    if t.fill_fraction > 1 or t.target <= t.ambient:
        raise InputError('thermal.target', 'Doluluk ≤1 ve hedef sıcaklık ortamdan yüksek olmalı.')
    area = t.length * t.width + 2 * t.height * (t.length + t.width)
    return dict(required_volume=pump_flow * t.residence_time,
                gross_volume=t.length * t.width * t.height,
                usable_volume=t.length * t.width * t.height * t.fill_fraction,
                exposed_area=area, average_loss=average_loss,
                equilibrium_temperature=t.ambient + average_loss / (t.heat_transfer * area),
                cooler_power=max(0., average_loss - t.heat_transfer * area * (t.target - t.ambient)))
