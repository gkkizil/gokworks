"""File-by-file DXF import: one bad source never hides the rest of a selection."""

from pathlib import Path
from dataclasses import replace

from modules.nesting.dxf_import import read_dxf, MissingUnits
from modules.nesting.import_plan import normalize_options


class ContourReview(Exception):
    def __init__(self, detail, signature):
        self.detail, self.signature = detail, signature


def import_batch(entries, options, sink, stop, *, existing_quantity=0):
    """Emit each result immediately; imported CAD objects never cross this API."""
    summary = dict(selected=len(entries), ready=0, errors=0, cancelled=0, parts=0, reviews=0)
    total_quantity = existing_quantity
    for index, entry in enumerate(entries, 1):
        source = entry['source']; key = entry['id']
        if stop.is_set():
            sink.put(('nest_file', dict(id=key, status='cancelled', detail='Okuma durduruldu; yeniden deneyebilirsiniz.', parts=[])))
            summary['cancelled'] += 1
            continue
        sink.put(('nest_file', dict(id=key, status='running', detail='Konturlar okunuyor…', parts=[])))
        if hasattr(sink,'flush'): sink.flush()
        try:
            file_options = normalize_options({**options, **entry.get('options',{})})
            if Path(source).suffix.lower()=='.dwg':
                from .dwg_import import read_dwg
                parts = read_dwg(source,stop=stop,**file_options)
            else:
                parts = read_dxf(source, stop=stop, **file_options)
            if not parts:
                raise ValueError('Kapalı kesim parçası bulunamadı.')
            code = entry.get('part_code')
            if code:
                parts = [replace(part,code=code+(f'-{i:02d}' if len(parts)>1 else '')) for i,part in enumerate(parts,1)]
            review = dict(sha256=parts[0].source_sha256, count=len(parts), quantity=file_options['quantity'])
            if len(parts)>1 and not file_options['grouped'] and entry.get('contour_approval') != review:
                detail = (f"{len(parts)} bağımsız parça bulundu. Her parçaya {file_options['quantity']} adet uygulanır: "
                          f"toplam {sum(p.quantity for p in parts)} kesim parçası. Adet dağılımını onaylamak veya "
                          'konturları tek grup yapmak için çift tıklayın. Delikler bu sayıya dahil değildir.')
                raise ContourReview(detail,review)
            next_total = total_quantity-entry.get('replace_quantity',0)+sum(p.quantity for p in parts)
            if next_total > 10000:
                raise ValueError('Bir projede en fazla 10000 parça örneği desteklenir; bu dosyanın adetlerini azaltın.')
            if stop.is_set(): raise InterruptedError
        except ContourReview as review:
            sink.put(('nest_file', dict(id=key,status='review',detail=review.detail,parts=[],contour_review=review.signature)))
            summary['reviews'] += 1
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
            total_quantity = next_total
        sink.put(('nest_progress', (index, len(entries), f'{index}/{len(entries)} dosya · {Path(source).name}')))
        if hasattr(sink,'flush'): sink.flush()
    sink.put(('nest_import_done', summary))
