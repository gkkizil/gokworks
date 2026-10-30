"""Read-only, STA-owned sheet inventory. Only plain data leaves the session.

File/configuration/body is the manufacturing identity, never a displayed name.
No UpdateCutList, suppression change, geometry rebuild or native Save is used.
"""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import math
import re

from modules.cad_converter.api import call, get, interface, PART_IID, ApiError, RestoreError
from modules.cad_converter.models import checkpoint, Cancelled
from modules.profile_cutting.solidworks import Session as ReadSession, optional, values
from modules.tolerance_stack.com import variant


def key(path, configuration=''):
    from .exporter import _part_key
    return _part_key(path, configuration)


def identity(source, configuration, body):
    return sha256(repr((*key(source, configuration), body)).encode('utf-8')).hexdigest()


class Session(ReadSession):
    def active_configuration(self,model):
        try:return str(get(get(get(model,'ConfigurationManager'),'ActiveConfiguration'),'Name'))
        finally:model=None

    @contextmanager
    def configuration(self,model,name):
        """Read a referenced configuration without activating hidden components.

        As in the native sheet-metal API workflow, ShowConfiguration2 operates
        on the explicit document. Only the actual export activates a visible
        part. Preserve its previous configuration and any selection list.
        """
        previous=None;manager=None;suspended=False;changed=False
        try:
            previous=self.active_configuration(model)
            if name not in values(call(model,'GetConfigurationNames')):
                raise ApiError('İstenen konfigürasyon bulunamadı: '+name)
            if name!=previous:
                manager=get(model,'SelectionManager')
                call(manager,'SuspendSelectionList');suspended=True;changed=True
                if not call(model,'ShowConfiguration2',name):
                    raise ApiError('Konfigürasyon açılamadı: '+name)
            if self.active_configuration(model)!=name:
                raise ApiError('İstenen konfigürasyon doğrulanamadı.')
            yield
        finally:
            failures=[]
            try:
                if changed and (not call(model,'ShowConfiguration2',previous) or self.active_configuration(model)!=previous):
                    failures.append('Kaynak konfigürasyon geri getirilemedi.')
            except Exception as error:failures.append(str(error))
            try:
                if suspended:call(manager,'ResumeSelectionList2',False)
            except Exception as error:failures.append('Seçim listesi geri getirilemedi: '+str(error))
            model=manager=None
            if failures:raise RestoreError(' '.join(failures))

    def part(self, model):
        return interface(model, PART_IID) if hasattr(model, 'QueryInterface') or hasattr(model, '_oleobj_') else model

    def features(self, model, stop=None):
        """Visit both SW feature links, independently; duplicate exposure is normal."""
        pending, visited, emitted = [(call(model, 'FirstFeature'), False)], set(), set()
        feature = None
        try:
            while pending:
                checkpoint(stop)
                feature, sub = pending.pop()
                if feature is None:
                    continue
                name, kind = str(get(feature, 'Name')), str(call(feature, 'GetTypeName2'))
                token = (name, kind, self.persistent_ref(model, feature))
                if (token, sub) in visited:
                    continue
                visited.add((token, sub))
                if len(visited) > 20000:
                    raise ApiError('Unsur ağacı güvenli tarama sınırını aştı.')
                pending.append((call(feature, 'GetNextSubFeature' if sub else 'GetNextFeature'), sub))
                pending.append((call(feature, 'GetFirstSubFeature'), True))
                if token not in emitted:
                    emitted.add(token)
                    yield feature, kind
        finally:
            pending.clear(); model = feature = None

    def same(self, model, a, b):
        if a is b:
            return True
        ra, rb = self.persistent_ref(model, a), self.persistent_ref(model, b)
        if ra and rb:
            return ra == rb
        return call(self.app, 'IsSame', a, b) == self.c('swObjectSame')

    def flat_body(self, feature):
        definition = entity = None
        try:
            definition = call(feature, 'GetDefinition')
            if definition is None:
                raise ApiError('Flat-Pattern tanımı okunamadı.')
            entity = get(definition, 'FixedFace2')
            if entity is None:
                raise ApiError('Flat-Pattern sabit yüzü/kenarı bulunamadı.')
            body = call(entity, 'GetBody')  # IFace2 / IEdge / IVertex
            if body is None:
                raise ApiError('Flat-Pattern gövdesi bulunamadı.')
            return body
        finally:
            feature = definition = entity = None

    def resolved(self, owner):
        return {name.upper(): p.evaluated for name, p in self.properties(owner).items()
                if p.resolved and p.evaluated}

    def document_properties(self, model, configuration):
        from types import SimpleNamespace
        from modules.cad_converter.api import invoke
        props = {}
        for scope in ('', configuration):
            try:
                manager = invoke(get(model, 'Extension'), 'CustomPropertyManager', 2, scope)
                props.update(self.resolved(SimpleNamespace(CustomPropertyManager=manager)))
            except Exception:
                pass
        return props

    def thickness(self, model, body, props, all_features):
        def read(features):
            found = []
            for feature in features:
                if call(feature, 'GetTypeName2') != 'SheetMetal':
                    continue
                state = call(feature, 'IsSuppressed2', self.c('swThisConfiguration'), variant(0, None))
                if state is None or any(values(state)):
                    continue
                value = float(get(call(feature, 'GetDefinition'), 'Thickness')) * 1000
                if math.isfinite(value) and value > 0:
                    found.append(value)
            return found
        linked = optional(body, 'GetFeatures', default=())
        measurements = read(values(linked))
        if not measurements:
            for name in ('SHEET METAL THICKNESS', 'SHEETMETAL THICKNESS', 'THICKNESS', 'SAC KALINLIĞI'):
                text = str(props.get(name, '')).strip()
                match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|inch|\")?', text, re.I)
                if match:
                    unit = (match[2] or self.display_unit(model)).lower()
                    factor = {'mm': 1, 'cm': 10, 'm': 1000, 'in': 25.4, 'inch': 25.4, '"': 25.4}.get(unit)
                    if factor:
                        measurements = [float(match[1].replace(',', '.')) * factor]
                        break
        if not measurements:
            # A shared value is safe only when every active sheet feature agrees.
            measurements = read([f for f, kind in all_features if kind == 'SheetMetal'])
        if not measurements or any(not math.isfinite(v) or v<=0 for v in measurements) or any(not math.isclose(v, measurements[0], abs_tol=1e-6, rel_tol=1e-9)
                                   for v in measurements[1:]):
            raise ApiError('Gövdeye ait sac kalınlığı kesin belirlenemedi.')
        return measurements[0]

    def material(self, model, body, configuration, props, *, body_props=None):
        """Body Cut List/native assignment precede document-wide defaults."""
        def property_value(properties):
            return next((str(properties[n]).strip() for n in ('MATERIAL', 'SW-MATERIAL', 'MALZEME')
                         if properties.get(n) and str(properties[n]).strip()), '')

        def native(owner):
            try:
                value = call(owner, 'GetMaterialPropertyName2', configuration, variant(0x4008, ''))
                return value.strip() if isinstance(value, str) else ''
            except Exception:
                return ''

        value = property_value(body_props or {}) or native(body) or property_value(props)
        if value:
            return value
        try:
            return native(self.part(model))
        except Exception:
            return ''

    def describe(self, model, source, configuration, stop=None, *, body_ref=''):
        """Classify with IsSheetMetal first. Mechanical parts get no feature scan."""
        bodies = sheets = features = folders = flats = None
        body = feature = folder = fixed = None
        rows, warnings = [], []
        folder_by_body,flat_by_body,property_cache = {},{},{}
        matches = patterns = members = ()
        try:
            bodies = values(call(self.part(model), 'GetBodies2', self.c('swSolidBody'), False))
            sheets = []
            for body in bodies:
                checkpoint(stop)
                try:
                    if call(body, 'IsSheetMetal'):
                        sheets.append(body)
                except Exception as error:
                    warnings.append(f'{source} [{configuration}]: gövdenin sac durumu doğrulanamadı: {error}')
            sheet_count = len(sheets)
            if body_ref:
                sheets = [body for body in sheets if self.persistent_ref(model, body) == body_ref]
            if not sheets:
                return rows, warnings
            try:
                features = list(self.features(model, stop))
            except (Cancelled,RestoreError):
                raise
            except Exception as error:
                features=[]
                warnings.append(f'{source} [{configuration}]: sac gövdesi bulundu, unsur ağacı okunamadı: {error}')
            folders, flats = [], []
            for feature, kind in features:
                checkpoint(stop)
                try:
                    if kind == 'CutListFolder':
                        folder = call(feature, 'GetSpecificFeature2')
                        folders.append((feature, values(call(folder, 'GetBodies'))))
                    elif kind == 'FlatPattern':
                        fixed = self.flat_body(feature)
                        flats.append((feature, fixed))
                except Exception as error:
                    warnings.append(f'{source} · {get(feature, "Name")}: {error}')
            document_props = self.document_properties(model, configuration)
            folder_by_body, flat_by_body = {}, {}
            for feature,members in folders:
                for member in members:
                    token = self.persistent_ref(model,member)
                    if token: folder_by_body.setdefault(token,[]).append(feature)
            for feature,fixed in flats:
                token = self.persistent_ref(model,fixed)
                if token: flat_by_body.setdefault(token,[]).append(feature)
            property_cache = {}
            rebuilt = self.rebuild_pending(model)
            for body in sheets:
                checkpoint(stop)
                reference = self.persistent_ref(model, body)
                row = dict(source=source, configuration=configuration, body_ref=reference,
                           body_name=str(optional(body, 'Name', prop=True, default='') or 'Adsız sac gövdesi'),
                           body_count=len(bodies), sheet_count=sheet_count, material='', thickness_mm=None,
                           flat_ref='', flat_pattern='', cut_list='', code=Path(source).stem,
                           status='pending', detail='', exportable=True)
                from .exporter import preview_identity
                row.update(preview_identity(model,body))
                notes = []
                try:
                    if not reference:
                        raise ApiError('Kalıcı gövde kimliği okunamadı; isimle tahmin edilmedi.')
                    matches = folder_by_body.get(reference,[])
                    props = dict(document_props)
                    body_props = {}
                    if len(matches) > 1:
                        raise ApiError('Gövde birden fazla Cut List klasörüne bağlı; eşleşme belirsiz.')
                    if matches:
                        feature = matches[0]
                        row['cut_list'] = str(get(feature, 'Name'))
                        if row['cut_list'] not in property_cache:
                            property_cache[row['cut_list']] = self.properties(feature)
                        properties = property_cache[row['cut_list']]
                        row['properties'] = {n: dict(raw=p.raw, evaluated=p.evaluated, resolved=p.resolved)
                                             for n, p in properties.items()}
                        body_props = {n.upper():p.evaluated for n,p in properties.items() if p.resolved and p.evaluated}
                        props.update(body_props)
                    else:
                        notes.append('Cut List bulunamadı; doğrudan gövde verisi kullanıldı.')
                    row['thickness_mm'] = self.thickness(model, body, props, features)
                    row['material'] = self.material(model, body, configuration, props, body_props=body_props)
                    row['code'] = next((props[n] for n in ('PART NUMBER', 'PARTNO', 'KOD', 'PARÇA KODU') if props.get(n)), row['code'])
                    patterns = flat_by_body.get(reference,[])
                    if len(patterns) != 1:
                        raise ApiError('Flat-Pattern bulunamadı.' if not patterns else 'Bir gövdeye birden fazla Flat-Pattern bağlı; seçim belirsiz.')
                    row['flat_pattern'] = str(get(patterns[0], 'Name'))
                    row['flat_ref'] = self.persistent_ref(model, patterns[0])
                    if not row['flat_ref']:
                        raise ApiError('Flat-Pattern kalıcı kimliği okunamadı.')
                    if rebuilt is not False:
                        raise ApiError('Model rebuild bekliyor veya güncelliği okunamadı; SolidWorks’te yeniden oluşturup tarayın.')
                except Exception as error:
                    if isinstance(error, (Cancelled, RestoreError)):
                        raise
                    row.update(status='error', exportable=False)
                    notes.append(str(error))
                row['detail'] = '; '.join(notes) or 'Açınım aktarımına hazır.'
                # Reference is mandatory for export; ordinal only distinguishes error rows.
                row['sheet_id'] = identity(source, configuration, reference or f'error-{len(rows)}')
                rows.append(row)
            return rows, warnings
        finally:
            model = bodies = sheets = features = folders = flats = None
            body = feature = folder = fixed = None
            folder_by_body.clear();flat_by_body.clear();property_cache.clear()
            matches = patterns = members = ()

    @contextmanager
    def selected_flat(self, model, body_ref, flat_ref, stop=None, *, feature_name=''):
        """Re-resolve both persistent IDs, verify ownership, isolate and restore selection."""
        manager = feature = body = None
        suspended = False
        try:
            checkpoint(stop)
            bodies = values(call(self.part(model), 'GetBodies2', self.c('swSolidBody'), False))
            matching = [b for b in bodies if self.persistent_ref(model, b) == body_ref]
            if len(matching) != 1 or not call(matching[0], 'IsSheetMetal'):
                raise ApiError('Seçilen sac gövdesi artık bulunamıyor; yeniden tarayın.')
            body = matching[0]
            patterns=[]
            if feature_name:
                try:
                    feature=call(model,'FeatureByName',feature_name)
                    if feature is not None and call(feature,'GetTypeName2')=='FlatPattern' and self.persistent_ref(model,feature)==flat_ref:
                        patterns=[feature]
                except Exception:
                    feature=None
            if not patterns:
                patterns = [f for f, kind in self.features(model, stop)
                            if kind == 'FlatPattern' and self.persistent_ref(model, f) == flat_ref]
            if len(patterns) != 1 or not self.same(model, body, self.flat_body(patterns[0])):
                raise ApiError('Flat-Pattern seçilen gövdeye ait değil; aktarım yapılmadı.')
            feature = patterns[0]
            checkpoint(stop)
            manager = get(model, 'SelectionManager')
            call(manager, 'SuspendSelectionList'); suspended = True
            call(model, 'ClearSelection2', True)
            if not call(feature, 'Select2', False, -1):
                raise ApiError('Gövdeye ait Flat-Pattern seçilemedi.')
            yield
        finally:
            try:
                if suspended:
                    call(model, 'ClearSelection2', True)
                    call(manager, 'ResumeSelectionList2', False)
            except Exception as error:
                raise RestoreError('Önceki seçim listesi geri alınamadı; kaynak kaydedilmedi.') from error
            finally:
                model = manager = feature = body = None
                bodies = matching = patterns = ()


def _children(component):
    try:return values(call(component, 'GetChildren'))
    finally:component=None


def assembly_occurrences(session, assembly, stop, warnings):
    """Instance traversal. Repeated subassemblies are counted for every occurrence.

    Lightweight leaves are read via a read-only part document, rather than
    changing suppression states in the user's assembly. Unloaded subassemblies
    are traversed in their exact referenced document/configuration.
    """
    configuration = session.active_configuration(assembly)
    config = get(get(assembly, 'ConfigurationManager'), 'ActiveConfiguration')
    if optional(config, 'IsSpeedPak', prop=True, default=False):
        raise ApiError('SpeedPak yerine tam montaj konfigürasyonunu açın.')
    root = call(config, 'GetRootComponent3', True)
    if root is None:
        raise ApiError('Aktif montajın bileşen ağacı okunamadı.')
    root_path = call(assembly, 'GetPathName') or call(assembly, 'GetTitle')
    records, seen_instances, complete = [], set(), True

    def traverse(children, prefix, ancestors):
        nonlocal complete
        if len(ancestors)>256 or len(seen_instances)>100000:
            raise ApiError('Montaj tarama güvenlik sınırı aşıldı.')
        sibling_names = set()
        try:
            for component in children:
                if len(seen_instances)>=100000:
                    raise ApiError('Montaj 100.000 örnek güvenlik sınırını aştı.')
                checkpoint(stop)
                model = None
                name = 'Bileşen'
                path = conf = ''
                virtual = False
                try:
                    name = str(get(component, 'Name2'))
                    instance = prefix + '/' + name
                    if name in sibling_names or instance in seen_instances:
                        raise ApiError('Aynı montaj örneği API tarafından tekrar döndürüldü.')
                    sibling_names.add(name); seen_instances.add(instance)
                    state = call(component, 'GetSuppression2')
                    if state == session.c('swComponentSuppressed'):
                        continue
                    if state == session.constants.get('swComponentInternalIdMismatch', object()):
                        raise ApiError('Bileşen kimliği tutarsız.')
                    path = str(call(component, 'GetPathName') or '')
                    conf = str(get(component, 'ReferencedConfiguration') or '')
                    if not conf:
                        raise ApiError('Bileşen konfigürasyonu okunamadı.')
                    model = call(component, 'GetModelDoc2')
                    virtual = bool(optional(component, 'IsVirtual', prop=True, default=False))
                    if not path and model is not None:
                        path = str(call(model, 'GetPathName') or '')
                    if model is None:
                        if virtual or not path:
                            raise ApiError('Sanal/çözümlenemeyen bileşenin modeli okunamadı.')
                        model = session.document(path)
                    kind = call(model, 'GetType')
                    if kind == session.c('swDocPART'):
                        source = path or f'{root_path}^{instance}.SLDPRT'
                        records.append((source, conf, instance, virtual, model if virtual else None))
                    elif kind == session.c('swDocASSEMBLY'):
                        token = key(path or instance, conf)
                        if token in ancestors:
                            raise ApiError('Montaj referanslarında döngü bulundu.')
                        if optional(component, 'IsSpeedPak', prop=True, default=False):
                            raise ApiError('SpeedPak alt montajın tam ağacı okunamıyor.')
                        children = _children(component)
                        if children:
                            traverse(children, instance, ancestors | {token})
                        else:
                            with session.configuration(model, conf):
                                c = get(get(model, 'ConfigurationManager'), 'ActiveConfiguration')
                                r = call(c, 'GetRootComponent3', True)
                                if r is None:
                                    raise ApiError('Alt montaj bileşen ağacı okunamadı.')
                                traverse(_children(r), instance, ancestors | {token})
                    else:
                        raise ApiError('Bileşenin belge türü doğrulanamadı.')
                except (Cancelled, RestoreError):
                    raise
                except Exception as error:
                    if path.lower().endswith('.sldprt') and conf:
                        # An identified part leaf cannot conceal further children.
                        # Preserve its physical occurrence for per-file reporting;
                        # another part's verified quantity remains usable.
                        if not virtual:records.append((path,conf,instance,False,None))
                    else:
                        # An unreadable subassembly can hide more occurrences of
                        # ANY known part, so its quantities cannot be certified.
                        complete = False
                    warnings.append(f'{prefix} · {locals().get("name", "Bileşen")}: {error}')
                finally:
                    model = component = None
        finally:
            children = component = model = c = r = None
    try:
        traverse(_children(root), str(root_path), {key(root_path, configuration)})
        return records, complete
    except BaseException:
        records.clear()
        raise
    finally:
        assembly = config = root = None


def scan_inventory(session, source=None, recursive=True, stop=None, *, mode='active', progress=None):
    """Return grouped body rows and warnings; cache descriptions per document/config."""
    from .exporter import find_parts
    if mode not in ('active','file','folder'):
        raise ValueError('Tarama modu active, file veya folder olmalı.')
    if mode=='file' and not source:
        raise ValueError('Bir SLDPRT veya SLDASM dosyası seçin.')
    warnings, records, complete = [], [], True
    model = None
    cache, rows = {}, {}
    try:
        if mode == 'folder':
            paths = find_parts(source, recursive, stop)
            active = get(session.app,'ActiveDoc')
            if active is not None and call(active,'GetType')==session.c('swDocASSEMBLY'):
                allowed = {key(path)[0] for path in paths}
                records,complete = assembly_occurrences(session,active,stop,warnings)
                records = [r for r in records if key(r[0])[0] in allowed]
            else:
                records = [(path, '', path, False, None) for path in paths]
            active = None
        else:
            model = session.document(source if mode == 'file' else None)
            if call(model, 'GetType') == session.c('swDocASSEMBLY'):
                records, complete = assembly_occurrences(session, model, stop, warnings)
            else:
                path = str(call(model, 'GetPathName') or '')
                if not path:
                    raise ApiError('Parçayı önce SolidWorks dosyası olarak kaydedin.')
                records = [(path, session.active_configuration(model), path, False, None)]
        for index,(source_path, conf, instance, virtual, virtual_model) in enumerate(records,1):
            checkpoint(stop)
            if progress is not None:
                progress(index,len(records))
            token = (*key(source_path, conf), instance if virtual else '')
            if token not in cache:
                try:
                    model = virtual_model if virtual else session.document(source_path)
                    conf = conf or session.active_configuration(model)
                    with session.configuration(model, conf):
                        descriptors, notes = session.describe(model, source_path, conf, stop)
                    warnings.extend(notes)
                    cache[token] = descriptors
                except (Cancelled, RestoreError):
                    raise
                except Exception as error:
                    warnings.append(f'{source_path} [{conf}]: sac sınıflandırması tamamlanamadı: {error}')
                    cache[token] = []
                finally:
                    model = None
                    if mode=='folder':session.release(source_path)
            for descriptor in cache[token]:
                row = rows.setdefault(descriptor['sheet_id'], dict(descriptor, instances=[], quantity=0))
                row['instances'].append(instance); row['quantity'] += 1
                if virtual:
                    row.update(exportable=False, status='error', detail='Sanal sac gövdesi bulundu. Aktarım/önizleme için önce harici SLDPRT olarak kaydedin.')
                if not complete:
                    row.update(exportable=False, status='error', detail='Montaj ağacı eksik okunabildi; adet doğrulanamadı. Günlüğü kontrol edip yeniden tarayın.')
        configurations = {}
        for path,conf,*_ in records:
            configurations.setdefault(key(path)[0],set()).add(conf)
        for row in rows.values():
            row['configuration_count'] = len(configurations[key(row['source'])[0]])
        return list(rows.values()), warnings
    finally:
        model = virtual_model = None
        records.clear(); cache.clear()


def scan_sources(source, recursive, events, stop, *, mode='folder', session_factory=Session):
    """Qt worker entry point. Never sends unclassified/mechanical source rows."""
    rows, warnings = [], []
    summary = dict(state='preview', total=0, warnings=warnings, mode=mode)
    try:
        events.put(('phase', 'Sac gövdeleri ve montaj örnekleri taranıyor…'))
        from .preview.cancellation import cancellable_read
        with cancellable_read(stop,timeout=None):
            with session_factory() as session:
                rows, notes = scan_inventory(session, source, recursive, stop, mode=mode,
                    progress=lambda done,total:events.put(('progress',(done,total))))
                warnings.extend(notes)
        checkpoint(stop)
        events.put(('sheet_inventory', rows))
        summary['total'] = len(rows)
        for note in warnings:
            events.put(('log', note))
    except Cancelled:
        summary['state'] = 'cancelled'
    except RestoreError as error:
        summary.update(state='error', error=str(error), native_restore_failed=True)
    except Exception as error:
        summary.update(state='error', error=str(error))
    finally:
        events.put(('done', summary))
