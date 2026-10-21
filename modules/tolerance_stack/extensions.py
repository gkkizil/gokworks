"""Future verified geometry adapters must return explicit 1D relations.

No STEP/OCC dependency and no claim of 2D/3D GD&T evaluation in this release.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FaceReference:
    source: str
    persistent_id: str
    coordinate_system: str
    normal: tuple


class GeometryAdapter(Protocol):
    def linear_relation(self, start: FaceReference, end: FaceReference, axis: tuple):
        """Return a documented, validated projection, or raise NotImplementedError."""
        ...
