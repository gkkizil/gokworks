"""Tree kinematics: a bend transports its whole downstream component."""
from math import cos, sin, radians
import numpy as np


def basis(bend):
    u = (np.asarray(bend.end)-bend.start)/bend.length
    result = np.eye(4)
    result[:3, 0] = (*u, 0)
    result[:3, 1] = (-u[1], u[0], 0)
    result[:3, 3] = (*bend.start, 0)
    return result


def rx(angle):
    c, s = cos(angle), sin(angle)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1.]])


def arc_parameters(bend, thickness, angle):
    """Constant t; measured developed width determines the interpolated radius.

    A fixed neutral factor implied by CAD is retained, including at intermediate
    angles. This is nominal geometry, not a plasticity/springback calculation.
    """
    target = radians(bend.turn)
    k = (bend.width/target-bend.radius)/thickness
    return bend.width/abs(angle)+(.5-k)*thickness


def fold_transform(bend, thickness, angle):
    if abs(angle) < 1e-10:
        return np.eye(4)
    r = arc_parameters(bend, thickness, angle)
    transform = rx(angle)
    endpoint = np.array([0, r*sin(abs(angle)), np.sign(angle)*r*(1-cos(angle))])
    transform[:3, 3] = endpoint-transform[:3, :3]@np.array([0, bend.width, 0])
    b = basis(bend)
    return b@transform@np.linalg.inv(b)


def poses(part, angles):
    transforms, pending = {part.root: np.eye(4)}, list(part.bends)
    while pending:
        previous = len(pending)
        for bend in pending[:]:
            if bend.parent in transforms:
                transforms[bend.child] = transforms[bend.parent]@fold_transform(bend, part.thickness, angles.get(bend.id, 0))
                pending.remove(bend)
        if len(pending) == previous:
            raise ValueError('Büküm grafiği sabit flanşa bağlı değil veya döngülü.')
    return transforms


def step_angles(plan, index, fraction):
    bends = {b.id: b for b in plan.part.bends}
    # Planned angle per step (target or CAD); the CAD bend zone itself never changes.
    return {s.bend: radians(plan.turn(s))*bends[s.bend].direction*(-1 if s.reverse else 1)*(fraction if i == index else 1)
            for i, s in enumerate(plan.steps) if i <= index}


def point(transform, xyz):
    return (transform@np.array([*xyz, 1.]))[:3]


def station_transform(plan, index, angles):
    """Align active axis to station X; centre neutral arc over selected V.

    Both tangents are symmetric about the station. Regripping is discrete and
    explicitly excluded from the collision motion scope.
    """
    step = plan.steps[index]
    bend = next(b for b in plan.part.bends if b.id == step.bend)
    flange = poses(plan.part, angles)[bend.parent]
    frame = flange@basis(bend)
    phi = angles.get(bend.id, 0)
    transform = rx(-phi/2)@np.linalg.inv(frame)
    # Centre the developed strip, not its near tangent.
    if abs(phi) < 1e-10:
        centre = np.array([bend.length/2, bend.width/2, 0.])
    else:
        r = arc_parameters(bend, plan.part.thickness, phi)
        centre = np.array([bend.length/2, r*sin(abs(phi)/2), np.sign(phi)*r*(1-cos(phi/2))])
    local = rx(-phi/2)[:3, :3]@centre
    transform[:3, 3] -= local
    # Negative bends are inverted so the punch works from the inside surface.
    if phi < 0 or (abs(phi) < 1e-10 and bend.direction*(-1 if step.reverse else 1) < 0):
        transform = rx(np.pi)@transform
    if step.fixed_side == 'child':
        turn = np.diag([-1., -1., 1., 1.]); transform = turn@transform
    if step.orientation == 180:
        turn = np.diag([-1., -1., 1., 1.]); transform = turn@transform
    return transform
