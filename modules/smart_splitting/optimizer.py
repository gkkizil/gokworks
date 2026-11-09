"""Bounded candidate search scored only by independently validated existing NFP results."""
import time

from shapely import union_all
from shapely.errors import GEOSException
from shapely.geometry import box

from modules.nesting.dxf_import import check_cancel
from modules.nesting.engine import nest
from modules.nesting.geometry import placed
from modules.nesting.validation import validate_result
from .adapter import to_project
from .models import CandidateResult, OptimizationResult, PROFILES
from .splitter import candidates, split


def metrics(project, result):
    keys=set((p.sheet_id,p.sheet_number) for p in result.placements)
    gross=sum(project.sheet(key[0]).width*project.sheet(key[0]).height for key in keys)
    net=sum(p.area*p.quantity for p in project.parts)
    # Defined remnant metric: largest connected free region; not a guaranteed
    # rectangular stock blank. Cut clearance is conservatively deducted.
    reusable=0.
    for key in keys:
        sheet=project.sheet(key[0]); margin=project.options.margin
        usable=box(margin,margin,sheet.width-margin,sheet.height-margin)
        occupied=union_all([placed(project.part(p.part_id),p).buffer(max(project.options.gap,project.options.kerf)/2)
                            for p in result.placements if (p.sheet_id,p.sheet_number)==key])
        remaining=usable.difference(occupied)
        regions=list(remaining.geoms) if remaining.geom_type=='MultiPolygon' else [remaining]
        reusable+=max((g.area for g in regions if g.geom_type=='Polygon'),default=0.)
    return len(keys),gross,100*(gross-net)/gross if gross else 0.,reusable


def fits(project):
    sheet=project.sheets[0]; o=project.options
    for part in project.parts:
        from shapely import affinity
        guard=2*(o.margin+part.geometry_error+o.kerf/2)
        if not any((lambda b:b[2]-b[0]+guard<=sheet.width+1e-7 and b[3]-b[1]+guard<=sheet.height+1e-7)(
                affinity.rotate(part.polygon,a,origin=(0,0)).bounds) for a in (o.angles if o.rotation else [0])):
            return False
    return True


def optimize(part, settings, *, stop=None, progress=None):
    settings.validate(); started=time.monotonic(); rows=[]; best=None; seen=set()
    maximum,_=PROFILES[settings.profile]
    for index,(label,trial,angles,mode) in enumerate(candidates(part,settings,stop),1):
        if stop is not None and stop.is_set(): break
        if progress: progress(index-1,maximum,label)
        tick=time.monotonic()
        try:
            solution=split(part,trial,angles=angles,mode=mode,stop=stop)
            signature=tuple(sorted(s.blank.normalize().wkb for s in solution.segments))
            if signature in seen:
                rows.append(CandidateResult(label,'Yinelenen aday atlandı',elapsed=time.monotonic()-tick)); continue
            seen.add(signature)
            project=to_project(solution)
            if not fits(project): raise ValueError('Segment izin verilen açılarda levhaya sığmıyor.')
            result=nest(project,stop=stop)
            if stop is not None and stop.is_set(): break
            if result.unplaced:
                raise ValueError(f'{len(result.unplaced)} segment süre/boyut sınırında yerleştirilemedi.')
            validate_result(project,result)
            sheets,gross,waste,reusable=metrics(project,result)
            row=CandidateResult(label,'Geçerli',sheets,gross,waste,solution.seam_length,reusable,time.monotonic()-tick)
            rows.append(row)
            score=(sheets,gross,-reusable,waste,solution.seam_length)
            if best is None or score<best[0]: best=(score,solution,project,result,label)
        except (ValueError,GEOSException) as error:
            rows.append(CandidateResult(label,str(error),elapsed=time.monotonic()-tick))
        except InterruptedError:
            break
    if best is None:
        check_cancel(stop)
        raise ValueError('Uygulanabilir tam yerleşim bulunamadı. '+('; '.join(r.status for r in rows[:3])))
    _,solution,project,result,label=best
    return OptimizationResult(solution,project,result,rows,label,time.monotonic()-started,
                              stopped=bool(stop is not None and stop.is_set()))
