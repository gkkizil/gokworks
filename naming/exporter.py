"""Plan names and copy a complete, verified Pack and Go package."""

from dataclasses import dataclass
from contextlib import contextmanager
import json
import ntpath
from pathlib import Path, PureWindowsPath
import re

from dxf_dwg import exporter as sw
from solidworks.connection import connect_to_solidworks

pythoncom, win32com = sw.pythoncom, sw.win32com
CAD_TYPES = {'.sldprt': 'Parça', '.sldasm': 'Montaj', '.slddrw': 'Teknik resim'}
REPORT_NAME = 'GOKWORKS-isimlendirme.json'


class Cancelled(Exception):
    pass


class NameCollision(ValueError):
    pass


def _check(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()


def path_key(path):
    return ntpath.normcase(ntpath.normpath(str(path)))


def valid_stem(value):
    value = str(value)
    if not value or value != value.strip() or value.endswith('.') or re.search(r'[<>:"/\\|?*\x00-\x1f]', value):
        raise ValueError('Dosya adı boş olamaz; geçersiz karakter, başta/sonda boşluk veya sonda nokta kullanılamaz.')
    if value in ('.', '..') or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', value, re.I):
        raise ValueError(f'Windows bu dosya adını kullanamaz: {value}')
    return value


def validate_destination(destination, snapshot=None):
    """Accept the selected exact folder only when it can hold a new package."""
    if destination is None or not str(destination).strip():
        raise ValueError('Yeni montajın kaydedileceği hedef klasörü seçin.')
    folder = Path(destination).expanduser().absolute()
    try:
        if folder.exists():
            if not folder.is_dir():
                raise ValueError('Hedef konum bir klasör olmalı.')
            if next(folder.iterdir(), None) is not None:
                raise ValueError('Hedef klasör boş olmalı. Boş veya yeni bir klasör seçin; var olan dosyaların üzerine yazılmaz.')
        elif not folder.parent.is_dir():
            raise ValueError('Hedef klasörün üst klasörü bulunamadı. Mevcut bir konumda yeni klasör seçin.')
        resolved = folder.resolve()
        if snapshot is not None and any(Path(doc.path).resolve().is_relative_to(resolved)
                                        for doc in snapshot.documents):
            raise ValueError('Kaynak dosyaların bulunduğu klasör hedef olarak kullanılamaz. Ayrı bir hedef klasör seçin.')
    except OSError as error:
        raise ValueError(f'Hedef klasöre erişilemiyor: {error}') from error
    return folder


@dataclass(frozen=True)
class Document:
    path: str
    dependencies: tuple
    stamp: tuple

    @property
    def kind(self):
        return CAD_TYPES.get(PureWindowsPath(self.path).suffix.lower(), 'Ek dosya')


@dataclass(frozen=True)
class Snapshot:
    root: str
    documents: tuple
    source_path: str | None = None
    require_assembly: bool = False


@dataclass(frozen=True)
class Rules:
    prefix: str = ''
    suffix: str = ''
    find: str = ''
    replacement: str = ''
    numbered: bool = False
    start: int = 1
    digits: int = 3


@dataclass(frozen=True)
class Entry:
    source: str
    destination: str


def _stamp(path):
    file = Path(path)
    if not file.is_file():
        raise RuntimeError(f'Kaynak dosya bulunamadı: {path}. Sanal parçaları önce dış dosyaya kaydedin.')
    info = file.stat()
    if not info.st_size:
        raise RuntimeError(f'Kaynak dosya boş: {path}')
    return info.st_size, info.st_mtime_ns


def _com_array(values):
    if pythoncom is None or win32com is None:
        return tuple(values)
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, tuple(values))


def _arrays(obj, method_name, count):
    """Support both makepy return tuples and late-bound byref VARIANTs."""
    try:
        # Type-aware dispatch can invoke an output-bearing getter during the
        # attribute lookup itself, before Python ever calls the method.
        method = getattr(obj, method_name)
        result = method()
    except Exception as error:
        code = getattr(error, 'hresult', None)
        if not isinstance(error, TypeError) and code not in (-2147352561, -2147352562, -2147352571):
            raise RuntimeError(f'SolidWorks {method_name} çağrısı başarısız: {error}') from error
        result = True  # Retry a late-bound method with explicit out arguments.
    if isinstance(result, tuple) and len(result) == count+1 and result[0] is True:
        return result[1:]
    if result is True:
        # Cached makepy methods have Python output parameters rather than
        # accepting explicit BYREF VARIANTs. Retry through late-bound dispatch.
        try:
            if hasattr(obj, '_oleobj_'):
                obj = _late_bound(obj, method_name)
            method = getattr(obj, method_name)
            outputs = [win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
                       for _ in range(count)]
            result = method(*outputs)
        except Exception as error:
            raise RuntimeError(f'SolidWorks {method_name} çıkış parametreleri okunamadı: {error}') from error
        if result is True:
            return tuple(out.value for out in outputs)
        if isinstance(result, tuple) and len(result) == count+1 and result[0] is True:
            return result[1:]
    raise RuntimeError(f'SolidWorks {method_name} sonucunu doğrulayamadı.')


def _dependencies(app, path):
    # Search=False reads stored references and never changes SW search folders.
    try:
        values = app.GetDocumentDependencies2(str(path), False, False, False)
    except Exception as error:
        raise RuntimeError(f'SolidWorks GetDocumentDependencies2 referansları okuyamadı ({path}): {error}') from error
    if values is None:
        values = ()
    if not isinstance(values, (tuple, list)) or len(values) % 2:
        raise RuntimeError(f'Dosya referansları okunamadı: {path}')
    paths = tuple(str(value) for value in values[1::2])
    if any(not path or not (ntpath.isabs(path) or Path(path).is_absolute()) for path in paths):
        raise RuntimeError(f'Boş veya göreli dosya referansı var: {path}')
    return paths


def _open_document(app, path):
    """Find a loaded document for ownership and state bookkeeping."""
    try:
        getter = getattr(app, 'GetOpenDocument', None)
        model = getter(str(path)) if getter is not None else None
    except Exception as error:
        raise RuntimeError(f'SolidWorks GetOpenDocument kaynak oturumunu okuyamadı ({path}): {error}') from error
    if model is not None:
        return model
    try:
        return app.GetOpenDocumentByName(str(path))
    except Exception as error:
        raise RuntimeError(f'SolidWorks GetOpenDocumentByName kaynak oturumunu okuyamadı ({path}): {error}') from error


def _out_integer():
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _late_bound(app, *methods):
    if hasattr(app, '_oleobj_'):
        app = win32com.client.dynamic.DumbDispatch(app)
        if methods:
            app._FlagAsMethod(*methods)
    return app


def _configuration(model):
    manager = getattr(model, 'ConfigurationManager', None)
    return sw._value(sw._value(manager, 'ActiveConfiguration'), 'Name') if manager is not None else None


def _activate(app, name):
    errors = _out_integer()
    try:
        model = app.ActivateDoc3(name, False, sw.DONT_REBUILD, errors)
    except Exception as error:
        raise RuntimeError(f'SolidWorks ActivateDoc3 belgeyi etkinleştiremedi ({name}): {error}') from error
    # swDocNeedsRebuildWarning=2 is successful activation without rebuilding.
    if model is None or errors.value not in (0, 2) or path_key(sw._document_name(model)) != path_key(name):
        raise RuntimeError(f'SolidWorks ActivateDoc3 hata kodu: {errors.value}; hedef: {name}')
    return model


@contextmanager
def _source_document(app, source_path, stop=None):
    """Borrow a selected source, or open and close only our own clean root.

    Pack and Go belongs to ModelDocExtension. Use the fresh activation pointer
    for the selected source, including visible documents behind another model.
    Hidden assembly-loaded sources need a temporary own window too.
    """
    _check(stop)
    if source_path is None:
        yield None
        return
    source_path = str(Path(source_path).absolute())
    kind = {'.sldprt': 1, '.sldasm': 2, '.slddrw': 3}.get(PureWindowsPath(source_path).suffix.lower())
    if kind is None:
        raise ValueError('Kaynak olarak bir SolidWorks montaj, parça veya teknik resim dosyası seçin.')
    _stamp(source_path)
    app = _late_bound(app)
    previous = sw._value(app, 'ActiveDoc')
    previous_name = sw._document_name(previous) if previous is not None else None
    model = None
    opened = attempted_open = activated = visibility_changed = False
    original_config = None
    failure = None
    cleanup_errors = []
    try:
        model = _open_document(app, source_path)
        if model is None:
            attempted_open = True
            errors, warnings = _out_integer(), _out_integer()
            try:
                model = app.OpenDoc6(source_path, kind, sw.SILENT, '', errors, warnings)
            except Exception as error:
                raise RuntimeError(f'SolidWorks OpenDoc6 kaynak dosyayı açamadı: {error}') from error
            matches = model is not None and path_key(sw._value(model, 'GetPathName')) == path_key(source_path)
            opened = matches and not (int(warnings.value or 0) & sw.ALREADY_OPEN)
            if model is None or errors.value:
                raise RuntimeError(f'Kaynak dosya açılamadı; SolidWorks OpenDoc6 hata kodu: {errors.value}')
        if (sw._value(model, 'GetType') != kind
                or path_key(sw._value(model, 'GetPathName')) != path_key(source_path)):
            raise RuntimeError('SolidWorks seçilen kaynak yerine farklı bir belge döndürdü.')
        if sw._value(model, 'GetSaveFlag'):
            raise RuntimeError(f'Kaynak dosyada kaydedilmemiş değişiklikler var; önce kaydedin: {source_path}')
        original_config = _configuration(model)
        visible = sw._value(model, 'Visible') if hasattr(model, 'Visible') else True
        if not visible:
            visibility_changed = True
            model.Visible = True
        activated = True  # Activation can change ActiveDoc even on failure.
        model = _activate(app, source_path)
        if sw._value(model, 'GetType') != kind:
            raise RuntimeError('Etkinleştirilen kaynak belgenin türü beklenen SolidWorks türü değil.')
        _check(stop)
        yield model
    except BaseException as error:
        failure = error
    finally:
        if model is not None and original_config is not None:
            try:
                if _configuration(model) != original_config:
                    if not model.ShowConfiguration2(original_config) or _configuration(model) != original_config:
                        raise RuntimeError('Önceki kaynak konfigürasyonu doğrulanamadı.')
            except Exception as error:
                cleanup_errors.append(f'Kaynak konfigürasyonu geri alınamadı: {error}')
        if visibility_changed and not opened and model is not None:
            try:
                model.Visible = False
            except Exception as error:
                cleanup_errors.append(f'Kaynak belge görünürlüğü geri alınamadı: {error}')
        if opened and model is not None:
            try:
                if sw._value(model, 'GetSaveFlag'):
                    raise RuntimeError('Açılan kaynakta kaydedilmemiş değişiklik oluştu; veri kaybını önlemek için belge açık bırakıldı.')
                app.CloseDoc(sw._value(model, 'GetTitle'))
            except Exception as error:
                cleanup_errors.append(f'Kaynak belge kapatılamadı: {error}')
        if (attempted_open or activated) and previous_name:
            try:
                active = sw._value(app, 'ActiveDoc')
                active_name = sw._document_name(active) if active is not None else None
                if active_name is None or path_key(active_name) != path_key(previous_name):
                    _activate(app, previous_name)
            except Exception as error:
                cleanup_errors.append(f'Önceki aktif belge geri açılamadı: {error}')
    if cleanup_errors:
        message = '; '.join(([str(failure)] if failure is not None and str(failure) else []) + cleanup_errors)
        raise RuntimeError(message) from failure
    if failure is not None:
        raise failure


def _session(app, stop=None, progress=None, *, model=None, source_path=None, require_assembly=False):
    _check(stop)
    model = sw._value(app, 'ActiveDoc') if model is None else model
    model = _late_bound(model)
    if model is None or sw._value(model, 'GetType') not in (1, 2, 3):
        raise RuntimeError('SolidWorks’te kayıtlı bir montaj, parça veya teknik resim açın.')
    if require_assembly and sw._value(model, 'GetType') != 2:
        raise RuntimeError('Aktif montaj seçeneği için SolidWorks’te bir montajı etkinleştirin.')
    root = str(sw._value(model, 'GetPathName') or '')
    if not root:
        raise RuntimeError('Önce açık SolidWorks belgesini kaydedin.')
    try:
        extension = _late_bound(sw._value(model, 'Extension'), 'SavePackAndGo')
    except Exception as error:
        raise RuntimeError(f'SolidWorks ModelDocExtension okunamadı: {error}') from error
    try:
        if hasattr(extension, '_oleobj_'):
            # GetPackAndGo() -> IDispatch. Specify its complete COM signature
            # directly; neither property probes nor inferred output arguments
            # should run while initializing the Pack and Go session.
            ole = extension._oleobj_
            dispid = ole.GetIDsOfNames(0, 'GetPackAndGo')
            raw = ole.InvokeTypes(dispid, 0, pythoncom.DISPATCH_METHOD,
                                  (pythoncom.VT_DISPATCH, 0), ())
            pg = win32com.client.Dispatch(raw) if raw is not None else None
        else:
            pg = extension.GetPackAndGo()
    except Exception as error:
        raise RuntimeError(f'SolidWorks GetPackAndGo başlatılamadı: {error}') from error
    if pg is None:
        raise RuntimeError('SolidWorks Pack and Go başlatılamadı.')
    for member in ('IncludeDrawings', 'IncludeSuppressed', 'IncludeToolboxComponents'):
        try:
            setattr(pg, member, True)
            if not sw._value(pg, member):
                raise RuntimeError('Ayar değeri geri okumada eşleşmedi.')
        except Exception as error:
            raise RuntimeError(f'Pack and Go ayarı uygulanamadı ({member}): {error}') from error
    try:
        pg.IncludeSimulationResults = False
        pg.AddPrefix = pg.AddSuffix = ''
    except Exception as error:
        raise RuntimeError(f'Pack and Go IncludeSimulationResults/AddPrefix/AddSuffix ayarları uygulanamadı: {error}') from error
    names, = _arrays(pg, 'GetDocumentNames', 1)
    try:
        count = sw._value(pg, 'GetDocumentNamesCount')
    except Exception as error:
        raise RuntimeError(f'SolidWorks GetDocumentNamesCount dosya sayısını okuyamadı: {error}') from error
    if type(count) is not int or not isinstance(names, (tuple, list)) or not names or len(names) != count:
        raise RuntimeError('Pack and Go dosya listesi eksik veya okunamıyor.')
    _, states = _arrays(pg, 'GetDocumentSaveToNames', 2)
    if not isinstance(states, (tuple, list)) or len(states) != count or any(type(state) is not int or state != 0 for state in states):
        raise RuntimeError('Sanal veya türü bilinmeyen dosyalar var. Sanal parçaları önce dış dosyaya kaydedin.')
    keys = [path_key(name) for name in names]
    if len(set(keys)) != count or path_key(root) not in keys:
        raise RuntimeError('Pack and Go listesi kök belgeyi içermiyor veya aynı dosya birden fazla kez listelenmiş.')
    documents = []
    for index, path in enumerate(names, 1):
        _check(stop)
        path = str(path)
        opened = _open_document(app, path)
        if opened is not None and sw._value(opened, 'GetSaveFlag'):
            raise RuntimeError(f'Kaydedilmemiş değişiklikler var; önce kaydedin: {path}')
        stamp = _stamp(path)
        dependencies = _dependencies(app, path) if PureWindowsPath(path).suffix.lower() in CAD_TYPES else ()
        missing = [ref for ref in dependencies if path_key(ref) not in keys]
        if missing:
            raise RuntimeError(f'Paket dışında kalan veya eksik dosya referansı: {missing[0]}')
        documents.append(Document(path, dependencies, stamp))
        if progress and (index == 1 or index == count or index % 25 == 0):
            progress(f'Dosyalar ve bağlantılar okunuyor · {index}/{count}')
    _check(stop)
    return Snapshot(root, tuple(documents), source_path, require_assembly), extension, pg


def scan(app, stop=None, progress=None, *, source_path=None, require_assembly=False):
    source_path = str(Path(source_path).absolute()) if source_path is not None else None
    with _source_document(app, source_path, stop) as model:
        snapshot, _, _ = _session(app, stop, progress, model=model,
                                  source_path=source_path, require_assembly=require_assembly)
    return snapshot


def plan_names(snapshot, destination, rules=Rules(), overrides=None, *, allow_collisions=False):
    """Keep SW extensions; pair same-folder/same-stem drawings to models."""
    # Planning is pure path/name work. Folder I/O is validated separately so
    # editing a prefix or leaving this page cannot block on a network share.
    if destination is None or not str(destination).strip():
        raise ValueError('Yeni montajın kaydedileceği hedef klasörü seçin.')
    destination = Path(destination).expanduser().absolute()
    if not isinstance(rules.start, int) or isinstance(rules.start, bool) or rules.start < 0:
        raise ValueError('Başlangıç numarası sıfır veya pozitif tam sayı olmalı.')
    if not isinstance(rules.digits, int) or not 1 <= rules.digits <= 8:
        raise ValueError('Numara basamak sayısı 1–8 arasında olmalı.')
    overrides = {path_key(path): value for path, value in (overrides or {}).items()}
    models = [doc for doc in snapshot.documents if doc.kind in ('Parça', 'Montaj')]
    drawings = [doc for doc in snapshot.documents if doc.kind == 'Teknik resim']
    names, paired = {}, {}
    # Sorting names does not reorder the eventual Pack and Go array.
    from bom.exporter import name_key
    ordered = sorted(models, key=lambda doc: (name_key(PureWindowsPath(doc.path).stem), path_key(doc.path)))
    for index, doc in enumerate(ordered, rules.start):
        file = PureWindowsPath(doc.path)
        stem = str(index).zfill(rules.digits) if rules.numbered else file.stem.replace(rules.find, rules.replacement) if rules.find else file.stem
        names[path_key(doc.path)] = valid_stem(overrides.get(path_key(doc.path), rules.prefix+stem+rules.suffix))
        paired.setdefault(path_key(str(file.with_suffix(''))), []).append((path_key(doc.path), names[path_key(doc.path)]))
    next_number = rules.start+len(ordered)
    for doc in sorted(drawings, key=lambda doc: path_key(doc.path)):
        file = PureWindowsPath(doc.path)
        candidates = paired.get(path_key(str(file.with_suffix(''))), ())
        refs = {path_key(ref) for ref in doc.dependencies}
        matched = [name for path, name in candidates if path in refs]
        pair = matched[0] if len(matched) == 1 else None
        stem = str(next_number).zfill(rules.digits) if rules.numbered else file.stem.replace(rules.find, rules.replacement) if rules.find else file.stem
        if pair is None:
            next_number += 1
        names[path_key(doc.path)] = valid_stem(overrides.get(path_key(doc.path), pair or rules.prefix+stem+rules.suffix))
    entries = []
    for doc in snapshot.documents:
        file = PureWindowsPath(doc.path)
        filename = names[path_key(doc.path)]+file.suffix if doc.kind != 'Ek dosya' else file.name
        valid_stem(filename)
        target = str(Path(destination).absolute()/filename)
        if len(target.encode('utf-16-le'))//2 >= 240:
            raise ValueError('Hedef dosya yolu çok uzun. Daha kısa klasör veya dosya adı seçin.')
        entries.append(Entry(doc.path, target))
    targets = [path_key(entry.destination) for entry in entries]
    if not allow_collisions and (len(set(targets)) != len(targets) or path_key(str(Path(destination)/REPORT_NAME)) in targets):
        raise NameCollision('Yeni dosya adları çakışıyor. Seçili adı düzenleyin veya numaralı isimlendirme kullanın.')
    if any(key in {path_key(doc.path) for doc in snapshot.documents} for key in targets):
        raise ValueError('Hedef dosya kaynak dosyanın üzerine yazamaz. Yeni bir paket klasörü seçin.')
    return tuple(entries)


def execute(app, snapshot, entries, destination, stop=None, progress=None):
    """Reopen an explicitly selected root rather than using a later ActiveDoc."""
    with _source_document(app, snapshot.source_path, stop) as model:
        return _execute(app, snapshot, entries, destination, stop, progress, model=model)


def _execute(app, snapshot, entries, destination, stop=None, progress=None, *, model=None):
    """Save directly to final paths so moving a staging folder cannot break refs."""
    _check(stop)
    destination = validate_destination(destination, snapshot)
    fresh, extension, pg = _session(app, stop, progress, model=model,
                                   source_path=snapshot.source_path, require_assembly=snapshot.require_assembly)
    old = {path_key(doc.path): doc for doc in snapshot.documents}
    current = {path_key(doc.path): doc for doc in fresh.documents}
    if path_key(fresh.root) != path_key(snapshot.root) or old != current:
        raise RuntimeError('Kaynak belge veya referansları önizlemeden sonra değişti. Dosyaları yeniden okuyun.')
    mapping = {path_key(entry.source): entry.destination for entry in entries}
    if set(mapping) != set(current) or len(mapping) != len(entries):
        raise ValueError('İsimlendirme planı bütün dosyaları tam olarak içermeli.')
    targets = [mapping[path_key(doc.path)] for doc in fresh.documents]
    if len({path_key(target) for target in targets}) != len(targets):
        raise ValueError('Hedef dosya adları çakışıyor.')
    if path_key(destination/REPORT_NAME) in {path_key(target) for target in targets}:
        raise ValueError('İsimlendirme raporunun adı başka bir dosyaya verilemez.')
    for target in targets:
        if Path(target).parent.absolute() != destination or Path(target).exists():
            raise ValueError('Bütün dosyalar yeni paket klasörünün içinde olmalı.')
        valid_stem(Path(target).name)
    for doc in fresh.documents:
        if PureWindowsPath(mapping[path_key(doc.path)]).suffix.lower() != PureWindowsPath(doc.path).suffix.lower():
            raise ValueError('SolidWorks dosya uzantısı değiştirilemez.')
    pg.FlattenToSingleFolder = True
    # SetSaveToName(True, ...) would override our explicit filename mapping.
    # The documented boolean return describes whether names were overridden;
    # False is legitimate with Override=False. Validate the explicit mapping
    # through Set/GetDocumentSaveToNames instead of interpreting it as failure.
    pg.SetSaveToName(False, str(destination))
    if not pg.SetDocumentSaveToNames(_com_array(targets)):
        raise RuntimeError('SolidWorks yeni dosya adlarını kabul etmedi.')
    saved_names, states = _arrays(pg, 'GetDocumentSaveToNames', 2)
    if (not isinstance(saved_names, (tuple, list)) or [path_key(p) for p in saved_names] != [path_key(p) for p in targets]
            or not isinstance(states, (tuple, list)) or len(states) != len(targets) or any(type(state) is not int or state != 0 for state in states)):
        raise RuntimeError('SolidWorks dosya adlarını planlandığı gibi eşleştirmedi.')
    _check(stop)
    # The folder picker may return an existing empty folder. Recheck after the
    # COM planning calls; originals and occupied folders must never be changed.
    validate_destination(destination, snapshot)
    created_folder = not destination.exists()
    if created_folder:
        destination.mkdir()
    validate_destination(destination, snapshot)
    complete = False
    try:
        if progress:
            progress('SolidWorks bağlantıları koruyarak yeni paketi oluşturuyor…')
        statuses = extension.SavePackAndGo(pg)
        if (not isinstance(statuses, (tuple, list)) or len(statuses) != len(targets)
                or any(type(status) is not int or status != 0 for status in statuses)):
            raise RuntimeError(f'Pack and Go bütün dosyaları kaydedemedi. Durum kodları: {statuses}')
        _check(stop)
        for index, doc in enumerate(fresh.documents, 1):
            _check(stop)
            target = mapping[path_key(doc.path)]
            if not Path(target).is_file() or Path(target).stat().st_size == 0:
                raise RuntimeError(f'Aktarılan dosya bulunamadı veya boş: {target}')
            expected = {path_key(mapping[path_key(ref)]) for ref in doc.dependencies}
            actual = {path_key(ref) for ref in _dependencies(app, target)} if doc.kind != 'Ek dosya' else set()
            if actual != expected:
                raise RuntimeError(f'Yeni pakette dosya referansları doğrulanamadı: {target}')
            if _stamp(doc.path) != doc.stamp:
                raise RuntimeError('Kaynak dosya aktarım sırasında değişti. Paketi yeniden hazırlayın.')
            if progress and (index == 1 or index == len(fresh.documents) or index % 25 == 0):
                progress(f'Yeni dosyanın bağlantıları doğrulandı: {PureWindowsPath(target).name}')
        report = dict(root=mapping[path_key(snapshot.root)], files=[dict(source=e.source, destination=e.destination) for e in entries],
                      file_references_verified=True, solidworks_pack_and_go=True)
        (destination/REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        _check(stop)
        complete = True
        return report
    finally:
        if not complete:
            for path in [*targets, str(destination/REPORT_NAME)]:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass
            if created_folder:
                try:
                    destination.rmdir()
                except OSError:
                    pass


def worker(events, stop, *, operation='scan', snapshot=None, entries=(), destination=None,
           source_path=None, require_assembly=False):
    initialized = False
    try:
        _check(stop)
        if pythoncom is None or win32com is None:
            raise RuntimeError('İsimlendirme Windows, pywin32 ve açık SolidWorks oturumu gerektirir.')
        pythoncom.CoInitialize()
        initialized = True
        app = _late_bound(connect_to_solidworks())
        phase = lambda text: events.put(('naming_phase', text))
        if operation == 'scan':
            outcome = dict(state='scanned', snapshot=scan(app, stop, phase,
                           source_path=source_path, require_assembly=require_assembly))
        elif operation == 'save':
            outcome = dict(state='saved', report=execute(app, snapshot, entries, destination, stop, phase))
        else:
            raise ValueError('Bilinmeyen isimlendirme işlemi.')
    except Cancelled:
        outcome = dict(state='cancelled')
    except Exception as error:
        outcome = dict(state='error', error=str(error))
    finally:
        if initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception as error:
                outcome = dict(state='error', error=f'SolidWorks bağlantısı kapatılamadı: {error}')
        events.put(('naming_done', outcome))
