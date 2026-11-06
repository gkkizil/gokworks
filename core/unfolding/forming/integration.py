"""Apply only mathematically defined compensation maps to existing geometry."""
from dataclasses import replace
import math

from .mechanics import bend_values, springback, normalize_options
from .profiles import profile_part
from .deformation import analyze_mesh
from ..models import FrozenMap, Geometry2D, Line2D, Polyline2D, Issue, to_data
from ..geometry import contour_area
from ..shapes.common import finish_part, check_cancel


def _curve(curve, point):
    if isinstance(curve, Line2D): return replace(curve, start=point(curve.start), end=point(curve.end))
    if isinstance(curve, Polyline2D): return replace(curve, points=tuple(point(p) for p in curve.points))
    raise ValueError('Bu konturda nötr eksen dönüşümü doğrulanmadı; yay/daire genel olarak ölçeklenmez.')


def _curved(part, n, material, options, spec):
    basis = part.forming_basis
    if not basis or basis['kind'] not in ('circle', 'stadium'):
        raise ValueError('Bu yüzey için doğrulanmış şekillendirme dönüşümü yok; nominal geometri korundu.')
    if spec['process'] not in ('roll_bending', 'air_bending'):
        raise ValueError('Sürekli eğri açınımı bu prosesle eşleştirilmedi; roll_bending veya açık K ile air_bending seçin.')
    if spec['method'] not in ('k_factor', 'material_k'):
        raise ValueError('Sürekli daire/oval için BA/BD numune açısını tüm eğriye ekstrapole etmiyoruz; açık K verisi gerekli.')
    radius = basis['radius_mm']; t = n['thickness']; inside = radius-t/2
    if inside < 0: raise ValueError('Kalınlık iç büküm yarıçapını negatif yapıyor.')
    values = bend_values(90., inside, t, spec)
    factor = (inside+values.k_factor*t)/radius
    straight = basis.get('straight_length_mm', 0.)
    half = math.pi*radius
    period = math.tau*radius+2*straight
    def neutral(s):
        cycles = math.floor(s/period); remaining=s-cycles*period
        value=cycles*(math.tau*radius*factor+2*straight)
        for length, scale in ((half,factor),(straight,1.),(half,factor),(straight,1.)):
            taken=min(remaining,length);value+=taken*scale;remaining-=taken
        return value
    start=basis['start_mm']
    point=lambda q:(neutral(start+q[0])-neutral(start), q[1])
    geometry=Geometry2D(tuple(_curve(c,point) for c in part.geometry_2d.outer),
                        tuple(tuple(_curve(c,point) for c in h) for h in part.geometry_2d.holes))
    area=abs(contour_area(geometry.outer))-sum(abs(contour_area(h)) for h in geometry.holes)
    rebuilt=finish_part(part.id, geometry, part.mesh_3d, part.surface_patches, area, n, material, options,
                        construction=tuple(_curve(c,point) for c in part.construction_lines),
                        seams=tuple(_curve(c,point) for c in part.seams),
                        mappings=tuple(replace(m,developed=point(m.developed)) for m in part.mappings),lengths=part.true_lengths)
    rebuilt=replace(rebuilt,code=part.code,quantity=part.quantity,forming_basis=part.forming_basis,
                    bending_lines=tuple(_curve(c,point) for c in part.bending_lines),
                    nominal_geometry_2d=part.geometry_2d,nominal_bending_lines=part.bending_lines,nominal_part=part)
    nominal=basis['span_mm']; corrected=neutral(start+nominal)-neutral(start)
    sb=springback(90.,inside,t,spec,radius_only=True)
    # A closed pipe does not have a 90-degree command angle. Report radius recovery
    # from a local pure-bending section, not an invented machine bend program.
    sb_radius={k:v for k,v in sb.items() if k not in ('target_final_turn_deg','loaded_turn_deg','overbend_deg','estimated_final_turn_deg','target_error_deg')}
    if spec['springback']=='calibrated':
        sb_radius=dict(status='NOT_EVALUATED',reason='Açısal kupon ölçümleri kapalı kesitin yük altı yarıçapını doğrulamaz; silindir prosesi için eğrilik ölçümü gerekli.')
    return rebuilt, dict(status='COMPENSATED', method='piecewise_neutral_axis_arc_length',
                          nominal_length_mm=nominal, compensated_length_mm=corrected, difference_mm=corrected-nominal,
                          bend_values=to_data(values), springback_radius_estimate=sb_radius,
                          interpretation='Yalnız eğri bölümler K ile değişir; oval düz yanlar korunur. Kesim yükseklikleri hedef orta yüzey üzerindedir.',
                          press_brake_plan='NOT_EVALUATED', machine_command_generated=False)


def _mesh_report(part):
    if len(part.mesh_3d.vertices)>10000 or len(part.mesh_3d.triangles)>20000:
        return dict(status='NOT_EVALUATED',reason='Ayrıntılı gerinim analizi 10000 düğüm / 20000 üçgen bütçesini aşıyor; geometri hesabı korunur.')
    if len(part.mappings) != len(part.mesh_3d.vertices) or any(
            math.dist(m.assembled,v)>1e-7 for m,v in zip(part.mappings,part.mesh_3d.vertices)):
        return dict(status='NOT_EVALUATED',reason='Önizleme mesh düğümlerinin bire bir 2D eşlemesi yok.')
    try:
        report=analyze_mesh(part.mesh_3d.vertices,part.mesh_3d.triangles,tuple(m.developed for m in part.mappings))
        # Full per-edge/per-triangle data are available from analyze_mesh. Keep the
        # service snapshot bounded; show worst edges and aggregate area metrics.
        report['worst_edges']=sorted(report.pop('edges'),key=lambda e:abs(e['unfolding_strain']),reverse=True)[:10]
        report['triangle_count']=len(report.pop('triangles'))
        return report
    except ValueError as exc: return dict(status='NOT_EVALUATED',reason=str(exc))


def _checks(n, spec, straights=(), bends=(), springbacks=()):
    tool=spec['tool'];checks=[]
    for key,title,values in (('minimum_flange_mm','Minimum teğet flanş',straights),
                              ('minimum_radius_mm','Minimum iç yarıçap',tuple(b.inside_radius_mm for b in bends))):
        limit=tool.get(key)
        checks.append(dict(check=title,status='NOT_EVALUATED' if limit is None or not tool.get('source') or not values else
                           'PASS' if min(values)>=limit else 'WARNING', limit_mm=limit,source=tool.get('source','')))
    v=tool.get('die_opening_mm');punch=tool.get('punch_radius_mm')
    checks.append(dict(check='Takım açıklığı geometrisi',status='NOT_EVALUATED' if v is None or punch is None else
                       'PASS' if v>2*punch and v>n['thickness'] else 'WARNING',
                       reason='Yalnız girilen geometrik ölçüler; V/t malzemeye bağlı üretim kuralı veya tonaj hesabı değildir.'))
    for index,(b,sb) in enumerate(zip(bends,springbacks),1):
        if b.k_factor>.5:
            checks.append(dict(check=f'B{index} K-Faktör kapsamı',status='WARNING',
                               reason='K>0.5 normal hava bükümü varsayımı değildir; yalnız özel ölçüm/girdi olarak tutuldu.'))
        if spec['angle_tolerance_deg'] is not None:
            error=sb.get('target_error_deg')
            checks.append(dict(check=f'B{index} çözücü açısal artık',status='NOT_EVALUATED' if error is None else
                               'PASS' if abs(error)<=spec['angle_tolerance_deg'] else 'WARNING',
                               reason='Yalnız sayısal model hedefi; gerçek üretim açı toleransı doğrulanmadı.'))
        if tool.get('die_angle_deg') is not None and sb.get('loaded_turn_deg') is not None:
            checks.append(dict(check=f'B{index} kalıp açık açısı',status='WARNING' if 180-abs(sb['loaded_turn_deg'])<tool['die_angle_deg'] else 'PASS'))
        if punch is not None:
            loaded_r=sb.get('loaded_inside_radius_mm')
            checks.append(dict(check=f'B{index} zımba yarıçapı',status='NOT_EVALUATED' if loaded_r is None else
                               'WARNING' if punch>loaded_r else 'PASS'))
        if spec['strain_limit'] is not None:
            checks.append(dict(check=f'B{index} kullanıcı geometrik gerinim sınırı',
                               status='WARNING' if max(abs(b.inner_engineering_strain),abs(b.outer_engineering_strain))>spec['strain_limit'] else 'PASS',
                               reason='Bir şekillendirme sınır eğrisi veya kopma kriteri değildir.'))
    checks.extend(dict(check=title,status='NOT_EVALUATED') for title in ('Büküm sırası', '3D takım/parça çarpışması', 'Makine/kalıp kapasitesi', 'Kalınlık incelmesi'))
    return checks


def apply_forming(parts,n,material,options,token=None):
    spec=normalize_options(n['forming_options'])
    if not spec:return parts,FrozenMap(),()
    out=[];records={};warnings=[]
    for part in parts:
        check_cancel(token)
        deformation=_mesh_report(part)
        try:
            if n['shape_id']=='bent_profile':
                rebuilt,bends,zones,length,straights=profile_part(n,material,options,token,forming=spec)
                rebuilt=replace(rebuilt,nominal_geometry_2d=part.geometry_2d,nominal_bending_lines=part.bending_lines,nominal_part=part)
                springs=tuple(springback(b.angle_deg,b.inside_radius_mm,n['thickness'],spec) for b in bends)
                nominal=part.metrics.bounds_mm[2]-part.metrics.bounds_mm[0]
                record=dict(status='COMPENSATED',method=spec['method'],nominal_length_mm=nominal,
                            compensated_length_mm=length,difference_mm=length-nominal,
                            bends=[dict(to_data(b),**zone,springback=sb) for b,zone,sb in zip(bends,zones,springs)],
                            checks=_checks(n,spec,straights,bends,springs),machine_command_generated=False)
            else:
                rebuilt,record=_curved(part,n,material,options,spec)
                record['checks']=_checks(n,spec)
            warnings.append(Issue('FORMING_COMPENSATED',f'{part.code}: nötr eksen/BA telafisi uygulandı; fark {record["difference_mm"]:.6f} mm. Üretim uygunluk onayı değildir.','INFO',part_id=part.id))
        except ValueError as exc:
            rebuilt=part;record=dict(status='NOT_EVALUATED',reason=str(exc))
            warnings.append(Issue('FORMING_NOT_EVALUATED',f'{part.code}: {exc}','NOT_EVALUATED',part_id=part.id))
        record['geometric_deformation']=deformation
        if spec['relax_mesh']:
            if rebuilt is part:
                try:
                    from .deformation import relax_part
                    rebuilt,optimization=relax_part(part,n,material,options,token)
                    record.update(status='MESH_OPTIMIZED',method='numerical_edge_metric_relaxation',relaxation=optimization,
                                  optimized_deformation=_mesh_report(rebuilt))
                    warnings.append(Issue('MESH_APPROXIMATION',f'{part.code}: mesh metrik hatası minimize edildi; plastik şekillendirme çözümü veya üretim onayı değildir.','WARNING',part_id=part.id))
                except ValueError as exc:record['relaxation']=dict(status='NOT_EVALUATED',reason=str(exc))
            else:record['relaxation']=dict(status='NOT_EVALUATED',reason='Analitik büküm/K dönüşümü uygulandı; ek mesh optimizasyonu uygulanmadı.')
        if spec['length_tolerance_mm'] is not None and record.get('difference_mm') is not None:
            record['difference_within_user_tolerance']=abs(record['difference_mm'])<=spec['length_tolerance_mm']
        if spec['reference']:
            from .reference import compare_part
            record['catalogue_comparison']=compare_part(rebuilt,spec['reference'])
        records[part.id]=record;out.append(rebuilt)
    all_applied=all(r['status']=='COMPENSATED' for r in records.values())
    # Dynamic scope message replaces the old blanket disclaimer only when the
    # specific compensation actually ran. Source-catalogue limitations remain.
    warnings.append(Issue('FORMING_SCOPE','Açısal yaylanma tahmini açınım uzunluğuna eklenmez. Makine programı, tonaj, plastik incelme ve üretim uygunluğu doğrulanmadı.','NOT_EVALUATED'))
    return tuple(out),FrozenMap(dict(version=1,options=spec,parts=records,all_compensated=all_applied,
                                     production_process_verified=False)),tuple(warnings)
