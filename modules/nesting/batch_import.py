"""File-by-file DXF import: one bad source never hides the rest of a selection."""

from pathlib import Path

from modules.nesting.dxf_import import read_dxf, MissingUnits


def import_batch(entries, options, sink, stop):
    """Emit each result immediately; imported CAD objects never cross this API."""
    summary = dict(selected=len(entries), ready=0, errors=0, cancelled=0, parts=0)
    for index, entry in enumerate(entries, 1):
        source = entry['source']; key = entry['id']
        if stop.is_set():
            sink.put(('nest_file', dict(id=key, status='cancelled', detail='Okuma durduruldu; yeniden deneyebilirsiniz.', parts=[])))
            summary['cancelled'] += 1
            continue
        sink.put(('nest_file', dict(id=key, status='running', detail='Konturlar okunuyor…', parts=[])))
        if hasattr(sink,'flush'): sink.flush()
        try:
            parts = read_dxf(source, stop=stop, **options)
            if not parts:
                raise ValueError('Kapalı kesim parçası bulunamadı.')
        except InterruptedError:
            sink.put(('nest_file', dict(id=key, status='cancelled', detail='Okuma durduruldu; yeniden deneyebilirsiniz.', parts=[])))
            summary['cancelled'] += 1
        except MemoryError:
            raise
        except Exception as error:
            # ezdxf.DXFError is NOT a ValueError/OSError. Treat parser, encoding,
            # geometry and other per-file exceptions as source-specific failures.
            detail = str(error).strip() or type(error).__name__
            if isinstance(error, MissingUnits):
                detail += ' Dosyaya çift tıklayıp mm, cm veya inch seçerek yeniden okuyun.'
            else:
                detail += ' Ayrıntı ve yeniden denemek için dosyaya çift tıklayın.'
            sink.put(('nest_file', dict(id=key, status='error', detail=detail, parts=[])))
            summary['errors'] += 1
        else:
            sink.put(('nest_file', dict(id=key, status='success', detail=f'{len(parts)} parça okundu.', parts=parts)))
            summary['ready'] += 1; summary['parts'] += len(parts)
        sink.put(('nest_progress', (index, len(entries), f'{index}/{len(entries)} dosya · {Path(source).name}')))
        if hasattr(sink,'flush'): sink.flush()
    sink.put(('nest_import_done', summary))
