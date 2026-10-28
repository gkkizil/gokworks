"""PDF and sheet-metal exports using the existing file-safe service engines."""

from pathlib import Path
from PySide6.QtCore import Slot

from modules.pdf.process import export_drawings
from modules.dxf_dwg.exporter import export_parts
from gui_qt import services
from gui_qt.components import (BasePage, ValueForm, ResultsPanel, Disclosure, card, button,
                          open_folder, TransferWorkspace, SourceFiles)
from solidworks import diagnostics


class ExportPage(BasePage):
    def __init__(self, context, mode):
        self.mode = mode
        pdf = mode == 'pdf'
        super().__init__(context, 'PDF aktarımı' if pdf else 'DXF / DWG aktarımı',
                         'Teknik resimlerin tüm sayfalarını tek PDF dosyasına aktarın.' if pdf else
                         'Sac parçalarının açınımlarını kalınlıklarına göre düzenleyin.')
        self.scan_button = self.action('Klasörü tara', self.scan)
        self.start_button = self.action('Aktarımı başlat', self.start_export, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.stop_button.setEnabled(False)
        panel, body = card('Kaynak ve çıktı')
        self.form = ValueForm(self.settings, mode + '_')
        self.source = self.form.path('source', 'Kaynak klasör')
        self.output = self.form.path('output', 'Çıktı klasörü')
        if not pdf:
            self.form.combo('format', 'Çıktı türü', ('DXF', 'DWG'), 'DXF')
        self.options_form = ValueForm(self.settings, mode + '_')
        self.options_form.check('recursive', 'Alt klasörleri tara', True)
        self.options_form.check('overwrite', 'Üzerine yaz', False).setToolTip('Mevcut çıktıların üzerine yaz')
        if not pdf:
            self.options_form.check('bend_lines', 'Büküm çizgilerini ekle', False)
            self.options_form.check('group_by_thickness', 'Kalınlığa göre klasörle', True)
        # Keep the original complete value interface used by the service boundary.
        self.form.fields.update(self.options_form.fields)
        self.options_form.changed.connect(self.form.changed)
        body.addWidget(self.form)
        self.form.stack_fields()
        self.options = Disclosure('Aktarım seçenekleri', self.options_form, expanded=True)
        body.addWidget(self.options)
        body.addWidget(button('Çıktıyı aç', lambda: open_folder(self.output.text()) if self.output.text() else None))
        self.controls.extend((self.form, self.options_form))
        self.results = ResultsPanel(empty_hint='Kaynak klasörü seçin, ardından “Klasörü tara” veya aktarım komutunu kullanın.')
        self.results.cleared.connect(lambda:self.set_status('Dosya listesi ve işlem günlüğü temizlendi.'))
        self.source_files = SourceFiles(self.results)
        body.addWidget(self.source_files,1)
        self.splitter = TransferWorkspace(self,panel,self.results)
        self.source_scroll = self.splitter.source_scroll
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()

    def set_busy(self, busy):
        super().set_busy(busy)
        self.results.set_busy(busy)

    def validate(self, *, output=False):
        values = self.form.values()
        if not values['source'].strip():
            raise ValueError('Bir kaynak klasörü seçin.')
        if output and not values['output'].strip():
            raise ValueError('Geçerli bir çıktı klasörü seçin.')
        return values

    def scan(self):
        if not self.can_start():
            return
        try:
            values = self.validate()
        except ValueError as error:
            return self.set_status(error, True)
        self.results.reset()
        mode = self.mode
        self.jobs.start(self, lambda sink, stop: services.scan_files(mode, values['source'], values['recursive'], sink, stop))
        self.set_status('Dosyalar taranıyor…')

    def start_export(self):
        if not self.can_start():
            return
        try:
            values = self.validate(output=True)
        except ValueError as error:
            return self.set_status(error, True)
        self.settings.flush()
        self.results.reset()
        mode = self.mode

        def operation(sink, stop):
            target = Path(values['output'])
            if target.exists() and not target.is_dir():
                raise ValueError('Çıktı konumu bir klasör olmalı.')
            args = (values['source'], values['output'], values['recursive'], values['overwrite'], sink, stop)
            if mode == 'pdf':
                export_drawings(*args)
            else:
                export_parts(*args, formats=(values['format'].lower(),), bend_lines=values['bend_lines'],
                             group_by_thickness=values['group_by_thickness'])

        self.jobs.start(self, operation)
        self.set_status('Aktarım hazırlanıyor…')

    @Slot(object)
    def handle_events(self, events):
        for kind, value in events:
            traced = kind not in ('counts', 'progress', 'total')
            if traced:
                diagnostics.record(f'export_ui_before mode={self.mode} event={kind}')
            if kind == 'files':
                self.results.files(value)
            elif kind == 'current':
                self.results.model.upsert(dict(source=value, status='running'))
            elif kind == 'result':
                if self.mode == 'dxf_dwg' and value.get('thickness_mm') is not None:
                    value = dict(value, detail=f"{value['thickness_mm']:g} mm · {value.get('quantity', 1)} adet · {value['detail']}")
                self.results.result(value)
            elif kind in ('phase', 'log'):
                self.set_status(value)
                if kind == 'log':
                    self.results.append_log(value)
            elif kind == 'progress':
                self.progressChanged.emit(*value)
            elif kind == 'done':
                state = value.get('state')
                if state == 'preview':
                    self.set_status(f"Tarama tamamlandı · {value['total']} dosya. Henüz aktarım yapılmadı.")
                elif state == 'error':
                    self.set_status(value.get('error', 'Aktarım tamamlanamadı.'), True)
                    self.results.append_log(value.get('error', ''))
                    self.results.tabs.setCurrentIndex(1)
                elif state == 'cancelled':
                    self.set_status('İşlem durduruldu; tamamlanan çıktılar korundu.')
                elif state == 'empty':
                    self.set_status('Kaynak klasörde uygun dosya bulunamadı.')
                else:
                    self.set_status(f"Tamamlandı · {value.get('succeeded', 0)} başarılı, {value.get('skipped', 0)} atlanan, {value.get('failed', 0)} hatalı")
            elif kind == 'job_error':
                self.results.append_log(value['error'])
                self.set_status(value['error'], True)
            if traced:
                diagnostics.record(f'export_ui_after mode={self.mode} event={kind}')
