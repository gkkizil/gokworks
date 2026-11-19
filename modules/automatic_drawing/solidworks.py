"""One STA, existing SolidWorks only. Reuse the application's raw COM boundary.

No model saving, suppression writes, temporary named views, application shutdown
or unowned-document closing is performed by this module.
"""

from collections import Counter
from contextlib import contextmanager
import copy
import math
from pathlib import Path
import threading
import time

from modules.cad_converter.api import (ApiError, RestoreError, MODEL_IID, PART_IID,
    ASSEMBLY_IID, interface, activation_failed)
from modules.profile_cutting.solidworks import Session as ReadSession, values
from modules.tolerance_stack.com import call as _call, get as _get, invoke, variant, out_int
from modules.tolerance_stack.com import put as put, null_dispatch as null_dispatch

from .models import (SCHEMA_VERSION, FaceEvidence, ModelInfo, Node, Source, checkpoint, finite, identity, to_mm)
from .outputs import fingerprint
from .rules import classify

DRAWING_IID = '{83A33D33-27C5-11CE-BFD4-00400513BB57}'
MAX_FEATURES = 20000
MAX_FACES = 50000
MAX_COMPONENTS = 50000


def hresult(error):
    while error is not None:
        code = getattr(error, 'hresult', None)
        if code is not None:
            return code
        error = error.__cause__
    return None


def error_text(error):
    code = hresult(error)
    if code in (-2147418111, -2147417846):
        return 'SolidWorks meşgul veya bir iletişim penceresi açık. SolidWorks’teki pencereyi kapatıp yeniden deneyin.'
    if code in (-2147417848, -2147023174):
        return 'SolidWorks bağlantısı kesildi. Açık kaynak belgelerini kontrol edip işlemi yeniden başlatın.'
    return str(error)


def _read_retry(operation):
    for attempt in range(3):
        try:
            return operation()
        except Exception as error:
            if hresult(error) not in (-2147418111, -2147417846) or attempt == 2:
                raise
            import pythoncom
            pythoncom.PumpWaitingMessages()
            time.sleep(.02*(attempt+1))


def call(obj, name, *args):
    # Only rejected READS retry. A creation/save call may have side effects and
    # is never repeated just because a COM result was lost.
    if name.startswith(('Get', 'Is')) or name in ('RevisionNumber', 'FirstFeature'):
        return _read_retry(lambda: _call(obj, name, *args))
    return _call(obj, name, *args)


def get(obj, name):
    return _read_retry(lambda: _get(obj, name))


def as_interface(obj, iid):
    return interface(obj, iid) if hasattr(obj, 'QueryInterface') or hasattr(obj, '_oleobj_') else obj


def prop(obj, name, *arguments):
    """Parameterized properties such as CustomPropertyManager are PROPERTYGET."""
    return _read_retry(lambda: invoke(obj, name, 2, *arguments))


def optional(obj, name, *arguments, property=False, default=None):
    try:
        return prop(obj, name, *arguments) if property else call(obj, name, *arguments)
    except Exception as error:
        # Optional means absent/version-dependent, never disconnected or busy.
        cause = error
        while cause is not None:
            if getattr(cause, 'hresult', None) in (
                    -2147417848, -2147023174, -2147418111, -2147417846):
                raise
            cause = cause.__cause__
        return default


def feature_tree(model, stop=None):
    pending, seen = [(call(model, 'FirstFeature'), False)], set()
    try:
        while pending:
            checkpoint(stop)
            feature, sub = pending.pop()
            if feature is None:
                continue
            name, kind = str(get(feature, 'Name')), str(call(feature, 'GetTypeName2'))
            token = name, kind, sub
            if token in seen:
                continue
            seen.add(token)
            if len(seen) > MAX_FEATURES:
                raise ApiError('Unsur ağacı tarama sınırını aştı.')
            pending.append((call(feature, 'GetNextSubFeature' if sub else 'GetNextFeature'), sub))
            pending.append((call(feature, 'GetFirstSubFeature'), True))
            yield feature, name, kind
    finally:
        pending.clear()
        feature = model = None


class Session(ReadSession):
    def __enter__(self):
        try:
            super().__enter__()  # CoInitialize is STA; raw GetActiveObject, installed swconst.
        except Exception as error:
            raise ApiError('Otomatik Teknik Resim için Windows, pywin32 ve açık bir SolidWorks oturumu gerekli. '
                           + error_text(error)) from error
        self.owner_thread = threading.get_ident()
        self.analysis_cache = {}
        self.created = []
        self.interface_ids = {}
        try:
            self.revision = str(call(self.app, 'RevisionNumber'))
        except BaseException:
            super().__exit__(None, None, None)
            raise
        return self

    def assert_thread(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError('SolidWorks COM nesnesi sahibi STA dışında kullanılamaz.')

    def named_interface(self, obj, name):
        """Resolve auxiliary dual-interface IIDs from the RUNNING SW type library."""
        from modules.cad_converter.api import raw
        dispatch = raw(obj)
        if not hasattr(dispatch, 'QueryInterface'):
            return obj
        import pythoncom
        if name not in self.interface_ids:
            library = self.type_library()
            for index in range(library.GetTypeInfoCount()):
                if library.GetDocumentation(index)[0] == name:
                    self.interface_ids[name] = library.GetTypeInfo(index).GetTypeAttr().iid
                    break
            else:
                raise ApiError('Kurulu SolidWorks arayüzü bulunamadı: '+name)
        return dispatch.QueryInterface(self.interface_ids[name], pythoncom.IID_IDispatch)

    def type_library(self):
        """sldworks type library of the running release.

        Recorded on SolidWorks 2025 SP5: ISldWorks' GetTypeInfo().GetContainingTypeLib() raises
        TYPE_E_ELEMENTNOTFOUND (-2147319765), so the library beside the running executable is
        loaded instead (as load_constants does for swconst.tlb).
        """
        from modules.cad_converter.api import raw
        import pythoncom
        try:
            return raw(self.app).GetTypeInfo().GetContainingTypeLib()[0]
        except Exception as error:
            executable = Path(str(call(self.app, 'GetExecutablePath') or ''))
            folder = executable if executable.is_dir() else executable.parent
            path = folder/'sldworks.tlb'
            if not path.is_file():
                raise ApiError('Çalışan SolidWorks tür kitaplığı bulunamadı: '+str(path)) from error
            return pythoncom.LoadTypeLib(str(path))

    def activate(self, model):
        self.assert_thread()
        errors = out_int()
        path = call(model, 'GetPathName') or call(model, 'GetTitle')
        activated = call(self.app, 'ActivateDoc3', path, False, self.c('swDontRebuildActiveDoc'), errors)
        if activated is None or activation_failed(errors.value):
            raise ApiError(f'Belge etkinleştirilemedi; SolidWorks kodu {errors.value}.')
        activated = as_interface(activated, MODEL_IID)
        if identity(call(activated, 'GetPathName') or call(activated, 'GetTitle')) != identity(path):
            raise ApiError('SolidWorks farklı bir belgeyi etkinleştirdi; işlem durduruldu.')

    def source(self, source=None):
        self.assert_thread()
        if source is None or not source.path:
            model = as_interface(get(self.app, 'ActiveDoc'), MODEL_IID)
            if model is None:
                raise ApiError('SolidWorks’te bir parça veya montaj açın.')
        else:
            model = self.document(source.path)  # Existing session: read-only OpenDoc6.
        if call(model, 'GetType') not in (self.c('swDocPART'), self.c('swDocASSEMBLY')):
            raise ApiError('Kaynak SLDPRT veya SLDASM olmalı.')
        path = str(call(model, 'GetPathName') or '')
        if not path or not Path(path).is_file():
            raise ApiError('Kaynak modelin kayıtlı dosyası bulunamadı; önce SolidWorks’te kaydedin.')
        return model

    @contextmanager
    def configuration(self, model, name):
        """Restore selection/configuration even when view creation changes ActiveDoc."""
        self.assert_thread()
        previous = self.active_configuration(model)
        if name not in values(call(model, 'GetConfigurationNames')):
            raise ApiError('Kaynak konfigürasyonu bulunamadı: '+name)
        manager, suspended = None, False
        try:
            manager = get(model, 'SelectionManager')
            call(manager, 'SuspendSelectionList'); suspended = True
            if name != previous and not call(model, 'ShowConfiguration2', name):
                raise ApiError('Kaynak konfigürasyonu açılamadı: '+name)
            if self.active_configuration(model) != name:
                raise ApiError('Kaynak konfigürasyonu doğrulanamadı.')
            yield
        finally:
            failures = []
            try:
                if self.active_configuration(model) != previous:
                    if not call(model, 'ShowConfiguration2', previous) or self.active_configuration(model) != previous:
                        raise RestoreError()
            except Exception:
                failures.append('Kaynak konfigürasyonu geri getirilemedi; sıradaki dosya işlenmedi.')
            try:
                if suspended:
                    call(manager, 'ResumeSelectionList2', False)
            except Exception:
                failures.append('Kaynağın önceki seçim listesi geri getirilemedi.')
            manager = model = None
            if failures:
                raise RestoreError(' '.join(failures))

    def source_ready(self, model):
        """A drawing must describe the saved model, not unknowable unsaved edits."""
        dirty = call(model, 'GetSaveFlag')
        if dirty is not False:
            raise ApiError('Kaynakta kaydedilmemiş değişiklik var veya kayıt durumu okunamadı. '
                           'Modeli SolidWorks’te kaydedip yeniden deneyin; uygulama kaynağı kaydetmedi.')
        pending = self.rebuild_pending(model)
        if pending is True and self.rebuild_after_load(model):
            pending = self.rebuild_pending(model)
        if pending is not False:
            raise ApiError('Kaynak yeniden oluşturulmalı veya güncelliği doğrulanamadı. '
                           'SolidWorks’te yeniden oluşturup kaydedin.')

    def rebuild_after_load(self, model):
        """Perform the rebuild SolidWorks itself requested while THIS session opened the file.

        Recorded on SolidWorks 2025 SP5 with 'rebuild assembly on load: always'
        (swPerformanceAssemRebuildOnLoad = 1): every assembly, even one saved fully rebuilt,
        opens with load warning swFileLoadWarning_NeedsRegen (32) and NeedsRebuild2 = 1.
        Only a document this session opened read-only is rebuilt, in memory: it cannot be
        saved, and documents the user already had open are never rebuilt here.
        """
        from modules.cad_converter.api import path_key
        flag = self.constants.get('swFileLoadWarning_NeedsRegen')
        key = path_key(str(call(model, 'GetPathName') or ''))
        if flag is None or key not in getattr(self, 'owned', {}) or not getattr(self, 'load_warnings', {}).get(key, 0) & flag:
            return False
        if call(model, 'ForceRebuild3', False) is not True:
            return False
        self.load_rebuilt = getattr(self, 'load_rebuilt', set()) | {key}
        return True

    def memory_stamp(self, model):
        value = optional(model, 'GetUpdateStamp')
        return int(value) if type(value) is int else None

    def persistent_ref(self, model, obj):
        # Preserve RPC/busy failures; the general read adapter's optional helper
        # treats every exception as missing data, which is unsafe for identity.
        import base64
        data = optional(get(model, 'Extension'), 'GetPersistReference3', obj, default=())
        if not data:
            return ''
        return 'persist:'+base64.b64encode(bytes(int(v) & 255 for v in data)).decode('ascii')

    def property_values(self, manager):
        result = {}
        for name in values(call(manager, 'GetNames')):
            raw, resolved = variant(0x4008, ''), variant(0x4008, '')
            good, linked = variant(0x400B, False), variant(0x400B, False)
            status = call(manager, 'Get6', str(name), False, raw, resolved, good, linked)
            if isinstance(status, (tuple, list)):
                if len(status) != 5:
                    raise ApiError('Custom Property Get6 çıktı sözleşmesi geçersiz.')
                status, raw.value, resolved.value, good.value, linked.value = status
            if status == self.c('swCustomInfoGetResult_ResolvedValue') and good.value:
                result[str(name)] = str(resolved.value or raw.value or '')
        return result

    def properties(self, model, configuration):
        result = {}
        extension = manager = None
        try:
            extension = get(model, 'Extension')
            for config in ('', configuration):
                manager = prop(extension, 'CustomPropertyManager', config)
                result.update(self.property_values(manager))
            return result
        finally:
            extension = manager = model = None

    def tree(self, model, stop=None):
        root_source = Source(str(call(model, 'GetPathName')), self.active_configuration(model))
        root_node = Node(str(call(model, 'GetTitle')), root_source, 'assembly')
        configuration = get(get(model, 'ConfigurationManager'), 'ActiveConfiguration')
        root = call(configuration, 'GetRootComponent3', False)
        if root is None:
            raise ApiError('Montaj kökü çözümlenemedi; montajı tam çözümlenmiş açın.')
        stack = [(root, root_node, frozenset((root_source.key,)))]
        count = 0
        component = parent = None
        try:
            while stack:
                checkpoint(stop)
                parent, parent_node, ancestors = stack.pop()
                for component in values(call(parent, 'GetChildren')):
                    checkpoint(stop); count += 1
                    if count > MAX_COMPONENTS:
                        raise ApiError('Montaj ağacı güvenli tarama sınırını aştı.')
                    name = str(get(component, 'Name2'))
                    state = call(component, 'GetSuppression2')
                    if state == self.c('swComponentSuppressed'):
                        parent_node.children.append(Node(name, Source(''), state='suppressed',
                                                         detail='Bastırılmış bileşen işlenmedi.'))
                        continue
                    path = str(call(component, 'GetPathName') or '')
                    config = str(get(component, 'ReferencedConfiguration') or '')
                    source = Source(path, config)
                    virtual = bool(optional(component, 'IsVirtual', property=True, default=False))
                    hidden = bool(call(component, 'IsHidden', False))
                    excluded = bool(optional(component, 'ExcludeFromBOM', property=True, default=False))
                    kind = 'assembly' if Path(path).suffix.casefold() == '.sldasm' else 'part'
                    node = Node(name, source, kind, hidden=hidden, excluded_bom=excluded)
                    parent_node.children.append(node)
                    if virtual:
                        node.state, node.detail = 'virtual', 'Sanal bileşen için kayıtlı kaynak dosyası gerekli.'
                        continue
                    if not path or not config or not Path(path).is_file():
                        node.state, node.detail = 'missing', 'Dosya veya referans konfigürasyonu bulunamadı.'
                        continue
                    resolved = call(component, 'GetModelDoc2')
                    if resolved is None:
                        node.state, node.detail = 'unresolved', 'Lightweight / çözümlenmemiş bileşen.'
                        continue
                    resolved = None
                    if kind == 'assembly':
                        if source.key in ancestors:
                            node.state, node.detail = 'cycle', 'Döngüsel montaj referansı.'
                        else:
                            stack.append((component, node, ancestors | {source.key}))
            return root_node
        finally:
            stack.clear()
            root = component = configuration = parent = model = None

    def inspect(self, model, source, stop=None):
        """COM stays here; ModelInfo/Node contain only Python values."""
        self.assert_thread()
        checkpoint(stop)
        path = str(call(model, 'GetPathName'))
        configuration = self.active_configuration(model)
        source = Source(path, configuration)
        stamp = fingerprint(path)
        memory = self.memory_stamp(model)
        clean = call(model, 'GetSaveFlag') is False
        key = source.key, stamp, memory, self.revision, SCHEMA_VERSION
        if clean and memory is not None and key in self.analysis_cache:
            return copy.deepcopy(self.analysis_cache[key])
        assembly = call(model, 'GetType') == self.c('swDocASSEMBLY')
        specific = as_interface(model, ASSEMBLY_IID if assembly else PART_IID)
        box = values(call(specific, 'GetBox', 0) if assembly else call(specific, 'GetPartBox', True))
        if len(box) != 6:
            raise ApiError('Modelin dış sınırları okunamadı.')
        size = tuple(to_mm(box[i+3]-box[i]) for i in range(3))
        if any(not math.isfinite(v) or v <= 0 for v in size):
            raise ApiError('Model geometrisi boş veya dış ölçüleri geçersiz.')
        info = ModelInfo(source, 'assembly' if assembly else 'part', str(call(model, 'GetTitle')), size,
                         configurations=tuple(str(s) for s in values(call(model, 'GetConfigurationNames'))),
                         revision=self.revision, fingerprint=stamp, memory_stamp=memory)
        try:
            info.properties = self.properties(model, configuration)
        except Exception as error:
            info.warnings.append('Model özellikleri tam okunamadı: '+str(error))
        if self.active_configuration(model) != configuration:
            if not call(model, 'ShowConfiguration2', configuration) or self.active_configuration(model) != configuration:
                raise ApiError('Özellik okuma sonrası kaynak konfigürasyonu doğrulanamadı.')
        info.source_unit = self.display_unit(model)
        kinds, names, thicknesses = Counter(), set(), set()
        feature = definition = None
        sheet_features = []
        try:
            for feature, name, kind in feature_tree(model, stop):
                if (name, kind) in names:
                    continue
                names.add((name, kind)); kinds[kind] += 1
                if kind in ('FlatPattern', 'CutListFolder'):
                    sheet_features.append((name, kind, self.persistent_ref(model, feature)))
                if 'sheetmetal' in kind.casefold():
                    definition = call(feature, 'GetDefinition')
                    thickness = optional(definition, 'Thickness', property=True)
                    if thickness is not None:
                        thicknesses.add(finite(to_mm(thickness), 'Sac kalınlığı', minimum=.0001))
                    definition = None
            info.feature_types = dict(kinds)
            info.thickness_mm = tuple(sorted(thicknesses))
            # Names alone are only candidates; native IsFlatPatternView is verified later.
            info.flat_configurations = tuple(s for s in info.configurations if 'flat-pattern' in s.casefold())
        finally:
            feature = definition = None
        if assembly:
            info.tree = self.tree(model, stop)
        else:
            bodies = values(call(specific, 'GetBodies2', self.c('swSolidBody'), False))
            info.body_count = len(bodies)
            face = body = surface = None
            try:
                for body in bodies:
                    checkpoint(stop)
                    if call(body, 'IsSheetMetal'):
                        info.sheet_body_count += 1
                    for face in values(call(body, 'GetFaces')):
                        checkpoint(stop)
                        if len(info.faces) >= MAX_FACES:
                            raise ApiError('Yüzey sayısı güvenli analiz sınırını aştı.')
                        area = finite(call(face, 'GetArea'), 'Yüzey alanı', minimum=0)*1e6
                        surface = call(face, 'GetSurface')
                        if call(surface, 'IsPlane'):
                            direction = tuple(float(v) for v in values(get(face, 'Normal')))
                            info.faces.append(FaceEvidence('plane', area, direction))
                        elif call(surface, 'IsCylinder'):
                            params = values(get(surface, 'CylinderParams'))
                            if len(params) != 7:
                                raise ApiError('Silindirik yüzey parametreleri geçersiz.')
                            info.faces.append(FaceEvidence('cylinder', area, tuple(float(v) for v in params[3:6]),
                                                           to_mm(params[6]), tuple(to_mm(v) for v in params[:3])))
                        else:
                            info.faces.append(FaceEvidence('other', area))
                        surface = None
                if not bodies:
                    raise ApiError('Kaynakta teknik resim oluşturulabilecek katı gövde yok.')
            finally:
                bodies = (); body = face = surface = None
            database = variant(0x4008, '')
            material = optional(specific, 'GetMaterialPropertyName2', configuration, database)
            if material and isinstance(material, str):
                info.properties.setdefault('Material', material)
            if info.sheet_body_count:
                from .sheetmetal import inspect_bodies
                info.sheet_bodies = inspect_bodies(self, model, info, sheet_features, stop)
                info.flat_configurations = tuple(sorted({name for row in info.sheet_bodies
                                                         for name in row.configurations}))
                for row in info.sheet_bodies:
                    info.warnings.extend(row.label+': '+text for text in row.warnings)
                if len({row.material for row in info.sheet_bodies if row.material}) > 1:
                    info.warnings.append('Sac gövdeleri farklı malzemelerde. Gövde başlıkları ayrı yazılır; '
                                         'firma antetindeki ortak model malzemesini kontrol edin.')
        mass = optional(get(model, 'Extension'), 'CreateMassProperty')
        if mass is not None:
            m, v = optional(mass, 'Mass', property=True), optional(mass, 'Volume', property=True)
            if m is not None: info.mass_kg = finite(m, 'Kütle', minimum=0)
            if v is not None: info.volume_m3 = finite(v, 'Hacim', minimum=0)
            mass = None
        info.classification, info.classification_reason = classify(info)
        if fingerprint(path) != stamp:
            raise ApiError('Kaynak model analiz sırasında değişti; eski analiz kullanılmadı.')
        if clean and memory is not None:
            self.analysis_cache[key] = copy.deepcopy(info)
        specific = model = None
        return info

    def sheet_format_folders(self, template=''):
        """Existing folders that hold .slddrt files: SolidWorks' setting, then the installation's own.

        The setting can name a folder of a removed release. Seen on SolidWorks 2025 SP5
        (Turkish): '...\\SOLIDWORKS 2024\\lang\\turkish\\sheetformat', which no longer existed,
        while the formats were in '...\\SOLIDWORKS 2025\\lang\\turkish\\sheetformat'.
        """
        import os
        found = []
        if 'swFileLocationsSheetFormat' in self.constants:
            setting = optional(self.app, 'GetUserPreferenceStringValue', self.c('swFileLocationsSheetFormat'), default='')
            found += [p.strip() for p in str(setting or '').split(';') if p.strip()]
        language = str(optional(self.app, 'GetCurrentLanguage', default='') or '').strip()
        roots = list(Path(template).parents) if template else []
        try:   # RevisionNumber 33.x is SOLIDWORKS 2025
            year = int(str(getattr(self, 'revision', '')).split('.')[0]) + 1992
            roots.append(Path(os.environ.get('ProgramData', r'C:\ProgramData'), 'SolidWorks', f'SOLIDWORKS {year}'))
        except ValueError:
            pass
        for root in roots:
            for name in dict.fromkeys(n for n in (language, 'english') if n):
                found.append(str(Path(root, 'lang', name, 'sheetformat')))
        return [folder for folder in dict.fromkeys(found) if Path(folder).is_dir()]

    def standard_sheet_format(self, paper, template=''):
        """The installed ISO sheet format of a standard paper ('a3 - iso.slddrt'), or ''."""
        from .models import PAPERS
        if paper not in PAPERS:
            return ''
        for folder in self.sheet_format_folders(template):
            path = Path(folder, f'{paper.casefold()} - iso.slddrt')
            if path.is_file():
                return str(path)
        return ''

    def new_drawing(self, template, width_mm, height_mm):
        self.assert_thread()
        model = call(self.app, 'NewDocument', template, self.c('swDwgPapersUserDefined'),
                     width_mm/1000, height_mm/1000)
        if model is None:
            raise ApiError('SolidWorks şablondan teknik resim oluşturamadı.')
        model = as_interface(model, MODEL_IID)
        # Track before any subsequent API validation, so failed setup is cleaned.
        self.created.append(model)
        if call(model, 'GetType') != self.c('swDocDRAWING'):
            raise ApiError('Şablon bir Drawing belgesi oluşturmadı.')
        return model, as_interface(model, DRAWING_IID)

    def close_created(self, model):
        self.assert_thread()
        if not any(item is model for item in self.created):
            raise RestoreError('Kullanıcının açık teknik resmi kapatılamaz.')
        title = str(call(model, 'GetTitle') or '')
        if not title:
            raise RestoreError('Oluşturulan teknik resmin başlığı okunamadı.')
        path = str(call(model, 'GetPathName') or '')
        call(self.app, 'CloseDoc', title)
        remaining = call(self.app, 'GetOpenDocumentByName', path or title)
        if remaining is not None:
            raise RestoreError('SolidWorks oluşturulan teknik resmi kapatmadı; kaynak belgeleri kapatılmadı.')
        self.created = [item for item in self.created if item is not model]

    def open_drawing(self, path):
        self.assert_thread()
        # Output/staging paths are owned and unique, never use an existing open drawing.
        if call(self.app, 'GetOpenDocumentByName', str(path)) is not None:
            raise ApiError('Doğrulama hedefi zaten açık; açık belgeye müdahale edilmedi.')
        errors, warnings = out_int(), out_int()
        model = call(self.app, 'OpenDoc6', str(path), self.c('swDocDRAWING'),
                     self.c('swOpenDocOptions_Silent') | self.c('swOpenDocOptions_ReadOnly'),
                     '', errors, warnings)
        if model is not None:
            model = as_interface(model, MODEL_IID)
            self.created.append(model)
        if model is None or errors.value:
            raise ApiError(f'Kaydedilen SLDDRW tekrar açılamadı; API kodu {errors.value}.')
        if call(model, 'GetType') != self.c('swDocDRAWING'):
            raise ApiError('Kayıtlı çıktı Drawing belgesi değil.')
        if identity(call(model, 'GetPathName')) != identity(str(path)):
            raise ApiError('Yeniden açılan SLDDRW kimliği eşleşmedi.')
        return model, as_interface(model, DRAWING_IID)

    def __exit__(self, kind, error, tb):
        failures = []
        try:
            for model in reversed(self.created[:]):
                try: self.close_created(model)
                except Exception as cleanup_error: failures.append(str(cleanup_error))
            self.created.clear()
            self.analysis_cache.clear()
            model = None
        finally:
            super().__exit__(kind, error, tb)
        if failures:
            raise RestoreError(' '.join(failures))
