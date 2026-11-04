"""Nearest entries from an explicit dimension list, never invented stock products."""

from dataclasses import replace
from .._numbers import integer
from ..calculation import calculate, checkpoint
from ..catalog.models import LengthCatalog, BeltCandidate
from ..models import SpecificationError


def nearest_catalog_candidates(specification, catalog, *, limit=5, stop=None):
    reference = calculate(specification, stop=stop)
    if not isinstance(catalog, LengthCatalog) or catalog.profile != specification.belt.profile:
        raise ValueError('Katalog profili tasarımla aynı olmalı; aynı adım HTD/T/AT uyumu sağlamaz.')
    integer(limit, 'Aday sınırı')
    if limit > 10000:
        raise ValueError('Aday sınırı en çok 10000 olabilir.')
    timing = specification.belt.family == 'timing'
    dimensions = [(count * reference.pitch_mm, count) for count in catalog.tooth_counts] if timing else \
                 [(length, None) for length in catalog.lengths_mm]
    chosen = sorted(dimensions, key=lambda item: (abs(item[0] - reference.length_exact_mm), item[0]))[:limit]
    results = []
    for length, count in chosen:
        checkpoint(stop)
        center = replace(specification.center, mode='length', distance_mm=None,
                         length_mm=None if timing else length, belt_teeth=count)
        try:
            result = calculate(replace(specification, center=center), stop=stop)
            engaged = min(result.engaged_driver_teeth_estimate, result.engaged_driven_teeth_estimate) if timing else None
            candidate = BeltCandidate(catalog.identifier, catalog.profile, catalog.source, catalog.reference_line,
                length, count, result.center_mm, result.center_mm - reference.center_mm,
                min(result.driver_wrap_deg, result.driven_wrap_deg), engaged, 'GEOMETRICALLY_SUITABLE',
                'Boyut yalnız beyan edilen listede vardır; ürün bulunabilirliği, güç ve ömür doğrulanmadı.')
        except SpecificationError as error:
            candidate = BeltCandidate(catalog.identifier, catalog.profile, catalog.source, catalog.reference_line,
                length, count, None, None, None, None, 'UNSUITABLE', str(error))
        results.append(candidate)
    return tuple(results)
