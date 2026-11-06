"""Multi-surface junctions and independently specified curved intersections."""
import math
from .development import circle,basis,adaptive,ribbon
from .common import add,sub,mul,dot,norm
from .source_intersections import Branch,Trunk,quadratic,mapped_part
from .source_extrusions import extrude


def build_torus_branch(m,n,material,options,token):
    p=n['parameters'];R=p['R'];r=p['Db']/2
    if R<=r:raise ValueError('Dirsek eksen yarıçapı kesit yarıçapından büyük olmalı.')
    angle=math.radians(p.get('A',0.));base=math.pi/4;axis=(math.cos(base)*math.cos(angle),math.cos(base)*math.sin(angle),math.sin(base));axis,rx,ry=basis(axis)
    origin=(p.get('X',0.),p.get('Z',0.),p.get('E',0.));limit=R+r+norm(origin)+p['D']
    worst=0.
    def lower(x,y):
        nonlocal worst
        start=add(origin,add(mul(rx,x),mul(ry,y)))
        def value(u):
            xx,yy,zz=add(start,mul(axis,u));return (math.hypot(xx,zz)-R)**2+yy*yy-r*r
        previous=0.;fp=value(0.);roots=[]
        for i in range(1,257):
            b=limit*i/256;fb=value(b)
            if fp*fb<=0:
                a=previous;fa=fp
                for _ in range(52):
                    mid=(a+b)/2;fm=value(mid)
                    if fa*fm<=0:b=mid
                    else:a=mid;fa=fm
                roots.append((a+b)/2)
            previous=limit*i/256;fp=value(previous)
        if not roots:raise ValueError('Boru üreteci 90° torus yüzeyiyle kesişmiyor.')
        u=max(roots);v=add(start,mul(axis,u));phi=math.atan2(v[2],v[0])
        if not 0<=phi<=math.pi/2:raise ValueError('Kesişim 90° dirsek parçasının dışında kalıyor.')
        if u>=p['L']:raise ValueError('Boru boyu torus dış kesişimine ulaşmıyor.')
        worst=max(worst,abs(value(u))/max(1.,2*r));return u
    part,e=extrude(m['source_id'],circle(p['D']),lower,lambda x,y:p['L'],n,material,options,token,origin=origin,axis=axis,radial_x=rx,radial_y=ry)
    return (part,),dict(measured_curve_residual_mm=e,torus_surface_residual_mm=worst,
        assumptions='Torus axis Y; bend sector XZ 0..90 deg; nominal pipe axis radial at 45 deg; A rotates it about Z; E/Z/X are world translations.')


def build_reducing_breech(m,n,material,options,token):
    p=n['parameters'];s=m['source_id']
    if '-3-' in s:return build_three_breech(m,n,material,options,token)
    R=p['D1']/2;r=p['D2']/2
    angled=s.endswith('angled-top')
    if angled:
        angle=math.radians(p['A']/2);X=p['L']*math.sin(angle);H=p['L']*math.cos(angle)
    else:X=p['A']/2;H=p['L'];angle=0.
    if X<=r*math.cos(angle):raise ValueError('İki kolun üst ağızları ayırıcı düzlemi geçiyor/çakışıyor.')
    out=[];error=0.;edge_error=0.
    for side in (-1,1):
        def at(t,top):
            theta=math.tau*t;x=R*math.cos(theta);y=R*math.sin(theta)
            if not top:return x,y,0.
            return side*X+r*math.cos(theta)*math.cos(angle),p['Y']+r*math.sin(theta),H-side*r*math.cos(theta)*math.sin(angle)
        def bounds(t):
            a,b=at(t,False),at(t,True);u=0.
            if side*a[0]<0:
                u=-a[0]/(b[0]-a[0])
                if not 0<=u<1:raise ValueError('Pantolon ayırıcı düzlemi üst ağızdan geçiyor.')
            lo=tuple(x+u*(y-x) for x,y in zip(a,b));return lo+b
        # Include exact intersections of the base circle with the X=0 divider.
        sampled,e=adaptive(bounds,0.,1.,options.chord_error_mm,options.max_samples,[i/32 for i in range(33)],token)
        part,ee=ribbon(s+('-left' if side<0 else '-right'),[v[:3] for t,v in sampled],[v[3:] for t,v in sampled],n,material,options,token)
        from .source_extrusions import edge_allowances
        flats=[mp.developed for mp in part.mappings];low=flats[::2];high=flats[1::2]
        part=edge_allowances(part,dict(bottom=low,top=high[::-1],left=(high[0],low[0]),right=(low[-1],high[-1])),n,material,options)
        out.append(part);error=max(error,e);edge_error=max(edge_error,ee)
    return tuple(out),dict(approximation='two mirrored clipped ruled surfaces; faceted material, smooth forming strain not solved',smooth_isometry=False,
         measured_curve_residual_mm=error,facet_edge_error_mm=edge_error,real_piece_count=2,divider_plane='X=0')


def build_three_breech(m,n,material,options,token):
    """Compatible quadrics share one constant term and linear bisector planes.

    F_i(P) = |P|^2 - R^2 - beta_i(P)^2,
    beta_i = sqrt(1+k_i^2) axis_i.P + R*k_i.
    The retained face satisfies beta_i >= beta_j for every neighbour. This
    selects the actual outward junction component, including unequal cones.
    """
    from .common import with_generators
    p=n['parameters'];s=m['source_id'];R=p['D']/2;H=p['H'];origin=(0.,0.,H)
    angles=[-p['A']/2,p['A']/2] if 'A' in p else [-p['A1'],p['A2']]
    lengths=[p.get('L1',p.get('L')),p.get('L2',p.get('L'))]
    ends=[p.get('d1',p.get('d'))/2,p.get('d2',p.get('d'))/2]
    axis,rx,ry=basis((0.,0.,-1.))
    branches=[Branch(origin,axis,rx,ry,circle(2*R),R,0.,H)]
    for angle,L,re in zip(angles,lengths,ends):
        roots=quadratic(L*L-R*R,-2*re*L,re*re-R*R)
        candidates=[k for k in roots if k<=0 and re-k*L>0]
        if not candidates:raise ValueError('Pantolon kol çapı/boyu ortak kuadrik birleşimini sağlamıyor.')
        k=max(candidates);rj=re-k*L
        if not math.isclose(rj*rj/(1+k*k),R*R,rel_tol=1e-10,abs_tol=1e-7):raise ValueError('Pantolon konisinin gövdeyle ortak sabiti uyuşmuyor.')
        angle=math.radians(angle);axis,rx,ry=basis((math.sin(angle),0.,math.cos(angle)))
        branches.append(Branch(origin,axis,rx,ry,circle(2*rj),rj,k,L))
    out=[];residual=0.;joint_planes=[]
    for i,branch in enumerate(branches):
        weight=math.hypot(1.,branch.slope);planes=[]
        for j,other in enumerate(branches):
            if i==j:continue
            normal=sub(mul(branch.axis,weight),mul(other.axis,math.hypot(1.,other.slope)))
            planes.append((normal,R*(other.slope-branch.slope)))
        joint_planes.append(planes)
        def sample(t):
            start,direction=branch.ray(t);q=sub(start,origin);limits=[]
            for normal,constant in planes:
                denominator=dot(normal,direction)
                if denominator<=1e-10:raise ValueError('Kol açısı/konikliği tek bağlı üreteç açınımını sağlamıyor.')
                limits.append((constant-dot(normal,q))/denominator)
            lo=max(limits)
            if lo>=branch.end or branch.radius+branch.slope*lo<=0:raise ValueError('Pantolon kol boyu birleşim kesiminden kısa veya tepe kesiliyor.')
            return branch.flat(t,lo)+branch.flat(t,branch.end)+branch.point(t,lo)+branch.point(t,branch.end)
        samples,e=adaptive(sample,0.,1.,options.chord_error_mm,options.max_samples,[j/48 for j in range(49)],token)
        low=[(v[:2],v[4:7]) for t,v in samples];high=[(v[2:4],v[7:10]) for t,v in samples]
        name=s+('-body' if i==0 else f'-arm{i}')
        part=mapped_part(name,low+high[::-1],(),n,material,options,token)
        count=n['model_options']['helper_divisions'];guides=[]
        for j in range(count+1):
            v=sample(j/count);guides.append((v[:2],v[2:4],v[4:7],v[7:10]))
        part=with_generators(part,guides,n)
        from .source_extrusions import edge_allowances
        part=edge_allowances(part,dict(bottom=[q for q,v in low],top=[q for q,v in high[::-1]],left=(high[0][0],low[0][0]),right=(low[-1][0],high[-1][0])),n,material,options)
        out.append(part);residual=max(residual,e)
    return tuple(out),dict(real_piece_count=3,measured_curve_residual_mm=residual,
        intersection_method='compatible quadrics with common R^2; weighted linear bisector envelopes',joint_planes=joint_planes)


def build_rain_head(m,n,material,options,token):
    from .development import polygon_part
    p=n['parameters'];r=p['d']/2;R=p['D']/2;H=p['H'];wall=p['W']
    if not 0<r<wall<R:raise ValueError('Arka sac için alt yarıçap < duvar kaçıklığı < üst yarıçap olmalı.')
    trunk=Trunk(r,(R-r)/H);seam=math.pi;mapper=trunk.mapping(seam)
    def top(theta):
        c=math.cos(theta)
        return min(H,(wall/(-c)-r)/trunk.slope) if c<0 else H
    def fn(t):
        theta=seam+math.tau*t;z=top(theta)
        return mapper(theta,0.)+mapper(theta,z)+trunk.point(theta,0.)+trunk.point(theta,z)
    samples,e=adaptive(fn,0.,1.,options.chord_error_mm,options.max_samples,[i/32 for i in range(33)],token)
    low=[(v[:2],v[4:7]) for t,v in samples];high=[(v[2:4],v[7:10]) for t,v in samples]
    cone=mapped_part(m['source_id']+'-cone',low+high[::-1],(),n,material,options,token)
    from .common import with_generators
    count=n['model_options']['helper_divisions'];guides=[]
    for j in range(count+1):
        v=fn(j/count);guides.append((v[:2],v[2:4],v[4:7],v[7:10]))
    cone=with_generators(cone,guides,n)
    z0=(wall-r)/trunk.slope
    # Back plate is the real cone/vertical-plane intersection, not a bounding rectangle.
    side,e2=adaptive(lambda z:(math.sqrt(max(0.,(r+trunk.slope*z)**2-wall*wall)),z),z0,H,options.chord_error_mm,options.max_samples,token=token)
    right=[(-wall,v[0],v[1]) for z,v in side];left=[(-wall,-v[0],v[1]) for z,v in side]
    verts=right+left[::-1];verts=[v for i,v in enumerate(verts) if not i or math.dist(v,verts[i-1])>1e-7]
    if math.dist(verts[0],verts[-1])<1e-7:verts.pop()
    plate=polygon_part(m['source_id']+'-back',verts,n,material,options,token)
    cut=n['model_options']['cut_type'];out=(cone,plate) if cut=='1_all' else (cone,) if cut=='1_cone' else (plate,)
    return out,dict(real_piece_count=len(out),measured_curve_residual_mm=max(e,e2),wall_plane_x_mm=-wall)
