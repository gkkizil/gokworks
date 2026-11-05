"""Tangent-segment elbow with exact bisector cuts and two half end segments."""
import math
from .common import add,mul
from .cylinder import shell_part
from ..geometry import sample_count


def normalize(p,t,ref,variant):
    p=dict(p);p['diameter']+={'inner':t,'mid':0.,'outer':-t}[ref]
    if p['diameter']<=t:raise ValueError('Kalınlık iç yarıçapı sıfır veya negatif yapıyor.')
    if p['center_radius']<=p['diameter']/2:raise ValueError('Eksen yarıçapı orta yüzey boru yarıçapından büyük olmalı.')
    return p


def build(n,material,options,token=None):
    p=n['parameters'];r=p['diameter']/2;R=p['center_radius'];count=p['segments'];split=n['split_options']['count']
    if count*split>256:raise ValueError('Segment × çevresel bölme sayısı 256 parçayı aşamaz.')
    total=math.radians(p['total_angle_deg']);delta=total/(count-1);slope=math.tan(delta/2)
    mesh_samples=sample_count(r*math.hypot(1.,slope),2*math.pi/split,options.mesh_error_mm,options.max_samples)
    cut_samples=max(1,math.ceil(2*math.pi/split*math.sqrt(r*abs(slope)/(8*options.chord_error_mm))))
    if count*split*(2*(mesh_samples+1)+2*(cut_samples+1))>250000:
        raise ValueError('Dirsek geometri bütçesi 250000 örneği aşıyor; hata hedefini veya segment sayısını değiştirin.')
    start=math.radians(n['seam_options']['start_angle_deg']);parts=[];error=0.
    position=(0.,0.,-p['inlet_extension']);joints=[]
    for i in range(count):
        a=i*delta;axis=(math.sin(a),0.,math.cos(a));radial=(math.cos(a),0.,-math.sin(a))
        length=R*slope*(1 if i in (0,count-1) else 2)
        if i==0:length+=p['inlet_extension']
        if i==count-1:length+=p['outlet_extension']
        for j in range(split):
            part,bound=shell_part(f'elbow-{i+1:02d}-{j+1:02d}',r,length,start+j*2*math.pi/split,2*math.pi/split,
                slope if i else 0.,-slope if i<count-1 else 0.,0.,position,axis,radial,(0.,1.,0.),
                n,material,options,token)
            parts.append(part);error=max(error,bound)
        position=add(position,mul(axis,length));joints.append(position)
    expected=(R*(1-math.cos(total))+p['outlet_extension']*math.sin(total),0.,
              R*math.sin(total)+p['outlet_extension']*math.cos(total))
    endpoint_error=math.dist(position,expected)
    closure=max(math.dist(a,b) for i in range(count-1) for j in range(split)
        for a,b in zip(parts[i*split+j].mesh_3d.vertices[1::2],parts[(i+1)*split+j].mesh_3d.vertices[::2]))
    return tuple(parts),dict(total_angle_deg=p['total_angle_deg'],direction_step_deg=math.degrees(delta),
         segment_count=count,end_segments_are_half=True,inlet_center=(0.,0.,-p['inlet_extension']),
         outlet_center=position,expected_outlet_center=expected,axis_vertices=tuple(joints),
         endpoint_error_mm=endpoint_error,chord_error_bound_mm=error,seam_closure_error_mm=closure)
