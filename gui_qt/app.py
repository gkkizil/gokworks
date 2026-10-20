"""GOKWORKS Qt desktop shell: persistent pages, asynchronous jobs and safe close."""

import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QFrame, QStackedWidget, QProgressBar, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox)
from .settings import SettingsStore
from .workers import JobManager
from .theme import apply_theme, COLORS
from .icons import BrandLogo, ASSETS, icon, set_application_identity
from .components import label, button, scroll, show_details
from . import services
from solidworks import diagnostics
from .pages.export import ExportPage
from .pages.bom import BomPage
from .pages.naming import NamingPage
from .pages.kr import KrPage
from .pages.bolt import BoltPage
from .pages.weight import WeightPage
from .pages.iso import IsoPage
from .pages.gdt import GdtPage
from .pages.tolerance_stack import ToleranceStackPage
from .pages.nesting import NestingPage


MODULES = (
    ('pdf', 'PDF aktarımı', 'AKTARIM VE MONTAJ'),
    ('dxf_dwg', 'DXF / DWG', 'AKTARIM VE MONTAJ'),
    ('bom', 'BOM · Ürün ağacı', 'AKTARIM VE MONTAJ'),
    ('naming', 'İsimlendirme aracı', 'AKTARIM VE MONTAJ'),
    ('k_factor', 'K faktörü / yarıçap', 'MÜHENDİSLİK HESAPLARI'),
    ('iso_fits', 'ISO geçme toleransları', 'MÜHENDİSLİK HESAPLARI'),
    ('geometric_tolerances', 'Geometrik toleranslar', 'MÜHENDİSLİK HESAPLARI'),
    ('tolerance_stack', 'Tolerans yığılması', 'MÜHENDİSLİK HESAPLARI'),
    ('bolt', 'Cıvata hesabı', 'MÜHENDİSLİK HESAPLARI'),
    ('weight', 'Ağırlık hesabı', 'MÜHENDİSLİK HESAPLARI'),
    ('nesting', 'Nesting · Sac maliyeti', 'MÜHENDİSLİK HESAPLARI'),
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
        self.sidebar = QFrame()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setFixedWidth(244)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(15, 14, 15, 16)
        self.logo = BrandLogo()
        side.addWidget(self.logo)
        side.addWidget(label('GOKWORKS', 'section'))
        side.addWidget(label('Mühendislik araçları', 'muted'))
        menu = QWidget()
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(0, 12, 0, 0)
        menu_layout.setSpacing(4)
        group = None
        for mode, title, section in MODULES:
            if section != group:
                caption = label(section, 'muted')
                caption.setStyleSheet('font-size:10px; padding-top:12px; padding-bottom:6px;')
                menu_layout.addWidget(caption)
                group = section
            nav = button(title, lambda checked=False, key=mode: self.navigate(key))
            nav.setProperty('nav', True)
            nav.setCheckable(True)
            nav.setIconSize(QSize(21, 21))
            nav.setAccessibleName(title)
            nav.setToolTip(title)
            self.navigation[mode] = nav
            menu_layout.addWidget(nav)
        menu_layout.addStretch()
        menu_scroll = scroll(menu)
        menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side.addWidget(menu_scroll, 1)
        tools = QHBoxLayout()
        tools.addWidget(button('Ayarlar', self.show_settings))
        tools.addWidget(button('Lisanslar', self.show_licenses))
        side.addLayout(tools)
        self.theme_picker = QComboBox()
        self.theme_picker.addItem('Koyu tema', 'dark')
        self.theme_picker.addItem('Açık tema', 'light')
        self.theme_picker.setCurrentIndex(0 if self.appearance == 'dark' else 1)
        self.theme_picker.currentIndexChanged.connect(lambda: self.set_theme(self.theme_picker.currentData()))
        side.addWidget(self.theme_picker)
        self.stack = QStackedWidget()
        outer.addWidget(self.sidebar)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(container)
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
        factories = dict(pdf=lambda: ExportPage(self, 'pdf'), dxf_dwg=lambda: ExportPage(self, 'dxf_dwg'),
                         bom=lambda: BomPage(self), naming=lambda: NamingPage(self), k_factor=lambda: KrPage(self),
                         iso_fits=lambda: IsoPage(self), geometric_tolerances=lambda: GdtPage(self),
                         tolerance_stack=lambda: ToleranceStackPage(self),
                         bolt=lambda: BoltPage(self), weight=lambda: WeightPage(self), nesting=lambda: NestingPage(self))
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
        QShortcut(QKeySequence('Ctrl+,'), self, activated=self.show_settings)

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
        owner = self.jobs.owner
        page = owner if owner in self.pages.values() else self.pages[mode]
        self.global_status.setText(page.status_text or 'Hazır')
        self.global_status.setToolTip(page.status_text)

    def set_theme(self, appearance):
        if appearance not in COLORS:
            return
        self.appearance = appearance
        apply_theme(QApplication.instance(), appearance)
        self.logo.set_appearance(appearance)
        for mode, nav in self.navigation.items():
            nav.setIcon(icon(mode, COLORS[appearance]['accent']))
        for page in self.pages.values():
            page.theme_changed()
        self.settings.set('appearance', appearance)

    def page_status(self, page, text, error):
        if page is self.jobs.owner or self.stack.currentWidget() is page:
            self.global_status.setText(text.splitlines()[0][:130])
            self.global_status.setToolTip(text)

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
        self.global_status.setText(text.splitlines()[0][:130])
        self.global_status.setToolTip(text)

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
        show_details(self, 'Uygulama ayarları',
                     f'Ayar dosyası: {self.settings.path}\n\nKlasörler, işlem seçenekleri ve hesap tercihleri otomatik kaydedilir. '
                     'Mevcut JSON ayarlarınız korunur. Pencere konumu ve boyutu ayrı Qt ayarlarında saklanır.\n\n'
                     'SolidWorks: açık oturum · Windows 10/11 · 2025 SP5\nArayüz: PySide6 / Qt Widgets\n'
                     'K/R: kaydet seçimi her açılışta kapalıdır.\n\nTema seçimini sol panelin altından değiştirebilirsiniz.')

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
