"""Deterministic ordering after hard filters, with explicit missing-data penalties."""

from math import isfinite


def ranking_key(request, *, error, center_deviation, area, count, width, margin, source_statuses, identifiers):
    if request.priority == 'balanced':
        weights = request.weights or (('speed', 1.), ('center', 1.), ('area', 1.), ('belts', 1.))
        # Normalizations are units/scales, never hidden physical constraints.
        metrics = dict(speed=error / (request.rpm_error_max_percent or 1.),
            center=abs(center_deviation) / request.center_target_mm if center_deviation is not None else None,
            area=area / (request.diameter_max_mm**2 if request.diameter_max_mm else 1e6),
            belts=count / (request.max_belts or 1.) if count is not None else None,
            width=width / (request.system_width_max_mm or 1000.) if width is not None else None,
            capacity=1. / margin if margin is not None else None,
            source=max({'OFFICIAL_VERIFIED': 0., 'USER_SUPPLIED': 1., 'EXAMPLE': 2., 'OUTDATED': 3., 'INCOMPLETE': 4.}[x] for x in source_statuses))
        missing = sum(weight for key, weight in weights if weight and metrics[key] is None)
        value = sum(weight * metrics[key] for key, weight in weights if weight and metrics[key] is not None)
        if not isfinite(value) or not isfinite(missing):
            raise ValueError('Sıralama puanı sayısal aralığı aşıyor.')
        return (missing, value, error, *identifiers)
    metric = dict(speed=error, center=abs(center_deviation) if center_deviation is not None else None,
                  compact=area, fewest_belts=count, capacity=-margin if margin is not None else None)[request.priority]
    return (1 if metric is None else 0, metric if metric is not None else 0., error, *identifiers)
