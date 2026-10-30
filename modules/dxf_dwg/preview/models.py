"""Immutable, bounded plain data across the STA / Qt boundary (never COM)."""

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    source: str
    configuration: str = ''
    body_ref: str = ''
    output: str = ''
    output_status: str = ''
    source_stamp: tuple = ()
    update_stamp: int | None = None
    quantity: int | None = None
    bend_lines: bool = False
    flat_ref: str = ''
    body_name: str = ''
    thickness_mm: float | None = None


@dataclass(frozen=True)
class Mesh:
    positions: bytes  # float32 triangle soup, mm relative to origin, 3 coordinates per vertex
    normals: bytes   # float32, per vertex
    edges: bytes     # float32 line segments, mm
    bounds: tuple
    triangles: int
    origin: tuple = (0., 0., 0.)

    @property
    def size(self):
        return len(self.positions) + len(self.normals) + len(self.edges)


@dataclass(frozen=True)
class Stroke:
    points: tuple
    color: str
    layer: str
    bend: bool = False


@dataclass(frozen=True)
class Flat:
    strokes: tuple
    bounds: tuple
    description: str
    cut_length: float | None
    warnings: tuple = ()


@dataclass(frozen=True)
class Payload:
    source: str
    configuration: str
    mesh: Mesh
    flat: Flat | None
    info: tuple
    revision: tuple
    warnings: tuple = ()
    cached: bool = False


class MeshCache:
    """Worker-owned LRU. Keys include live revision; no path-only cache hit."""
    def __init__(self, maximum=32 * 1024 * 1024, entries=8):
        self.maximum, self.entries = maximum, entries
        self.items = OrderedDict()
        self.size = 0

    def get(self, key):
        if key not in self.items:
            return None
        self.items.move_to_end(key)
        return self.items[key]

    def put(self, key, mesh):
        if key in self.items:
            self.size -= self.items.pop(key).size
        if mesh.size > self.maximum:
            return
        self.items[key] = mesh
        self.size += mesh.size
        while self.size > self.maximum or len(self.items) > self.entries:
            self.size -= self.items.popitem(last=False)[1].size

    def clear(self):
        self.items.clear()
        self.size = 0
