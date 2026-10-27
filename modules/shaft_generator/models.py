"""Millimetre-based project data with stable stage/operation identities."""

from dataclasses import asdict, dataclass, field, fields
import math
from uuid import uuid4


def identity():
    return uuid4().hex


@dataclass
class Stage:
    diameter: float = 30
    length: float = 40
    id: str = field(default_factory=identity)


@dataclass
class Groove:
    stage_id: str
    offset: float = 5
    width: float = 2
    depth: float = 1
    id: str = field(default_factory=identity)
    kind: str = field(default='groove', init=False)


@dataclass
class Keyway:
    """Closed obround pocket: overall length, end radius width/2, flat floor."""
    stage_id: str
    offset: float = 5
    length: float = 20
    width: float = 8
    depth: float = 3
    angle: float = 0
    id: str = field(default_factory=identity)
    kind: str = field(default='keyway', init=False)


@dataclass
class Chamfer:
    stage_id: str
    edge: str = 'left'
    distance: float = 1
    angle: float = 45
    id: str = field(default_factory=identity)
    kind: str = field(default='chamfer', init=False)


@dataclass
class Fillet:
    stage_id: str
    edge: str = 'right'
    radius: float = 1
    id: str = field(default_factory=identity)
    kind: str = field(default='fillet', init=False)


@dataclass
class Bore:
    """One coaxial flat-bottom hole, through the shaft or blind from an end."""
    diameter: float = 10
    depth: float = 20
    end_condition: str = 'through_all'
    entry: str = 'left'

    def interval(self, total_length):
        if self.end_condition == 'through_all':
            return 0., total_length
        return (0., self.depth) if self.entry == 'left' else (total_length-self.depth, total_length)


@dataclass
class CosmeticThread:
    stage_id: str
    edge: str = 'left'
    length: float = 20
    pitch: float = 1.5
    id: str = field(default_factory=identity)
    kind: str = field(default='cosmetic_thread', init=False)


OPERATION_TYPES = {c.__dataclass_fields__['kind'].default: c for c in (Groove, Keyway, Chamfer, Fillet, CosmeticThread)}


@dataclass
class Project:
    name: str = 'MIL_001'
    stages: list[Stage] = field(default_factory=lambda: [Stage(30, 40), Stage(45, 65), Stage(35, 50), Stage(25, 35)])
    operations: list[Groove | Keyway | Chamfer | Fillet | CosmeticThread] = field(default_factory=list)
    minimum_wall: float = .5
    bore: Bore | None = None

    @property
    def total_length(self):
        return math.fsum(stage.length for stage in self.stages)

    @property
    def maximum_diameter(self):
        return max((s.diameter for s in self.stages), default=0)

    def start(self, stage_id):
        index = next(i for i, s in enumerate(self.stages) if s.id == stage_id)
        return self.boundaries[index]

    @property
    def boundaries(self):
        """One cumulative coordinate definition for outlines, picks and plans."""
        return [math.fsum(s.length for s in self.stages[:i]) for i in range(len(self.stages)+1)]

    def end(self, stage_id):
        index = next(i for i, s in enumerate(self.stages) if s.id == stage_id)
        return self.boundaries[index+1]

    def stage(self, stage_id):
        return next(s for s in self.stages if s.id == stage_id)

    def thread_interval(self, operation):
        """Local interval on the full-diameter cylindrical land after end treatments."""
        stage = self.stage(operation.stage_id)
        trims = {'left': 0., 'right': 0.}
        for op in self.operations:
            if op.stage_id == stage.id and isinstance(op, (Chamfer, Fillet)) and op.edge in trims:
                size = op.distance if isinstance(op, Chamfer) else op.radius
                if type(size) in (int, float) and math.isfinite(size):
                    trims[op.edge] = max(trims[op.edge], size)
        start = trims['left'] if operation.edge == 'left' else stage.length-trims['right']-operation.length
        return start, start+operation.length

    def add_stage(self, after=None, *, copy=False):
        index = next((i for i, s in enumerate(self.stages) if s.id == after), len(self.stages) - 1)
        source = self.stages[index] if copy and self.stages else Stage()
        new = Stage(source.diameter, source.length)
        self.stages.insert(index + 1, new)
        return new.id

    def remove_stage(self, stage_id):
        if len(self.stages) <= 1:
            raise ValueError('En az bir kademe gerekli.')
        self.stages.remove(self.stage(stage_id))
        self.operations[:] = [op for op in self.operations if op.stage_id != stage_id]

    def move_stage(self, stage_id, direction):
        index = self.stages.index(self.stage(stage_id))
        target = index + direction
        if 0 <= target < len(self.stages):
            self.stages[index], self.stages[target] = self.stages[target], self.stages[index]

    def to_dict(self):
        values = asdict(self)
        extended = self.bore is not None or any(isinstance(op, CosmeticThread) for op in self.operations)
        if not extended:
            values.pop('bore')
        return dict(schema='gokworks.shaft', version=2 if extended else 1, units='mm', **values)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('schema') != 'gokworks.shaft' or type(data.get('version')) is not int or data['version'] not in (1,2) or data.get('units') != 'mm':
            raise ValueError('Desteklenmeyen mil projesi, sürüm veya ölçü birimi.')
        try:
            expected = {'schema', 'version', 'units', 'name', 'stages', 'operations', 'minimum_wall'}
            if data['version'] == 2:expected.add('bore')
            if set(data) != expected:
                raise ValueError('Bilinmeyen veya eksik proje alanı.')
            bore_data = data.get('bore')
            if bore_data is not None and (not isinstance(bore_data,dict) or set(bore_data) != {f.name for f in fields(Bore)}):
                raise ValueError('İç delik alanları eksik veya geçersiz.')
            bore = None if bore_data is None else Bore(**bore_data)
            if not isinstance(data['stages'], list) or not 1 <= len(data['stages']) <= 100:
                raise ValueError('1–100 kademe gerekli.')
            if not isinstance(data['operations'], list) or len(data['operations']) > 200:
                raise ValueError('En fazla 200 operasyon desteklenir.')
            if any(not isinstance(row,dict) or set(row) != {f.name for f in fields(Stage)} for row in data['stages']):
                raise ValueError('Kademe alanları eksik veya geçersiz.')
            stages = [Stage(**row) for row in data['stages']]
            operations = []
            for row in data['operations']:
                values = dict(row)
                constructor = OPERATION_TYPES[values.pop('kind')]
                if data['version'] == 1 and constructor is CosmeticThread:
                    raise ValueError('Kozmetik diş için proje sürümü 2 gerekli.')
                if set(row) != {f.name for f in fields(constructor)}:
                    raise ValueError('Operasyon alanları eksik veya geçersiz.')
                operations.append(constructor(**values))
            project = cls(data['name'], stages, operations, data['minimum_wall'], bore)
        except (KeyError, TypeError) as error:
            raise ValueError('Mil projesi alanları geçersiz veya eksik.') from error
        from .validation import require_valid
        require_valid(project)
        return project
