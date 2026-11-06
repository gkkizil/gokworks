"""Shared human-readable mechanics summary for UI and vector PDF appendices."""


def report_lines(report, part_id=None):
    if not report:
        return ['Yalnız geometrik orta yüzey hesabı; üretim telafisi seçilmedi.']
    o=report['options'];m=o['material'];lines=[
        'Şekillendirme hesabı · mm / MPa / derece',
        f'Proses: {o["process"]} · yöntem: {o["method"]} · hadde yönü: {o["grain_direction"]}',
        f'Mekanik kalite: {m.get("grade", "belirtilmedi")} · standart: {m.get("standard", "belirtilmedi")}',
        f'Malzeme kaynağı: {m.get("source", "girilmedi")}',
        f'Takım: {o["tool"].get("id", "girilmedi")} · kaynak: {o["tool"].get("source", "girilmedi")}',
        'Açılar düz sacdan dönüş açısıdır; açık açı = 180° − |dönüş|.']
    for key,title in (('young_modulus_mpa','Elastisite E'),('yield_strength_mpa','Akma dayanımı'),
                      ('tensile_strength_mpa','Çekme dayanımı'),('hardening_modulus_mpa','Teğet pekleşme modülü')):
        if m.get(key) is not None:lines.append(f'{title}: {m[key]:.8g} MPa')
    for ident,p in report['parts'].items():
        if part_id is not None and ident!=part_id:continue
        lines.extend(('',f'{ident}: {p["status"]} · {p.get("method", "hesaplanmadı")}'))
        if p.get('reason'):lines.append(p['reason'])
        for key,title in (('nominal_length_mm','Nominal açınım'),('compensated_length_mm','Telafili açınım'),('difference_mm','Açınım farkı')):
            if p.get(key) is not None:lines.append(f'{title}: {p[key]:.9f} mm')
        for i,b in enumerate(p.get('bends',()),1):
            lines.extend((f'B{i}: dönüş {b["angle_deg"]:g}° · R iç {b["inside_radius_mm"]:g} mm · K {b["k_factor"]:.8g}',
                          f'BA {b["allowance_mm"]:.9f} mm · BD {b["deduction_mm"]:.9f} mm · OSSB {b["outside_setback_mm"]:.9f} mm',
                          f'Büküm çizgisi {b["line_at_mm"]:.9f} mm · nötr eksen içten {b["neutral_axis_from_inside_mm"]:.9f} mm',
                          f'Geometrik gerinim: iç {b["inner_engineering_strain"]:.6%} · dış {b["outer_engineering_strain"]:.6%}',
                          f'BA/BD kaynağı: {b["source"]}'))
            sb=b['springback'];lines.append(f'Yaylanma: {sb["status"]} · {sb.get("reason", "")}')
            if sb.get('overbend_deg') is not None:
                lines.append(f'Fazla büküm {sb["overbend_deg"]:.8f}° · yük altında {sb["loaded_turn_deg"]:.8f}° · tahmini nihai {sb["estimated_final_turn_deg"]:.8f}°')
        if p.get('bend_values'):
            b=p['bend_values'];lines.extend((
                f'Sürekli eğri nötr ekseni: K {b["k_factor"]:g} · içten {b["neutral_axis_from_inside_mm"]:.9f} mm',
                f'Yerel kesit gerinimi: iç {b["inner_engineering_strain"]:.6%} · dış {b["outer_engineering_strain"]:.6%}',
                'Oval düz kenarlar korunur; sürekli eğri için makine büküm açıları üretilmez.'))
            sb=p['springback_radius_estimate'];lines.append(f'Yerel eğrilik yaylanma modeli: {sb["status"]} · {sb.get("reason", "")}')
            if sb.get('loaded_inside_radius_mm') is not None:lines.append(f'Tahmini yük altı iç yarıçap: {sb["loaded_inside_radius_mm"]:.9f} mm')
        d=p.get('optimized_deformation',p.get('geometric_deformation',{}))
        if d.get('max_abs_edge_strain') is not None:
            lines.append(f'Mesh metrik hatası: kenar en çok {d["max_abs_edge_strain"]:.8%} · toplam alan farkı {d["total_area_change_ratio"]:.8%}')
        elif d:lines.append('Mesh gerinimi: NOT_EVALUATED · '+d.get('reason',''))
        opt=p.get('relaxation')
        if opt and 'initial_energy' in opt:lines.append(f'Mesh optimizasyonu: {opt["iterations"]} adım · enerji {opt["initial_energy"]:.9g} → {opt["final_energy"]:.9g} · yakınsama {opt["converged"]}')
        for c in p.get('checks',()):lines.append(f'{c["check"]}: {c["status"]}')
        reference=p.get('catalogue_comparison')
        if reference:
            lines.append(f'Katalog ölçü karşılaştırması: {reference["status"]} · {reference.get("source", "")}')
            for row in reference.get('points',()):lines.append(f'{row["point"]}: mutlak fark {row["absolute_difference_mm"]:.9f} mm · yüzde {row["percent_difference"]}')
            for row in reference.get('point_measurements',()):lines.append(f'Nokta {row["point"]}: {row["status"]} · mutlak hata {row.get("absolute_error_mm", "hesaplanamadı")} mm')
            lines.append('Ölçü eşleşmesi kaynak yazılım algoritması veya üretim eşdeğerliği onayı değildir.')
    lines.extend(('', 'Açısal yaylanma telafisi kesim uzunluğuna eklenmez.',
                  'Geometrik gerinim plastik gerinim veya incelme değildir; kalınlık değişimi hesaplanmadı.',
                  'Analitik sonuç deneysel doğrulama değildir. Kalibre edilmiş interpolasyon da bağımsız üretim uygunluk onayı değildir.',
                  'Makine programı, büküm sırası, 3D takım çarpışması ve kapasite: NOT_EVALUATED.'))
    return lines
