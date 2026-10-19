"""Seeded, cancellable independent simulation; no clipping of normal draws."""

import math
import random
from statistics import NormalDist, fmean, stdev
from .calculator import check_cancel, distribution_parameters
from .chain import validate


def quantile(values, p):
    position = (len(values)-1)*p
    index = int(position)
    fraction = position-index
    return values[index]*(1-fraction)+values[min(index+1, len(values)-1)]*fraction


def simulate(project, *, parameters=None, stop=None, progress=None):
    dimensions = validate(project)
    if project.samples * len(project.terms) > 20000000:
        raise ValueError('Simülasyon sınırı: örnek sayısı × zincir adedi en çok 20.000.000 olmalı.')
    if parameters is None:
        parameters = [distribution_parameters(dimensions[t.dimension_id], t, project) for t in project.terms]
    rng, normal = random.Random(project.seed), NormalDist()
    samplers = []
    for kind, low, high, mean, sigma, mode in parameters:
        if sigma == 0:
            samplers.append(lambda mean=mean: mean)
        elif kind == 'uniform':
            samplers.append(lambda a=low, b=high: rng.uniform(a,b))
        elif kind == 'triangular':
            samplers.append(lambda a=low, b=high, c=mode: rng.triangular(a,b,c))
        elif not project.truncate_normal:
            samplers.append(lambda m=mean, s=sigma: rng.gauss(m,s))
        else:
            a, b = normal.cdf((low-mean)/sigma), normal.cdf((high-mean)/sigma)
            if b-a <= 1e-14:
                raise ValueError('Kesilmiş normal dağılım aralığı çözülemiyor.')
            def sample(a=a, b=b, m=mean, s=sigma):
                p = max(math.nextafter(0.,1.), min(math.nextafter(1.,0.), a+(b-a)*rng.random()))
                return m+s*normal.inv_cdf(p)
            samplers.append(sample)
    factors = [float(t.factor)*t.direction for t in project.terms]
    values = []
    for index in range(project.samples):
        if index % 1000 == 0:
            check_cancel(stop)
            if progress:
                progress(index, project.samples)
        values.append(math.fsum(factor*sample() for factor, sample in zip(factors, samplers)))
    check_cancel(stop)
    mean, sigma = fmean(values), stdev(values)
    low, high = project.acceptance_min, project.acceptance_max
    known = low is not None or high is not None
    outside = sum((low is not None and x < float(low)) or (high is not None and x > float(high)) for x in values) if known else None
    rate = outside/len(values) if known else None
    cp = float(high-low)/(6*sigma) if low is not None and high is not None and sigma > 0 else None
    margins = [] if sigma == 0 else ([float(high)-mean] if high is not None else []) + ([mean-float(low)] if low is not None else [])
    cpk = min(margins)/(3*sigma) if margins else None
    ordered = sorted(values)
    bins = min(60, max(10, round(math.sqrt(len(values)))))
    minimum, maximum = ordered[0], ordered[-1]
    width = (maximum-minimum)/bins
    histogram = [0]*bins
    for x in values:
        histogram[min(bins-1, int((x-minimum)/width)) if width else 0] += 1
    interval = None
    if known:
        n, z = len(values), 1.959963984540054
        center = (rate+z*z/(2*n))/(1+z*z/n)
        half = z*math.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/(1+z*z/n)
        interval = [max(0., center-half)*1e6, min(1., center+half)*1e6]
    if progress:
        progress(project.samples, project.samples)
    return dict(samples=len(values), seed=project.seed, mean=mean, sigma=sigma, sample_minimum=minimum,
        sample_maximum=maximum, percentiles={str(p):quantile(ordered,p/100) for p in (.135,1,5,50,95,99,99.865)},
        acceptance_rate=None if rate is None else 1-rate, rejected=outside, ppm=None if rate is None else rate*1e6,
        ppm_confidence_95=interval, cp=cp, cpk=cpk, capability_basis='Varsayımsal / simülasyon temelli; ölçülmüş proses kabiliyeti değildir.',
        histogram=dict(minimum=minimum, maximum=maximum, counts=histogram))
