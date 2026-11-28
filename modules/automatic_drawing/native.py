"""Published SolidWorks drawing APIs, with explicit units and real readback.

IModelDoc2 and IDrawingDoc are distinct dual interfaces. Their pointers never
leave this worker-owned adapter. See docs/automatic-drawing/SOLIDWORKS_API_REFERENCES.md.
"""

import math

from modules.cad_converter.api import ApiError, MODEL_IID, PART_IID
from modules.tolerance_stack.solidworks_reader import nominal_value, DIMENSION_TYPES
from .solidworks import call, get, put, prop, optional, values, variant, out_int, null_dispatch, as_interface
from .models import Box, Finding, checkpoint, to_mm, to_m, degrees, identity
from .layout import arrange, place_texts, text_box, union
from .validation import validate_views, validate_annotations, validate_annotation_obstacles


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


def annotation_leaders(annotation):
    count = optional(annotation, 'GetLeaderCount')
    segments = []
    for index in range(count if type(count) is int and 0 < count <= 100 else 0):
        raw = values(optional(annotation, 'GetLeaderPointsAtIndex', index, default=()))
        if len(raw) in (6, 9) and all(isinstance(x, (int, float)) and math.isfinite(x) for x in raw):
            points = [(to_mm(raw[i]), to_mm(raw[i+1])) for i in range(0, len(raw), 3)]
            segments.extend(zip(points, points[1:]))
    return segments, type(count) is int and (count < 0 or count > 100 or count > len(segments))


def linear_placement(annotation, kind, box, value):
    """Direction and near edge from the native arrow and extension lines."""
    data = optional(annotation, 'GetDisplayData')
    arrow = values(optional(data, 'GetArrowHeadAtIndex2', 0, default=()))
    if kind == 'linear':
        if len(arrow) == 12:
            dx, dy = map(abs, arrow[3:5])
            if dx > .999:
                kind = 'horizontal'
            elif dy > .999:
                kind = 'vertical'
            else:
                return None
        elif box.height > 2*box.width:
            kind = 'vertical'
        elif box.width > 2*box.height:
            kind = 'horizontal'
        else:
            return None
    index = 0 if kind == 'vertical' else 1
    anchors = []
    count = optional(data, 'GetLineCount', default=0)
    if len(arrow) == 12 and type(count) is int and 0 < count <= 24:
        for i in range(count):
            line = values(optional(data, 'GetLineAtIndex3', i, default=()))
            if len(line) != 10 or abs(line[5-index]-line[8-index]) > 1e-6:
                continue
            ends = line[4+index], line[7+index]
            distances = tuple(abs(end-arrow[index]) for end in ends)
            if min(distances) <= .002 and max(distances) > .002:
                anchors.append(to_mm(ends[distances.index(max(distances))]))
    anchor = sum(anchors)/len(anchors) if anchors else box.center[index]
    return kind, anchor, abs(value) if value is not None and math.isfinite(value) else float('inf')


def derived_labels(view, planned):
    kind = planned.role
    symbol = call(view, 'GetSection' if kind == 'section' else 'GetDetail')
    label = planned.derived.label
    if symbol is None:
        return []
    if kind == 'section':
        raw = values(optional(symbol, 'GetTextInfo', default=()))
        points = (raw[:2], raw[3:5]) if len(raw) == 6 else ()
    else:
        x, y = variant(0x4005, float('nan')), variant(0x4005, float('nan'))
        result = optional(symbol, 'GetLabelPosition', x, y)
        if isinstance(result, (tuple, list)):
            if len(result) != 2:
                raise ApiError('Detay etiketi konumunun BYREF sözleşmesi geçersiz.')
            x.value, y.value = result
        points = ((x.value, y.value),)
    style = optional(symbol, 'GetTextFormat')
    height = optional(style, 'CharHeight', property=True)
    boxes = [Box(to_mm(x), to_mm(y-height), to_mm(height)*len(label)*.8, to_mm(height))
             for x, y in points if type(height) in (int, float) and height > 0. and
             all(type(v) in (int, float) and math.isfinite(v) for v in (x, y, height))]
    return [dict(name=f'{label}/{index}', owner='main', kind='view_label', annotation_kind='view_label',
                 box=box, estimated=box is not None) for index, box in enumerate(boxes or [None], 1)]


# SolidWorks names the standard model views in its UI language and requires the exact name.
STANDARD_ORDER = ('*Front', '*Back', '*Left', '*Right', '*Top', '*Bottom', '*Isometric')
LOCAL_VIEW_NAMES = {'*Front': '*Ön', '*Back': '*Arka', '*Left': '*Sol', '*Right': '*Sağ',
                    '*Top': '*Üst', '*Bottom': '*Alt', '*Isometric': '*İzometrik'}


def scale_ratio(scale):
    """Sheet scale as SolidWorks stores it: whole-number ratio (0.5 → 1:2, 0.4 → 2:5, 2.5 → 5:2)."""
    from fractions import Fraction
    fraction = Fraction(scale).limit_denominator(1000)
    if not math.isclose(float(fraction), scale, rel_tol=1e-9):
        return float(scale), 1.
    return float(fraction.numerator), float(fraction.denominator)


class NativeDrawing:
    def __init__(self, session, info, options, result, stop=None):
        self.session, self.info, self.options, self.result, self.stop = session, info, options, result, stop
        self.model = self.drawing = None
        self.template, self.auto_format = '', False
        self.pages = {}
        self.annotations = {}
        self.bom_rows = []

    def create(self, template, plan):
        self.template = template
        self.model, self.drawing = self.session.new_drawing(template, plan.width_mm, plan.height_mm,
                                                            paper=self.paper_code(plan))
        call(self.model, 'SetUnits', self.session.c('swMM'), self.session.c('swDECIMAL'), 0, 3, False)
        units = values(call(self.model, 'GetUnits'))
        if not units or int(units[0]) != self.session.c('swMM'):
            raise ApiError('Teknik resmin mm birimi doğrulanamadı.')
        self.setup(plan)

    def paper_code(self, plan):
        """SolidWorks' own code for a standard ISO sheet (its templates and formats key on it)."""
        name = {'A4': 'swDwgPaperA4size', 'A3': 'swDwgPaperA3size', 'A2': 'swDwgPaperA2size',
                'A1': 'swDwgPaperA1size', 'A0': 'swDwgPaperA0size'}.get(getattr(plan, 'paper', ''))
        try:
            return self.session.c(name) if name else self.session.c('swDwgPapersUserDefined')
        except (KeyError, AttributeError):
            return self.session.c('swDwgPapersUserDefined')

    def keep_template_format(self, plan):
        """Scale/projection on the template's own sheet, keeping its title block.

        The path the shaft drawing uses on real SolidWorks: no SetupSheet when no separate
        sheet format was chosen, only ISheet.SetProperties2 on the sheet NewDocument made.
        Returns False (nothing kept) when SolidWorks refuses or the size is not the planned one.
        """
        sheet = call(self.drawing, 'GetCurrentSheet')
        props = values(call(sheet, 'GetProperties2'))
        if len(props) < 8:
            return False
        scale1, scale2 = scale_ratio(plan.scale)
        try:
            accepted = call(sheet, 'SetProperties2', self.paper_code(plan), int(props[1]), scale1, scale2,
                            self.options.projection == 'first', to_m(plan.width_mm), to_m(plan.height_mm), True)
        except ApiError:
            return False
        if accepted is False:
            return False
        self.rebuild()
        actual = self.sheet_state(plan.name)
        return (abs(actual['width_mm']-plan.width_mm) <= .05 and abs(actual['height_mm']-plan.height_mm) <= .05
                and abs(actual['scale'] - scale1/scale2) <= 1e-9 * max(1., scale1/scale2)
                and actual['projection'] == self.options.projection)

    def setup(self, plan, *, new=False):
        checkpoint(self.stop)
        c = self.session.c
        if new:
            template_name = self.options.sheet_format or (
                self.standard_format(plan) if self.auto_format else self.pages[next(iter(self.pages))]['format'])
        else:
            current = call(self.drawing, 'GetCurrentSheet')
            template_name = self.options.sheet_format or str(call(current, 'GetTemplateName') or '')
            if not template_name or template_name.startswith('*'):
                # '*.drt': the template has no sheet format; it is not a file to load
                # (SetupSheet6 returns False for it). Use the installed ISO format instead.
                self.auto_format = True
                template_name = self.standard_format(plan)
            call(current, 'SetName', plan.name)
            # Keep the template's own sheet only when it HAS a sheet format; a '*.drt'
            # template would keep no title block, so the installed ISO format is set up below.
            if not self.options.sheet_format and not self.auto_format and self.keep_template_format(plan):
                self.result.measurements.setdefault('sheet_setup', {})[plan.name] = 'template'
                self.pages[plan.name] = {'plan': plan, 'views': {}, 'format': template_name, 'tables': [], 'notes': []}
                if not template_name:
                    self.result.warn('sheet_format', 'Şablonda antet / sayfa çerçevesi bulunamadı; firma .SLDDRT '
                                     'dosyası seçebilirsiniz.', plan.name)
                return
        zones = (to_m(self.options.margin_mm),)*4 + (4, 4)
        scale1, scale2 = scale_ratio(plan.scale)
        def prefix(template, view_name, size=True):
            kind = c('swDwgTemplateCustom' if template else 'swDwgTemplateNone')
            return (plan.name, c('swDwgPapersUserDefined'), kind, scale1, scale2,
                    self.options.projection == 'first', template,
                    to_m(plan.width_mm) if size else 0., to_m(plan.height_mm) if size else 0., view_name)
        # Untested combinations are tried in order of likelihood; the first one SolidWorks
        # accepts is recorded. 'no_format' drops the sheet format and says so.
        attempts = [('standard', template_name, ''), ('default_view', template_name, 'Default')]
        if template_name:
            attempts += [('format_size', template_name, 'Default'), ('no_format', '', '')]
        if new:
            for label, template, view_name in attempts:
                if call(self.drawing, 'NewSheet4', *prefix(template, view_name, label != 'format_size'), *zones):
                    break
            else:
                raise ApiError('Ek pafta oluşturulamadı: '+plan.name+' · '+self._sheet_arguments(prefix(template_name, ''), zones))
        if not call(self.drawing, 'ActivateSheet', plan.name):
            raise ApiError('Pafta etkinleştirilemedi: '+plan.name)
        # SetupSheet6 has SEVENTEEN arguments; unlike SetupSheet5 it includes zones.
        for label, template, view_name in attempts:
            if not call(self.drawing, 'SetupSheet6', *prefix(template, view_name, label != 'format_size'), False, *zones):
                continue
            if label == 'format_size':      # only when the sheet format is the planned paper itself
                self.rebuild(); actual = self.sheet_state(plan.name)
                if abs(actual['width_mm']-plan.width_mm) > .05 or abs(actual['height_mm']-plan.height_mm) > .05:
                    continue
            break
        else:
            raise ApiError('Pafta / şablon ayarı SolidWorks tarafından reddedildi. '
                           + self._sheet_arguments(prefix(template_name, ''), zones))
        self.result.measurements.setdefault('sheet_setup', {})[plan.name] = label
        if label != 'standard':
            self.result.warn('sheet_setup', f'Pafta ayarı ilk denemede reddedildi; "{label}" ayarıyla kuruldu.'
                             + (f' Şablonun sayfa biçimi (antet) uygulanamadı: {template_name}' if label == 'no_format' else '')
                             + (' Sayfa biçiminin kendi boyutu kullanıldı.' if label == 'format_size' else ''),
                             plan.name)
        template_name = template
        self.rebuild()
        self.pages[plan.name] = {'plan': plan, 'views': {}, 'format': template_name, 'tables': [], 'notes': []}
        actual = self.sheet_state(plan.name)
        if abs(actual['width_mm']-plan.width_mm) > .05 or abs(actual['height_mm']-plan.height_mm) > .05:
            raise ApiError('Şablon seçilen pafta boyutunu uygulamadı; farklı boyutta çıktı üretilmedi.')
        if not template_name:
            self.result.warn('sheet_format', 'Şablonda antet / sayfa çerçevesi bulunamadı; firma .SLDDRT dosyası seçebilirsiniz.',
                             plan.name)

    def standard_format(self, plan):
        """The installed '<paper> - iso.slddrt' for a template without a sheet format, or ''."""
        find = getattr(self.session, 'standard_sheet_format', None)
        path = find(plan.paper, getattr(self, 'template', '')) if find is not None else ''
        if path:
            files = self.result.measurements.setdefault('sheet_format_file', {})
            repeated = path in files.values()
            files[plan.name] = path
            if not repeated:     # one warning per format file, every sheet is recorded
                self.result.warn('sheet_format_standard', 'Şablonda antet / sayfa biçimi yoktu; SolidWorks’ün standart '
                                 'sayfa biçimi uygulandı: '+path+'. Firma anteti için .SLDDRT seçebilirsiniz.', plan.name)
        return path

    def _sheet_arguments(self, prefix, zones):
        """The values SolidWorks refused, for the report (a refusal gives no reason)."""
        name, paper, kind, scale1, scale2, first, template, width, height, view = prefix
        return (f'Pafta "{name}", {to_mm(width):g} × {to_mm(height):g} mm, ölçek {scale1:g}:{scale2:g}, '
                f'{"1." if first else "3."} açı, şablon "{template or "yok"}", kenar {to_mm(zones[0]):g} mm, '
                f'alan {zones[4]}×{zones[5]}.')

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
            if view_plan.derived:
                view = self.create_derived_view(page['views'][view_plan.parent], view_plan, x, y)
            elif view_plan.parent:
                self.select_view(page['views'][view_plan.parent])
                view = call(self.drawing, 'CreateUnfoldedViewAt3', x, y, 0., False)
            else:
                view = self.model_view_at(view_plan, x, y)
            if view is None:
                raise ApiError('Görünüş oluşturulamadı: '+view_plan.role)
            if view_plan.parent:
                if str(get(view, 'ReferencedConfiguration')) != self.info.source.configuration:
                    raise ApiError('İzdüşüm ana görünüşün konfigürasyonunu devralmadı.')
            else:
                put(view, 'ReferencedConfiguration', self.info.source.configuration)
            if not view_plan.derived or view_plan.role == 'section':
                put(view, 'UseSheetScale', 1)
            page['views'][view_plan.role] = view
        self.set_scale(plan.name, plan.scale)
        for role, scale in list(plan.view_scales.items()):
            if role != 'detail':
                self.set_view_scale(plan, role, scale)

    def transform_point(self, point, *transforms):
        utility = call(self.session.app, 'GetMathUtility')
        result = call(utility, 'CreatePoint', variant(0x2005, point))
        for transform in transforms:
            result = call(result, 'MultiplyTransform', transform)
        coordinates = tuple(float(value) for value in values(get(result, 'ArrayData')))
        if len(coordinates) != 3 or not all(math.isfinite(value) for value in coordinates):
            raise ApiError('Çizim koordinat dönüşümü okunamadı.')
        return coordinates

    def create_derived_view(self, parent, plan, x, y):
        evidence = plan.derived
        name = str(call(parent, 'GetName2'))
        if not call(self.drawing, 'ActivateView', name):
            raise ApiError('Kesit/detay için ana görünüş etkinleştirilemedi.')
        call(self.model, 'ClearSelection2', True)
        view_transform = get(parent, 'ModelToViewTransform')
        sketch_transform = get(call(parent, 'GetSketch'), 'ModelToSketchTransform')
        point = tuple(to_m(v) for v in evidence.point_mm)
        px, py, _ = self.transform_point(point, view_transform)
        parent_box = outline(parent)
        if not parent_box.grow(2.).contains(Box(to_mm(px), to_mm(py), 0., 0.)):
            raise ApiError('Kesit/detay referans noktası ana görünüşe izdüşürülemedi.')
        sketch = get(self.model, 'SketchManager')
        original = get(sketch, 'AddToDB')
        try:
            put(sketch, 'AddToDB', True)
            if plan.role == 'section':
                # Obtain the signed direction from the actual view transform.
                end = tuple(v+d for v, d in zip(point, evidence.direction))
                ex, ey, _ = self.transform_point(end, view_transform)
                length = math.hypot(ex-px, ey-py)
                if length <= 1e-9:
                    raise ApiError('Kesit ekseni ana görünüşte izlenemedi.')
                reach = to_m(math.hypot(parent_box.width, parent_box.height)+5.)
                dx, dy = (ex-px)*reach/length, (ey-py)*reach/length
            else:
                ratio = values(get(parent, 'ScaleRatio'))
                if len(ratio) != 2 or ratio[0] <= 0 or ratio[1] <= 0:
                    raise ApiError('Detay çemberi için ana görünüş ölçeği okunamadı.')
                dx, dy = to_m(evidence.radius_mm)*ratio[0]/ratio[1], 0.
            start = (px-dx, py-dy, 0.) if plan.role == 'section' else (px, py, 0.)
            first = self.transform_point(start, sketch_transform)
            last = self.transform_point((px+dx, py+dy, 0.), sketch_transform)
            segment = call(sketch, 'CreateLine' if plan.role == 'section' else 'CreateCircle', *first, *last)
        finally:
            put(sketch, 'AddToDB', original)
        if segment is None or not call(segment, 'Select4', False, null_dispatch()):
            raise ApiError('Kesit çizgisi veya detay çemberi görünüş eskizinde seçilemedi.')
        try:
            c = self.session.c
            if plan.role == 'section':
                view = call(self.drawing, 'CreateSectionViewAt5', x, y, 0., evidence.label,
                            c('swCreateSectionView_ScaleWithModel'), variant(0, None), 0.)
                section = call(view, 'GetSection') if view is not None else None
                if section is None or call(section, 'SetLabel2', evidence.label) != 0:
                    raise ApiError('Native kesit veya benzersiz kesit etiketi oluşturulamadı.')
            else:
                view = call(self.drawing, 'CreateDetailViewAt4', x, y, 0., c('swDetViewSTANDARD'),
                            evidence.scale, 1., evidence.label, c('swDetCircleCIRCLE'), True, False, False, 5)
                if view is None or call(view, 'GetDetail') is None:
                    raise ApiError('Native detay görünüşü oluşturulamadı.')
            return view
        finally:
            call(self.model, 'ClearSelection2', True)

    def model_view_names(self):
        """The source model's named views as SolidWorks lists them (localized), or ()."""
        if not hasattr(self, '_model_views'):
            self._model_views = ()
            try:
                model = call(self.session.app, 'GetOpenDocumentByName', self.info.source.path)
                if model is not None:
                    self._model_views = tuple(str(v) for v in values(call(model, 'GetModelViewNames')) if v)
            except Exception:       # diagnostics only; the English name was already refused
                pass
        return self._model_views

    def model_view_at(self, view_plan, x, y):
        """Create a model view; standard view names are localized ('*Ön' in Turkish SolidWorks)."""
        def create(name):
            return call(self.drawing, 'CreateDrawViewFromModelView3', self.info.source.path, name, x, y, 0.)
        view = create(view_plan.model_view)
        if view is not None:
            return view
        candidates = [LOCAL_VIEW_NAMES.get(view_plan.model_view)]
        names = self.model_view_names()
        standard = [n for n in names if n.startswith('*')]
        if view_plan.model_view in STANDARD_ORDER and len(standard) >= len(STANDARD_ORDER):
            candidates.append(standard[STANDARD_ORDER.index(view_plan.model_view)])
        for name in dict.fromkeys(c for c in candidates if c and c != view_plan.model_view):
            view = create(name)
            if view is not None:
                self.result.measurements.setdefault('model_view_names', {})[view_plan.model_view] = name
                return view
        raise ApiError(f'Görünüş oluşturulamadı: {view_plan.role} ({view_plan.model_view}). '
                       f'Modelin görünüş adları: {", ".join(names) or "okunamadı"}.')

    def set_view_scale(self, plan, role, scale):
        """Own scale for one view (the isometric), so it does not shrink the orthographic views."""
        view = self.pages[plan.name]['views'].get(role)
        ratio = (scale, 1.) if scale >= 1 else (1., 1/scale)
        try:
            put(view, 'UseSheetScale', 0)
            put(view, 'ScaleRatio', variant(0x2005, ratio))
            self.rebuild()
            actual = values(get(view, 'ScaleRatio'))
            if len(actual) < 2 or not math.isclose(float(actual[0])/float(actual[1]), scale, rel_tol=1e-6):
                raise ApiError('görünüş ölçeği okunamadı')
        except Exception as error:      # keep the drawing valid: fall back to the sheet scale
            put(view, 'UseSheetScale', 1); self.rebuild()
            plan.view_scales.pop(role, None)
            self.result.warn('view_scale', f'{role} görünüşüne ayrı ölçek uygulanamadı; pafta ölçeği kullanıldı ({error}).',
                             plan.name)

    def set_scale(self, name, scale):
        call(self.drawing, 'ActivateSheet', name)
        sheet = call(self.drawing, 'GetCurrentSheet')
        if not call(sheet, 'SetScale', *scale_ratio(scale), True, False):
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
            parent = call(view, 'GetBaseView') if role in ('top', 'side', 'section', 'detail') else None
            referenced = get(view, 'ReferencedDocument')
            referenced = as_interface(referenced, MODEL_IID) if referenced is not None else None
            record = dict(role=role, name=str(call(view, 'GetName2')), outline=outline(view),
                path=str(call(view, 'GetReferencedModelName') or ''),
                model_available=referenced is not None,
                resolved_path=str(call(referenced, 'GetPathName') or '') if referenced is not None else '',
                configuration=str(get(view, 'ReferencedConfiguration') or ''),
                parent=str(call(parent, 'GetName2')) if parent is not None else '',
                main_name=main, flat=False,
                position=tuple(to_mm(v) for v in view_position(view)))
            if role in ('section', 'detail'):
                derived = next(v.derived for v in page['plan'].views if v.role == role)
                native = call(view, 'GetSection' if role == 'section' else 'GetDetail')
                label = str(call(native, 'GetLabel') or '') if native is not None else ''
                record.update(label=label, expected_label=derived.label, offset_axis=derived.offset_axis)
                if role == 'detail':
                    ratio = values(get(view, 'ScaleRatio'))
                    record.update(view_scale=float(ratio[0])/float(ratio[1]) if len(ratio) == 2 and ratio[1] else 0.,
                                  expected_scale=derived.scale)
            target = page.get('flat_body') if role == 'flat' else None
            if target is not None:
                from .sheetmetal import verify_unfolded
                if referenced is None:
                    raise ApiError('Gövde açınımının kaynak belgesi çözümlenemedi.')
                verify_unfolded(self.session, referenced, target, target.configurations[0])
                bodies, count = values(get(view, 'Bodies')), int(call(view, 'GetBodiesCount'))
                if not bodies and count == 0:
                    # Recorded on SolidWorks 2025 SP5: a view keeps no body filter (GetBodiesCount 0,
                    # Bodies empty, even after Bodies is written). A single-body part: its only body.
                    solids = values(call(as_interface(referenced, PART_IID), 'GetBodies2',
                                         self.session.c('swSolidBody'), False))
                    if len(solids) == 1:
                        bodies, count = solids, 1
                    elif call(view, 'IsFlatPatternView') and self.only_target_unfolded(referenced, target, record['configuration']):
                        # Multibody FLAT PATTERN view (recorded, 2026-11-25 again): no body filter either;
                        # its saved flat configuration unfolds exactly the target body's FlatPattern.
                        # An unfiltered MODEL view of a multibody part shows every body: never accepted.
                        record.update(expected_body=target.body_ref, expected_flat_configuration=target.configurations[0],
                                      body_references=(target.body_ref,), body_count=1, body_label=target.label, flat=True)
                        result.append(record)
                        continue
                if count == 1 and len(self.info.sheet_bodies) > 1 and not self.only_target_unfolded(
                        referenced, target, record['configuration']):
                    raise ApiError('Açınım konfigürasyonu başka veya birden fazla gövdeyi açıyor.')
                record.update(expected_body=target.body_ref, expected_flat_configuration=target.configurations[0],
                    body_references=tuple(self.session.persistent_ref(referenced, body) for body in bodies)
                                    if referenced is not None else (),
                    body_count=count, body_label=target.label, flat=True)
                bodies = ()
            result.append(record)
        return result

    def only_target_unfolded(self, model, target, configuration):
        """True when ``configuration`` unfolds the target body's FlatPattern and no other sheet body's."""
        from .sheetmetal import feature_by_ref, unfolded_configurations
        rows = [row for row in getattr(self.info, 'sheet_bodies', ()) if row.flat_feature and row.flat_ref]
        if not configuration or target not in rows or len(rows) < 2:
            return False
        for row in rows:
            feature = feature_by_ref(self.session, model, row.flat_feature, row.flat_ref, 'FlatPattern')
            unfolded = unfolded_configurations(self.session, feature, (configuration,)) == (configuration,)
            if unfolded != (row is target):
                return False
        return True

    def body_heading(self, name, row, area):
        self.session.activate(self.model)
        if not call(self.drawing, 'ActivateSheet', name):
            raise ApiError('Gövde kimliği için pafta etkinleştirilemedi.')
        call(self.model, 'ClearSelection2', True)
        text = row.label
        if row.thickness_mm is not None:
            text += f'\nt = {row.thickness_mm:g} mm'
        if row.material:
            text += '\n'+row.material
        note = call(self.model, 'InsertNote', text)
        if note is None:
            raise ApiError('Açınım paftasına gövde kimliği yazılamadı.')
        annotation = call(note, 'GetAnnotation')
        note_name = str(call(note, 'GetName') or '')
        if not note_name:
            raise ApiError('Gövde kimliği anotasyonunun native adı okunamadı.')
        # The note must belong to the SHEET so it cannot follow/scale with a body view.
        # Recorded on SolidWorks 2025 SP5: with the sheet active InsertNote already puts the
        # note on the sheet; Select3 then returns False and AttachAnnotation returns True even
        # with nothing selected. So ownership is read back from the sheet's own note list.
        if not self.sheet_has_note(note_name):
            call(annotation, 'Select3', False, null_dispatch())
            call(self.drawing, 'AttachAnnotation', self.session.c('swAttachAnnotationOption_Sheet'))
            if not self.sheet_has_note(note_name):
                raise ApiError('Gövde kimliği görünüş yerine paftaya bağlanamadı.')
        call(self.model, 'ClearSelection2', True)
        text_format = call(annotation, 'GetTextFormat', 0)
        if text_format is None:
            raise ApiError('Gövde kimliği yazı biçimi okunamadı.')
        put(text_format, 'CharHeight', .003)
        if not call(annotation, 'SetTextFormat', 0, False, text_format):
            raise ApiError('Gövde kimliği yazı boyutu uygulanamadı.')
        if not call(annotation, 'SetPosition2', to_m(area.x+1.), to_m(area.top-4.), 0.):
            raise ApiError('Gövde kimliği ayrılan alana yerleştirilemedi.')
        self.pages[name]['notes'].append(dict(handle=note, name=note_name, text=text, area=area))

    def sheet_has_note(self, note_name):
        """The active sheet's own notes (GetFirstView is the sheet itself), by native name."""
        sheet = call(self.drawing, 'GetFirstView')
        return sheet is not None and note_name in {str(call(n, 'GetName')) for n in values(call(sheet, 'GetNotes'))}

    def notes(self, name):
        records, findings = [], []
        for target in self.pages[name].get('notes', ()):
            note = target['handle']
            text = str(call(note, 'GetText') or '').replace('\r\n', '\n').replace('\r', '\n')
            if text != target['text']:
                findings.append(Finding('FAIL', 'body_heading', 'Gövde kimliği / kalınlık notu değişmiş.', name))
            annotation = call(note, 'GetAnnotation')
            box, estimated = annotation_box(annotation)
            if box is None:
                findings.append(self._warning('heading_bounds', 'Gövde kimliği metin sınırları okunamadı.', name))
            elif not target['area'].contains(box):
                findings.append(Finding('FAIL', 'heading_outside', 'Gövde kimliği ayrılan başlık alanına sığmıyor.', name))
            if estimated:
                findings.append(self._warning('heading_estimate', 'Gövde kimliği metin genişliği tahmin içeriyor.', name))
            records.append(dict(name=target['name'], text=text, box=box, area=target['area']))
        return records, findings

    def dimensions(self, name, roles=None):
        page = self.pages[name]
        call(self.drawing, 'ActivateSheet', name)
        result = []
        for role, view in page['views'].items():
            if roles is not None and role not in roles:
                continue
            configuration = str(get(view, 'ReferencedConfiguration') or '')
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
                    raw_value = float(nominal_value(dimension, configuration, reference))
                    value = degrees(raw_value) if kind == 'angle' else to_mm(raw_value)
                    if value == 0:
                        # A dimension owned by the drawing (AutoDimension on a flat view): recorded
                        # on SolidWorks 2025 SP5, the model-configuration read returns 0 for it while
                        # Value holds it in the drawing's own units (mm, set in create()).
                        value = float(get(dimension, 'Value'))
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
                    annotation_kind='hole_callout' if optional(display, 'IsHoleCallout') is True else '',
                    model_identity=(identity(self.info.source.path, configuration), model_name, kind, reference)
                                   if model_name else None,
                    position=tuple(float(v) for v in position)))
                result[-1]['leaders'], result[-1]['leader_bounds_unknown'] = annotation_leaders(annotation)
                display = call(display, 'GetNext5')
        return result

    def annotation_obstacles(self, name):
        from collections import Counter
        from .hole_annotations import hole_table_tags
        from .manufacturing import table_box
        page = self.pages[name]
        call(self.drawing, 'ActivateSheet', name)
        first = call(self.drawing, 'GetFirstView')
        supported = {self.session.constants[key]: kind for key, kind in (
            ('swNote', 'note'), ('swLeader', 'leader')) if key in self.session.constants}
        hidden = {self.session.constants[key] for key in ('swAnnotationHidden', 'swAnnotationHalfHidden')
                  if key in self.session.constants}
        records, seen = [], set()
        wizard_notes = Counter(page.get('wizard_notes', ()))
        for role, view in [('sheet', first), *page['views'].items()]:
            if view is None:
                continue
            for annotation in values(optional(view, 'GetAnnotations', default=())):
                checkpoint(self.stop)
                kind = supported.get(optional(annotation, 'GetType'))
                if kind is None or optional(annotation, 'Visible', property=True) in hidden:
                    continue
                label = str(optional(annotation, 'GetName') or kind)
                key = role, label
                if key in seen:
                    continue
                seen.add(key)
                try:
                    box, estimated = annotation_box(annotation)
                except (ValueError, ApiError):
                    box, estimated = None, False
                specific = optional(annotation, 'GetSpecificAnnotation')
                content = str(optional(specific, 'GetText') or '').replace('\r\n', '\n').replace('\r', '\n') if kind == 'note' else ''
                if wizard_notes[content]:
                    wizard_notes[content] -= 1
                    kind = 'wizard_note'
                if optional(specific, 'IsBomBalloon') is True:
                    kind = 'balloon'
                if content and role in ('main', 'section', 'detail'):
                    labels = [v.derived.label for v in page['plan'].views if v.derived]
                    if any(content.strip() in (label, label+'-'+label, 'KESİT '+label+'-'+label,
                                                'SECTION '+label+'-'+label) for label in labels):
                        kind = 'view_label'
                if role == 'sheet' and (box is None or box.top <= page['plan'].usable.y):
                    kind = 'title'
                leaders, unreadable = annotation_leaders(annotation)
                record = dict(name=label, owner=role, kind=kind, annotation_kind=kind, box=box,
                                    estimated=estimated, leaders=leaders, leader_bounds_unknown=unreadable,
                                    text=content, dangling=optional(annotation, 'IsDangling'))
                if kind == 'wizard_note' and role in page['views']:
                    record['key'] = name, role, 'wizard_note', label
                    record['position'] = values(call(annotation, 'GetPosition'))
                    self.annotations[record['key']] = annotation
                records.append(record)
            for table in values(optional(view, 'GetTableAnnotations', default=())):
                generic = self.session.named_interface(table, 'ITableAnnotation')
                annotation = call(generic, 'GetAnnotation')
                label = str(optional(annotation, 'GetName') or '')
                bounds = table_box(generic)
                key = 'table', label or bounds
                if key in seen:
                    continue
                seen.add(key)
                code = int(get(generic, 'Type'))
                title_type = self.session.constants.get('swTableAnnotation_TitleBlock')
                hole_type = self.session.constants.get('swTableAnnotation_HoleChart')
                kind = 'title' if code == title_type else 'hole_table' if code == hole_type else 'table'
                records.append(dict(name=label or kind, owner=role, kind=kind, box=bounds,
                                    annotation_kind=kind, rows=int(get(generic, 'RowCount'))))
                if kind == 'hole_table':
                    records[-1]['tags'] = hole_table_tags(self.session, generic)
        for planned in page['plan'].views:
            if planned.derived:
                records.extend(derived_labels(page['views'][planned.role], planned))
        if any(wizard_notes.values()):
            raise ApiError('Oluşturulan delik notu çizimde bulunamadı.')
        if len([r for r in records if r['kind'] == 'hole_table']) < len(page.get('hole_tables', ())):
            raise ApiError('Oluşturulan delik tablosu çizimde bulunamadı veya tekrarlı.')
        return records

    def import_dimensions(self, name):
        if not call(self.drawing, 'ActivateSheet', name):
            raise ApiError('Ölçü aktarımı için pafta etkinleştirilemedi: '+name)
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

    def flat_dimensions(self, name):
        """Overall size and bend-line positions on a flat pattern page (geometry reference dimensions).

        Recorded on SolidWorks 2025 SP5: AutoDimension on a flat pattern view returns 1
        (swAutodimStatusBadOptionValue) while it DOES create the overall length/width and
        the bend-line positions; success is therefore judged by the dimensions read back.
        """
        view = self.pages[name]['views']['flat']
        try:
            self.flat_baseline_dimensions(view)
        except Exception as error:      # an unusual outline: fall back to SolidWorks' own scheme
            self.result.warn('flat_dimensions', f'Açınım ölçüleri taban kenardan çıkarılamadı ({error}); '
                             'SolidWorks otomatik ölçülendirmesi kullanıldı.', name)
            c = self.session.c
            self.select_view(view)
            call(self.drawing, 'AutoDimension', c('swAutodimEntitiesAll'), c('swAutodimSchemeBaseline'),
                 c('swAutodimHorizontalPlacementAbove'), c('swAutodimSchemeBaseline'), c('swAutodimVerticalPlacementRight'))
        call(self.model, 'ClearSelection2', True)
        self.rebuild()
        count = len(self.dimensions(name, roles=('flat',)))
        self.result.measurements.setdefault('flat_dimensions', {})[name] = count
        if not count:
            self.result.warn('flat_dimensions', 'Açınım görünüşüne ölçü eklenemedi; toplam ölçüleri ve büküm '
                             'konumlarını SolidWorks’te elle ekleyin.', name)
            return
        self.remove_duplicate_flat_dimensions(name)
        # Refit with the dimension texts' real boxes. (Recorded: the general pages' align/place
        # step pushed a bend-position text off its extension lines on a flat view.)
        self.fit(name, include_dimensions=True)

    def flat_baseline_dimensions(self, view):
        """Overall length / width and every bend line from one datum edge (recorded on SolidWorks 2025 SP5).

        Edges come from IView.GetVisibleEntities2 and are mapped to the sheet with
        ModelToViewTransform. A bend line is selected by its sheet position as EXTSKETCHSEGMENT
        (IView.SelectEntity returns False for it, and ISketchSegment.Select4 selects nothing usable).
        """
        c = self.session.c
        transform = tuple(float(v) for v in values(get(get(view, 'ModelToViewTransform'), 'ArrayData')))
        r, t, s = transform[0:9], transform[9:12], transform[12]

        def sheet(p):
            return ((p[0]*r[0]+p[1]*r[3]+p[2]*r[6])*s+t[0], (p[0]*r[1]+p[1]*r[4]+p[2]*r[7])*s+t[1])
        components = values(call(view, 'GetVisibleComponents'))
        if not components:
            raise ApiError('görünür gövde bileşeni yok')
        edges = []
        for edge in values(call(view, 'GetVisibleEntities2', components[0], c('swViewEntityType_Edge'))):
            params = values(call(edge, 'GetCurveParams2'))
            if len(params) >= 6:
                edges.append((edge, sheet(params[0:3]), sheet(params[3:6])))
        horizontal = [e for e in edges if abs(e[1][1]-e[2][1]) < 1e-6 and abs(e[1][0]-e[2][0]) > 1e-6]
        vertical = [e for e in edges if abs(e[1][0]-e[2][0]) < 1e-6 and abs(e[1][1]-e[2][1]) > 1e-6]
        if len(horizontal) < 2 or len(vertical) < 2:
            raise ApiError('dikdörtgen olmayan açınım dış hattı')
        bottom, top = min(horizontal, key=lambda e: e[1][1]), max(horizontal, key=lambda e: e[1][1])
        left, right = min(vertical, key=lambda e: e[1][0]), max(vertical, key=lambda e: e[1][0])
        x0, y0, x1, y1 = (float(v) for v in values(call(view, 'GetOutline')))
        gap = to_m(9.)
        call(self.drawing, 'ActivateView', str(call(view, 'GetName2')))
        extension = get(self.model, 'Extension')

        def between(a, b, x, y):
            call(self.model, 'ClearSelection2', True)
            if not (call(view, 'SelectEntity', a, False) and call(view, 'SelectEntity', b, True)):
                raise ApiError('açınım kenarı seçilemedi')
            return call(self.model, 'AddDimension2', x, y, 0.)
        right_slot, top_slot = [x1+gap], [y1+gap]
        # Bend positions on the inner rows, overall dimensions outermost (drafting convention).
        for bend in values(call(view, 'GetBendLines')):
            start, end = call(bend, 'GetStartPoint2'), call(bend, 'GetEndPoint2')
            ends = [sheet((float(get(p, 'X')), float(get(p, 'Y')), float(get(p, 'Z')))) for p in (start, end)]
            mx, my = (ends[0][0]+ends[1][0])/2, (ends[0][1]+ends[1][1])/2
            placed = None
            for datum, x, y, slot in ((bottom[0], right_slot[0], my, right_slot), (left[0], mx, top_slot[0], top_slot)):
                call(self.model, 'ClearSelection2', True)
                if not call(extension, 'SelectByID2', '', 'EXTSKETCHSEGMENT', mx, my, 0., False, 0, null_dispatch(), 0):
                    raise ApiError('büküm çizgisi seçilemedi')
                if not call(view, 'SelectEntity', datum, True):
                    continue
                display = call(self.model, 'AddDimension2', x, y, 0.)
                dimension = call(display, 'GetDimension2', 0) if display is not None else None
                value = float(get(dimension, 'Value')) if dimension is not None else 0.
                if value > .01 and get(display, 'Type2') != self.session.constants.get('swAngularDimension', -1):
                    placed = display; slot[0] += gap
                    break
                if display is not None:       # perpendicular datum: not a bend position, remove it
                    call(self.model, 'ClearSelection2', True)
                    call(call(display, 'GetAnnotation'), 'Select3', False, null_dispatch())
                    call(self.model, 'EditDelete')
            if placed is None:
                raise ApiError('büküm konumu ölçülemedi')
        between(bottom[0], top[0], right_slot[0], (y0+y1)/2)       # overall length
        between(left[0], right[0], (x0+x1)/2, top_slot[0])          # overall width
        call(self.model, 'ClearSelection2', True)

    def remove_duplicate_flat_dimensions(self, name):
        """AutoDimension adds e.g. the flat width both as a sketch and as a reference dimension (recorded);
        keep one per value, orientation and SPAN, preferring the reference dimension. Two equal flanges
        (a U profile: 30 / 60 / 30) are different spans along the same axis and are both kept."""
        records = self.dimensions(name, roles=('flat',))
        kept, extra = {}, []
        for record in sorted(records, key=lambda r: not r['reference']):
            if record['value'] is None or record['box'] is None:
                continue
            box = record['box']
            horizontal = box.width >= box.height
            along = box.x + box.width/2 if horizontal else box.y + box.height/2   # centre along the measured axis
            key = round(record['value'], 2), horizontal, round(along/3)
            (extra if key in kept else kept.setdefault(key, [])).append(record)
        if not extra:
            return
        extension = get(self.model, 'Extension')
        call(self.model, 'ClearSelection2', True)
        for index, record in enumerate(extra):
            if not call(extension, 'SelectByID2', record['name'], 'DIMENSION', 0., 0., 0., bool(index), 0, null_dispatch(), 0):
                call(self.model, 'ClearSelection2', True)
                return
        call(self.model, 'EditDelete')
        call(self.model, 'ClearSelection2', True)
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
        self.place_annotations(name, report=False)

    def place_annotations(self, name, *, report=True):
        if not self.options.arrange_dimensions:
            return
        records = self.dimensions(name)
        outlines = {v['role']: v['outline'] for v in self.actual_views(name)}
        extras = self.annotation_obstacles(name)
        moving = [*records, *(record for record in extras if 'key' in record)]
        fixed = [record for record in extras if 'key' not in record]
        linear = {}
        for record in records:
            box, kind = record['box'], record['kind']
            if record['annotation_kind'] or box is None or kind not in ('horizontal', 'vertical', 'linear'):
                continue
            key = record['key']
            placement = linear_placement(self.annotations[key], kind, box, record['value'])
            if placement is not None:
                linear[key] = placement
        moves, unresolved = place_texts([(r['key'], r['owner'], r['box']) for r in moving],
            outlines, self.pages[name]['plan'].usable, linear=linear,
            obstacle_boxes=[record['box'] for record in fixed if record['box'] is not None],
            obstacle_leaders=[line for record in fixed for line in record.get('leaders', ())])
        if not moves and not unresolved:
            return
        for record in moving:
            if record['key'] not in moves:
                continue
            dx, dy = moves[record['key']]
            pos = record['position']
            moved = len(pos) >= 3 and call(self.annotations[record['key']], 'SetPosition2',
                                            pos[0]+to_m(dx), pos[1]+to_m(dy), pos[2])
            if not moved and report:
                self.result.warn('dimension_move', 'Anotasyon konumu düzenlenemedi: '+record['name'], name)
        if unresolved and report:
            self.result.warn('dimension_layout', f'{len(unresolved)} anotasyon metni için boş konum bulunamadı veya sınırlar okunamadı.',
                             name)
        if moves:
            self.rebuild()

    def fit(self, name, *, include_dimensions=False):
        """Refit measured native outlines, preserving projected view links."""
        page, options = self.pages[name], self.options
        scales = ((options.manual_scale,) if options.manual_scale is not None else
                  tuple(sorted(set(options.scales), reverse=True)))
        for scale in scales:
            checkpoint(self.stop)
            # SetScale scales annotation positions, but keeps paper-space text
            # size fixed. Scaling a geometry+text union can reject a valid scale.
            self.set_scale(name, scale)
            for attempt in range(3):
                actual = self.actual_views(name)
                records = self.dimensions(name) if include_dimensions else []
                measured = {v['role']: union([v['outline']]+[r['box'] for r in records
                            if r['owner'] == v['role'] and r['box'] is not None]) for v in actual}
                planned = arrange(page['plan'].views, scale, page['plan'].usable, options,
                                  measured=measured, positions={v['role']: v['position'] for v in actual})
                if planned is None:
                    break
                for target in planned:  # Absolute native origins; parent precedes its children.
                    view = page['views'][target.role]
                    put(view, 'Position', variant(0x2005, tuple(to_m(v) for v in target.center)))
                self.rebuild()
                actual = self.actual_views(name)
                records = self.dimensions(name) if include_dimensions else []
                bounds = [union([v['outline']]+[r['box'] for r in records
                          if r['owner'] == v['role'] and r['box'] is not None]).grow(options.annotation_padding_mm)
                          for v in actual]
                if all(page['plan'].usable.contains(b) for b in bounds) and not any(
                        a.overlaps(b) for i, a in enumerate(bounds) for b in bounds[i+1:]):
                    page['plan'].views = planned
                    return
        if include_dimensions:
            self.fit(name)
            width, height = page['plan'].width_mm, page['plan'].height_mm
            bounds = Box(0., 0., width, height)
            if all(record['box'] is None or bounds.contains(record['box']) for record in self.dimensions(name)):
                self.result.warn('dimension_layout', 'Görünüşler yerleşti. Ölçü boşlukları için kayıt sonrası bulguları kontrol edin.',
                                 name)
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
        if not call(self.drawing, 'ActivateSheet', name):
            raise ApiError('Merkez işaretleri için pafta etkinleştirilemedi: '+name)
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
            marks = self.center_mark_count(view)
            if not marks:   # the document option may already have inserted them with the view
                self.select_view(view)
                call(view, 'AutoInsertCenterMarks2', mask, 0, True, True, True, 0., 0., False, True, 0.)
                marks = self.center_mark_count(view)
            count += marks
        self.result.measurements.setdefault('center_marks', {})[name] = count
        call(self.model, 'ClearSelection2', True)

    def center_mark_count(self, view):
        """Center marks are view annotations of type swCenterMarkSym.

        Recorded on SolidWorks 2025 SP5: a front view of a plate with 5 holes already had
        5 such annotations right after creation (swDetailingAutoInsertCenterMarksForHoles);
        AutoInsertCenterMarks2 returned True and added 5 duplicates, and GetCenterMarkCount2
        returned 0 both before and after. So the annotations are counted instead.
        """
        kind, count = self.session.c('swCenterMarkSym'), 0
        annotation = call(view, 'GetFirstAnnotation3')
        for _ in range(20000):
            if annotation is None:
                return count
            count += call(annotation, 'GetType') == kind
            annotation = call(annotation, 'GetNext3')
        raise ApiError('Görünüş anotasyon listesi döngüsel veya güvenli sınırdan büyük.')

    def validate(self):
        findings, snapshots = [], []
        for name, page in self.pages.items():
            if page.get('flat_body') is not None:
                from .sheetmetal import verify_metadata
                source = get(page['views']['flat'], 'ReferencedDocument')
                if source is not None:
                    source = as_interface(source, MODEL_IID)
                    if identity(call(source, 'GetPathName'))[0] != self.info.source.key[0]:
                        raise ApiError('Açınımın kaynak belge kimliği eşleşmedi; farklı belgeye işlem uygulanmadı.')
                    verify_metadata(self.session, source, page['flat_body'], self.info)
                source = None
            state = self.sheet_state(name)
            state.update(expected=[v.role for v in page['plan'].views],
                         usable=page.get('validation_area', page['plan'].usable))
            actual = self.actual_views(name)
            records = self.dimensions(name)
            extras = self.annotation_obstacles(name)
            findings.extend(validate_views(state, actual, self.info.source,
                             flat_configurations=self.info.flat_configurations, projection=self.options.projection))
            bounds = Box(0., 0., state['width_mm'], state['height_mm'])
            findings.extend(validate_annotations(records, {v['role']: v['outline'] for v in actual},
                                                  page['plan'].usable, name, bounds=bounds))
            findings.extend(validate_annotation_obstacles(records, extras, {v['role']: v['outline'] for v in actual},
                                                          page['plan'].usable, name))
            for record in [*records, *extras]:
                if record.get('leader_bounds_unknown'):
                    findings.append(self._warning('annotation_leader_bounds', 'Lider çizgisi okunamadı.',
                                                  name, record['name']))
            for record in extras:
                if record.get('estimated'):
                    findings.append(self._warning('annotation_text_estimate', 'Anotasyon metin genişliği tahmin içeriyor.',
                                                  name, record['name']))
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
            notes, note_findings = self.notes(name)
            findings.extend(note_findings)
            snapshots.append(dict(**state, views=actual, dimensions=records, notes=notes, annotations=extras))
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
                note_handles = {}
                if state.get('notes'):
                    for note in values(call(view, 'GetNotes')):
                        note_handles[str(call(note, 'GetName'))] = note
                handles, tables = {}, []

                def bom_tables(owner):
                    for table in values(call(owner, 'GetTableAnnotations')):
                        generic = self.session.named_interface(table, 'ITableAnnotation')
                        if int(get(generic, 'Type')) == self.session.c('swTableAnnotation_BillOfMaterials'):
                            tables.append(table_box(generic))
                            columns = quantity_columns(generic, self.session)
                            if len(columns) == 1:
                                for row in self.bom_rows:
                                    number, text = displayed_quantity(generic, row['row_index'], columns[0])
                                    if number != row['quantity']:
                                        raise ApiError('Kayıt sonrası BOM adetleri değişmiş.')
                # Recorded on SolidWorks 2025 SP5: a BOM inserted on a model view is listed under
                # the SHEET entry after the drawing is saved and reopened, not under that view.
                if view is not None:
                    bom_tables(view)
                view = call(view, 'GetNextView') if view is not None else None
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
                    bom_tables(view)
                    view = call(view, 'GetNextView')
                if set(handles) != set(state['expected']):
                    raise ApiError('SLDDRW yeniden açıldığında görünüşler eksik.')
                original = self.pages[name]
                if len(tables) != len(original['tables']):
                    raise ApiError('BOM tablosu kaydedilen teknik resimde bulunamadı veya tekrarlı.')
                check.pages[name] = dict(plan=original['plan'], views=handles, tables=tables,
                    format=original['format'], validation_area=state['usable'], flat_body=original.get('flat_body'),
                    notes=[], wizard_notes=original.get('wizard_notes', ()), hole_tables=original.get('hole_tables', ()))
                for target in state.get('notes', ()):
                    if target['name'] not in note_handles:
                        raise ApiError('Gövde kimliği / kalınlık notu kaydedilen teknik resimde bulunamadı.')
                    check.pages[name]['notes'].append(dict(target, handle=note_handles[target['name']]))
                actual_state = check.sheet_state(name)
                for key in ('width_mm', 'height_mm', 'scale'):
                    if not math.isclose(actual_state[key], state[key], rel_tol=1e-7, abs_tol=.001):
                        raise ApiError('Kaydedilen pafta boyutu / ölçeği değişmiş.')
            findings, reread = check.validate()
            for before, after in zip(snapshots, reread):
                if len(before['dimensions']) != len(after['dimensions']):
                    raise ApiError('Kayıt sonrası model ölçüleri korunmamış.')
                def holes(state):
                    selected = [(r['kind'], r.get('text', ''), r.get('rows', 0), tuple(r.get('tags', ())))
                                for r in state['annotations']
                                if r['kind'] in ('hole_table', 'wizard_note')]
                    selected.extend(('callout', str(r['value']), 0, ()) for r in state['dimensions']
                                    if r['annotation_kind'] == 'hole_callout')
                    return sorted(selected)
                if holes(before) != holes(after):
                    raise ApiError('Kayıt sonrası delik bilgisi / tablosu korunmamış.')
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
            # SolidWorks 2025 SP5 returns False for swExportData_ExportAllSheets with any
            # Sheets argument (empty, null, names); naming every sheet is accepted.
            names = tuple(str(v) for v in values(call(self.drawing, 'GetSheetNames')))
            if not names or not call(export, 'SetSheets', c('swExportData_ExportSpecifiedSheets'),
                                     variant(0x2008, names)):
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
            page.get('notes', []).clear()
        self.drawing = None
        if self.model is not None:
            model, self.model = self.model, None
            self.session.close_created(model)
