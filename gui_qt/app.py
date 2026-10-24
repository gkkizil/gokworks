"""GOKWORKS Qt desktop shell: persistent pages, asynchronous jobs and safe close."""

import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize, QEvent
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QFrame, QStackedWidget, QProgressBar, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QToolButton, QCheckBox, QToolBar, QDockWidget, QMenu, QSizePolicy)
from .settings import SettingsStore
from .workers import JobManager
from .workspace import ModuleBrowser, WORKSPACES
from .theme import apply_theme, COLORS
from .icons import BrandLogo, ASSETS, icon, set_application_identity
from .components import label, button, scroll, show_details, Disclosure, card
from . import services
from solidworks import diagnostics
from modules.pdf.ui import PdfPage
from modules.dxf_dwg.ui import DxfDwgPage
from modules.bom.ui import BomPage
from modules.naming.ui import NamingPage
from modules.k_factor.ui import KrPage
from modules.bolt.ui import BoltPage
from modules.bolt_torque.ui import TorquePage
from modules.weight.ui import WeightPage
from modules.iso_fits.ui import IsoPage
from modules.geometric_tolerances.ui import GdtPage
from modules.tolerance_stack.ui import ToleranceStackPage
from modules.nesting.ui import NestingPage
from modules.cad_converter.ui import CadConverterPage
from modules.profile_cutting.ui import ProfileCuttingPage


MODULES = (
    ('pdf', 'PDF aktarımı', 'AKTARIM VE MONTAJ'),
    ('dxf_dwg', 'DXF / DWG', 'AKTARIM VE MONTAJ'),
    ('cad_converter', '3D Dönüştürücü', 'AKTARIM VE MONTAJ'),
    ('bom', 'BOM · Ürün ağacı', 'AKTARIM VE MONTAJ'),
    ('naming', 'İsimlendirme aracı', 'AKTARIM VE MONTAJ'),
    ('k_factor', 'K faktörü / yarıçap', 'MÜHENDİSLİK HESAPLARI'),
    ('iso_fits', 'ISO geçme toleransları', 'MÜHENDİSLİK HESAPLARI'),
    ('geometric_tolerances', 'Geometrik toleranslar', 'MÜHENDİSLİK HESAPLARI'),
    ('tolerance_stack', 'Tolerans yığılması', 'MÜHENDİSLİK HESAPLARI'),
    ('bolt', 'Cıvata hesabı', 'MÜHENDİSLİK HESAPLARI'),
    ('bolt_torque', 'Hızlı tork hesabı', 'MÜHENDİSLİK HESAPLARI'),
    ('weight', 'Ağırlık hesabı', 'MÜHENDİSLİK HESAPLARI'),
    ('nesting', 'Nesting · Sac maliyeti', 'MÜHENDİSLİK HESAPLARI'),
    ('profile_cutting', 'Profil kesim', 'MÜHENDİSLİK HESAPLARI'),
)


class MainWindow(QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__()
        self.setWindowTitle('GOKWORKS · Mühendislik araçları')
        self.setWindowIcon(QIcon(str(ASSETS / 'GOK_app_windows.ico')))
        self.settings = SettingsStore(parent=self) if settings_path is None else SettingsStore(settings_path, self)
        self.appearance = str(self.settings.get('appearance', 'dark'))
        if self.appearance not in COLORS:
            self.appearance = 'dark'
        self.jobs = JobManager(self)
        self.closing = False
        self.busy = False
        self.pages = {}
        self.navigation = {}
        self.setMinimumSize(820, 560)
        self.resize(1360, 900)
        container = QWidget()
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.browser = ModuleBrowser(MODULES,self.settings,self.navigate,self.toggle_sidebar,
                                     self.show_settings,self.show_licenses,self.set_theme)
        self.sidebar = self.browser; self.sidebar_collapsed = False
        self.navigation = self.browser.buttons
        self.logo = self.browser.logo; self.brand_label = self.browser.caption
        self.menu_toggle = self.browser.menu_toggle
        self.section_labels = [group.toggle for group in self.browser.groups.values()]
        self.settings_button = self.browser.settings_button; self.licenses_button = self.browser.licenses_button
        self.theme_picker = self.browser.theme_picker
        self.stack = QStackedWidget()
        outer.addWidget(self.sidebar)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(container)
        self.create_workbench_chrome()
        self.global_status = label('Hazır', 'muted', wrap=False)
        self.global_status.setMaximumWidth(600)
        self.statusBar().addWidget(self.global_status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.connection_button = button('SolidWorks · Bağlantıyı kontrol et', self.check_connection)
        self.statusBar().addPermanentWidget(self.connection_button)
        # Build once; navigation only changes the visible page. No rebuild/COM on activation.
        factories = dict(pdf=lambda: PdfPage(self), dxf_dwg=lambda: DxfDwgPage(self),
                         cad_converter=lambda: CadConverterPage(self),
                         bom=lambda: BomPage(self), naming=lambda: NamingPage(self), k_factor=lambda: KrPage(self),
                         iso_fits=lambda: IsoPage(self), geometric_tolerances=lambda: GdtPage(self),
                         tolerance_stack=lambda: ToleranceStackPage(self),
                         bolt=lambda: BoltPage(self), bolt_torque=lambda: TorquePage(self),
                         weight=lambda: WeightPage(self), nesting=lambda: NestingPage(self),
                         profile_cutting=lambda: ProfileCuttingPage(self))
        for mode, factory in factories.items():
            page = factory()
            page.statusChanged.connect(lambda text, error, page=page: self.page_status(page, text, error))
            page.progressChanged.connect(self.set_progress)
            self.pages[mode] = page
            self.stack.addWidget(page)
        self.jobs.busyChanged.connect(self.job_state_changed)
        self.jobs.finished.connect(self.finished_job)
        self.set_theme(self.appearance)
        initial = self.settings.get('mode', 'pdf')
        self.navigate(initial if isinstance(initial, str) and initial in self.pages else 'pdf')
        self.restore_window()
        self.set_sidebar_collapsed(self.settings.get('sidebar_collapsed',False) is True)
        QShortcut(QKeySequence('Ctrl+,'), self, activated=self.show_settings)
        QShortcut(QKeySequence('Ctrl+B'),self,activated=self.toggle_sidebar)
        QShortcut(QKeySequence('Ctrl+K'),self,activated=self.focus_module_search)

    def toggle_sidebar(self):
        self.set_sidebar_collapsed(not self.sidebar_collapsed)

    def set_sidebar_collapsed(self, collapsed):
        self.sidebar_collapsed = bool(collapsed)
        self.browser.set_collapsed(self.sidebar_collapsed)
        self.settings.set('sidebar_collapsed',self.sidebar_collapsed)

    def create_workbench_chrome(self):
        self.workbench_bar = QToolBar('Çalışma alanı',self)
        self.workbench_bar.setObjectName('applicationTools'); self.workbench_bar.setMovable(False)
        self.workbench_bar.setFloatable(False); self.workbench_bar.setIconSize(QSize(16,16))
        self.addToolBar(Qt.TopToolBarArea,self.workbench_bar)
        self.workbench_bar.addWidget(label('ÇALIŞMA ALANI','muted'))
        self.workspace_picker = QComboBox(); self.workspace_picker.setMinimumWidth(138)
        self.workspace_picker.setAccessibleName('Mühendislik çalışma alanı')
        for title,_ in WORKSPACES:self.workspace_picker.addItem(title,title)
        self.last_workspaces = {}
        self.workspace_picker.currentIndexChanged.connect(self.change_workspace)
        self.workbench_bar.addWidget(self.workspace_picker)
        self.workbench_bar.addSeparator()
        self.workspace_context = label('','muted',wrap=False)
        self.workbench_bar.addWidget(self.workspace_context)
        space=QWidget();space.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        self.workbench_bar.addWidget(space)
        self.inspectors = {}; self._syncing_dock = False
        self.inspector_requested = self.settings.get('inspector_visible',True) is not False
        self.property_dock = QDockWidget('ÖZELLİKLER',self)
        self.property_dock.setObjectName('propertiesDock');self.property_dock.setMinimumWidth(248)
        self.property_dock.installEventFilter(self)
        self.property_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        self.inspector_stack = QStackedWidget();self.inspector_stack.setMinimumWidth(0)
        self.property_dock.setWidget(self.inspector_stack)
        self.addDockWidget(Qt.RightDockWidgetArea,self.property_dock)
        self.property_dock.hide()
        self.property_dock.visibilityChanged.connect(self.inspector_visibility_changed)
        self.inspector_button = button('Özellikler',self.toggle_inspector)
        self.inspector_button.setCheckable(True);self.inspector_button.setToolTip('Bağlamsal özellikler panelini göster / gizle')
        self.inspector_action=self.workbench_bar.addWidget(self.inspector_button)
        view = QToolButton();view.setText('Görünüm');view.setPopupMode(QToolButton.InstantPopup)
        view_menu=QMenu(view)
        view_menu.addAction('Sol gezgini daralt / genişlet · Ctrl+B',self.toggle_sidebar)
        view_menu.addAction('Araç bul · Ctrl+K',self.focus_module_search)
        view_menu.addSeparator()
        view_menu.addAction('Koyu tema',lambda:self.set_theme('dark'))
        view_menu.addAction('Açık tema',lambda:self.set_theme('light'))
        view_menu.addSeparator();view_menu.addAction('Uygulama ayarları…',self.show_settings)
        view.setMenu(view_menu);self.workbench_bar.addWidget(view)
        self.workbench_bar.addAction('Lisanslar',self.show_licenses)

    def change_workspace(self):
        group=self.workspace_picker.currentData()
        modes=dict(WORKSPACES).get(group,())
        if modes:self.navigate(self.last_workspaces.get(group,modes[0]))

    def focus_module_search(self):
        if self.sidebar_collapsed:self.set_sidebar_collapsed(False)
        self.browser.search.setFocus();self.browser.search.selectAll()

    def register_inspector(self,mode,widget):
        self.inspectors[mode]=widget;self.inspector_stack.addWidget(widget)
        self.jobs.busyChanged.connect(lambda busy:widget.setEnabled(not busy))

    def inspector_visibility_changed(self,visible):
        self.inspector_button.setChecked(visible)
        if not self._syncing_dock and not self.closing and self.isVisible() and getattr(self,'mode',None) in self.inspectors:
            self.inspector_requested=visible;self.settings.set('inspector_visible',visible)

    def update_inspector(self):
        if self._syncing_dock:return
        self._syncing_dock=True
        try:
            widget=self.inspectors.get(getattr(self,'mode',None))
            self.inspector_button.setEnabled(widget is not None)
            self.inspector_action.setVisible(widget is not None)
            if widget is not None:self.inspector_stack.setCurrentWidget(widget)
            show=widget is not None and self.inspector_requested and (self.width()>=1320 or self.property_dock.isFloating())
            was_visible=self.property_dock.isVisible()
            self.property_dock.setVisible(show);self.inspector_button.setChecked(show)
            if show and not was_visible and not self.property_dock.isFloating():
                width=self.settings.get('inspector_width',286)
                if not isinstance(width,int) or isinstance(width,bool):width=286
                self.resizeDocks([self.property_dock],[max(248,min(width,self.width()//3))],Qt.Horizontal)
        finally:self._syncing_dock=False

    def eventFilter(self,watched,event):
        if watched is getattr(self,'property_dock',None) and event.type()==QEvent.Resize:
            if not self._syncing_dock and watched.isVisible() and not watched.isFloating():
                self.settings.set('inspector_width',watched.width())
        return super().eventFilter(watched,event)

    def toggle_inspector(self):
        if getattr(self,'mode',None) not in self.inspectors:return
        self.inspector_requested=not self.property_dock.isVisible()
        if self.inspector_requested and self.width()<1320:self.property_dock.setFloating(True)
        self.settings.set('inspector_visible',self.inspector_requested);self.update_inspector()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'property_dock'):self.update_inspector()

    def restore_window(self):
        geometry = self.settings.qt.value('window/geometry')
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except (TypeError, ValueError):
                # A damaged INI value must not prevent the JSON/CAD workflow opening.
                pass
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            self.resize(min(self.width(), available.width()), min(self.height(), available.height()))
            # Reconnects or unplugged monitors must not leave the saved window unreachable.
            if not any(s.availableGeometry().intersects(self.frameGeometry()) for s in QGuiApplication.screens()):
                self.move(available.topLeft())

    def navigate(self, mode):
        if mode not in self.pages:
            return
        self.mode = mode
        self.stack.setCurrentWidget(self.pages[mode])
        for key, nav in self.navigation.items():
            nav.setChecked(key == mode)
        self.settings.set('mode', mode)
        group=self.browser.group_for_mode[mode];self.last_workspaces[group]=mode
        blocked=self.workspace_picker.blockSignals(True)
        self.workspace_picker.setCurrentIndex(self.workspace_picker.findData(group))
        self.workspace_picker.blockSignals(blocked)
        self.workspace_context.setText(group+' / '+dict((key,title) for key,title,_ in MODULES)[mode])
        if self.browser.buttons[mode].isHidden() and self.browser.search.text():self.browser.search.clear()
        self.browser.activate(mode)
        for key,nav in self.navigation.items():nav.setIcon(icon(key,COLORS[self.appearance]['accent' if key==mode else 'muted']))
        self.update_inspector()
        owner = self.jobs.owner
        page = owner if owner in self.pages.values() else self.pages[mode]
        self.show_status(page.status_text,page.status.property('role')=='error')

    def set_theme(self, appearance):
        if appearance not in COLORS:
            return
        if appearance == self.appearance and getattr(self,'_theme_applied',False):
            return
        self.appearance = appearance
        if hasattr(self,'theme_picker'):
            blocked = self.theme_picker.blockSignals(True)
            self.theme_picker.setCurrentIndex(0 if appearance == 'dark' else 1)
            self.theme_picker.blockSignals(blocked)
        apply_theme(QApplication.instance(), appearance)
        self.inspector_button.setIcon(icon('inspector',COLORS[appearance]['muted']))
        self.inspector_button.setIconSize(QSize(16,16))
        self.logo.set_appearance(appearance)
        for mode, nav in self.navigation.items():
            nav.setIcon(icon(mode, COLORS[appearance]['accent' if nav.isChecked() else 'muted']))
        for page in self.pages.values():
            page.refresh_command_icons()
            page.theme_changed()
        self.settings.set('appearance', appearance)
        self._theme_applied=True

    def page_status(self, page, text, error):
        if page is self.jobs.owner or self.stack.currentWidget() is page:
            self.show_status(text,error)

    def show_status(self,text,error=False):
        text=str(text)
        self.global_status.setText((text.splitlines() or ['Hazır'])[0][:130])
        self.global_status.setToolTip(text)
        role='error' if error else 'muted'
        if self.global_status.property('role')!=role:
            self.global_status.setProperty('role',role)
            self.global_status.style().unpolish(self.global_status)
            self.global_status.style().polish(self.global_status)

    def set_progress(self, current, total):
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    def job_state_changed(self, busy):
        self.connection_button.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)

    def check_connection(self):
        self.jobs.start(self, services.check_connection)

    def set_busy(self, busy):
        self.busy = busy

    def set_status(self, text, error=False):
        self.show_status(text,error)

    def handle_events(self, events):
        for kind, result in events:
            if kind == 'connection_done':
                if result['connected']:
                    self.connection_button.setText('SolidWorks · ' + result['revision'])
                    self.set_status('Açık SolidWorks oturumuna bağlanıldı.')
                else:
                    self.connection_button.setText('SolidWorks · Bağlantı yok')
                    self.connection_button.setToolTip(result['error'])
                    self.set_status(result['error'], True)
            elif kind == 'job_error':
                self.set_status(result['error'], True)

    def job_finished(self):
        pass

    def finished_job(self):
        if self.closing:
            QTimer.singleShot(0, self.close)

    def show_settings(self):
        dialog=QDialog(self);dialog.setWindowTitle('GOKWORKS · Uygulama ayarları');dialog.resize(480,300)
        layout=QVBoxLayout(dialog);layout.setSpacing(10)
        panel,body=card('Görünüm')
        body.addWidget(label('Tema','muted'))
        appearance=QComboBox();appearance.setObjectName('appearancePreference');appearance.setAccessibleName('Uygulama teması')
        appearance.addItem('Koyu tema','dark');appearance.addItem('Açık tema','light')
        appearance.setCurrentIndex(0 if self.appearance=='dark' else 1)
        appearance.currentIndexChanged.connect(lambda:self.set_theme(appearance.currentData()));body.addWidget(appearance)
        compact=QCheckBox('Sol menüyü simgelere daralt');compact.setObjectName('compactNavigationPreference')
        compact.setChecked(self.sidebar_collapsed);compact.toggled.connect(self.set_sidebar_collapsed);body.addWidget(compact)
        body.addWidget(label('Menüyü Ctrl+B ile de daraltıp genişletebilirsiniz.','muted'));layout.addWidget(panel)
        layout.addWidget(label('Tercihler ve girdiğiniz değerler otomatik kaydedilir.','muted'))
        details=label(f'Ayar dosyası: {self.settings.path}\n\nPencere konumu ve boyutu ayrıca korunur. '
            'SolidWorks araçları açık oturumu kullanır; hesap araçları bağlantı olmadan çalışır. '
            'K/R dosya kaydetme seçimi her açılışta kapalıdır.\n\nArayüz: PySide6 / Qt Widgets.','muted')
        layout.addWidget(Disclosure('Dosya ve çalışma bilgileri',details));layout.addStretch()
        close=QDialogButtonBox(QDialogButtonBox.Close);close.button(QDialogButtonBox.Close).setText('Kapat')
        close.rejected.connect(dialog.reject);layout.addWidget(close)
        try:dialog.exec()
        finally:self.settings.flush();dialog.deleteLater()

    def show_licenses(self):
        from .licenses import LicensesDialog
        dialog = LicensesDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def closeEvent(self, event):
        diagnostics.record(f'gui_close_requested busy={self.jobs.busy} closing={self.closing}')
        if self.jobs.busy:
            event.ignore()
            if not self.closing:
                answer = QMessageBox.question(self, 'İşlem sürüyor',
                    'İşlemi durdurup çıkılsın mı? Geçerli CAD işlemi güvenli biçimde tamamlanana kadar beklenir.',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
                self.closing = True
                owner = self.jobs.owner
                if hasattr(owner, 'pending_apply'):
                    owner.pending_apply = None
                self.jobs.cancel()
            return
        self.settings.qt.setValue('window/geometry', self.saveGeometry())
        self.settings.qt.sync()
        if not self.settings.flush():
            if QMessageBox.warning(self, 'Ayarlar kaydedilemedi', self.settings.last_error + '\nKaydetmeden çıkılsın mı?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                self.closing = False
                event.ignore()
                return
        self.closing = True
        diagnostics.record('gui_close_accepted')
        event.accept()


def create_application(argv=None):
    existing = QApplication.instance()
    if existing is not None and existing.applicationName() == 'GOKWORKS':
        return existing
    set_application_identity()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setApplicationName('GOKWORKS')
    app.setOrganizationName('GOKWORKS')
    app.setStyle('Fusion')
    app.setWindowIcon(QIcon(str(ASSETS / 'GOK_app_windows.ico')))
    return app


def main():
    from solidworks.diagnostics import enable
    from solidworks.process_watch import start_watch
    from .diagnostics import install
    log = enable('gui')
    start_watch(os.getpid(), log, 'gui')
    install()
    app = create_application()
    app.lastWindowClosed.connect(lambda: diagnostics.record('gui_last_window_closed'))
    app.aboutToQuit.connect(lambda: diagnostics.record('gui_about_to_quit'))
    window = MainWindow()
    window.show()
    diagnostics.record('gui_ready')
    result = app.exec()
    diagnostics.record(f'gui_event_loop_returned code={result}')
    return result
