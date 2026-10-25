"""STA-owned SolidWorks adapter. Enum IDs come from the installed swconst TLB.

No generated MakePy wrappers, guessed preference IDs or global CAD pointers.
AP242 uses PublishSTEP242File, not a fictitious swStepAP=242 preference.
"""

from contextlib import contextmanager
import math
from pathlib import Path

from .models import checkpoint
from .scanner import path_key

MODEL_IID = '{B90793FB-EF3D-4B80-A5C4-99959CDB6CEB}'
ASSEMBLY_IID = '{83A33D35-27C5-11CE-BFD4-00400513BB57}'
PART_IID = '{83A33D32-27C5-11CE-BFD4-00400513BB57}'
# A native part may retain usable B-Rep after its imported source is moved.
# Native CAD references and unrecognised dependencies remain mandatory.
IMPORTED_SOURCES = frozenset(('.stp', '.step', '.igs', '.iges', '.x_t', '.x_b', '.sat'))


def raw(obj):
    return getattr(obj, '_oleobj_', obj)


def invoke(obj, name, flags, *args):
    dispatch = raw(obj)
    member = None
    try:
        if hasattr(dispatch, 'Invoke') and hasattr(dispatch, 'GetIDsOfNames'):
            member = dispatch.GetIDsOfNames(0, name)
            return dispatch.Invoke(member, 0, flags, True, *args)
        member = getattr(obj, name)
        return member(*args) if flags == 1 else member
    finally:
        # Exceptions can retain frames until after the STA exits. Do not leave
        # child IDispatch pointers alive inside those tracebacks.
        obj = dispatch = member = None
        args = ()


def call(obj, name, *args):
    try: return invoke(obj, name, 1, *args)
    finally: obj = None; args = ()


def get(obj, name):
    try: return invoke(obj, name, 2)
    finally: obj = None


def interface(obj, iid):
    import pythoncom
    return raw(obj).QueryInterface(pythoncom.MakeIID(iid), pythoncom.IID_IDispatch)


def out_int():
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def null_dispatch():
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_DISPATCH, None)


def enum_values(library):
    values = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != 0:  # COM TKIND_ENUM, not a SolidWorks magic number.
            continue
        for number in range(attributes.cVars):
            description = info.GetVarDesc(number)
            values[info.GetDocumentation(description[0])[0]] = int(description[1])
    return values


def load_constants(app):
    import pythoncom
    from win32com.client.selecttlb import EnumTlbs
    failures = []
    # Prefer the TLB beside the running executable when multiple SW releases
    # are installed. Never take an older library just because registry order
    # happens to list it first.
    try:
        executable = Path(call(app, 'GetExecutablePath'))
        folder = executable if executable.is_dir() else executable.parent
        for path in (folder / 'swconst.tlb', folder / 'lang/english/swconst.tlb'):
            if path.is_file():
                values = enum_values(pythoncom.LoadTypeLib(str(path)))
                if 'swStepAP' in values: return values
    except Exception as error:
        failures.append(type(error).__name__)
    def version(value): return int(value, 16) if isinstance(value, str) else int(value)
    for entry in sorted(EnumTlbs(), key=lambda e: (version(e.major), version(e.minor)), reverse=True):
        description = str(entry.desc).casefold()
        if not any(w in description for w in ('solidworks', 'sldworks')) or not any(w in description for w in ('constant', 'swconst')):
            continue
        try:
            # selecttlb preserves registry version components as hexadecimal strings.
            major, minor = version(entry.major), version(entry.minor)
            values = enum_values(pythoncom.LoadRegTypeLib(entry.clsid, major, minor, int(entry.lcid)))
            if 'swStepAP' in values: return values
        except Exception as error:
            failures.append(type(error).__name__)
    raise RuntimeError('Kurulu SolidWorks swconst tür kitaplığı okunamadı. SolidWorks kurulumunu/COM kaydını onarın; tahmini API değerleriyle aktarım yapılmadı.')


class ApiError(RuntimeError):
    def __init__(self, message, errors=0, warnings=0):
        super().__init__(message)
        self.errors, self.warnings = int(errors), int(warnings)


class RestoreError(RuntimeError):
    """Stop the batch when session state cannot be restored safely."""


class Session:
    def __enter__(self):
        try:
            import pythoncom
        except ImportError as error:
            raise RuntimeError('3D aktarımı Windows, pywin32 ve açık SolidWorks oturumu gerektirir.') from error
        pythoncom.CoInitialize()
        self.pythoncom = pythoncom
        self.app = None
        self.owned = {}
        self.load_warnings = {}
        self.previous = ''
        active = None
        try:
            from solidworks.connection import connect_to_solidworks
            self.app = connect_to_solidworks(raw=True)
            self.constants = load_constants(self.app)
            active = get(self.app, 'ActiveDoc')
            if active is not None: self.previous = call(active, 'GetPathName') or call(active, 'GetTitle')
            active = None
            return self
        except Exception:
            active = self.app = None
            pythoncom.CoUninitialize()
            raise

    def c(self, name):
        try: return self.constants[name]
        except KeyError as error:
            raise RuntimeError(f'Kurulu SolidWorks API bu ayarı desteklemiyor: {name}.') from error

    def document(self, path):
        path = str(Path(path).resolve())
        if not Path(path).is_file(): raise FileNotFoundError('Kaynak model bulunamadı: ' + Path(path).name)
        model = call(self.app, 'GetOpenDocumentByName', path)
        if model is None:
            errors, warnings = out_int(), out_int()
            doc_type = self.c('swDocPART' if Path(path).suffix.casefold() == '.sldprt' else 'swDocASSEMBLY')
            options = self.c('swOpenDocOptions_Silent') | self.c('swOpenDocOptions_ReadOnly') | self.c('swOpenDocOptions_OverrideDefaultLoadLightweight')
            model = call(self.app, 'OpenDoc6', path, doc_type, options, '', errors, warnings)
            self.load_warnings[path_key(path)] = int(warnings.value)
            if model is not None and not warnings.value & self.c('swFileLoadWarning_AlreadyOpen'):
                self.owned[path_key(path)] = call(model, 'GetTitle')
            if model is None or errors.value:
                raise ApiError(f'Model açılamadı; SolidWorks kodu {errors.value}.', errors.value, warnings.value)
        model = interface(model, MODEL_IID)
        if path_key(call(model, 'GetPathName')) != path_key(path):
            raise ApiError('SolidWorks istenen kaynak yerine başka bir belge döndürdü.')
        if call(model, 'GetType') not in (self.c('swDocPART'), self.c('swDocASSEMBLY')):
            raise ApiError('Belge bir 3D parça veya montaj değil.')
        return model

    def activate(self, model):
        errors = out_int()
        path = call(model, 'GetPathName') or call(model, 'GetTitle')
        activated = None
        try:
            activated = call(self.app, 'ActivateDoc3', path, False, self.c('swDontRebuildActiveDoc'), errors)
            if activated is None or errors.value or path_key(call(activated, 'GetPathName')) != path_key(path):
                raise ApiError('Kaynak model etkinleştirilemedi; yanlış belgeden aktarım yapılmadı.', errors.value)
        finally:
            activated = model = None

    def configurations(self, model, options):
        active = str(get(get(get(model, 'ConfigurationManager'), 'ActiveConfiguration'), 'Name'))
        names = call(model, 'GetConfigurationNames') or ()
        names = (names,) if isinstance(names, str) else tuple(names)
        if not names or active not in names: raise ApiError('Model konfigürasyonları okunamadı.')
        if options.configurations == 'active': return (active,)
        if options.configurations == 'all': return names
        missing = set(options.selected_configurations) - set(names)
        if missing: raise ApiError('Bu modelde konfigürasyon yok: ' + ', '.join(sorted(missing)))
        return tuple(dict.fromkeys(options.selected_configurations))

    @contextmanager
    def configuration(self, model, name):
        previous = str(get(get(get(model, 'ConfigurationManager'), 'ActiveConfiguration'), 'Name'))
        manager = get(model, 'SelectionManager')
        suspended = False
        extension = None
        try:
            call(manager, 'SuspendSelectionList'); suspended = True
            self.activate(model)
            if name != previous and not call(model, 'ShowConfiguration2', name):
                raise ApiError('Konfigürasyon etkinleştirilemedi: ' + name)
            if str(get(get(get(model, 'ConfigurationManager'), 'ActiveConfiguration'), 'Name')) != name:
                raise ApiError('SolidWorks istenen konfigürasyona geçmedi.')
            extension = get(model, 'Extension')
            if get(extension, 'NeedsRebuild2') and not call(model, 'EditRebuild3'):
                raise ApiError('Konfigürasyon yeniden oluşturulamadı; eski geometri aktarılmadı.')
            call(model, 'ClearSelection2', True)
            extension = None
            yield
        finally:
            failures = []
            try:
                if name != previous:
                    if not call(model, 'ShowConfiguration2', previous): raise RestoreError('Konfigürasyon geri alınamadı.')
                    restored = str(get(get(get(model, 'ConfigurationManager'), 'ActiveConfiguration'), 'Name'))
                    if restored != previous: raise RestoreError('Konfigürasyon geri alma doğrulanamadı.')
            except Exception: failures.append('Kaynak konfigürasyon geri getirilemedi; modeli kontrol edin, kaydetmeyin.')
            try:
                if suspended: call(manager, 'ResumeSelectionList2', False)
            except Exception: failures.append('Önceki seçim listesi geri getirilemedi.')
            manager = model = extension = None
            if failures: raise RestoreError(' '.join(failures))

    def components(self, model):
        assembly = interface(model, ASSEMBLY_IID)
        values = call(assembly, 'GetComponents', False)
        assembly = None
        return tuple(values or ())

    def component(self, component):
        name = str(get(component, 'Name2'))
        state = call(component, 'GetSuppression2')
        if state == self.c('swComponentSuppressed'): return name, '', '', 'suppressed'
        if state == self.c('swComponentInternalIdMismatch'): return name, '', '', 'mismatch'
        path = str(call(component, 'GetPathName') or '')
        configuration = str(get(component, 'ReferencedConfiguration') or '')
        if get(component, 'IsVirtual'): return name, path, configuration, 'virtual'
        return name, path, configuration, 'normal'

    def is_assembly(self, model):
        return call(model, 'GetType') == self.c('swDocASSEMBLY')

    def has_saved_brep(self, model):
        """Check real solid/surface bodies, never a bounding box or graphics mesh."""
        part = body = None
        bodies = ()
        try:
            part = interface(model, PART_IID)
            for kind in ('swSolidBody', 'swSheetBody'):
                body_type = self.c(kind)
                bodies = call(part, 'GetBodies2', body_type, False) or ()
                for body in bodies:
                    if call(body, 'GetType') == body_type and call(body, 'GetFaceCount') > 0:
                        return True
            return False
        except Exception as error:
            raise ApiError('İçe aktarılan parçanın kayıtlı katı/yüzey geometrisi doğrulanamadı; aktarılmadı.') from error
        finally:
            model = part = body = None
            bodies = ()

    def dependencies(self, model):
        dependencies = call(self.app, 'GetDocumentDependencies2', call(model, 'GetPathName'), True, True, False) or ()
        if len(dependencies) % 2: raise ApiError('Model referansları okunamadı; eksiksiz aktarım doğrulanamıyor.')
        missing = [str(p) for p in dependencies[1::2] if not p or not Path(str(p)).is_file()]
        assembly = self.is_assembly(model)
        notes = ()
        if missing:
            names = ', '.join(Path(p).name or '(boş)' for p in missing)
            if assembly or any(Path(p).suffix.casefold() not in IMPORTED_SOURCES for p in missing):
                raise ApiError('Eksik/çözümlenemeyen model referansları: ' + names)
            if not self.has_saved_brep(model):
                raise ApiError('İçe aktarma kaynağı eksik ve parçada kayıtlı katı/yüzey geometrisi yok: ' + names)
            notes = ('İçe aktarma kaynağı bulunamadı: ' + names +
                     '. SLDPRT içindeki mevcut geometri aktarıldı; dış kaynağın güncelliği doğrulanmadı.',)
        if assembly:
            for component in self.components(model):
                name, path, _, state = self.component(component)
                if state == 'suppressed': continue
                if state == 'mismatch' or (state != 'virtual' and (not path or not Path(path).is_file())):
                    raise ApiError(name + ': montaj referansı eksik veya tutarsız.')
                if call(component, 'GetModelDoc2') is None:
                    raise ApiError(name + ': bileşen tam çözümlenmemiş. Montajı SolidWorks’te tam çözümlenmiş açın.')
        return notes

    @contextmanager
    def preferences(self, fmt, options):
        settings = []
        def add(kind, key, value): settings.append((kind, self.c(key), value))
        if fmt.protocol in (203, 214):
            add('IntegerValue', 'swStepAP', fmt.protocol)
            add('IntegerValue', 'swStepExportPreference', self.c('swAcisOutputAsSolidAndSurface'))
            add('Toggle', 'swStepExportConfigurationData', False)
        if fmt.key == 'iges':
            add('IntegerValue', 'swIGESRepresentation', self.c('swIGES_BREP'))
            add('Toggle', 'swIGESComponentsIntoOneFile', True)
            add('Toggle', 'swIGESExportSolidAndSurface', True)
            add('Toggle', 'swIGESExportAsWireframe', False)
        if fmt.key.startswith('stl_'):
            add('Toggle', 'swSTLBinaryFormat', fmt.key == 'stl_binary')
            add('Toggle', 'swSTLComponentsIntoOneFile', True)
            add('Toggle', 'swSTLShowInfoOnSave', False)
            add('Toggle', 'swSTLPreview', False)
            add('Toggle', 'swSTLDontTranslateToPositive', True)
            add('IntegerValue', 'swExportStlUnits', self.c('swMM' if options.stl_unit == 'mm' else 'swINCHES'))
            quality = {'coarse': 'Coarse', 'fine': 'Fine'}.get(options.stl_quality, 'Custom')
            add('IntegerValue', 'swSTLQuality', self.c('swSTLQuality_' + quality))
            if quality == 'Custom':
                deviation, angle = ((.1, 15) if options.stl_quality == 'medium' else (options.deviation_mm, options.angle_degrees))
                add('DoubleValue', 'swSTLDeviation', deviation / 1000)
                add('DoubleValue', 'swSTLAngleTolerance', math.radians(angle))
        # Snapshot everything before a setter can indirectly change another
        # setting (notably STL quality versus custom deviation/angle).
        snapshots = [(kind, key) for kind, key, _ in settings]
        if fmt.key.startswith('stl_'):
            for name in ('swSTLDeviation', 'swSTLAngleTolerance'):
                pair = ('DoubleValue', self.c(name))
                if pair not in snapshots: snapshots.append(pair)
        originals = [(kind, key, call(self.app, 'GetUserPreference' + kind, key)) for kind, key in snapshots]
        changed = False
        try:
            for kind, key, value in settings:
                changed = True
                result = call(self.app, 'SetUserPreference' + kind, key, value)
                # Toggle's published Automation return is void (None in pywin32).
                # Numeric setters return bool. All kinds are read back below.
                if kind != 'Toggle' and not result:
                    raise ApiError('SolidWorks dışa aktarma ayarını kabul etmedi; aktarım yapılmadı.')
                actual = call(self.app, 'GetUserPreference' + kind, key)
                if not math.isclose(actual, value, rel_tol=1e-9, abs_tol=1e-12):
                    raise ApiError('Dışa aktarma ayarı geri okunarak doğrulanamadı.')
            yield
        finally:
            failures = []
            # Restore mode/quality first, then dependent numeric settings.
            for kind, key, value in originals if changed else ():
                try:
                    result = call(self.app, 'SetUserPreference' + kind, key, value)
                    if kind != 'Toggle' and not result: raise RestoreError()
                except Exception: failures.append(str(key))
            for kind, key, value in originals if changed else ():
                try:
                    if not math.isclose(call(self.app, 'GetUserPreference' + kind, key), value, rel_tol=1e-9, abs_tol=1e-12): raise RestoreError()
                except Exception: failures.append(str(key))
            if failures: raise RestoreError('SolidWorks aktarım ayarları geri yüklenemedi; işlem durdu. Ayar kimlikleri: ' + ', '.join(failures))

    def save(self, model, path, fmt):
        self.activate(model)
        call(model, 'ClearSelection2', True)
        extension = get(model, 'Extension')
        try:
            if fmt.protocol == 242:
                error = int(call(extension, 'PublishSTEP242File', str(path)))
                if error != self.c('swPublishStep242_Success'):
                    if error == self.c('swPublishStep242_MBDLicenseNotAvailable'):
                        raise ApiError('STEP AP242 yayınlanamadı: SolidWorks MBD lisansı yok.', error)
                    raise ApiError(f'AP242 bu kurulumda yayınlanamadı; SolidWorks kodu {error}.', error)
                return 0, 0
            errors, warnings = out_int(), out_int()
            saved = call(extension, 'SaveAs3', str(path), self.c('swSaveAsCurrentVersion'),
                         self.c('swSaveAsOptions_Silent') | self.c('swSaveAsOptions_Copy'),
                         null_dispatch(), null_dispatch(), errors, warnings)
            if not saved or errors.value:
                raise ApiError(f'CAD dışa aktarımı başarısız; SolidWorks kodu {errors.value}.', errors.value, warnings.value)
            return errors.value, warnings.value
        finally:
            extension = model = None

    def release(self, path):
        key = path_key(path)
        title = self.owned.pop(key, None)
        if title:
            try: call(self.app, 'CloseDoc', title)
            except Exception:
                self.owned[key] = title
                raise

    def __exit__(self, kind, error, tb):
        failures = []
        try:
            for key, title in reversed(tuple(self.owned.items())):
                try: call(self.app, 'CloseDoc', title)
                except Exception: failures.append('Araç tarafından açılan model kapatılamadı.')
            self.owned.clear()
            if self.previous:
                try:
                    errors = out_int()
                    restored = call(self.app, 'ActivateDoc3', self.previous, False, self.c('swDontRebuildActiveDoc'), errors)
                    if restored is None or errors.value: raise RestoreError()
                    restored = None
                except Exception: failures.append('Önceki aktif belge geri getirilemedi.')
                finally: restored = None
        finally:
            self.app = None
            self.pythoncom.CoUninitialize()
        if failures: raise RestoreError(' '.join(failures))
