"""STA-owned Weldments adapter using the existing raw IDispatch connection."""

from contextlib import contextmanager
from dataclasses import dataclass
import base64
from pathlib import Path

from modules.cad_converter.api import (Session as CadSession, call, get, interface,
    ASSEMBLY_IID, ApiError, RestoreError)
from modules.tolerance_stack.com import variant
from .models import Property, checkpoint
from .geometry import Face


def values(value):
    if value is None: return ()
    return tuple(value) if isinstance(value, (tuple, list)) else (value,)


def optional(obj, name, *, prop=False, default=None):
    try: return get(obj, name) if prop else call(obj, name)
    except Exception: return default


@dataclass(frozen=True)
class Component:
    name: str
    path: str
    configuration: str
    state: str


class Session(CadSession):
    def __enter__(self):
        try: return super().__enter__()
        except Exception as error:
            cause = error
            while cause is not None:
                if getattr(cause, 'hresult', None) == -2147221164:
                    raise ApiError('SolidWorks kurulu değil veya COM kaydı bulunamadı. Lisanslı SolidWorks kurulumunu kontrol edin.') from error
                cause = cause.__cause__
            raise

    def document(self, path=None):
        if path is not None:
            if Path(path).suffix.casefold() not in ('.sldprt','.sldasm'):
                raise ValueError('Yalnız SLDPRT veya SLDASM kaynakları seçilebilir.')
            return super().document(path)
        model = get(self.app, 'ActiveDoc')
        if model is None:
            raise ApiError('SolidWorks’te bir SLDPRT veya SLDASM açın.')
        from modules.cad_converter.api import MODEL_IID
        model = interface(model, MODEL_IID) if hasattr(model, 'QueryInterface') or hasattr(model, '_oleobj_') else model
        if call(model, 'GetType') not in (self.c('swDocPART'), self.c('swDocASSEMBLY')):
            raise ApiError('Açık belge parça veya montaj değil; SLDPRT / SLDASM açın.')
        return model

    def active_configuration(self, model):
        return str(get(get(get(model, 'ConfigurationManager'), 'ActiveConfiguration'), 'Name'))

    @contextmanager
    def configuration(self, model, name):
        previous = self.active_configuration(model)
        names = values(call(model, 'GetConfigurationNames'))
        if name not in names:
            raise ApiError('İstenen konfigürasyon bulunamadı: ' + name)
        try:
            if name != previous:
                self.activate(model)
                if not call(model, 'ShowConfiguration2', name):
                    raise ApiError('Konfigürasyon açılamadı: ' + name)
            if self.active_configuration(model) != name:
                raise ApiError('İstenen konfigürasyon doğrulanamadı.')
            yield
        finally:
            try:
                if name != previous:
                    if not call(model, 'ShowConfiguration2', previous) or self.active_configuration(model) != previous:
                        raise RestoreError('Kaynak konfigürasyon geri getirilemedi; tarama durduruldu.')
            finally: model = None

    def children(self, model, stop=None):
        assembly = interface(model, ASSEMBLY_IID) if hasattr(model, 'QueryInterface') or hasattr(model, '_oleobj_') else model
        components = component = None
        try:
            components = values(call(assembly, 'GetComponents', True))  # Top level only; recurse in service.
            result = []
            names = set()
            for component in components:
                checkpoint(stop)
                name = str(get(component, 'Name2'))
                if name in names: raise ApiError('Montaj API’si aynı bileşen örneğini iki kez döndürdü: ' + name)
                names.add(name)
                state = call(component, 'GetSuppression2')
                if state == self.c('swComponentSuppressed'):
                    result.append(Component(name, '', '', 'suppressed')); continue
                path = str(call(component, 'GetPathName') or '')
                configuration = str(get(component, 'ReferencedConfiguration') or '')
                virtual = optional(component, 'IsVirtual', prop=True, default=False)
                mismatch = state == self.constants.get('swComponentInternalIdMismatch', object())
                result.append(Component(name, path, configuration,
                    'virtual' if virtual else 'mismatch' if mismatch else
                    'lightweight' if state in tuple(self.constants[k] for k in
                        ('swComponentLightweight', 'swComponentFullyLightweight') if k in self.constants) else 'normal'))
            return result
        finally: model = assembly = components = component = None

    def properties(self, feature):
        manager = get(feature, 'CustomPropertyManager')
        properties = {}
        try:
            for name in values(call(manager, 'GetNames')):
                raw, resolved = variant(0x4008, ''), variant(0x4008, '')
                was_resolved, linked = variant(0x400B, False), variant(0x400B, False)
                try:
                    status = call(manager, 'Get6', name, False, raw, resolved, was_resolved, linked)
                    if isinstance(status, (list, tuple)):
                        if len(status) != 5: raise ApiError('Get6 çıktı sözleşmesi geçersiz.')
                        status, raw.value, resolved.value, was_resolved.value, linked.value = status
                    good = status == self.c('swCustomInfoGetResult_ResolvedValue')
                    properties[str(name)] = Property(str(name), str(raw.value or ''), str(resolved.value or ''),
                        bool(was_resolved.value and good), bool(linked.value),
                        'resolved' if good else 'cached_or_missing')
                except Exception as error:
                    properties[str(name)] = Property(str(name), status='Okunamadı: ' + str(error))
            return properties
        finally: manager = feature = None

    def display_unit(self, model):
        try:
            value = call(model, 'GetUnits')[0]
            for name, unit in (('swMM','mm'), ('swCM','cm'), ('swMETER','m'), ('swINCHES','in'), ('swFEET','ft')):
                if name in self.constants and self.constants[name] == value: return unit
        except Exception: pass
        return ''

    def persistent_ref(self, model, obj):
        extension = None
        try:
            extension = get(model, 'Extension')
            data = call(extension, 'GetPersistReference3', obj)
            if data: return 'persist:' + base64.b64encode(bytes((int(x) & 255 for x in data))).decode('ascii')
        except Exception: pass
        finally: extension = model = obj = None
        return ''

    def faces(self, body, stop=None):
        faces = face = surface = None
        result = []
        try:
            faces = values(call(body, 'GetFaces'))
            for face in faces:
                checkpoint(stop)
                surface = call(face, 'GetSurface')
                if call(surface, 'IsPlane'):
                    normal = tuple(float(v) for v in get(face, 'Normal'))
                    point = tuple(float(v) for v in call(face, 'GetClosestPointOn', 0., 0., 0.)[:3])
                    result.append(Face('plane', normal, point))
                elif call(surface, 'IsCylinder'):
                    parameters = get(surface, 'CylinderParams')
                    if len(parameters) != 7: raise ApiError('Silindir verisi geçersiz.')
                    result.append(Face('cylinder', tuple(float(v) for v in parameters[3:6])))
                else:
                    result.append(Face('unsupported', (0., 0., 0.)))
            return result
        finally: body = faces = face = surface = None

    def cut_folders(self, model, stop=None):
        """Walk top-level and subfeatures, keeping each actual folder once."""
        seen = set()
        def walk(feature, sub=False):
            siblings = set()
            while feature is not None:
                checkpoint(stop)
                token = self.persistent_ref(model, feature) or str(get(feature, 'Name'))
                if token in siblings: raise ApiError('FeatureManager ağacında yinelenen/döngüsel unsur bulundu.')
                siblings.add(token)
                if token not in seen:
                    seen.add(token)
                    kind = call(feature, 'GetTypeName2')
                    if kind in ('CutListFolder', 'SolidBodyFolder'):
                        yield feature, kind
                    child = call(feature, 'GetFirstSubFeature')
                    if child is not None: yield from walk(child, True)
                feature = call(feature, 'GetNextSubFeature' if sub else 'GetNextFeature')
        yield from walk(call(model, 'FirstFeature'))

    def assembly_cautions(self, model, stop=None):
        """A part-document cut list cannot prove instance-specific assembly cuts."""
        safe = {'Reference','HistoryFolder','CommentsFolder','FavoriteFolder','FavoritesFolder',
                'SelectionSetFolder','SensorFolder','DetailCabinet','DocsFolder','MaterialFolder',
                'RefPlane','RefAxis','RefPoint','CoordSys','OriginProfileFeature','MateGroup',
                'ProfileFeature','3DProfileFeature','FtrFolder','MateReference','ExplodedView',
                'LocalLPattern','LocalCirPattern','MirrorComponent','DerivedComponentPattern',
                'CompCurvePattern','SketchDrivenPattern'}
        feature = extension = None
        warnings = []
        try:
            extension = get(model, 'Extension')
            if optional(extension, 'NeedsRebuild2', prop=True) is not False:
                warnings.append('Montaj rebuild bekliyor veya güncelliği okunamadı.')
            feature = call(model, 'FirstFeature')
            seen = set()
            while feature is not None:
                checkpoint(stop)
                name = str(get(feature, 'Name'))
                if name in seen: raise ApiError('Montaj unsur ağacı döngüsel.')
                seen.add(name)
                kind = call(feature, 'GetTypeName2')
                if kind not in safe:
                    warnings.append(f'Montaj unsuru {name} ({kind}): örneğe özel kesim/cope etkisi parça Cut List’iyle doğrulanamadı.')
                feature = call(feature, 'GetNextFeature')
            return warnings
        finally: model = feature = extension = None
