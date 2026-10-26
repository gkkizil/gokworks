"""Source/configuration matched native isometric BMP capture; STA-owned COM only."""

from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.cad_converter.api import call, get, invoke, raw, ApiError, RestoreError
from modules.cad_converter.scanner import path_key
from modules.profile_cutting.solidworks import Session as ReadSession
from modules.tolerance_stack.com import variant
from .exporter import Cancelled, _check_cancel, sw


@dataclass(frozen=True)
class Preview:
    png: bytes | None
    note: str


def _put(obj, name, value):
    try:
        if hasattr(raw(obj), 'Invoke'):
            return invoke(obj, name, 4, value)
        setattr(obj, name, value)
    finally:
        obj = value = None


def _array(obj, length):
    data = tuple(float(x) for x in get(obj, 'ArrayData'))
    if len(data) != length or not all(math.isfinite(x) for x in data):
        raise ApiError('SolidWorks görünüm dönüşümü okunamadı.')
    return data


def _same(left, right):
    return len(left) == len(right) and all(math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-9)
                                         for a, b in zip(left, right))


def _isometric(view, utility):
    orientation = vector = transformed = None
    try:
        orientation = get(view, 'Orientation3')
        lengths = []
        for axis in ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)):
            vector = call(utility, 'CreateVector', variant(0x2005, axis))  # SAFEARRAY(double)
            transformed = call(vector, 'MultiplyTransform', orientation)
            x, y, _ = _array(transformed, 3)
            lengths.append(x*x+y*y)
        return lengths[0] > 1e-12 and all(math.isclose(lengths[0], n, rel_tol=1e-6) for n in lengths[1:])
    finally:
        view = utility = orientation = vector = transformed = None


def _png(bitmap):
    from PIL import Image
    with Image.open(bitmap) as source:
        if source.format != 'BMP' or not all(16 <= n <= 4096 for n in source.size):
            raise ApiError('SolidWorks geçerli bir parça görüntüsü üretmedi.')
        image = source.convert('RGB')
    if all(low == high for low, high in image.getextrema()):
        raise ApiError('SolidWorks boş bir parça görüntüsü üretti.')
    image.thumbnail((256, 192), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (264, 200), 'white')
    canvas.paste(image, ((264-image.width)//2, (200-image.height)//2))
    buffer = BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


class Session(ReadSession):
    @contextmanager
    def view_state(self, model):
        """Restore the original view even when a configuration or capture fails."""
        view = manager = camera = utility = None
        visible = snapshot = None
        suspended = False
        try:
            visible = bool(get(model, 'Visible'))
            if not visible:
                _put(model, 'Visible', True)
            self.activate(model)
            view = get(model, 'ActiveView')
            if view is None:
                raise ApiError('Parçanın görüntü penceresi oluşturulamadı.')
            orientation = _array(get(view, 'Orientation3'), 16)
            translation = _array(get(view, 'Translation3'), 3)
            scale = float(get(view, 'Scale2'))
            if not math.isfinite(scale) or scale <= 0:
                raise ApiError('Parçanın görüntü ölçeği okunamadı.')
            perspective = bool(call(view, 'HasPerspective'))
            camera = get(view, 'Camera')
            utility = call(self.app, 'GetMathUtility')
            if utility is None:
                raise ApiError('SolidWorks görünüm geri yükleme API’sine erişilemiyor.')
            snapshot = (orientation, translation, scale, perspective)
            manager = get(model, 'SelectionManager')
            call(manager, 'SuspendSelectionList')
            suspended = True
            yield
        finally:
            failures = []
            try:
                if snapshot is not None:
                    orientation, translation, scale, perspective = snapshot
                    view = get(model, 'ActiveView')
                    if camera is not None:
                        _put(view, 'Camera', camera)
                    if bool(call(view, 'HasPerspective')) != perspective:
                        call(view, 'AddPerspective' if perspective else 'RemovePerspective')
                    _put(view, 'Orientation3', call(utility, 'CreateTransform', variant(0x2005, orientation)))
                    _put(view, 'Scale2', scale)
                    _put(view, 'Translation3', call(utility, 'CreateVector', variant(0x2005, translation)))
                    if (not _same(_array(get(view, 'Orientation3'), 16), orientation)
                        or not _same(_array(get(view, 'Translation3'), 3), translation)
                        or not math.isclose(float(get(view, 'Scale2')), scale, rel_tol=1e-8)
                        or bool(call(view, 'HasPerspective')) != perspective):
                        raise RestoreError()
                    call(model, 'GraphicsRedraw2')
            except Exception:
                failures.append('Parçanın önceki görünümü geri getirilemedi; modeli kontrol edin, kaydetmeyin.')
            try:
                if suspended:
                    call(manager, 'ResumeSelectionList2', False)
            except Exception:
                failures.append('Parçanın önceki seçimi geri getirilemedi.')
            try:
                if visible is not None:
                    _put(model, 'Visible', visible)
                    if bool(get(model, 'Visible')) != visible:
                        raise RestoreError()
            except Exception:
                failures.append('Parçanın önceki pencere görünürlüğü geri getirilemedi.')
            model = view = manager = camera = utility = None
            if failures:
                raise RestoreError(' '.join(failures))

    def picture(self, part, stop_event=None):
        model = view = None
        owned_key = path_key(str(Path(part.path).resolve()))
        try:
            model = self.document(part.path)
            if call(model, 'GetType') != self.c('swDocPART'):
                raise ApiError('BOM görsel kaynağı bir parça değil.')
            # Snapshot BEFORE switching configuration; restore AFTER switching back.
            with self.view_state(model), self.configuration(model, part.configuration):
                if self.rebuild_pending(model) is not False:
                    raise ApiError('Parça yeniden oluşturulmalı; eski geometri görseli eklenmedi.')
                _check_cancel(stop_event)
                call(model, 'ShowNamedView2', '', self.c('swIsometricView'))
                view = get(model, 'ActiveView')
                if call(view, 'HasPerspective'):
                    call(view, 'RemovePerspective')
                if call(view, 'HasPerspective') or not _isometric(view, call(self.app, 'GetMathUtility')):
                    raise ApiError('Parçanın izometrik görünüşü doğrulanamadı; farklı bir görünüş eklenmedi.')
                call(model, 'ViewZoomtofit2')
                call(model, 'GraphicsRedraw2')
                with TemporaryDirectory(prefix='gokworks-bom-image-') as folder:
                    bitmap = Path(folder)/'isometric.bmp'
                    if not call(model, 'SaveBMP', str(bitmap), 512, 384) or not bitmap.is_file():
                        raise ApiError('SolidWorks izometrik görüntüyü oluşturamadı.')
                    _check_cancel(stop_event)
                    return Preview(_png(bitmap), 'İzometrik · '+part.configuration)
        finally:
            model = view = None
            # Keep large BOMs bounded; never close pre-existing user documents.
            if owned_key in self.owned:
                try:
                    call(self.app, 'CloseDoc', self.owned[owned_key])
                    del self.owned[owned_key]
                except Exception as error:
                    raise RestoreError('Görsel için açılan parça kapatılamadı.') from error


def collect_previews(result, stop_event=None, *, progress=None, session_factory=Session):
    """One image per exact file/configuration; missing images retain every BOM row."""
    previews = {}
    _check_cancel(stop_event)
    if not result.parts:
        return previews
    try:
        with session_factory() as session:
            for index, part in enumerate(result.parts, 1):
                _check_cancel(stop_event)
                key = sw._part_key(part.path, part.configuration)
                if key in previews:
                    continue
                if progress:
                    progress(f'İzometrik görseller · {index}/{len(result.parts)} · {part.name}')
                try:
                    previews[key] = session.picture(part, stop_event)
                except (Cancelled, RestoreError):
                    raise
                except Exception as error:
                    previews[key] = Preview(None, 'Görsel alınamadı: '+str(error)[:500])
    except (Cancelled, RestoreError):
        raise
    except Exception as error:
        note = 'SolidWorks görseli alınamadı: '+str(error)[:500]
        for part in result.parts:
            previews.setdefault(sw._part_key(part.path, part.configuration), Preview(None, note))
    _check_cancel(stop_event)
    return previews
