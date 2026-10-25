"""Serialized, cancellable exports with validation before atomic publication."""

from pathlib import Path
import time
from uuid import uuid4

from .api import Session, RestoreError
from .formats import BY_KEY
from .models import Outcome, Source, Cancelled, checkpoint
from .naming import Destinations, publish
from .scanner import identity, path_key
from .validation import validate_output


def convert(sources, options, events, stop=None, *, session_factory=Session):
    """COM objects stay in this worker; events contain only Python values.

    A synchronous SaveAs is allowed to finish. Cancellation discards its
    unpublished temporary output, restores state and never starts a new item.
    """
    summary = dict(state='completed', total=0, processed=0, succeeded=0,
                   warned=0, skipped=0, failed=0, error='')
    destinations = Destinations(options, sources)
    seen = set()
    completed_rows = []

    def emit(row):
        row = row.row()
        completed_rows.append(row)
        summary['processed'] += 1
        summary['total'] = max(summary['total'], summary['processed'])
        summary[{'success': 'succeeded', 'partial': 'warned', 'skipped': 'skipped', 'error': 'failed'}[row['status']]] += 1
        events.put(('cad_result', row))
        events.put(('cad_counts', dict(summary)))
        events.put(('progress', (summary['processed'], summary['total'])))

    def issue(source, configuration, detail, *, status='error', error=None):
        for key in options.formats:
            fmt = BY_KEY[key]
            emit(Outcome(source.path, configuration, fmt.label, status, detail,
                         errors=getattr(error, 'errors', 0), warnings=getattr(error, 'warnings', 0), protocol=fmt.protocol))

    def export_one(session, model, source, configuration, key, dependency_notes=()):
        checkpoint(stop)
        unique = (identity(source.path), configuration, key)
        if unique in seen: return
        seen.add(unique)
        fmt = BY_KEY[key]
        start = time.monotonic()
        target = None; temporary = None
        try:
            target = destinations.path(source, configuration, fmt)
            if target.exists():
                if not target.is_file(): raise ValueError('Çıktı yolu bir dosya değil.')
                if not options.overwrite:
                    emit(Outcome(source.path, configuration, fmt.label, 'skipped',
                                 'Çıktı zaten var; değiştirilmedi.', str(target), protocol=fmt.protocol))
                    return
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name('.gokworks-' + uuid4().hex + fmt.extension)
            events.put(('cad_current', dict(source=source.path, configuration=configuration,
                                           format=fmt.label, output=str(target))))
            with session.preferences(fmt, options):
                errors, warnings = session.save(model, temporary, fmt)
                checkpoint(stop)
                size = validate_output(temporary, key, stop=stop)
            checkpoint(stop)
            try:
                publish(temporary, target, options.overwrite)
            except FileExistsError:
                emit(Outcome(source.path, configuration, fmt.label, 'skipped',
                             'Aktarım sırasında aynı isimli çıktı oluştu; üzerine yazılmadı.', str(target), protocol=fmt.protocol))
                return
            detail = 'Dosya yapısı doğrulandı; geometrik eşdeğerlik testi yapılmadı.'
            open_warnings = getattr(session, 'load_warnings', {}).get(path_key(source.path), 0)
            if key.startswith('stl_'): detail += f' Mesh · {options.stl_unit}; montaj gövdeleri tek dosyada.'
            if fmt.protocol == 242: detail += ' MBD yayınlama API’si başarılı; PMI içeriğinin eksiksizliği ayrıca doğrulanmalıdır.'
            if warnings: detail += f' SolidWorks kaydetme uyarısı: {warnings}.'
            if open_warnings: detail += f' SolidWorks açma uyarısı: {open_warnings}.'
            if dependency_notes: detail += ' ' + ' '.join(dependency_notes)
            emit(Outcome(source.path, configuration, fmt.label, 'partial' if warnings or open_warnings or dependency_notes else 'success', detail,
                         str(target), size, time.monotonic() - start, errors, warnings, fmt.protocol, open_warnings))
        except (Cancelled, RestoreError):
            raise
        except Exception as error:
            emit(Outcome(source.path, configuration, fmt.label, 'error', str(error),
                         str(target or ''), seconds=time.monotonic() - start,
                         errors=getattr(error, 'errors', 0), warnings=getattr(error, 'warnings', 0), protocol=fmt.protocol))
        finally:
            model = None
            if temporary is not None:
                try: temporary.unlink(missing_ok=True)
                except OSError as error:
                    raise RestoreError('Geçici CAD çıktısı temizlenemedi; işlem durdu: ' + str(temporary)) from error

    def components(session, model, source):
        targets = []
        entries = (); component = None
        try:
            entries = session.components(model)
            for component in entries:
                checkpoint(stop)
                name, path, configuration, state = session.component(component)
                if state == 'suppressed':
                    issue(Source(path or name), configuration, 'Bastırılmış bileşen; montaj durumuna uygun olarak aktarılmadı.', status='skipped')
                    continue
                if state in ('virtual', 'mismatch') or not path or not configuration or not Path(path).is_file():
                    messages = {'virtual': 'Sanal bileşenin bağımsız dosyası yok; SolidWorks’te haricî parça olarak kaydedin.',
                                'mismatch': 'Bileşen kimliği montaj referansıyla uyuşmuyor.'}
                    issue(Source(path or name), configuration, name + ': ' + messages.get(state, 'Kaynak dosya veya referans konfigürasyonu bulunamadı.'))
                    continue
                suffix = Path(path).suffix.casefold()
                if suffix == '.sldasm' and not options.include_subassemblies: continue
                if suffix not in ('.sldprt', '.sldasm'):
                    issue(Source(path), configuration, 'Bileşen yerel bir SolidWorks parça/montaj dosyası değil.'); continue
                root = source.root if source.root and Path(path).resolve().is_relative_to(Path(source.root).resolve()) else ''
                targets.append((Source(str(Path(path).resolve()), root), configuration))
            return sorted(set(targets), key=lambda t: (t[0].path.casefold(), t[1]))
        finally:
            model = component = None
            entries = ()

    def process(session, source, forced=None):
        checkpoint(stop)
        model = None
        try:
            if Path(source.path).suffix.casefold() not in ('.sldprt', '.sldasm'):
                raise ValueError('3D dönüştürücü yalnız SLDPRT ve SLDASM modellerini aktarır.')
            model = session.document(source.path)
            configurations = forced or session.configurations(model, options)
            for configuration in configurations:
                checkpoint(stop)
                with session.configuration(model, configuration):
                    if forced is None and options.assembly_mode == 'components' and session.is_assembly(model):
                        # Collect only plain paths/configurations before releasing the
                        # assembly. Referenced configurations override the root policy.
                        targets = components(session, model, source)
                    else:
                        notes = session.dependencies(model) or ()
                        for key in options.formats: export_one(session, model, source, configuration, key, notes)
                        targets = []
                for child, child_configuration in targets:
                    if all((identity(child.path), child_configuration, key) in seen for key in options.formats): continue
                    process(session, child, (child_configuration,))
        except (Cancelled, RestoreError):
            raise
        except Exception as error:
            issue(source, (forced or ('',))[0], str(error), error=error)
        finally:
            model = None
            session.release(source.path)

    try:
        options.validate()
        if not sources: raise ValueError('Önce SLDPRT veya SLDASM dosyası ekleyin.')
        checkpoint(stop)
        events.put(('phase', 'SolidWorks’e bağlanılıyor; kaynak dosyalar kaydedilmeyecek…'))
        with session_factory() as session:
            for source in sources:
                checkpoint(stop)
                process(session, source)
    except Cancelled:
        summary['state'] = 'cancelled'
    except Exception as error:
        summary.update(state='error', error=str(error))
        events.put(('log', str(error)))
    finally:
        summary['total'] = summary['processed']
        events.put(('cad_done', dict(summary)))
    return completed_rows


def inspect_configurations(sources, events, stop=None, *, session_factory=Session):
    """Populate a selectable configuration list without carrying CAD pointers."""
    from .models import Options
    with session_factory() as session:
        for source in sources:
            checkpoint(stop)
            model = None
            try:
                model = session.document(source.path)
                names = session.configurations(model, Options('.', configurations='all'))
                events.put(('cad_configurations', dict(source=source.path, names=list(names))))
            finally:
                model = None
                session.release(source.path)
