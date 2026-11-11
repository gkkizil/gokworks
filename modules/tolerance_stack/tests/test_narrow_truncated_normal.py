"""Independent bounded-variance and high-precision conditional-normal oracles."""
from decimal import Decimal as D, localcontext
import math

import pytest

from modules.tolerance_stack.calculator import calculate, moments
from modules.tolerance_stack.models import Project, Term, manual_dimension


def reference(sigma,mean=0):
    # Integrate x^n exp(-x²/2σ²) on [-1/2,1/2] term by term in Decimal,
    # independently of either floating CDFs or the production quadrature.
    with localcontext() as ctx:
        ctx.prec=60
        center=D(str(mean)); a,b=-D('.5')-center,D('.5')-center
        factor=D(1); integrals=[D(0),D(0),D(0)]
        for k in range(30):
            for n in range(3):
                power=2*k+n+1
                integrals[n]+=factor*(b**power-a**power)/D(power)
            factor*= -D(1)/(2*D(str(sigma))**2*D(k+1))
        zeroth,first,second=integrals
        return float(center+first/zeroth),float(second/zeroth-(first/zeroth)**2)


@pytest.mark.parametrize('sigma',[5,10,100,1e4,1e6,1e10,1e12])
def test_narrow_band_variance_matches_high_precision_integral(sigma):
    mean,variance=moments(('normal',-.5,.5,0.,sigma,0.),True)
    assert mean==pytest.approx(0,abs=1e-15)
    assert variance==pytest.approx(reference(sigma)[1],rel=2e-11)
    assert 0<variance<=.25  # Popoviciu bound for every width-one distribution.


@pytest.mark.parametrize('mean',[-.5,-.2,.5])
def test_off_center_large_sigma_tends_to_uniform_not_a_zero_or_huge_variance(mean):
    measured,variance=moments(('normal',-.5,.5,mean,1e10,0.),True)
    assert measured==pytest.approx(0,abs=1e-12)
    assert variance==pytest.approx(1/12,rel=1e-12)


@pytest.mark.parametrize('mean',[-.5,-.2,.5])
@pytest.mark.parametrize('sigma',[10,50])
def test_skewed_narrow_conditional_normal_matches_decimal_integrals(mean,sigma):
    observed=moments(('normal',-.5,.5,mean,sigma,0.),True)
    expected=reference(sigma,mean)
    assert observed==pytest.approx(expected,rel=2e-11,abs=1e-15)


def test_numerical_paths_meet_continuously_at_the_narrow_band_threshold():
    for sigma in (math.nextafter(10.,0.),10.,math.nextafter(10.,math.inf)):
        assert moments(('normal',-.5,.5,0.,sigma,0.),True)[1]==pytest.approx(reference(sigma)[1],rel=2e-10)


@pytest.mark.parametrize('sigma',[1e6,1e12])
def test_full_rss_and_simulation_remain_inside_the_real_tolerance_band(sigma):
    dimension=manual_dimension('Bounded input',0,'-.5','.5')
    project=Project(dimensions=[dimension],end='P1',method='all',samples=12000,
                    acceptance_min=D('-.5'),acceptance_max=D('.5'),
                    terms=[Term(dimension.id,start='P0',end='P1',datum='A',sigma=D(str(sigma)))])
    project.confirm();result=calculate(project);mc=result.monte_carlo
    assert result.sigma==pytest.approx(math.sqrt(1/12),rel=1e-10)
    assert mc['sigma']==pytest.approx(result.sigma,rel=.025)
    assert -.5<=mc['sample_minimum']<=mc['sample_maximum']<=.5
    assert mc['rejected']==0 and mc['acceptance_rate']==1
    assert calculate(project).monte_carlo==mc
