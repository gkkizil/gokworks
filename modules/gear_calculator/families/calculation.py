"""Nominal geometry and ideal kinematics; no inferred hypoid tooth geometry."""
from math import atan, atan2, cos, degrees, isfinite, pi, radians, sin, sqrt, tan
from .models import CATALOG, MechanismSpecification, MechanismResult
from ..models import GearSpecification, GearPairSpecification
from ..validation import finite, pair_issues, require_valid
from ..calculation import calculate_pair, TORQUE_POWER_FACTOR


def validate(s):
    if not isinstance(s, MechanismSpecification) or type(s.kind) is not str or s.kind not in CATALOG:
        raise ValueError('Bilinmeyen dişli mekanizması.')
    limits = {'module_mm':(.1,20), 'pressure_angle_deg':(14.5,30), 'width_mm':(.1,500),
        'bore1_mm':(0,5999), 'bore2_mm':(0,5999), 'helix_deg':(0,40),
        'rack_base_mm':(.1,1000), 'rim_mm':(.2,1000), 'shaft_angle_deg':(20,160),
        'offset_mm':(.001,1000), 'diameter_quotient':(4,30),
        'eccentricity_mm':(.001,20), 'roller_radius_mm':(.01,100)}
    for key,(low,high) in limits.items():
        v=getattr(s,key)
        if not finite(v) or not low<=v<=high:
            raise ValueError(f'{key}: {low}–{high} aralığında sonlu sayı gerekli.')
    for key,low,high in (('teeth1',6,300),('teeth2',6,300),('rack_teeth',4,80),('planets',2,6),('worm_starts',1,8)):
        v=getattr(s,key)
        if type(v) is not int or not low<=v<=high:
            raise ValueError(f'{key}: {low}–{high} aralığında tam sayı gerekli.')
    # Share the original strict single-primary load validation, without
    # interpreting normal-plane geometry as the original transverse spec.
    require_valid(pair_issues(GearPairSpecification(load=s.load)))
    if s.module_mm*(max(s.teeth1,s.teeth2)+2)>6000:
        raise ValueError('Dişli çapı 6000 mm kaynak sınırını aşıyor.')
    if s.kind in ('internal','planetary') and s.pressure_angle_deg != 20:
        raise ValueError('İç dişli CAD doğrulaması bu sürümde yalnız 20° için desteklenir.')
    if s.kind in ('helical','herringbone') and not 0<s.helix_deg<=40:
        raise ValueError('Helisel türde helis açısı 0° üstünde olmalı.')


def cylindrical(s, teeth, bore=0):
    """Section geometry. Addendum/dedendum use normal, NOT transverse module."""
    beta=radians(s.helix_deg) if s.kind in ('helical','herringbone') else 0.
    mt=s.module_mm/cos(beta);alpha=atan(tan(radians(s.pressure_angle_deg))/cos(beta))
    r=mt*teeth/2;rb=r*cos(alpha);ra=r+s.module_mm;rf=r-1.25*s.module_mm
    critical=2*cos(beta)/sin(alpha)**2
    if teeth+1e-12<critical:
        raise ValueError(f'z={teeth}: alttan kesilme riski; kesici trokoidi desteklenmiyor (sınır {critical:.4f}).')
    if bore and rf-bore/2<max(.2,.1*s.module_mm)-1e-9:
        raise ValueError('Delik diş dibi altında yeterli radyal et bırakmıyor.')
    if 2*ra>6000:
        raise ValueError('Diş üstü çapı 6000 mm kaynak sınırını aşıyor.')
    return dict(r=r,rb=rb,ra=ra,rf=rf,alpha=alpha,mt=mt,beta=beta)


def calculate(s):
    validate(s);m=s.module_mm;z1=s.teeth1;z2=s.teeth2;alpha=radians(s.pressure_angle_deg)
    load=s.load;n=load.input_rpm
    torque=TORQUE_POWER_FACTOR*load.power_kw/abs(n) if load.mode=='power' else load.torque_nm
    power=load.power_kw if load.mode=='power' else torque*abs(n)/TORQUE_POWER_FACTOR
    rows=[];warnings=[CATALOG[s.kind].note,'Nominal/ideal hesap; ISO/AGMA dayanım, verim ve tolerans yığılması doğrulanmadı.']
    def add(key,value,unit=''):rows.append((key,float(value),unit))
    add('P',power,'kW');add('n₁',n,'dev/dak');add('T₁',torque,'N·m')
    ratio=z2/z1;n2=-n/ratio;d1=m*z1;d2=m*z2
    cad=CATALOG[s.kind].geometry
    if s.kind in ('helical','herringbone','rack','internal','planetary'):
        g=cylindrical(s,z1,s.bore1_mm);r=g['r'];d1=2*r
        add('d₁',d1,'mm');add('dₐ₁',2*g['ra'],'mm');add('d𝒻₁',2*g['rf'],'mm');add('dᵦ₁',2*g['rb'],'mm')
        add('mₜ',g['mt'],'mm');add('αₜ',degrees(g['alpha']),'°')
        ft=1000*torque/r;add('Fₜ',ft,'N');add('Fᵣ',ft*tan(g['alpha']),'N')
        if s.kind in ('helical','herringbone'):
            g2=cylindrical(s,z2,s.bore2_mm);d2=2*g2['r'];a=r+g2['r']
            path=sqrt(g['ra']**2-g['rb']**2)+sqrt(g2['ra']**2-g2['rb']**2)-a*sin(g['alpha'])
            eps=path/(pi*g['mt']*cos(g['alpha']))
            overlap=s.width_mm*sin(g['beta'])/(pi*m)/(2 if s.kind=='herringbone' else 1)
            add('β',s.helix_deg,'°');add('εα',eps);add('εβ (yarım yüz)' if s.kind=='herringbone' else 'εβ',overlap)
            add('εγ',eps+overlap);add('a',a,'mm')
            add('Fₐ (her yarı)' if s.kind=='herringbone' else 'Fₐ',ft*tan(g['beta'])/(2 if s.kind=='herringbone' else 1),'N')
            if s.kind=='herringbone':add('Fₐ net (ideal)',0,'N')
            if path<=0 or eps<1:raise ValueError('Alın düzleminde sürekli kavraşma sağlanmıyor.')
        elif s.kind=='rack':
            add('p',pi*m,'mm');add('L kremayer',pi*m*s.rack_teeth,'mm')
            add('v kremayer',pi*d1*n/60,'mm/s');add('s / tur',pi*d1,'mm')
            add('Montaj yüksekliği',r,'mm');ratio=None;n2=None
            if s.rack_base_mm<=1.25*m:raise ValueError('Kremayer taban yüksekliği 1,25m üstünde olmalı.')
            if m-pi*m/4/tan(alpha)>=0:raise ValueError('Kremayer diş üstü kalınlığı pozitif değil.')
        elif s.kind=='internal':
            ring_checks(s,z2,z1);d2=m*z2;n2=n/ratio
            add('a',(d2-d1)/2,'mm');add('dₐ₂',m*(z2-2),'mm');add('d𝒻₂',m*(z2+2.5),'mm')
        else:
            zp=z2;zr=z1+2*zp
            if zr>300:raise ValueError('Planet halka diş sayısı 300 sınırını aşıyor.')
            cylindrical(s,zp,s.bore2_mm);ring_checks(s,zr,zp)
            if (z1+zr)%s.planets:raise ValueError('(Güneş + halka diş sayısı) / planet adedi tam sayı olmalı.')
            orbit=m*(z1+zp)/2
            if 2*orbit*sin(pi/s.planets)<=m*(zp+2):raise ValueError('Komşu planet dişliler çarpışıyor.')
            ratio=1+zr/z1;n2=n/ratio
            add('z halka',zr);add('a planet',orbit,'mm');add('n planet (mutlak)',n2-(n-n2)*z1/zp,'dev/dak')
            add('n halka',0,'dev/dak');add('N planet',s.planets)
            warnings.append('Taşıyıcı ve rulmanlar çizilmez; kuvvetler toplam güneş yüküdür, eşit planet yük paylaşımı varsayılmaz.')
        if s.kind!='rack':add('d₂',d2 if s.kind!='planetary' else m*z2,'mm')
    elif s.kind in ('bevel','spiral_bevel'):
        sigma=radians(s.shaft_angle_deg);delta1=atan2(sin(sigma),z2/z1+cos(sigma));delta2=sigma-delta1
        if not 0<delta1<pi/2 or not 0<delta2<pi/2:raise ValueError('Bu hesap iki dar bölüm konisi gerektirir.')
        R=d1/(2*sin(delta1))
        if s.width_mm>R/3:raise ValueError('Konik dişlide yüz genişliği dış koni mesafesinin üçte birini aşmamalı.')
        add('δ₁',degrees(delta1),'°');add('δ₂',degrees(delta2),'°');add('R dış',R,'mm');add('R orta',R-s.width_mm/2,'mm')
        add('d₁ dış bölüm',d1,'mm');add('d₂ dış bölüm',d2,'mm')
        if s.kind=='bevel':
            add('dₐ₁',d1+2*m*cos(delta1),'mm');add('dₐ₂',d2+2*m*cos(delta2),'mm')
        else:
            warnings.append('m dış alın modülüdür. Spiral diş kalınlığı, baş/dip payı ve yüzeyler kesici sistemine bağlı olduğundan hesaplanmaz.')
    elif s.kind=='worm':
        ratio=z2/s.worm_starts;n2=n/ratio;gamma=atan(s.worm_starts/s.diameter_quotient)
        d1=m*s.diameter_quotient
        add('d vida',d1,'mm');add('d çark',d2,'mm');add('a',(d1+d2)/2,'mm')
        add('γ',degrees(gamma),'°');add('mₙ',m*cos(gamma),'mm');add('pₓ',pi*m,'mm');add('İlerleme',pi*m*s.worm_starts,'mm/tur')
        warnings.append('m eksenel modüldür. Çıkış yönü sağ/sol ağız ve eksen seçimine bağlıdır; n₂ yalnız büyüklüktür. Kendinden kilitleme/verim sonucu verilmez.')
        n2=abs(n2)
    elif s.kind=='hypoid':
        warnings.append('Ofset tek başına yüzey tasarımını belirlemez; modülden çap veya konik dişli formülüyle hipoid yüzeyi türetilmez. n₂ yalnız büyüklüktür.')
        n2=abs(n2);add('E ofset',s.offset_mm,'mm')
    elif s.kind=='cycloidal':
        N=z2;R=m*N/2;e=s.eccentricity_mm;roller=s.roller_radius_mm
        if e*N>=R:raise ValueError('Pim zarfı sivrilmemesi için e·N < pim dairesi yarıçapı olmalı.')
        if roller>=R*sin(pi/N):raise ValueError('Komşu pimler çarpışıyor.')
        if R-e-roller-s.bore1_mm/2<max(.2,.1*m):raise ValueError('Sikloid disk deliği için yeterli et yok.')
        ratio=N-1;n2=-n/ratio
        add('N pim',N);add('z disk',N-1);add('R pim',R,'mm');add('e',e,'mm');add('F eksantrik (ideal)',1000*torque/e,'N')
    if ratio is not None:
        add('i',ratio);add('n₂',n2,'dev/dak');add('T₂ ideal',torque*ratio,'N·m')
    if not cad:warnings.append('CAD ve hareket kapalı: eşlenik yüzey doğrulanmadı; bu tür henüz tamamlanmış değildir.')
    if any(not isfinite(v) for key,v,unit in rows):raise ValueError('Hesap sonlu olmayan sonuç üretti.')
    return MechanismResult(s,tuple(rows),tuple(warnings),cad)


def ring_checks(s,zr,zp):
    rb=s.module_mm*zr/2*cos(radians(20));ra=s.module_mm*(zr-2)/2
    if ra<=rb or zr-zp<=9:raise ValueError('İç dişli temel daire veya küçük diş farkı girişim sınırını ihlal ediyor.')
    alpha_tip=atan(sqrt(ra*ra-rb*rb)/rb)
    if zp/zr < 1-tan(alpha_tip)/tan(radians(20)):
        raise ValueError('İç dişli evolvent girişimi var.')
