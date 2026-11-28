"""Gerçek SolidWorks kabul fixture'larını API ile sıfırdan üretir (kullanıcı dosyası kullanmaz).

    python tools/automatic_drawing/build_live_fixtures.py HEDEF_KLASOR \
        [shaft plate sheet multibody_sheet assembly suppressed_assembly missing_reference
         company_templates wizard_plate bored_shaft small_radius_detail]

Her fixture kendi alt klasörüne kaydedilir (LIVE_ACCEPTANCE.md: klasör SHA256 ile izlenir).
Var olan bir fixture dosyasının üzerine yazılmaz. Montajlar HEDEF_KLASOR (veya üst klasörü)
altındaki 01-mil / 02-delikli-plaka parçalarının kopyalarını kullanır; önce shaft ve plate üretin.
Açınım konfigürasyonlarını SolidWorks kendisi oluşturur (kullanıcının bir kez açınım görünüşü
eklemesi gibi). Ölçü eklerken 'ölçü değerini girişte sor' tercihi geçici kapatılır ve geri yüklenir.
Aynı ada sahip fixture'ları farklı klasörlerde tutmayın: tek açılan bir SLDDRW, SolidWorks'ün
dış referans aramasıyla başka klasördeki aynı adlı modele bağlanabilir.
"""

from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import shutil
import sys

import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.cad_converter.api import load_constants  # noqa: E402

NULL = VARIANT(pythoncom.VT_DISPATCH, None)
MM = .001


def out_int():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


class Builder:
    def __init__(self, root):
        self.root = root
        self.app = wc.dynamic.Dispatch(wc.GetActiveObject('SldWorks.Application')._oleobj_)
        self.app._FlagAsMethod('GetOpenDocumentByName')
        self.c = load_constants(self.app)
        self.created = []

    def new(self, kind):
        key = {'part': 'swDefaultTemplatePart', 'assembly': 'swDefaultTemplateAssembly'}[kind]
        template = self.app.GetUserPreferenceStringValue(self.c[key])
        model = self.app.NewDocument(template, 0, 0., 0.)
        if model is None:
            raise RuntimeError('Yeni belge oluşturulamadı: ' + template)
        self.created.append(model.GetTitle)
        return model

    @staticmethod
    def planes(model):
        """Front, Top, Right reference plane names in the UI language (first three RefPlanes)."""
        names, feature = [], model.FirstFeature
        while feature is not None and len(names) < 3:
            if feature.GetTypeName2 == 'RefPlane':
                names.append(feature.Name)
            feature = feature.GetNextFeature
        return names

    def sketch_on(self, model, plane):
        model.ClearSelection2(True)
        if not model.Extension.SelectByID2(plane, 'PLANE', 0., 0., 0., False, 0, NULL, 0):
            raise RuntimeError('Düzlem seçilemedi: ' + plane)
        self.sketches_before = self.profiles(model)
        model.SketchManager.InsertSketch(True)
        model.SketchManager.AddToDB = True

    def close_sketch(self, model):
        model.SketchManager.AddToDB = False
        model.SketchManager.InsertSketch(True)
        # FeatureByPositionReverse(0) is the FlatPattern on sheet metal parts, not the sketch.
        new = [n for n in self.profiles(model) if n not in self.sketches_before]
        model.ClearSelection2(True)
        if len(new) != 1 or not model.Extension.SelectByID2(new[0], 'SKETCH', 0., 0., 0., False, 0, NULL, 0):
            raise RuntimeError(f'Taslak seçilemedi: {new}')
        return new[0]

    @staticmethod
    def profiles(model):
        names, feature = [], model.FirstFeature
        while feature is not None:
            if feature.GetTypeName2 == 'ProfileFeature':
                names.append(feature.Name)
            feature = feature.GetNextFeature
        return names

    def dimension(self, model, segment, x, y):
        model.ClearSelection2(True)
        segment.Select4(False, NULL)
        return model.AddDimension2(x, y, 0.)

    def save(self, model, folder, name):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        if os.path.exists(path):
            raise RuntimeError('Var olan fixture üzerine yazılmaz: ' + path)
        model.ForceRebuild3(False)
        errors, warnings = out_int(), out_int()
        ok = model.Extension.SaveAs(path, self.c['swSaveAsCurrentVersion'], self.c['swSaveAsOptions_Silent'],
                                    NULL, errors, warnings)
        if not ok or errors.value:
            raise RuntimeError(f'Kaydedilemedi: {path} ({errors.value})')
        print('kaydedildi:', path)
        return path

    def no_dimension_dialog(self):
        """AddDimension2 opens the Modify dialog when 'input dimension value' is on; restore after."""
        key = self.c['swInputDimValOnCreate']
        previous = self.app.GetUserPreferenceToggle(key)
        self.app.SetUserPreferenceToggle(key, False)
        return lambda: self.app.SetUserPreferenceToggle(key, previous)

    # ---------- fixtures ----------
    def shaft(self):
        model = self.new('part')
        front = self.planes(model)[0]
        self.sketch_on(model, front)
        sm = model.SketchManager
        profile = [(0, 0), (0, 15), (40, 15), (40, 20), (100, 20), (100, 12.5), (150, 12.5), (150, 0)]
        lines = [sm.CreateLine(a[0]*MM, a[1]*MM, 0., b[0]*MM, b[1]*MM, 0.)
                 for a, b in zip(profile, profile[1:] + profile[:1])]
        sm.CreateCenterLine(0., 0., 0., .15, 0., 0.)
        restore = self.no_dimension_dialog()
        try:
            self.dimension(model, lines[1], .02, .025)       # Ø30 kademe uzunluğu 40
            self.dimension(model, lines[3], .07, .03)        # 60
            self.dimension(model, lines[5], .125, .02)       # 50
        finally:
            restore()
        self.close_sketch(model)
        feature = model.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0,
                                                       2*math.pi, 0., False, False, 0., 0., 0, 0., 0.,
                                                       True, True, True)
        if feature is None:
            raise RuntimeError('Döndürme unsuru oluşturulamadı')
        path = self.save(model, os.path.join(self.root, '01-mil'), 'kademeli_mil.SLDPRT')
        self.app.CloseDoc(model.GetTitle)
        return path

    def plate(self):
        model = self.new('part')
        front = self.planes(model)[0]
        self.sketch_on(model, front)
        sm = model.SketchManager
        rectangle = sm.CreateCornerRectangle(0., 0., 0., .1, .05, 0.)
        circles = [sm.CreateCircleByRadius(x*MM, y*MM, 0., 4*MM) for x, y in ((10, 10), (90, 10), (10, 40), (90, 40))]
        circles.append(sm.CreateCircleByRadius(.05, .025, 0., 3*MM))
        restore = self.no_dimension_dialog()
        try:
            self.dimension(model, rectangle[0], .05, -.01)
            self.dimension(model, rectangle[1], .11, .025)
            self.dimension(model, circles[0], .0, .0)
            self.dimension(model, circles[4], .06, .035)
        finally:
            restore()
        self.close_sketch(model)
        feature = model.FeatureManager.FeatureExtrusion3(True, False, False, 0, 0, .01, 0., False, False, False,
                                                         False, 0., 0., False, False, False, False, True, True, True,
                                                         0, 0., False)
        if feature is None:
            raise RuntimeError('Ekstrüzyon oluşturulamadı')
        path = self.save(model, os.path.join(self.root, '02-delikli-plaka'), 'delikli_plaka.SLDPRT')
        self.app.CloseDoc(model.GetTitle)
        return path

    def extrude_plate(self, model, width, height, thickness):
        self.sketch_on(model, self.planes(model)[0])
        model.SketchManager.CreateCornerRectangle(0., 0., 0., width, height, 0.)
        self.close_sketch(model)
        feature = model.FeatureManager.FeatureExtrusion3(
            True, False, False, 0, 0, thickness, 0., False, False, False, False,
            0., 0., False, False, False, False, True, True, True, 0, 0., False)
        if feature is None:
            raise RuntimeError('Fixture plakası oluşturulamadı')
        return feature

    def wizard_plate(self):
        model = self.new('part')
        self.extrude_plate(model, .1, .05, .01)
        c = self.c
        for x, y in ((.02, .015), (.08, .015), (.02, .035), (.08, .035)):
            model.ClearSelection2(True)
            if not model.Extension.SelectByRay(x, y, .02, 0., 0., -1., .0001, c['swSelFACES'],
                                                False, 0, 0):
                raise RuntimeError('Hole Wizard yüzü seçilemedi')
            feature = model.FeatureManager.HoleWizard5(
                c['swWzdCounterSink'], c['swStandardAnsiMetric'], c['swStandardAnsiMetricFlatHead82'],
                'M5', c['swEndCondThroughAll'], .0055, .01, 0.,
                .01, math.pi/2, 0., 0., -1., -1., -1., -1., 1., -1., -1., -1.,
                '', False, True, True, True, True, False)
            if feature is None or feature.GetTypeName2 != 'HoleWzd':
                raise RuntimeError('Native Hole Wizard deliği oluşturulamadı')
        model.ClearSelection2(True)
        path = self.save(model, os.path.join(self.root, '09-wizard'), 'kabul_wizard_plaka.SLDPRT')
        self.app.CloseDoc(model.GetTitle)
        return path

    def bored_shaft(self):
        model = self.new('part')
        self.sketch_on(model, self.planes(model)[0])
        sm = model.SketchManager
        # Both coaxial bores open at the left end; the smaller one passes through.
        points = ((0, 8), (30, 8), (30, 4), (150, 4), (150, 13),
                  (110, 13), (110, 20), (45, 20), (45, 15), (0, 15))
        for a, b in zip(points, points[1:] + points[:1]):
            sm.CreateLine(a[0]*MM, a[1]*MM, 0., b[0]*MM, b[1]*MM, 0.)
        sm.CreateCenterLine(0., 0., 0., .15, 0., 0.)
        self.close_sketch(model)
        feature = model.FeatureManager.FeatureRevolve2(
            True, True, False, False, False, False, 0, 0, 2*math.pi, 0.,
            False, False, 0., 0., 0, 0., 0., True, True, True)
        if feature is None:
            raise RuntimeError('İç kademeli mil oluşturulamadı')
        path = self.save(model, os.path.join(self.root, '10-kesit'), 'kabul_ic_kademeli_mil.SLDPRT')
        self.app.CloseDoc(model.GetTitle)
        return path

    def small_radius_detail(self):
        model = self.new('part')
        self.extrude_plate(model, .08, .03, .008)
        c = self.c
        model.ClearSelection2(True)
        if not model.Extension.SelectByRay(.081, .031, .004, -1., -1., 0., .00005,
                                            c['swSelEDGES'], False, 1, 0):
            raise RuntimeError('R2 için köşe kenarı seçilemedi')
        feature = model.FeatureManager.FeatureFillet3(
            c['swFeatureFilletUniformRadius'], .002, 0., 0., c['swFeatureFilletType_Simple'],
            c['swFilletOverFlowType_Default'], c['swFeatureFilletCircular'], *([None]*7))
        if feature is None or 'fillet' not in feature.GetTypeName2.casefold():
            raise RuntimeError('Native 2 mm radyüs oluşturulamadı')
        model.ClearSelection2(True)
        path = self.save(model, os.path.join(self.root, '11-detay'), 'kabul_r2_detay.SLDPRT')
        self.app.CloseDoc(model.GetTitle)
        return path

    def company_templates(self):
        """Dedicated fixture templates. Customer-provided templates are separate inputs."""
        folder = Path(self.root)/'08-sablon'
        source = _assembly(self, str(folder), 'kabul_sablon_montaj.SLDASM',
                           [(_part(self, 'plate'), 2), (_part(self, 'shaft'), 1)])
        # Force an A3 sheet before saving its format: the user's default DRWDOT
        # may describe another size or have no antet at all.
        from modules.automatic_drawing.solidworks import Session, call, get, null_dispatch
        from modules.automatic_drawing.solidworks import out_int as raw_out_int
        with Session() as session:
            c = session.c
            install = Path(call(session.app, 'GetExecutablePath'))
            iso = session.standard_sheet_format('A3')
            template = call(session.app, 'GetUserPreferenceStringValue', c('swDefaultTemplateDrawing'))
            model, drawing = session.new_drawing(template, 420, 297, c('swDwgPaperA3size'))
            try:
                sheet = call(drawing, 'GetCurrentSheet')
                name = call(sheet, 'GetName')
                if not iso or not call(drawing, 'SetupSheet6',
                        name, c('swDwgPaperA3size'), c('swDwgTemplateCustom'), 1., 1., True, iso,
                        .42, .297, '', False, .01, .01, .01, .01, 4, 4):
                    raise RuntimeError('A3 kabul paftası ayarlanamadı')
                sheet = call(drawing, 'GetCurrentSheet')
                width, height = call(sheet, 'GetProperties2')[5:7]
                if not math.isclose(width, .42, abs_tol=.00005) or not math.isclose(height, .297, abs_tol=.00005):
                    raise RuntimeError(f'Beklenen A3 yerine {width:g} × {height:g} m pafta oluşturuldu')
                sheet_format, drwdot = folder/'kabul_antet.slddrt', folder/'kabul_resim.drwdot'
                for target in (sheet_format, drwdot):
                    if target.exists():
                        raise FileExistsError(target)
                if not call(sheet, 'SaveFormat', str(sheet_format)):
                    raise RuntimeError('Fixture antet şablonu kaydedilemedi')
                errors, warnings = raw_out_int(), raw_out_int()
                if not call(get(model, 'Extension'), 'SaveAs', str(drwdot), c('swSaveAsCurrentVersion'),
                            c('swSaveAsOptions_Silent'), null_dispatch(), errors, warnings) or errors.value:
                    raise RuntimeError(f'Fixture resim şablonu kaydedilemedi ({errors.value})')
            finally:
                session.close_created(model)
        bom = folder/'kabul_bom.sldbomtbt'
        with (install/'lang'/'english'/'bom-standard.sldbomtbt').open('rb') as src, bom.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        return source


def _sheet_body(builder, model, plane, x0, thickness, depth, merge=False):
    """U profile (2 bends) as a sheet metal base flange; returns the new feature."""
    builder.sketch_on(model, plane)
    sm = model.SketchManager
    points = [(x0, 30), (x0, 0), (x0+60, 0), (x0+60, 30)]
    for a, b in zip(points, points[1:]):
        sm.CreateLine(a[0]*MM, a[1]*MM, 0., b[0]*MM, b[1]*MM, 0.)
    builder.close_sketch(model)
    # Argument set accepted by SolidWorks 2025 SP5 (UseDefaultRelief=False, small relief sizes).
    feature = model.FeatureManager.InsertSheetMetalBaseFlange2(
        thickness*MM, False, 2*MM, depth*MM, .01, False, 0, 0, 0, NULL,
        False, 0, .0001, .0001, .5, True, merge, True, True)
    if feature is None:
        raise RuntimeError('Sac taban flanşı oluşturulamadı')
    return feature


def _native_flat_configurations(builder, model, path):
    """Let SolidWorks create its own '<parent>SM-FLAT-PATTERN' configuration(s), as a user would by
    once inserting a flat pattern view (one per sheet body, the body pre-selected), then save the part."""
    app, c = builder.app, builder.c
    parent = model.ConfigurationManager.ActiveConfiguration.Name
    template = app.GetUserPreferenceStringValue(c['swDefaultTemplateDrawing'])
    drawing = app.NewDocument(template, c['swDwgPapersUserDefined'], .42, .297)
    builder.created.append(drawing.GetTitle)
    errors = out_int()
    bodies = sorted((b for b in model.GetBodies2(c['swSolidBody'], False) if b.IsSheetMetal), key=lambda b: b.Name)
    for index, body in enumerate(bodies):
        app.ActivateDoc3(model.GetTitle, False, 0, errors)
        model.ClearSelection2(True)
        if len(bodies) > 1 and not body.Select2(False, None):
            raise RuntimeError('Sac gövdesi seçilemedi: ' + body.Name)
        app.ActivateDoc3(drawing.GetTitle, False, 0, errors)
        view = drawing.CreateFlatPatternViewFromModelView3(path, parent, .1 + .15*index, .15, 0., False, False)
        if view is None:
            raise RuntimeError('SolidWorks açınım görünüşü oluşturmadı: ' + body.Name)
        print('  ', body.Name, '→', view.ReferencedConfiguration)
    app.CloseDoc(drawing.GetTitle)
    app.ActivateDoc3(model.GetTitle, False, 0, errors)
    model.ShowConfiguration2(parent)
    warnings = out_int()
    if not model.Save3(builder.c['swSaveAsOptions_Silent'], errors, warnings) or errors.value:
        raise RuntimeError(f'Parça açınım konfigürasyonlarıyla kaydedilemedi ({errors.value})')
    print('   konfigürasyonlar:', tuple(model.GetConfigurationNames))


def sheet(builder):
    model = builder.new('part')
    front = builder.planes(model)[0]
    _sheet_body(builder, model, front, 0, 2, 50)
    path = builder.save(model, os.path.join(builder.root, '03-sac'), 'tek_govde_sac.SLDPRT')
    _native_flat_configurations(builder, model, path)
    builder.app.CloseDoc(model.GetTitle)
    return path


def multibody_sheet(builder):
    model = builder.new('part')
    front = builder.planes(model)[0]
    _sheet_body(builder, model, front, 0, 2, 50, merge=False)
    _sheet_body(builder, model, front, 100, 3, 40, merge=False)
    path = builder.save(model, os.path.join(builder.root, '04-cok-govdeli-sac'), 'cok_govdeli_sac.SLDPRT')
    _native_flat_configurations(builder, model, path)
    builder.app.CloseDoc(model.GetTitle)
    return path


def _assembly(builder, folder, name, parts, suppress=(), configuration=None):
    """Assembly of copies of the shaft/plate fixtures placed in ``folder``.

    parts: [(source_part, count)]; suppress: component indexes suppressed in the active
    configuration; configuration: (name, indexes suppressed only there) for a second configuration.
    """
    import shutil
    app, c = builder.app, builder.c
    os.makedirs(folder, exist_ok=True)
    paths, opened = [], []
    for source, count in parts:
        target = os.path.join(folder, os.path.basename(source))
        if not os.path.exists(target):
            shutil.copy2(source, target)
        doc = app.GetOpenDocumentByName(target)
        already_open = doc is not None
        if not already_open:
            errors, warnings = out_int(), out_int()
            doc = app.OpenDoc6(target, c['swDocPART'], c['swOpenDocOptions_Silent'], '', errors, warnings)
        if doc is None or os.path.normcase(doc.GetPathName) != os.path.normcase(target):
            raise RuntimeError('Bileşen açılamadı: ' + target)
        if not already_open:
            opened.append(target)
            builder.created.append(target)
        paths += [target]*count
    model = builder.new('assembly')
    components = []
    for index, path in enumerate(paths):
        component = model.AddComponent5(path, c['swAddComponentConfigOptions_CurrentSelectedConfig'], '', False, '',
                                        .2*index, 0., 0.)
        if component is None:
            raise RuntimeError('Bileşen eklenemedi: ' + path)
        components.append(component)
    for index in suppress:
        components[index].SetSuppression2(c['swComponentSuppressed'])
    if configuration is not None:
        parent = model.ConfigurationManager.ActiveConfiguration.Name
        other, hidden = configuration
        if model.ConfigurationManager.AddConfiguration2(other, '', '', 0, '', '', True) is None:
            raise RuntimeError('Montaj konfigürasyonu oluşturulamadı: ' + other)
        model.ShowConfiguration2(other)
        # Component handles from before the configuration change do not apply there:
        # reacquire them in the new configuration and check the state actually read back.
        names = [x.Name2 for x in components]
        current = {x.Name2: x for x in model.GetComponents(True)}
        for index in hidden:
            target = current[names[index]]
            target.SetSuppression2(c['swComponentSuppressed'])
            if model.GetComponentByName(names[index]).GetSuppression2 != c['swComponentSuppressed']:
                raise RuntimeError('Bileşen bastırılamadı: ' + names[index])
        model.ForceRebuild3(False)
        model.ShowConfiguration2(parent)
    path = builder.save(model, folder, name)
    app.CloseDoc(model.GetTitle)
    for target in opened:
        app.CloseDoc(target)
    return path


def _part(builder, key):
    relative = {'shaft': r'01-mil\kademeli_mil.SLDPRT', 'plate': r'02-delikli-plaka\delikli_plaka.SLDPRT'}[key]
    for root in (builder.root, os.path.dirname(builder.root)):     # v2\ fixtures reuse the base parts
        if os.path.isfile(os.path.join(root, relative)):
            return os.path.join(root, relative)
    raise FileNotFoundError(relative)


def assembly(builder):
    return _assembly(builder, os.path.join(builder.root, '05-montaj-konfig'), 'konfigurasyonlu_montaj.SLDASM',
                     [(_part(builder, 'plate'), 3), (_part(builder, 'shaft'), 1)], configuration=('Konfig-B', (1, 2)))


def suppressed_assembly(builder):
    return _assembly(builder, os.path.join(builder.root, '06-montaj-bastirilmis'), 'bastirilmis_montaj.SLDASM',
                     [(_part(builder, 'plate'), 2), (_part(builder, 'shaft'), 1)], suppress=(1,))


def missing_reference(builder):
    folder = os.path.join(builder.root, '07-eksik-referans')
    path = _assembly(builder, folder, 'eksik_referansli_montaj.SLDASM',
                     [(_part(builder, 'plate'), 1), (_part(builder, 'shaft'), 1)])
    missing = os.path.join(folder, 'kademeli_mil.SLDPRT')
    os.remove(missing)          # this fixture's own copy; the assembly now has a missing reference
    print('silindi (eksik referans için):', missing)
    return path


Builder.sheet = sheet
Builder.multibody_sheet = multibody_sheet
Builder.assembly = assembly
Builder.suppressed_assembly = suppressed_assembly
Builder.missing_reference = missing_reference


def build_fixtures(root, wanted):
    pythoncom.CoInitialize()
    try:
        builder = Builder(root)
        failed = False
        for name in wanted:
            try:
                getattr(builder, name)()
            except Exception as error:      # noqa: BLE001
                failed = True
                print(f'{name}: HATA {type(error).__name__}: {error}')
            finally:
                for title in builder.created:   # only documents this builder created or opened
                    if builder.app.GetOpenDocumentByName(title) is not None:
                        builder.app.CloseDoc(title)
                builder.created.clear()
        return int(failed)
    finally:
        pythoncom.CoUninitialize()


def main():
    root = os.path.abspath(sys.argv[1])
    wanted = sys.argv[2:] or ['shaft', 'plate']
    # A worker apartment lets both the builder and nested drawing Session
    # acquire and release their own COM references.
    with ThreadPoolExecutor(max_workers=1) as worker:
        return worker.submit(build_fixtures, root, wanted).result()


if __name__ == '__main__':
    raise SystemExit(main())
