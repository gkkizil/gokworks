from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QLabel,QPushButton

from gui_qt.about import AboutDialog,ContactDialog
from shared.app_info import AUTHOR,EMAIL,LINKEDIN_URL,GITHUB_URL,COPYRIGHT,DISCLAIMER
from test_fusion_workbench import window  # noqa: F401


def test_main_entries_are_about_and_contact_without_a_license_entry(window,monkeypatch):
    opened=[]
    def about(dialog):opened.append(dialog.windowTitle());return QDialog.Rejected
    monkeypatch.setattr(AboutDialog,'exec',about);monkeypatch.setattr(ContactDialog,'exec',about)
    assert window.about_button.text()=='Hakkında' and window.contact_button.text()=='İletişim'
    assert not any(b.text()=='Lisanslar' for b in window.findChildren(QPushButton))
    window.about_button.click();window.contact_button.click()
    actions=[a for a in window.workbench_bar.actions() if a.text()=='Hakkında']
    assert len(actions)==1 and not any(a.text()=='Lisanslar' for a in window.workbench_bar.actions())
    actions[0].trigger()
    assert opened==['GOKWORKS · Hakkında','GOKWORKS · İletişim','GOKWORKS · Hakkında']
    assert window.browser.footer.layout().indexOf(window.contact_button)>=0


def test_about_has_exact_requested_text_and_no_license_links(window,qtbot):
    dialog=AboutDialog(window);qtbot.addWidget(dialog);dialog.show()
    assert dialog.developer.text()==AUTHOR and dialog.disclaimer.text()==DISCLAIMER
    assert dialog.version.text() and any(label.text()==COPYRIGHT for label in dialog.findChildren(QLabel))
    assert not any('lisans' in b.text().lower() or 'bildirim' in b.text().lower() for b in dialog.findChildren(QPushButton))
    assert not hasattr(window,'show_licenses')
    for theme in ('dark','light'):
        window.set_theme(theme);dialog.resize(400,360);qtbot.wait(30)
        close=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Kapat')
        assert close.isVisible() and dialog.rect().contains(close.geometry())


def test_contact_links_open_the_exact_email_and_linkedin_addresses(window,qtbot,monkeypatch):
    opened=[]
    monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:opened.append(bytes(url.toEncoded()).decode()) or True)
    dialog=ContactDialog(window);qtbot.addWidget(dialog);dialog.show()
    assert EMAIL in dialog.email.text()
    dialog.email.linkActivated.emit('mailto:'+EMAIL);dialog.linkedin.linkActivated.emit(LINKEDIN_URL)
    about=AboutDialog(window);qtbot.addWidget(about);about.github.linkActivated.emit(GITHUB_URL)
    assert opened==['mailto:'+EMAIL,LINKEDIN_URL,GITHUB_URL]


def test_about_and_contact_do_not_load_engineering_modules(window,monkeypatch):
    loaded=tuple(window.pages.loaded_values())
    monkeypatch.setattr(AboutDialog,'exec',lambda self:QDialog.Rejected)
    monkeypatch.setattr(ContactDialog,'exec',lambda self:QDialog.Rejected)
    window.show_about();window.show_contact()
    assert tuple(window.pages.loaded_values())==loaded
