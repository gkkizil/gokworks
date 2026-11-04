"""Analysis entry points: pure Python, safe on a worker thread, read-only on sources."""

from datetime import datetime
import hashlib
from pathlib import Path

from .importers import dxf as dxf_reader
from .geometry import topology
from .models import AnalysisResult
from .profiles import bundled
from .rules import Context, evaluate

SCOPE = ('Yalnız seçilen profildeki kurallarla yapılan 2B geometri kontrolüdür; üretime uygunluk onayı veya '
         'sertifika değildir. Makineye özel sınırlar profilde doğrulanmadıkça örnek değerdir. Kerf telafisi, '
         'giriş/çıkış (lead-in/out), ısı dağılımı ve takım yolu kontrol edilmez.')


def analyze(path, profile, *, thickness=None, material='', unit=None, tolerance=.01, excluded_layers=(),
            stop=None, progress=None):
    """Read ``path`` (DXF) and evaluate ``profile``. Raises MissingUnits when the unit is needed."""
    path = Path(path)
    if path.suffix.casefold() != '.dxf':
        raise ValueError('Aşama 1 yalnız DXF analiz eder. DWG için önce DXF’e dönüştürün.')
    if thickness is not None and (thickness <= 0 or thickness != thickness):
        raise ValueError('Sac kalınlığı pozitif olmalı.')
    report = progress or (lambda *args: None)
    report(0, 3, 'DXF okunuyor')
    drawing, data = dxf_reader.read(path, unit=unit, tolerance=tolerance, excluded_layers=excluded_layers, stop=stop)
    report(1, 3, 'Konturlar ve parçalar çıkarılıyor')
    topo = topology.build(drawing.contours, closure=profile.closure_tolerance, short_segment=profile.short_segment,
                          tolerance=tolerance, stop=stop)
    report(2, 3, 'Kurallar değerlendiriliyor')
    context = Context(topo, drawing, profile, thickness, material, accuracy=tolerance, stop=stop)
    outcomes, findings = evaluate(context)
    if path.read_bytes() != data:
        raise ValueError('Kaynak DXF analiz sırasında değişti; yeniden analiz edin.')
    notes = [f'Kaynak birim: {drawing.source_unit or "mm"}; sonuçlar mm.',
             f'Eğriler en çok {tolerance:g} mm kiriş sapmasıyla düzleştirildi; ölçümler bu kadar sapabilir.']
    if drawing.ignored:
        kinds = {}
        for kind, layer, reason in drawing.ignored:
            kinds[(reason, layer)] = kinds.get((reason, layer), 0) + 1
        notes += [f'{n} nesne kesime katılmadı ({layer}): {reason}.' for (reason, layer), n in sorted(kinds.items())]
    if not profile.verified:
        notes.append('Profil doğrulanmamış örnek başlangıç profilidir; sınırlar makine verisi değildir.')
    report(3, 3, 'Tamamlandı')
    return AnalysisResult(
        source=str(path.resolve()), sha256=hashlib.sha256(data).hexdigest(),
        analysed_at=datetime.now().astimezone().isoformat(timespec='seconds'), process=profile.process,
        material=material, thickness_mm=thickness, profile_id=profile.id, profile_name=profile.name,
        profile_version=profile.profile_version, profile_verified=profile.verified, unit='mm',
        outcomes=outcomes, findings=findings,
        parts=[dict(name=p.name, island=p.island, outline=list(p.outline.polygon.exterior.coords),
                    holes=[list(h.polygon.exterior.coords) for h in p.holes]) for p in topo.parts],
        contours=[dict(handle=c['handle'], layer=c['layer'], points=c['points']) for c in drawing.contours],
        notes=notes, scope=SCOPE)


def profiles():
    return bundled()


def worker(path, profile, options):
    """JobManager entry: events ('dfm_progress', (i, n, text)) then ('dfm_result', AnalysisResult)."""
    def run(events, stop):
        result = analyze(path, profile, stop=stop,
                         progress=lambda i, n, text: events.put(('dfm_progress', (i, n, text))), **options)
        events.put(('dfm_result', result))
    return run
