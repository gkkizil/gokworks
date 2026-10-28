"""Nominal sprocket and approximate open-chain mounting calculations, pure Python."""
from math import asin,ceil,degrees,isfinite,pi,sin,sqrt
from .models import ChainSpecification,SprocketSpecification,SprocketPairSpecification,SprocketDimensions,SprocketPairResult,PROFILE
from .catalog import CHAINS,maximum_tooth_width
from ..models import GearPairSpecification
from ..validation import finite,pair_issues,require_valid
from ..calculation import TORQUE_POWER_FACTOR


def dimensions(s):
    """Public ISO arc construction: minimum seat radius, mid seating angle,
    r_e=0.12 d_r(z+2), and lower published tip-diameter limit. See README.
    Actual root includes seating clearance; nominal Dp-dr is reported separately.
    """
    c=s.chain;p=c.pitch_mm;d=c.roller_diameter_mm;z=s.teeth
    dp=p/sin(pi/z);ri=.505*d
    return SprocketDimensions(dp,dp-d,dp-2*ri,dp+(1-1.6/z)*p-d,
        dp+1.25*p-d,ri,.12*d*(z+2),130-90/z,360/z)


def validate_sprocket(s):
    if not isinstance(s,SprocketSpecification) or not isinstance(s.chain,ChainSpecification):
        raise ValueError('Tip güvenli zincir ve zincir dişlisi verisi gerekli.')
    c=s.chain
    for k in ('pitch_mm','roller_diameter_mm','inner_width_mm'):
        if not finite(getattr(c,k)) or getattr(c,k)<=0:raise ValueError('Zincir ölçüleri pozitif ve sonlu olmalı.')
    if c.roller_diameter_mm>=c.pitch_mm:raise ValueError('Makara çapı zincir adımından küçük olmalı.')
    if type(c.series) is not str or type(c.standard) is not str or type(c.strands) is not int or CHAINS.get(c.series)!=c:
        raise ValueError('Zincir standardı/serisi veya ölçüleri doğrulanmış tek sıralı katalogla eşleşmiyor.')
    if type(s.teeth) is not int or not 9<=s.teeth<=120:
        raise ValueError('Zincir diş sayısı 9–120 aralığında tam sayı olmalı (geometri/kaynak sınırı).')
    if s.profile_reference!=PROFILE:raise ValueError('Desteklenmeyen zincir dişi profil referansı.')
    if s.material is not None and (type(s.material) is not str or len(s.material)>120):
        raise ValueError('Malzeme açıklaması en çok 120 karakter olmalı.')
    for k in ('width_mm','bore_mm','hub_diameter_mm','hub_length_mm'):
        if not finite(getattr(s,k)):raise ValueError('Dişli ölçüleri sonlu sayı olmalı.')
    if not .5<=s.width_mm<=maximum_tooth_width(c):
        raise ValueError(f'Diş genişliği 0,5–{maximum_tooth_width(c):.4f} mm olmalı; zincir iç genişliğine boşluk bırakın.')
    g=dimensions(s);wall=max(1.,.05*c.pitch_mm)
    if s.bore_mm!=0 and s.bore_mm<1:raise ValueError('Delik 0 (dolu) veya en az 1 mm olmalı.')
    if s.bore_mm<0 or s.bore_mm>g.profile_root_diameter_mm-2*wall:
        raise ValueError('Delik diş dibi altında yeterli radyal et bırakmıyor.')
    hub=s.hub_diameter_mm;length=s.hub_length_mm
    if (hub==0)!=(length==0):raise ValueError('Göbek çapı ve toplam uzunluğu birlikte girilmeli veya ikisi de 0 olmalı.')
    if hub and (not s.bore_mm+2*wall<=hub<=g.profile_root_diameter_mm-2*wall or not s.width_mm<=length<=500):
        raise ValueError('Göbek deliğe ve diş dibine et bırakmalı; toplam uzunluk diş genişliği–500 mm aralığında olmalı.')


def links_for_center(p,z1,z2,center):
    if not finite(center) or center<=0:raise ValueError('Eksen mesafesi pozitif ve sonlu olmalı.')
    x=center/p
    return 2*x+(z1+z2)/2+(z2-z1)**2/(4*pi*pi*x)


def center_for_links(p,z1,z2,links,minimum_center):
    """Bisection on the physical, increasing branch of the approximate equation.
    Returns an approximate mounting distance, NOT an exact discrete-chain solve.
    """
    low=max(minimum_center,p*abs(z2-z1)/(2*pi*sqrt(2)))
    if links<links_for_center(p,z1,z2,low)-1e-10:
        raise ValueError('Bakla sayısı ayrık dişliler için yeterli eksen mesafesi sağlamıyor.')
    high=max(low,p*links)
    for _ in range(80):
        mid=(low+high)/2
        if links_for_center(p,z1,z2,mid)<links:low=mid
        else:high=mid
    return (low+high)/2


def calculate(s):
    if not isinstance(s,SprocketPairSpecification):raise ValueError('SprocketPairSpecification gerekli.')
    validate_sprocket(s.driver);validate_sprocket(s.driven)
    if s.driver.chain!=s.driven.chain:raise ValueError('İki zincir dişlisi aynı standart ve zincir serisini kullanmalı.')
    require_valid(pair_issues(GearPairSpecification(load=s.load)))
    g1,g2=dimensions(s.driver),dimensions(s.driven);p=s.driver.chain.pitch_mm
    # Conservative 1 mm between tip envelopes; no strength/shaft-clearance claim.
    minimum=(g1.outside_diameter_mm+g2.outside_diameter_mm)/2+1
    if s.mounting_mode=='center':
        C=s.center_distance_mm
        if s.link_count is not None:raise ValueError('Eksen mesafesi modunda bakla sayısı ikincil sonuç olmalı.')
        if not finite(C) or not minimum<C<=10000:raise ValueError(f'Eksen mesafesi {minimum:.4f} mm üstünde, en çok 10000 mm olmalı.')
        theoretical=links_for_center(p,s.driver.teeth,s.driven.teeth,C)
        links=2*ceil((theoretical-1e-10)/2)
    elif s.mounting_mode=='links':
        if s.center_distance_mm is not None:raise ValueError('Bakla modunda eksen mesafesi ikincil sonuç olmalı.')
        links=s.link_count
        if type(links) is not int or not 4<=links<=2000:raise ValueError('Bakla sayısı 4–2000 aralığında tam sayı olmalı.')
        theoretical=float(links)
    else:raise ValueError('Montaj girdisi eksen mesafesi veya bakla sayısı olmalı.')
    if links>2000:raise ValueError('Zincir 2000 bakla kaynak sınırını aşıyor.')
    corrected=center_for_links(p,s.driver.teeth,s.driven.teeth,links,minimum)
    if not minimum<corrected<=10000:raise ValueError('Düzeltilmiş eksen mesafesi desteklenen montaj sınırının dışında.')
    load=s.load;n=load.input_rpm;i=s.driven.teeth/s.driver.teeth
    torque=TORQUE_POWER_FACTOR*load.power_kw/abs(n) if load.mode=='power' else load.torque_nm
    power=load.power_kw if load.mode=='power' else torque*abs(n)/TORQUE_POWER_FACTOR
    v=p*s.driver.teeth*abs(n)/60000
    alpha=asin(abs(g2.pitch_diameter_mm-g1.pitch_diameter_mm)/(2*corrected))
    warnings=['Yaklaşık açık zincir montajı; tam baklaya göre C yeniden çözüldü. Gergi, tolerans ve uzama payı hesaplanmaz.',
        'Ortalama oranla rijit dişli kinematiği; gerçek zincir hareketi, poligonal etki ve dinamik yükler simüle edilmez.',
        'Ft etkin kuvvet farkıdır; gergin/gevşek kol kuvvetleri, dayanım, ömür ve verim hesabı değildir.',
        'Dairesel yaylı nominal profil; imalat toleransı, yan pah/rölyef ve ISO tam uygunluk onayı verilmez.']
    if links%2:warnings.append('Tek bakla sayısı özel/offset bağlantı gerektirebilir; üretici uygunluğunu doğrulayın.')
    if min(s.driver.teeth,s.driven.teeth)<17:warnings.append('17 diş altında poligonal etki artar; hız ve çalışma koşulları ayrıca değerlendirilmeli.')
    if degrees(pi-2*alpha)<120:warnings.append('Küçük dişlide sarılma açısı 120° altında; montajı/gergiyi değerlendirin.')
    if not 30<=corrected/p<=50:warnings.append('Eksen mesafesi 30–50 adım öneri aralığının dışında; montaj değerlendirmesi gerekir.')
    r=SprocketPairResult(s,g1,g2,i,n/i,power,torque,torque*i,v,1000*power/v,
        theoretical,links,corrected,links*p,degrees(pi-2*alpha),degrees(pi+2*alpha),tuple(warnings))
    if any(not isfinite(value) for key,value,unit in r.values):raise ValueError('Hesap sonlu olmayan sonuç üretti.')
    return r
