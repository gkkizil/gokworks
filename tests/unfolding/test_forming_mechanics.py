"""Independent mechanics references. Material numbers here are synthetic test inputs."""
import math
import pytest

from core.unfolding.forming.mechanics import bend_values,normalize_options,springback,section_moment,compare_reference
from core.unfolding.forming.profiles import develop_bends


def spec(**kwargs):
    return dict(k_factor=.4,material=dict(grade='S235',standard='TEST ONLY',source='Synthetic test fixture; not a material certificate',
                                       young_modulus_mpa=210000.,yield_strength_mpa=235.,hardening_modulus_mpa=0.),
                tool=dict(id='TEST-V16',source='Synthetic test fixture'),**kwargs)


def row(angle=90.,radius=2.,**kwargs):
    return dict(material_grade='S235',process='air_bending',tool_id='TEST-V16',grain_direction='unspecified',
                source='Synthetic measured coupon for tests only',thickness_mm=2.,inside_radius_mm=radius,angle_deg=angle,**kwargs)


@pytest.mark.parametrize('grade,t,r,E,Y,H', [('DC01',1.,1.,210000.,200.,0.),('S235',2.,2.,210000.,235.,0.),
                                          ('AISI 304',3.,3.,193000.,220.,1000.)])
def test_three_material_scenarios_with_explicit_not_default_properties(grade,t,r,E,Y,H):
    o=spec(springback='analytic');o['material'].update(grade=grade,young_modulus_mpa=E,yield_strength_mpa=Y,hardening_modulus_mpa=H)
    b=bend_values(90.,r,t,o)
    assert b.allowance_mm==pytest.approx(math.pi/2*(r+.4*t))
    assert b.outside_setback_mm==pytest.approx(r+t)
    assert b.deduction_mm==pytest.approx(2*(r+t)-math.pi/2*(r+.4*t))
    s=springback(90.,r,t,o)
    assert s['status']=='ANALYTICAL_ESTIMATE'
    assert 90<s['loaded_turn_deg']<180
    assert s['loaded_inside_radius_mm']<r
    assert s['estimated_final_turn_deg']==pytest.approx(90.,abs=1e-10)
    assert s['production_process_verified'] is False


@pytest.mark.parametrize('radius', [.1,1.,2.,5.,10.,30.])
@pytest.mark.parametrize('k', [.2,.33,.4,.5])
def test_rt_and_k_sweep_against_independent_formulas(radius,k):
    t=2.;b=bend_values(-60.,radius,t,dict(k_factor=k))
    assert b.allowance_mm==pytest.approx(math.pi/3*(radius+k*t))
    assert b.deduction_mm==pytest.approx(2*(radius+t)/math.sqrt(3)-b.allowance_mm)
    assert b.inner_engineering_strain==-k*t/(radius+k*t)
    assert b.outer_engineering_strain==(1-k)*t/(radius+k*t)
    assert b.thickness_after_forming_mm is None


def test_elastic_plastic_moment_against_independent_midpoint_stress_integration():
    t,E,Y,H,k=2.,210000.,235.,1800.,1/6
    steps=20000;dy=t/2/steps
    moment=0.
    for i in range(steps):
        y=(i+.5)*dy;strain=k*y
        stress=E*strain if strain<=Y/E else Y+H*(strain-Y/E)
        moment+=2*stress*y*dy
    assert section_moment(k,t,E,Y,H)==pytest.approx(moment,rel=1e-8)
    residual=k-moment/(E*t**3/12)
    final_radius=1/residual-t/2
    o=spec(springback='analytic');o['material']['hardening_modulus_mpa']=H
    result=springback(90.,final_radius,t,o)
    assert result['loaded_inside_radius_mm']==pytest.approx(5.,abs=1e-7)
    assert result['loaded_turn_deg']==pytest.approx(90*k/residual,abs=1e-7)


def test_fully_elastic_section_unloads_to_zero_curvature():
    E,Y,t=210000.,235.,2.;k=Y/(E*t)
    assert section_moment(k,t,E,Y)==pytest.approx(E*t**3/12*k)


def test_springback_changes_with_rt_and_material_instead_of_constant_degrees():
    o=spec(springback='analytic')
    results=[springback(90.,r,2.,o)['overbend_deg'] for r in (1.,3.,10.)]
    assert results[0]<results[1]<results[2]
    stronger=spec(springback='analytic');stronger['material']['yield_strength_mpa']=500.
    assert springback(90.,3.,2.,stronger)['overbend_deg']>results[1]
    assert springback(-90.,3.,2.,o)['loaded_turn_deg']==-springback(90.,3.,2.,o)['loaded_turn_deg']


@pytest.mark.parametrize('process',['bottoming','coining','segmented_assembly'])
def test_pure_bending_is_not_silently_applied_to_other_processes(process):
    assert springback(90.,2.,2.,spec(process=process,springback='analytic'))['status']=='NOT_EVALUATED'


def test_ba_bd_and_coupon_calibration_share_reference_geometry():
    allowance=4.39822971502571;deduction=3.60177028497429
    samples=[('ba_table',row(allowance_mm=allowance)),('bd_table',row(deduction_mm=deduction)),
             ('calibrated',row(outside_first_mm=50.,outside_second_mm=50.,measured_flat_mm=96.39822971502571))]
    for method,sample in samples:
        b=bend_values(90.,2.,2.,spec(method=method,table=[sample]))
        assert b.k_factor==pytest.approx(.4,abs=1e-12)
        assert b.allowance_mm==pytest.approx(allowance,abs=1e-12)
        assert b.deduction_mm==pytest.approx(deduction,abs=1e-12)


def test_table_included_angles_are_converted_once():
    sample=row(angle=120.,allowance_mm=math.pi/3*2.8,angle_kind='included')
    o=normalize_options(spec(method='ba_table',table=[sample]))
    assert o['table'][0]['angle_deg']==60.
    assert bend_values(60.,2.,2.,o).k_factor==pytest.approx(.4)


def test_bilinear_table_interpolation_is_bounded_and_requires_all_corners():
    table=[row(angle=a,radius=r,allowance_mm=math.radians(a)*(r+.8)) for a in (60.,120.) for r in (1.,3.)]
    o=spec(method='ba_table',table=table,table_interpolation='bilinear')
    assert bend_values(90.,2.,2.,o).allowance_mm==pytest.approx(4.39822971502571)
    with pytest.raises(ValueError,match='ekstrapolasyon'):bend_values(130.,2.,2.,o)
    with pytest.raises(ValueError,match='hücresi'):bend_values(90.,2.,2.,dict(o,table=table[:-1]))
    with pytest.raises(ValueError):bend_values(90.,2.,3.,o)
    with pytest.raises(ValueError):bend_values(90.,2.,2.,dict(o,grain_direction='along'))


def test_empirical_springback_interpolation_is_scoped_and_not_extrapolated():
    samples=[row(angle=60.,loaded_angle_deg=61.),row(angle=120.,loaded_angle_deg=123.)]
    o=spec(springback='calibrated',springback_samples=samples)
    result=springback(90.,2.,2.,o)
    assert result['status']=='CALIBRATED_ESTIMATE' and result['loaded_turn_deg']==92.
    assert springback(130.,2.,2.,o)['status']=='NOT_EVALUATED'
    assert springback(90.,3.,2.,o)['status']=='NOT_EVALUATED'
    assert springback(90.,2.,2.,dict(o,grain_direction='across'))['status']=='NOT_EVALUATED'


def test_multi_bend_reference_and_dimension_semantics():
    straight,bends,zones,total=develop_bends((20.,50.,20.),(90.,-90.),(2.,2.),2.,dict(k_factor=.4),dimension_reference='outside')
    assert straight==pytest.approx((16.,42.,16.))
    assert total==pytest.approx(82.79645943005141)
    assert tuple(z['line_at_mm'] for z in zones)==pytest.approx((18.199114857512853,64.59734457253856))
    for ref,expected in [('inside',80.39822971502571),('tangent',84.39822971502571)]:
        assert develop_bends((30.,50.),(90.,),(2.,),2.,dict(k_factor=.4),dimension_reference=ref)[3]==pytest.approx(expected)
    with pytest.raises(ValueError):develop_bends((2.,50.),(90.,),(2.,),2.,dict(k_factor=.4),dimension_reference='outside')


@pytest.mark.parametrize('o',[{},dict(k_factor=True),dict(k_factor=-.1),dict(k_factor=1.1),dict(k_factor=float('nan')),
                            dict(method='material_k',k_factor=.4),dict(k_factor=.4,tool={'die_opening_mm':0.}),
                            dict(k_factor=.4,unexpected=1)])
def test_invalid_or_missing_production_input_is_not_guessed(o):
    with pytest.raises(ValueError):bend_values(90.,2.,2.,o)


@pytest.mark.parametrize('angle',[0.,180.,float('inf'),True,'90'])
def test_invalid_turns(angle):
    with pytest.raises(ValueError):bend_values(angle,2.,2.,dict(k_factor=.4))


def test_missing_properties_do_not_create_springback_numbers():
    r=springback(90.,2.,2.,dict(k_factor=.4,springback='analytic',material={'grade':'S235'}))
    assert r['status']=='NOT_EVALUATED' and r['overbend_deg'] is None


def test_switching_methods_preserves_inactive_measurements_without_using_wrong_payload():
    o=spec(table=[row(allowance_mm=4.39822971502571)])
    assert bend_values(90.,2.,2.,o).k_factor==.4
    with pytest.raises(ValueError):bend_values(90.,2.,2.,dict(o,method='bd_table'))


@pytest.mark.parametrize('value',[False,None,[],1])
def test_profile_options_must_be_an_object(value):
    with pytest.raises(ValueError):normalize_options(value)


def test_closed_roll_curvature_does_not_have_an_artificial_180_degree_command_limit():
    o=spec(process='roll_bending',springback='analytic')
    assert springback(90.,10000.,2.,o)['status']=='NOT_EVALUATED'
    radius=springback(90.,10000.,2.,o,radius_only=True)
    assert radius['status']=='ANALYTICAL_ESTIMATE' and 0<radius['loaded_inside_radius_mm']<10000.


def test_reference_measurements_report_absolute_relative_and_zero_reference():
    r=compare_reference({'width':100.,'origin':0.},{'width':100.2,'origin':.01},source='Synthetic reference',
                        absolute_tolerance_mm=.3,relative_tolerance_percent=.3)
    assert r['dimensions_match'] is True
    assert r['points'][0]['percent_difference']==pytest.approx(.2)
    assert r['production_equivalence_verified'] is False
