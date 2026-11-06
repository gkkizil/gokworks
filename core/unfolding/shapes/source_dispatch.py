"""Model-specific conversions and capability dispatch; unimplemented IDs fail closed."""
from dataclasses import replace
import math
from .common import check_cancel

FAMILIES={'Silindir','Oval boru','Eğik silindir','Saca eğik oturan boru','Düzlemle kesilen koni','Düz kanal','Kanal redüksiyonu','Kanal S parçası','Kanal branşmanı','Kanal Y parçası','Kanal dirseği','Koni','Eğik koni','Prizma','Piramit','Tank bombesi','Helezon kanat','Helezon yaprağı',
    'Dikdörtgenden yuvarlağa','Dikdörtgen redüksiyon','Yuvarlak redüksiyon','Ovalden yuvarlağa','Oval redüksiyon','Ovalden dikdörtgene',
    'Elipsten yuvarlağa','Elips redüksiyon','Elipsten dikdörtgene','Altıgenden yuvarlağa','Sekizgenden yuvarlağa'}


SUPPORTED_FAMILIES=FAMILIES|{
    'Yağmur haznesi','Kanal ayırıcı','Boru pantolon','Redüksiyonlu pantolon',
    'Segmentli dirsek, yuvarlak','Segmentli dirsek, oval','Segmentli dirsek, yatık oval','Segmentli dirsek, redüksiyonlu',
    'Gönye dirsek, boru','Gönye dirsek, boru-koni','Gönye dirsek, koni-koni','Gönye dirsek, koni-boru',
    'Boru branşmanı','Borudan koniye','Borudan eğik koniye','Koniden koniye','Koniden eğik koniye','Koniden boruya',
    'Dikdörtgenden boruya','Dikdörtgenden koniye','Dikdörtgenden eğik koniye','Borudan dirseğe'}


def supported(m):return m['family'] in SUPPORTED_FAMILIES


def references(m):
    return ('inner','mid','outer') if m['family'] in ('Silindir','Oval boru','Koni','Prizma') else ('mid',)


def method_for(m):
    if m['family'] in ('Silindir','Oval boru','Koni','Prizma'):return 'analytic_developable' if m['source_id'] in ('cylinder','oval-cylinder','cone','cone-frustum','cone-frustum-apex-height','cone-frustum-angle','cone-frustum-levels','prism') else 'sampled_developable'
    if m['family'] in ('Tank bombesi','Helezon kanat','Helezon yaprağı'):return 'formed_approximation'
    if m['category'] in ('Branşmanlar ve T parçalar','Segmentli dirsekler','Dirsekler') or m['family'] in ('Saca eğik oturan boru','Düzlemle kesilen koni','Yağmur haznesi','Boru pantolon') or '-3-' in m['source_id']:
        return 'sampled_developable'
    if m['category']=='Dikdörtgen kanallar' or m['family']=='Piramit':return 'analytic_developable'
    return 'faceted_real_length'


def normalize(m,p,t,ref):
    p=dict(p);s=m['source_id'];family=m['family']
    if ref not in references(m):raise ValueError('Bu modelde doğrulanmış normal offset yok; orta yüzey (mid) ölçüleri kullanın.')
    # Strict profile/positive primary dimensions; offsets, radii, skirts and openings may be zero.
    field_kinds={f['id']:f['kind'] for f in m['fields']}
    for k in ('D','d','Dt','Db','db','D1','D2','W','w','W1','W2','Wt','L','Lt','Lc','H','H1','H2','Ha','Hc','AF','hRight','Hr','P'):
        if k=='d' and family in ('Koni','Piramit') and p.get(k)==0:continue  # true full-cone/pyramid limit
        if k in p and field_kinds.get(k)=='length' and p[k]<=0:raise ValueError(k+': pozitif ölçü gerekli.')
    for f in m['fields']:
        orientation=f['id'] in ('seam','turn','P') or f['label']=='Plan açısı'
        if f['kind']=='angle' and not orientation and abs(p[f['id']])>=180:
            raise ValueError(f['id']+': açı tekil veya ters yüzey oluşturuyor.')
    change={'inner':t,'mid':0.,'outer':-t}[ref]
    if family=='Silindir':
        if s=='cylinder-angled-top':p['_plane_slope']=(p['H2']-p['H1'])/p['D']
        if s=='cylinder-top-angle-side':p['_center_height']=p['H']+p['D']/2*abs(math.tan(math.radians(p['A'])))
        p['D']+=change
        if p['D']<=t:raise ValueError('Kalınlık iç çapı sıfır/negatif yapıyor.')
    elif family=='Oval boru':
        p['L']+=change;p['W']+=change
        if p['W']<=t:raise ValueError('Oval iç yarıçap/kalınlık ilişkisi geçersiz.')
    elif family=='Koni':
        d=p.get('d',0.)
        if p['D']<d:raise ValueError('Alt çap üst çaptan küçük olamaz.')
        if 'Ha' in p:p['H']=p['Ha']*(p['D']-d)/p['D']
        if s.endswith('-angle'):
            if not 0<p['A']<180:raise ValueError('Koni tam tepe açısı (0,180) arasında olmalı.')
            p['H']=(p['D']-d)/(2*math.tan(math.radians(p['A']/2)))
        if p['H']<=0:raise ValueError('Koni yüksekliği pozitif olmalı; eşit çapta H girişi kullanın.')
        if not d and t and ref!='mid':raise ValueError('Tam koninin tepe offseti doğrulanmadı; mid kullanın.')
        delta=change*math.hypot(1.,(p['D']-d)/(2*p['H']));p['D']+=delta
        if d:p['d']=d+delta
        if p['D']<=t or d and p['d']<=t*math.hypot(1.,(p['D']-p['d'])/(2*p['H'])):raise ValueError('Koni offseti iç açıklığı yok ediyor.')
    elif family=='Prizma':
        p['D']+=change/math.cos(math.pi/p['n'])
        if p['D']*math.cos(math.pi/p['n'])<=t:raise ValueError('Prizma iç kesiti kalınlıkla kapanıyor.')
    elif family=='Eğik silindir' and s.endswith('-angle'):
        if not 0<p['A']<=90:raise ValueError('Tabana açı (0,90] olmalı.')
        p['H']=p['Lc']*math.sin(math.radians(p['A']));p['X']=p['Lc']*math.cos(math.radians(p['A']))
    elif family=='Eğik koni':
        if p['D']<=p['d']:raise ValueError('Eğik konide alt çap üst çaptan büyük olmalı.')
        if s.endswith('upright-side'):p['X']=(p['D']-p['d'])/2
    if family=='Silindir' or family=='Oval boru':
        for k in ('A','B','A1','A2'):
            if k in p and abs(p[k])>=89.9:raise ValueError('Düzlem kesim açısı ±89.9° sınırında tekilleşir.')
    return p


def build(m,n,material,options,token=None):
    check_cancel(token);family=m['family']
    if family=='Yağmur haznesi':
        from .source_complex import build_rain_head
        out,q=build_rain_head(m,n,material,options,token)
    elif family=='Redüksiyonlu pantolon':
        from .source_complex import build_reducing_breech
        out,q=build_reducing_breech(m,n,material,options,token)
    elif family=='Borudan dirseğe':
        from .source_complex import build_torus_branch
        out,q=build_torus_branch(m,n,material,options,token)
    elif m['category']=='Segmentli dirsekler':
        from .source_bends import build_segmented
        out,q=build_segmented(m,n,material,options,token)
    elif m['category']=='Dirsekler':
        from .source_bends import build_miter
        out,q=build_miter(m,n,material,options,token)
    elif m['category']=='Dikdörtgen kanallar':
        from .source_ducts import build_duct
        out,q=build_duct(m,n,material,options,token)
    elif family=='Saca eğik oturan boru':
        from .source_planes import build_plate_pipe
        out,q=build_plate_pipe(m,n,material,options,token)
    elif family=='Düzlemle kesilen koni':
        from .source_planes import build_cut_cone
        out,q=build_cut_cone(m,n,material,options,token)
    elif family=='Boru pantolon' or family=='Boru branşmanı' and not m['source_id'].endswith(('-branch','-trunk')):
        from .source_intersections import multi_pipe_parts
        out,q=multi_pipe_parts(m,n,material,options,token)
    elif m['category']=='Branşmanlar ve T parçalar':
        from .source_intersections import build_branch
        out,q=build_branch(m,n,material,options,token)
    elif family in ('Silindir','Oval boru'):
        from .source_extrusions import build_cylinder
        out,q=build_cylinder(m,n,material,options,token)
    elif family=='Prizma':
        from .source_extrusions import build_prism
        out,q=build_prism(m,n,material,options,token)
    elif family=='Koni':
        from .source_lofts import build_cone
        out,q=build_cone(m,n,material,options,token)
    elif family=='Piramit':
        from .source_lofts import build_pyramid
        out,q=build_pyramid(m,n,material,options,token)
    elif family=='Tank bombesi':
        from .source_formed import build_head
        out,q=build_head(m,n,material,options,token)
    elif family.startswith('Helezon'):
        from .source_formed import build_helix
        out,q=build_helix(m,n,material,options,token)
    elif family in FAMILIES:
        from .source_lofts import build_loft
        out,q=build_loft(m,n,material,options,token)
    else:raise ValueError('Kaynak model için doğrulanmış hesap yöntemi henüz yok: '+m['source_id'])
    if not n['model_options']['numbering']:
        out=tuple(replace(part,construction_lines=tuple(replace(line,id='') for line in part.construction_lines),
                          bending_lines=tuple(replace(line,id='') for line in part.bending_lines),true_lengths=()) for part in out)
    q.update(source_id=m['source_id'],calculation_method=method_for(m),bend_direction_evaluated=False)
    return out,q
