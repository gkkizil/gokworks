"""Conservative straight-prism verification. Never infer length from an AABB."""

from dataclasses import dataclass
from math import sqrt, isfinite


@dataclass(frozen=True)
class Face:
    kind: str
    direction: tuple[float, float, float]
    point: tuple[float, float, float] = (0., 0., 0.)


@dataclass(frozen=True)
class Verification:
    verified: bool
    length_mm: float | None = None
    reason: str = ''


def unit(vector):
    if len(vector) != 3 or not all(isfinite(v) for v in vector): raise ValueError('Geometri vektörü geçersiz.')
    norm = sqrt(sum(v*v for v in vector))
    if norm < 1e-12: raise ValueError('Geometri yönü sıfır.')
    return tuple(v/norm for v in vector)


def dot(a, b): return sum(x*y for x, y in zip(a, b))


def verify(faces, expected_mm=None):
    """Two end planes, all remaining faces axial planes or axial cylinders.

    Face positions are SI metres. Parallel intermediate end faces, oblique
    planes, transverse holes, toroidal/spline surfaces and ambiguous axes fail.
    This supports a deliberately restricted, untapered straight-prism family.
    """
    if not faces or any(face.kind not in ('plane', 'cylinder') for face in faces):
        return Verification(False, reason='Kavisli veya özel yüzey: doğrusal prizma doğrulanamadı.')
    try:
        normals = [(face, unit(face.direction)) for face in faces]
        axes = []
        for face, normal in normals:
            if face.kind == 'plane' and not any(abs(dot(normal, axis)) > 1-1e-7 for axis in axes):
                axes.append(normal)
        candidates = []
        for axis in axes:
            positions = []
            valid = True
            for face, normal in normals:
                alignment = abs(dot(normal, axis))
                if face.kind == 'cylinder':
                    if alignment < 1-1e-7: valid = False; break
                elif alignment > 1-1e-7:
                    if len(face.point) != 3 or not all(isfinite(p) for p in face.point): valid = False; break
                    position = dot(face.point, axis)
                    if not any(abs(position-p) < 1e-7 for p in positions): positions.append(position)
                elif alignment > 1e-7:
                    valid = False; break
            if not valid or len(positions) != 2: continue
            length = abs(positions[1]-positions[0])*1000
            if length <= .001: continue
            if expected_mm is not None and abs(length-float(expected_mm)) > max(.001, float(expected_mm)*1e-7): continue
            candidates.append(length)
        if len(candidates) != 1:
            return Verification(False, reason='Tek doğrusal eksen ve kare uçlar doğrulanamadı; gönye/cope/özel trim veya boy uyuşmazlığı olabilir.')
        return Verification(True, candidates[0])
    except (ValueError, TypeError, OverflowError):
        return Verification(False, reason='Geometri verisi okunamadı veya geçersiz.')
