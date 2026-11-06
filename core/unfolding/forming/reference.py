"""Compare explicit supplied catalogue dimensions/points; never infer equivalence."""
import math
from .mechanics import compare_reference
from ..models import FrozenMap,to_data


def compare_part(part,reference):
    if reference['part_id']!=part.id:
        return FrozenMap(dict(status='NOT_EVALUATED',reason='Referans parça kimliği bu parçayla eşleşmiyor.'))
    bounds=part.metrics.bounds_mm
    nominal=part.nominal_part or part;nb=nominal.metrics.bounds_mm
    available=dict(width=bounds[2]-bounds[0],height=bounds[3]-bounds[1],cutting_length=part.metrics.cutting_length_mm,
                   nominal_length=nb[2]-nb[0],compensated_length=bounds[2]-bounds[0])
    dimensions=reference.get('measurements_mm',{})
    if 'compensated_length' in dimensions and not part.nominal_part:
        return FrozenMap(dict(status='NOT_EVALUATED',reason='Telafi uygulanmadı; telafili ölçü karşılaştırılamaz.'))
    result=to_data(compare_reference(dimensions,{k:available[k] for k in dimensions},source=reference['source'],
                                     absolute_tolerance_mm=reference['absolute_tolerance_mm'],
                                     relative_tolerance_percent=reference['relative_tolerance_percent'])) if dimensions else dict(points=[],dimensions_match=True)
    mapped={m.id:m.developed for m in part.mappings};points=[]
    for key,xy in reference.get('points_mm',{}).items():
        if key not in mapped:
            points.append(dict(point=key,status='NOT_EVALUATED',reason='Hesapta aynı kimlikli ölçüm noktası yok.'));continue
        distance=math.dist(xy,mapped[key]);length=math.hypot(*xy);percent=distance/length*100 if length else None
        points.append(dict(point=key,status='COMPARED',reference_mm=xy,computed_mm=mapped[key],
                           absolute_error_mm=distance,percent_error=percent,
                           within_tolerance=distance<=reference['absolute_tolerance_mm'] and (percent is None or percent<=reference['relative_tolerance_percent'])))
    result.update(status='COMPARED',point_measurements=points,source=reference['source'],
                  all_supplied_measurements_match=result['dimensions_match'] and all(p.get('within_tolerance',False) for p in points),
                  geometry_equivalence_verified=False,production_equivalence_verified=False)
    return FrozenMap(result)
