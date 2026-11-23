"""REAL SolidWorks acceptance scenarios for the automatic drawing module.

Run on Windows with a licensed, running SolidWorks and the fixtures listed in
``docs/automatic-drawing/LIVE_ACCEPTANCE.md``::

    python -m modules.automatic_drawing.live_acceptance --report acceptance.json

Each scenario names its fixture through an environment variable. A scenario whose
fixture or SolidWorks session is missing is reported as ``çalıştırılmadı`` with the
reason; it is never reported as passed. Mock/fake COM results are not used here and
are never written into this report.

Source safety: every file in a fixture's folder is hashed before and after the run.
Any change (the user's model saved, rebuilt-and-saved, a configuration written)
fails the scenario, whatever the drawing result was.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import SimpleQueue
from threading import Event

NOT_RUN, PASSED, FAILED = 'çalıştırılmadı', 'geçti', 'kaldı'
TEMPLATE_ENV = 'GOKWORKS_DRAWING_LIVE_TEMPLATE'


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    env: str                       # fixture path (SLDPRT / SLDASM)
    options: dict = field(default_factory=dict)
    extra_env: tuple = ()          # further required variables (configuration, templates)
    expect_failure: bool = False   # the run must be refused with a clear finding


SCENARIOS = (
    Scenario('stepped_shaft', 'Kademeli mil', 'GOKWORKS_LIVE_SHAFT',
             dict(flat_pattern=False, bom=False)),
    Scenario('holed_plate', 'Delikli plaka', 'GOKWORKS_LIVE_HOLED_PLATE',
             dict(flat_pattern=False, bom=False, center_marks=True)),
    Scenario('single_body_sheet', 'Tek gövdeli sac', 'GOKWORKS_LIVE_SHEET',
             dict(flat_pattern=True, bend_lines=True, bom=False)),
    Scenario('multibody_sheet', 'Çok gövdeli sac', 'GOKWORKS_LIVE_MULTIBODY_SHEET',
             dict(flat_pattern=True, bom=False)),
    Scenario('assembly_configurations', 'Konfigürasyonlu montaj', 'GOKWORKS_LIVE_ASSEMBLY',
             dict(bom=True, bom_type='parts', balloons=True), extra_env=('GOKWORKS_LIVE_ASSEMBLY_CONFIGURATION',)),
    Scenario('assembly_suppressed_component', 'Bastırılmış bileşenli montaj', 'GOKWORKS_LIVE_SUPPRESSED_ASSEMBLY',
             dict(bom=True, bom_type='parts')),
    Scenario('missing_reference', 'Eksik referanslı montaj', 'GOKWORKS_LIVE_MISSING_REFERENCE',
             dict(bom=True), expect_failure=True),
    Scenario('company_templates', 'Firma DRWDOT / SLDDRT / BOM şablonları', 'GOKWORKS_LIVE_COMPANY_SOURCE',
             dict(bom=True), extra_env=('GOKWORKS_LIVE_COMPANY_DRWDOT', 'GOKWORKS_LIVE_COMPANY_SLDDRT',
                                         'GOKWORKS_LIVE_COMPANY_BOM')),
    Scenario('holed_plate_wizard', 'Hole Wizard delikli plaka', 'GOKWORKS_LIVE_HOLED_PLATE_WIZARD',
             dict(flat_pattern=False, bom=False)),
    Scenario('bored_shaft_section', 'İç kademeli mil kesiti', 'GOKWORKS_LIVE_BORED_SHAFT_SECTION',
             dict(flat_pattern=False, bom=False)),
    Scenario('small_radius_detail', 'Küçük radyüs detay görünüşü', 'GOKWORKS_LIVE_SMALL_RADIUS_DETAIL',
             dict(flat_pattern=False, bom=False, manual_scale=1.)),
)


def folder_digest(path):
    """sha256 of every file next to the fixture (assembly components live there too)."""
    folder = Path(path).parent
    digests = {}
    for item in sorted(folder.rglob('*')):
        if item.is_file() and not item.name.startswith('~$'):
            digests[str(item.relative_to(folder))] = hashlib.sha256(item.read_bytes()).hexdigest()
    return digests


def missing_requirements(scenario, environ=os.environ):
    """Why the scenario cannot run here (empty when it can)."""
    reasons = []
    if os.name != 'nt':
        reasons.append('Windows değil')
    for name in (scenario.env, *scenario.extra_env):
        value = environ.get(name)
        if not value:
            reasons.append(f'{name} tanımlı değil')
        elif name != 'GOKWORKS_LIVE_ASSEMBLY_CONFIGURATION' and not Path(value).is_file():
            reasons.append(f'{name} dosyası yok: {value}')
    if scenario.key != 'company_templates' and not environ.get(TEMPLATE_ENV):
        reasons.append(f'{TEMPLATE_ENV} tanımlı değil')
    return reasons


def options_for(scenario, output_dir, environ=os.environ):
    from .models import Options
    values = dict(output_dir=str(output_dir), pdf=True, geometry_dimensions=False, **scenario.options)
    if scenario.key == 'company_templates':
        values.update(template=environ['GOKWORKS_LIVE_COMPANY_DRWDOT'], sheet_format=environ['GOKWORKS_LIVE_COMPANY_SLDDRT'],
                      bom_template=environ['GOKWORKS_LIVE_COMPANY_BOM'])
    else:
        values['template'] = environ[TEMPLATE_ENV]
    return Options(**values)


def check(scenario, result, environ=os.environ):
    """Problems in a REAL result for this scenario (empty list = accepted)."""
    problems = []
    outputs = result.outputs or {}
    def published():
        for kind in ('slddrw', 'pdf'):
            path = outputs.get(kind)
            if not path or not Path(path).is_file():
                problems.append(f'{kind} çıktısı yok')
        if outputs.get('pdf') and Path(outputs['pdf']).is_file() and not Path(outputs['pdf']).read_bytes().startswith(b'%PDF-'):
            problems.append('PDF dosyası PDF değil')
    if scenario.expect_failure:
        if result.status != 'FAIL':
            problems.append(f'eksik referans engellenmedi (durum {result.status})')
        if not result.findings:
            problems.append('engelleme nedeni bildirilmedi')
        if outputs.get('slddrw') and Path(outputs['slddrw']).exists():
            problems.append('eksik referansla resim yayımlandı')
        return problems
    if result.status not in ('PASS', 'WARNING'):
        problems.append(f'durum {result.status}: ' + '; '.join(f.text for f in result.findings[:5]))
        return problems
    published()
    info = result.analysis
    if not result.sheets:
        problems.append('pafta kaydı yok')
    expected = [role for sheet in result.sheets for role in sheet.get('expected', ())]
    if scenario.key == 'stepped_shaft' and getattr(info, 'classification', '') != 'shaft':
        problems.append(f'mil olarak sınıflanmadı ({getattr(info, "classification", "?")})')
    if scenario.key == 'holed_plate' and getattr(info, 'classification', '') not in ('plate', 'block'):
        problems.append(f'plaka olarak sınıflanmadı ({getattr(info, "classification", "?")})')
    if scenario.key == 'holed_plate_wizard':
        groups = [row for row in result.measurements.get('holes', ()) if row.get('source') == 'Hole Wizard']
        saved = [annotation for sheet in result.sheets for annotation in sheet.get('annotations', ())]
        saved += [dimension for sheet in result.sheets for dimension in sheet.get('dimensions', ())]
        if (not groups or not all(row.get('view') and row.get('annotated_count') == row.get('count') for row in groups)
                or not any(row.get('annotation_kind') in ('hole_callout', 'wizard_note', 'hole_table') for row in saved)):
            problems.append('Tüm Hole Wizard delikleri kayıtlı görünüşte delik bilgisi veya tablosuyla doğrulanamadı')
    if scenario.key in ('bored_shaft_section', 'small_radius_detail'):
        role, label = ('section', 'A') if scenario.key == 'bored_shaft_section' else ('detail', 'B')
        view = next((v for sheet in result.sheets for v in sheet.get('views', ()) if v['role'] == role), None)
        if view is None or not view.get('parent') or view.get('label') not in (label, f'{label}-{label}'):
            problems.append('Kayıtlı kesit A-A veya detay B görünüşü ve ana görünüş bağı doğrulanamadı')
        elif role == 'detail' and view.get('view_scale') not in (2., 5., 10.):
            problems.append('Detay büyütme ölçeği beklenen 2:1, 5:1 veya 10:1 değerlerinden biri değil')
    if scenario.key == 'single_body_sheet':
        if getattr(info, 'sheet_body_count', 0) != 1:
            problems.append('tek sac gövdesi okunmadı')
        if 'flat' not in expected:
            problems.append('açınım görünüşü yok')
    if scenario.key == 'multibody_sheet':
        rows = getattr(info, 'sheet_bodies', [])
        pages = [s for s in result.sheets if s.get('expected') == ['flat']]
        if getattr(info, 'sheet_body_count', 0) < 2 or len(pages) != len(rows):
            problems.append('her sac gövdesi için ayrı açınım paftası yok')
    if scenario.key.startswith('assembly') or scenario.key == 'company_templates':
        if scenario.key != 'company_templates' and getattr(info, 'kind', '') != 'assembly':
            problems.append('montaj olarak okunmadı')
        # The BOM is a table on its own sheet (whose only view role is 'main'); bom_page records
        # its native rows, read back again from the saved drawing by verify_saved.
        if not ((getattr(result, 'measurements', None) or {}).get('bom') or {}).get('rows'):
            problems.append('BOM tablosu yok')
    if scenario.key == 'assembly_configurations':
        wanted = environ.get('GOKWORKS_LIVE_ASSEMBLY_CONFIGURATION', '')
        if result.source.configuration != wanted:
            problems.append(f'istenen konfigürasyon kullanılmadı ({result.source.configuration!r} ≠ {wanted!r})')
    if scenario.key == 'assembly_suppressed_component':
        stack, suppressed = [getattr(info, 'tree', None)], 0
        while stack:
            node = stack.pop()
            if node is None:
                continue
            suppressed += node.state == 'suppressed'
            stack.extend(node.children)
        if not suppressed:
            problems.append('bastırılmış bileşen ağaçta görünmüyor')
    return problems


def solidworks_running():
    """A running SolidWorks in the Running Object Table; never starts one."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:
            pythoncom.GetActiveObject('SldWorks.Application')
            return True
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        return False


def run_scenario(scenario, output_root, environ=os.environ, *, generate=None):
    """One scenario → report row. ``generate`` is the production pipeline unless given."""
    row = dict(key=scenario.key, title=scenario.title, fixture=environ.get(scenario.env, ''))
    reasons = missing_requirements(scenario, environ)
    if reasons:
        return dict(row, status=NOT_RUN, reason='; '.join(reasons))
    if generate is None:
        # generate() reports a missing session as a FAIL result, not an exception: without this
        # check every scenario would 'fail' and the missing-reference one would falsely pass.
        if not solidworks_running():
            return dict(row, status=NOT_RUN, reason='Çalışan SolidWorks oturumu bulunamadı.')
        from .pipeline import generate
    from .models import Source
    source = environ[scenario.env]
    configuration = environ.get('GOKWORKS_LIVE_ASSEMBLY_CONFIGURATION', '') if scenario.key == 'assembly_configurations' else ''
    output = Path(output_root)/scenario.key; output.mkdir(parents=True, exist_ok=True)
    before = folder_digest(source)
    started = time.monotonic()
    try:
        results = generate([Source(source, configuration)], options_for(scenario, output, environ), SimpleQueue(), Event())
    except Exception as error:          # e.g. no running SolidWorks: not run, not a CAD verdict
        return dict(row, status=NOT_RUN, reason=f'SolidWorks oturumu kullanılamadı: {type(error).__name__}: {error}')
    after = folder_digest(source)
    problems = []
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    if changed:
        problems.append('kaynak klasörde dosya değişti: ' + ', '.join(changed[:10]))
    if len(results) != 1:
        problems.append(f'{len(results)} sonuç döndü, 1 bekleniyordu')
    else:
        problems.extend(check(scenario, results[0], environ))
    result = results[0] if results else None
    return dict(row, status=FAILED if problems else PASSED, problems=problems, elapsed_s=round(time.monotonic()-started, 2),
                drawing_status=getattr(result, 'status', ''), api_revision=getattr(result, 'api_revision', ''),
                outputs=getattr(result, 'outputs', {}),
                findings=[dict(severity=f.severity, code=f.code, text=f.text) for f in getattr(result, 'findings', [])])


def run(output_root, environ=os.environ, *, generate=None):
    rows = [run_scenario(s, output_root, environ, generate=generate) for s in SCENARIOS]
    return dict(kind='GOKWORKS automatic drawing REAL SolidWorks acceptance', platform=platform.platform(),
                python=sys.version.split()[0], scenarios=rows,
                summary={status: sum(r['status'] == status for r in rows) for status in (PASSED, FAILED, NOT_RUN)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--report', default='automatic-drawing-live-acceptance.json')
    parser.add_argument('--output', default='automatic-drawing-live-output')
    args = parser.parse_args(argv)
    report = run(args.output)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for row in report['scenarios']:
        print(f"{row['status']:>15}  {row['title']}" + (f" — {row.get('reason')}" if row.get('reason') else '')
              + ''.join(f'\n{"":>17}• {p}' for p in row.get('problems', [])))
    return 1 if report['summary'][FAILED] else 0


if __name__ == '__main__':
    raise SystemExit(main())
