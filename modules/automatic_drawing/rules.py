"""Conservative geometry rules; evidence and design intent remain distinct."""

from collections import Counter
from dataclasses import dataclass
import math

from .models import ViewPlan, identity

MODEL_VIEWS = {'front': '*Front', 'back': '*Back', 'top': '*Top', 'bottom': '*Bottom',
               'right': '*Right', 'left': '*Left', 'isometric': '*Isometric'}
NORMAL_AXIS = {'front': 2, 'back': 2, 'top': 1, 'bottom': 1, 'right': 0, 'left': 0}
VIEW_AXES = {'front': (0, 1, 2), 'back': (0, 1, 2), 'top': (0, 2, 1),
             'bottom': (0, 2, 1), 'right': (2, 1, 0), 'left': (2, 1, 0)}
CLASS_TITLES = {'general': 'Genel makine parçası', 'assembly': 'Montaj',
                'sheet': 'Sac metal', 'plate': 'Plaka', 'block': 'Prizmatik parça',
                'shaft': 'Mil / döner parça', 'flange': 'Flanş', 'bushing': 'Burç / boru',
                'weldment': 'Kaynaklı konstrüksiyon', 'multibody': 'Çok gövdeli parça',
                'freeform': 'Karmaşık / serbest yüzey'}


def classify(info):
    if info.kind == 'assembly':
        return 'assembly', 'SolidWorks belge türü montaj.'
    kinds = {k.casefold() for k in info.feature_types}
    if info.sheet_body_count and any('sheetmetal' in k or 'flatpattern' in k for k in kinds):
        return 'sheet', 'Sac gövdesi ve SheetMetal / FlatPattern unsuru birlikte doğrulandı.'
    if any('weld' in k or 'structuralmember' in k for k in kinds):
        return 'weldment', 'Kaynak / yapısal profil unsuru bulundu.'
    if info.body_count > 1:
        return 'multibody', 'Birden fazla katı gövde bulundu; tek parçaya indirgenmedi.'
    dimensions = sorted(info.size_mm)
    if len(dimensions) != 3 or min(dimensions) <= 0:
        return 'general', 'Geometri sınıflandırması için veri yetersiz.'
    planar = sum(f.kind == 'plane' for f in info.faces)
    cylinders = sum(f.kind == 'cylinder' for f in info.faces)
    revolved = any('revol' in k for k in kinds)
    if revolved and cylinders:
        if dimensions[2] > 1.8*dimensions[1]:
            return 'shaft', 'Döndürme unsuru, silindirik yüzey ve uzun eksen birlikte bulundu.'
        if cylinders >= 2 and dimensions[0] < .6*dimensions[2]:
            return 'flange', 'Döndürme unsuru ve ince dairesel gövde; flanş sınıfı önerildi.'
        return 'bushing', 'Döndürme unsuru ve silindirik yüzeyler; burç sınıfı önerildi.'
    if planar >= 2 and dimensions[0] <= .18*dimensions[2]:
        return 'plate', 'İnce dış ölçüler ve düzlemsel yüzeyler birlikte bulundu.'
    if planar >= 6 and not cylinders and planar == len(info.faces):
        return 'block', 'Taranan yüzeylerin tamamı düzlemsel.'
    if info.faces and sum(f.kind == 'other' for f in info.faces) > len(info.faces)*.6:
        return 'freeform', 'Taranan yüzeylerin çoğu düzlemsel veya silindirik değil.'
    return 'general', 'Kesin imalat sınıfı çıkarılmadı; genel görünüş kuralları kullanıldı.'


@dataclass(frozen=True)
class ViewScore:
    name: str
    score: float
    reasons: tuple


def score_views(info):
    """Use measured face areas, cylinder axes and bounding projection as proxies.

    These are not hidden-line or silhouette measurements. Opposite directions
    tie unless a user explicitly chooses one; stable ordering makes this repeatable.
    """
    size = info.size_mm
    diagonal = max(math.sqrt(sum(x*x for x in size)), 1e-9)
    total_planar = sum(f.area_mm2 for f in info.faces if f.kind == 'plane') or 1.
    total_cyl = sum(f.area_mm2 for f in info.faces if f.kind == 'cylinder') or 1.
    scores = []
    for name, (a, b, normal) in VIEW_AXES.items():
        area = size[a]*size[b] / diagonal**2
        face = sum(f.area_mm2*abs(f.direction[normal]) for f in info.faces
                   if f.kind == 'plane' and len(f.direction) == 3) / total_planar
        axis = sum(f.area_mm2*abs(f.direction[normal]) for f in info.faces
                   if f.kind == 'cylinder' and len(f.direction) == 3) / total_cyl
        if info.classification in ('shaft', 'bushing'):
            manufacturing = 1-axis       # show the turning axis in the plane
        elif info.classification == 'flange':
            manufacturing = axis
        else:
            manufacturing = face
        score = 2*area + 3*face + 3*manufacturing
        scores.append(ViewScore(name, score, ('ölçülmüş düzlemsel yüzeyler',
                                              'sınıfa bağlı eksen kuralı', 'kutu projeksiyonu')))
    return sorted(scores, key=lambda s: -s.score)


def plan_views(info, options):
    name = score_views(info)[0].name if options.main_view == 'auto' else options.main_view
    a, b, c = VIEW_AXES[name]
    w, h, d = (info.size_mm[i] for i in (a, b, c))
    views = [ViewPlan('main', MODEL_VIEWS[name], (w, h))]
    if options.top:
        views.append(ViewPlan('top', '', (w, d), parent='main'))
    if options.side:
        views.append(ViewPlan('side', '', (d, h), parent='main'))
    if options.isometric:
        # Exact isometric projection of the model's bounding box (view along (±1, ±1, ±1), Y up):
        # the part lies inside its box, so this still bounds it. Native GetOutline replaces it after creation.
        x, y, z = info.size_mm
        views.append(ViewPlan('isometric', MODEL_VIEWS['isometric'],
                              ((x+z)/math.sqrt(2), (x+2*y+z)/math.sqrt(6))))
    return views


def unique_sources(nodes, scope='all'):
    """Preserve the instance tree, but draw each file/configuration once."""
    found = {}
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        if node.state not in ('ready', 'hidden'):
            continue
        if node.source.path and (scope == 'all' or node.kind == 'part'):
            found.setdefault(node.source.key, node.source)
        stack.extend(reversed(node.children))
    return tuple(found.values())


def quantities(root, mode='parts'):
    """Count actual component occurrences, including repeated subassemblies."""
    counter = Counter()
    if root is None:
        return counter
    stack = list(root.children)
    while stack:
        node = stack.pop()
        if node.state not in ('ready', 'hidden') or node.excluded_bom:
            continue
        if mode == 'top' or node.kind == 'part':
            counter[node.source.key] += 1
        if mode != 'top':
            stack.extend(node.children)
    return counter


@dataclass(frozen=True)
class DimensionCandidate:
    model: str
    configuration: str
    name: str
    kind: str
    value: float
    references: tuple = ()
    axis: str = ''
    reference: bool = False


def unique_dimensions(candidates):
    """Equal numbers are never a duplicate test. Unknown identities stay separate."""
    seen = set()
    selected = []
    for candidate in candidates:
        key = (identity(candidate.model, candidate.configuration), candidate.name,
               candidate.kind, candidate.references, candidate.axis, candidate.reference)
        if candidate.name and key in seen:
            continue
        if candidate.name:
            seen.add(key)
        selected.append(candidate)
    return selected


def recommendations(info):
    suggestions = []
    cylinders = [f for f in info.faces if f.kind == 'cylinder']
    if info.classification in ('bushing', 'flange') or len(cylinders) > 2:
        suggestions.append('İç boşlukların ve kademelerin açıklanması için kesit gereksinimini kontrol edin.')
    if any('hole' in name.casefold() for name in info.feature_types):
        suggestions.append('Delik / diş açıklamalarını modelde tanımlanan Hole Wizard bilgileriyle doğrulayın.')
    if any('chamfer' in name.casefold() or 'fillet' in name.casefold() for name in info.feature_types):
        suggestions.append('Küçük pah ve radyüslerin okunabilirliği için detay görünüşü gereksinimini kontrol edin.')
    return suggestions
