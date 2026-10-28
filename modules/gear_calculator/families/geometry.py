"""Involute sections, straight rack, and analytic offset envelope of cycloid pins."""
from dataclasses import dataclass
from functools import lru_cache
from math import atan, ceil, cos, hypot, pi, sin, sqrt, tan
import cmath
from ..geometry import Segment, involute, involute_derivative, rotate
from .calculation import calculate, cylindrical


@dataclass(frozen=True)
class Section:
    outer: tuple
    inner: tuple = ()
    bore: float = 0.


def flank(rb,t0,t1,offset,tol):
    n=max(1,ceil(abs(t1-t0)*(rb*sqrt(9+max(t0,t1)**2)/(384*tol))**.25))
    result=[]
    for j in range(n):
        a=t0+(t1-t0)*j/n;b=t0+(t1-t0)*(j+1)/n;h=b-a
        p,q=involute(rb,a),involute(rb,b);u,v=involute_derivative(rb,a),involute_derivative(rb,b)
        controls=(p,(p[0]+h*u[0]/3,p[1]+h*u[1]/3),(q[0]-h*v[0]/3,q[1]-h*v[1]/3),q)
        result.append(Segment('bezier',tuple(rotate(c,offset) for c in controls)))
    return result


def repeat(template,z):
    result=[]
    for j in range(z):
        theta=2*pi*j/z
        for seg in template:
            result.append(Segment(seg.kind,tuple(rotate(p,theta) for p in seg.controls),seg.radius,
                                  seg.start_angle+theta,seg.end_angle+theta,j))
    return tuple(result)


def external(s,z,bore):
    g=cylindrical(s,z,bore);rb,ra,rf=g['rb'],g['ra'],g['rf']
    t0=sqrt(max(0,(rf/rb)**2-1));t1=sqrt((ra/rb)**2-1)
    delta=pi/(2*z)+tan(g['alpha'])-g['alpha']
    tip=delta-t1+atan(t1);root=delta-t0+atan(t0)
    if tip<=0:raise ValueError('Diş üstü kalınlığı pozitif değil.')
    f=flank(rb,t0,t1,-delta,min(.001,s.module_mm/2000));segments=[]
    if rf<rb:segments.append(Segment('line',((rf*cos(delta),-rf*sin(delta)),f[0].controls[0])))
    segments.extend(f);segments.append(Segment('arc',radius=ra,start_angle=-tip,end_angle=tip))
    segments.extend(Segment('bezier',tuple((x,-y) for x,y in reversed(seg.controls))) for seg in reversed(f))
    if rf<rb:segments.append(Segment('line',((rb*cos(delta),rb*sin(delta)),(rf*cos(delta),rf*sin(delta)))))
    segments.append(Segment('arc',radius=rf,start_angle=root,end_angle=2*pi/z-root))
    return Section(repeat(segments,z),bore=bore)


def ring(s,z):
    m=s.module_mm;alpha=pi/9;r=m*z/2;ra=r-m;rf=r+1.25*m;rb=r*cos(alpha)
    if ra<=rb:raise ValueError('İç dişli ucu temel dairenin altında.')
    ta=sqrt((ra/rb)**2-1);tf=sqrt((rf/rb)**2-1)
    delta=pi/(2*z)+tan(alpha)-alpha
    gap_tip=delta-ta+atan(ta);gap_root=delta-tf+atan(tf)
    if not 0<gap_root<gap_tip<pi/z:raise ValueError('İç dişli kalınlığı pozitif değil.')
    f=[Segment('bezier',tuple((x,-y) for x,y in seg.controls))
       for seg in flank(rb,tf,ta,-delta,min(.001,m/2000))]
    segs=[Segment('arc',radius=rf,start_angle=-gap_root,end_angle=gap_root),*f,
          Segment('arc',radius=ra,start_angle=gap_tip,end_angle=2*pi/z-gap_tip)]
    for seg in reversed(f):
        segs.append(Segment('bezier',tuple(rotate((x,-y),2*pi/z) for x,y in reversed(seg.controls))))
    return Section((Segment('arc',radius=rf+s.rim_mm,start_angle=0,end_angle=2*pi),),repeat(segs,z))


def rack(s):
    m=s.module_mm;p=pi*m;alpha=s.pressure_angle_deg*pi/180
    ha=m;hf=1.25*m;wt=p/2-2*ha*tan(alpha);wf=p/2+2*hf*tan(alpha)
    centers=[(k-s.rack_teeth//2)*p for k in range(s.rack_teeth)]
    left=centers[0]-p/2;right=centers[-1]+p/2
    pts=[(left,-s.rack_base_mm),(right,-s.rack_base_mm),(right,-hf)]
    for x in reversed(centers):pts.extend(((x+wf/2,-hf),(x+wt/2,ha),(x-wt/2,ha),(x-wf/2,-hf)))
    pts.extend(((left,-hf),pts[0]))
    return Section(tuple(Segment('line',(a,b)) for a,b in zip(pts,pts[1:])))


def cycloid_point(s,u):
    """Envelope of N fixed rollers in the eccentric disk's rotating frame.

    p(u)=R exp(iu)-e exp(iNu); outward normal=-i p'/|p'|.
    Disk boundary is the inward roller-radius offset, not a decorative cycloid.
    """
    N=s.teeth2;R=s.module_mm*N/2;e=s.eccentricity_mm
    a=cmath.exp(1j*u);b=cmath.exp(1j*N*u)
    p=R*a-e*b;v=1j*(R*a-N*e*b);acc=-R*a+N*N*e*b
    speed=abs(v);normal=-1j*v/speed
    normal_d=-1j*(acc/speed-v*(acc*v.conjugate()).real/speed**3)
    return p-s.roller_radius_mm*normal,v-s.roller_radius_mm*normal_d


def cycloid(s):
    tol=min(.001,s.module_mm/2000);parts=[]
    def point(u):
        p,d=cycloid_point(s,u);return (p.real,p.imag),(d.real,d.imag)
    def fit(a,b,depth=0):
        p,d=point(a);q,v=point(b);h=b-a
        seg=Segment('bezier',(p,(p[0]+h*d[0]/3,p[1]+h*d[1]/3),
                              (q[0]-h*v[0]/3,q[1]-h*v[1]/3),q))
        error=max(hypot(*(x-y for x,y in zip(seg.point(t),point(a+h*t)[0]))) for t in (.25,.5,.75))
        if error>tol/4:
            if depth>=12:raise ValueError('Sikloid eğri hassasiyeti sağlanamadı.')
            fit(a,(a+b)/2,depth+1);fit((a+b)/2,b,depth+1)
        else:parts.append(seg)
    n=8*(s.teeth2-1)
    for j in range(n):fit(2*pi*j/n,2*pi*(j+1)/n)
    return Section(tuple(parts),bore=s.bore1_mm)


@lru_cache(maxsize=12)
def sections(s):
    calculate(s)
    if s.kind in ('helical','herringbone'):return (external(s,s.teeth1,s.bore1_mm),external(s,s.teeth2,s.bore2_mm))
    if s.kind=='rack':return (external(s,s.teeth1,s.bore1_mm),rack(s))
    if s.kind=='internal':return (external(s,s.teeth1,s.bore1_mm),ring(s,s.teeth2))
    if s.kind=='planetary':return (external(s,s.teeth1,s.bore1_mm),external(s,s.teeth2,s.bore2_mm),ring(s,s.teeth1+2*s.teeth2))
    if s.kind=='cycloidal':return (cycloid(s),)
    raise ValueError('Bu türün doğrulanmış CAD profili henüz yok.')


def sample(segments,tol):
    pts=[]
    for seg in segments:pts.extend(seg.sampled(tol) if not pts else seg.sampled(tol)[1:])
    pts[-1]=pts[0];return tuple(pts)


def section_polygon(section,tol):
    from shapely.geometry import Polygon,Point
    holes=[sample(section.inner,tol)] if section.inner else []
    if section.bore:holes.append(tuple(Point(0,0).buffer(section.bore/2,quad_segs=128).exterior.coords))
    p=Polygon(sample(section.outer,tol),holes)
    if not p.is_valid or p.area<=0:raise ValueError('Dişli profili kendini kesiyor veya alanı geçersiz.')
    return p


def poses(s,angle=0.,depth=0.):
    """(section index, angle, x, y); depth is axial coordinate in mm."""
    m=s.module_mm;z1=s.teeth1;z2=s.teeth2
    if s.kind in ('helical','herringbone'):
        r1=cylindrical(s,z1)['r'];r2=cylindrical(s,z2)['r']
        axial=depth if s.kind=='helical' else min(depth,s.width_mm-depth)
        twist=axial*tan(s.helix_deg*pi/180)/r1
        return ((0,angle+twist,0,0),(1,pi-pi/z2-angle*z1/z2-twist*z1/z2,r1+r2,0))
    if s.kind=='rack':return ((0,-pi/2-pi/z1+angle,0,m*z1/2),(1,0,m*z1/2*angle,0))
    if s.kind=='internal':return ((0,angle,m*(z2-z1)/2,0),(1,angle*z1/z2,0,0))
    if s.kind=='planetary':
        zr=z1+2*z2;carrier=angle*z1/(z1+zr);orbit=m*(z1+z2)/2
        result=[(0,angle,0,0),(2,(z2-1)*pi/zr,0,0)]
        for j in range(s.planets):
            psi=2*pi*j/s.planets+carrier
            spin=psi+pi-pi/z2-(angle-psi)*z1/z2
            result.append((1,spin,orbit*cos(psi),orbit*sin(psi)))
        return tuple(result)
    if s.kind=='cycloidal':return ((0,-angle/(z2-1),s.eccentricity_mm*cos(angle),s.eccentricity_mm*sin(angle)),)
    return ()


@lru_cache(maxsize=12)
def verify(s,samples=48):
    from shapely.affinity import rotate as sr,translate
    from shapely.geometry import Point
    if not calculate(s).cad_available:raise ValueError('Bu türün CAD/kavraşma doğrulaması henüz yok.')
    profiles=[section_polygon(sec,min(.0005,s.module_mm*.00025)) for sec in sections(s)]
    worst=0.;allowed=2e-5*s.module_mm**2
    # One full sun cycle is needed to exercise all carrier positions; the
    # ordinary meshes are periodic in one tooth pitch.
    extent=2*pi if s.kind in ('cycloidal','planetary') else 2*pi/s.teeth1
    for k in range(samples):
        angle=extent*k/samples
        shapes=[translate(sr(profiles[idx],theta,origin=(0,0),use_radians=True),xoff=x,yoff=y)
                for idx,theta,x,y in poses(s,angle)]
        for i,p in enumerate(shapes):
            for q in shapes[i+1:]:worst=max(worst,p.intersection(q).area)
        if s.kind=='cycloidal':
            R=s.module_mm*s.teeth2/2
            for j in range(s.teeth2):
                pin=Point(R*cos(2*pi*j/s.teeth2),R*sin(2*pi*j/s.teeth2)).buffer(s.roller_radius_mm,quad_segs=64)
                worst=max(worst,shapes[0].intersection(pin).area)
    if worst>allowed:raise ValueError(f'Diş/pim girişimi: {worst:.6g} mm² (sınır {allowed:.6g}).')
    return dict(samples=samples,maximum_overlap_mm2=worst,overlap_tolerance_mm2=allowed)
