"""Bend lengths, measured coupon lookup and elastic unloading of a rectangular strip.

Lengths are mm, stresses/moduli MPa, angles signed turns from straight (degrees).
The analytical model is isotropic pure bending with bilinear hardening and elastic
unloading, without axial load, thinning, contact, Bauschinger or anisotropy. It is
an estimate, never machine instructions or a forming-limit certification.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import math

from ..bend_profiles import calibrate_k
from ..models import FrozenMap

PROCESSES = ('air_bending', 'bottoming', 'coining', 'roll_bending', 'segmented_assembly')
METHODS = ('k_factor', 'material_k', 'ba_table', 'bd_table', 'calibrated')
GRADES = ('S235', 'S355', 'DC01', 'DX51D', 'AISI 304', 'AISI 316', 'Alüminyum')


def finite(value, name, low=0., high=1e12, *, positive=False):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value) or positive and value == low:
        raise ValueError(f'{name}: {low:g}–{high:g} aralığında sonlu sayı gerekli.')
    return float(value)


def text(value, name, *, required=False):
    if not isinstance(value, str) or len(value) > 512 or required and not value.strip():
        raise ValueError(f'{name}: geçerli kaynak/kimlik metni gerekli.')
    return value


def _keys(value, allowed, name):
    if not isinstance(value, Mapping) or set(value)-set(allowed):
        raise ValueError(name + ': tanımsız alan veya nesne türü.')
    return dict(value)


def normalize_options(options):
    """Strict, versioned optional payload; *_mm and MPa stay SI irrespective of drawing units."""
    if not isinstance(options,Mapping):raise ValueError('Şekillendirme seçenekleri JSON nesnesi olmalı.')
    if not options:
        return FrozenMap()
    o = _keys(options, ('version', 'process', 'method', 'k_factor', 'material', 'tool', 'grain_direction',
                        'springback', 'table', 'springback_samples', 'strain_limit', 'length_tolerance_mm',
                        'angle_tolerance_deg', 'relax_mesh', 'table_interpolation', 'reference'), 'Şekillendirme')
    defaults = dict(version=1, process='air_bending', method='k_factor', k_factor=None, material={}, tool={},
                    grain_direction='unspecified', springback='none', table=[], springback_samples=[],
                    strain_limit=None, length_tolerance_mm=None, angle_tolerance_deg=None, relax_mesh=False,
                    table_interpolation='exact',reference={})
    o = dict(defaults, **o)
    if type(o['version']) is not int or o['version'] != 1:
        raise ValueError('Şekillendirme şeması yalnız v1 destekler.')
    for key, choices in (('process', PROCESSES), ('method', METHODS),
                         ('grain_direction', ('unspecified', 'along', 'across')),
                         ('springback', ('none', 'analytic', 'calibrated'))):
        if o[key] not in choices:
            raise ValueError(key + ': geçersiz seçim.')
    if type(o['relax_mesh']) is not bool:
        raise ValueError('relax_mesh mantıksal değer olmalı.')
    if o['table_interpolation'] not in ('exact','bilinear'):
        raise ValueError('Tablo interpolasyonu exact veya bilinear olmalı.')
    if o['k_factor'] is not None:
        finite(o['k_factor'], 'K', high=1.)
    for key in ('strain_limit', 'length_tolerance_mm', 'angle_tolerance_deg'):
        if o[key] is not None:
            finite(o[key], key, high=1. if key == 'strain_limit' else 180. if key == 'angle_tolerance_deg' else 1e6, positive=True)
    m = _keys(o['material'], ('grade', 'standard', 'source', 'young_modulus_mpa', 'poisson_ratio',
                             'yield_strength_mpa', 'tensile_strength_mpa', 'hardening_modulus_mpa'), 'Mekanik malzeme')
    for key in ('grade', 'standard', 'source'):
        if key in m: text(m[key], key)
    for key in ('young_modulus_mpa', 'yield_strength_mpa', 'tensile_strength_mpa'):
        if key in m and m[key] is not None: finite(m[key], key, high=1e7, positive=True)
    if m.get('poisson_ratio') is not None: finite(m['poisson_ratio'], 'Poisson', low=-.99, high=.4999)
    if m.get('hardening_modulus_mpa') is not None:
        finite(m['hardening_modulus_mpa'], 'Pekleşme modülü', high=1e7)
        if m.get('young_modulus_mpa') and m['hardening_modulus_mpa'] >= m['young_modulus_mpa']:
            raise ValueError('Teğet pekleşme modülü E’den küçük olmalı.')
    if m.get('yield_strength_mpa') and m.get('tensile_strength_mpa') and m['yield_strength_mpa'] > m['tensile_strength_mpa']:
        raise ValueError('Akma dayanımı çekme dayanımından büyük olamaz.')
    tool = _keys(o['tool'], ('id', 'source', 'punch_radius_mm', 'die_opening_mm', 'die_angle_deg',
                            'minimum_flange_mm', 'minimum_radius_mm'), 'Takım')
    for key, value in tool.items():
        if key in ('id', 'source'): text(value, key)
        elif value is not None:
            finite(value, key, high=179.999 if key == 'die_angle_deg' else 1e7,
                   positive=key in ('die_opening_mm', 'die_angle_deg'))
    for key in ('table', 'springback_samples'):
        if not isinstance(o[key], (list, tuple)) or len(o[key]) > 256:
            raise ValueError(key + ': en çok 256 ölçüm satırı gerekli.')
        rows = []
        for row in o[key]:
            row = _keys(row, ('material_grade', 'process', 'tool_id', 'grain_direction', 'source',
                             'thickness_mm', 'inside_radius_mm', 'angle_deg', 'allowance_mm', 'deduction_mm',
                             'outside_first_mm', 'outside_second_mm', 'measured_flat_mm', 'loaded_angle_deg', 'angle_kind'), key)
            angle_kind=row.get('angle_kind','turn')
            if angle_kind not in ('turn','included'):raise ValueError('Tablo açı türü turn/included olmalı.')
            if angle_kind=='included':
                row['angle_deg']=180-finite(row.get('angle_deg'),'Açık açı',high=179.999,positive=True)
                if 'loaded_angle_deg' in row:row['loaded_angle_deg']=180-finite(row['loaded_angle_deg'],'Yük altı açık açı',high=179.999,positive=True)
            row['angle_kind']='turn'
            for name in ('material_grade', 'process', 'tool_id', 'grain_direction', 'source'):
                text(row.get(name), name, required=True)
            if row['process'] not in PROCESSES or row['grain_direction'] not in ('unspecified', 'along', 'across'):
                raise ValueError('Ölçüm proses/hadde yönü geçersiz.')
            for name in ('thickness_mm', 'inside_radius_mm', 'angle_deg'):
                finite(row.get(name), name, high=179.999 if name == 'angle_deg' else 1e7,
                       positive=name != 'inside_radius_mm')
            if key=='springback_samples':required=('loaded_angle_deg',)
            else:
                required=tuple(name for name in ('allowance_mm','deduction_mm') if name in row)
                coupon=('outside_first_mm','outside_second_mm','measured_flat_mm')
                if any(name in row for name in coupon):required+=coupon
                if not required:raise ValueError('Tablo satırı BA, BD veya tam kupon ölçümü taşımalı.')
            for name in required:
                finite(row.get(name), name, low=-1e7 if name == 'deduction_mm' else 0.,
                       high=179.999 if name == 'loaded_angle_deg' else 1e7, positive=name != 'deduction_mm')
            if key == 'springback_samples' and row['loaded_angle_deg'] < row['angle_deg']:
                raise ValueError('Kalibrasyonda yük altı dönüş açısı nihai açıdan küçük olamaz.')
            rows.append(row)
        o[key] = rows
    o['material'], o['tool'] = m, tool
    if not isinstance(o['reference'],Mapping):raise ValueError('Referans verisi JSON nesnesi olmalı.')
    if o['reference']:
        ref=_keys(o['reference'],('source','part_id','measurements_mm','points_mm','absolute_tolerance_mm','relative_tolerance_percent'),'Katalog karşılaştırması')
        text(ref.get('source'),'Referans kaynağı',required=True);text(ref.get('part_id'),'Referans parça kimliği',required=True)
        for key in ('absolute_tolerance_mm','relative_tolerance_percent'):finite(ref.get(key),key)
        dimensions=ref.get('measurements_mm',{})
        if not isinstance(dimensions,Mapping) or set(dimensions)-{'width','height','cutting_length','nominal_length','compensated_length'}:raise ValueError('Referans boyut kimlikleri geçersiz.')
        for key,value in dimensions.items():finite(value,key,low=-1e12)
        points=ref.get('points_mm',{})
        if not isinstance(points,Mapping) or len(points)>1000:raise ValueError('Referans nokta listesi geçersiz.')
        for key,point in points.items():
            text(key,'Ölçüm noktası',required=True)
            if not isinstance(point,(list,tuple)) or len(point)!=2:raise ValueError('Referans noktası iki mm koordinatı gerektirir.')
            for value in point:finite(value,key,low=-1e12)
        if not dimensions and not points:raise ValueError('Referans en az bir boyut veya nokta içermeli.')
        o['reference']=ref
    return FrozenMap(o)


@dataclass(frozen=True)
class BendValues:
    angle_deg: float
    inside_radius_mm: float
    thickness_mm: float
    k_factor: float
    allowance_mm: float
    outside_setback_mm: float
    inside_setback_mm: float
    deduction_mm: float
    method: str
    source: str
    neutral_axis_from_inside_mm: float
    inner_engineering_strain: float
    outer_engineering_strain: float
    strain_distribution: tuple
    thickness_after_forming_mm: None = None


def _scope(row, o, t, r):
    return (row['material_grade'] == o['material'].get('grade') and row['process'] == o['process']
            and row['tool_id'] == o['tool'].get('id') and row['grain_direction'] == o['grain_direction']
            and math.isclose(row['thickness_mm'], t, rel_tol=0, abs_tol=1e-8)
            and math.isclose(row['inside_radius_mm'], r, rel_tol=0, abs_tol=1e-8))


def bend_values(angle_deg, radius_mm, thickness_mm, options):
    o = normalize_options(options)
    if not o:raise ValueError('Büküm telafisi için açık hesap yöntemi ve veriler gerekli.')
    signed_angle=finite(angle_deg,'Büküm dönüş açısı',low=-179.999,high=179.999)
    angle = finite(abs(signed_angle), 'Büküm dönüş açısı', high=179.999, positive=True)
    r = finite(radius_mm, 'İç yarıçap', high=1e7)
    t = finite(thickness_mm, 'Kalınlık', high=1e7, positive=True)
    rad = math.radians(angle)
    ossb = (r+t)*math.tan(rad/2)
    method = o['method']
    if method in ('k_factor', 'material_k'):
        k = o['k_factor']
        if k is None: raise ValueError('K-Faktör girilmedi; varsayılan malzeme K değeri yok.')
        if method == 'material_k' and not all(isinstance(o['material'].get(k),str) and o['material'][k].strip() for k in ('grade', 'source')):
            raise ValueError('Malzemeye bağlı K için kalite ve veri kaynağı gerekli.')
        source = o['material'].get('source', '') if method == 'material_k' else 'Kullanıcının açık K-Faktör girdisi'
        ba = rad*(r+k*t)
    else:
        payload=('allowance_mm',) if method=='ba_table' else ('deduction_mm',) if method=='bd_table' else ('outside_first_mm','outside_second_mm','measured_flat_mm')
        rows = [row for row in o['table'] if all(k in row for k in payload) and _scope(row, o, t, r)
                and math.isclose(row['angle_deg'], angle, rel_tol=0, abs_tol=1e-8)]
        if not rows and method in ('ba_table','bd_table') and o['table_interpolation']=='bilinear':
            ba,source=_interpolate(o,t,r,angle,ossb)
            k=(ba/rad-r)/t
            if not 0<=k<=1:raise ValueError('İnterpolasyon nötr ekseni sac dışına taşıyor.')
            rn=r+k*t
            return BendValues(signed_angle,r,t,k,ba,ossb,r*math.tan(rad/2),2*ossb-ba,method+'_bilinear',
                              source,k*t,-k*t/rn,(1-k)*t/rn,tuple((i*t/8,(i*t/8-k*t)/rn) for i in range(9)))
        if len(rows) != 1:
            raise ValueError('Malzeme/kalınlık/yarıçap/açı/proses/takım/hadde yönü için tek eşleşen üretim satırı gerekli; ekstrapolasyon yapılmaz.')
        row = rows[0]; source = row['source']
        if method == 'ba_table': ba = row['allowance_mm']
        elif method == 'bd_table': ba = 2*ossb-row['deduction_mm']
        else:
            k = calibrate_k(row['outside_first_mm'], row['outside_second_mm'], row['measured_flat_mm'], angle, r, t)
            ba = rad*(r+k*t)
        k = (ba/rad-r)/t
        if not 0 <= k <= 1: raise ValueError('Üretim satırı nötr ekseni sacın dışına taşıyor (K∉[0,1]).')
    rn = r+k*t
    if rn <= 0: raise ValueError('Nötr eksen yarıçapı pozitif olmalı.')
    strains = tuple((i*t/8, (i*t/8-k*t)/rn) for i in range(9))
    return BendValues(angle_deg, r, t, k, ba, ossb, r*math.tan(rad/2), 2*ossb-ba,
                      method, source, k*t, -k*t/rn, (1-k)*t/rn, strains)


def _interpolate(o,t,r,angle,ossb):
    key='allowance_mm' if o['method']=='ba_table' else 'deduction_mm'
    rows=[row for row in o['table'] if key in row and _scope(row,o,t,row['inside_radius_mm'])]
    def bracket(values,value):
        lower=[v for v in values if v<=value];upper=[v for v in values if v>=value]
        if not lower or not upper:raise ValueError('Tablo aralığı dışında ekstrapolasyon yapılmaz.')
        return max(lower),min(upper)
    rl,rh=bracket({row['inside_radius_mm'] for row in rows},r)
    al,ah=bracket({row['angle_deg'] for row in rows},angle)
    cells={};sources=set()
    for rr in {rl,rh}:
        for aa in {al,ah}:
            matches=[row for row in rows if row['inside_radius_mm']==rr and row['angle_deg']==aa]
            if len(matches)!=1:raise ValueError('Bilineer interpolasyon için eksiksiz, tekrarsız dört köşe hücresi gerekli.')
            cells[rr,aa]=matches[0][key];sources.add(matches[0]['source'])
    def lerp(a,b,f):return a+(b-a)*f
    fr=(r-rl)/(rh-rl) if rh!=rl else 0.;fa=(angle-al)/(ah-al) if ah!=al else 0.
    value=lerp(lerp(cells[rl,al],cells[rh,al],fr),lerp(cells[rl,ah],cells[rh,ah],fr),fa)
    return (value if key=='allowance_mm' else 2*ossb-value),'; '.join(sorted(sources))


def section_moment(curvature, thickness, young, yield_strength, tangent=0.):
    """Exact integral 2∫sigma(y)*y dy, per unit width (N); plane stress."""
    c = thickness/2
    elastic = min(c, yield_strength/(young*curvature))
    return (2*young*curvature*elastic**3/3
            + yield_strength*(1-tangent/young)*(c*c-elastic*elastic)
            + 2*tangent*curvature*(c**3-elastic**3)/3)


def springback(angle_deg, radius_mm, thickness_mm, options, *, radius_only=False):
    o = normalize_options(options)
    base = dict(status='NOT_EVALUATED', target_final_turn_deg=angle_deg, overbend_deg=None,
                loaded_turn_deg=None, estimated_final_turn_deg=None, target_error_deg=None,
                loaded_inside_radius_mm=None, production_process_verified=False)
    if not o:return dict(base,reason='Şekillendirme verisi girilmedi.')
    if o['springback'] == 'none': return dict(base, reason='Yaylanma hesabı seçilmedi.')
    angle_deg=finite(angle_deg,'Hedef dönüş',low=-179.999,high=179.999)
    sign = 1 if angle_deg > 0 else -1
    target = finite(abs(angle_deg), 'Hedef dönüş', high=179.999, positive=True)
    r = finite(radius_mm, 'İç yarıçap', high=1e7)
    t = finite(thickness_mm, 'Kalınlık', high=1e7, positive=True)
    if o['springback'] == 'calibrated':
        rows = sorted((row for row in o['springback_samples'] if _scope(row, o, t, r)), key=lambda row: row['angle_deg'])
        if len(rows) < 2 or not rows[0]['angle_deg'] <= target <= rows[-1]['angle_deg']:
            return dict(base, reason='Aynı üretim bağlamında hedefi çevreleyen en az iki ölçüm gerekli; ekstrapolasyon yok.')
        if any(b['angle_deg'] <= a['angle_deg'] or b['loaded_angle_deg'] <= a['loaded_angle_deg'] for a, b in zip(rows, rows[1:])):
            raise ValueError('Yaylanma kalibrasyon eğrisi tek değerli ve monoton olmalı.')
        a, b = next((a, b) for a, b in zip(rows, rows[1:]) if a['angle_deg'] <= target <= b['angle_deg'])
        loaded = a['loaded_angle_deg']+(target-a['angle_deg'])*(b['loaded_angle_deg']-a['loaded_angle_deg'])/(b['angle_deg']-a['angle_deg'])
        return dict(base, status='CALIBRATED_ESTIMATE', model='measured_piecewise_linear',
                    source=tuple(sorted({row['source'] for row in rows})), loaded_turn_deg=sign*loaded,
                    overbend_deg=loaded-target, estimated_final_turn_deg=angle_deg, target_error_deg=0.,
                    reason='Ölçülen aralıkta interpolasyon; bağımsız üretim doğrulaması değildir.')
    if o['process'] not in ('air_bending', 'roll_bending'):
        return dict(base, reason='Saf eğilme modeli bottoming/coining/segment birleştirme için geçerli değil; ölçüm gerekli.')
    m = o['material']
    if (not all(isinstance(m.get(k),str) and m[k].strip() for k in ('grade','source'))
            or not all(m.get(k) for k in ('young_modulus_mpa','yield_strength_mpa')) or m.get('hardening_modulus_mpa') is None):
        return dict(base, reason='Kalite, kaynak, E, akma dayanımı ve açık pekleşme modülü (ideal plastik için 0) gerekli.')
    E, Y, H = m['young_modulus_mpa'], m['yield_strength_mpa'], m['hardening_modulus_mpa']
    I = t**3/12
    final_curvature = 1/(r+t/2)
    def unloaded(k): return k-section_moment(k, t, E, Y, H)/(E*I)
    lo, hi = final_curvature, 2/t
    if unloaded(hi) < final_curvature:
        return dict(base, reason='Hedef nihai yarıçap için pozitif yük altı iç yarıçapı bulunamadı.')
    for _ in range(80):
        mid = (lo+hi)/2
        if unloaded(mid) < final_curvature: lo = mid
        else: hi = mid
    loaded_curvature = (lo+hi)/2
    loaded = target*loaded_curvature/final_curvature
    if loaded >= 180 and not radius_only:
        return dict(base, reason='Gerekli fazla büküm 180° sınırına ulaşıyor; model/takım kapsamı dışında.')
    final = loaded*unloaded(loaded_curvature)/loaded_curvature
    return dict(base, status='ANALYTICAL_ESTIMATE', model='bilinear_pure_bending_elastic_unloading', source=m['source'],
                loaded_turn_deg=sign*loaded, overbend_deg=loaded-target, estimated_final_turn_deg=sign*final,
                target_error_deg=sign*(final-target), loaded_inside_radius_mm=1/loaded_curvature-t/2,
                section_moment_n=section_moment(loaded_curvature, t, E, Y, H),
                reason='İzotropik düzlem gerilme, sabit kesit, saf eğilme; takım teması/hadde anizotropisi/Bauschinger ve incelme çözülmedi.')


def compare_reference(reference, computed, *, source, absolute_tolerance_mm, relative_tolerance_percent):
    """Same named measurement points only; no geometric equivalence from catalogue names."""
    text(source, 'Referans kaynağı', required=True)
    atol = finite(absolute_tolerance_mm, 'Mutlak tolerans')
    rtol = finite(relative_tolerance_percent, 'Yüzde tolerans')
    if not isinstance(reference, Mapping) or not isinstance(computed, Mapping) or not reference or set(reference) != set(computed):
        raise ValueError('Referans ve hesap ölçüm noktaları aynı ve boş olmayan kimlik kümesini taşımalı.')
    rows = []
    for name in reference:
        a = finite(reference[name], name, low=-1e12)
        b = finite(computed[name], name, low=-1e12)
        delta = b-a; percent = abs(delta/a)*100 if a else None
        rows.append(dict(point=name, reference_mm=a, computed_mm=b, difference_mm=delta,
                         absolute_difference_mm=abs(delta), percent_difference=percent,
                         within_tolerance=abs(delta) <= atol and (percent <= rtol if percent is not None else True)))
    return FrozenMap(dict(source=source, points=rows, dimensions_match=all(row['within_tolerance'] for row in rows),
                          production_equivalence_verified=False))
