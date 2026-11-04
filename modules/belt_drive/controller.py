"""A Qt-free JobManager operation factory; no thread or COM object is created."""

from dataclasses import dataclass
from .calculation import calculate, checkpoint
from .catalog.models import BeltCandidate
from .engineering.belt_selection import nearest_catalog_candidates
from .models import BeltDriveResult


@dataclass(frozen=True, slots=True)
class CalculationReport:
    result: BeltDriveResult
    candidates: tuple[BeltCandidate, ...] = ()


def calculation_job(specification, catalog=None, *, candidate_limit=5):
    """Pass the returned (events, stop) callable to existing JobManager.start."""
    def run(events, stop):
        checkpoint(stop)
        result = calculate(specification, stop=stop)
        candidates = nearest_catalog_candidates(specification, catalog, limit=candidate_limit, stop=stop) if catalog else ()
        checkpoint(stop)
        events.put(('belt_result', CalculationReport(result, candidates)))
    return run
