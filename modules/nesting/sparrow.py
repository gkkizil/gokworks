"""Sparrow strip packing adapted to finite sheet stock, verified in millimetres.

The official spyrrow 0.9.0 wheels bundle Sparrow 0.1.0 / jagua-rs 0.7.0.
Only complete contours inside each physical sheet are accepted from the strip.
Holes remain in the source/output geometry; their space is conservatively reserved.
"""

from collections import Counter
from datetime import datetime, timezone
from importlib import metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from shapely import affinity
from shapely.geometry import box, Polygon
from shapely.geometry.polygon import orient

from modules.nesting.geometry import placed
from modules.nesting.models import Placement, Result
from modules.nesting.validation import validate_result
from modules.nesting.sparrow_files import filesystem_call, workspace

VERSION = 'Sparrow 0.1.0 / spyrrow 0.9.0 / jagua-rs 0.7.0'


def _available():
    try:
        version = metadata.version('spyrrow')
    except metadata.PackageNotFoundError:
        raise ValueError('Sparrow yerleşim bileşeni bulunamadı. GOKWORKS kurulumunu güncelleyin.') from None
    if version != '0.9.0':
        raise ValueError(f'Sparrow bağlantısı spyrrow 0.9.0 gerektiriyor; kurulu sürüm: {version}.')


def _run(request, deadline, stop):
    """Kill/reap only our child on cancel/timeout; retain its last feasible snapshot."""
    with workspace() as directory:
        path = Path(directory)/'request.json'
        path.write_text(json.dumps(request, allow_nan=False), encoding='utf-8')
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(Path(__file__).resolve().parents[2]/'main.py'))
        command += ['--sparrow-worker', str(path)]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=flags)
        interrupted = False
        try:
            while child.poll() is None:
                if (stop is not None and stop.is_set()) or time.monotonic() >= deadline:
                    interrupted = True
                    child.kill()
                    break
                try: child.wait(timeout=.05)
                except subprocess.TimeoutExpired: pass
        finally:
            if child.poll() is None: child.kill()
            child.wait()
        output = path.with_name('result.json')
        try:
            def read():
                if output.stat().st_size > 10*1024*1024:
                    raise ValueError('Sparrow sonucu boyut sınırını aştı.')
                return output.read_text(encoding='utf-8')
            response = json.loads(filesystem_call(read))
            if response['ok'] is not True:
                raise ValueError('Sparrow: '+str(response.get('error','Hesaplama başarısız.')))
            if child.returncode and not interrupted:
                raise ValueError('Sparrow yardımcı süreci başarısız oldu.')
            rows = response['placements']
            if not isinstance(rows,list): raise TypeError()
            return rows
        except FileNotFoundError:
            if interrupted: return None
            raise ValueError(f'Sparrow yardımcı süreci sonuç üretemedi (çıkış {child.returncode}).') from None
        except PermissionError:
            # A child killed at the deadline may leave its snapshot locked.
            if interrupted: return None
            raise ValueError('Sparrow sonuç dosyası okunamadı (dosya kilitli).') from None
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError('Sparrow sonuç biçimi geçersiz.') from error


def _angles(part, options, width, height, ended=lambda:False):
    angles = options.angles if options.rotation else [0.]
    if options.grain_locked or part.grain_locked:
        angles = [a for a in angles if abs(a % 180) < 1e-7]
    selected = []
    for angle in dict.fromkeys(a % 360 for a in angles):
        if ended(): break
        x0,y0,x1,y1 = affinity.rotate(part.polygon, angle, origin=(0,0)).bounds
        if x1-x0 <= width and y1-y0 <= height: selected.append(angle)
    return selected


def _poses(rows, specs, scale, pad, separation, sheet, sheet_number, counts):
    """Validate the entire native strip contract before accepting a finite prefix."""
    if Counter(r.get('id') for r in rows if isinstance(r,dict)) != Counter({k:s['demand'] for k,s in specs.items()}):
        raise ValueError('Sparrow parça kimlikleri veya adetleri istekle eşleşmiyor.')
    accepted = []
    boundary = box(pad-1e-7,pad-1e-7,sheet.width-pad+1e-7,sheet.height-pad+1e-7)
    local_counts = counts.copy()
    for row in rows:
        try:
            spec = specs[row['id']]; part = spec['part']
            x,y,angle = (row[k] for k in ('x','y','angle'))
            if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in (x,y,angle)):
                raise ValueError('Sonlu olmayan yerleşim.')
            allowed = min(spec['angles'], key=lambda a:abs((angle-a+180)%360-180))
            if abs((angle-allowed+180)%360-180) > 1e-4:
                raise ValueError('İzin verilmeyen dönüş açısı.')
            # Native input uses a local origin, uniform scale, then rotate+translate.
            ox,oy = spec['origin']; radians = math.radians(allowed)
            tx = x/scale+pad-separation-ox*math.cos(radians)+oy*math.sin(radians)
            ty = y/scale+pad-separation-ox*math.sin(radians)-oy*math.cos(radians)
            pose = Placement(part.id,local_counts[part.id]+1,sheet.id,sheet_number,tx,ty,allowed)
            if boundary.covers(placed(part,pose)):
                local_counts[part.id] += 1; accepted.append(pose)
        except (KeyError, TypeError, OverflowError) as error:
            raise ValueError('Sparrow yerleşim kaydı geçersiz.') from error
    return accepted


def nest(project, *, stop=None, progress=None, deadline=None, allow_disconnected=False):
    project.validate(); _available()
    if not allow_disconnected and any(p.polygon.geom_type != 'Polygon' for p in project.parts):
        raise ValueError('Sparrow çekirdeği her parça için tek bağlı dış kontur gerektirir.')
    started = time.monotonic(); options = project.options
    seconds = options.seconds if options.seconds is not None else {'Hızlı':5.,'Dengeli':15.,'Yüksek':45.}[options.quality]
    deadline = min(started+seconds,deadline) if deadline is not None else started+seconds
    counts = Counter(); stock = Counter(); placements = []; iterations = 0
    error = max(p.geometry_error for p in project.parts)
    dimension = max(max(s.width,s.height) for s in project.sheets)
    guard = max(.0001,dimension*2e-6)
    pad = options.margin+error+options.kerf/2+guard
    separation = max(options.gap,options.kerf)+2*error+2*guard
    clearance = separation/2
    scale = 1./max(1.,dimension)
    digest = project.fingerprint()

    def ended(): return (stop is not None and stop.is_set()) or time.monotonic() >= deadline

    def result():
        return Result(digest,placements[:],[p.id for p in project.parts for _ in range(p.quantity-counts[p.id])],
                      'Sparrow',VERSION,time.monotonic()-started,iterations,datetime.now(timezone.utc).isoformat(),
                      stopped=stop is not None and stop.is_set(),timed_out=time.monotonic()>=deadline)

    while sum(counts.values()) < sum(p.quantity for p in project.parts):
        if ended(): break
        best = None; seen = set()
        for sheet in sorted(project.sheets,key=lambda s:s.width*s.height):
            if stock[sheet.id] >= sheet.stock: continue
            key = (sheet.width,sheet.height,sheet.material,sheet.thickness)
            if key in seen: continue
            seen.add(key)
            width,height = sheet.width-2*pad,sheet.height-2*pad
            if min(width,height) <= 0: continue
            specs = {}
            for part in project.parts:
                if ended(): break
                if part.polygon.geom_type != 'Polygon': continue
                demand = part.quantity-counts[part.id]
                if not demand or part.material != sheet.material or not math.isclose(part.thickness,sheet.thickness,abs_tol=1e-7): continue
                angles = _angles(part,options,width,height,ended)
                if not angles: continue
                ox,oy,_,_ = part.polygon.bounds
                # Reserve clearance in our exact geometry layer. The native
                # separation option also deflates its initially narrow strip;
                # sparse jobs can make that strip disappear and panic in jagua.
                # Mitre offsets conservatively contain the Euclidean clearance.
                footprint = Polygon(part.polygon.exterior).buffer(clearance,join_style=2)
                if footprint.geom_type!='Polygon' or footprint.is_empty or not footprint.is_valid:
                    raise ValueError(part.code+': kesim aralığı konturu oluşturulamadı.')
                fitting = []
                for angle in angles:
                    if ended(): break
                    a,b,c,d = affinity.rotate(footprint,angle,origin=(0,0)).bounds
                    if c-a<=width+2*clearance and d-b<=height+2*clearance:
                        fitting.append(angle)
                # Acute mitres may be wider than a half-gap edge extension.
                # Leave such exact-fit cases to the nominal-contour refinement.
                if not fitting: continue
                angles = fitting
                specs[part.id] = dict(part=part,demand=demand,angles=angles,origin=(ox,oy),
                    # Normalize only the private footprint; source entities and
                    # nominal cutting contours retain their original geometry.
                    shape=[((x-ox)*scale,(y-oy)*scale) for x,y in list(orient(footprint,sign=1.).exterior.coords)[:-1]])
            if not specs: continue
            if ended(): break
            slice_seconds = min(deadline-time.monotonic(),{'Hızlı':1.,'Dengeli':2.,'Yüksek':4.}[options.quality])
            request = dict(items=[dict(id=k,shape=s['shape'],demand=s['demand'],angles=s['angles']) for k,s in specs.items()],
                           height=(height+2*clearance)*scale, separation=None,
                           seconds=max(1,math.ceil(slice_seconds)),seed=options.seed)
            rows = _run(request,min(deadline,time.monotonic()+slice_seconds+1.),stop)
            iterations += 1
            if rows is None: continue
            candidate = _poses(rows,specs,scale,pad,clearance,sheet,stock[sheet.id]+1,counts)
            if not candidate: continue
            # A second, independent double-precision check uses original contours.
            trial = result(); trial.placements += candidate
            trial_counts = Counter(p.part_id for p in trial.placements)
            trial.unplaced = [p.id for p in project.parts for _ in range(p.quantity-trial_counts[p.id])]
            try: validate_result(project,trial,complete=False)
            except ValueError as failure:
                raise ValueError(f'Sparrow sonucu geometrik doğrulamayı geçemedi: {failure}') from failure
            score = (len(candidate),-sheet.width*sheet.height)
            if best is None or score > best[0]: best = (score,candidate,sheet)
            if len(candidate) == sum(p.quantity-counts[p.id] for p in project.parts): break
        if best is None: break
        _,candidate,sheet = best
        placements.extend(candidate); counts.update(p.part_id for p in candidate); stock[sheet.id] += 1
        if progress: progress(100*len(placements)/sum(p.quantity for p in project.parts),f'Sparrow · {len(placements)} parça yerleşti')
    final = result()
    validate_result(project,final,complete=False)
    return final
