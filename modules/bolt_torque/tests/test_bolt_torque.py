"""Quick torque mechanics, ISO strength bases, thread geometry and units."""

from math import isfinite
from pathlib import Path
import subprocess
import sys

import pytest

from modules.bolt_torque.rules import (calculate, strength_for, pitch_choices, METRICS,
                               GRADES, THREAD_SERIES, CONDITIONS)


def test_m10_88_dry_reference_and_explicit_units():
    result = calculate()
    # Independent rounded ISO stress-area reference: As ≈ 58.0 mm².
    assert result.tensile_area_mm2 == pytest.approx(58.0, abs=.02)
    assert result.preload_n == pytest.approx(25984, abs=10)
    assert result.preload_kn == pytest.approx(25.979339412, abs=1e-8)
    assert result.diameter_m == .01
    assert result.torque_nm == pytest.approx(51.958678824, abs=1e-8)
    assert result.preload_percent == 70 and result.k == .20


@pytest.mark.parametrize('metric,area', [('M3',5.03),('M4',8.78),('M5',14.2),('M6',20.1),
    ('M8',36.6),('M10',58.0),('M12',84.3),('M16',157),('M18',192),('M20',245),('M24',353),('M36',817)])
def test_stress_area_matches_rounded_metric_references(metric, area):
    # Integer reference areas have 1 mm² resolution (e.g. 156.668 -> 157).
    assert calculate(metric=metric).tensile_area_mm2 == pytest.approx(area, rel=.002, abs=.5 if area >= 100 else 0)


@pytest.mark.parametrize('grade,expected,symbol', [('4.8',320,'Rp0,2'),('5.8',400,'Rp0,2'),
    ('8.8',640,'ReL'),('10.9',940,'Rp0,2'),('12.9',1100,'Rp0,2')])
def test_grade_values_use_the_documented_yield_basis(grade, expected, symbol):
    result = calculate(grade=grade)
    assert result.yield_strength_mpa == expected and result.strength_symbol == symbol
    assert ('nominal' in result.strength_basis) == (grade in ('4.8','5.8'))


def test_88_diameter_boundary_applies_to_both_thread_series():
    for series in THREAD_SERIES:
        assert calculate(metric='M16',thread_series=series).yield_strength_mpa == 640
        assert calculate(metric='M18',thread_series=series).yield_strength_mpa == 660
        assert calculate(metric='M36',thread_series=series).yield_strength_mpa == 660
    assert 'd > 16' in strength_for('M18','8.8').basis
    # 8.8 coarse proof stress Sp=580/600 must not enter this preload formula.
    assert calculate().yield_strength_mpa != 580


def test_condition_k_and_preload_percentage_are_independent():
    dry = calculate()
    oil = calculate(condition='Hafif yağlı')
    custom = calculate(condition='Hafif yağlı', k='0,18')
    half = calculate(preload_percent='35')
    assert oil.torque_nm == pytest.approx(dry.torque_nm*.75)
    assert oil.preload_n == dry.preload_n and oil.k == .15
    assert custom.torque_nm == pytest.approx(dry.torque_nm*.9)
    assert custom.custom_k and not oil.custom_k
    assert half.preload_n == dry.preload_n/2 and half.torque_nm == dry.torque_nm/2
    assert calculate(preload_percent=0).torque_nm == 0
    assert calculate(preload_percent=100).preload_n == pytest.approx(dry.preload_n/.7)


def test_fine_threads_use_the_selected_pitch_and_stress_area():
    coarse = calculate()
    fine = calculate(thread_series='İnce diş',pitch='1,25')
    assert fine.tensile_area_mm2 == pytest.approx(61.195, abs=.01)
    assert fine.preload_n > coarse.preload_n and fine.torque_nm > coarse.torque_nm
    assert calculate(thread_series='İnce diş',pitch='1').tensile_area_mm2 == pytest.approx(64.497,abs=.01)
    assert pitch_choices('M10') == (1.5,)
    assert pitch_choices('M10','İnce diş') == (1.25,1.,.75)


@pytest.mark.parametrize('metric', METRICS)
def test_supported_diameters_grades_and_pitches_are_finite_positive(metric):
    for series in THREAD_SERIES:
        for pitch in pitch_choices(metric,series):
            for grade in GRADES:
                for condition in CONDITIONS:
                    result = calculate(metric=metric,thread_series=series,pitch=pitch,grade=grade,condition=condition)
                    assert 3 <= result.diameter_mm <= 36
                    assert isfinite(result.torque_nm) and result.torque_nm > 0


@pytest.mark.parametrize('changes', [dict(metric='M2'),dict(metric='M39'),dict(metric=[]),dict(grade='4.6'),
    dict(grade={}),dict(thread_series='UNC'),dict(condition='Kaplamalı'),dict(pitch=1.25),
    dict(thread_series='İnce diş',pitch=1.5),dict(pitch=True),dict(pitch='nan'),dict(pitch=''),
    dict(k=0),dict(k=-.2),dict(k=''),dict(k='nan'),dict(k='inf'),dict(k=True),dict(k=1e308),
    dict(preload_percent=''),dict(preload_percent='nan'),dict(preload_percent=True),
    dict(preload_percent=-1),dict(preload_percent=101),dict(preload_percent=None)])
def test_invalid_values_never_return_a_plausible_torque(changes):
    with pytest.raises(ValueError): calculate(**changes)


def test_manual_coefficient_and_decimal_comma_without_gui_imports():
    result = calculate(k='0,175',preload_percent='62,5')
    assert result.k == .175 and result.preload_percent == 62.5
    assert result.torque_nm == pytest.approx(.175 * result.preload_n * .01)


def test_calculation_imports_without_qt_or_solidworks():
    code = ('import sys; from modules.bolt_torque import calculate; '
            'assert calculate().torque_nm > 0; '
            'assert not any(n in sys.modules for n in ("PySide6", "solidworks", "pythoncom", "tkinter"))')
    subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[3],check=True,timeout=10)
