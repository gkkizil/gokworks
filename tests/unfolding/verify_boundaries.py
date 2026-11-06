"""Probe every nonzero source length at zero; report uncaught exceptions separately.

An explicit validation/geometry error is acceptable in this crash-resistance
probe. It does not prove that every accepted/rejected limit is physically right.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time

from core.unfolding import UnfoldService, UnfoldRequest
from core.unfolding.models import ENGINE_VERSION
from core.unfolding.source_models import inventory
from .verify_source_outputs import implementation_digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    data=json.loads((root/'docs/unfolding/examples/source_models.json').read_text(encoding='utf-8'))
    examples={e['source_id']:e['request'] for e in data['models']}
    service=UnfoldService(0);rows=[];started=time.monotonic();digest=implementation_digest(root)
    for index,model in enumerate(inventory()['models'],1):
        request=UnfoldRequest(**examples[model['source_id']])
        for field in model['fields']:
            if field['kind']!='length' or request.parameters[field['id']]==0:continue
            parameters=dict(request.parameters);parameters[field['id']]=0.
            row=dict(source_id=model['source_id'],parameter=field['id'],value=0.)
            try:
                result=service.calculate(replace(request,parameters=parameters))
                row['status']=result.status
            except Exception as exc:
                row.update(status='uncaught_exception',exception=type(exc).__name__,message=str(exc))
                print(json.dumps(row,ensure_ascii=False),flush=True)
            rows.append(row)
        if index%25==0:print(f'{index}/191; {len(rows)} cases',flush=True)
    uncaught=[r for r in rows if r['status']=='uncaught_exception']
    unchanged=digest==implementation_digest(root)
    report=dict(scope=__doc__,engine_version=ENGINE_VERSION,implementation_sha256=digest,
        implementation_unchanged=unchanged,cases=len(rows),uncaught=uncaught,rows=rows,
        elapsed_seconds=time.monotonic()-started,complete=unchanged and not uncaught)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"DONE {len(rows)}; uncaught={len(uncaught)}; unchanged={unchanged}",flush=True)
    return 0 if report['complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
