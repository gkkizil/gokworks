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
    flat_pattern: str = ''
    cut_list: str = ''


@dataclass(frozen=True)
class Mesh:
    positions: bytes  # float32 triangle soup, mm relative to origin, 3 coordinates per vertex
    normals: bytes   # float32, per vertex
    edges: bytes     # float32 line segments, mm
    bounds: tuple
    triangles: int
    origin: tuple = (0., 0., 0.)
    colours: bytes = b''  # optional uint8 RGB per triangle; empty = the viewer's single base colour

    @property
    def size(self):
        return len(self.positions) + len(self.normals) + len(self.edges) + len(self.colours)


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

    @property
    def size(self):
        return (1024 + len(self.description)*4 + sum(128 + len(w)*4 for w in self.warnings)
                + sum(512 + len(s.points)*192 + 4*(len(s.layer)+len(s.color)) for s in self.strokes))


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
    timings: tuple = ()


class MeshCache:
    """Worker-owned LRU. Keys include live revision; no path-only cache hit."""
    def __init__(self, maximum=32 * 1024 * 1024, entries=16):
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

    def get_flat(self, key):
        return self.get(('flat', key))

    def put_flat(self, key, flat):
        self.put(('flat', key), flat)

    def clear(self):
        self.items.clear()
        self.size = 0


class PreviewCache:
    """GUI-owned snapshots, keyed by request and source/output file revisions.

    Includes folded mesh AND flat geometry. Memory charges conservatively
    include Python point/metadata overhead, rather than just mesh byte arrays.
    Snapshots are visual history; production review still validates live CAD.
    """
    def __init__(self, maximum=64 * 1024 * 1024, entries=64):
        self.maximum, self.entries = maximum, entries
        self.items = OrderedDict()
        self.size = 0

    def get(self, key):
        if key not in self.items:return None
        self.items.move_to_end(key)
        return self.items[key][0]

    def put(self, key, payload):
        if not payload.flat or not payload.flat.strokes:return
        size = payload.mesh.size + 1024
        size += sum(512 + len(s.points)*192 + 4*(len(s.layer)+len(s.color)) for s in payload.flat.strokes)
        size += sum(256 + 4*(len(str(k))+len(str(v))) for k,v in payload.info)
        size += sum(128 + len(w)*4 for w in (*payload.warnings,*payload.flat.warnings))
        if key in self.items:self.size -= self.items.pop(key)[1]
        if size>self.maximum:return
        self.items[key] = (payload,size);self.size += size
        while self.size>self.maximum or len(self.items)>self.entries:
            self.size -= self.items.popitem(last=False)[1][1]

    def invalidate_source(self, source):
        for key in list(self.items):
            if key[0].source==source:self.size -= self.items.pop(key)[1]

    def clear(self):
        self.items.clear();self.size = 0
