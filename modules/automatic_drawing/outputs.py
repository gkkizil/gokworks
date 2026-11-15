"""No-clobber drawing packages, same-folder staging and source fingerprints."""

import json
import os
from pathlib import Path
import re
import string
from tempfile import mkstemp
import uuid

from shared.files import write_text_atomic


class ExistingOutput(RuntimeError):
    pass


def fingerprint(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .')
    value = re.sub(r'\s+', ' ', value)[:140].rstrip(' .')
    if not value:
        value = 'Teknik-resim'
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
            *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        value = '_' + value
    return value


def output_stem(info, pattern):
    fields = {'name': Path(info.source.path).stem, 'configuration': info.source.configuration,
              'part_number': info.properties.get('PartNumber', '')}
    for _, field, spec, conversion in string.Formatter().parse(pattern):
        if field is not None and (field not in fields or spec or conversion):
            raise ValueError('Dosya adı yalnız {name}, {configuration}, {part_number} alanlarını kullanabilir.')
    return safe_name(pattern.format(**fields).rstrip('-_ '))


def _existing(folder, stem, suffixes):
    wanted = {(stem+s).casefold() for s in suffixes}
    return any(p.name.casefold() in wanted for p in folder.iterdir())


class OutputTransaction:
    """Stage in the FINAL folder, so relative model reference bases do not move.

    SLDDRW is always the primary deliverable. Optional exports and a JSON report
    form one package. Publication never replaces an existing file, including a
    file another process creates after the first existence check.
    """

    def __init__(self, info, options):
        self.info, self.options = info, options
        self.folder = Path(options.output_dir or Path(info.source.path).parent).resolve()
        self.staged, self.targets, self.published = {}, {}, {}
        self.lock = None
        self.suffixes = {'slddrw': '.SLDDRW', 'report': '.drawing.json'}
        if options.pdf: self.suffixes['pdf'] = '.pdf'
        if options.dxf: self.suffixes['dxf'] = '.dxf'

    def __enter__(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        stem = output_stem(self.info, self.options.naming)
        for number in range(10000):
            candidate = stem if not number else f'{stem}-{number:02d}'
            if _existing(self.folder, candidate, self.suffixes.values()):
                if self.options.existing == 'skip':
                    raise ExistingOutput('Mevcut çıktı atlandı: ' + candidate)
                continue
            lock = self.folder / ('.'+candidate+'.gokworks-drawing.lock')
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if self.options.existing == 'skip':
                    raise ExistingOutput('Bu çıktı başka bir işlemde hazırlanıyor: ' + candidate)
                continue
            self.lock = lock
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(json.dumps({'source': self.info.source.path,
                                             'configuration': self.info.source.configuration}))
            except BaseException:
                try: os.close(fd)
                except OSError: pass
                lock.unlink(missing_ok=True); self.lock = None
                raise
            if _existing(self.folder, candidate, self.suffixes.values()):
                lock.unlink(); self.lock = None
                if self.options.existing == 'skip':
                    raise ExistingOutput('Çıktı başka bir işlem tarafından oluşturuldu.')
                continue
            try:
                token = uuid.uuid4().hex
                for kind, suffix in self.suffixes.items():
                    self.targets[kind] = self.folder / (candidate+suffix)
                    fd, temporary = mkstemp(prefix='.gokworks-drawing-'+token+'-', suffix=suffix,
                                            dir=self.folder)
                    os.close(fd)
                    self.staged[kind] = Path(temporary)
                return self
            except BaseException:
                self.__exit__(None, None, None)
                raise
        raise ValueError('Benzersiz çıktı adı üretilemedi.')

    def discard(self, kind):
        path = self.staged.pop(kind, None)
        self.targets.pop(kind, None)
        if path is not None:
            path.unlink(missing_ok=True)

    def write_report(self, result):
        self.staged['report'].write_text(json.dumps(result.as_dict(), ensure_ascii=False,
            indent=2, allow_nan=False), encoding='utf-8')

    def commit(self):
        if 'slddrw' not in self.staged or not self.staged['slddrw'].stat().st_size:
            raise RuntimeError('SLDDRW doğrulanmadan çıktı paketi yayımlanamaz.')
        try:
            # JSON last: a published report never describes an uncommitted drawing.
            for kind in sorted(self.staged, key=lambda k: (k == 'report', k)):
                source, target = self.staged[kind], self.targets[kind]
                if not source.is_file() or not source.stat().st_size:
                    raise RuntimeError('Boş veya eksik çıktı: ' + kind)
                try:
                    os.link(source, target)
                except FileExistsError:
                    raise ExistingOutput('Çıktı işlem sırasında oluşturuldu; üzerine yazılmadı: '+str(target))
                except OSError:
                    if os.name != 'nt':
                        raise
                    # Win32 MoveFile's rename semantics reject existing targets.
                    # This also supports SMB/FAT volumes that cannot hard-link.
                    os.rename(source, target)
                self.published[kind] = fingerprint(target)
                # Clear staged hard-links while publication can still roll back.
                source.unlink(missing_ok=True)
            self.lock.unlink()
            self.lock = None
            return {key: str(value) for key, value in self.targets.items()}
        except BaseException:
            # Remove only the exact files this transaction created.
            for kind, stamp in self.published.items():
                target = self.targets[kind]
                try:
                    if fingerprint(target) == stamp:
                        target.unlink()
                except OSError:
                    pass
            raise

    def __exit__(self, kind, error, tb):
        for path in self.staged.values():
            try: path.unlink(missing_ok=True)
            except OSError: pass  # a native file lock must not erase the real API error
        if self.lock is not None:
            try: self.lock.unlink(missing_ok=True)
            except OSError:
                if error is None:
                    raise
            finally: self.lock = None


def check_file(path, kind):
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 16:
        raise RuntimeError('Çıktı boş veya bulunamadı: '+str(path))
    with path.open('rb') as stream:
        header = stream.read(16)
        if kind == 'pdf':
            if not header.startswith(b'%PDF-'):
                raise RuntimeError('PDF dosya başlığı doğrulanamadı.')
            stream.seek(max(0, path.stat().st_size-2048))
            if b'%%EOF' not in stream.read():
                raise RuntimeError('PDF tamamlanmamış görünüyor.')
        elif kind == 'slddrw' and not header.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
            raise RuntimeError('SLDDRW bileşik belge başlığı doğrulanamadı.')
    if kind == 'dxf':
        import ezdxf
        doc = ezdxf.readfile(path)
        if not doc.modelspace() and not any(len(layout) for layout in doc.layouts):
            raise RuntimeError('DXF içinde görünüş geometrisi bulunamadı.')
        audit = doc.audit()
        if audit.has_errors:
            raise RuntimeError('DXF yapısal denetimi başarısız.')


def write_batch_report(path, results):
    payload = {'schema_version': 1, 'results': [r.as_dict() for r in results],
               'summary': dict((status, sum(r.status == status for r in results))
                               for status in ('PASS', 'WARNING', 'FAIL', 'CANCELLED', 'SKIPPED')),
               'scope': 'PASS temel yapısal doğrulamadır; imalata serbest bırakma onayı değildir.'}
    return write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
