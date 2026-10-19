"""Signed interval arithmetic and explicitly assumed independent moments."""

from datetime import datetime, timezone
from decimal import Decimal
import math
from statistics import NormalDist

from .chain import validate
from .models import Contribution, Result


class Cancelled(RuntimeError):
    pass


def check_cancel(stop=None):
    if stop is not None and stop.is_set():
        raise Cancelled('İşlem durduruldu; sonuç yayımlanmadı.')


def distribution_parameters(dimension, term, project):
    low, high = float(dimension.minimum), float(dimension.maximum)
    if low == high and dimension.minimum != dimension.maximum:
        raise ValueError(f'{dimension.name}: bu büyüklükteki çok dar bant istatistiksel hassasiyeti aşıyor; Worst-Case kullanın.')
    middle, half = (low+high)/2, (high-low)/2
    kind = project.distribution if term.distribution == 'inherit' else term.distribution
    mean = middle if term.mean is None else float(term.mean)
    sigma = half/float(project.input_sigma) if term.sigma is None else float(term.sigma)
    mode = middle if term.mode is None else float(term.mode)
    if not all(math.isfinite(value) for value in (low, high, mean, sigma, mode)):
        raise ValueError(f'{dimension.name}: dağılım parametreleri sonlu olmalı.')
    if kind == 'triangular' and not low <= mode <= high:
        raise ValueError(f'{dimension.name}: üçgensel dağılım tepesi tolerans bandı içinde olmalı.')
    if kind == 'normal' and (sigma < 0 or project.truncate_normal and not low <= mean <= high):
        raise ValueError(f'{dimension.name}: normal dağılım merkezi/band sınırları veya σ geçersiz.')
    if low == high and (kind != 'normal' or project.truncate_normal):
        mean, sigma, mode = low, 0., low
    if kind == 'uniform':
        return kind, low, high, middle, (high-low)/math.sqrt(12), mode
    if kind == 'triangular':
        mean = (low+high+mode)/3
        width, offset = high-low, mode-low
        sigma = math.sqrt(max(0., (width*width+offset*offset-width*offset)/18))
    return kind, low, high, mean, sigma, mode


def moments(parameters, truncated):
    kind, low, high, mean, sigma, mode = parameters
    if kind != 'normal' or not truncated or sigma == 0:
        return mean, sigma*sigma
    normal = NormalDist()
    a, b = (low-mean)/sigma, (high-mean)/sigma
    mass = normal.cdf(b)-normal.cdf(a)
    if mass <= 1e-14:
        raise ValueError('Kesilmiş normal dağılım aralığı sayısal olarak çözülemiyor; merkez/σ değerlerini değiştirin.')
    pa, pb = math.exp(-a*a/2)/math.sqrt(2*math.pi), math.exp(-b*b/2)/math.sqrt(2*math.pi)
    shift = (pa-pb)/mass
    return mean+sigma*shift, max(0., sigma*sigma*(1+(a*pa-b*pb)/mass-shift*shift))


def within(low, high, project):
    if project.acceptance_min is None and project.acceptance_max is None:
        return None
    return ((project.acceptance_min is None or low >= project.acceptance_min) and
            (project.acceptance_max is None or high <= project.acceptance_max))


def calculate(project, *, stop=None, progress=None):
    dimensions = validate(project)
    nominal = low = high = Decimal(0)
    means, variances, widths, parameters = [], [], [], []
    for term in project.terms:
        check_cancel(stop)
        dimension = dimensions[term.dimension_id]
        factor = term.factor*term.direction
        a, b = factor*dimension.minimum, factor*dimension.maximum
        nominal += factor*dimension.nominal
        low += min(a, b)
        high += max(a, b)
        widths.append(abs(b-a))
        if project.method != 'worst_case':
            p = distribution_parameters(dimension, term, project)
            mean, variance = moments(p, project.truncate_normal)
            parameters.append(p)
            means.append(float(factor)*mean)
            variances.append(float(factor)**2*variance)
    total_width, total_variance = sum(widths), math.fsum(variances)
    mean, sigma = (math.fsum(means), math.sqrt(total_variance)) if parameters else (None, None)
    rss_low = None if sigma is None else mean-float(project.output_sigma)*sigma
    rss_high = None if sigma is None else mean+float(project.output_sigma)*sigma
    contributions = tuple(Contribution(term.dimension_id, dimensions[term.dimension_id].name,
        float(widths[i]/total_width*100) if total_width else 0.,
        (variances[i]/total_variance*100 if total_variance else 0.) if parameters else None)
        for i, term in enumerate(project.terms))
    assumptions = ['1D doğrusal zincir; yön/konum/datum ilişkisi kullanıcı tarafından doğrulandı.',
                   'Worst-Case gerçek alt/üst limitleri kullanır; üretim olasılığı belirtmez.']
    manual_count=sum(dimensions[t.dimension_id].provenance=='manual_override' for t in project.terms)
    if manual_count:assumptions.append(f'{manual_count} kaynak ölçü manuel analiz verisiyle tamamlandı; bu değerler okunmuş CAD toleransı olarak sunulmaz.')
    if parameters:
        assumptions += ['Girdiler bağımsızdır; korelasyon modellenmedi.',
            f'Normal girdide aksi belirtilmedikçe merkez bant ortası, σ = yarı genişlik / {project.input_sigma}.',
            'Normal dağılım ' + ('tolerans bandında kesilir; RSS gerçek kesilmiş dağılım momentlerini kullanır.' if project.truncate_normal else 'kesilmez; tolerans dışı örnekler mümkündür.'),
            f'RSS aralığı ortalama ±{project.output_sigma}σ; normallik ve uygunluk garantisi değildir.',
            'Cp/Cpk ve PPM varsayımsal/simülasyon temellidir; ölçülmüş proses kabiliyeti değildir.']
    if project.offline_snapshot and project.sources:
        assumptions.append('ÇEVRİMDIŞI CAD ANLIK GÖRÜNTÜSÜ: açık SolidWorks oturumundaki değişiklikler doğrulanmadı.')
    kind = ('Tam temas' if low == high == 0 else 'Pozitif boşluk' if low > 0 else
            'Sınırda temas / boşluk' if low == 0 else 'Negatif boşluk / sıkılık' if high < 0 else
            'Sınırda temas / sıkılık' if high == 0 else 'Ara geçme')
    mc = None
    if project.method == 'all':
        from .monte_carlo import simulate
        mc = simulate(project, parameters=parameters, stop=stop, progress=progress)
    check_cancel(stop)
    return Result(project.fingerprint(), datetime.now(timezone.utc).isoformat(), nominal, low, high,
                  mean, sigma, rss_low, rss_high, within(low, high, project),
                  None if rss_low is None else within(Decimal(str(rss_low)), Decimal(str(rss_high)), project),
                  kind, contributions, tuple(assumptions), mc)
