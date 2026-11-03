"""`create_shaft_drawing` command: plan snapshot, CAD bridge and honest outcome.

The existing ``create_shaft`` command is unchanged. A drawing job either runs
on a saved GOKWORKS part, or follows a successful ``create_shaft`` that saved a
new SLDPRT. A model that was created while its drawing failed is reported as a
partial success; the model is never discarded.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from ..models import Project
from .models import DrawingSettings
from .planner import plan as build_plan

HOST_SOURCE = Path(__file__).resolve().parents[1] / 'interop' / 'ShaftDrawingHost.cs'
LOADER = r"""$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    $interop = $env:GOKWORKS_SHAFT_INTEROP
    $constants = [IO.Path]::Combine([IO.Path]::GetDirectoryName($interop), 'SolidWorks.Interop.swconst.dll')
    [Reflection.Assembly]::LoadFrom($interop) | Out-Null
    [Reflection.Assembly]::LoadFrom($constants) | Out-Null
    $references = @($interop, $constants, 'System.dll', 'System.Core.dll', 'System.Web.Extensions.dll')
    $facade = [IO.Path]::Combine([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory(), 'Facades\netstandard.dll')
    if ([IO.File]::Exists($facade)) { $references += $facade }
    Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:GOKWORKS_SHAFT_HOST)) -ReferencedAssemblies $references -ErrorAction Stop
    [Console]::WriteLine('{"event":"shaft_ready","protocol":1}')
    [Gokworks.ShaftInterop.DrawingHost]::Run()
} catch {
    [Console]::WriteLine((@{success=$false; errors=@($_.Exception.Message)} | ConvertTo-Json -Depth 4 -Compress))
    exit 1
}
"""


def output_paths(part_path, settings):
    """Sibling outputs named like the part: MIL_001.SLDDRW / .PDF / .DWG."""
    part = Path(part_path)
    return dict(drawing_path=str(part.with_suffix('.SLDDRW')),
                pdf_path=str(part.with_suffix('.PDF')) if settings.pdf else '',
                dwg_path=str(part.with_suffix('.DWG')) if settings.dwg else '')


def request(project, part_path, *, drawing_path=None, pdf_path=None, dwg_path=None):
    settings = project.drawing or DrawingSettings()
    paths = output_paths(part_path, settings)
    if drawing_path is not None:
        paths['drawing_path'] = str(drawing_path)
    if pdf_path is not None:
        paths['pdf_path'] = str(pdf_path)
    if dwg_path is not None:
        paths['dwg_path'] = str(dwg_path)
    plan = build_plan(project, settings)
    return dict(operation='create_shaft_drawing', project=project.to_dict(), plan=plan, part_path=str(part_path),
                template=settings.template, sheet_format=settings.sheet_format, **paths)


def checked_payload(payload):
    """Re-derive the plan and refuse stale, invalid or overwriting requests."""
    if not isinstance(payload, dict) or payload.get('operation') != 'create_shaft_drawing':
        raise ValueError('Desteklenmeyen teknik resim komutu.')
    project = Project.from_dict(payload['project'])
    plan = build_plan(project, project.drawing or DrawingSettings())
    if json.loads(json.dumps(plan)) != json.loads(json.dumps(payload['plan'])):
        raise ValueError('Teknik resim planı mil parametreleriyle eşleşmiyor.')
    if not plan['ready']:
        raise ValueError('Teknik resim planında hata var:\n' + '\n'.join(plan['errors']))
    part = Path(payload['part_path'])
    if not part.is_absolute() or part.suffix.lower() != '.sldprt' or not part.is_file():
        raise ValueError('Teknik resim için kayıtlı SLDPRT gerekli: ' + str(part))
    for key, suffix, required in (('drawing_path', '.slddrw', True), ('pdf_path', '.pdf', False), ('dwg_path', '.dwg', False)):
        value = payload.get(key, '')
        if not value:
            if required:
                raise ValueError('SLDDRW çıktı yolu gerekli.')
            continue
        target = Path(value)
        if not target.is_absolute() or target.suffix.lower() != suffix or not target.parent.is_dir():
            raise ValueError(f'{suffix.upper()} için mevcut klasörde tam dosya yolu gerekli.')
        if target.exists():
            raise FileExistsError('Mevcut dosya üzerine yazılmaz: ' + value)
    for name in ('template', 'sheet_format'):
        value = payload.get(name, '')
        if value and not Path(value).is_file():
            raise FileNotFoundError('Şablon dosyası bulunamadı: ' + value)
    return project, plan


def assess(result, plan):
    """Classify a host response: complete only if everything planned was created and verified."""
    problems = []
    if not isinstance(result, dict) or result.get('success') is not True:
        errors = result.get('errors', ['Geçersiz C# yanıtı.']) if isinstance(result, dict) else ['Geçersiz C# yanıtı.']
        return 'failed', [str(e) for e in errors]
    for group, title in (('views', 'görünüş'), ('dimensions', 'ölçü'), ('notes', 'not'), ('finishes', 'yüzey işareti'),
                         ('datums', 'datum'), ('frames', 'geometrik tolerans')):
        rows = result.get(group, [])
        expected = len(plan.get(group, [])) + (0 if group != 'views' else 0)
        failed = [r for r in rows if not r.get('created')]
        if group != 'views' and len(rows) != expected:
            problems.append(f'{title}: {expected} planlandı, {len(rows)} yanıt alındı.')
        if failed:
            problems.append(f'{len(failed)} {title} oluşturulamadı.')
        bad = [r for r in rows if r.get('tolerance_ok') is False]
        if bad:
            problems.append(f'{len(bad)} ölçüde tolerans doğrulanamadı.')
    reopened = result.get('reopened') or {}
    if not reopened.get('references_ok'):
        problems.append('Görünüşlerin model referansı doğrulanamadı.')
    if result.get('rebuild_success') is not True:
        problems.append('Yeniden açılan teknik resmin rebuild işlemi başarısız.')
    if result.get('part_unchanged') is not True:
        problems.append('Parça ölçülerinin değişmediği doğrulanamadı.')
    if result.get('layout_conflicts'):
        problems.append(f'{len(result["layout_conflicts"])} ölçü metni çakışması çözülemedi.')
    for key in ('pdf', 'dwg'):
        if key in result and not result[key].get('verified'):
            problems.append(f'{key.upper()} çıktısı doğrulanamadı.')
    problems += [str(i) for i in result.get('issues', [])]
    return ('complete' if not problems else 'partial'), problems


def execute(payload, *, stop=None, on_status=None):
    project, plan = checked_payload(payload)
    if sys.platform != 'win32':
        raise RuntimeError('SOLIDWORKS teknik resmi Windows ve açık SOLIDWORKS gerektirir.')
    if stop is not None and stop.is_set():
        raise RuntimeError('Teknik resim başlamadan durduruldu.')
    import pythoncom
    from solidworks.connection import connect_to_solidworks
    from modules.naming.native import _installed_interop
    from ..bridge import _exchange
    pythoncom.CoInitialize()
    app = None
    try:
        if on_status:
            on_status('Açık SOLIDWORKS oturumuna bağlanılıyor…')
        app = connect_to_solidworks()
        value = app.GetProcessID
        process_id = value() if callable(value) else value
        if type(process_id) is not int or process_id <= 0:
            raise RuntimeError('SOLIDWORKS işlem kimliği okunamadı.')
        library = _installed_interop(process_id)
    finally:
        value = None
        app = None
        pythoncom.CoUninitialize()
    if not HOST_SOURCE.is_file():
        raise RuntimeError('ShaftDrawingHost.cs uygulama paketinde bulunamadı.')
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not powershell.is_file():
        raise RuntimeError('Windows PowerShell 5.1 bulunamadı.')
    if on_status:
        on_status('SOLIDWORKS teknik resim yardımcısı hazırlanıyor…')
    command = [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-Command', LOADER]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding='utf-8', errors='strict', creationflags=subprocess.CREATE_NO_WINDOW,
                          env={**os.environ, 'GOKWORKS_SHAFT_INTEROP': str(library),
                               'GOKWORKS_SHAFT_HOST': str(HOST_SOURCE)}) as process:
        result = _exchange(process, dict(payload, process_id=process_id), stop=stop, on_status=on_status,
                           operation_timeout=600)
    if isinstance(result, dict) and result.get('success') and result.get('process_id') != process_id:
        raise RuntimeError('C# yanıtındaki SOLIDWORKS işlem kimliği uyuşmuyor.')
    state, problems = assess(result, plan)
    return dict(result if isinstance(result, dict) else {}, state=state, problems=problems)


def create_drawing(project, part_path, events, stop):
    """Worker entry: drawing for an existing, saved GOKWORKS part."""
    payload = request(project, part_path)
    if stop.is_set():
        events.put(('shaft_cancelled', None)); return
    events.put(('shaft_phase', 'Teknik resim planı doğrulandı; SOLIDWORKS teknik resmi hazırlanıyor…'))
    outcome = execute(payload, stop=stop, on_status=lambda text: events.put(('shaft_phase', text)))
    events.put(('shaft_drawing', outcome))


def create_part_and_drawing(project, output_path, events, stop):
    """Worker entry: new SLDPRT, then its drawing. A failed drawing keeps the model."""
    from .. import controller as part_controller
    snapshot = deepcopy(project)
    created = part_controller.create(snapshot, events, stop, output_path=output_path)
    if not (isinstance(created, dict) and created.get('success') is True) or not Path(output_path).is_file():
        events.put(('shaft_drawing', dict(state='skipped', problems=['Model oluşturulamadığı için teknik resim başlatılmadı.'])))
        return
    if stop.is_set():
        events.put(('shaft_drawing', dict(state='skipped', problems=['Model oluşturuldu; teknik resim durdurma isteği nedeniyle başlatılmadı.'])))
        return
    try:
        create_drawing(snapshot, output_path, events, stop)
    except Exception as error:
        events.put(('shaft_drawing', dict(state='failed', problems=[str(error)], model_path=str(output_path))))
