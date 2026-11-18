"""Unsaved-work protection shared by every page that saves a project file.

A page opts in with ``project_title`` and ``project_snapshot()``: a JSON-able picture
of everything its project file would hold. The page is "unsaved" when that picture
differs from the one taken after its last save, load, new project or example, so
any edit (quantity, size, material, geometry, stock, name...) counts, and undoing
back to the saved content does not.

Before New / Open / Example / quit the page asks Save / Continue without saving /
Cancel. "Save" runs the page's own save command; the pending step runs only after
that save really completed (a synchronous save returned clean, or the save job
finished clean). A cancelled save dialog or a failed write keeps the current work.

Recovery: ``write_recovery(path)`` / ``restore_recovery(path)`` let the main window
keep a copy of unsaved work in its own folder (never the user's project file, never
a SolidWorks document) and offer it on the next start.
"""
import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

SAVE, DISCARD, CANCEL = 'save', 'discard', 'cancel'
RECOVERY_FORMAT, RECOVERY_VERSION = 'GOKWORKS-RECOVERY', 1


def _plain(value):
    """Canonical, comparable form of a snapshot (floats rounded to 1e-9, NaN kept apart)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_plain(v) for v in value]
        return sorted(items, key=repr) if isinstance(value, (set, frozenset)) else items
    if isinstance(value, float):
        return repr(value) if not math.isfinite(value) else round(value, 9)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if hasattr(value, '__dataclass_fields__'):
        from dataclasses import asdict
        return _plain(asdict(value))
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def widget_values(root):
    """Values of every editable input under ``root`` (for pages whose model is the form itself)."""
    from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit
    values = []
    for widget in root.findChildren(QWidget):
        name = widget.objectName() or type(widget).__name__
        if isinstance(widget, QLineEdit):
            if widget.isReadOnly() or isinstance(widget.parent(), (QAbstractSpinBox, QComboBox)):
                continue
            values.append((name, widget.text()))
        elif isinstance(widget, QAbstractSpinBox):
            if not widget.isReadOnly():
                values.append((name, widget.text()))
        elif isinstance(widget, QComboBox):
            values.append((name, widget.currentText()))
        elif isinstance(widget, QAbstractButton) and widget.isCheckable():
            values.append((name, widget.isChecked()))
        elif isinstance(widget, (QPlainTextEdit, QTextEdit)) and not widget.isReadOnly():
            values.append((name, widget.toPlainText()))
    return values


def digest(snapshot):
    text = json.dumps(_plain(snapshot), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def current_digest(page):
    try:
        snapshot = page.project_snapshot()
    except Exception as error:      # an unreadable form is an unsaved edit, never "clean"
        snapshot = {'unreadable': type(error).__name__ + ': ' + str(error)}
    return digest(snapshot)


def mark_saved(page):
    page._saved_digest = current_digest(page)


def mark_recovered(page):
    """Recovered work is unsaved until the user saves it somewhere."""
    page._saved_digest = 'recovered'


def has_unsaved(page):
    if not getattr(page, 'project_title', None):
        return False
    saved = getattr(page, '_saved_digest', None)
    return saved is not None and current_digest(page) != saved


def ask(page, action):
    """Save / Continue without saving / Cancel. Separate so tests can answer it."""
    box = QMessageBox(QMessageBox.Warning, f'Kaydedilmemiş {page.project_title.lower()}',
                      f'{page.project_title} üzerinde kaydedilmemiş değişiklikler var. {action} önce kaydedilsin mi?',
                      parent=page)
    save = box.addButton('Kaydet', QMessageBox.AcceptRole)
    discard = box.addButton('Kaydetmeden devam et', QMessageBox.DestructiveRole)
    cancel = box.addButton('İptal', QMessageBox.RejectRole)
    box.setDefaultButton(save); box.setEscapeButton(cancel)
    box.exec()
    clicked = box.clickedButton()
    return SAVE if clicked is save else DISCARD if clicked is discard else CANCEL


def save_then(page, proceed):
    """Run the page's save; ``proceed`` only once the project is really saved.

    Returns True (saved, proceeded), None (save job running; proceeds when it ends
    clean) or False (save dialog cancelled or the write failed: nothing changes).
    """
    page._after_save = proceed
    page.save_project()
    jobs = getattr(page, 'jobs', None)
    if jobs is not None and jobs.busy and jobs.owner is page:
        return None
    page._after_save = None
    if has_unsaved(page):
        return False
    proceed()
    return True


def job_done(page):
    """Called after every job of ``page``: finish a step that waited for a save."""
    proceed, page._after_save = getattr(page, '_after_save', None), None
    if proceed is not None and not has_unsaved(page):
        proceed()


def guard(page, action, proceed):
    """Protect unsaved work before ``proceed`` replaces it. Returns True/None/False as save_then."""
    if not has_unsaved(page):
        proceed(); return True
    choice = ask(page, action)
    if choice == CANCEL:
        return False
    if choice == DISCARD:
        proceed(); return True
    return save_then(page, proceed)


# ----------------------------------------------------------------------------- recovery
def _atomic_write_text(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


class Recovery:
    """One recovery copy per module in ``folder``: the module's own file format plus a manifest."""

    def __init__(self, folder):
        self.folder = Path(folder)

    def _manifest(self, key):
        return self.folder / f'{key}.recovery.json'

    def write(self, key, page):
        if not getattr(page, 'recovery_suffix', None):
            return False
        data = self.folder / f'{key}.recovery{page.recovery_suffix}'
        self.folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=data.name + '.', suffix=page.recovery_suffix, dir=self.folder)
        os.close(fd)
        try:
            page.write_recovery(tmp)            # the module's own (validated) project writer
            os.replace(tmp, data)
        except BaseException:
            try: os.unlink(tmp)
            except OSError: pass
            raise
        manifest = dict(format=RECOVERY_FORMAT, version=RECOVERY_VERSION, module=key, title=page.project_title,
                        file=data.name, saved_at=time.time(), digest=current_digest(page))
        _atomic_write_text(self._manifest(key), json.dumps(manifest, ensure_ascii=False))
        return True

    def discard(self, key):
        for path in self.folder.glob(f'{key}.recovery*'):
            try: path.unlink()
            except OSError: pass

    def available(self, modules):
        """[(key, manifest, data path)] for intact recovery copies; broken ones are skipped, never raised."""
        found = []
        if not self.folder.is_dir():
            return found
        for manifest_path in sorted(self.folder.glob('*.recovery.json')):
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                key = manifest['module']
                data = self.folder / manifest['file']
                if (manifest.get('format') != RECOVERY_FORMAT or manifest.get('version') != RECOVERY_VERSION
                        or key not in modules or Path(manifest['file']).name != manifest['file'] or not data.is_file()):
                    continue
                found.append((key, manifest, data))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return found
