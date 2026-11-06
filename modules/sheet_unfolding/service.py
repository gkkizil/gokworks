"""Adapter between the Qt page and ``core.unfolding.UnfoldService`` (contract v1).

The engine owns geometry, validation, development, exports and projects. This
module only converts: page dicts → ``UnfoldRequest`` and engine results →
display dicts. The engine objects travel with the converted data, so exports,
projects and nesting always use the exact result that is on screen.

The presentation table holds only what the engine schema does not carry:
categories, workshop names for search, thumbnails, variant titles and where an
input dimension (``dimension_id``) is written on the sketch. It defines no
parameters, limits or defaults; those always come from ``get_schema``.
"""

from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions
from core.unfolding.models import ProjectItem, UnfoldProject, to_data
from core.unfolding.shapes.common import UnfoldCancelled

UNIT_KINDS = {'length': 'length', 'deg': 'angle', 'count': 'count', 'option': 'count'}
VARIANT_TITLES = {
    'straight': 'Düz uçlu', 'bevel': 'Üstü açılı kesik', 'full': 'Tam koni', 'frustum': 'Kesik koni (redüksiyon)',
    'centered': 'Merkezli', 'centered_faceted': 'Merkezli · fasetli', 'constant_diameter': 'Sabit çaplı',
}
BASIC = 'Temel şekiller · krokili'     # the first five engine families, with dimensioned sketches
# shape_id: (category, workshop names, thumbnail 0–1, {variant: (sketch lines, {dimension_id: (start, end, symbol)})})
PRESENTATION = {
    'cylinder': (BASIC, ('silindir', 'boru', 'manşon', 'yuvarlak kanal', 'gönye kesik'),
                 [[[.2, 0], [.8, 0], [.8, 1], [.2, 1], [.2, 0]]],
                 {'straight': ([[[-150, 0], [150, 0], [150, 200], [-150, 200], [-150, 0]]],
                               {'diameter': ([-150, -30], [150, -30], 'D'), 'height': ([185, 0], [185, 200], 'H')}),
                  'bevel': ([[[-150, 0], [150, 0], [150, 260], [-150, 140], [-150, 0]]],
                            {'diameter': ([-150, -30], [150, -30], 'D'), 'height': ([185, 0], [185, 200], 'H'),
                             'cut_angle_deg': ([-60, 240], [40, 240], 'β')})}),
    'cone': (BASIC, ('koni', 'redüksiyon', 'konik', 'konsantrik', 'huni'),
             [[[0, 0], [1, 0], [.72, 1], [.28, 1], [0, 0]]],
             {'full': ([[[-150, 0], [150, 0], [0, 220], [-150, 0]]],
                       {'bottom_diameter': ([-150, -30], [150, -30], 'D'), 'height': ([185, 0], [185, 220], 'H')}),
              'frustum': ([[[-150, 0], [150, 0], [75, 200], [-75, 200], [-150, 0]]],
                          {'bottom_diameter': ([-150, -30], [150, -30], 'D'), 'top_diameter': ([-75, 230], [75, 230], 'd'),
                           'height': ([185, 0], [185, 200], 'H')})}),
    'rectangular_reducer': (BASIC, ('dikdörtgen redüksiyon', 'kanal redüksiyonu', 'huni', 'bunker'),
                            [[[0, 0], [1, 0], [.75, 1], [.25, 1], [0, 0]]],
                            {'centered': ([[[-200, 0], [200, 0], [100, 300], [-100, 300], [-200, 0]]],
                                          {'bottom_width': ([-200, -30], [200, -30], 'A'), 'top_width': ([-100, 330], [100, 330], 'a'),
                                           'height': ([235, 0], [235, 300], 'H')})}),
    'rect_to_round': (BASIC, ('kare yuvarlak', 'kurtağzı', 'dikdörtgen yuvarlak', 'geçiş'),
                      [[[0, 0], [1, 0], [.8, 1], [.2, 1], [0, 0]], [[.2, 1], [.5, .88], [.8, 1]]],
                      {'centered_faceted': ([[[-200, 0], [200, 0], [125, 300], [-125, 300], [-200, 0]]],
                                            {'width': ([-200, -30], [200, -30], 'A'), 'diameter': ([-125, 330], [125, 330], 'D'),
                                             'height': ([235, 0], [235, 300], 'H')})}),
    'segmented_elbow': (BASIC, ('dirsek', 'segmentli dirsek', 'dilimli dirsek', 'gönye dirsek'),
                        [[[0, 0], [0, .45], [.2, .8], [.55, 1], [1, 1]]],
                        {'constant_diameter': ([[[0, 0], [0, 120], [60, 230], [170, 290], [300, 300]]],
                                               {'diameter': ([-60, -25], [60, -25], 'D'),
                                                'center_radius': ([0, 0], [300, 0], 'R'),
                                                'total_angle_deg': ([90, 110], [150, 160], 'α')})}),
}
# Families the engine does not offer yet: shown in their category, never selectable.
PLANNED = (
    ('branch_tee', 'Branşman / T parça', 'Branşmanlar', ('branşman', 't parça', 'kurtağzı', 'saplama')),
    ('y_pants', 'Y / pantolon', 'Pantolon ve Y parça', ('pantolon', 'y parça', 'çatal')),
    ('oblique_cone', 'Eğik koni (eksantrik)', 'Koni ve redüksiyon', ('eksantrik redüksiyon', 'eğik koni')),
    ('dished_head', 'Bombe / kapak', 'Bombeler', ('bombe', 'torisferik', 'kapak')),
    ('helix', 'Helezon', 'Helezonlar', ('helezon', 'konveyör', 'vida')),
)


# Source catalogue (engine 1.1.0): categories, labels and parameters come from the engine; only a
# category thumbnail and workshop synonyms for the search box are added here.
CATEGORY_PRESENTATION = {
    'Silindirler ve boru kesimleri': ([[[.2, 0], [.8, 0], [.8, 1], [.2, .75], [.2, 0]]], ('boru', 'manşon', 'gönye kesik', 'oval')),
    'Koniler ve redüksiyonlar': ([[[0, 0], [1, 0], [.72, 1], [.28, 1], [0, 0]]], ('redüksiyon', 'konik', 'eksantrik', 'huni')),
    'Geçiş parçaları': ([[[0, 0], [1, 0], [.8, 1], [.2, 1], [0, 0]], [[.2, 1], [.5, .88], [.8, 1]]],
                        ('kurtağzı', 'kare yuvarlak', 'geçiş', 'redüksiyon')),
    'Segmentli dirsekler': ([[[0, 0], [0, .45], [.2, .8], [.55, 1], [1, 1]], [[.3, 0], [.3, .38], [.45, .62], [.65, .72], [1, .72]]],
                            ('dirsek', 'dilimli dirsek', 'segment')),
    'Dirsekler': ([[[0, 0], [0, .6], [.4, 1], [1, 1]], [[.3, 0], [.3, .5], [.52, .7], [1, .7]]], ('gönye dirsek', 'dirsek', 'açılı')),
    'Branşmanlar ve T parçalar': ([[[0, 0], [1, 0], [1, .4], [0, .4], [0, 0]], [[.35, .4], [.35, 1], [.65, 1], [.65, .4]]],
                                  ('branşman', 't parça', 'saplama', 'kurtağzı', 'delik')),
    'Pantolonlar ve Y parçalar': ([[[.4, 0], [.6, 0], [.6, .4], [1, .88], [.85, 1], [.5, .58], [.15, 1], [0, .88], [.4, .4], [.4, 0]]],
                                  ('pantolon', 'y parça', 'çatal')),
    'Huniler, bunkerler ve piramitler': ([[[0, 1], [1, 1], [.65, .25], [.35, .25], [0, 1]], [[.35, .25], [.35, 0], [.65, 0], [.65, .25]]],
                                         ('huni', 'bunker', 'piramit', 'prizma')),
    'Bombeler ve kapaklar': ([[[0, .2], [.05, .5], [.2, .75], [.5, .85], [.8, .75], [.95, .5], [1, .2], [0, .2]]],
                             ('bombe', 'kapak', 'torisferik', 'eliptik', 'yarım küre')),
    'Helezonlar': ([[[0, .1], [.25, .35], [.5, .1], [.75, .35], [1, .1]], [[0, .55], [.25, .8], [.5, .55], [.75, .8], [1, .55]],
                    [[.5, 0], [.5, 1]]], ('helezon', 'konveyör', 'vida', 'spiral')),
    'Dikdörtgen kanallar': ([[[0, 0], [.7, 0], [.7, .6], [0, .6], [0, 0]], [[0, .6], [.3, .9], [1, .9], [.7, .6]], [[1, .9], [1, .3], [.7, 0]]],
                            ('kanal', 'hava kanalı', 'dikdörtgen', 'flanş')),
}
STATUS_TITLES = {'validated_example_with_restrictions': 'Örneklerle doğrulandı · sınırlamalı'}
STAGE_TITLES = (('calculated', 'Hesaplanabilir'), ('normal_and_invalid_tests_passed', 'Normal ve hatalı giriş testleri geçti'),
                ('output_readback_passed', 'Çıktılar geri okunarak doğrulandı'),
                ('source_full_feature_parity', 'Kaynakla tam özellik eşdeğerliği'), ('production_approved', 'İmalat onayı'))
OUTPUT_TITLES = {'dxf': 'DXF', 'pdf': 'PDF', 'step_surface': 'STEP (yüzey)', 'step_solid': 'STEP (katı)'}
RESTRICTION_TITLES = {
    'GOKWORKS geometry is not manufacturing/process approval.': 'Geometri imalat/proses onayı değildir.',
    'Signed UP/DOWN fold direction is not evaluated for source fitting developments.':
        'Büküm yönü (yukarı/aşağı) değerlendirilmez; büküm çizgileri nötr katmandadır.',
    'Curve residual is measured sampling error, not certified manufacturing tolerance.':
        'Eğri sapması ölçülen örnekleme hatasıdır; sertifikalı imalat toleransı değildir.',
    'STEP is an OCCT surface B-Rep, not a solid or editable SolidWorks feature tree.':
        'STEP bir yüzey modelidir; katı veya düzenlenebilir SolidWorks özellik ağacı değildir.',
    'Verified trimmed B-Rep unavailable; STEP disabled for this example.': 'Doğrulanmış yüzey modeli yok; bu modelde STEP kapalı.',
    'Only geometric mid-surface inputs; unverified inner/outer normal offsets are rejected.':
        'Yalnız orta yüzey ölçüsü; doğrulanmamış iç/dış ölçü seçimleri kapalıdır.',
    'piecewise_planar_ruled_surface; smooth forming strain is not solved':
        'Fasetli (parça parça düzlem) yüzey; düzgün şekillendirme gerinimi hesaplanmaz.',
    'two mirrored clipped ruled surfaces; faceted material, smooth forming strain not solved':
        'Ayna simetrik iki fasetli yüzey; düzgün şekillendirme gerinimi hesaplanmaz.',
    'faceted_gore; forming/springback/press forces not evaluated':
        'Dilimli (gore) yaklaşık açınım; şekillendirme, geri esneme ve pres kuvveti değerlendirilmez.',
    'triangulated_helicoid; forming strain between facets not evaluated':
        'Üçgenlenmiş helezon; fasetler arası şekillendirme gerinimi değerlendirilmez.',
    'outer_edge_length_matched_annular_forming_blank; not an isometric development':
        'Dış kenar boyuna göre halka şeklinde şekillendirme taslağı; gerçek (izometrik) açınım değildir.',
    'heel=true unsupported: source flag has no numerical heel definition; request rejected.':
        'Topuk seçeneği desteklenmiyor (sayısal tanımı yok).',
    'Outside-to-axis H/X conversion subtracts D; source dimension drawing equivalence not confirmed.':
        'Dış ölçüden eksene H/X dönüşümünde D düşülür; kaynak ölçü çizimiyle eşdeğerliği doğrulanmadı.',
    'Torus intersection validated; source E/Z/X/A dimension interpretation not confirmed. See SOURCE_MODELS.md.':
        'Torus kesişimi doğrulandı; kaynaktaki E/Z/X/A ölçü yorumu doğrulanmadı.',
}
LAP_TITLES = {'lap_top': 'Üst kenar payı', 'lap_bottom': 'Alt kenar payı', 'lap_left': 'Sol kenar payı',
              'lap_right': 'Sağ kenar payı', 'strip_lap': 'Şerit payı'}
# Ducts: lap_top is the flange on both long wall edges, lap_left the lap at both wall ends (others rejected).
DUCT_LAP_TITLES = {'top': ('lap_top', 'Duvar flanşı (iki uzun kenar)',
                           'Her duvarın iki uzun kenarında, üst/alt plakaların üzerine katlanan flanş. 0 = yok.'),
                   'left': ('lap_left', 'Duvar uçlarında bindirme',
                            'Her duvarın iki ucunda, tam yükseklikte; komşu duvarla veya kanal ağzıyla birleşir. 0 = yok.')}


FIELD_ALIASES = {'thickness': 'thickness', 'joint_options.overlap': 'joint', 'seam_options.start_angle_deg': 'seam_angle',
                 'split_options.count': 'split_count', 'material.unit_price': 'price'}


def field_id(engine_id):
    """Engine field path → page field id ('parameters.diameter' → 'diameter')."""
    if engine_id.startswith('parameters.'):
        return engine_id.split('.', 1)[1]
    if engine_id.startswith('model_options.'):
        return 'opt.' + engine_id.split('.', 1)[1]
    return FIELD_ALIASES.get(engine_id, engine_id)


def _issue(issue, severity):
    return dict(severity=severity, code=issue.code, message=issue.message,
                field_ids=[field_id(f) for f in issue.field_ids], part_id=issue.part_id)


def curve_entity(curve, layer):
    kind = curve.kind
    if kind == 'line':
        return dict(layer=layer, type='line', start=list(curve.start), end=list(curve.end), id=curve.id)
    if kind == 'arc':
        start, sweep = curve.start_angle_deg, curve.sweep_deg
        if sweep < 0:                                   # contract: negative sweep is clockwise
            start, sweep = start + sweep, -sweep
        return dict(layer=layer, type='arc', center=list(curve.center), radius=curve.radius,
                    start_deg=start, end_deg=start + sweep, sweep_deg=sweep)
    if kind == 'circle':
        return dict(layer=layer, type='circle', center=list(curve.center), radius=curve.radius)
    return dict(layer=layer, type='polyline', points=[list(p) for p in curve.points], closed=curve.closed)


def part_view(part):
    """Engine UnfoldPart → display dict (entities by layer, mesh triangles, metrics, views)."""
    entities = [curve_entity(c, 'cut') for c in part.geometry_2d.outer]
    for hole in part.geometry_2d.holes:
        entities += [curve_entity(c, 'hole') for c in hole]
    entities += [curve_entity(c, 'bend') for c in part.bending_lines]
    entities += [curve_entity(c, 'construction') for c in part.construction_lines]
    entities += [curve_entity(c, 'seam') for c in part.seams]
    for a in part.dimension_annotations:
        entities.append(dict(layer='dimension', type='dimension', start=list(a.start), end=list(a.end),
                             text=f'{a.value:.2f}'.replace('.', ','), parameter_id=a.parameter_id))
    vertices = part.mesh_3d.vertices
    triangles = [c for tri in part.mesh_3d.triangles for index in tri for c in vertices[index]]
    m = part.metrics
    metrics = dict(net_area_mm2=m.net_area_mm2, gross_area_mm2=m.cutting_area_mm2, rectangle_area_mm2=m.rectangle_area_mm2,
                   bbox_mm=[m.bounds_mm[2] - m.bounds_mm[0], m.bounds_mm[3] - m.bounds_mm[1]],
                   cut_length_mm=m.cutting_length_mm, mass_kg=m.mass_kg, cost=m.material_cost) if m else {}
    views = [dict(id=v.id, label=v.label, entities=[curve_entity(c, 'cut') for c in v.geometry]) for v in part.drawing_views]
    return dict(part_id=part.id, name=part.code, quantity=part.quantity, geometry_2d=dict(entities=entities),
                mesh_3d=dict(triangles_mm=triangles), metrics=metrics, drawing_views=views,
                true_lengths=[dict(id=t.id, length_mm=t.length_mm) for t in part.true_lengths])


class EngineService:
    """The real engine behind the page's dict-shaped surface."""
    is_fixture = False
    notice = ''

    def __init__(self, engine=None):
        self.engine = engine or UnfoldService()

    # ---- catalogue / schema ----------------------------------------------------------
    def list_shapes(self):
        shapes = []
        for summary in self.engine.list_shapes():
            category, keywords, preview, _ = PRESENTATION.get(summary.shape_id, ('Diğer', (), [], {}))
            if summary.category:
                category = summary.category
                preview, synonyms = CATEGORY_PRESENTATION.get(category, ([], ()))
                keywords = (*summary.variant_labels.values(), *synonyms)
            shapes.append(dict(shape_id=summary.shape_id, title=summary.label, category=category, keywords=list(keywords),
                               status='implemented', preview=preview, method=summary.method,
                               source_ids=list(summary.source_ids),
                               variants=[dict(variant_id=v, title=summary.variant_labels.get(v,VARIANT_TITLES.get(v, v)), status='implemented')
                                         for v in summary.variants]))
        for shape_id, title, category, keywords in (() if any(s['source_ids'] for s in shapes) else PLANNED):
            shapes.append(dict(shape_id=shape_id, title=title, category=category, keywords=list(keywords),
                               status='planned', preview=[], variants=[], method=None))
        return shapes

    def get_schema(self, shape_id, variant_id):
        schema = self.engine.get_schema(shape_id, variant_id)
        lines, anchors = PRESENTATION.get(shape_id, ('', (), [], {}))[3].get(variant_id, ([], {}))
        parameters = [dict(id=f.id, label=f.label, symbol=f.dimension_id if schema.source_id else '', kind=UNIT_KINDS.get(f.unit, 'length'), default=f.default,
                           min=f.minimum, max=f.maximum, required=f.required, integer=f.type == 'integer',
                           choices=list(f.choices), description=f.description, dimension_id=f.dimension_id, group='common')
                      for f in schema.fields]
        annotations = []
        for p in parameters:
            if p['dimension_id'] in anchors:
                start, end, symbol = anchors[p['dimension_id']]
                annotations.append(dict(parameter_id=p['id'], start=start, end=end, text=symbol))
        return dict(shape_id=shape_id, variant_id=variant_id, title=schema.label, parameters=parameters, source_id=schema.source_id,
                    source=self.source_info(schema.source_id),
                    constraints=list(schema.constraints), sketch=lines, dimension_annotations=annotations,
                    options=dict(dimension_reference=list(schema.supported_dimension_references), default_reference='mid',
                                 seam=schema.seam_supported, split=schema.split_supported, joint_kinds=list(schema.joint_kinds),
                                 model_options=to_data(schema.model_options)),
                    capabilities=dict(outputs=list(schema.output_kinds)))

    def source_info(self, source_id):
        """Catalogue record of one source model, in Turkish where the engine text is English."""
        if not source_id:
            return None
        record = next((to_data(m) for m in self.engine.list_source_models() if m['source_id'] == source_id), None)
        if record is None:
            return None
        texts = list(record.get('restrictions') or ())
        if record.get('approximation') and record['approximation'] not in texts:
            texts.insert(0, record['approximation'])
        return dict(source_id=source_id, url=record.get('source_url', ''), method=record.get('calculation_method'),
                    status=STATUS_TITLES.get(record.get('implementation_status'), record.get('implementation_status') or '—'),
                    stages=[(title, bool((record.get('stages') or {}).get(key))) for key, title in STAGE_TITLES],
                    outputs=[OUTPUT_TITLES.get(o, o) for o in record.get('validated_outputs') or ()],
                    restrictions=[RESTRICTION_TITLES.get(t, t) for t in texts],
                    has_example=bool(self.example_request(source_id)))

    def example_request(self, source_id):
        """Engine-team example that is known to calculate (page dict), or None."""
        examples = getattr(self, '_examples', None)
        if examples is None:
            import json
            from pathlib import Path
            path = Path(__file__).resolve().parents[2] / 'docs/unfolding/examples/source_models.json'
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                examples = {m['source_id']: m['request'] for m in data.get('models', ())}
            except (OSError, ValueError, KeyError, TypeError):
                examples = {}
            self._examples = examples
        request = examples.get(source_id)
        if request is None:
            return None
        try:
            return self.page_request(UnfoldRequest(**request))
        except (TypeError, ValueError):
            return None

    # ---- requests --------------------------------------------------------------------
    @staticmethod
    def engine_request(request):
        """Page dict → UnfoldRequest. Values stay in the user's input unit (contract)."""
        material = request.get('material') or {}
        joint = request.get('joint_options') or {}
        return UnfoldRequest(
            shape_id=request['shape_id'], variant_id=request['variant_id'], parameters=dict(request['parameters']),
            request_id=request['request_id'], revision=request['revision'], input_units=request['input_units'],
            thickness=request.get('thickness') or 0., dimension_reference=request['dimension_reference'],
            material=dict(name=material.get('name', ''), density_kg_m3=material.get('density_kg_m3'),
                          unit_price=material.get('unit_price'), price_unit=material.get('price_unit','kg'), currency=material.get('currency', '')),
            seam_options=dict(start_angle_deg=(request.get('seam_options') or {}).get('start_angle_deg', 0.)),
            split_options=dict(count=(request.get('split_options') or {}).get('count', 1)),
            joint_options=dict(kind=joint.get('kind', 'butt'), overlap=joint.get('overlap', 0.) or 0.),
            development_options=request.get('development_options') or {},
            model_options=request.get('model_options') or {})

    @staticmethod
    def page_request(engine_request):
        """UnfoldRequest (from a project file) → page dict, so the form is restored exactly."""
        data = to_data(engine_request)
        return dict(schema_version=data['schema_version'], request_id=data['request_id'], revision=data['revision'],
                    shape_id=data['shape_id'], variant_id=data['variant_id'], parameters=dict(data['parameters']),
                    input_units=data['input_units'], thickness=data['thickness'] or None,
                    dimension_reference=data['dimension_reference'], material=dict(data['material']),
                    seam_options=dict(data['seam_options']), split_options=dict(data['split_options']),
                    joint_options=dict(data['joint_options']), development_options=dict(data['development_options']),model_options=dict(data['model_options']))

    def validate(self, request):
        try:
            report = self.engine.validate(self.engine_request(request))
        except (ValueError, TypeError) as error:
            return dict(ok=False, issues=[dict(severity='error', code='REQUEST', message=str(error), field_ids=[])], note='')
        issues = [_issue(i, 'error') for i in report.errors] + [_issue(i, 'warning') for i in report.warnings]
        return dict(ok=report.valid, issues=issues, note='')

    def calculate(self, request, cancel_token=None):
        engine_request = self.engine_request(request)
        try:
            result = self.engine.calculate(engine_request, cancel_token=cancel_token)
        except UnfoldCancelled as error:
            raise InterruptedError('İptal edildi.') from error
        caps = dict(result.capabilities)
        exports = [k for k in ('dxf', 'pdf', 'zip') if caps.get(k)] + (['step'] if caps.get('step_surface') else [])
        status = 'error' if result.status != 'success' else 'warning' if result.warnings else 'ok'
        return dict(request_id=result.request_id, revision=result.revision, input_hash=result.input_hash,
                    engine_version=f'motor {result.engine_version}', status=status,
                    calculation_method=result.calculation_method or None,
                    parts=[part_view(p) for p in result.parts], metrics=to_data(result.metrics),
                    warnings=[_issue(i, 'warning') for i in result.warnings],
                    errors=[_issue(i, 'error') for i in result.errors],
                    capabilities=dict(exports=exports if status != 'error' else [],
                                      nesting=bool(caps.get('nesting')) and status != 'error',
                                      step_kind='surface', step_solid=bool(caps.get('step_solid'))),
                    quality_metrics=to_data(result.quality_metrics),
                    engine_result=result, engine_request=engine_request)

    # ---- outputs, projects, nesting --------------------------------------------------
    @staticmethod
    def _files(outcome):
        return dict(status=outcome.status, files=[dict(path=f.path, format=f.format, part_id=f.part_id) for f in outcome.files],
                    errors=[_issue(i, 'error') for i in outcome.errors])

    def export(self, result, export_options, cancel_token=None):
        engine_result = result['engine_result']
        options = ExportOptions(path=export_options['path'], format=export_options['format'],
                                part_ids=tuple(export_options.get('part_ids', ())), overwrite=True,
                                page_size=export_options.get('page_size', 'A4'),
                                include_pdf=export_options.get('include_pdf', True),
                                include_step=export_options.get('include_step', False),
                                expected_revision=engine_result.revision, expected_input_hash=engine_result.input_hash,
                                project_name=export_options.get('project_name', ''))
        try:
            return self._files(self.engine.export(engine_result, options, cancel_token=cancel_token))
        except UnfoldCancelled as error:
            raise InterruptedError('İptal edildi.') from error

    def project(self, parts, name):
        return UnfoldProject(items=tuple(ProjectItem(p['code'], self.engine_request(p['request']), int(p.get('quantity', 1)))
                                         for p in parts), name=name or 'Sac açınımı')

    def save_project(self, project, path):
        return self.engine.save_project(project, path, overwrite=True)

    def load_project(self, path):
        return self.engine.load_project(path)

    def export_project(self, project, path, cancel_token=None):
        options = ExportOptions(path=path, format='zip', overwrite=True, project_name=project.name)
        try:
            return self._files(self.engine.export_project(project, options, cancel_token=cancel_token))
        except UnfoldCancelled as error:
            raise InterruptedError('İptal edildi.') from error

    @staticmethod
    def nesting_parts(result):
        from core.unfolding.nesting import to_nesting_parts
        return to_nesting_parts(result['engine_result'])


def resolve_service():
    return EngineService()
