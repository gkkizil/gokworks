"""Selectable nesting engines, sharing the same project and result contracts."""


def nest(project, *, stop=None, progress=None):
    project.validate()
    if project.options.engine == 'Sparrow':
        from modules.nesting.sparrow import nest as solve
    else:
        from modules.nesting.engine import nest as solve
    return solve(project, stop=stop, progress=progress)
