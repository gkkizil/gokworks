"""Gerçek SolidWorks'te teknik resim API zincirini modülsüz, adım adım dener.

Kullanım (açık SolidWorks ile):
    python tools/automatic_drawing/sw_drawing_probe.py KAYNAK.SLDPRT CIKTI_KLASORU [--paper A3]

Kaynak dosya salt-okunur açılır ve asla kaydedilmez. Her çağrının dönüş değeri
ve varsa COM hata kodu yazdırılır. Sabitler kurulu swconst kitaplığından okunur.
"""

import argparse
import glob
import os
import sys
import traceback

import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.cad_converter.api import load_constants  # noqa: E402  (yalnız sabitler)

PAPERS = {'A4': (.297, .210), 'A3': (.420, .297), 'A2': (.594, .420), 'A1': (.841, .594), 'A0': (1.189, .841)}


NULL = VARIANT(pythoncom.VT_DISPATCH, None)


def out_int():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def step(label, fn):
    try:
        value = fn()
        print(f'[OK ] {label}: {value!r}')
        return value
    except pythoncom.com_error as error:
        print(f'[COM] {label}: hresult={error.hresult} {error.strerror} {error.excepinfo}')
    except Exception as error:      # noqa: BLE001 — deneme betiği, her hatayı yazdırır
        print(f'[ERR] {label}: {type(error).__name__}: {error}')
        traceback.print_exc(limit=1)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--paper', default='A3', choices=sorted(PAPERS))
    parser.add_argument('--template', default='')
    args = parser.parse_args()
    width, height = PAPERS[args.paper]

    pythoncom.CoInitialize()
    app = wc.dynamic.Dispatch(wc.GetActiveObject('SldWorks.Application')._oleobj_)
    c = load_constants(app)
    print('SolidWorks revizyonu:', app.RevisionNumber)
    step('Dil', lambda: app.GetCurrentLanguage)

    template = args.template or app.GetUserPreferenceStringValue(c['swDefaultTemplateDrawing'])
    print('Varsayılan resim şablonu:', template, '| var:', os.path.isfile(template))
    folders = app.GetUserPreferenceStringValue(c['swFileLocationsSheetFormat']) or ''
    print('Sayfa biçimi klasörleri:', folders)
    formats = []
    for folder in folders.split(';'):
        formats += glob.glob(os.path.join(folder, '*.slddrt'))
    if not formats:
        root = os.path.dirname(os.path.dirname(template))  # ...\SOLIDWORKS 2025
        lang = app.GetCurrentLanguage
        formats = glob.glob(os.path.join(root, 'lang', lang, 'sheetformat', '*.slddrt'))
        print('Ayarlı klasör boş; kurulum klasöründen:', os.path.join(root, 'lang', lang, 'sheetformat'))
    print('Bulunan .slddrt:', len(formats))

    # --- kaynak: salt okunur ---
    errors, warnings = out_int(), out_int()
    options = c['swOpenDocOptions_Silent'] | c['swOpenDocOptions_ReadOnly']
    part = app.OpenDoc6(args.source, c['swDocPART'], options, '', errors, warnings)
    print('OpenDoc6:', part is not None, 'errors', errors.value, 'warnings', warnings.value)
    view_names = step('GetModelViewNames', lambda: tuple(part.GetModelViewNames))

    # --- NewDocument ---
    model = step('NewDocument', lambda: app.NewDocument(template, c['swDwgPapersUserDefined'], width, height))
    if model is None:
        return
    drawing = model
    step('GetType', lambda: model.GetType)
    sheet = drawing.GetCurrentSheet
    step('Sheet.GetName', lambda: sheet.GetName)
    step('Sheet.GetTemplateName', lambda: sheet.GetTemplateName)
    step('Sheet.GetProperties2', lambda: tuple(sheet.GetProperties2))
    step('Sheet.GetSheetFormatName', lambda: sheet.GetSheetFormatName)
    step('Sheet.SheetFormatVisible', lambda: sheet.SheetFormatVisible)
    step('Sheet.CustomPropertyView', lambda: sheet.CustomPropertyView)

    name = step('Sheet.GetName', lambda: sheet.GetName) or 'Sayfa1'
    zones = (.01, .01, .01, .01, 4, 4)
    fmt = next((f for f in formats if os.path.basename(f).casefold().startswith(args.paper.casefold())
                and 'iso' in os.path.basename(f).casefold()), '')
    print('Kağıda uygun sayfa biçimi:', fmt or 'YOK')

    def setup(label, kind, tmpl, w, h, view):
        r = step(f'SetupSheet6[{label}]', lambda: drawing.SetupSheet6(
            name, c['swDwgPapersUserDefined'], kind, 1., 1., False, tmpl, w, h, view, False, *zones))
        s = drawing.GetCurrentSheet
        print('      props:', tuple(s.GetProperties2), '| template:', s.GetTemplateName)
        return r

    setup('custom+şablonun kendi adı', c['swDwgTemplateCustom'], sheet.GetTemplateName, width, height, '')
    setup('none, boş', c['swDwgTemplateNone'], '', width, height, '')
    if fmt:
        setup('custom+slddrt', c['swDwgTemplateCustom'], fmt, width, height, '')
        setup('custom+slddrt, Default', c['swDwgTemplateCustom'], fmt, width, height, 'Default')
    step('ForceRebuild3', lambda: model.ForceRebuild3(False))
    step('Sheet.GetTemplateName (son)', lambda: drawing.GetCurrentSheet.GetTemplateName)

    # --- görünüşler ---
    views = {}
    for wanted in ('*Front', '*Ön', *(view_names or ())[:1]):
        v = step(f'CreateDrawViewFromModelView3[{wanted}]',
                 lambda: drawing.CreateDrawViewFromModelView3(args.source, wanted, .12, .18, 0.))
        if v is not None:
            views['main'] = v
            break
    main = views.get('main')
    if main is not None:
        vname = main.GetName2
        print('Ana görünüş adı:', vname)
        step('ActivateView', lambda: drawing.ActivateView(vname))
        step('SelectByID2', lambda: model.Extension.SelectByID2(vname, 'DRAWINGVIEW', 0., 0., 0., False, 0, NULL, 0))
        top = step('CreateUnfoldedViewAt3', lambda: drawing.CreateUnfoldedViewAt3(.12, .26, 0., False))
        mask = c['swInsertDimensionsMarkedForDrawing']
        for k in ('swInsertHoleWizardProfileDimensions', 'swInsertHoleWizardLocationDimensions'):
            mask |= c.get(k, 0)
        step('SelectByID2 (ölçü öncesi)', lambda: model.Extension.SelectByID2(vname, 'DRAWINGVIEW', 0., 0., 0., False, 0, NULL, 0))
        ann = step('InsertModelAnnotations3', lambda: drawing.InsertModelAnnotations3(
            c['swImportModelItemsFromEntireModel'], mask, False, True, False, False))
        print('      dönen:', type(ann), (len(ann) if isinstance(ann, tuple) else ''))
        step('GetDimensionCount4', lambda: main.GetDimensionCount4)
        cm_mask = 0
        for k, val in c.items():
            if k.startswith('swAutoInsertCenterMark') and 'hole' in k.casefold():
                cm_mask |= val
        print('Merkez işareti maskesi:', cm_mask, [k for k in c if k.startswith('swAutoInsertCenterMark')])
        step('AutoInsertCenterMarks2', lambda: main.AutoInsertCenterMarks2(
            cm_mask, 0, True, True, True, 0., 0., False, True, 0.))
        step('GetCenterMarkCount2 (argsız)', lambda: main.GetCenterMarkCount2)
        step('GetCenterMarkCount2(out)', lambda: main.GetCenterMarkCount2(out_int()))
        step('GetCenterMarkCount', lambda: main.GetCenterMarkCount)
        step('GetCenterMarks', lambda: (lambda m: len(m) if m else m)(main.GetCenterMarks))

    # --- kaydet ---
    os.makedirs(args.output, exist_ok=True)
    for ext in ('SLDDRW', 'PDF'):
        path = os.path.join(args.output, 'probe.' + ext)
        e, w = out_int(), out_int()
        flags = c['swSaveAsOptions_Silent'] | (c['swSaveAsOptions_Copy'] if ext == 'PDF' else 0)
        r = step(f'Extension.SaveAs[{ext}]', lambda: model.Extension.SaveAs(
            path, c['swSaveAsCurrentVersion'], flags, NULL, e, w))
        print('      errors', e.value, 'warnings', w.value, 'dosya:', os.path.isfile(path))

    title = model.GetTitle
    app.CloseDoc(title)
    if part is not None:
        app.CloseDoc(part.GetTitle)


if __name__ == '__main__':
    main()
