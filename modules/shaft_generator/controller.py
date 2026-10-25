"""Immutable job snapshots; invalid geometry cannot reach the CAD bridge."""

from .geometry import operation_plan
from .models import Project


def request(project, *, output_path='', verify_edit=False):
    plan = operation_plan(project)
    return dict(operation='create_shaft', project=project.to_dict(), plan=plan,
                output_path=str(output_path), verify_edit=bool(verify_edit))


def create(project, events, stop, *, output_path='', verify_edit=False):
    from .bridge import execute
    payload = request(project, output_path=output_path, verify_edit=verify_edit)
    if stop.is_set():
        events.put(('shaft_cancelled', None))
        return
    events.put(('shaft_phase', 'SOLIDWORKS bağlantısı ve yerel özellikler hazırlanıyor…'))
    result = execute(payload, stop=stop, on_status=lambda text:events.put(('shaft_phase',text)))
    events.put(('shaft_created', result))
