"""Standard, zero-shift, full-depth external spur gears. Pure SI/mm functions."""

from math import cos, pi, radians, sin, sqrt, tan
from .models import GearSpecification, GearPairSpecification, GearResult, GearPairResult, Issue
from .validation import gear_issues, pair_issues, require_valid

TORQUE_POWER_FACTOR = 60000 / (2*pi)  # exact conversion, not rounded 9550


def calculate_gear(spec: GearSpecification) -> GearResult:
    require_valid(gear_issues(spec))
    m,z,alpha=spec.module_mm,spec.teeth,radians(spec.pressure_angle_deg)
    d=m*z
    return GearResult(d,m*(z+2),m*(z-2.5),d*cos(alpha),pi*m,pi*m/2,
        m,1.25*m,2.25*m,.25*m,d/2,d*cos(alpha)/2,m*(z+2)/2,m*(z-2.5)/2,
        pi*m*cos(alpha),2/sin(alpha)**2)


def calculate_pair(spec: GearPairSpecification) -> GearPairResult:
    issues=pair_issues(spec);require_valid(issues)
    g1,g2=calculate_gear(spec.pinion),calculate_gear(spec.wheel)
    alpha=radians(spec.pinion.pressure_angle_deg)
    ratio=spec.wheel.teeth/spec.pinion.teeth
    a=g1.pitch_radius_mm+g2.pitch_radius_mm
    approach=sqrt(g2.outside_radius_mm**2-g2.base_radius_mm**2)-g2.pitch_radius_mm*sin(alpha)
    recess=sqrt(g1.outside_radius_mm**2-g1.base_radius_mm**2)-g1.pitch_radius_mm*sin(alpha)
    path=approach+recess;contact=path/g1.base_pitch_mm
    if approach>g1.pitch_radius_mm*sin(alpha)+1e-9 or recess>g2.pitch_radius_mm*sin(alpha)+1e-9:
        issues.append(Issue('interference','Temas yolu evolventin temel daire sınırını aşıyor; girişim riski var.',severity='warning'))
    if contact<1:
        issues.append(Issue('contact_ratio','Kavrama oranı 1’den küçük; sürekli kavraşma sağlanamıyor.',severity='warning'))
    load=spec.load
    torque=TORQUE_POWER_FACTOR*load.power_kw/abs(load.input_rpm) if load.mode=='power' else load.torque_nm
    power=load.power_kw if load.mode=='power' else torque*abs(load.input_rpm)/TORQUE_POWER_FACTOR
    ft=2000*torque/g1.pitch_diameter_mm
    return GearPairResult(spec,g1,g2,ratio,a,a,-load.input_rpm/ratio,torque,torque*ratio,
        power,ft,ft*tan(alpha),approach,recess,path,contact,tuple(i for i in issues if i.severity=='warning'))
