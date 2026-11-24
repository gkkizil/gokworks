"""Validate measured native geometry, never file existence or a planned rectangle alone."""

from itertools import combinations
import math

from .models import Box, Finding, identity
from .layout import crosses_box


def validate_views(sheet, actual, source, *, flat_configurations=(), projection=None):
    findings = []
    if projection is not None and projection != sheet.get('projection'):
        findings.append(Finding('FAIL', 'projection', 'Paftanın gerçek izdüşüm yöntemi istenen yöntemle uyuşmuyor.',
                                sheet['name']))
    expected = set(sheet['expected'])
    roles = [view['role'] for view in actual]
    if set(roles) != expected or len(roles) != len(expected):
        findings.append(Finding('FAIL', 'views', 'Beklenen görünüşler eksik, fazla veya tekrarlı.', sheet['name']))
    bounds = Box(0., 0., sheet['width_mm'], sheet['height_mm'])
    usable = sheet.get('usable', bounds)
    main_position = next((v.get('position') for v in actual if v['role'] == 'main'), None)
    for view in actual:
        label = view['name']
        outline = view.get('outline')
        if outline is None or outline.width <= .001 or outline.height <= .001:
            findings.append(Finding('FAIL', 'empty_view', 'Görünüş geometrisi boş veya okunamadı.',
                                    sheet['name'], label))
        elif not bounds.contains(outline) or not usable.contains(outline):
            findings.append(Finding('FAIL', 'view_outside', 'Görünüş pafta / antet güvenli alanının dışında.',
                                    sheet['name'], label))
        if identity(view.get('path', ''))[0] != source.key[0]:
            findings.append(Finding('FAIL', 'source_link', 'Görünüş farklı modele bağlı veya model bağlantısı kopuk.',
                                    sheet['name'], label))
        if view.get('model_available') is False or ('resolved_path' in view and
                identity(view['resolved_path'])[0] != source.key[0]):
            findings.append(Finding('FAIL', 'resolved_source', 'Görünüşün gerçek kaynak dokümanı çözümlenemedi.',
                                    sheet['name'], label))
        config = view.get('configuration')
        if view['role'] == 'flat':
            if config not in flat_configurations or not view.get('flat'):
                findings.append(Finding('FAIL', 'flat_link', 'Açınımın konfigürasyonu / FlatPattern durumu doğrulanamadı.',
                                        sheet['name'], label))
            if view.get('expected_body') and (
                    tuple(view.get('body_references', ())) != (view['expected_body'],) or
                    view.get('body_count') != 1 or config != view.get('expected_flat_configuration')):
                findings.append(Finding('FAIL', 'flat_body', 'Açınım görünüşü istenen tek sac gövdesine bağlı değil.',
                                        sheet['name'], label))
        elif config != source.configuration:
            findings.append(Finding('FAIL', 'configuration', 'Görünüş yanlış konfigürasyona bağlı.',
                                    sheet['name'], label))
        if view['role'] in ('top', 'side', 'section', 'detail') and view.get('parent') != view.get('main_name'):
            findings.append(Finding('FAIL', 'projection_link', 'İzdüşümün ana görünüş ilişkisi korunmamış.',
                                    sheet['name'], label))
        if view['role'] in ('section', 'detail') and (not view.get('label') or
                view['label'] not in (view['expected_label'], view['expected_label']+'-'+view['expected_label'])):
            findings.append(Finding('FAIL', 'derived_label', 'Kesit/detay etiketi doğrulanamadı.',
                                    sheet['name'], label))
        if view['role'] == 'detail' and not math.isclose(view['view_scale'], view['expected_scale'], rel_tol=1e-6):
            findings.append(Finding('FAIL', 'detail_scale', 'Kayıtlı detay ölçeği seçilen değerle uyuşmuyor.',
                                    sheet['name'], label))
        if view['role'] in ('top', 'side', 'section') and main_position and view.get('position'):
            axis = 1-view['offset_axis'] if view['role'] == 'section' else int(view['role'] == 'side')
            if abs(view['position'][axis]-main_position[axis]) > .05:
                findings.append(Finding('FAIL', 'projection_alignment', 'İzdüşüm ana görünüşle aynı eksende değil.',
                                        sheet['name'], label))
            method = projection or sheet.get('projection')
            if method in ('first', 'third'):
                direction = view['position'][1-axis]-main_position[1-axis]
                if direction*(-1 if method == 'first' else 1) <= 0:
                    findings.append(Finding('FAIL', 'projection_direction',
                        'İzdüşüm seçilen birinci/üçüncü açı yöntemine göre yanlış tarafta.', sheet['name'], label))
    for first, second in combinations(actual, 2):
        a, b = first.get('outline'), second.get('outline')
        if a is not None and b is not None and a.overlaps(b):
            findings.append(Finding('FAIL', 'view_collision', f"Görünüşler çakışıyor: {first['name']} / {second['name']}.",
                                    sheet['name']))
    return findings


def validate_annotations(records, outlines, area, sheet='', *, bounds=None):
    findings = []
    seen = set()
    for record in records:
        name, box = record['name'], record.get('box')
        if record.get('dangling'):
            findings.append(Finding('FAIL', 'dangling_dimension', 'Ölçünün geometri bağlantısı kopuk: '+name, sheet))
        value = record.get('value')
        if value is None or not math.isfinite(value):
            findings.append(Finding('WARNING', 'dimension_value', 'Ölçü değeri okunamadı: '+name, sheet))
        elif abs(value) < 1e-12:
            findings.append(Finding('WARNING', 'zero_dimension', 'Sıfır ölçüyü kontrol edin: '+name, sheet))
        key = record.get('model_identity')
        if key:
            if key in seen:
                findings.append(Finding('WARNING', 'duplicate_dimension', 'Aynı model ölçüsü tekrar gösterilmiş: '+name, sheet))
            seen.add(key)
        if box is None:
            findings.append(Finding('WARNING', 'dimension_bounds', 'Ölçünün metin sınırları okunamadı: '+name, sheet))
        elif not area.contains(box):
            if bounds is None or not bounds.contains(box):
                findings.append(Finding('FAIL', 'dimension_outside', 'Ölçü pafta dışında: '+name, sheet))
            else:
                findings.append(Finding('WARNING', 'dimension_title_area', 'Ölçü antet veya kenar boşluğuna taşıyor: '+name,
                                        sheet))
        elif any(box.overlaps(outline) for outline in outlines.values()):
            findings.append(Finding('WARNING', 'dimension_on_view', 'Ölçü metni görünüş üzerine geliyor: '+name, sheet))
    readable = [r for r in records if r.get('box') is not None]
    for first, second in combinations(readable, 2):
        if first['box'].overlaps(second['box'], .25):
            findings.append(Finding('WARNING', 'dimension_collision',
                                    f"Ölçü metinleri çakışıyor: {first['name']} / {second['name']}.", sheet))
    return findings


def validate_annotation_obstacles(dimensions, extras, outlines, area, sheet):
    findings = []
    for record in extras:
        box = record['box']
        if record['kind'] == 'wizard_note' and record.get('dangling') is True:
            findings.append(Finding('FAIL', 'hole_note_link', 'Delik notunun geometri bağı kopmuş: '+record['name'], sheet))
        if box is None:
            findings.append(Finding('WARNING', 'annotation_bounds',
                                    'Anotasyon sınırları okunamadı: '+record['name'], sheet))
        elif record['kind'] != 'title':
            if not area.contains(box):
                findings.append(Finding('WARNING', 'annotation_outside',
                    'Anotasyon pafta veya antet alanına taşıyor: '+record['name'], sheet))
            if any(box.overlaps(view) for view in outlines.values()):
                findings.append(Finding('WARNING', 'annotation_on_view',
                    'Anotasyon metni görünüş üzerine geliyor: '+record['name'], sheet))
    for first, second in combinations([*dimensions, *extras], 2):
        a, b = first.get('box'), second.get('box')
        if first.get('kind') == second.get('kind') == 'title':
            continue
        if (a is not None and b is not None and (first.get('annotation_kind') or second.get('annotation_kind'))
                and a.overlaps(b, .25)):
            findings.append(Finding('WARNING', 'annotation_collision',
                f"Anotasyonlar çakışıyor: {first['name']} / {second['name']}.", sheet))
        if ((a is not None and any(crosses_box(*line, a) for line in second.get('leaders', ()))) or
                (b is not None and any(crosses_box(*line, b) for line in first.get('leaders', ())))):
            findings.append(Finding('WARNING', 'annotation_leader_collision',
                f"Lider çizgisi metin veya tabloyu kesiyor: {first['name']} / {second['name']}.", sheet))
    return findings
