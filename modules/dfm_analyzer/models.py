"""DFM result contract: plain data, no Qt, no CAD. Lengths are millimetres.

A finding always points at real geometry (``marks``) so the viewer and the
report show exactly what was measured. A rule that could not be evaluated is
reported as NOT_EVALUATED, never as passed.
"""

from dataclasses import dataclass, field, asdict
import json

ERROR, WARNING, INFO = 'ERROR', 'WARNING', 'INFO'
SEVERITIES = (ERROR, WARNING, INFO)
PASSED, FAILED, NOT_EVALUATED = 'PASSED', 'FAILED', 'NOT_EVALUATED'
SEVERITY_TITLES = {ERROR: 'Hata', WARNING: 'Uyarı', INFO: 'Bilgi'}
STATUS_TITLES = {PASSED: 'Geçti', FAILED: 'Bulgu var', NOT_EVALUATED: 'Değerlendirilemedi'}
RESULT_SCHEMA = 'gokworks.dfm_result'
RESULT_VERSION = 1


@dataclass
class Mark:
    """Geometry to highlight, in drawing millimetres.

    kind: 'point' (one point), 'line' (two points: a measured distance),
    'path' (an open or closed polyline) or 'area' (a closed outline).
    """
    kind: str
    points: list
    label: str = ''


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    process: str
    severity: str
    message: str
    suggestion: str
    measured: float | None = None
    limit: float | None = None
    unit: str = 'mm'
    entities: list = field(default_factory=list)     # DXF handles involved
    marks: list = field(default_factory=list)        # [Mark]
    part: str = ''

    @property
    def difference(self):
        if self.measured is None or self.limit is None:
            return None
        return self.limit - self.measured

    def bounds(self):
        points = [p for m in self.marks for p in m.points]
        if not points:
            return None
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass
class RuleOutcome:
    rule_id: str
    rule_name: str
    process: str
    status: str                       # PASSED / FAILED / NOT_EVALUATED
    limit: float | None = None
    unit: str = 'mm'
    reason: str = ''                  # why NOT_EVALUATED, or the checked scope
    reference: str = ''
    assumptions: str = ''
    findings: int = 0


@dataclass
class Drawing:
    """Geometry as read: polylines in mm, with the entity they came from."""
    contours: list                    # [dict(handle, kind, layer, points, closed, circle)]
    unit: str
    source_unit: str
    bounds: tuple | None
    ignored: list = field(default_factory=list)          # [(kind, layer, reason)]
    unsupported: list = field(default_factory=list)      # [(kind, layer, count)]


@dataclass
class AnalysisResult:
    source: str
    sha256: str
    analysed_at: str
    process: str
    material: str
    thickness_mm: float | None
    profile_id: str
    profile_name: str
    profile_version: str
    profile_verified: bool
    unit: str
    outcomes: list = field(default_factory=list)          # [RuleOutcome]
    findings: list = field(default_factory=list)          # [Finding]
    parts: list = field(default_factory=list)             # [dict(name, outline, holes)] for the viewer
    contours: list = field(default_factory=list)          # raw paths for the viewer
    notes: list = field(default_factory=list)
    scope: str = ''

    def summary(self):
        counts = dict(rules=len(self.outcomes),
                      passed=sum(o.status == PASSED for o in self.outcomes),
                      failed=sum(o.status == FAILED for o in self.outcomes),
                      not_evaluated=sum(o.status == NOT_EVALUATED for o in self.outcomes))
        for severity in SEVERITIES:
            counts[severity.lower()] = sum(f.severity == severity for f in self.findings)
        return counts

    def to_dict(self):
        data = asdict(self)
        data['schema'], data['version'] = RESULT_SCHEMA, RESULT_VERSION
        data['summary'] = self.summary()
        return data

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1, allow_nan=False)

    @classmethod
    def from_dict(cls, data):
        if data.get('schema') != RESULT_SCHEMA or data.get('version') != RESULT_VERSION:
            raise ValueError('Bu dosya GOKWORKS DFM analiz sonucu (sürüm 1) değil.')
        data = {k: v for k, v in data.items() if k not in ('schema', 'version', 'summary')}
        data['outcomes'] = [RuleOutcome(**o) for o in data.get('outcomes', [])]
        data['findings'] = [Finding(**{**f, 'marks': [Mark(**m) for m in f.get('marks', [])]})
                            for f in data.get('findings', [])]
        return cls(**data)
