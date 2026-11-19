"""Native BOM/balloons and body-verified existing flat-pattern drawing pages."""

from collections import Counter
from dataclasses import replace
import re

from modules.cad_converter.api import ApiError, RestoreError
from .solidworks import call, get, put, prop, optional, values, variant, out_int, as_interface
from .models import Box, ViewPlan, checkpoint, identity, to_mm, to_m
from .layout import plan_sheet
from .rules import quantities


def table_box(table):
    """ITableAnnotation bounds from native row/column dimensions and top-left anchor."""
    rows, columns = int(get(table, 'RowCount')), int(get(table, 'ColumnCount'))
    if not 0 < rows < 10000 or not 0 < columns < 1000:
        raise ApiError('BOM tablo boyutları okunamadı.')
    annotation = call(table, 'GetAnnotation')
    position = values(call(annotation, 'GetPosition'))
    if len(position) < 2:
        raise ApiError('BOM tablosu konumu okunamadı.')
    width = sum(to_mm(call(table, 'GetColumnWidth', i)) for i in range(columns))
    height = sum(to_mm(call(table, 'GetRowHeight', i)) for i in range(rows))
    return Box(to_mm(position[0]), to_mm(position[1])-height, width, height)


def quantity_columns(table, session):
    columns = []
    for index in range(int(get(table, 'ColumnCount'))):
        data, status = variant(0x400C, None), out_int()
        kind = call(table, 'GetColumnType3', index, False, data, status)
        if isinstance(kind, (tuple, list)):
            if len(kind) != 3:
                raise ApiError('BOM sütun tipi sözleşmesi geçersiz.')
            kind, data.value, status.value = kind
        if status.value != session.c('swColumnTypeStatus_Success'):
            raise ApiError('BOM sütun bilgisi okunamadı; API kodu '+str(status.value))
        if kind == session.c('swBomTableColumnType_Quantity'):
            columns.append(index)
    return columns


def displayed_quantity(table, row, column):
    text = str(prop(table, 'DisplayedText2', row, column, False) or '').strip()
    # Do not reinterpret lengths, weights, equations or arbitrary overrides as counts.
    if not re.fullmatch(r'[0-9]+', text):
        return None, text
    return int(text), text


def flat_page(native, source_model):
    info, options, result = native.info, native.options, native.result
    if not options.flat_pattern or not info.sheet_body_count:
        return
    if info.sheet_bodies:
        return body_flat_pages(native, source_model)
    if info.body_count != 1 or info.sheet_body_count != 1:
        result.warn('multibody_flat', 'Sac gövdelerinin kalıcı kimlikleri / açınım eşleştirmeleri eksik; '
                    'yeniden analiz edin. Gövde adı veya sırası ile açınım tahmin edilmedi.')
        return
    matching = []
    for name in info.flat_configurations:
        config = call(source_model, 'GetConfigurationByName', name)
        parent = call(config, 'GetParent')
        if parent is not None and str(get(parent, 'Name')) == info.source.configuration:
            matching.append(name)
    if len(matching) != 1:
        result.warn('flat_configuration', 'Kaynağa bağlı tek bir mevcut SM-FLAT-PATTERN konfigürasyonu '
                    'doğrulanamadı; kaynakta yeni açınım konfigürasyonu oluşturulmadı.')
        return
    before = tuple(str(v) for v in values(call(source_model, 'GetConfigurationNames')))
    single = replace(options, top=False, side=False, isometric=False)
    diagonal = sum(x*x for x in info.size_mm)**.5
    plan = plan_sheet([ViewPlan('flat', '', (diagonal, diagonal))], single, 'Sac açınımı')
    native.setup(plan, new=True)
    x, y = (to_m(v) for v in plan.views[0].center)
    view = call(native.drawing, 'CreateFlatPatternViewFromModelView3', info.source.path,
                info.source.configuration, x, y, 0., not options.bend_lines, False)
    after = tuple(str(v) for v in values(call(source_model, 'GetConfigurationNames')))
    if set(after) != set(before):
        raise RestoreError('SolidWorks mevcut açınım yerine kaynakta yeni bir konfigürasyon oluşturdu. '
                           'Kaynak dosya kaydedilmedi; SolidWorks’te geçici konfigürasyonu kontrol edin.')
    if view is None:
        raise ApiError('Native açınım görünüşü oluşturulamadı.')
    if str(get(view, 'ReferencedConfiguration')) != matching[0] or not call(view, 'IsFlatPatternView'):
        raise ApiError('Açınım görünüşünün beklenen konfigürasyonu doğrulanamadı.')
    put(view, 'UseSheetScale', 1)
    native.pages[plan.name]['views']['flat'] = view
    native.set_scale(plan.name, plan.scale)
    native.fit(plan.name)
    native.flat_dimensions(plan.name)
    result.measurements['flat_pattern'] = {'configuration': matching[0], 'body_count': 1,
        'bend_lines_requested': options.bend_lines, 'thickness_mm': info.thickness_mm}
    result.warn('bend_notes', 'Açınım native görünüş olarak eklendi. Büküm çizgileri / yönleri ve büküm notlarının '
                'tamlığı SolidWorks’te kontrol edilmeli; eksik K faktörü veya büküm açısı tahmin edilmedi.', plan.name)


def body_flat_pages(native, source_model):
    """One existing flat configuration and one verified body per native page."""
    from modules.cad_converter.api import PART_IID
    from .sheetmetal import verify_unfolded
    info, options, session = native.info, native.options, native.session
    multibody = len(info.sheet_bodies) > 1
    before = tuple(str(v) for v in values(call(source_model, 'GetConfigurationNames')))
    delivered = []
    for row in info.sheet_bodies:
        checkpoint(native.stop)
        if not row.ready:
            native.result.warn('body_flat_unavailable', row.label+': gövdeye bağlı tek bir mevcut açınım '
                               'konfigürasyonu doğrulanamadı; bu gövdenin açınımı atlandı.')
            continue
        configuration = row.configurations[0]
        verify_unfolded(session, source_model, row, configuration)
        single = replace(options, top=False, side=False, isometric=False)
        # The folded box is only an initial estimate; native.fit uses the actual
        # unfolded geometry. Reserve a separate header outside the view region.
        diagonal = sum(x*x for x in (row.size_mm or info.size_mm))**.5
        plan = plan_sheet([ViewPlan('flat', '', (diagonal, diagonal))], single,
                          f'Sac açınımı {row.index:02d}')
        whole = plan.usable
        header = Box(whole.x, whole.top-18., whole.width, 18.)
        plan.usable = Box(whole.x, whole.y, whole.width, whole.height-22.)
        plan.views = [replace(plan.views[0], center=plan.usable.center)]
        native.setup(plan, new=True)
        page = native.pages[plan.name]
        page['flat_body'] = row
        x, y = (to_m(v) for v in plan.views[0].center)
        # Request the PARENT configuration: SolidWorks resolves it to its existing derived flat
        # configuration (localized name, e.g. 'VarsayılanSM-DÜZ-ÇOĞALTMA'), checked below.
        # Recorded on SolidWorks 2025 SP5: naming the flat configuration itself returns a FOLDED
        # view that still reports IsFlatPatternView and references the parent configuration.
        if multibody:
            select_body(native, source_model, row)
        view = call(native.drawing, 'CreateFlatPatternViewFromModelView3', info.source.path,
                    info.source.configuration, x, y, 0., not options.bend_lines, False)
        after = tuple(str(v) for v in values(call(source_model, 'GetConfigurationNames')))
        created = [name for name in after if name not in before]
        if multibody and created:
            # Recorded on SolidWorks 2025 SP5: on a reopened multibody part the selected body's
            # flat view always gets a NEW in-memory '<parent>SM-FLAT-PATTERN<n>'; a drawing bound
            # to it loses the unfolded geometry on reopen (the source is never saved). Retarget
            # the view to the body's SAVED flat configuration, then remove the temporary one.
            if view is not None:
                put(view, 'ReferencedConfiguration', configuration)
                native.rebuild()
            for name in created:
                if call(source_model, 'DeleteConfiguration2', name) is not True:
                    raise RestoreError('Açınımın geçici kaynak konfigürasyonu kaldırılamadı: '+name+
                                       '. Kaynak kaydedilmedi; SolidWorks’te bu konfigürasyonu kaydetmeden kapatın.')
            after = tuple(str(v) for v in values(call(source_model, 'GetConfigurationNames')))
        if set(after) != set(before):
            raise RestoreError('Açınım oluşturulurken kaynak konfigürasyonları değişti; kaynak kaydedilmedi.')
        if view is None or str(get(view, 'ReferencedConfiguration')) != configuration or not call(view, 'IsFlatPatternView'):
            raise ApiError(row.label+': istenen native açınım görünüşü doğrulanamadı.')
        # Select through IView.Bodies rather than names or the first body's index.
        # Source handles are reacquired AFTER any definition/rollback access.
        with session.configuration(source_model, configuration):
            part = as_interface(source_model, PART_IID)
            candidates = values(call(part, 'GetBodies2', session.c('swSolidBody'), False))
            matches = [body for body in candidates if session.persistent_ref(source_model, body) == row.body_ref]
            if len(matches) != 1 or not call(matches[0], 'IsSheetMetal'):
                raise ApiError(row.label+': açınım konfigürasyonunda aynı sac gövdesi bulunamadı.')
            put(view, 'Bodies', variant(0x2009, (matches[0],)))
            candidates = matches = (); part = None
            native.rebuild()
        put(view, 'UseSheetScale', 1)
        page['views']['flat'] = view
        native.set_scale(plan.name, plan.scale)
        native.fit(plan.name)
        native.flat_dimensions(plan.name)
        actual = native.actual_views(plan.name)[0]
        if actual.get('body_references') != (row.body_ref,) or actual.get('body_count') != 1:
            raise ApiError(row.label+': native açınım başka veya birden fazla gövde gösteriyor.')
        native.body_heading(plan.name, row, header)
        delivered.append({'label': row.label, 'body_ref': row.body_ref, 'configuration': configuration,
                          'flat_ref': row.flat_ref, 'cut_list': row.cut_list, 'cut_list_quantity': row.cut_list_quantity,
                          'thickness_mm': row.thickness_mm, 'material': row.material, 'sheet': plan.name})
    if delivered:
        native.result.measurements['flat_pattern'] = {'bodies': delivered, 'body_count': len(delivered),
                                                     'bend_lines_requested': options.bend_lines}
        native.result.warn('bend_notes', 'Gövde bazlı açınımlar mevcut konfigürasyonlardan oluşturuldu. '
                           'Büküm çizgileri, yönleri ve notlarının tamlığını SolidWorks’te kontrol edin.')


def select_body(native, source_model, row):
    """Pre-select the body in the source: SolidWorks asks which body to unfold on a multibody part."""
    from modules.cad_converter.api import PART_IID
    from .solidworks import null_dispatch
    session = native.session
    session.activate(source_model)
    try:
        call(source_model, 'ClearSelection2', True)
        bodies = values(call(as_interface(source_model, PART_IID), 'GetBodies2', session.c('swSolidBody'), False))
        matches = [body for body in bodies if session.persistent_ref(source_model, body) == row.body_ref]
        if len(matches) != 1 or not call(matches[0], 'Select2', False, null_dispatch()):
            raise ApiError(row.label+': açınım için sac gövdesi kaynakta seçilemedi.')
    finally:
        bodies = matches = ()
        session.activate(native.model)


def bom_page(native):
    info, options, result, session = native.info, native.options, native.result, native.session
    if info.kind != 'assembly' or not options.bom:
        return
    diagonal = sum(x*x for x in info.size_mm)**.5
    plan = plan_sheet([ViewPlan('main', '*Isometric', (diagonal, diagonal))],
                       replace(options, top=False, side=False, isometric=False), 'Montaj parça listesi')
    whole_area = plan.usable
    # Keep the table and native assembly view in separate, measured columns.
    plan.usable = Box(whole_area.x+whole_area.width*.58, whole_area.y,
                      whole_area.width*.42, whole_area.height)
    plan.views = [replace(plan.views[0], center=plan.usable.center)]
    native.setup(plan, new=True)
    native.create_views(plan)
    native.fit(plan.name)
    view = native.pages[plan.name]['views']['main']
    c = session.c
    bom_type = c({'parts': 'swBomType_PartsOnly', 'top': 'swBomType_TopLevelOnly',
                  'indented': 'swBomType_Indented'}[options.bom_type])
    table = call(view, 'InsertBomTable4', False, to_m(whole_area.x), to_m(whole_area.top),
                 c('swBOMConfigurationAnchor_TopLeft'), bom_type,
                 '' if options.bom_type == 'top' else info.source.configuration,
                 options.bom_template, False,
                 c('swNumberingType_Detailed' if options.bom_type == 'indented' else 'swNumberingType_None'), False)
    if table is None:
        raise ApiError('BOM tablosu oluşturulamadı; montaj / BOM şablonunu kontrol edin.')
    feature = get(table, 'BomFeature')
    if options.bom_type == 'top':
        if not call(feature, 'SetConfigurations', True, variant(0x200B, (True,)),
                    variant(0x2008, (info.source.configuration,))):
            raise ApiError('BOM için kaynak konfigürasyonu ayarlanamadı.')
    else:
        if str(get(feature, 'Configuration')) != info.source.configuration:
            raise ApiError('BOM yanlış konfigürasyona bağlı.')
    generic_table = session.named_interface(table, 'ITableAnnotation')
    bounds = table_box(generic_table)
    if not whole_area.contains(bounds) or bounds.overlaps(plan.usable):
        raise ApiError('BOM ayrılan alana sığmıyor; daha büyük pafta seçin veya BOM kapsamını azaltın.')
    native.pages[plan.name]['tables'].append(bounds)
    native.pages[plan.name]['validation_area'] = whole_area
    rows, counts, unknown = [], Counter(), False
    columns = quantity_columns(generic_table, session)
    if len(columns) != 1:
        unknown = True
        result.warn('bom_quantity_columns', 'Tek bir görünür BOM adet sütunu doğrulanamadı; '
                    'satır metinleri gerçek adet olarak kabul edilmedi.', plan.name)
    configuration = info.source.configuration if options.bom_type == 'top' else ''
    for row in range(int(get(generic_table, 'RowCount'))):
        checkpoint(native.stop)
        item, part = variant(0x4008, ''), variant(0x4008, '')
        number = call(table, 'GetComponentsCount2', row, configuration, item, part)
        if isinstance(number, (tuple, list)):
            if len(number) != 3:
                raise ApiError('BOM satır adet sözleşmesi geçersiz.')
            number, item.value, part.value = number
        number = int(number)
        if number <= 0:
            continue
        listed = values(call(table, 'GetComponents2', row, configuration))
        # Recorded on SolidWorks 2025 SP5: GetComponentsCount2 and GetComponents2 include a
        # component suppressed in the BOM configuration; the displayed quantity does not.
        components = [component for component in listed
                      if optional(component, 'GetSuppression2') != c('swComponentSuppressed')]
        number -= len(listed)-len(components)
        if number <= 0:
            continue
        keys = [identity(str(call(component, 'GetPathName') or ''),
                         str(get(component, 'ReferencedConfiguration') or '')) for component in components]
        if len(keys) == number:
            counts.update(keys)
        elif keys and len(set(keys)) == 1:
            counts[keys[0]] += number
        else:
            unknown = True
        displayed, text = displayed_quantity(generic_table, row, columns[0]) if len(columns) == 1 else (None, '')
        if displayed is None:
            unknown = True
        elif displayed != number:
            raise ApiError('BOM üzerinde görünen adet gerçek bileşen sayısıyla uyuşmuyor; '
                           'adet override / ölçü birimi ayarını kontrol edin.')
        rows.append(dict(row_index=row, item=str(item.value), part_number=str(part.value),
                         quantity=displayed, displayed_quantity=text, component_count=number, components=keys))
    native.bom_rows = rows
    expected = quantities(info.tree, 'top' if options.bom_type == 'top' else 'parts')
    if options.bom_type == 'indented':
        result.warn('indented_bom', 'Girintili BOM oluşturuldu; terfi / gizleme ve alt montaj BOM kuralları nedeniyle '
                    'satır adetleri basit parça toplamıyla eşit kabul edilmedi.', plan.name)
    elif unknown:
        result.warn('bom_quantities', 'Bazı BOM satırlarının bileşen kimlikleri okunamadı; adet eşleştirmesini kontrol edin.',
                    plan.name)
    elif counts != expected:
        raise ApiError('Native BOM adetleri taranan dosya / konfigürasyon adetleriyle uyuşmuyor. '
                       'BOM birleştirme / terfi ayarlarını kontrol edin.')
    result.measurements['bom'] = {'type': options.bom_type, 'rows': rows,
        'quantities_verified': not unknown and counts == expected and options.bom_type != 'indented'}
    if options.balloons:
        name = str(get(call(feature, 'GetFeature'), 'Name'))
        if not call(view, 'SetKeepLinkedToBOM', True, name):
            raise ApiError('Görünüş ile BOM tablosu balon bağlantısı kurulamadı.')
        native.select_view(view)
        settings = call(native.drawing, 'CreateAutoBalloonOptions')
        put(settings, 'IgnoreMultiple', True)
        put(settings, 'UpperTextContent', c('swBalloonTextItemNumber'))
        notes = values(call(native.drawing, 'AutoBalloon5', settings))
        numbers = [str(call(note, 'GetBomBalloonText', True) or '') for note in notes]
        item_numbers = {row['item'] for row in rows}
        if any(number not in item_numbers for number in numbers):
            raise ApiError('Otomatik balon numaraları native BOM satırlarıyla uyuşmuyor.')
        if set(numbers) != item_numbers:
            result.warn('balloon_coverage', 'Bazı BOM öğelerine görünür balon eklenemedi; gizli bileşenleri ve balonları kontrol edin.',
                        plan.name)
        result.measurements['balloons'] = numbers
        # Native balloon leader/text collisions still need operator inspection.
        result.warn('balloon_layout', 'Balonlar BOM’a bağlı oluşturuldu; lider çizgilerinin ve balon metinlerinin '
                    'yerleşimi ayrıca kontrol edilmeli.', plan.name)
    native.rebuild()
