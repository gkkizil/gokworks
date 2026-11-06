"""Shape schemas and normal-reference conversions at fixed end measurement planes."""
from dataclasses import dataclass
import math
from .models import FieldSchema,ShapeSchema,ShapeSummary,FrozenMap
from .shapes import cylinder,cone,transitions,elbow


def length(key,label,default,description=''):
    return FieldSchema(key,label,description or label,default=default,dimension_id=key)


def angle(key,label,default,minimum,maximum):
    return FieldSchema(key,label,label,unit='deg',default=default,minimum=minimum,maximum=maximum,dimension_id=key)


def radial(p,t,ref,variant):
    p=dict(p);p['diameter'] += {'inner':t,'mid':0.,'outer':-t}[ref]
    if p['diameter']<=t: raise ValueError('Kalınlık iç yarıçapı sıfır veya negatif yapıyor.')
    if variant=='bevel' and p['height']<=p['diameter']/2*abs(math.tan(math.radians(p['cut_angle_deg']))):
        raise ValueError('Eğik kesim alt düzlemi geçiyor; minimum yükseklik pozitif olmalı.')
    return p


def conical(p,t,ref,variant):
    p=dict(p);p.setdefault('top_diameter',0.)
    if p['bottom_diameter']<p['top_diameter']: raise ValueError('Taban çapı üst çaptan küçük olamaz.')
    if variant=='full' and t>0 and ref!='mid':
        raise ValueError('Tam konide kalınlıklı iç/dış tepe bitişi v1 kapsamında değil; orta yüzey ölçüsü kullanın.')
    slope=(p['bottom_diameter']-p['top_diameter'])/(2*p['height'])
    change={'inner':1.,'mid':0.,'outer':-1.}[ref]*t*math.hypot(1.,slope)
    p['bottom_diameter']+=change;p['top_diameter']+=change
    if p['bottom_diameter']<=t or p['top_diameter']<0:
        raise ValueError('Konide normal offset, pozitif olmayan yarıçap oluşturuyor.')
    if p['top_diameter'] and p['top_diameter']<=t*math.hypot(1.,slope):
        raise ValueError('Üst açıklıkta kalınlık ve iç yarıçap ilişkisi geçersiz.')
    return p


@dataclass(frozen=True)
class Definition:
    summary: ShapeSummary
    variants: tuple
    normalize: object
    build: object
    constraints: tuple[str,...] = ()
    split: bool = True
    lap: bool = True
    dimension_refs: tuple[str,...] = ('inner','mid','outer')

    def schema(self,variant):
        fields=dict(self.variants).get(variant)
        if fields is None: raise ValueError('Bu şekil varyantı uygulanmadı.')
        outputs=('dxf','pdf','zip','json')
        if self.summary.shape_id not in ('segmented_elbow','bent_profile') and not (self.summary.shape_id=='cylinder' and variant=='bevel'):
            outputs+=('step_surface',)
        return ShapeSchema(self.summary.shape_id,variant,self.summary.label,fields,self.constraints,
                           self.split,self.split,('butt','lap') if self.lap else ('butt',),
                           outputs,self.dimension_refs)


CYLINDER=Definition(ShapeSummary('cylinder','Silindir',('straight','bevel'),'analytic_developable'),
    (('straight',(length('diameter','Çap D',300.),length('height','Eksen yüksekliği H',200.))),
     ('bevel',(length('diameter','Çap D',300.),length('height','Kesim düzleminin eksendeki yüksekliği H',200.),
               angle('cut_angle_deg','Kesim eğimi',30.,-80.,80.),angle('plane_azimuth_deg','Kesim düzlemi yönü',0.,-360.,360.)))),
    radial,cylinder.build,('Eğik kesim z=H−r·tan(β)·cos(θ−azimut); tüm çevrede z>0 olmalı.',))

CONE=Definition(ShapeSummary('cone','Konsantrik koni',('full','frustum'),'analytic_developable'),
    (('full',(length('bottom_diameter','Taban çapı D',300.),length('height','Dik yükseklik H',200.))),
     ('frustum',(length('bottom_diameter','Taban çapı D',300.),length('top_diameter','Üst çap d',150.),length('height','Dik yükseklik H',200.)))),
    conical,cone.build,('D≥d. Ölçüler sabit z=0/H düzlemlerinde alınır; offset normal mesafeyi korur.',
                       'Tam koni t>0 için yalnız mid ölçü yüzeyi; eşit çap sınırı silindire çözülür.'))

RECT=Definition(ShapeSummary('rectangular_reducer','Dikdörtgen redüksiyon',('centered',),'analytic_developable'),
    (('centered',tuple(length(k,label,default) for k,label,default in (
        ('bottom_width','Taban genişliği',400.),('bottom_depth','Taban derinliği',300.),
        ('top_width','Üst genişlik',200.),('top_depth','Üst derinlik',150.),('height','Dik yükseklik',300.)))),),
    transitions.normalize_rect,transitions.build_rect,('Dört ayrı düz trapez panel; keskin köşeler için abkant telafisi uygulanmaz.',),False,False)

ROUND=Definition(ShapeSummary('rect_to_round','Kare/dikdörtgen–yuvarlak geçiş',('centered_faceted',),'faceted_developable'),
    (('centered_faceted',(length('width','Dikdörtgen genişliği',400.),length('depth','Dikdörtgen derinliği',300.),
                         length('diameter','Yuvarlak uç çapı',250.),length('height','Dik yükseklik',300.))),),
    transitions.normalize_round,transitions.build_round,
    ('Dört düz üçgen ve dört fasetli köşe yaması: 8 ayrı panel. Üst çevre, kord hata sınırıyla yaklaşılır.',
     'Kalınlıklı inner/outer normal offset ve köşe radyüsü v1 kapsamında değil.'),False,False,('mid',))

ELBOW=Definition(ShapeSummary('segmented_elbow','Segmentli dirsek',('constant_diameter',),'analytic_developable'),
    (('constant_diameter',(length('diameter','Boru çapı',200.),length('center_radius','Eksen yay yarıçapı',300.),
        angle('total_angle_deg','Toplam dönüş açısı',90.,.001,179.),
        FieldSchema('segments','Toplam segment sayısı','İki uçtaki yarım segment DAHİL; çevresel örnekleme sayısı değildir.',
                    type='integer',unit='count',default=4,minimum=2,maximum=64,dimension_id='segments'),
        FieldSchema('inlet_extension','Giriş uzatması','İlk eksen doğrultusunda düz uzatma.',default=0.,dimension_id='inlet_extension'),
        FieldSchema('outlet_extension','Çıkış uzatması','Son eksen doğrultusunda düz uzatma.',default=0.,dimension_id='outlet_extension'))),),
    elbow.normalize,elbow.build,('N segment, N−1 birleşim ve Δ=toplam açı/(N−1). Uç parçalar yarım dilimdir.',
                               'Eksen yarıçapı boru orta yüzey yarıçapından büyük olmalı.'))

DEFINITIONS={d.summary.shape_id:d for d in (CYLINDER,CONE,RECT,ROUND,ELBOW)}
from .forming.profiles import normalize_profile,build_profile


def _profile_fields(count):
    return (length('width','Büküm uzunluğu / parça genişliği',100.),
            *(length(f'flange_{i+1}',f'Flanş {i+1}',50.) for i in range(count+1)),
            *(f for i in range(count) for f in (
                angle(f'bend_{i+1}_deg',f'B{i+1} dönüş açısı (açık açı değil)',90.,-179.,179.),
                length(f'radius_{i+1}',f'B{i+1} iç yarıçap',2.))),
            FieldSchema('length_reference','Flanş ölçüsü: 1 dış / 2 iç / 3 teğet','Sanal keskin köşe veya teğet boyları.',
                        type='integer',unit='option',default=1,minimum=1,maximum=3,choices=(1,2,3),dimension_id='length_reference'))


DEFINITIONS['bent_profile']=Definition(
    ShapeSummary('bent_profile','Abkant · bükümlü profil',('single','double'),'explicit_bend_profile',
                 category='Şekillendirme',variant_labels=FrozenMap({'single':'Tek büküm','double':'İki büküm'})),
    (('single',_profile_fields(1)),('double',_profile_fields(2))),normalize_profile,build_profile,
    ('Pozitif kalınlık ve iç yarıçap; açılar düz sacdan işaretli dönüş açısıdır.',
     'Üretim K/BA/BD verisi yokken yalnız geometrik orta yüzey hesaplanır.'),False,False,('mid',))
from .source_models import definitions as source_definitions
DEFINITIONS.update({d.summary.shape_id:d for d in source_definitions()})


def definition(shape_id):
    try:return DEFINITIONS[shape_id]
    except (KeyError,TypeError):raise ValueError('Bu şekil ailesi henüz uygulanmadı.') from None
