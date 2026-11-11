"""Immutable, COM/Qt-free snapshots; lengths mm, angles degrees, directions ±1."""
from dataclasses import dataclass, replace
from math import hypot, isfinite, radians

Point = tuple[float, float]


@dataclass(frozen=True)
class Region:
    outer: tuple[Point, ...]
    holes: tuple[tuple[Point, ...], ...] = ()

    def polygon(self):
        from shapely.geometry import Polygon
        return Polygon(self.outer, self.holes)

    @classmethod
    def from_polygon(cls, polygon):
        from shapely.geometry.polygon import orient
        p = orient(polygon)
        if p.is_empty or not p.is_valid or p.area <= 1e-8:
            raise ValueError('Kontur kapalı, geçerli ve pozitif alanlı olmalı.')
        return cls(tuple(p.exterior.coords)[:-1], tuple(tuple(r.coords)[:-1] for r in p.interiors))


@dataclass(frozen=True)
class Flange:
    id: str
    region: Region


@dataclass(frozen=True)
class Bend:
    id: str
    parent: str
    child: str
    start: Point  # tangent at stationary side; left normal points to child
    end: Point
    width: float  # measured developed bend-zone width, never guessed
    inside_angle: float
    radius: float
    direction: int
    region: Region
    provenance: str = 'CAD'
    label: str = ''

    @property
    def title(self):
        return self.label or self.id

    @property
    def turn(self):
        return 180.0 - self.inside_angle

    @property
    def length(self):
        return hypot(self.end[0]-self.start[0], self.end[1]-self.start[1])


@dataclass(frozen=True)
class Part:
    name: str
    configuration: str
    material: str
    thickness: float
    root: str
    flanges: tuple[Flange, ...]
    bends: tuple[Bend, ...]
    fixed_face: str
    source: str
    demo: bool = False
    contour_tolerance: float = .02

    def validate(self):
        from shapely.ops import unary_union
        numbers = [self.thickness, self.contour_tolerance]
        ids = {p.id for p in self.flanges}
        if not self.name or not self.bends or self.thickness <= 0 or self.contour_tolerance <= 0 or self.root not in ids or len(ids) != len(self.flanges):
            raise ValueError('Parça adı, kalınlık veya sabit flanş geçersiz.')
        seen = {self.root}
        if len({b.id for b in self.bends}) != len(self.bends) or len(self.bends) != len(ids)-1:
            raise ValueError('Kapalı/döngülü veya ayrık flanş grafiği desteklenmiyor.')
        pending = list(self.bends)
        while pending:
            ready = [b for b in pending if b.parent in seen]
            if not ready:
                raise ValueError('Flanş grafiği sabit yüze bağlı değil.')
            for b in ready:
                if b.child in seen or b.child not in ids:
                    raise ValueError(f'{b.id}: döngülü flanş bağlantısı.')
                if not 0 < b.inside_angle < 180 or b.radius <= 0 or b.width <= 0 or b.length <= 0 or b.direction not in (-1, 1):
                    raise ValueError(f'{b.id}: açı, iç R, yön veya eksen geçersiz.')
                numbers.extend((*b.start, *b.end, b.width, b.inside_angle, b.radius))
                # A developed width incompatible with constant-thickness bending
                # cannot be repaired by inventing a neutral-axis factor.
                neutral = b.width/radians(b.turn)
                if not b.radius-1e-4 <= neutral <= b.radius+self.thickness+1e-4:
                    raise ValueError(f'{b.id}: açınım boyu/iç R/kalınlık birbiriyle tutarsız.')
                seen.add(b.child); pending.remove(b)
        if not all(isfinite(v) for v in numbers):
            raise ValueError('Parça sonlu olmayan ölçü içeriyor.')
        regions = [f.region.polygon() for f in self.flanges] + [b.region.polygon() for b in self.bends]
        for region in regions:
            Region.from_polygon(region)
        union = unary_union(regions)
        if union.geom_type != 'Polygon' or abs(sum(p.area for p in regions)-union.area) > .01:
            raise ValueError('Flanş ve büküm bölgeleri ayrık veya üst üste geliyor.')
        return self


@dataclass(frozen=True)
class Channel:
    id: str
    opening: float
    angle: float
    center: Point  # section y,z in mm
    shoulder_radius: float | None = None
    rotation: float = 0.  # section rotation about the station X axis, degrees


@dataclass(frozen=True)
class Segment:
    start: float
    length: float


@dataclass(frozen=True)
class Mount:
    tool_interface: str
    holder_interface: str
    adapter_from: str = ''
    adapter_to: str = ''

    @property
    def compatible(self):
        if not self.tool_interface or not self.holder_interface:
            return False
        generic = {'wila', 'european', 'promecam', 'european/promecam', 'american', 'amada'}
        if any(value.strip().casefold().replace(' ', '') in generic for value in (self.tool_interface, self.holder_interface)):
            return False
        if self.adapter_from or self.adapter_to:
            return self.tool_interface == self.adapter_from and self.adapter_to == self.holder_interface
        return self.tool_interface == self.holder_interface


@dataclass(frozen=True)
class Tool:
    id: str
    maker: str
    code: str
    kind: str
    family: str
    height: float
    mount_reference: Point
    section: Region | None
    source: str
    segments: tuple[Segment, ...]
    mount: Mount
    tip_angle: float | None = None
    tip_radius: float | None = None
    tip: Point | None = None
    channels: tuple[Channel, ...] = ()
    line_load: float | None = None
    line_load_unit: str = ''
    # Native DXF entities as text preserve exact lines/arcs for B-Rep creation.
    section_dxf: str = ''
    contour_index: int = 0
    holder_section: Region | None = None
    holder_source: str = ''
    demo: bool = False
    holder_segments: tuple[Segment, ...] = ()
    holder_dxf: str = ''
    catalog_url: str = ''
    catalog_note: str = ''
    catalog_segments: tuple[tuple[float, int], ...] = ()

    def validate(self):
        numbers = [self.height, *self.mount_reference]
        numbers += [v for v in (self.tip_radius, self.tip_angle, self.line_load) if v is not None]
        if self.tip is not None:
            numbers.extend(self.tip)
        for segment in (*self.segments, *self.holder_segments):
            numbers.extend((segment.start, segment.length))
            if segment.length <= 0 or not isfinite(segment.start+segment.length):
                raise ValueError(self.code+': sonlu segment uçları ve pozitif boy gerekli.')
        for channel in self.channels:
            numbers.extend((channel.opening, channel.angle, channel.rotation, *channel.center))
            if channel.shoulder_radius is not None:
                numbers.append(channel.shoulder_radius)
                if channel.shoulder_radius < 0:
                    raise ValueError(self.code+': omuz R negatif olamaz.')
            if channel.opening <= 0 or not 0 < channel.angle < 180:
                raise ValueError(self.code+': V kanalı ölçüleri geçersiz.')
        for length, quantity in self.catalog_segments:
            numbers.append(length)
            if length <= 0 or type(quantity) is not int or quantity < 0:
                raise ValueError(self.code+': katalog segment boyu/adedi geçersiz.')
        if not all(isfinite(v) for v in numbers) or self.height <= 0:
            raise ValueError(self.code+': sonlu ölçüler ve pozitif çalışma yüksekliği gerekli.')
        if not self.id or not self.code or self.kind not in ('punch', 'die'):
            raise ValueError('Takım kimliği, kodu veya tipi geçersiz.')
        if self.tip_radius is not None and self.tip_radius < 0:
            raise ValueError(self.code+': uç R negatif olamaz.')
        if self.tip_angle is not None and not 0 < self.tip_angle < 180:
            raise ValueError(self.code+': uç açısı geçersiz.')
        if self.line_load is not None and (self.line_load <= 0 or not self.line_load_unit.strip()):
            raise ValueError(self.code+': hat yükü değeri ve özgün birimi birlikte gerekli.')
        if self.section is not None:
            Region.from_polygon(self.section.polygon())
        if self.holder_section is not None:
            Region.from_polygon(self.holder_section.polygon())
        return self


@dataclass(frozen=True)
class Step:
    bend: str
    punch: str = 'demo-punch'
    die: str = 'demo-die'
    channel: str = 'V16'
    reverse: bool = False
    fixed_side: str = 'parent'
    orientation: int = 0  # 0/180 about station vertical; recorded reposition
    punch_segments: tuple[Segment, ...] | None = None
    die_segments: tuple[Segment, ...] | None = None
    target: float | None = None  # planned inside angle, degrees; None = the CAD angle


@dataclass(frozen=True)
class Plan:
    part: Part
    steps: tuple[Step, ...]
    tools: tuple[Tool, ...]
    revision: int = 0

    def tool(self, id):
        return next(t for t in self.tools if t.id == id)

    def changed(self, **kwargs):
        return replace(self, revision=self.revision+1, **kwargs)

    def validate(self):
        self.part.validate()
        if len(self.steps) != len(self.part.bends) or {s.bend for s in self.steps} != {b.id for b in self.part.bends}:
            raise ValueError('Plan her bükümü tam bir kez içermeli.')
        if len({t.id for t in self.tools}) != len(self.tools):
            raise ValueError('Takım kimlikleri benzersiz olmalı.')
        for tool in self.tools:
            tool.validate()
        for step in self.steps:
            if step.fixed_side not in ('parent', 'child') or step.orientation not in (0, 180):
                raise ValueError('Desteklenmeyen tutuş yönü.')
            for segments in (step.punch_segments, step.die_segments):
                for segment in segments or ():
                    try:
                        valid = (isinstance(segment, Segment)
                                 and all(not isinstance(v, bool) and isfinite(v) for v in (segment.start, segment.length))
                                 and isfinite(segment.start+segment.length)
                                 and segment.length > 0)
                    except (TypeError, ValueError, OverflowError):
                        valid = False
                    if not valid:
                        raise ValueError('Adım segmentleri sonlu başlangıç ve pozitif sonlu boy içermeli.')
            if self.tool(step.punch).kind != 'punch' or self.tool(step.die).kind != 'die':
                raise ValueError('Üst ve alt takım tipleri yanlış.')
            if step.target is not None:
                bend = self.bend(step.bend)
                if not 1 <= step.target <= 179:
                    raise ValueError(f'{bend.title}: hedef iç açı 1° ile 179° arasında olmalı.')
                # The CAD bend zone (measured width, neutral factor) stays; a different
                # target angle changes the radius it implies. It must stay positive.
                k = (bend.width/radians(bend.turn)-bend.radius)/self.part.thickness
                if bend.width/radians(180-step.target)-k*self.part.thickness <= 0:
                    raise ValueError(f'{bend.title}: {step.target:g}° hedef açı bu büküm bölgesiyle oluşturulamaz (iç R sıfırın altına düşer).')
        return self

    def bend(self, id):
        return next(b for b in self.part.bends if b.id == id)

    def inside(self, step):
        """Planned inside angle of a step: its target, else the CAD angle."""
        return self.bend(step.bend).inside_angle if step.target is None else step.target

    def turn(self, step):
        return 180.0-self.inside(step)
