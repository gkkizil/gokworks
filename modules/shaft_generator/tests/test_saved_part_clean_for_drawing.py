"""'SolidWorks'te çiz + teknik resim' must hand a clean (unmodified) part to the drawing.

Reported 2026-11-03: the drawing always failed with 'Parçada kaydedilmemiş
değişiklik var'. ShaftHost saved the new part, reopened it and ran
Builder.Verify(), which rebuilds (EditRebuild3 + ForceRebuild3) and marks the
document modified; ShaftDrawingHost then refused the dirty part. ShaftHost now
saves the verified part in place and checks the flag. Live behaviour needs
SOLIDWORKS (see test_live.py); this test locks the order in the source.
"""

from pathlib import Path
import re

HOST = Path(__file__).resolve().parents[1] / 'interop' / 'ShaftHost.cs'
DRAWING = Path(__file__).resolve().parents[1] / 'interop' / 'ShaftDrawingHost.cs'


def _body():
    source = HOST.read_text(encoding='utf-8')
    start = source.index('Report("SLDPRT kaydediliyor ve yeniden açılıyor");')
    end = source.index('Console.WriteLine(Json.Serialize(new {', start)
    return source[start:end]


def test_reopened_part_is_saved_after_verification_and_before_success():
    body = _body()
    verify = body.index('builder.Verify();')
    save = body.index('model.Save3(')
    check = body.index('Need(!model.GetSaveFlag()')
    assert verify < save < check                       # rebuild first, then save, then prove clean
    assert 'model.GetSaveFlag()' in body[verify:save]  # only when actually modified
    assert 'swSaveAsOptions_Silent' in body[save:check]


def test_drawing_host_still_refuses_a_modified_part():
    # The drawing must keep binding to the saved model only; the fix is upstream.
    assert re.search(r'Need\(!part\.GetSaveFlag\(\),', DRAWING.read_text(encoding='utf-8'))


def test_drawing_views_use_the_parts_own_localized_view_names():
    """Turkish (or any localized) SOLIDWORKS names '*Front' differently; the English
    name made CreateDrawViewFromModelView3 return null ('Ana görünüş oluşturulamadı').
    Names come from IModelDoc2.GetModelViewNames (index == swStandardViews_e)."""
    source = DRAWING.read_text(encoding='utf-8')
    calls = re.findall(r'CreateDrawViewFromModelView3\(([^;]*)\);', source)
    assert calls and all('"*' not in call for call in calls)          # no hard-coded view name
    assert 'part.GetModelViewNames()' in source
    english = re.search(r'EnglishViews = \{([^}]*)\}', source).group(1)
    assert [name.strip().strip('"') for name in english.split(',')] == [
        '*Normal To', '*Front', '*Back', '*Left', '*Right', '*Top', '*Bottom', '*Isometric']
    # Front, Back, Top, Bottom, Right, Left mapped to swStandardViews_e values.
    assert 'int[] names = { 1, 2, 5, 6, 4, 3 };' in source
    assert 'ModelView(drawing, part, partPath, 7, at)' in source       # isometric
