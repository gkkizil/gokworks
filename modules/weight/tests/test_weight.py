"""Weight engine: reference values, every section type, standard catalogue, units and validation."""

import math

import pytest

from modules.weight import catalog, rules, sections

STEEL = 7850


# ---- 1. reference values requested for acceptance ----------------------------------
@pytest.mark.parametrize('values,expected', [
    (dict(kind='Mil', d=220, length=200), 59.681),                       # Test 1
    (dict(kind='Sac levha', b=1000, t=2, length=2000), 31.4),            # Test 2
    (dict(kind='Kare dolu çubuk', b=20, length=1000), 3.14),            # Test 3
    (dict(kind='Boru', d=60, t=3, length=1000), 4.217),                  # Test 4
])
def test_acceptance_reference_masses(values, expected):
    result = rules.calculate(count=1, **values)
    assert result.density == STEEL
    assert result.mass_kg == pytest.approx(expected, abs=5e-4)
    assert result.total_mass_kg == result.mass_kg


def test_tube_uses_inner_diameter_d_equals_D_minus_2t():
    result = rules.calculate(kind='Boru', d=60, t=3)
    assert result.area_mm2 == pytest.approx(math.pi * (60 ** 2 - 54 ** 2) / 4)
    assert any('d = D − 2t = 54' in note for note in result.notes)


# ---- 2. every section type against an independent hand formula ----------------------
HAND = {
    'Mil': (dict(d=50), math.pi * 625),
    'Kare dolu çubuk': (dict(b=40), 1600),
    'Lama / dikdörtgen çubuk': (dict(b=60, t=10), 600),
    'Altıköşe çubuk': (dict(s=30), math.sqrt(3) * 900 / 2),
    'Sac levha': (dict(b=1000, t=5), 5000),
    'Boru': (dict(d=60, t=3), math.pi * (3600 - 2916) / 4),
    'Kare kutu profil': (dict(b=100, t=5, corner='Keskin köşe'), 100 * 100 - 90 * 90),
    'Dikdörtgen kutu profil': (dict(b=120, h=80, t=4, corner='Keskin köşe'), 120 * 80 - 112 * 72),
    'Eşit kollu köşebent': (dict(b=50, t=5, r1=0), 5 * (50 + 50 - 5)),
    'Farklı kollu köşebent': (dict(b=50, h=80, t=6, r1=0), 6 * (50 + 80 - 6)),
    'U profil': (dict(h=100, b=50, tw=6, tf=8, r=0), 2 * 50 * 8 + (100 - 16) * 6),
    'Bükme U profil (sac)': (dict(h=100, b=50, t=3, r=3), 3 * (88 + 2 * 44) + math.pi / 2 * (36 - 9)),
    'T profil': (dict(b=60, h=60, tw=7, tf=7), 60 * 7 + 53 * 7),
    'I profil': (dict(h=200, b=100, tw=5.6, tf=8.5, r=0), 2 * 100 * 8.5 + (200 - 17) * 5.6),
}


def test_hand_table_covers_every_geometric_section_type():
    assert set(HAND) == set(sections.SECTION_TYPES)


@pytest.mark.parametrize('kind', sorted(HAND))
def test_each_section_matches_its_hand_area(kind):
    dims, area = HAND[kind]
    result = rules.calculate(kind=kind, length=1000, **dims)
    assert result.area_mm2 == pytest.approx(area)
    assert result.kg_per_m == pytest.approx(area * 1e-6 * STEEL)
    assert result.mass_kg == pytest.approx(result.kg_per_m)  # 1 m


def test_radius_terms_follow_en_formulas():
    # I/H: + (4 − π) r²; U: + (4 − π)/2 r²; angle: + (1 − π/4)(r1² − 2 r2²), r2 = r1/2.
    i = rules.calculate(kind='I profil', h=200, b=100, tw=5.6, tf=8.5, r=12)
    assert i.area_mm2 == pytest.approx(HAND['I profil'][1] + (4 - math.pi) * 144)
    u = rules.calculate(kind='U profil', h=100, b=50, tw=6, tf=8, r=8)
    assert u.area_mm2 == pytest.approx(HAND['U profil'][1] + (4 - math.pi) / 2 * 64)
    angle = rules.calculate(kind='Eşit kollu köşebent', b=120, t=8, r1=13)
    assert angle.area_mm2 == pytest.approx(8 * 232 + (1 - math.pi / 4) * (169 - 2 * 6.5 ** 2))
    assert angle.corner_radii == (13, 6.5) and not angle.approximate
    assert rules.calculate(kind='Eşit kollu köşebent', b=50, t=5).approximate   # r1 = 0: sharp model


# ---- 3. box sections ----------------------------------------------------------------
@pytest.mark.parametrize('b,h,t,radii', [(100, 100, 5, (10, 5)), (40, 40, 3, (6, 3)), (200, 100, 8, (20, 12)),
                                         (300, 300, 12.5, (37.5, 25))])
def test_cold_formed_box_uses_en_10219_calculation_radii(b, h, t, radii):
    result = rules.calculate(kind='Dikdörtgen kutu profil', b=b, h=h, t=t)
    outer, inner = radii
    assert result.corner_radii == pytest.approx(radii)
    assert result.area_mm2 == pytest.approx(2 * t * (b + h - 2 * t) - (4 - math.pi) * (outer ** 2 - inner ** 2))
    assert not result.approximate


def test_box_corner_modes_and_square_alias():
    square = rules.calculate(kind='Kare kutu profil', b=100, t=5)
    rectangle = rules.calculate(kind='Dikdörtgen kutu profil', b=100, h=100, t=5)
    assert square.area_mm2 == pytest.approx(rectangle.area_mm2) and square.kg_per_m == pytest.approx(14.41, abs=.01)
    manual = rules.calculate(kind='Kare kutu profil', b=100, t=5, corner='Elle yarıçap', ro=7.5, ri=5)
    assert manual.area_mm2 == pytest.approx(1900 - (4 - math.pi) * (7.5 ** 2 - 25))
    sharp = rules.calculate(kind='Kare kutu profil', b=100, t=5, corner='Keskin köşe')
    assert sharp.area_mm2 == 1900 and sharp.approximate


# ---- 4. verified standard catalogue ---------------------------------------------------
def test_shipped_catalogue_passes_its_own_area_and_mass_checks():
    assert catalog.validate() == []
    docs = catalog.sources()
    for family in catalog.families():
        for item in catalog.profiles(family):
            assert item.sources and all(docs[s]['url'].startswith('https://') for s in item.sources)


@pytest.mark.parametrize('kind,name,kg_m,area_cm2', [
    ('IPE', 'IPE 200', 22.4, 28.5), ('IPE', 'IPE A 200', 18.4, 23.5), ('IPE', 'IPE O 200', 25.1, 32.0),
    ('HEA', 'HEA 200', 42.3, 53.8), ('HEB', 'HEB 300', 117.0, 149.1),
    ('HEM', 'HEM 200', 103.0, 131.3), ('UPN (NPU)', 'UPN 200', 25.3, 32.2), ('UPE', 'UPE 200', 22.8, 29.0),
    ('Eşit kollu köşebent · EN 10056-1', 'L 150x150x12', 27.3, 34.8),
    ('Farklı kollu köşebent · EN 10056-1', 'L 200x100x10', 23.0, 29.2)])
def test_standard_profiles_use_manufacturer_kg_per_m(kind, name, kg_m, area_cm2):
    result = rules.calculate(kind=kind, profile=name, length=6000, count=2)
    assert result.method == rules.STANDARD_METHOD
    assert result.kg_per_m == kg_m and result.catalog_kg_m == kg_m
    assert result.area_mm2 == pytest.approx(area_cm2 * 100)
    assert result.mass_kg == pytest.approx(kg_m * 6) and result.total_mass_kg == pytest.approx(kg_m * 12)
    assert result.source and result.standard.startswith('EN')
    # The parallel-flange geometric model is reported separately, never substituted.
    assert result.geometric_area_mm2 > 0


def test_catalogue_kg_per_m_is_not_reused_for_another_density():
    steel = rules.calculate(kind='IPE', profile='IPE 200')
    aluminium = rules.calculate(kind='IPE', profile='IPE 200', material='Alüminyum')
    assert aluminium.kg_per_m == pytest.approx(steel.area_mm2 * 1e-6 * 2700)
    assert any('çelik (7850 kg/m³) içindir' in note for note in aluminium.notes)


def test_source_differences_between_manufacturers_are_kept_visible():
    result = rules.calculate(kind='IPE', profile='IPE 400')
    assert any('British Steel' in note for note in result.notes)


def test_families_without_verified_data_are_not_offered_as_standard():
    assert 'IPN' not in catalog.families() and 'HL' not in catalog.families()
    assert rules.normalise_kind('IPN') == 'I profil'


# ---- 5. units, count and density ----------------------------------------------------
def test_mm_cm_m_and_mass_units_describe_the_same_piece():
    results = [rules.calculate(b=100, t=5, length=1000, unit='mm'),
               rules.calculate(b=10, t=.5, length=100, unit='cm'),
               rules.calculate(b=.1, t=.005, length=1, unit='m')]
    for result in results:
        assert result.mass_kg == pytest.approx(3.925) and result.length_mm == pytest.approx(1000)
    assert rules.mass_in(3.925, 'g') == pytest.approx(3925) and rules.mass_in(3.925, 't') == pytest.approx(.003925)
    with pytest.raises(ValueError):
        rules.mass_in(1, 'lb')


def test_count_and_density_scale_linearly():
    one = rules.calculate(kind='Mil', d=40, length=500)
    ten = rules.calculate(kind='Mil', d=40, length=500, count=10)
    assert ten.total_mass_kg == pytest.approx(one.mass_kg * 10) and ten.mass_kg == one.mass_kg
    custom = rules.calculate(kind='Mil', d=40, length=500, material='Özel malzeme', density='3925',
                             material_name='Deneme')
    assert custom.mass_kg == pytest.approx(one.mass_kg / 2) and custom.material_label == 'Deneme'


def test_preset_densities_are_fixed_and_custom_density_is_range_checked():
    with pytest.raises(ValueError, match='Özel malzeme'):
        rules.calculate(material='Demir / Çelik', density=7000)
    for density in (0, -5, 50, 30000, 'abc', None):
        with pytest.raises(ValueError):
            rules.calculate(material='Özel malzeme', density=density)


# ---- 6. invalid, extreme and locale-formatted input -------------------------------------
@pytest.mark.parametrize('values', [
    {'kind': 'Bilinmeyen'}, {'material': 'Bilinmeyen'}, {'unit': 'inch'}, {'method': 'Bilinmeyen'},
    {'count': 1.5}, {'count': 0}, {'count': 1000001}, {'count': True}, {'length': 0}, {'length': -1},
    {'length': float('nan')}, {'b': -1}, {'b': 0}, {'t': None}, {'b': float('inf')},
    {'method': 'Katalog alanından'}, {'method': 'Katalog alanından', 'area_cm2': 0},
    {'kind': 'Boru', 'd': 10, 't': 5}, {'kind': 'Kare kutu profil', 'b': 10, 't': 5},
    {'kind': 'Kare kutu profil', 'b': 20, 't': 8},                         # EN radius larger than the side
    {'kind': 'Kare kutu profil', 'b': 50, 't': 3, 'corner': 'Elle yarıçap', 'ro': 4, 'ri': 6},
    {'kind': 'Farklı kollu köşebent', 'b': 10, 'h': 20, 't': 10},
    {'kind': 'Eşit kollu köşebent', 'b': 30, 't': 5, 'r1': 40},
    {'kind': 'T profil', 'b': 20, 'h': 10, 'tf': 10, 'tw': 5}, {'kind': 'T profil', 'b': 20, 'h': 30, 'tf': 5, 'tw': 20},
    {'kind': 'I profil', 'b': 20, 'h': 10, 'tf': 5, 'tw': 3}, {'kind': 'I profil', 'h': 100, 'b': 50, 'tw': 5, 'tf': 8, 'r': 30},
    {'kind': 'U profil', 'b': 10, 'h': 20, 'tf': 2, 'tw': 10}, {'kind': 'IPE', 'profile': 'IPE 999'},
    {'kind': 'Kare kutu profil', 'corner': 'Yuvarlak'}])
def test_invalid_input_never_returns_a_result(values):
    with pytest.raises(ValueError):
        rules.calculate(**values)


@pytest.mark.parametrize('values', [{'b': '1e308', 't': '1e308'}, {'kind': 'Kare dolu çubuk', 'b': '1e200'},
                                    {'method': 'Katalog alanından', 'area_cm2': '1e308'},
                                    {'unit': 'm', 'length': '1e308'}])
def test_overflow_is_a_validation_error(values):
    with pytest.raises(ValueError):
        rules.calculate(**values)


def test_very_small_values_stay_finite_and_unrounded():
    result = rules.calculate(kind='Mil', d='0,01', length='0,01')
    assert result.mass_kg == pytest.approx(math.pi / 4 * 1e-4 * 1e-2 * 1e-9 * STEEL)
    assert rules.fmt(result.mass_kg) != '0'


def test_decimal_comma_point_and_ambiguous_thousands():
    assert rules.calculate(b=' 100,5 ', t='2,5', length='1000,5', count='2,0').area_mm2 == pytest.approx(251.25)
    assert rules.calculate(b='100.5', t='2.5').area_mm2 == pytest.approx(251.25)
    assert rules.calculate(b='1.234,5', t=1).area_mm2 == pytest.approx(1234.5)
    for text in ('1.000', '12.500', '1,000.5', '1.2.3'):
        with pytest.raises(ValueError):
            rules.calculate(b=text)
    assert rules.fmt(12.500) == '12,5' and rules.fmt_fixed(1234.5, 2) == '1.234,50'


def test_only_active_fields_are_parsed():
    result = rules.calculate(kind='Mil', d=20, b='geçersiz', h=-1, t=float('nan'), tw=None, tf=False, s='sonsuz',
                             area_cm2='geçersiz')
    assert result.area_mm2 == pytest.approx(100 * math.pi) and result.dimensions_mm == {'d': 20}


def test_catalogue_area_method_ignores_geometry():
    result = rules.calculate(kind='I profil', method='Katalog alanından', area_cm2='12,34', length=2, unit='m',
                             b='hatalı', h=-1)
    assert result.area_mm2 == pytest.approx(1234) and result.dimensions_mm == {}
    assert result.mass_kg == pytest.approx(1234e-6 * 2 * STEEL)


def test_old_kind_names_still_calculate():
    for old, new in rules.KIND_ALIASES.items():
        assert rules.normalise_kind(old) == new
    assert rules.calculate(kind='Kare demir', b=40).kind == 'Kare dolu çubuk'
    assert rules.calculate(kind='Kutu profil', b=100, h=50, t=4).kind == 'Dikdörtgen kutu profil'


# ---- 7. materials -----------------------------------------------------------------------
def test_every_selectable_material_has_density_note_and_source():
    names = [name for members in rules.MATERIAL_GROUPS.values() for name in members]
    assert len(names) == len(set(names))
    for name in names:
        assert math.isfinite(rules.MATERIALS[name]) and rules.MATERIAL_NOTES[name]
        assert rules.MATERIAL_SOURCES[name].startswith('https://')


@pytest.mark.parametrize('name,density', [('S235JR', 7850), ('C45', 7850), ('42CrMo4', 7850), ('304L', 8000),
                                          ('430', 7750), ('1050A', 2710), ('6063', 2700), ('6082', 2700),
                                          ('7075', 2810), ('PA66', 1150), ('PE-HD', 950), ('PTFE', 2070),
                                          ('Nikel', 8908), ('Magnezyum', 1738), ('Tungsten', 19250)])
def test_requested_material_densities(name, density):
    assert rules.MATERIALS[name] == density
    assert rules.calculate(material=name, b=1000, t=10, length=1000).mass_kg == pytest.approx(density / 100)
