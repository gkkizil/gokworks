"""Public source catalogue and independent model definitions; no downloaded engine code."""
from collections import defaultdict
from functools import lru_cache
import json
import math
from pathlib import Path
from .models import FieldSchema,FrozenMap,ShapeSchema,ShapeSummary


@lru_cache(maxsize=1)
def inventory():
    path=Path(__file__).resolve().parents[2]/'docs/unfolding/unfoldo_inventory.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    ids=[m['source_id'] for m in data['models']]
    if len(ids)!=191 or len(set(ids))!=191 or sum(len(m['fields']) for m in data['models'])!=1136:
        raise ValueError('Kaynak envanteri kontrol toplamı geçersiz.')
    return data


def model(identifier):
    try:return next(m for m in inventory()['models'] if m['source_id']==identifier)
    except StopIteration:raise ValueError('Kaynak model kimliği bulunamadı.') from None


def normalize_options(request,schema,scale):
    m=model(schema.source_id);flags=m['source_features'];given=dict(request.model_options)
    allowed={'cut_type','helper_divisions','numbering'}
    if flags.get('lap'):allowed.update(('lap_top','lap_bottom','lap_left','lap_right'))
    if flags.get('stripLap'):allowed.add('strip_lap')
    if flags.get('heel'):allowed.add('heel')
    if set(given)-allowed:raise ValueError('Modelde desteklenmeyen seçenek: '+', '.join(sorted(set(given)-allowed)))
    cut=given.get('cut_type',m['cut_options'][0]['value'])
    if cut not in [x['value'] for x in m['cut_options']]:raise ValueError('Modelin kesim/dikiş seçeneği geçersiz.')
    if request.split_options.count!=1:raise ValueError('Kaynak modellerde parça adedi cut_type veya kaynak parts alanıyla seçilir.')
    if not schema.seam_supported and request.seam_options.start_angle_deg:
        raise ValueError('Bu modelde ortak dikiş dönüşü yok; modele özgü seam alanını/kesim seçeneğini kullanın.')
    divisions=given.get('helper_divisions',24)
    if type(divisions) is not int or divisions not in (12,24,36,48,72,96):raise ValueError('Yardımcı bölme sayısı 12/24/36/48/72/96 olmalı.')
    numbering=given.get('numbering',not flags.get('noNumbers',False))
    if type(numbering) is not bool or flags.get('noNumbers') and numbering:raise ValueError('Bu modelde numaralama seçeneği kullanılamaz.')
    out=dict(cut_type=cut,helper_divisions=divisions,numbering=numbering)
    for k in ('lap_top','lap_bottom','lap_left','lap_right','strip_lap'):
        v=given.get(k,0.)
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v*scale<=1e5:raise ValueError('Kenar payı 0–100000 mm aralığında olmalı.')
        if flags.get('lapFields') and k in ('lap_bottom','lap_right') and v:
            raise ValueError('Kanallarda yalnız lap_top (iki uzun kenar) ve lap_left (iki duvar ucu) kullanılır.')
        out[k]=v*scale
    heel=given.get('heel',False)
    if type(heel) is not bool:raise ValueError('Topuk seçimi boolean olmalı.')
    out['heel']=heel
    if 'seam' in request.parameters and request.seam_options.start_angle_deg:
        raise ValueError('Kaynak seam alanıyla ortak dikiş açısı birlikte kullanılamaz.')
    return out


class SourceDefinition:
    split=True
    lap=True
    def __init__(self,models):
        self.models={m['source_id']:m for m in models}
        first=models[0]
        self.summary=ShapeSummary(first['internal_id']['shape_id'],first['family'],tuple(self.models),
            'model_specific',first['category'],FrozenMap({m['source_id']:m['variant'] for m in models}),tuple(self.models))
    def schema(self,variant):
        m=self.models.get(variant)
        if m is None:raise ValueError('Bu kaynak varyantı henüz hesaplanabilir değil.')
        fields=[]
        for f in m['fields']:
            kind=f['kind'];choices=tuple(v for v,label in f['options'])
            minimum=f['minimum'] if f['minimum'] is not None else (-360. if kind=='angle' and f['signed'] else -1e7 if f['signed'] else 0.)
            fields.append(FieldSchema(f['id'],f['label'],f['label'],
                type='integer' if kind in ('count','option') else 'number',
                unit={'angle':'deg','count':'count','option':'option'}.get(kind,'length'),default=f['default'],
                minimum=minimum,maximum=256 if kind=='count' else max(choices) if choices else 360. if kind=='angle' else 1e7,
                choices=choices,dimension_id=f['symbol']))
        from .shapes.source_dispatch import references,method_for
        refs=references(m)
        flags=m['source_features']
        seam=(m['family'] in ('Koni','Eğik silindir','Eğik koni','Düzlemle kesilen koni') or m['category'] in ('Geçiş parçaları','Segmentli dirsekler','Dirsekler')
              or m['category']=='Branşmanlar ve T parçalar' and m['source_id'].endswith('-trunk')
              or m['family']=='Silindir' and not any(f.id=='seam' for f in fields))
        return ShapeSchema(self.summary.shape_id,variant,m['name'],tuple(fields),
            ('Kaynak varsayılanları örnektir; fiziksel sınırlar ayrıca doğrulanır.',
             'Yardımcı bölme adedi eğri toleransından bağımsızdır.',method_for(m)),seam,False,
            ('butt','lap') if flags.get('lap') else ('butt',),('json','dxf','pdf','zip'),refs,m['source_id'],
            FrozenMap(dict(cut_options=m['cut_options'],source_features=flags,
                           parameter_options={f['id']:f['options'] for f in m['fields'] if f['options']},
                           option_support=dict(heel=False,edge_allowances=bool(flags.get('lap')),strip_lap=bool(flags.get('stripLap'))),
                           length_options=('lap_top','lap_bottom','lap_left','lap_right','strip_lap'),
                           helper_divisions=(12,24,36,48,72,96),source_url=m['source_url'])))
    def normalize(self,p,t,ref,variant):
        from .shapes.source_dispatch import normalize
        return normalize(model(variant),p,t,ref)
    def build(self,n,material,options,token=None):
        from .shapes.source_dispatch import build
        return build(model(n['variant_id']),n,material,options,token)


def definitions():
    from .shapes.source_dispatch import supported
    groups=defaultdict(list)
    for m in inventory()['models']:
        if supported(m):groups[m['family']].append(m)
    return tuple(SourceDefinition(ms) for ms in groups.values())
