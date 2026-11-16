"""Published SolidWorks drawing APIs, with explicit units and real readback.

IModelDoc2 and IDrawingDoc are distinct dual interfaces. Their pointers never
leave this worker-owned adapter. See docs/automatic-drawing/SOLIDWORKS_API_REFERENCES.md.
"""

import math

from modules.cad_converter.api import ApiError, MODEL_IID
from modules.tolerance_stack.solidworks_reader import nominal_value, DIMENSION_TYPES
from .solidworks import call, get, put, prop, optional, values, variant, out_int, null_dispatch, as_interface
from .models import Box, checkpoint, to_mm, to_m, degrees
from .layout import arrange, place_texts, text_box, union
from .validation import validate_views, validate_annotations


def outline(view):
    data = values(call(view, 'GetOutline'))
    if len(data) != 4:
        raise ApiError('Görünüş dış sınırları okunamadı.')
    x0, y0, x1, y1 = (to_mm(v) for v in data)
    return Box(x0, y0, x1-x0, y1-y0)


def view_position(view):
    # IView.Position is a TWO-double SAFEARRAY; IAnnotation.GetPosition is 3D.
    position = values(get(view, 'Position'))
    if len(position) != 2 or any(not math.isfinite(float(v)) for v in position):
        raise ApiError('Görünüşün iki boyutlu pafta konumu okunamadı.')
    return tuple(float(v) for v in position)


def annotation_box(annotation):
    """Native text geometry; a conservative estimate is explicitly identified."""
    data = call(annotation, 'GetDisplayData')
    if data is None:
        return None, False
    count = int(call(data, 'GetTextCount'))
    if count < 0 or count > 200:
        raise ApiError('Anotasyon metin sayısı geçersiz.')
    boxes, estimated = [], False
    for index in range(count):
        position = values(call(data, 'GetTextPositionAtIndex', index))
        if len(position) < 2:
            return None, False
        width = float(call(data, 'GetTextInBoxWidthAtIndex', index))
        height = float(call(data, 'GetTextHeightAtIndex', index))
        angle = float(call(data, 'GetTextAngleAtIndex', index))
        if width <= 0:
            import re
            text = str(call(data, 'GetTextAtIndex', index) or '')
            width = max(1, len(re.sub(r'<[^<>]*>', 'X', text)))*height*.7
            estimated = True
        boxes.append(text_box(to_mm(position[0]), to_mm(position[1]), to_mm(width), to_mm(height), angle))
    return union(boxes), estimated


class NativeDrawing:
    def __init__(self, session, info, options, result, stop=None):
        self.session, self.info, self.options, self.result, self.stop = session, info, options, result, stop
        self.model = self.drawing = None
        self.pages = {}
        self.annotations = {}
        self.bom_rows = []

    def create(self, template, plan):
        self.model, self.drawing = self.session.new_drawing(template, plan.width_mm, plan.height_mm)
        call(self.model, 'SetUnits', self.session.c('swMM'), self.session.c('swDECIMAL'), 0, 3, False)
        units = values(call(self.model, 'GetUnits'))
        if not units or int(units[0]) != self.session.c('swMM'):
            raise ApiError('Teknik resmin mm birimi doğrulanamadı.')
        self.setup(plan)

    def setup(self, plan, *, new=False):
        checkpoint(self.stop)
        c = self.session.c
        if new:
            template_name = self.options.sheet_format or self.pages[next(iter(self.pages))]['format']
        else:
            current = call(self.drawing, 'GetCurrentSheet')
            template_name = self.options.sheet_format or str(call(current, 'GetTemplateName') or '')
            call(current, 'SetName', plan.name)
        template_kind = c('swDwgTemplateCustom' if template_name else 'swDwgTemplateNone')
        prefix = (plan.name, c('swDwgPapersUserDefined'), template_kind, plan.scale, 1.,
                  self.options.projection == 'first', template_name,
                  to_m(plan.width_mm), to_m(plan.height_mm), '')
        zones = (to_m(self.options.margin_mm),)*4 + (4, 4)
        if new and not call(self.drawing, 'NewSheet4', *prefix, *zones):
            raise ApiError('Ek pafta oluşturulamadı: '+plan.name)
        if not call(self.drawing, 'ActivateSheet', plan.name):
            raise ApiError('Pafta etkinleştirilemedi: '+plan.name)
        # SetupSheet6 has SEVENTEEN arguments; unlike SetupSheet5 it includes zones.
        if not call(self.drawing, 'SetupSheet6', *prefix, False, *zones):
            raise ApiError('Pafta / şablon ayarı SolidWorks tarafından reddedildi.')
        self.rebuild()
        self.pages[plan.name] = {'plan': plan, 'views': {}, 'format': template_name, 'tables': []}
        actual = self.sheet_state(plan.name)
        if abs(actual['width_mm']-plan.width_mm) > .05 or abs(actual['height_mm']-plan.height_mm) > .05:
            raise ApiError('Şablon seçilen pafta boyutunu uygulamadı; farklı boyutta çıktı üretilmedi.')
        if not template_name:
            self.result.warn('sheet_format', 'Şablonda antet / sayfa çerçevesi bulunamadı; firma .SLDDRT dosyası seçebilirsiniz.',
                             plan.name)

    def sheet_state(self, name):
        call(self.drawing, 'ActivateSheet', name)
        sheet = call(self.drawing, 'GetCurrentSheet')
        props = values(call(sheet, 'GetProperties2'))
        if len(props) < 8 or not props[3]:
            raise ApiError('Gerçek pafta özellikleri okunamadı.')
        return dict(name=str(call(sheet, 'GetName')), width_mm=to_mm(props[5]), height_mm=to_mm(props[6]),
                    scale=float(props[2])/float(props[3]), projection='first' if props[4] else 'third')

    def rebuild(self):
        if call(self.model, 'ForceRebuild3', False) is not True:
            raise ApiError('Teknik resim yeniden oluşturulamadı.')

    def select_view(self, view):
        call(self.model, 'ClearSelection2', True)
        name = str(call(view, 'GetName2'))
        if not call(self.drawing, 'ActivateView', name):
            raise ApiError('Görünüş etkinleştirilemedi: '+name)
        extension = get(self.model, 'Extension')
        if not call(extension, 'SelectByID2', name, 'DRAWINGVIEW', 0., 0., 0., False, 0, null_dispatch(), 0):
            raise ApiError('Görünüş seçilemedi; başka görünüşe işlem uygulanmadı: '+name)

    def create_views(self, plan):
        page = self.pages[plan.name]
        call(self.drawing, 'ActivateSheet', plan.name)
        for view_plan in plan.views:
            checkpoint(self.stop)
            x, y = (to_m(v) for v in view_plan.center)
            if view_plan.parent:
                self.select_view(page['views'][view_plan.parent])
                view = call(self.drawing, 'CreateUnfoldedViewAt3', x, y, 0., False)
            else:
                view = call(self.drawing, 'CreateDrawViewFromModelView3', self.info.source.path,
                            view_plan.model_view, x, y, 0.)
            if view is None:
                raise ApiError('Görünüş oluşturulamadı: '+view_plan.role)
            if view_plan.parent:
                if str(get(view, 'ReferencedConfiguration')) != self.info.source.configuration:
                    raise ApiError('İzdüşüm ana görünüşün konfigürasyonunu devralmadı.')
            else:
                put(view, 'ReferencedConfiguration', self.info.source.configuration)
            put(view, 'UseSheetScale', True)
            page['views'][view_plan.role] = view
        self.set_scale(plan.name, plan.scale)
        for role, scale in list(plan.view_scales.items()):
            self.set_view_scale(plan, role, scale)

    def set_view_scale(self, plan, role, scale):
        """Own scale for one view (the isometric), so it does not shrink the orthographic views."""
        view = self.pages[plan.name]['views'].get(role)
        ratio = (scale, 1.) if scale >= 1 else (1., 1/scale)
        try:
            put(view, 'UseSheetScale', False)
            put(view, 'ScaleRatio', variant(0x2005, ratio))
            self.rebuild()
            actual = values(get(view, 'ScaleRatio'))
            if len(actual) < 2 or not math.isclose(float(actual[0])/float(actual[1]), scale, rel_tol=1e-6):
                raise ApiError('görünüş ölçeği okunamadı')
        except Exception as error:      # keep the drawing valid: fall back to the sheet scale
            put(view, 'UseSheetScale', True); self.rebuild()
            plan.view_scales.pop(role, None)
            self.result.warn('view_scale', f'{role} görünüşüne ayrı ölçek uygulanamadı; pafta ölçeği kullanıldı ({error}).',
                             plan.name)

    def set_scale(self, name, scale):
        call(self.drawing, 'ActivateSheet', name)
        sheet = call(self.drawing, 'GetCurrentSheet')
        if not call(sheet, 'SetScale', scale, 1., True, False):
            raise ApiError('Pafta ölçeği uygulanamadı.')
        self.rebuild()
        actual = self.sheet_state(name)
        if not math.isclose(actual['scale'], scale, rel_tol=1e-8):
            raise ApiError('Gerçek pafta ölçeği istenen değerle uyuşmuyor.')
        self.pages[name]['plan'].scale = scale

    def actual_views(self, name, roles=None):
        page = self.pages[name]
        call(self.drawing, 'ActivateSheet', name)
        result = []
        main = str(call(page['views']['main'], 'GetName2')) if 'main' in page['views'] else ''
        for role, view in page['views'].items():
            if roles is not None and role not in roles:
                continue
            checkpoint(self.stop)
            parent = call(view, 'GetBaseView') if role in ('top', 'side') else None
            referenced = get(view, 'ReferencedDocument')
            referenced = as_interface(referenced, MODEL_IID) if referenced is not None else None
            result.append(dict(role=role, name=str(call(view, 'GetName2')), outline=outline(view),
                path=str(call(view, 'GetReferencedModelName') or ''),
                model_available=referenced is not None,
                resolved_path=str(call(referenced, 'GetPathName') or '') if referenced is not None else '',
                configuration=str(get(view, 'ReferencedConfiguration') or ''),
                parent=str(call(parent, 'GetName2')) if parent is not None else '',
                main_name=main, flat=bool(call(view, 'IsFlatPatternView')) if role == 'flat' else False,
                position=tuple(to_mm(v) for v in view_position(view))))
        return result

    def dimensions(self, name, roles=None):
        page = self.pages[name]
        call(self.drawing, 'ActivateSheet', name)
        result = []
        for role, view in page['views'].items():
            if roles is not None and role not in roles:
                continue
            display = call(view, 'GetFirstDisplayDimension5')
            seen = set()
            while display is not None:
                checkpoint(self.stop)
                if len(seen) > 2000:
                    raise ApiError('Görünüşte ölçü sayısı güvenli sınırı aştı.')
                selection = str(call(display, 'GetNameForSelection') or '')
                if not selection or selection in seen:
                    raise ApiError('Ölçü zinciri kimliği eksik veya döngüsel.')
                seen.add(selection)
                annotation = call(display, 'GetAnnotation')
                dimension = call(display, 'GetDimension2', 0)
                model_name = str(get(dimension, 'FullName') or '')
                reference = bool(call(display, 'IsReferenceDim'))
                kind = DIMENSION_TYPES.get(get(display, 'Type2'), 'unknown')
                value, box, estimated = None, None, False
                try:
                    raw_value = float(nominal_value(dimension, self.info.source.configuration, reference))
                    value = degrees(raw_value) if kind == 'angle' else to_mm(raw_value)
                except Exception:
                    pass  # validator explicitly reports unreadable numbers
                try:
                    box, estimated = annotation_box(annotation)
                except Exception:
                    pass
                dangling = optional(annotation, 'IsDangling')
                position = values(call(annotation, 'GetPosition'))
                key = name, role, selection
                self.annotations[key] = annotation
                result.append(dict(key=key, name=selection, owner=role, box=box, estimated=estimated,
                    value=value, kind=kind, reference=reference, dangling=dangling,
                    model_identity=(self.info.source.key, model_name, kind, reference) if model_name else None,
                    position=tuple(float(v) for v in position)))
                display = call(display, 'GetNext5')
        return result

    def import_dimensions(self, name):
        if not self.options.model_dimensions:
            return
        c = self.session.c
        mask = c('swInsertDimensionsMarkedForDrawing')
        for kind in ('swInsertHoleWizardProfileDimensions', 'swInsertHoleWizardLocationDimensions'):
            if kind in self.session.constants:
                mask |= c(kind)
        if self.options.include_unmarked:
            mask |= c('swInsertDimensionsNotMarkedForDrawing')
        source = c('swImportModelItemsFromAssemblyOnly' if self.info.kind == 'assembly' else
                   'swImportModelItemsFromEntireModel')
        for role, view in self.pages[name]['views'].items():
            if role == 'isometric':
                continue
            checkpoint(self.stop)
            self.select_view(view)
            call(self.drawing, 'InsertModelAnnotations3', source, mask, False, True, False, False)
        call(self.model, 'ClearSelection2', True)
        self.rebuild()

    def geometry_dimensions(self, name):
        if not self.options.geometry_dimensions:
            return
        if self.info.kind == 'assembly':
            self.result.warn('assembly_reference_dimensions', 'Montaj için tüm parça geometrilerine otomatik ölçü uygulanmadı.',
                             name)
            return
        c = self.session.c
        self.select_view(self.pages[name]['views']['main'])
        status = call(self.drawing, 'AutoDimension', c('swAutodimEntitiesAll'),
                      c('swAutodimSchemeBaseline'), c('swAutodimHorizontalPlacementAbove'),
                      c('swAutodimSchemeBaseline'), c('swAutodimVerticalPlacementRight'))
        if status != c('swAutodimStatusSuccess'):
            raise ApiError('Geometrik referans ölçüler oluşturulamadı; API kodu '+str(status))
        call(self.model, 'ClearSelection2', True)
        self.result.warn('reference_dimensions', 'Geometriden eklenen referans ölçüler tasarım ölçüsü veya tolerans sayılmaz; '
                         'imalat referanslarını kontrol edin.', name)
        self.rebuild()

    def arrange_dimensions(self, name):
        if not self.options.arrange_dimensions:
            return
        records = self.dimensions(name)
        extension = get(self.model, 'Extension')
        for role in self.pages[name]['views']:
            group = [r for r in records if r['owner'] == role]
            if not group:
                continue
            call(self.model, 'ClearSelection2', True)
            for index, record in enumerate(group):
                if not call(extension, 'SelectByID2', record['name'], 'DIMENSION', 0., 0., 0.,
                            bool(index), 0, null_dispatch(), 0):
                    raise ApiError('Ölçü yerleşimi için seçim başarısız: '+record['name'])
            if not call(extension, 'AlignDimensions', self.session.c('swAlignDimensionType_AutoArrange'), .008):
                self.result.warn('dimension_arrange', 'SolidWorks otomatik ölçü hizalamasını uygulayamadı.', name)
        call(self.model, 'ClearSelection2', True)
        self.rebuild()
        records = self.dimensions(name)
        outlines = {v['role']: v['outline'] for v in self.actual_views(name)}
        moves, unresolved = place_texts([(r['key'], r['owner'], r['box']) for r in records],
            outlines, self.pages[name]['plan'].usable)
        for record in records:
            if record['key'] not in moves:
                continue
            dx, dy = moves[record['key']]
            pos = record['position']
            if len(pos) < 3 or not call(self.annotations[record['key']], 'SetPosition2',
                                       pos[0]+to_m(dx), pos[1]+to_m(dy), pos[2]):
                self.result.warn('dimension_move', 'Ölçü konumu düzenlenemedi: '+record['name'], name)
        if unresolved:
            self.result.warn('dimension_layout', f'{len(unresolved)} ölçü metni için boş konum bulunamadı veya sınırlar okunamadı.',
                             name)
        self.rebuild()

    def fit(self, name, *, include_dimensions=False):
        """Refit measured native outlines, preserving projected view links."""
        page, options = self.pages[name], self.options
        original_scale = self.sheet_state(name)['scale']
        actual = self.actual_views(name)
        records = self.dimensions(name) if include_dimensions else []
        sizes = {v['role']: union([v['outline']]+[r['box'] for r in records
                 if r['owner'] == v['role'] and r['box'] is not None]) for v in actual}
        scales = ((options.manual_scale,) if options.manual_scale is not None else
                  tuple(sorted(set(options.scales), reverse=True)))
        for scale in scales:
            checkpoint(self.stop)
            own = page['plan'].view_scales      # views with their own scale keep their size
            predicted = {role: box if role in own else Box(0, 0, box.width*scale/original_scale,
                                   box.height*scale/original_scale) for role, box in sizes.items()}
            if arrange(page['plan'].views, scale, page['plan'].usable, options, measured=predicted) is None:
                continue
            self.set_scale(name, scale)
            for attempt in range(3):
                actual = self.actual_views(name)
                records = self.dimensions(name) if include_dimensions else []
                measured = {v['role']: union([v['outline']]+[r['box'] for r in records
                            if r['owner'] == v['role'] and r['box'] is not None]) for v in actual}
                planned = arrange(page['plan'].views, scale, page['plan'].usable, options, measured=measured)
                if planned is None:
                    break
                for target in planned:  # Move parent first; remeasure children after it moves.
                    current = self.actual_views(name, roles=(target.role,))[0]
                    dimensions = self.dimensions(name, roles=(target.role,)) if include_dimensions else []
                    bounds = union([current['outline']]+[r['box'] for r in dimensions
                                   if r['owner'] == target.role and r['box'] is not None])
                    dx, dy = target.center[0]-bounds.center[0], target.center[1]-bounds.center[1]
                    view = page['views'][target.role]
                    position = view_position(view)
                    put(view, 'Position', variant(0x2005, (float(position[0])+to_m(dx),
                        float(position[1])+to_m(dy))))
                self.rebuild()
                actual = self.actual_views(name)
                if all(page['plan'].usable.contains(v['outline']) for v in actual) and not any(
                        a['outline'].overlaps(b['outline']) for i, a in enumerate(actual) for b in actual[i+1:]):
                    page['plan'].views = planned
                    return
        raise ApiError('Gerçek görünüş / ölçü sınırları paftaya sığdırılamadı; dosya başarılı sayılmadı.')

    def title_properties(self):
        manager = prop(get(self.model, 'Extension'), 'CustomPropertyManager', '')
        c = self.session.c
        for source, target in self.options.property_map:
            value = self.info.properties.get(source, '')
            if not value.strip():
                self.result.warn('title_property', 'Antet için model özelliği eksik / boş: '+source)
            # A missing source must not leave an old template part number/revision.
            status = call(manager, 'Add3', target, c('swCustomInfoText'), value,
                          c('swCustomPropertyReplaceValue'))
            if status != c('swCustomInfoAddResult_AddedOrChanged'):
                raise ApiError('Antet özelliği yazılamadı: '+target)
        for name, page in self.pages.items():
            call(self.drawing, 'ActivateSheet', name)
            sheet = call(self.drawing, 'GetCurrentSheet')
            first = next(iter(page['views'].values()), None)
            if first is not None:
                put(sheet, 'CustomPropertyView', str(call(first, 'GetName2')))

    def center_marks(self, name):
        if not self.options.center_marks:
            return
        mask = 0
        for key, value in self.session.constants.items():
            if key.startswith('swAutoInsertCenterMark') and 'hole' in key.casefold():
                mask |= value
        if not mask:
            raise ApiError('Kurulu API’de delik merkez işareti türü bulunamadı.')
        count = 0
        for role, view in self.pages[name]['views'].items():
            if role == 'isometric':
                continue
            self.select_view(view)
            call(view, 'AutoInsertCenterMarks2', mask, 0, True, True, True, 0., 0., False, True, 0.)
            count += int(call(view, 'GetCenterMarkCount2'))
        self.result.measurements.setdefault('center_marks', {})[name] = count
        call(self.model, 'ClearSelection2', True)

    def validate(self):
        findings, snapshots = [], []
        for name, page in self.pages.items():
            state = self.sheet_state(name)
            state.update(expected=[v.role for v in page['plan'].views],
                         usable=page.get('validation_area', page['plan'].usable))
            actual = self.actual_views(name)
            records = self.dimensions(name)
            findings.extend(validate_views(state, actual, self.info.source,
                             flat_configurations=self.info.flat_configurations, projection=self.options.projection))
            findings.extend(validate_annotations(records, {v['role']: v['outline'] for v in actual},
                                                  page['plan'].usable, name))
            for record in records:
                if record['estimated']:
                    findings.append(self._warning('text_estimate', 'Ölçü metni genişliği tahmin içeriyor; yerleşimi kontrol edin.',
                                                  name, record['name']))
                if record['dangling'] is None:
                    findings.append(self._warning('attachment_unknown', 'Ölçü bağlantısı doğrulanamadı.',
                                                  name, record['name']))
            for table in page['tables']:
                if not state['usable'].contains(table):
                    raise ApiError('BOM tablosu pafta / antet güvenli alanı dışında.')
                if any(table.overlaps(v['outline']) for v in actual):
                    raise ApiError('BOM tablosu görünüşle çakışıyor.')
            snapshots.append(dict(**state, views=actual, dimensions=records))
        return findings, snapshots

    def verify_saved(self, path, snapshots):
        """Reopen the native file and enumerate ALL saved sheets/views, including extras."""
        from .manufacturing import table_box, quantity_columns, displayed_quantity
        model, drawing = self.session.open_drawing(path)
        check = NativeDrawing(self.session, self.info, self.options, self.result, self.stop)
        check.model, check.drawing = model, drawing
        try:
            names = tuple(str(v) for v in values(call(drawing, 'GetSheetNames')))
            if set(names) != {s['name'] for s in snapshots} or len(names) != len(snapshots):
                raise ApiError('Kaydedilen SLDDRW pafta listesi beklenen listeyle uyuşmuyor.')
            for state in snapshots:
                name = state['name']
                if not call(drawing, 'ActivateSheet', name):
                    raise ApiError('Kaydedilen pafta açılamadı: '+name)
                expected = {v['name']: v['role'] for v in state['views']}
                view = call(drawing, 'GetFirstView')  # The first entry is the sheet itself.
                view = call(view, 'GetNextView') if view is not None else None
                handles, tables = {}, []
                while view is not None:
                    checkpoint(self.stop)
                    if len(handles) > 100:
                        raise ApiError('Kayıtlı görünüş listesi döngüsel veya beklenenden büyük.')
                    view_name = str(call(view, 'GetName2'))
                    if view_name not in expected:
                        raise ApiError('Şablondan / kayıt işleminden beklenmeyen ek görünüş bulundu: '+view_name)
                    role = expected[view_name]
                    if role in handles:
                        raise ApiError('Kaydedilen görünüş tekrarlı.')
                    handles[role] = view
                    for table in values(call(view, 'GetTableAnnotations')):
                        generic = self.session.named_interface(table, 'ITableAnnotation')
                        if int(get(generic, 'Type')) == self.session.c('swTableAnnotation_BillOfMaterials'):
                            tables.append(table_box(generic))
                            columns = quantity_columns(generic, self.session)
                            if len(columns) == 1:
                                for row in self.bom_rows:
                                    number, text = displayed_quantity(generic, row['row_index'], columns[0])
                                    if number != row['quantity']:
                                        raise ApiError('Kayıt sonrası BOM adetleri değişmiş.')
                    view = call(view, 'GetNextView')
                if set(handles) != set(state['expected']):
                    raise ApiError('SLDDRW yeniden açıldığında görünüşler eksik.')
                original = self.pages[name]
                if len(tables) != len(original['tables']):
                    raise ApiError('BOM tablosu kaydedilen teknik resimde bulunamadı veya tekrarlı.')
                check.pages[name] = dict(plan=original['plan'], views=handles, tables=tables,
                    format=original['format'], validation_area=state['usable'])
                actual_state = check.sheet_state(name)
                for key in ('width_mm', 'height_mm', 'scale'):
                    if not math.isclose(actual_state[key], state[key], rel_tol=1e-7, abs_tol=.001):
                        raise ApiError('Kaydedilen pafta boyutu / ölçeği değişmiş.')
            findings, reread = check.validate()
            for before, after in zip(snapshots, reread):
                if len(before['dimensions']) != len(after['dimensions']):
                    raise ApiError('Kayıt sonrası model ölçüleri korunmamış.')
            return findings, reread
        finally:
            check.close()

    @staticmethod
    def _warning(code, text, sheet='', view=''):
        from .models import Finding
        return Finding('WARNING', code, text, sheet, view)

    def save(self, path, kind):
        self.session.activate(self.model)
        call(self.model, 'ClearSelection2', True)
        errors, warnings = out_int(), out_int()
        export = null_dispatch()
        c = self.session.c
        if kind == 'pdf':
            export = call(self.session.app, 'GetExportFileData', c('swExportPdfData'))
            if export is None:
                raise ApiError('PDF aktarım nesnesi oluşturulamadı.')
            put(export, 'ViewPdfAfterSaving', False)
            if not call(export, 'SetSheets', c('swExportData_ExportAllSheets'), variant(0, None)):
                raise ApiError('PDF için tüm paftalar seçilemedi.')
        flags = c('swSaveAsOptions_Silent')
        if kind != 'slddrw':
            flags |= c('swSaveAsOptions_Copy')
        saved = call(get(self.model, 'Extension'), 'SaveAs', str(path), c('swSaveAsCurrentVersion'),
                     flags, export, errors, warnings)
        if saved is not True or errors.value:
            raise ApiError(f'{kind.upper()} kaydı başarısız; API hata kodu {errors.value}.',
                           errors.value, warnings.value)
        if warnings.value:
            self.result.warn('save_warning', f'{kind.upper()} kayıt uyarı kodu: {warnings.value}.')
        return str(path)

    def close(self):
        self.annotations.clear()
        for page in self.pages.values():
            page['views'].clear()
        self.drawing = None
        if self.model is not None:
            model, self.model = self.model, None
            self.session.close_created(model)
