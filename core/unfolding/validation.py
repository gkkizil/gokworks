"""Strict input checks; unit conversion and normal-offset conversion happen once."""
import math
from .models import Issue,ValidationReport,FrozenMap,UnfoldRequest,to_data
from .registry import definition


def number(value,name,minimum=0.,strict=False,maximum=1e7):
    if type(value) not in (int,float) or not math.isfinite(value) or value<minimum or value>maximum or strict and value==minimum:
        raise ValueError(f'{name}: {minimum:g}–{maximum:g} aralığında sonlu {"pozitif " if strict else ""}sayı gerekli.')
    return float(value)


def integer(value,name,low=1,high=64):
    if type(value) is not int or not low<=value<=high:raise ValueError(f'{name}: {low}–{high} arasında tam sayı gerekli.')
    return value


def validate(request):
    if not isinstance(request,UnfoldRequest):return ValidationReport((Issue('REQUEST_TYPE','UnfoldRequest gerekli.'),))
    active=('schema_version',)
    try:
        if type(request.schema_version) is not int or request.schema_version!=1:raise ValueError('Yalnız istek şeması v1 desteklenir.')
        active=('revision',);integer(request.revision,'Revizyon',0,2**31-1)
        active=('request_id',)
        if not isinstance(request.request_id,str) or not 1<=len(request.request_id)<=128 or any(ord(c)<32 for c in request.request_id):
            raise ValueError('İstek kimliği 1–128 görünür karakter olmalı.')
        active=('input_units',)
        if request.input_units not in ('mm','inch'):raise ValueError('Giriş birimi mm veya inch olmalı.')
        active=('dimension_reference',)
        if request.dimension_reference not in ('inner','mid','outer'):raise ValueError('Ölçü yüzeyi inner/mid/outer olmalı.')
        scale=25.4 if request.input_units=='inch' else 1.
        active=('shape_id','variant_id');d=definition(request.shape_id);schema=d.schema(request.variant_id)
        active=('parameters',)
        known={f.id for f in schema.fields}
        if set(request.parameters)!=known:raise ValueError('Eksik veya tanımsız parametre: '+', '.join(sorted(known^set(request.parameters))))
        p={}
        source=bool(schema.source_id)
        for f in schema.fields:
            active=('parameters.'+f.id,)
            v=request.parameters[f.id]
            if f.choices and (type(v) not in (int,float,str) or v not in f.choices):
                raise ValueError(f'{f.label}: tanımlı seçeneklerden biri gerekli.')
            if f.type=='integer':p[f.id]=integer(v,f.label,int(f.minimum),int(f.maximum))
            else:
                if type(v) not in (int,float) or not math.isfinite(v):raise ValueError(f'{f.label}: sonlu sayı gerekli.')
                # Field-schema length bounds are millimetres, including positive
                # source minima. Applying them before conversion rejects valid inches.
                p[f.id]=number(v*scale if f.unit=='length' else v,f.label,
                    minimum=f.minimum,maximum=f.maximum,
                    strict=f.unit=='length' and not source and f.default!=0.)
        active=('thickness',);t=number(number(request.thickness,'Kalınlık')*scale,'Kalınlık')
        active=('seam_options.start_angle_deg',)
        seam=number(request.seam_options.start_angle_deg,'Dikiş açısı',-360.,maximum=360.)
        active=('split_options.count',);split=integer(request.split_options.count,'Bölme adedi')
        if not d.split and (split!=1 or seam!=0):raise ValueError('Bu aile sabit panel düzeni kullanır; dikiş dönüşü/bölme v1 kapsamında değil.')
        active=('joint_options',);joint=request.joint_options
        overlap=number(number(joint.overlap,'Bindirme payı')*scale,'Bindirme payı')
        if joint.kind not in schema.joint_kinds:raise ValueError('Bu ailede istenen birleşim türü uygulanmadı.')
        if joint.kind=='butt' and overlap or joint.kind=='lap' and overlap<=0:raise ValueError('Alın birleşimde pay 0; bindirmede pay pozitif olmalı.')
        active=('development_options',);o=request.development_options
        number(o.geometry_tolerance_mm,'Geometri toleransı',strict=True,maximum=1.)
        number(o.chord_error_mm,'Kord hatası',strict=True,maximum=100.)
        number(o.mesh_error_mm,'Mesh hatası',strict=True,maximum=100.)
        integer(o.max_samples,'Örnekleme üst sınırı',16,8192)
        if o.geometry_tolerance_mm>o.chord_error_mm:raise ValueError('Geometri toleransı kord hata hedefinden büyük olamaz.')
        if number(o.kerf_mm,'Kerf')!=0:raise ValueError('V1 kerf telafisi uygulamaz; kerf CAM tarafında kalmalı.')
        active=('material',)
        material=request.material
        if not isinstance(material.name,str) or len(material.name)>256:raise ValueError('Malzeme adı geçersiz.')
        if material.density_kg_m3 is not None:number(material.density_kg_m3,'Yoğunluk',strict=True,maximum=1e6)
        if material.unit_price is not None:number(material.unit_price,'Birim fiyat',maximum=1e12)
        if material.price_unit not in ('kg','m2','m'):raise ValueError('Fiyat birimi kg/m2/m olmalı.')
        if not isinstance(material.currency,str) or len(material.currency)>16:raise ValueError('Para birimi kısa metin olmalı.')
        active=('parameters','thickness','dimension_reference')
        reference_parameters=dict(p)
        p=d.normalize(p,t,request.dimension_reference,request.variant_id)
        n=to_data(request);n.update(input_units='mm',thickness=t,parameters=p)
        n.update(dimension_reference='mid',source_dimension_reference=request.dimension_reference,
                 reference_parameters_mm=reference_parameters)
        n['joint_options']['overlap']=overlap
        if source:
            from .source_models import normalize_options
            n['model_options']=normalize_options(request,schema,scale)
        elif request.model_options:raise ValueError('Bu eski modelde model_options tanımlı değil.')
        active=('forming_options',)
        from .forming.mechanics import normalize_options
        n['forming_options']=to_data(normalize_options(request.forming_options))
        warnings=[Issue('GEOMETRIC_MIDSURFACE','Geometrik orta yüzey açınımıdır; yaylanma, uzama ve abkant telafisi hesaplanmadı.',
                        'INFO',('dimension_reference',))]
        if not t or material.density_kg_m3 is None:
            warnings.append(Issue('MASS_NOT_EVALUATED','Kalınlık sıfır veya yoğunluk eksik; kütle hesaplanamaz.','NOT_EVALUATED',('thickness','material.density_kg_m3')))
        if not material.name:warnings.append(Issue('MATERIAL_UNSPECIFIED','Malzeme adı girilmedi.','WARNING',('material.name',)))
        if joint.kind=='lap':warnings.append(Issue('LAP_PREVIEW','Bindirme şeridi 2D kesim konturuna eklenir; 3D görünüm nominal yüzeydir. Bindirmeli STEP v1 kapsamında değil.',
                                                    'INFO',('joint_options',)))
        if request.variant_id=='bevel' or request.shape_id=='segmented_elbow':
            warnings.append(Issue('CURVE_SAMPLING',f'Eğik kesim çizgisi en çok {o.chord_error_mm:g} mm kord hatası hedefiyle polyline üretilir; kesim uzunluğu bu kontura aittir.',
                                  'INFO',('development_options.chord_error_mm',)))
        if request.shape_id=='rect_to_round':
            warnings.append(Issue('FACETED_SURFACE',f'8 ayrı paneldir; köşe yamaları en çok {o.chord_error_mm:g} mm üst çevre kord hatasıyla fasetlenir. Düzgün loft veya şekillendirme çözümü değildir.',
                                  'INFO',('development_options.chord_error_mm',)))
        if source:
            warnings.append(Issue('SOURCE_MODEL_SCOPE','Kaynak katalog tanımıdır; GOKWORKS geometri hesabı bağımsızdır. Üretim süreci veya kaynak hesap motoruyla eşdeğerlik onayı değildir.','INFO'))
        return ValidationReport(warnings=tuple(warnings),normalized_inputs=FrozenMap(n))
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return ValidationReport((Issue('INVALID_INPUT',str(exc),field_ids=active),))
