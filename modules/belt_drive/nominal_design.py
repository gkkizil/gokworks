"""Catalogue-independent geometric sizing. Dimensions are NOT product SKUs.

Reuses the validated Stage 1 engine. Always retains calculated required belt
length when a preferred/integer length cannot meet the given center bounds.
No power-based section, belt-count or width approval is inferred.
"""

from collections import Counter
from bisect import bisect_left
from dataclasses import dataclass, field, asdict
import json
import math

from ._numbers import positive, integer, finite
from .calculation import calculate
from .catalog.profiles import get_profile
from .design_models import DesignRequest
from .design_search import outside, operating_limit_failure, minimum_center_for_limits
from .models import (BeltDriveSpecification,BeltSpecification,PulleySpecification,
                     CenterSpecification,LoadSpecification,Issue,BeltDriveResult)
from .preferred_sizes import preferred_sizes,REFERENCE_MIN_DATUM_MM
from .engineering.belt_length import solve_center_distance
from .validation import CalculationCancelled


@dataclass(frozen=True,slots=True)
class NominalSizingOptions:
    diameter_min_mm: float=50.
    diameter_max_mm: float=1000.
    teeth_min: int=12
    teeth_max: int=160
    length_policy: str='preferred'  # preferred / required
    pulley_source: str='nominal'  # nominal / tosyali_v_sk2018

    def __post_init__(self):
        positive(self.diameter_min_mm,'Nominal çap alt sınırı');positive(self.diameter_max_mm,'Nominal çap üst sınırı')
        if self.diameter_min_mm>self.diameter_max_mm:
            raise ValueError('Nominal çap sınırları ters.')
        integer(self.teeth_min,'Diş alt sınırı');integer(self.teeth_max,'Diş üst sınırı')
        if self.teeth_min>self.teeth_max or self.teeth_max-self.teeth_min>2000:
            raise ValueError('Diş aralığı ters veya 2000 adım sınırından büyük.')
        if self.length_policy not in ('preferred','required'):
            raise ValueError('Boy politikası preferred/required olmalı.')
        if self.pulley_source not in ('nominal','tosyali_v_sk2018'):
            raise ValueError('Bilinmeyen kasnak/kayış referans yöntemi.')


@dataclass(frozen=True,slots=True)
class NominalCandidate:
    identifier: str
    result: BeltDriveResult
    rpm_error_percent: float
    center_deviation_mm: float
    required_length_mm: float
    length_kind: str  # required / preferred_r40 / integer_pitch
    reference_area_mm2: float
    checks: tuple[Issue,...]
    ranking_key: tuple
    catalog_product: bool=field(default=False,init=False)
    engineering_approved: bool=field(default=False,init=False)


@dataclass(frozen=True,slots=True)
class NominalSizingReport:
    request: DesignRequest
    options: NominalSizingOptions
    profile: str
    candidates: tuple[NominalCandidate,...]
    pairs_visited: int
    matching_count: int
    rejection_counts: tuple[tuple[str,int],...]
    search_complete: bool
    results_limited: bool
    cancelled: bool
    assumptions: tuple[str,...]

    @property
    def capacity_verified(self):return ()

    @property
    def unverified(self):return self.candidates


def _bounds_and_target(request,d1,d2):
    if request.mode=='fixed':
        return (request.center_target_mm-request.center_tolerance_mm,
                request.center_target_mm+request.center_tolerance_mm,request.center_target_mm)
    low,high=request.center_min_mm,request.center_max_mm
    target=request.center_target_mm
    if target is None:
        physical=d1/2+d2/2
        if low is not None and high is not None:
            target=(max(low,math.nextafter(physical,math.inf))/2+high/2) if high>physical else high
        else:target=d1+d2
        if low is not None:target=max(target,low)
        if high is not None:target=min(target,high)
    return low,high,target


def _chosen_spec(spec,request,options,low,high,target,stop):
    base=calculate(spec,stop=stop)
    if options.length_policy=='required':return base,'required',base.length_exact_mm
    timing=request.family=='timing'
    if timing:
        n=base.theoretical_belt_teeth
        lengths=tuple((count*base.pitch_mm,count) for count in sorted({max(1,math.floor(n)),max(1,math.ceil(n))}))
    else:
        length=base.length_exact_mm
        lengths=tuple((value,None) for value in preferred_sizes(max(.001,length/2),min(1e7,length*2)))
    # L(C) is monotone: the immediate length below/above the target brackets
    # the closest center; farther lengths on either side cannot improve it.
    lengths=sorted(lengths)
    index=bisect_left([x[0] for x in lengths],base.length_exact_mm)
    lengths=lengths[max(0,index-1):min(len(lengths),index+1)]
    choices=[]
    for length,count in lengths:
        if stop is not None and stop.is_set():raise CalculationCancelled('Nominal boy seçimi durduruldu.')
        try:
            c=solve_center_distance(base.driver_reference_diameter_mm,base.driven_reference_diameter_mm,length,stop=stop).center_mm
            if outside(c,low,high):continue
            center=CenterSpecification('length',None,None if timing else length,count)
            selected=calculate(BeltDriveSpecification(spec.belt,spec.driver,spec.driven,spec.load,center),stop=stop)
            if operating_limit_failure(request,selected):continue
            choices.append((abs(c-target),length,selected))
        except ValueError:
            continue
    if not choices:return base,'required',base.length_exact_mm
    result=min(choices,key=lambda x:(x[0],x[1]))[2]
    return result,'integer_pitch' if timing else 'preferred_r40',base.length_exact_mm


def size_drive(request,options=None,*,stop=None,progress=None):
    if not isinstance(request,DesignRequest):raise ValueError('DesignRequest gerekli.')
    options=options or NominalSizingOptions()
    if not isinstance(options,NominalSizingOptions):raise ValueError('NominalSizingOptions gerekli.')
    if options.pulley_source=='tosyali_v_sk2018':
        from .tosyali_design import size_tosyali_drive
        return size_tosyali_drive(request,options,stop=stop,progress=progress)
    if request.manufacturer is not None or request.series_id is not None:
        raise ValueError('Genel boyutlandırma üretici/seri filtrelemez; katalog yöntemini kullanın.')
    if any(getattr(request,k) is not None for k in ('outside_diameter_max_mm','system_width_max_mm','max_belts',
            'available_installation_travel_mm','available_tensioning_travel_mm')):
        raise ValueError('Gerçek dış çap/genişlik/adet/germe sınırları ürün verisi gerektirir; katalog yöntemini kullanın.')
    if request.priority in ('capacity','fewest_belts'):
        raise ValueError('Adet/kapasite sıralaması üretici verisi gerektirir; genel boyutlandırmada devir/alan/C kullanın.')
    if request.priority=='balanced' and any(k not in ('speed','area','center') and w>0 for k,w in request.weights):
        raise ValueError('Genel boyutlandırma ağırlıkları yalnız devir, referans alanı ve C olabilir.')
    profile=get_profile(request.profile or ('A' if request.family=='v' else 'HTD_5M'))
    if profile.family!=request.family or not profile.nominal_supported:raise ValueError('Profil/aile uyuşmuyor.')
    dlo=request.diameter_min_mm or options.diameter_min_mm; dhi=request.diameter_max_mm or options.diameter_max_mm
    if request.family=='v':
        dimensions=tuple((d,None) for d in preferred_sizes(max(dlo,REFERENCE_MIN_DATUM_MM[profile.key]),dhi))
    else:
        zlo=request.teeth_min or options.teeth_min;zhi=request.teeth_max or options.teeth_max
        if zhi-zlo>2000:raise ValueError('Diş aralığı 2000 adım sınırını aşıyor.')
        dimensions=tuple((z*profile.pitch_mm/math.pi,z) for z in range(zlo,zhi+1)
                         if not outside(z*profile.pitch_mm/math.pi,request.diameter_min_mm,request.diameter_max_mm))
    if not dimensions:raise ValueError('Profil ve çap/diş sınırları içinde nominal kasnak ölçüsü yok.')
    upper=request.center_target_mm+request.center_tolerance_mm if request.mode=='fixed' else request.center_max_mm
    if upper is not None and upper<=min(x[0] for x in dimensions):
        raise ValueError(f'C üst sınırı {upper:g} mm çok küçük. Bu çap aramasında C en az {min(x[0] for x in dimensions):g} mm değerinden büyük olmalı; örneğin 300–500 mm aralığını değerlendirin.')
    visited=matched=0;cancelled=False;limited=False;counts=Counter();retained=[]
    for d1,z1 in dimensions:
        for d2,z2 in dimensions:
            if stop is not None and stop.is_set():cancelled=True;break
            if visited>=request.work_limit:limited=True;break
            visited+=1
            if progress is not None and visited%100==0:progress(visited,matched)
            try:
                ratio=z2/z1 if z1 is not None else d2/d1
                error=finite(100*abs(request.input_rpm/ratio-request.target_rpm)/request.target_rpm,'Devir sapması')
                if outside(error,None,request.rpm_error_max_percent):counts['RPM_TOLERANCE']+=1;continue
                low,high,target=_bounds_and_target(request,d1,d2)
                physical=d1/2+d2/2
                limit_center=minimum_center_for_limits(request,d1,d2,z1,z2)
                if not math.isfinite(limit_center):
                    counts['MINIMUM_ENGAGED_TEETH' if request.minimum_engaged_teeth is not None else 'MINIMUM_WRAP']+=1;continue
                feasible=max(low or 0.,math.nextafter(physical,math.inf),limit_center)
                if high is not None and feasible>high:
                    counts['CENTER_GEOMETRY' if high<=physical else 'OPERATING_CENTER_BOUNDS']+=1;continue
                trial=max(target,feasible)
                spec=BeltDriveSpecification(BeltSpecification(request.family,profile.key),
                    PulleySpecification(None,z1) if z1 is not None else PulleySpecification(d1),
                    PulleySpecification(None,z2) if z2 is not None else PulleySpecification(d2),
                    LoadSpecification(request.input_rpm,request.power_kw,service_factor=request.service_factor),
                    CenterSpecification(distance_mm=trial))
                result,kind,required=_chosen_spec(spec,request,options,feasible,high,target,stop)
                failed_limit=operating_limit_failure(request,result)
                if failed_limit:counts[failed_limit]+=1;continue
                area=positive((result.center_mm+d1/2+d2/2)*max(d1,d2),'Referans alanı')
                offset=result.center_mm-target
                if request.priority=='balanced':
                    weights=request.weights or (('speed',1.),('area',1.),('center',1.))
                    values=dict(speed=error/(request.rpm_error_max_percent or 1.),area=area/1e6,center=abs(offset)/target)
                    score=sum(w*values[k] for k,w in weights if w)
                else:score=area if request.priority=='compact' else abs(offset) if request.priority=='center' else error
                score=finite(score,'Nominal sıralama puanı')
                identity=json.dumps((profile.key,d1,d2,target,kind,result.selected_length_mm,result.selected_belt_teeth),separators=(',',':'))
                checks=(Issue('NOMINAL_DIMENSIONS','Kasnak ve kayış değerleri nominal tasarım ölçüleridir; ürün kodu/standart stok uygunluğu onaylanmaz.',severity='INFO'),
                    Issue('SECTION_AND_COUNT','Profil seçimi güç tablosundan yapılmadı; gerekli kayış adedi/genişliği üretici verisiyle boyutlandırılmalı.',severity='NOT_EVALUATED'),
                    Issue('CAPACITY','Güç/ömür/germe ve gerçek dış gövde zarfı doğrulanmadı.',severity='NOT_EVALUATED'))
                if trial!=target:
                    checks+=(Issue('TARGET_CENTER_ADJUSTED',f'Hedef C={target:g} mm uygulanamıyor; izin verilen aralıktaki ilk geometrik çözüm C={trial:g} mm üzerinden boy seçildi.',severity='WARNING'),)
                if kind=='required' and request.family=='timing':
                    checks+=(Issue('TIMING_LENGTH_UNSELECTED','Bu sonuç teorik bölüm boyudur; kullanılacak kapalı kayış için tam diş sayısı ve buna uygun C seçilmelidir.',severity='WARNING'),)
                # In preferred mode retain theoretical fallbacks, but never let
                # them hide a candidate with a selected discrete belt length.
                key=(int(options.length_policy=='preferred' and kind=='required'),score,error,area,abs(offset),identity)
                candidate=NominalCandidate(identity,result,error,offset,required,kind,area,checks,key)
            except CalculationCancelled:cancelled=True;break
            except (ValueError,OverflowError,ZeroDivisionError):counts['CALCULATION']+=1;continue
            matched+=1;retained.append(candidate);retained.sort(key=lambda x:x.ranking_key)
            if len(retained)>request.result_limit:retained.pop()
        if cancelled or limited:break
    return NominalSizingReport(request,options,profile.key,tuple(retained),visited,matched,tuple(sorted(counts.items())),
        not(cancelled or limited),matched>len(retained),cancelled,(
            (f'V çap arama kapsamı {dlo:g}–{dhi:g} mm; R40 tercihli nominal ölçülerdir, katalog ürünü değildir.' if request.family=='v' else
             f'Kasnak diş arama kapsamı {zlo}–{zhi}; bölüm çapı z×p/π hesaplanır, katalog ürünü olduğu varsayılmaz.'),
            'V datum uzunluğu Ld, triger-senkron bölüm uzunluğu kullanılır; Li/La dönüşümü yapılmaz.',
            'C verilmezse aralığın fiziksel olarak uygun kısmının ortası veya D₁+D₂ başlangıç mesafesi kullanılır; bu üretici yerleşim onayı değildir.',
            'R40 tercihli boy ISO 3 sayı yaklaşımıdır; ISO 4184 ürün uygunluğu ve stok bulunabilirliği ayrıca kontrol edilmelidir.',
        ))


def report_to_dict(report,*,selected_ids=None):
    if not isinstance(report,NominalSizingReport):raise ValueError('NominalSizingReport gerekli.')
    data=asdict(report)
    if selected_ids is not None:
        ids=set(selected_ids)
        if not ids<={x.identifier for x in report.candidates}:raise ValueError('Güncel nominal aday seçimi gerekli.')
        data['candidates']=tuple(c for c in data['candidates'] if c['identifier'] in ids)
    return dict(schema='gokworks.belt_drive.nominal_result',version=1,units='mm',**data)
