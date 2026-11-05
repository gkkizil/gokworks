"""Four planar reducer panels and an explicit eight-panel faceted square-to-round."""
import math
from ..models import Line2D,TrueLength
from ..geometry import sample_count
from .common import planar_part,check_cancel,cross,sub,norm


def normalize_rect(p,t,ref,variant):
    p=dict(p);sign={'inner':1.,'mid':0.,'outer':-1.}[ref];H=p['height']
    for low,high in (('bottom_width','top_width'),('bottom_depth','top_depth')):
        factor=math.hypot(1.,(p[high]-p[low])/(2*H))
        p[low]+=sign*t*factor;p[high]+=sign*t*factor
        if min(p[low],p[high])<=t*factor:raise ValueError('Normal offset sonrası iç panel açıklığı pozitif değil.')
    return p


def normalize_round(p,t,ref,variant):
    if t and ref!='mid':raise ValueError('Faset geçişte kalınlıklı iç/dış normal offset v1 kapsamında değil; mid ölçü yüzeyi kullanın.')
    return dict(p)


def build_rect(n,material,options,token=None):
    p=n['parameters'];a,b,c,d,H=(p[k] for k in ('bottom_width','bottom_depth','top_width','top_depth','height'))
    bottom=((a/2,b/2,0.),(-a/2,b/2,0.),(-a/2,-b/2,0.),(a/2,-b/2,0.))
    top=((c/2,d/2,H),(-c/2,d/2,H),(-c/2,-d/2,H),(c/2,-d/2,H))
    parts=[];error=0.
    for i in range(4):
        check_cancel(token);j=(i+1)%4;v=(bottom[i],bottom[j],top[j],top[i])
        low=math.dist(v[0],v[1]);high=math.dist(v[2],v[3]);slant=math.hypot(H,(b-d)/2 if i%2==0 else (a-c)/2)
        xy=((0.,0.),(low,0.),((low+high)/2,slant),((low-high)/2,slant))
        for k,l in ((0,1),(1,2),(2,3),(3,0),(0,2)):
            error=max(error,abs(math.dist(v[k],v[l])-math.dist(xy[k],xy[l])))
        lengths=tuple(TrueLength(f'reducer-{i+1}.E{k+1}',v[k],v[(k+1)%4],math.dist(v[k],v[(k+1)%4])) for k in range(4))
        parts.append(planar_part(f'reducer-{i+1:02d}',v,xy,((0,1,2),(0,2,3)),n,material,options,lengths=lengths))
    return tuple(parts),dict(edge_length_error_mm=error,chord_error_bound_mm=0.,panel_count=4,seam_closure_error_mm=0.)


def triangle_xy(v):
    base=math.dist(v[0],v[1]);left=math.dist(v[0],v[2]);right=math.dist(v[1],v[2])
    x=(base*base+left*left-right*right)/(2*base);square=left*left-x*x
    if square<=0:raise ValueError('Dejenere geçiş üçgeni.')
    return ((0.,0.),(base,0.),(x,math.sqrt(square)))


def build_round(n,material,options,token=None):
    p=n['parameters'];W,D,H,r=p['width'],p['depth'],p['height'],p['diameter']/2
    corners=((W/2,D/2,0.),(-W/2,D/2,0.),(-W/2,-D/2,0.),(W/2,-D/2,0.))
    count=sample_count(r,math.pi/2,options.chord_error_mm,options.max_samples)
    parts=[];error=0.;area3=0.
    for i in range(4):
        check_cancel(token);a=i*math.pi/2
        top=tuple((r*math.cos(a+math.pi*j/(2*count)),r*math.sin(a+math.pi*j/(2*count)),H) for j in range(count+1))
        v=(corners[i],)+top;xy=[(0.,0.),(math.dist(v[0],v[1]),0.)];phi=0.
        for j in range(1,count+1):
            if j%128==0:check_cancel(token)
            l1=math.dist(v[0],v[j]);l2=math.dist(v[0],v[j+1]);base=math.dist(v[j],v[j+1])
            cosine=(l1*l1+l2*l2-base*base)/(2*l1*l2)
            phi+=math.acos(max(-1.,min(1.,cosine)));xy.append((l2*math.cos(phi),l2*math.sin(phi)))
        triangles=tuple((0,j,j+1) for j in range(1,count+1))
        for tri in triangles:
            v0,v1,v2=(v[k] for k in tri);area3+=norm(cross(sub(v1,v0),sub(v2,v0)))/2
            for k,l in zip(tri,tri[1:]+tri[:1]):error=max(error,abs(math.dist(v[k],v[l])-math.dist(xy[k],xy[l])))
        lengths=tuple(TrueLength(f'corner-{i+1}.G{j}',v[0],v[j],math.dist(v[0],v[j])) for j in range(1,len(v)))
        construction=tuple(Line2D(xy[0],xy[j],f'G{j}') for j in range(2,len(xy)-1))
        parts.append(planar_part(f'corner-{i+1:02d}',v,tuple(xy),triangles,n,material,options,
                                 construction=construction,lengths=lengths))
        # The adjacent straight rectangular side is a true triangular plane.
        v=(corners[i],corners[(i+1)%4],top[-1]);xy=triangle_xy(v)
        area3+=norm(cross(sub(v[1],v[0]),sub(v[2],v[0])))/2
        parts.append(planar_part(f'flat-{i+1:02d}',v,xy,((0,1,2),),n,material,options))
    return tuple(parts),dict(edge_length_error_mm=error,chord_error_bound_mm=r*(1-math.cos(math.pi/(4*count))),
         corner_facets=count,surface_area_3d_mm2=area3,panel_count=8,
         approximation='Four planar triangles and four triangulated oblique-cone fans; no smooth loft flattening.',
         seam_closure_error_mm=0.)
