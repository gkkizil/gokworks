"""Independent 60-digit oracle, not used by the application or CAD engine.

Trigonometry uses Decimal Taylor series. Loads follow pitch-line speed and
P=F*v rather than the production torque conversion. Contact ratio uses each
gear's dimensionless roll contribution. Area follows Green's theorem on the
analytic involutes, circular arcs and radial root connectors, not sampled CAD.
"""

from decimal import Decimal, localcontext
from functools import lru_cache

D=Decimal
PI=D('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986')


def sin_cos(x):
    st=x;ct=D(1);s=st;c=ct
    for k in range(1,60):
        st*=-x*x/D((2*k)*(2*k+1));s+=st
        ct*=-x*x/D((2*k-1)*(2*k));c+=ct
    return s,c


def atan(x):
    if x>1:
        return PI/2-atan(1/x)
    if x>D('.3'):
        return 2*atan(x/(1+(1+x*x).sqrt()))
    value=D(0);term=x
    for k in range(100):
        value+=term/D(2*k+1);term*=-x*x
    return value


@lru_cache(maxsize=512)
def gear(module,teeth,angle):
    with localcontext() as ctx:
        ctx.prec=60
        m,z=D(str(module)),D(teeth);alpha=D(str(angle))*PI/180
        sine,cosine=sin_cos(alpha)
        d=m*z;rp=d/2;rb=rp*cosine;ra=rp+m;rf=rp-D('1.25')*m
        ta=((ra/rb)**2-1).sqrt()
        tf=max(D(0),(rf/rb)**2-1).sqrt()
        delta=PI/(2*z)+sine/cosine-alpha
        area=z*(rb**2*(ta**3-tf**3)/3+ra**2*(delta-ta+atan(ta))+
                rf**2*(PI/z-delta+tf-atan(tf)))
        return dict(pitch_diameter_mm=d,outside_diameter_mm=2*ra,root_diameter_mm=2*rf,
            base_diameter_mm=2*rb,circular_pitch_mm=PI*m,tooth_thickness_mm=PI*m/2,
            addendum_mm=m,dedendum_mm=D('1.25')*m,whole_depth_mm=D('2.25')*m,clearance_mm=m/4,
            pitch_radius_mm=rp,base_radius_mm=rb,outside_radius_mm=ra,root_radius_mm=rf,
            base_pitch_mm=2*PI*rb/z,undercut_limit_teeth=2/(sine*sine),
            roll_contact=z*(ta-sine/cosine)/(2*PI),area_mm2=area,sine=sine,cosine=cosine)


def pair(spec):
    with localcontext() as ctx:
        ctx.prec=60
        g1=gear(spec.pinion.module_mm,spec.pinion.teeth,spec.pinion.pressure_angle_deg)
        g2=gear(spec.wheel.module_mm,spec.wheel.teeth,spec.wheel.pressure_angle_deg)
        n=abs(D(str(spec.load.input_rpm)))
        pitch_speed=PI*g1['pitch_diameter_mm']*n/D(60000)  # metres per second
        if spec.load.mode=='power':
            power=D(str(spec.load.power_kw))
            ft=power*1000/pitch_speed
        else:
            ft=D(str(spec.load.torque_nm))/(g1['pitch_radius_mm']/1000)
            power=ft*pitch_speed/1000
        fn=ft/g1['cosine']
        ratio=D(spec.wheel.teeth)/D(spec.pinion.teeth)
        torque=ft*g1['pitch_radius_mm']/1000
        contact=g1['roll_contact']+g2['roll_contact']
        return dict(ratio=ratio,center_distance_mm=g1['pitch_radius_mm']+g2['pitch_radius_mm'],
            output_rpm=-D(str(spec.load.input_rpm))/ratio,input_torque_nm=torque,output_torque_nm=torque*ratio,
            power_kw=power,tangential_force_n=ft,radial_force_n=(fn*fn-ft*ft).sqrt(),
            approach_length_mm=g2['roll_contact']*g2['base_pitch_mm'],
            recess_length_mm=g1['roll_contact']*g1['base_pitch_mm'],
            path_of_contact_mm=contact*g1['base_pitch_mm'],transverse_contact_ratio=contact)


def volume(spec):
    with localcontext() as ctx:
        ctx.prec=60
        g=gear(spec.module_mm,spec.teeth,spec.pressure_angle_deg)
        return (g['area_mm2']-PI*(D(str(spec.bore_mm))/2)**2)*D(str(spec.face_width_mm))
