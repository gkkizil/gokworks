"""Sequential, cancellable native drawing jobs on the existing JobManager worker."""

from collections import deque
from contextlib import contextmanager
from dataclasses import replace
import logging
from pathlib import Path
import time

from modules.cad_converter.api import ApiError, RestoreError
from .models import (Cancelled, DrawingResult, Options, Source, STAGES, checkpoint, identity)
from .outputs import ExistingOutput, OutputTransaction, check_file, fingerprint
from .rules import CLASS_TITLES, plan_views, recommendations, unique_sources
from .layout import plan_sheets
from .solidworks import Session, call, error_text
from .native import NativeDrawing
from .manufacturing import flat_page, bom_page

logger = logging.getLogger(__name__)
SOURCE_TYPES = ('.sldprt', '.sldasm')


def fatal(error):
    if isinstance(error, RestoreError):
        return True
    cause = error
    while cause is not None:
        if getattr(cause, 'hresult', None) in (-2147417848, -2147023174, -2147418111, -2147417846):
            return True
        cause = cause.__cause__
    return False


def scan_folder(folder, recursive=True, stop=None):
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Kaynak klasör bulunamadı.')
    paths = root.rglob('*') if recursive else root.iterdir()
    found = {}
    for path in paths:
        checkpoint(stop)
        if path.suffix.casefold() in SOURCE_TYPES and path.is_file() and not path.name.startswith('~$'):
            resolved = str(path.resolve())
            found.setdefault(identity(resolved), Source(resolved))
    return sorted(found.values(), key=lambda s: s.key)


def resolve_template(session, options):
    template = options.template or str(call(session.app, 'GetUserPreferenceStringValue',
                                          session.c('swDefaultTemplateDrawing')) or '')
    if not template or Path(template).suffix.casefold() != '.drwdot' or not Path(template).is_file():
        raise ValueError('SolidWorks Drawing şablonu bulunamadı. Bir .DRWDOT seçin veya '
                         'SolidWorks varsayılan teknik resim şablonunu ayarlayın.')
    return str(Path(template).resolve())


class Progress:
    def __init__(self, result, events, stop):
        self.result, self.events, self.stop = result, events, stop

    @contextmanager
    def phase(self, index):
        checkpoint(self.stop)
        self.result.stage = STAGES[index]
        self.events.put(('drawing_progress', dict(source=self.result.source, stage=STAGES[index],
                          completed=len(self.result.completed_stages), total=len(STAGES))))
        yield
        self.result.completed_stages.append(STAGES[index])
        self.events.put(('drawing_progress', dict(source=self.result.source, stage=STAGES[index],
                          completed=len(self.result.completed_stages), total=len(STAGES))))


def _tree_problems(root):
    if root is None:
        return []
    problems, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.state not in ('ready', 'hidden', 'suppressed'):
            problems.append(node.name+': '+node.detail)
        stack.extend(node.children)
    return problems


def generate_one(session, source, options, events, stop, *, native_factory=NativeDrawing):
    """A mockable orchestration boundary; the production factory is native COM only."""
    result = DrawingResult(source, api_revision=session.revision)
    progress = Progress(result, events, stop)
    started = time.monotonic()
    model = native = None
    try:
        with progress.phase(0):
            options.validate()
            session.assert_thread()
        with progress.phase(1):
            model = session.source(source)
            session.source_ready(model)
            configuration = source.configuration or session.active_configuration(model)
            source = Source(str(call(model, 'GetPathName')), configuration)
            result.source = source
            stamp = fingerprint(source.path)
        with session.configuration(model, configuration):
            with progress.phase(2):
                info = session.inspect(model, source, stop)
                result.analysis = info
                for note in info.warnings:
                    result.warn('analysis', note)
        with progress.phase(3):
            if options.classification != 'auto':
                if options.classification not in CLASS_TITLES or options.classification == 'assembly':
                    raise ValueError('Geçersiz parça sınıflandırması.')
                if info.kind == 'part':
                    info.classification = options.classification
                    info.classification_reason = 'Kullanıcının seçtiği sınıf.'
            problems = _tree_problems(info.tree)
            if problems and options.bom:
                raise ApiError('Montaj ağacı eksiksiz çözümlenemedi; BOM doğrulanamaz. '+'; '.join(problems[:20]))
            for problem in problems:
                result.warn('assembly_reference', problem)
        with progress.phase(4):
            plans = plan_sheets(plan_views(info, options), options)
            plan = plans[0]
        with progress.phase(5):
            template = resolve_template(session, options)
        with OutputTransaction(info, options) as transaction:
            # Restore the source BEFORE committing a successful package/report.
            with session.configuration(model, configuration):
                memory_stamp = session.memory_stamp(model)
                if memory_stamp is None:
                    result.warn('memory_stamp', 'Kaynağın bellek güncelleme damgası okunamadı; '
                                'işlem sırasında SolidWorks’te kaynak düzenlenmediğini kontrol edin.')
                native = native_factory(session, info, options, result, stop)
                with progress.phase(6):
                    native.create(template, plan)
                with progress.phase(7):
                    for index, page in enumerate(plans):
                        if index:
                            native.setup(page, new=True)
                        native.create_views(page)
                        native.fit(page.name)
                with progress.phase(8):
                    native.import_dimensions(plan.name)
                    count_before = len(native.dimensions(plan.name))
                    result.measurements['model_dimensions_imported'] = count_before
                    if options.model_dimensions and not count_before:
                        result.warn('no_model_dimensions', 'Aktarılabilir model ölçüsü bulunamadı. '
                                    'Modelde resme işaretli ölçüleri kontrol edin veya geometrik referans ölçülerini seçin.')
                with progress.phase(9):
                    native.geometry_dimensions(plan.name)
                    count_after = len(native.dimensions(plan.name))
                    result.measurements['geometry_dimensions_created'] = max(0, count_after-count_before)
                with progress.phase(10):
                    for page in plans:
                        native.arrange_dimensions(page.name)
                        native.fit(page.name, include_dimensions=True)
                with progress.phase(11):
                    native.center_marks(plan.name)
                    flat_page(native, model)
                    bom_page(native)
                    native.title_properties()
                    for note in recommendations(info):
                        result.warn('engineering_review', note)
                with progress.phase(12):
                    native.rebuild()
                with progress.phase(13):
                    findings, snapshots = native.validate()
                    result.findings.extend(findings)
                    result.sheets = snapshots
                    if any(f.severity == 'FAIL' for f in findings):
                        raise ApiError('Teknik resim yapısal doğrulamayı geçemedi; çıktı yayımlanmadı.')
                with progress.phase(14):
                    native.save(transaction.staged['slddrw'], 'slddrw')
                with progress.phase(15):
                    for kind in ('pdf', 'dxf'):
                        if kind not in transaction.staged:
                            continue
                        checkpoint(stop)
                        if kind == 'dxf' and len(snapshots) != 1:
                            result.warn('multipage_dxf', 'Çok paftalı resim DXF’e tek pafta olarak aktarılmadı. '
                                        'Tüm paftalar SLDDRW / PDF içinde korundu.')
                            transaction.discard(kind)
                            continue
                        native.save(transaction.staged[kind], kind)
                        check_file(transaction.staged[kind], kind)
                with progress.phase(16):
                    native.close()
                    check_file(transaction.staged['slddrw'], 'slddrw')
                    findings, reread = native.verify_saved(transaction.staged['slddrw'], snapshots)
                    # The saved/reopened geometry is the delivered evidence.
                    result.findings = [f for f in result.findings if f not in findings]
                    result.findings.extend(findings)
                    result.sheets = reread
                    if any(f.severity == 'FAIL' for f in findings):
                        raise ApiError('Kaydedilen SLDDRW yeniden açılıp doğrulanamadı.')
                # Flat-pattern creation may switch the native model configuration;
                # its read-only file/configuration checks remain mandatory.
                if not result.measurements.get('flat_pattern') and memory_stamp is not None:
                    if session.memory_stamp(model) != memory_stamp:
                        raise ApiError('Kaynak modelin bellekteki geometrisi işlem sırasında değişti; çıktı yayımlanmadı.')
            if fingerprint(source.path) != stamp:
                raise ApiError('Kaynak dosya işlem sırasında değişti; çıktı paketi yayımlanmadı.')
            with progress.phase(17):
                result.classify()
                result.elapsed_s = time.monotonic()-started
                result.outputs = {k: str(v) for k, v in transaction.targets.items()}
                # Include the final completed phase in the persisted ledger.
                persisted = replace(result, completed_stages=[*result.completed_stages, STAGES[17]])
                transaction.write_report(persisted)
                result.outputs = transaction.commit()
        return result
    except ExistingOutput as error:
        result.status = 'SKIPPED'
        result.warn('existing_output', str(error))
        return result
    except Cancelled:
        result.status = 'CANCELLED'
        result.warn('cancelled', 'İşlem iptal edildi; doğrulanmamış paket yayımlanmadı.')
        return result
    except Exception as error:
        logger.exception('Native drawing failed at %s for %s', result.stage, source.path)
        result.fail('pipeline', f'{result.stage}: {error_text(error)}')
        result.status = 'FAIL'
        result.outputs = {}
        if fatal(error):
            # Carry only plain data to the outer queue; no COM exception escapes the STA.
            result.measurements['stop_batch'] = True
        return result
    finally:
        if native is not None:
            try:
                native.close()
            except Exception as error:
                result.fail('cleanup', 'Oluşturulan teknik resim kapatılamadı: '+str(error))
                result.status = 'FAIL'
                result.measurements['stop_batch'] = True
        result.elapsed_s = time.monotonic()-started
        model = native = None


def analyze(sources, events, stop, *, session_factory=Session):
    with session_factory() as session:
        for source in sources or (None,):
            checkpoint(stop)
            model = None
            try:
                model = session.source(source)
                configuration = source.configuration if source and source.configuration else session.active_configuration(model)
                with session.configuration(model, configuration):
                    info = session.inspect(model, Source(str(call(model, 'GetPathName')), configuration), stop)
                events.put(('drawing_analysis', info))
            except Cancelled:
                events.put(('drawing_notice', 'Analiz kullanıcı tarafından durduruldu.'))
                return
            except Exception as error:
                events.put(('drawing_analysis_error', {'source': source, 'error': error_text(error)}))
                if fatal(error):
                    return
            finally:
                if model is not None:
                    path = str(call(model, 'GetPathName') or '')
                    model = None
                    if path: session.release(path)


def generate(sources, options, events, stop, *, session_factory=Session, native_factory=NativeDrawing):
    """One session/STA, unique file+configuration jobs, per-file failure isolation."""
    options.validate()
    queue = deque(sources)
    seen, results = set(), []
    try:
        with session_factory() as session:
            while queue:
                if stop.is_set():
                    events.put(('drawing_notice', f'İşlem durduruldu; {len(queue)} iş çalıştırılmadı.'))
                    break
                source = queue.popleft()
                if source.key in seen:
                    continue
                seen.add(source.key)
                result = generate_one(session, source, options, events, stop, native_factory=native_factory)
                results.append(result)
                if result.analysis is not None:
                    seen.add(result.analysis.source.key)
                events.put(('drawing_result', result))
                if result.measurements.get('stop_batch'):
                    events.put(('drawing_notice', 'SolidWorks bağlantısı / kaynak durumu güvenle geri alınamadı; '
                                'toplu işlem durduruldu.'))
                    break
                if result.analysis is not None and result.analysis.tree is not None and options.assembly_scope != 'assembly':
                    mode = 'all' if options.assembly_scope == 'all' else 'parts'
                    queue.extend(s for s in unique_sources(result.analysis.tree.children, mode) if s.key not in seen)
                # Keep user-open documents; close only files opened by this session.
                session.release(result.source.path)
    except Cancelled:
        events.put(('drawing_notice', 'İşlem kullanıcı tarafından durduruldu.'))
    except Exception as error:
        logger.exception('Drawing batch session failed')
        events.put(('drawing_notice', 'SolidWorks oturum hatası: '+error_text(error)))
        if not results:
            for source in sources:
                result = DrawingResult(source)
                result.fail('session', str(error))
                results.append(result)
                events.put(('drawing_result', result))
    events.put(('drawing_done', results))
    return results


def worker(kind, sources=(), options=None, folder=None, recursive=True):
    """Only plain source/options values are captured by the Qt worker closure."""
    sources = tuple(sources)
    def run(events, stop):
        if kind == 'folder':
            events.put(('drawing_sources', scan_folder(folder, recursive, stop)))
        elif kind == 'analyze':
            analyze(sources, events, stop)
        elif kind == 'generate':
            generate(sources, options or Options(), events, stop)
        else:
            raise ValueError('Geçersiz teknik resim işlemi.')
    return run
