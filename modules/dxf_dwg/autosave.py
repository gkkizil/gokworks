"""Explicit native autosave policy shared by preview and selected exports."""
from pathlib import Path

from modules.cad_converter.api import ApiError, RestoreError, call
from .sheetmetal import Session as ReadSession
from . import exporter


class Session(ReadSession):
    save_modified = False

    def save_pending(self, *, extra=()):
        if not self.save_modified:
            return [], []
        try:
            return exporter.save_modified_documents(exporter._late_bound(self.app), extra=extra)
        except exporter.SaveDocumentsError as error:
            self._save_failure = str(error)
            raise ApiError(str(error) + ' Belgeler açık bırakılacak; işlem tamamlanmadı.') from error
        finally:
            extra = ()

    def document(self, path=None):
        # Inventory and programmatic read-only callers retain their old policy.
        # An operation explicitly allowed to save must not open its own source with
        # ReadOnly: rebuild/export can dirty even an initially clean part.
        if self.save_modified and path is not None:
            from modules.cad_converter import api
            path = str(Path(path).resolve())
            if not Path(path).is_file():
                raise FileNotFoundError('Kaynak model bulunamadı: ' + Path(path).name)
            model = call(self.app, 'GetOpenDocumentByName', path)
            if model is None:
                errors, warnings = api.out_int(), api.out_int()
                options = self.c('swOpenDocOptions_Silent') | self.c('swOpenDocOptions_OverrideDefaultLoadLightweight')
                model = call(self.app, 'OpenDoc6', path, self.c('swDocPART'), options, '', errors, warnings)
                key = api.path_key(path)
                self.load_warnings[key] = int(warnings.value)
                if model is not None and not warnings.value & self.c('swFileLoadWarning_AlreadyOpen'):
                    self.owned[key] = call(model, 'GetTitle')
                    if not hasattr(self, '_document_paths'): self._document_paths = {}
                    self._document_paths[key] = path
                if model is None or errors.value:
                    raise ApiError(f'Model açılamadı; SolidWorks kodu {errors.value}.', errors.value, warnings.value)
            model = None
        return super().document(path)

    def _close_document(self, path, *, window_only=False):
        if self.save_modified:
            # On failure/cancellation never enter CloseDoc with dirty documents:
            # it can open the modal "Save Modified Documents" dialog. Do not
            # force-discard or save a model whose configuration failed to restore.
            try:
                app = exporter._late_bound(self.app)
                if getattr(self, '_save_failure', ''):
                    raise ApiError(self._save_failure)
                if hasattr(app, '_FlagAsMethod'): app._FlagAsMethod('GetDocuments')
                for model in exporter._value(app, 'GetDocuments') or ():
                    if exporter._value(model, 'GetSaveFlag'):
                        raise ApiError('Kaydedilmemiş SolidWorks belgesi var.')
            except Exception as error:
                raise RestoreError(f'{error} Kayıt penceresi açılmaması için belgeler açık bırakıldı.') from error
            finally:
                app = model = None
        return super()._close_document(path, window_only=window_only)

    def __exit__(self, kind, error, tb):
        if self.save_modified and isinstance(error, (RestoreError, exporter.SourceRestoreError)):
            self._save_failure = str(error)
        return super().__exit__(kind, error, tb)

