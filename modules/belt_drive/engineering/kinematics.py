"""Ideal no-slip kinematics. Diameters mm, power kW, speed rpm/m/s, torque N·m."""

import math
from .._numbers import positive, integer


def pitch_diameter_mm(teeth, pitch_mm):
    return positive(integer(teeth, 'Diş sayısı') * positive(pitch_mm, 'Adım') / math.pi, 'Bölüm çapı')


def transmission_ratio(driver_diameter_mm, driven_diameter_mm):
    return positive(positive(driven_diameter_mm, 'Sürülen çap') / positive(driver_diameter_mm, 'Sürücü çap'), 'Oran')


def belt_speed_m_s(diameter_mm, rpm):
    return positive(positive(diameter_mm, 'Referans çap') * (positive(rpm, 'Devir') / 60000.) * math.pi, 'Kayış hızı')


def torque_nm(power_kw, rpm):
    return positive((positive(power_kw, 'Güç') / positive(rpm, 'Devir')) * (60000. / (2. * math.pi)), 'Tork')


def power_kw(torque, rpm):
    return positive(positive(torque, 'Tork') * (positive(rpm, 'Devir') / 60000.) * (2. * math.pi), 'Güç')
