from core.unfolding import UnfoldService,UnfoldRequest


def request_for(shape='cylinder',variant='straight',**changes):
    s=UnfoldService();schema=s.get_schema(shape,variant)
    params={f.id:int(f.default) if f.type=='integer' else f.default for f in schema.fields}
    params.update(changes.pop('parameters',{}))
    return UnfoldRequest(shape_id=shape,variant_id=variant,parameters=params,**changes)


def calculate(shape='cylinder',variant='straight',**changes):
    r=UnfoldService().calculate(request_for(shape,variant,**changes))
    assert r.status=='success',r.errors
    return r
