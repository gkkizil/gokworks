"""Native tessellation validation and crease edges; no DXF-to-3D inference."""

import numpy as np

from modules.cad_converter.models import checkpoint
from .models import Mesh

MAX_TRIANGLES = 120000


def make_mesh(coordinates, stop=None):
    checkpoint(stop)
    points = np.asarray(coordinates, dtype=np.float64)
    if points.size == 0 or points.size % 9 or points.size > MAX_TRIANGLES * 9:
        raise ValueError('3D üçgen verisi boş/geçersiz veya 120.000 üçgen sınırını aşıyor.')
    if not np.isfinite(points).all():
        raise ValueError('SolidWorks üçgen verisi sonlu olmayan koordinat içeriyor.')
    points = points.reshape((-1, 3, 3)) * 1000  # API metres -> display mm
    normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    points, normals, lengths = points[valid], normals[valid], lengths[valid]
    if not len(points):
        raise ValueError('Görüntülenebilir yüzey üçgeni bulunamadı.')
    normals /= lengths[:, None]
    vertices = points.reshape((-1, 3))
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    if np.max(high - low) <= 0 or np.max(np.abs(vertices)) > 1e12:
        raise ValueError('3D parça sınırları geçersiz.')
    # Avoid float32 collapse for a small part far from the model origin.
    origin = (low + high) / 2
    points = points - origin
    vertices = points.reshape((-1, 3))
    low, high = low - origin, high - origin
    # Do not display every triangle diagonal as a CAD edge. Retain boundaries
    # and >=30 degree creases. Quantisation is visual only, never for machining.
    quantum = max(float(np.max(high - low)) * 1e-8, 1e-7)
    edges = {}
    for i, triangle in enumerate(points):
        if i % 256 == 0:
            checkpoint(stop)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(np.rint(triangle[a] / quantum).astype(np.int64)),
                                tuple(np.rint(triangle[b] / quantum).astype(np.int64)))))
            if key not in edges:
                edges[key] = [triangle[a], triangle[b], normals[i], 1, False]
            else:
                entry = edges[key]
                entry[3] += 1
                entry[4] |= float(np.dot(entry[2], normals[i])) < .8660254
    lines = [point for a, b, _, count, crease in edges.values()
             if count == 1 or crease for point in (a, b)]
    checkpoint(stop)
    return Mesh(vertices.astype('<f4').tobytes(), np.repeat(normals, 3, axis=0).astype('<f4').tobytes(),
                np.asarray(lines, dtype='<f4').tobytes(), tuple(low) + tuple(high), len(points), tuple(origin))
