"""Private headless subprocess. Never imports Qt, COM or an external service."""

import json
from pathlib import Path
from .serialization import from_dict


def run_worker(request_path):
    request_path=Path(request_path)
    folder=request_path.parent
    try:
        if request_path.stat().st_size>32000:
            raise ValueError('Dişli işlem isteği çok büyük.')
        request=json.loads(request_path.read_text(encoding='utf-8'))
        if set(request)!={'specification','mode','target','construction'}:
            raise ValueError('Dişli işlem sözleşmesi geçersiz.')
        spec=from_dict(request['specification']);mode=request['mode'];target=request['target']
        if mode=='check':
            from dataclasses import asdict
            from .geometry import verify_mesh
            result=asdict(verify_mesh(spec))
        elif mode=='mesh':
            import numpy as np
            from .cad import placed_gears,triangulate,compound,shape_stats
            from .geometry import verify_mesh
            verify_mesh(spec)
            shapes=placed_gears(spec,target)
            points=np.asarray(triangulate(shapes,min(.12,spec.pinion.module_mm*.05)),dtype='float64')
            np.save(folder/'mesh.npy',points,allow_pickle=False)
            result=dict(mode='mesh',**shape_stats(compound(shapes)))
        elif mode in ('dxf','step'):
            from .export import export_cad
            result=export_cad(spec,folder/('model.'+mode),target=target,construction=request['construction'])
        else:
            raise ValueError('Bilinmeyen dişli işlemi.')
        response=dict(ok=True,result=result)
    except Exception as error:
        response=dict(ok=False,error=str(error),error_type=type(error).__name__)
    (folder/'result.json').write_text(json.dumps(response,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return 0 if response['ok'] else 1
