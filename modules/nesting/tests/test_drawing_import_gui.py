"""Framed source option, quantity review and real worker integration."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from .test_nesting_gui import window  # noqa: F401
from .test_drawing_import import drawing
from .test_filename_import_gui import finish
from modules.nesting.import_ui import ImportDialog
from modules.nesting.storage import load_project, save_project


def test_drawing_option_and_review_show_per_part_quantities_and_preserve_geometry(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,(1,7,20)); page=window.pages['nesting']
    def configure(d):
        d.form.set_value('drawing_layout',True)
        assert d.preview_model.index(0,2).data()=='Çizimden'
        assert not d.preview_model.flags(d.preview_model.index(0,2)) & Qt.ItemIsEditable
        d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',configure)
    page.configure_import([path]); finish(window,qtbot)
    entry=page.imports[0]
    assert entry['status']=='review' and not page.project.parts
    page.start_nest(); assert 'henüz hazır değil' in page.status_text
    target=tmp_path/'pending.goknest.json'; save_project(page.project,target,imports=page.imports)
    page.project,_,page.imports=load_project(target,with_imports=True)
    entry=page.imports[0]
    def review(d):
        d.show(); qtbot.wait(30)
        assert [d.drawing_model.index(i,1).data() for i in range(3)]==['1','7','20']
        assert '28 adet' in d.contour_summary.text() and 'çarpılmaz' in d.contour_summary.text()
        assert d.drawing_table.isVisible()
        for theme in ('dark','light'):
            window.set_theme(theme); qtbot.wait(30)
            assert d.drawing_table.viewport().height()>100
            assert d.drawing_toggle.isVisible()
            assert d.buttons.geometry().bottom()<=d.height()
            assert d.size().width()<=d.screen().availableGeometry().width()
        d.submit(); assert d.result()!=QDialog.Accepted
        d.confirm_contours.setChecked(True); d.submit(); return d.result()
    monkeypatch.setattr(ImportDialog,'exec',review)
    page.configure_import([path],defaults=entry['options'],retry_id=entry['id']); finish(window,qtbot)
    assert [p.quantity for p in page.project.parts]==[1,7,20]
    assert all(p.area<1500 for p in page.project.parts)
    assert entry['status']=='success'
    page.set_part_quantity(page.project.parts[1].id,5)
    assert [p.quantity for p in page.project.parts]==[1,5,20]


def test_drawing_review_changes_require_new_confirmation_and_cancel_preserves_project(window,qtbot,tmp_path,monkeypatch):
    path=drawing(tmp_path,(1,)); page=window.pages['nesting']
    page.import_files([path],drawing_layout=True); finish(window,qtbot)
    entry=page.imports[0]; fingerprint=page.project.fingerprint()
    def inspect(d):
        d.confirm_contours.setChecked(True)
        d.form.set_value('drawing_layout',False)
        assert not d.confirm_contours.isChecked()
        d.form.set_value('drawing_layout',True)
        assert '1 adet' in d.contour_summary.text()
        return QDialog.Rejected
    monkeypatch.setattr(ImportDialog,'exec',inspect)
    page.configure_import([path],defaults=entry['options'],retry_id=entry['id'])
    assert page.project.fingerprint()==fingerprint and not window.jobs.busy
