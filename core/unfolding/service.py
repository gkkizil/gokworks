"""Stable, bounded-cache synchronous service for the application's job manager."""
from collections import OrderedDict
from dataclasses import replace
import hashlib
import importlib.util
import json
from threading import RLock
from .models import ENGINE_VERSION,UnfoldResult,FrozenMap,Issue,to_data
from .registry import DEFINITIONS,definition
from .validation import validate
from .shapes.common import check_cancel,UnfoldCancelled


def input_hash(normalized):
    data=to_data(normalized)
    data.pop('request_id',None);data.pop('revision',None)
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


class UnfoldService:
    def __init__(self,cache_size=16):
        if type(cache_size) is not int or not 0<=cache_size<=64:raise ValueError('Cache boyutu 0–64 olmalı.')
        self._cache_size=cache_size;self._cache=OrderedDict();self._lock=RLock()

    def list_shapes(self):return tuple(d.summary for d in DEFINITIONS.values())
    def list_source_models(self):
        from .source_models import inventory
        from .shapes.source_dispatch import supported,method_for
        return tuple(FrozenMap(dict(m,calculation_available=supported(m),calculation_method=method_for(m) if supported(m) else None))
                     for m in inventory()['models'])
    def get_schema(self,shape_id,variant_id):return definition(shape_id).schema(variant_id)
    def validate(self,request):return validate(request)

    def calculate(self,request,cancel_token=None):
        check_cancel(cancel_token);report=validate(request)
        if not report.valid:
            return UnfoldResult(getattr(request,'request_id',''),getattr(request,'revision',0),'',ENGINE_VERSION,
                 FrozenMap(),'','error',errors=report.errors,capabilities=FrozenMap())
        n=report.normalized_inputs;digest=input_hash(n);key=(ENGINE_VERSION,digest)
        with self._lock:
            cached=self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key);check_cancel(cancel_token)
                return replace(cached,request_id=request.request_id,revision=request.revision,normalized_inputs=n,
                    parts=tuple(replace(p,assembly_id=request.request_id) for p in cached.parts))
        d=definition(request.shape_id)
        try:
            parts,quality=d.build(n,request.material,request.development_options,cancel_token)
            check_cancel(cancel_token)
            if not parts:raise ValueError('Hesap parça üretmedi.')
            from .quality import inspect_parts
            quality.update(inspect_parts(parts,request.development_options.geometry_tolerance_mm))
            if quality.get('seam_closure_error_mm',0.)>request.development_options.geometry_tolerance_mm:
                raise ValueError('Montaj dikiş kapanma hatası toleransı aşıyor.')
            area=sum(p.metrics.cutting_area_mm2*p.quantity for p in parts)
            masses=[p.metrics.mass_kg*p.quantity for p in parts if p.metrics.mass_kg is not None]
            costs=[p.metrics.material_cost*p.quantity for p in parts if p.metrics.material_cost is not None]
            metrics=FrozenMap(dict(net_area_mm2=sum(p.metrics.net_area_mm2*p.quantity for p in parts),cutting_area_mm2=area,
                rectangle_area_mm2=sum(p.metrics.rectangle_area_mm2*p.quantity for p in parts),
                cutting_length_mm=sum(p.metrics.cutting_length_mm*p.quantity for p in parts),
                mass_kg=sum(masses) if len(masses)==len(parts) else None,
                material_cost=sum(costs) if len(costs)==len(parts) else None,part_count=sum(p.quantity for p in parts),
                units=dict(length='mm',area='mm2',mass='kg',currency=request.material.currency)))
            surface=all(p.surface_patches for p in parts) and request.joint_options.kind=='butt'
            # Trimmed cylinders need a separate verified B-Rep implementation; never claim it ready.
            surface=surface and all(s.kind!='cylinder' or s.data['upper']==s.data['lower']==0 for p in parts for s in p.surface_patches)
            capabilities=FrozenMap(dict(dxf=importlib.util.find_spec('ezdxf') is not None,
                pdf=importlib.util.find_spec('PySide6') is not None,step_surface=surface and importlib.util.find_spec('OCP') is not None,
                step_solid=False,nesting=True,zip=True,json=True,production_process_verified=False))
            warnings=report.warnings
            if quality.get('approximation'):
                warnings+=(Issue('APPROXIMATION',str(quality['approximation'])+'; düzgün yüzeyin gerinimsiz açınımı veya şekillendirme onayı değildir.','WARNING'),)
            result=UnfoldResult(request.request_id,request.revision,digest,ENGINE_VERSION,n,quality.get('calculation_method',d.summary.method),'success',parts,metrics,
                               warnings,capabilities=capabilities,quality_metrics=FrozenMap(quality))
            with self._lock:
                if self._cache_size:
                    self._cache[key]=result
                    while len(self._cache)>self._cache_size:self._cache.popitem(last=False)
            return result
        except UnfoldCancelled:raise
        except (ValueError,ArithmeticError) as exc:
            return UnfoldResult(request.request_id,request.revision,digest,ENGINE_VERSION,n,d.summary.method,'error',
                               warnings=report.warnings,errors=(Issue('GEOMETRY_INVALID',str(exc)),))

    def export(self,result,export_options,*,cancel_token=None):
        from .exporting import export_result
        return export_result(result,export_options,cancel_token=cancel_token)

    def save_project(self,project,path,*,overwrite=False):
        from .storage import save_project
        return save_project(project,path,overwrite=overwrite)

    def export_project(self,project,export_options,*,cancel_token=None):
        from .batch import export_project
        return export_project(self,project,export_options,cancel_token=cancel_token)

    def load_project(self,path):
        from .storage import load_project
        return load_project(path)
