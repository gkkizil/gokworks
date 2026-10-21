from dataclasses import replace
from decimal import Decimal as D
import math
import threading

import pytest

from modules.tolerance_stack.models import Project, Term, manual_dimension, iso_dimension, length
from modules.tolerance_stack.calculator import calculate, Cancelled


def example(**changes):
    dims = [manual_dimension('A',50,'-.10','.10'), manual_dimension('B',20,'-.05','.05'),
            manual_dimension('C','29.80','-.03','.03')]
    p = Project(dimensions=dims, end='P3', acceptance_max=D('.40'), method='rss',
                truncate_normal=False, **changes)
    p.terms = [Term(d.id, 1 if i == 0 else -1, f'P{i}', f'P{i+1}', datum='A') for i,d in enumerate(dims)]
    p.confirm()
    return p


def test_requested_signed_worst_case_and_independent_rss():
    p = example()
    r = calculate(p)
    assert (r.nominal,r.minimum,r.maximum) == (D('.20'),D('.02'),D('.38'))
    expected = math.sqrt(.10**2+.05**2+.03**2)
    assert r.mean == pytest.approx(.2)
    assert r.rss_minimum == pytest.approx(.2-expected)
    assert r.rss_maximum == pytest.approx(.2+expected)
    assert r.worst_case_pass is True
    assert sum(c.variance_percent for c in r.contributions) == pytest.approx(100)
    assert r.contributions[0].variance_percent == pytest.approx(100*.01/.0134)


def test_asymmetric_shift_keeps_nominal_separate_and_negative_sign_flips_limits():
    p = example()
    p.dimensions[0] = replace(p.dimensions[0],lower=D('-.10'),upper=D('.05'))
    p.confirm()
    r = calculate(p)
    assert r.nominal == D('.20') and r.mean == pytest.approx(.175)
    assert (r.minimum,r.maximum) == (D('.02'),D('.33'))
    p.terms[0] = replace(p.terms[0],direction=-1)
    p.confirm()
    r = calculate(p)
    assert (r.minimum,r.maximum) == (D('-99.93'),D('-99.62'))


@pytest.mark.parametrize('unit,amount', [('mm','25.4'),('cm','2.54'),('m','.0254'),('in','1'),('µm','25400')])
def test_exact_unit_conversion(unit,amount):
    assert length(amount,unit) == D('25.4')


@pytest.mark.parametrize('unit', ['rad','deg','ft','kg'])
def test_angles_or_unsupported_units_are_not_lengths(unit):
    with pytest.raises(ValueError): length(1,unit)


@pytest.mark.parametrize('kind,low,high', [('Pozitif boşluk','.1','.2'), ('Tam temas','0','0'),
    ('Negatif boşluk / sıkılık','-.2','-.1'),('Ara geçme','-.1','.1')])
def test_clearance_contact_interference_and_transition(kind,low,high):
    p = Project(dimensions=[manual_dimension('Gap',0,low,high)],end='P1',method='worst_case')
    p.terms=[Term(p.dimensions[0].id,start='P0',end='P1',datum='A')]
    p.confirm()
    assert calculate(p).kind == kind


@pytest.mark.parametrize('change', ['missing','duplicate','direction','datum','axis','discontinuous','missing_dimension','angle','basic','diameter','unknown_unit'])
def test_incomplete_or_inconsistent_chain_is_blocked(change):
    p=example()
    if change=='missing': p.dimensions[0]=replace(p.dimensions[0],lower=None)
    elif change=='duplicate': p.terms[1]=replace(p.terms[1],dimension_id=p.terms[0].dimension_id)
    elif change=='direction': p.terms[0]=replace(p.terms[0],direction=0)
    elif change=='datum': p.terms[0]=replace(p.terms[0],datum='B')
    elif change=='axis': p.terms[0]=replace(p.terms[0],axis='Y')
    elif change=='discontinuous': p.terms[0]=replace(p.terms[0],end='Other')
    elif change=='missing_dimension': p.dimensions.pop(0)
    elif change=='unknown_unit': p.dimensions[0]=replace(p.dimensions[0],display_unit='unknown')
    else: p.dimensions[0]=replace(p.dimensions[0],kind=change)
    with pytest.raises(ValueError): p.confirm()


def test_edit_requires_new_confirmation_and_physical_duplicates_from_other_views_block():
    p=example()
    p.dimensions[0]=replace(p.dimensions[0],nominal=D(51))
    with pytest.raises(ValueError,match='doğrulayın'): calculate(p)
    p.dimensions[0]=replace(p.dimensions[0],physical_id='model-dim')
    p.dimensions[1]=replace(p.dimensions[1],physical_id='model-dim')
    with pytest.raises(ValueError,match='iki kez'): p.confirm()


@pytest.mark.parametrize('nominal,hole,shaft',[(50,'H7','h6'),(38,'H7','k6'),(25,'H7','p6')])
def test_iso_reuses_verified_limits_and_requires_functional_diameter_relation(nominal,hole,shaft):
    from modules.iso_fits.rules import calculate as fit
    a,b=iso_dimension('Delik',nominal,hole,'hole'),iso_dimension('Mil',nominal,shaft,'shaft')
    p=Project(dimensions=[a,b],end='P2',method='worst_case',terms=[
        Term(a.id,1,'P0','P1',datum='A',relation='Çapsal boşluk D-d'),
        Term(b.id,-1,'P1','P2',datum='A',relation='Çapsal boşluk D-d')])
    p.confirm();r=calculate(p);reference=fit(nominal,hole,shaft)
    assert r.minimum==D(reference.minimum_clearance_nm)/1000000
    assert r.maximum==D(reference.maximum_clearance_nm)/1000000
    p.terms=[replace(t,factor=D('.5'),relation='Radyal boşluk (D-d)/2') for t in p.terms]
    p.confirm();assert calculate(p).minimum==r.minimum/2


@pytest.mark.parametrize('distribution',['normal','uniform','triangular'])
def test_seeded_simulation_matches_rss_moments_and_bounds(distribution):
    p=example();p.method='all';p.distribution=distribution;p.samples=15000;p.confirm()
    a=calculate(p);b=calculate(p)
    assert a.monte_carlo==b.monte_carlo
    mc=a.monte_carlo
    assert mc['mean']==pytest.approx(a.mean,abs=.002)
    assert mc['sigma']==pytest.approx(a.sigma,rel=.03)
    assert mc['percentiles']['5']<mc['percentiles']['95']
    assert sum(mc['histogram']['counts'])==p.samples
    assert mc['ppm_confidence_95'][1]>mc['ppm']
    if distribution!='normal':
        assert mc['sample_minimum']>=float(a.minimum)
        assert mc['sample_maximum']<=float(a.maximum)


def test_truncated_normal_moments_and_samples_are_not_clipped():
    p=example();p.method='all';p.input_sigma=D(1);p.truncate_normal=True;p.samples=12000;p.confirm()
    r=calculate(p);mc=r.monte_carlo
    assert mc['sigma']==pytest.approx(r.sigma,rel=.04)
    assert float(r.minimum)<mc['sample_minimum']<mc['sample_maximum']<float(r.maximum)
    assert mc['sigma']<math.sqrt(.1**2+.05**2+.03**2)
    p.truncate_normal=False;p.confirm();unbounded=calculate(p).monte_carlo
    assert unbounded['sample_minimum']<float(r.minimum) or unbounded['sample_maximum']>float(r.maximum)


def test_correlated_statistics_blocked_but_worst_case_remains_available():
    p=example();p.independent=False
    with pytest.raises(ValueError,match='Korelasyon'): p.confirm()
    p.method='worst_case';p.confirm();assert calculate(p).sigma is None


def test_no_acceptance_means_no_yield_or_capability_and_cancel_does_not_publish():
    p=example();p.method='all';p.samples=1000;p.acceptance_min=p.acceptance_max=None;p.confirm()
    r=calculate(p)
    assert r.worst_case_pass is None and r.monte_carlo['ppm'] is None and r.monte_carlo['cpk'] is None
    stop=threading.Event();stop.set()
    with pytest.raises(Cancelled): calculate(p,stop=stop)


def test_explicit_cad_alignment_is_auditable_and_does_not_replace_other_engineering_checks():
    from modules.tolerance_stack.chain import ChainIssue
    p=example();p.dimensions[0]=replace(p.dimensions[0],source='drawing.SLDDRW')
    with pytest.raises(ChainIssue) as issue:p.confirm()
    assert issue.value.target=='confirm' and issue.value.term_index==0
    p.terms[0]=replace(p.terms[0],alignment_confirmed=True);p.confirm()
    assert calculate(p).minimum==D('.02')
    p.dimensions[0]=replace(p.dimensions[0],upper=None)
    with pytest.raises(ChainIssue) as issue:p.confirm()
    assert issue.value.target=='dimension' and issue.value.dimension_id==p.dimensions[0].id
    p.dimensions[0]=replace(p.dimensions[0],upper=D('.1'),kind='diameter')
    with pytest.raises(ChainIssue,match='çap veya radyüs'):p.confirm()
    p.dimensions[0]=replace(p.dimensions[0],kind='linear')
    p.terms[0]=replace(p.terms[0],factor=D('.5'))
    with pytest.raises(ChainIssue,match='katsayı'):p.confirm()


def test_alignment_confirmation_must_be_a_boolean():
    p=example();p.terms[0]=replace(p.terms[0],alignment_confirmed='yes')
    with pytest.raises(ValueError,match='doğrultusu kontrolü'):p.confirm()
