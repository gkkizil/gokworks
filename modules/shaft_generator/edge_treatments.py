"""Atomic end/shoulder edge treatments using the existing per-edge CAD contract."""

from copy import deepcopy
from dataclasses import dataclass, replace

from .models import Chamfer, Fillet, Project
from .validation import number, require_valid


@dataclass(frozen=True)
class Edge:
    stage_id: str
    side: str
    position: float
    radius: float


@dataclass(frozen=True)
class TreatmentBatch:
    project: Project
    added: int
    updated: int
    preserved: int
    edge_count: int
    straight_joints: int


def circular_edges(project):
    """Enumerate each real profile corner; equal-diameter joints have no edge.

    A shoulder's inner and outer circles are distinct corners. The two ends
    of a single stage therefore do not alias the adjacent stage's corners.
    Channels, bore mouths and the shaft axis are outside this command's scope.
    """
    require_valid(replace(project, operations=[]))
    edges = []
    boundaries = project.boundaries
    for index,stage in enumerate(project.stages):
        for side,neighbor,position in (('left',index-1,boundaries[index]),
                                       ('right',index+1,boundaries[index+1])):
            if 0 <= neighbor < len(project.stages) and project.stages[neighbor].diameter == stage.diameter:
                continue
            edges.append(Edge(stage.id,side,position,stage.diameter/2))
    return edges


def plan_treatments(project, kind, size, *, replace_existing=False):
    """Return a validated draft; failure never mutates the caller's project.

    The UI commits the returned draft once, as one undoable batch. No CAD
    connection, schema change or new native feature type is required.
    """
    if kind not in ('chamfer','fillet'):
        raise ValueError('Toplu işlem türü pah veya radyüs olmalı.')
    if not number(size):
        raise ValueError('Pah/radyüs ölçüsü 0,00001–1.000.000 mm arasında ve sonlu olmalı.')
    if type(replace_existing) is not bool:
        raise ValueError('Mevcut kenarları değiştirme seçimi geçersiz.')
    edges = circular_edges(project)
    draft = deepcopy(project)
    treatments = (Chamfer,Fillet)
    old = {(op.stage_id,op.edge):op for op in draft.operations if isinstance(op,treatments)}
    if replace_existing:
        draft.operations = [op for op in draft.operations if not isinstance(op,treatments)]
    added = updated = preserved = 0
    for edge in edges:
        previous = old.get((edge.stage_id,edge.side))
        if previous is not None and not replace_existing:
            preserved += 1
            continue
        values = dict(stage_id=edge.stage_id,edge=edge.side)
        if previous is not None: values['id'] = previous.id
        operation = Chamfer(**values,distance=size) if kind=='chamfer' else Fillet(**values,radius=size)
        draft.operations.append(operation)
        if previous is None: added += 1
        else: updated += 1
    # Reuse all existing checks, including channels, shared shoulder space,
    # bore walls, cosmetic thread land and the 200-operation ceiling.
    require_valid(draft)
    from .geometry import check_profile, treated_profile
    check_profile(treated_profile(draft))
    straight_joints = sum(a.diameter==b.diameter for a,b in zip(project.stages,project.stages[1:]))
    return TreatmentBatch(draft,added,updated,preserved,len(edges),straight_joints)
