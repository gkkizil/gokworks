"""Tosyalı actual pulley pairs + explicitly identified Optibelt SK reference.

This reference assembly is distinct from generic nominal sizing and from a
manufacturer-approved product assembly. All selected grooves get matched belts.
"""
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import math

from .calculation import calculate
from .catalog.tosyali_v import catalog, PROFILES, MAX_SPEED_M_S, TosyaliVPulley
from .design_search import outside, minimum_center_for_limits, operating_limit_failure
from .engineering.belt_length import solve_center_distance
from .engineering.optibelt_sk import rate, reference_data, SKRating
from .models import BeltDriveSpecification, BeltSpecification, PulleySpecification, LoadSpecification, CenterSpecification, Issue
from .nominal_design import NominalCandidate, NominalSizingReport, _bounds_and_target
from .preferred_sizes import REFERENCE_MIN_DATUM_MM
from .validation import CalculationCancelled


@dataclass(frozen=True, slots=True)
class TosyaliCandidate(NominalCandidate):
    driver_pulley: TosyaliVPulley | None = None
    driven_pulley: TosyaliVPulley | None = None
    rating: SKRating | None = None
    belt_count: int = 0


def chart_sections(power_kw, small_rpm):
    """Approximate log-chart regions (Tosyalı printed p44), advice only.

    Manual digitisation cannot decide a safety boundary. Candidates in all four
    sections are rated independently; this chart only breaks otherwise equal
    rankings. Design power is used conservatively, not un-factored motor power.
    """
    regions = {
        'SPZ': ((.1,930),(.5,5300),(.5,8000),(.1,8000)),
        'SPA': ((.1,100),(1,100),(24,2850),(30,2850),(30,8000),(.5,8000),(.5,5300),(.1,930)),
        'SPB': ((1,100),(3.5,100),(63,2100),(90,2100),(90,2850),(24,2850)),
        'SPC': ((3.5,100),(150,100),(150,2100),(63,2100)),
    }
    if not .1 <= power_kw <= 150 or not 100 <= small_rpm <= 8000:
        return ()
    x,y=math.log10(power_kw),math.log10(small_rpm)
    found=[]
    for key,vertices in regions.items():
        polygon=[(math.log10(a),math.log10(b)) for a,b in vertices]; inside=False
        for (a,b),(c,d) in zip(polygon,polygon[1:]+polygon[:1]):
            if (b>y)!=(d>y) and x<(c-a)*(y-b)/(d-b)+a:inside=not inside
        if inside:found.append(key)
    return tuple(found)


def size_tosyali_drive(request, options, *, stop=None, progress=None):
    if request.family != 'v' or request.profile is not None and request.profile not in PROFILES:
        raise ValueError('Tosyalı dar V yöntemi SPZ, SPA, SPB ve SPC içindir; STB profil adı değildir.')
    if request.service_factor is None:
        raise ValueError('Tosyalı kanal hesabı için servis faktörünü girin; uygulama yüküne göre seçilmelidir.')
    if request.manufacturer is not None or request.series_id is not None:
        raise ValueError('Bu yöntem Tosyalı kasnak + Optibelt SK 2018 kayış referansını kullanır; başka seri filtresi uygulanamaz.')
    if any(getattr(request,k) is not None for k in ('system_width_max_mm','available_installation_travel_mm','available_tensioning_travel_mm','teeth_min','teeth_max')):
        raise ValueError('Toplam gövde genişliği, germe/kurulum payı ve diş filtreleri bu V referans veri kümesinde yok; katalog yöntemini kullanın.')
    if any(k=='width' and w>0 for k,w in request.weights):
        raise ValueError('Tosyalı V veri kümesinde toplam gövde genişliği yok; genişlik ağırlığı kullanılamaz.')
    groups=defaultdict(dict)
    for pulley in catalog():
        if request.profile is not None and pulley.profile != request.profile:continue
        if outside(pulley.datum_mm,max(request.diameter_min_mm or options.diameter_min_mm,REFERENCE_MIN_DATUM_MM[pulley.profile]),
                   request.diameter_max_mm or options.diameter_max_mm):continue
        if outside(pulley.outside_mm,None,request.outside_diameter_max_mm):continue
        groups[pulley.profile].setdefault(pulley.datum_mm,{})[pulley.grooves]=pulley
    counts=Counter(); retained=[];visited=matched=work=0;cancelled=limited=False
    try:
        for profile,dimensions in groups.items():
            for d1,first in dimensions.items():
                for d2,second in dimensions.items():
                    if stop is not None and stop.is_set():raise CalculationCancelled('Durduruldu.')
                    if work>=request.work_limit:limited=True;break
                    work+=1;visited+=1
                    if progress is not None and visited%50==0:progress(visited,matched)
                    error=100*abs(request.input_rpm*d1/d2-request.target_rpm)/request.target_rpm
                    if outside(error,None,request.rpm_error_max_percent):counts['RPM_TOLERANCE']+=1;continue
                    available=sorted(first.keys() & second.keys())
                    if not available:counts['NO_COMMON_GROOVES']+=1;continue
                    low,high,target=_bounds_and_target(request,d1,d2)
                    limit=minimum_center_for_limits(request,d1,d2,None,None)
                    physical=(first[available[0]].outside_mm+second[available[0]].outside_mm)/2
                    feasible=max(low or 0.,math.nextafter(physical,math.inf),limit)
                    if not math.isfinite(feasible) or high is not None and feasible>high:
                        counts['CENTER_GEOMETRY']+=1;continue
                    spec=BeltDriveSpecification(BeltSpecification('v',profile),PulleySpecification(d1),PulleySpecification(d2),
                        LoadSpecification(request.input_rpm,request.power_kw,service_factor=request.service_factor),
                        CenterSpecification(distance_mm=max(feasible,target)))
                    try:
                        base=calculate(spec,stop=stop)
                        if base.speed_m_s>min(MAX_SPEED_M_S,request.maximum_belt_speed_m_s or MAX_SPEED_M_S):
                            counts['MAXIMUM_BELT_SPEED']+=1;continue
                        if options.length_policy=='required':
                            choices=[(base,'required')]
                        else:
                            lengths=reference_data()['profiles'][profile]['listed_lengths_mm']
                            # L(C) increases strictly; bracket the closest feasible C.
                            i=bisect_left(lengths,base.length_exact_mm)
                            choices=[]
                            for length in lengths[max(0,i-1):min(len(lengths),i+1)]:
                                try:c=solve_center_distance(d1,d2,length,stop=stop).center_mm
                                except ValueError:continue
                                if outside(c,feasible,high):continue
                                result=calculate(replace(spec,center=CenterSpecification('length',None,length)),stop=stop)
                                choices.append((result,'optibelt_sk_listed'))
                        if not choices:counts['NO_LISTED_LENGTH_IN_CENTER_BOUNDS']+=1;continue
                        choices.sort(key=lambda item:abs(item[0].center_mm-target))
                        accepted=None
                        for result,kind in choices:
                            if stop is not None and stop.is_set():raise CalculationCancelled('Durduruldu.')
                            if work>=request.work_limit:limited=True;break
                            work+=1
                            failure=operating_limit_failure(request,result)
                            if failure:counts[failure]+=1;continue
                            try:rating=rate(profile,result)
                            except ValueError:counts['SK_REFERENCE_RANGE']+=1;continue
                            channel=next((n for n in available if n>=rating.required_belts and not outside(n,None,request.max_belts)),None)
                            if channel is None:counts['INSUFFICIENT_CATALOG_GROOVES']+=1;continue
                            driver,driven=first[channel],second[channel]
                            if result.center_mm<=(driver.outside_mm+driven.outside_mm)/2:
                                counts['CENTER_GEOMETRY']+=1;continue
                            result=replace(result,specification=replace(result.specification,belt=replace(result.specification.belt,count=channel)))
                            area=(result.center_mm+d1/2+d2/2)*max(driver.outside_mm,driven.outside_mm)
                            offset=result.center_mm-target;margin=channel*rating.per_belt_power_kw/rating.design_power_kw
                            values=dict(speed=error/(request.rpm_error_max_percent or 1.),area=area/1e6,
                                        center=abs(offset)/target,belts=channel,capacity=1/margin,source=1.)
                            metric={'speed':values['speed'],'compact':values['area'],'center':values['center'],
                                    'fewest_belts':channel,'capacity':1/margin}
                            score=sum(w*values[k] for k,w in (request.weights or (('speed',1.),('area',1.),('belts',1.)))) if request.priority=='balanced' else metric[request.priority]
                            recommended=chart_sections(rating.design_power_kw,rating.small_rpm)
                            identity=f'tosyali-sk2018:{driver.code}:{driven.code}:{kind}:{result.length_exact_mm:.12g}'
                            checks=(Issue('SK_REFERENCE','Kapasite yalnız Optibelt SK 2018 kayış serisinin referans hesabıdır; başka marka/seri için geçerli değildir.',severity='WARNING'),
                                    Issue('ASSEMBLY_REVIEW','Mil deliği, burç, gövde genişliği, balans, germe, yatak yükü ve güncel ürün uygunluğu ayrıca kontrol edilmelidir.',severity='NOT_EVALUATED'))
                            if kind=='required':checks+=(Issue('CUSTOM_LENGTH','Boy teoriktir; standart/stok kayış seçilmedi.',severity='WARNING'),)
                            # Prefer a listed length, then the user's requested metric.
                            key=(int(kind=='required'),score,channel,int(bool(recommended) and profile not in recommended),error,area,abs(offset),identity)
                            accepted=TosyaliCandidate(identity,result,error,offset,base.length_exact_mm,kind,area,checks,key,
                                                      driver,driven,rating,channel)
                            break
                        if accepted is None:continue
                        matched+=1;retained.append(accepted);retained.sort(key=lambda c:c.ranking_key)
                        if len(retained)>request.result_limit:retained.pop()
                    except (ValueError,OverflowError,ZeroDivisionError):counts['CALCULATION']+=1;continue
                if limited:break
            if limited:break
    except CalculationCancelled:cancelled=True
    return NominalSizingReport(request,options,request.profile or 'SPZ / SPA / SPB / SPC',tuple(retained),visited,matched,
        tuple(sorted(counts.items())),not(cancelled or limited),matched>len(retained),cancelled,(
            'Tosyalı kasnak: kullanıcı kataloğu PDF 48–74 (basılı 46–72); 708 kayıt, çelişkili T SPB 565-2 kapsam dışı.',
            'Tosyalı kasnak çevresel hız sınırı 35 m/s; küçük çap alt sınırları SPZ 63, SPA 90, SPB 140, SPC 224 mm.',
            'Kayış: Optibelt SK, üretici teknik kılavuzu 2018; basılı 74/76/87/98–101. Tarihli referans, güncel üretici onayı değildir.',
            'Ptasarım=P×servis faktörü; Pkayış=(Ptemel+ΔPoran)×c₁×c₃; gerekli adet=tavan(Ptasarım/Pkayış).',
            'İki kasnakta ortak en küçük yeterli kanal sayısı seçilir; bütün kanallar eşlenmiş kayış takımıyla kullanılır.',
            'Tosyalı basılı 44 seçim grafiği yaklaşık ön tavsiyedir; tüm dar kesitler ayrıca güç hesabından geçirilir.',
            'Standart boy seçeneği yalnız Optibelt SK basılı 27 listesi; C hedefinin iki komşu boyu incelenir, tüm boyların küresel optimizasyonu yapılmaz.',
        ))
