"""Partial catalogue-pulley alternatives when belt SKUs are not yet available.

This is deliberately separate from complete drive search: no belt length,
actual installation center or capacity is inferred from a pulley catalogue.
"""

from dataclasses import dataclass, field
from math import isclose
from .catalog.importers import fingerprint
from .design_search import outside, _fits_product, compatibility_group
from .engineering.kinematics import belt_speed_m_s
from .models import Issue


@dataclass(frozen=True, slots=True)
class PulleyPairAlternative:
    manufacturer: str
    series_id: str
    driver_code: str
    driven_code: str
    driver_teeth: int | None
    driven_teeth: int | None
    ratio: float
    nominal_output_rpm: float
    rpm_error_percent: float
    checks: tuple[Issue, ...]
    source_ids: tuple[str, ...] = ()
    complete_drive: bool = field(default=False, init=False)
    capacity_verified: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class PulleyPairReport:
    alternatives: tuple[PulleyPairAlternative, ...]
    pairs_visited: int
    matching_count: int
    search_complete: bool
    results_limited: bool
    cancelled: bool
    catalog_sha256: str
    sources: tuple = ()


def search_pulley_pairs(request, catalog, *, stop=None):
    from .design_models import DesignRequest
    from .catalog.products import ProductCatalog
    if not isinstance(request, DesignRequest) or not isinstance(catalog, ProductCatalog):
        raise ValueError('DesignRequest ve ProductCatalog gerekli.')
    if request.priority != 'speed':
        raise ValueError('Eksik kayış verisinde kasnak-çifti araması yalnız devir sıralaması sağlar.')
    groups = {}
    for pulley in catalog.pulleys:
        if not _fits_product(request,catalog,pulley):
            continue
        if outside(pulley.diameter_mm,request.diameter_min_mm,request.diameter_max_mm):
            continue
        if request.family=='timing' and outside(pulley.teeth,request.teeth_min,request.teeth_max):
            continue
        key=compatibility_group(catalog,pulley)
        groups.setdefault(key,[]).append(pulley)
    count=visited=0; complete=True; cancelled=False; results=[]
    for key in sorted(groups):
        pulleys=sorted(groups[key],key=lambda x:x.code)
        for driver in pulleys:
            for driven in pulleys:
                if stop is not None and stop.is_set():
                    complete=False;cancelled=True;break
                if visited>=request.work_limit:
                    complete=False;break
                visited+=1
                if outside(belt_speed_m_s(driver.diameter_mm,request.input_rpm),None,request.maximum_belt_speed_m_s):
                    continue
                ratio=driven.teeth/driver.teeth if request.family=='timing' else driven.diameter_mm/driver.diameter_mm
                rpm=request.input_rpm/ratio
                error=100*abs(rpm-request.target_rpm)/request.target_rpm
                if outside(error,None,request.rpm_error_max_percent):
                    continue
                if driver.nominal_belt_width_mm is not None and driven.nominal_belt_width_mm is not None and \
                        not isclose(driver.nominal_belt_width_mm,driven.nominal_belt_width_mm):
                    continue
                checks=(Issue('BELT_PRODUCT_MISSING','Bu yalnız kasnak çifti alternatifidir; gerçek kayış SKU/uzunluk ve gerçekleşen C seçilmedi.',severity='NOT_EVALUATED'),
                        Issue('MANUFACTURER_CAPACITY','Profil uyumu, kapasite, hız/minimum kasnak ve germe onayı verilmedi.',severity='NOT_EVALUATED'),
                        Issue('PARTIAL_SEARCH','Bu arama yalnız profil/seri/uyumluluk, çap/diş ve hedef devir filtresidir; C/germe/kurulum/genişlik kısıtları tamamlanmış sayılmaz.',severity='NOT_EVALUATED'))
                candidate=PulleyPairAlternative(catalog.source(driver.source_id).manufacturer,driver.series_id,driver.code,
                    driven.code,driver.teeth,driven.teeth,ratio,rpm,error,checks,tuple(sorted({driver.source_id,driven.source_id})))
                count+=1
                if request.include_unverified:
                    results.append(candidate)
                    results.sort(key=lambda x:(x.rpm_error_percent,x.series_id,x.driver_code,x.driven_code))
                    if len(results)>request.result_limit:
                        results.pop()
            if not complete:break
        if not complete:break
    if stop is not None and stop.is_set():
        complete=False;cancelled=True
    return PulleyPairReport(tuple(results),visited,count,complete,count>len(results),cancelled,fingerprint(catalog),catalog.sources)
