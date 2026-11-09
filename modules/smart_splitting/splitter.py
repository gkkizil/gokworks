"""Deterministic radial clipping; exact count and conservation are hard gates."""
from dataclasses import replace
import hashlib
import math
import time
from numbers import Real

from shapely import union_all
from shapely.geometry import LineString, Point, Polygon, shape

from modules.nesting.dxf_import import check_cancel
from .analysis import analyze, validate_source
from .models import PROFILES, Segment, SplitSolution
from .validation import validate_manufacturing, validate_partition


def center_for(part, settings):
    return settings.center or analyze(part)[settings.center_mode+'_center' if settings.center_mode=='bounds' else 'centroid']


def ray(center, angle, radius):
    angle=math.radians(angle % 360)
    return LineString([center,(center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle))])


def radius_for(g, center):
    x0,y0,x1,y1=g.bounds
    radius=4*max(math.dist(center,corner) for corner in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)))+1
    if not math.isfinite(radius): raise ValueError('Bölme merkezi / kaynak ölçüleri hesaplama aralığını aşıyor.')
    return radius


def equal_angles(settings):
    return tuple(settings.start_angle+i*360/settings.count for i in range(settings.count))


def protected_holes(g, center):
    # A central bore is a deliberate assembly boundary, not a bolt-hole keep-out.
    return [Polygon(r) for r in g.interiors if not Polygon(r).covers(Point(center))]


def safe_ray(g, center, angle, settings, radius):
    line=ray(center,angle,radius)
    for hole in protected_holes(g,center):
        if line.intersects(hole) or line.distance(hole)+1e-7<settings.hole_clearance: return False
    if any(line.intersects(shape(region)) for region in settings.forbidden): return False
    return True


def aware_angles(part, settings, *, offset=0., stop=None):
    g=validate_source(part); center=center_for(part,settings); radius=radius_for(g,center)
    step=360/settings.count; angles=[]
    for angle in equal_angles(settings):
        check_cancel(stop)
        target=angle+offset
        trials=[target+step*f for f in (0,.04,-.04,.08,-.08,.12,-.12,.18,-.18,.25,-.25,.33,-.33)]
        safe=[a for a in trials if safe_ray(g,center,a,settings,radius)]
        if not safe: raise ValueError('Delik yaklaşma mesafesi / yasaklı bölge için güvenli bölme açısı bulunamadı.')
        angles.append(min(safe,key=lambda a:abs(a-target)))
    return tuple(angles)


def split(part, settings, *, mode='equal', angles=None, stop=None):
    started=time.monotonic(); settings.validate(); g=validate_source(part); check_cancel(stop)
    center=center_for(part,settings); radius=radius_for(g,center)
    if mode not in ('equal','smart'): raise ValueError('Bölme yöntemi geçersiz.')
    try:
        angles=tuple(angles) if angles is not None else aware_angles(part,settings,stop=stop) if mode=='smart' else equal_angles(settings)
    except TypeError: raise ValueError('Bölme açıları sonlu sayılardan oluşan bir liste olmalı.') from None
    if len(angles)!=settings.count or any(not isinstance(a,Real) or isinstance(a,bool) or not math.isfinite(a) for a in angles):
        raise ValueError('Bölme açısı sayısı segment sayısıyla aynı olmalı.')
    gaps=[b-a for a,b in zip(angles,(*angles[1:],angles[0]+360))]
    if any(a<=1e-5 or a>=360 for a in gaps): raise ValueError('Bölme açıları sıralı olmalı; kesimler üst üste gelemez.')
    polygons=[]
    rays=[ray(center,a,radius) for a in angles]
    for index,(angle,sweep) in enumerate(zip(angles,gaps)):
        check_cancel(stop)
        if settings.forbidden and not all(not ray(center,angle,radius).intersects(shape(r)) for r in settings.forbidden):
            raise ValueError('Bölme çizgisi yasaklı bölgeden geçiyor.')
        if (mode=='smart' or settings.hole_clearance>0) and not safe_ray(g,center,angle,settings,radius):
            raise ValueError('Bölme çizgisi kritik delik/slot yaklaşma mesafesini ihlal ediyor.')
        steps=math.ceil(sweep/60)
        # Both neighboring sectors must use the identical shared endpoint,
        # including the 360° wrap. Re-evaluating sin/cos creates microscopic
        # cracks reaching the center that area-only checks cannot detect.
        points=[center,rays[index].coords[-1]]+[ray(center,angle+sweep*i/steps,radius).coords[-1]
            for i in range(1,steps)]+[rays[(index+1)%settings.count].coords[-1]]
        polygons.append(g.intersection(Polygon(points)))
    delta,symmetric=validate_partition(g,polygons,settings.count)
    seams={i:[] for i in range(settings.count)}; cutting={i:[] for i in range(settings.count)}
    neighbors={i:[] for i in range(settings.count)}; length=0.
    for i,angle in enumerate(angles):
        check_cancel(stop)
        j=(i-1)%settings.count
        # The cyclic boundary is constructed at angle+360 on one side. Using
        # the generating ray avoids losing that seam to floating-point drift.
        common=ray(center,angle,radius).intersection(g).difference(g.boundary.buffer(1e-8))
        if common.length>1e-6:
            seams[i].append(common); seams[j].append(common)
            cutting[i].append(rays[i]); cutting[j].append(rays[i])
            if j+1 not in neighbors[i]: neighbors[i].append(j+1)
            if i+1 not in neighbors[j]: neighbors[j].append(i+1)
            length+=common.length
    segments=[]
    for i,p in enumerate(polygons):
        check_cancel(stop)
        edges=seams[i]; seam=union_all(edges) if edges else LineString()
        cutting_lines=union_all(cutting[i]) if cutting[i] else LineString()
        blank=p
        if settings.weld_gap and not seam.is_empty:
            blank=p.difference(cutting_lines.buffer(settings.weld_gap/2))
        if settings.allowance and not seam.is_empty:
            blank=p.union(cutting_lines.buffer(settings.allowance).intersection(g))
        if blank.geom_type!='Polygon' or blank.is_empty or not blank.is_valid:
            raise ValueError('Boşluk / işleme payı bağlantısız veya boş segment üretti.')
        minimum=validate_manufacturing(blank,settings)
        key=hashlib.sha256((part.id+str(i)+blank.normalize().wkb_hex).encode()).hexdigest()[:32]
        segments.append(Segment(key,i+1,part.code,p,blank,minimum,seam.length,neighbors[i],edges))
    warnings=['Nominal bölüm doğrulandı; yapısal dayanım ve kaynak mukavemeti hesaplanmaz.',
              'Minimum genişlik döndürülmüş sınır dikdörtgeninin kısa kenarıdır; yerel uç kalınlığı değildir.',
              'Kerf DXF geometrisine uygulanmaz; CAM takım telafisi ayrıca ayarlanır.']
    if settings.min_web: warnings.append('Et kalınlığı kontrolü erozyon bağlantısı ve delik mesafeleriyle sınırlıdır.')
    if settings.weld_gap or settings.allowance: warnings.append('Nesting/DXF imalat konturlarını kullanır; nominal montaj alanından farklıdır.')
    if mode=='equal' and any(ray(center,a,radius).intersects(h) for a in angles for h in protected_holes(g,center)):
        warnings.append('Eşit açısal bölme bazı delik/slotları açıyor; korumak için kontur duyarlı modu kullanın.')
    return SplitSolution(part,settings,center,angles,segments,delta,symmetric,length,warnings,time.monotonic()-started)


def candidates(part, settings, stop=None):
    maximum,_=PROFILES[settings.profile]
    yield 'Eşit açısal başlangıç',settings,equal_angles(settings),'equal'
    step=360/settings.count
    for i in range(1,maximum):
        check_cancel(stop)
        trial=settings
        if i>=9 and settings.center is None:
            center=center_for(part,settings); g=part.polygon
            trial=replace(settings,center=(center[0]+(g.bounds[2]-g.bounds[0])*.02*(-1 if i%2 else 1),center[1]))
        try: angles=aware_angles(part,trial,offset=step*(i-1)/(maximum-1),stop=stop)
        except ValueError: angles=None
        yield f'Kontur adayı {i}',trial,angles,'smart'
