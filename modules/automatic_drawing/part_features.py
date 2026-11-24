"""Read-only observations of machined features on the active part configuration."""

from collections import defaultdict
from dataclasses import replace
import math

from .models import Detail, Hole, degrees, to_mm
from .solidworks import call, get, optional, values

# The Wizard API documents properties per swWzdHoleTypes_e value. Other
# properties can return defaults that do not describe the selected hole.
WIZARD_TYPES = {code: (end, tuple(properties.split()))
                for codes, end, properties in (
    ((0, 5), '',
     'Diameter Depth'),
    ((1, 6), '',
     'MinorDiameter Depth MajorDiameter'),
    ((2, 7), '',
     'Diameter Depth CounterBoreDiameter CounterBoreDepth'),
    ((3,), '',
     'Diameter Depth CounterSinkAngle CounterSinkDiameter'),
    ((4, 9), '',
     'Diameter Depth CounterDrillDiameter CounterDrillDepth CounterDrillAngle'),
    ((8,), '',
     'Diameter Depth CounterSinkDiameter CounterSinkAngle'),
    ((10,), 'blind',
     'HoleDiameter HoleDepth CounterBoreDiameter CounterBoreDepth'),
    ((11,), 'blind',
     'HoleDiameter HoleDepth CounterBoreDiameter CounterBoreDepth MidCounterSinkDiameter MidCounterSinkAngle'),
    ((12,), 'blind',
     'HoleDiameter HoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((13,), 'blind',
     'HoleDiameter HoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle MidCounterSinkDiameter MidCounterSinkAngle'),
    ((14,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth'),
    ((15,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth FarCounterSinkDiameter FarCounterSinkAngle'),
    ((16,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth MidCounterSinkDiameter MidCounterSinkAngle'),
    ((17,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth MidCounterSinkDiameter MidCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((18,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((19,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((20,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle MidCounterSinkDiameter MidCounterSinkAngle'),
    ((21,), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterBoreDiameter CounterBoreDepth NearCounterSinkDiameter NearCounterSinkAngle MidCounterSinkDiameter MidCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((22,), 'blind',
     'HoleDiameter HoleDepth'),
    ((23,), 'blind',
     'HoleDiameter HoleDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((24, 43), 'blind',
     'HoleDiameter HoleDepth CounterSinkDiameter CounterSinkAngle'),
    ((25,), 'through',
     'ThruHoleDiameter ThruHoleDepth'),
    ((26,), 'through',
     'ThruHoleDiameter ThruHoleDepth FarCounterSinkDiameter FarCounterSinkAngle'),
    ((27,), 'through',
     'ThruHoleDiameter ThruHoleDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((28,), 'through',
     'ThruHoleDiameter ThruHoleDepth NearCounterSinkDiameter NearCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((29, 44), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterSinkDiameter CounterSinkAngle'),
    ((30, 45), 'through',
     'ThruHoleDiameter ThruHoleDepth CounterSinkDiameter CounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((31, 46), 'blind',
     'TapDrillDiameter TapDrillDepth ThreadDiameter ThreadDepth'),
    ((32, 47), 'blind',
     'TapDrillDiameter TapDrillDepth ThreadDiameter ThreadDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((33, 48), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadDepth'),
    ((34, 50), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadDepth FarCounterSinkDiameter FarCounterSinkAngle'),
    ((35, 49), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((36,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadDepth NearCounterSinkDiameter NearCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((37,), 'blind',
     'TapDrillDiameter TapDrillDepth ThreadDiameter ThreadAngle ThreadDepth'),
    ((38,), 'blind',
     'TapDrillDiameter TapDrillDepth ThreadDiameter ThreadAngle ThreadDepth CounterSinkDiameter CounterSinkAngle'),
    ((39,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadAngle ThreadDepth'),
    ((40,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadAngle ThreadDepth FarCounterSinkDiameter FarCounterSinkAngle'),
    ((41,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadAngle ThreadDepth NearCounterSinkDiameter NearCounterSinkAngle'),
    ((42,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadAngle ThreadDepth NearCounterSinkDiameter NearCounterSinkAngle FarCounterSinkDiameter FarCounterSinkAngle'),
    ((51,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThreadDiameter ThreadDepth FarCounterSinkDiameter FarCounterSinkAngle NearCounterSinkDiameter NearCounterSinkAngle'),
    ((52,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThruHoleDepth ThruHoleDiameter ThreadDiameter ThreadDepth ThreadEndCondition'),
    ((53,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThruHoleDepth ThruHoleDiameter ThreadDiameter ThreadDepth ThreadEndCondition NearCounterSinkDiameter NearCounterSinkAngle'),
    ((54,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThruHoleDepth ThruHoleDiameter ThreadDiameter ThreadDepth ThreadEndCondition FarCounterSinkDiameter FarCounterSinkAngle'),
    ((55,), 'through',
     'ThruTapDrillDiameter ThruTapDrillDepth ThruHoleDepth ThruHoleDiameter ThreadDiameter ThreadDepth ThreadEndCondition FarCounterSinkDiameter FarCounterSinkAngle NearCounterSinkDiameter NearCounterSinkAngle'),
    ((56,), 'blind',
     'TapDrillDiameter TapDrillDepth'),
) for code in codes}
SLOT_TYPES = dict(zip(range(57, 80), (*range(10, 31), 43, 44))) | {90: 45}
THREAD_FIELDS = ('FastenerSize', 'ThreadClass', 'Standard2', 'FastenerType2')

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def circle(edge):
    curve = call(edge, 'GetCurve')
    if curve is None or not call(curve, 'IsCircle'):
        return None
    data = values(get(curve, 'CircleParams'))
    if len(data) != 7 or not all(math.isfinite(n) for n in data) or data[6] <= 0:
        return None
    return tuple(to_mm(n) for n in data[:3]), tuple(data[3:6]), to_mm(data[6])


def cylinder_hole(face, area, axis, radius):
    if optional(face, 'FaceInSurfaceSense') is not True or radius <= 0:
        return None
    rims = []
    blind = False
    for edge in values(optional(face, 'GetEdges', default=())):
        geometry = circle(edge)
        if geometry is None:
            continue
        center, normal, rim_radius = geometry
        if abs(dot(normal, axis)) < .9999 or abs(rim_radius-radius) > .005:
            continue
        if not any(math.dist(center, seen) < .005 for seen in rims):
            rims.append(center)
        for neighbor in values(optional(edge, 'GetTwoAdjacentFaces2', default=())):
            if neighbor is None or not call(call(neighbor, 'GetSurface'), 'IsPlane'):
                continue
            # A closed end needs a planar disk bounded only by this rim.
            # A planar entry face with a circular inner loop has other edges.
            if (len(values(optional(neighbor, 'GetEdges', default=()))) == 1 and
                    abs(float(call(neighbor, 'GetArea'))*1e6-math.pi*radius**2) <= .02*math.pi*radius**2):
                blind = True
    if len(rims) != 2:
        return None
    rims.sort()
    span = abs(dot(tuple(y-x for x, y in zip(*rims)), axis))
    if span <= .01 or not .98 <= area/(2*math.pi*radius*span) <= 1.02:
        return None
    owner = optional(face, 'GetFeature')
    feature = str(get(owner, 'Name')) if owner is not None else ''
    return Hole(axis, tuple(rims), 2*radius, feature, end_condition='blind' if blind else '')


def wizard_definition(session, feature):
    definition = call(feature, 'GetDefinition')
    if definition is None:
        return None
    definition = session.named_interface(definition, 'IWizardHoleFeatureData2')
    kind = optional(definition, 'Type', property=True)
    if type(kind) is not int or SLOT_TYPES.get(kind, kind) not in WIZARD_TYPES:
        return None
    end = optional(definition, 'EndCondition', property=True)
    type_end, names = WIZARD_TYPES[SLOT_TYPES.get(kind, kind)]
    condition = next((value for name, value in (
        ('swEndCondBlind', 'blind'), ('swEndCondThroughAll', 'through'),
        ('swEndCondThroughAllBoth', 'through')) if type(end) is int and end == session.constants.get(name)), type_end)
    parameters = []
    texts = THREAD_FIELDS if 'ThreadDiameter' in names else ('Standard2', 'FastenerType2')
    for name in (*names, *texts, *(('Length',) if kind in SLOT_TYPES else ())):
        value = optional(definition, name, property=True)
        if name in (*texts, 'ThreadEndCondition'):
            if type(value) is int and value >= 0 or isinstance(value, str) and value.strip():
                parameters.append((name, value if type(value) is int else value.strip()))
        elif type(value) in (int, float) and math.isfinite(value) and value > 0:
            parameters.append((name, (degrees if name.endswith('Angle') else to_mm)(value)))
    return str(kind), condition, tuple(parameters)


def line_distance(a, b, axis):
    delta = tuple(x-y for x, y in zip(a, b))
    return math.dist(delta, tuple(dot(delta, axis)*v for v in axis))


def apply_wizard_data(holes, definitions):
    """Match by feature ownership. Each bore of one wizard is counted once."""
    grouped = defaultdict(list)
    plain = []
    for hole in holes:
        definition = definitions.get(hole.feature)
        if definition is None:
            plain.append(hole)
            continue
        kind, end, parameters = definition
        grouped[hole.feature].append(replace(hole, wizard_type=kind, end_condition=end or hole.end_condition,
                                             parameters=parameters))
    for members in grouped.values():
        locations = []
        for hole in sorted(members, key=lambda h: -h.diameter_mm):
            for index, existing in enumerate(locations):
                if (abs(dot(hole.axis, existing.axis)) > .9999 and
                        line_distance(hole.rims_mm[0], existing.rims_mm[0], hole.axis) <= .005):
                    locations[index] = replace(existing, rims_mm=tuple(dict.fromkeys(
                        (*existing.rims_mm, *hole.rims_mm))))
                    break
            else:
                locations.append(hole)
        plain.extend(locations)
    return plain


def detail_evidence(session, face, surface, wizard, axis=(), radius=None):
    owner = optional(face, 'GetFeature')
    kind = str(call(owner, 'GetTypeName2')).casefold() if owner is not None else ''
    slot = wizard.get(str(get(owner, 'Name'))) if kind == 'holewzd' else None
    slot = slot if slot is not None and int(slot[0]) in SLOT_TYPES else None
    if not (slot and axis) and not any(token in kind for token in ('fillet', 'chamfer')):
        return None
    bounds = values(optional(face, 'GetBox', default=()))
    if len(bounds) != 6 or not all(math.isfinite(v) for v in bounds):
        return None
    spans = [to_mm(high-low) for low, high in zip(bounds[:3], bounds[3:])]
    if slot:
        data = dict(slot[2])
        size = data.get('HoleDiameter', data.get('ThruHoleDiameter', 0.))
        label = 'Kanal'
    elif 'chamfer' in kind:
        definition = optional(owner, 'GetDefinition')
        chamfer = session.named_interface(definition, 'IChamferFeatureData2') if definition is not None else None
        width = optional(chamfer, 'GetEdgeChamferDistance', 0)
        size = to_mm(width) if type(width) in (int, float) and math.isfinite(width) else 0.
        label = 'Pah'
    else:
        torus = values(optional(surface, 'TorusParams', property=True, default=())) if radius is None else ()
        size = radius if radius is not None else to_mm(torus[7]) if len(torus) == 8 else 0.
        if len(torus) == 8:
            axis = torus[3:6]
        label = 'Radyüs'
    if not .01 <= size:
        return None
    normal = max(range(3), key=lambda i: abs(axis[i])) if axis else min(range(3), key=spans.__getitem__)
    point = tuple(to_mm((lo+hi)/2) for lo, hi in zip(bounds[:3], bounds[3:]))
    return Detail(label, point, size, normal)
