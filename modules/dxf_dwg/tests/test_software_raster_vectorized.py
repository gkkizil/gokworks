"""CPU 3D preview: the vectorized rasterizer matches a plain per-triangle z-buffer.

Reported 2026-11-03: rotating the 3D preview stuttered where OpenGL is not
available ('yazılımsal görüntüleyici etkin'). The CPU path rasterized one
triangle per Python iteration (~300-400 ms per frame for ~3000 triangles).
It is now batched with numpy; this test keeps it pixel-equivalent to the
straightforward algorithm it replaced.
"""

import math
import random
import threading

import numpy as np
import pytest
from PySide6.QtGui import QImage

from modules.dxf_dwg.preview import viewer
from modules.dxf_dwg.preview.models import Mesh


def _mesh(seed=7, count=900):
    rng = random.Random(seed)
    triangles = []
    for _ in range(count):                         # mixed sizes: specks, slivers, large faces
        cx, cy, cz = (rng.uniform(-40, 40) for _ in range(3))
        size = rng.choice([0.3, 2, 8, 30, 70])
        triangles.append([(cx + rng.uniform(-size, size), cy + rng.uniform(-size, size),
                           cz + rng.uniform(-size, size)) for _ in range(3)])
    points = np.array(triangles, dtype='<f4')
    normal = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    normal /= np.linalg.norm(normal, axis=1)[:, None] + 1e-12
    normals = np.repeat(normal, 3, axis=0).astype('<f4')
    edges = points[:200][:, [0, 1, 1, 2, 2, 0]].reshape(-1, 3).astype('<f4')
    flat = points.reshape(-1, 3)
    return Mesh(points.tobytes(), normals.tobytes(), edges.tobytes(),
                tuple(flat.min(axis=0)) + tuple(flat.max(axis=0)), len(points))


def _reference(mesh, width, height, state, background):
    """The original per-triangle algorithm, kept here as the oracle."""
    vertices, normals, edges = viewer.normalized(mesh)
    view, mvp = viewer.matrices(state, width / height)

    def project(points):
        clip = np.c_[points, np.ones(len(points))] @ mvp.T
        return clip[:, :3] / clip[:, 3, None]
    p = project(vertices)
    p[:, 0] = (p[:, 0] + 1) * .5 * (width - 1)
    p[:, 1] = (1 - p[:, 1]) * .5 * (height - 1)
    pixels = np.empty((height, width, 3), dtype=np.uint8); pixels[:] = background
    depth = np.full((height, width), np.inf)
    light = np.array([.25, .45, 1.]); light /= np.linalg.norm(light)
    shade = .42 + .58 * np.abs((normals[::3] @ view[:3, :3].T) @ light)
    for i, (a, b, c) in enumerate(p.reshape((-1, 3, 3))):
        tri = np.array([a, b, c])
        if np.max(tri[:, 2]) < -1 or np.min(tri[:, 2]) > 1:
            continue
        x0, y0 = np.floor(tri[:, :2].min(axis=0)).astype(int)
        x1, y1 = np.ceil(tri[:, :2].max(axis=0)).astype(int)
        x0, x1, y0, y1 = max(0, x0), min(width - 1, x1), max(0, y0), min(height - 1, y1)
        if x0 > x1 or y0 > y1:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-10:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / den
        v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / den
        w = 1 - u - v
        z = u * a[2] + v * b[2] + w * c[2]
        old = depth[y0:y1 + 1, x0:x1 + 1]
        mask = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8) & (z < old) & (z >= -1) & (z <= 1)
        old[mask] = z[mask]
        pixels[y0:y1 + 1, x0:x1 + 1][mask] = np.array([155, 172, 188]) * shade[i]
    return pixels


def _array(image):
    image = image.convertToFormat(QImage.Format_RGB888)
    data = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return data[:, :image.width() * 3].reshape(image.height(), image.width(), 3).astype(int)


@pytest.mark.parametrize('state', [(-45, math.degrees(math.asin(1 / math.sqrt(3))), 1, 0, 0, False, False),
                                   (30, -20, 2.5, .1, -.05, True, False),
                                   (0, 90, 4, 0, 0, False, False)], ids=['iso', 'perspective', 'top_zoomed'])
def test_vectorized_frame_matches_per_triangle_reference(state):
    mesh = _mesh()
    background = (26, 27, 30)
    fast = _array(viewer.raster(mesh, 320, 240, state, threading.Event(), background))
    slow = _reference(mesh, 320, 240, state, background).astype(int)
    differing = (np.abs(fast - slow).sum(axis=2) > 3).mean()
    assert differing < 0.002            # float32 sampling may flip isolated boundary pixels only
    assert (fast != background).any(axis=2).sum() > 1000


def test_cancelled_render_returns_none():
    stop = threading.Event(); stop.set()
    assert viewer.raster(_mesh(), 320, 240, (0, 0, 1, 0, 0, False, True), stop) is None
