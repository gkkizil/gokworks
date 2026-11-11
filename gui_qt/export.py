"""PDF and sheet-metal exports using the existing file-safe service engines."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout)

from modules.pdf.process import export_drawings
from gui_qt import services
from gui_qt.components import (BasePage, ValueForm, ResultsPanel, Disclosure, button, label,
                          separator, section_header, open_folder, TransferWorkspace, SourceFiles)
from gui_qt.theme import COLORS, SPACING
# Shared widgets now live in gui_qt.components; re-exported for existing imports.
from gui_qt.components import STATUS_TOKENS, StatusDelegate, AdaptiveRow  # noqa: F401
from solidworks import diagnostics

def outcome_text(results, appearance):
    """Rich-text outcome counter: counts in their semantic colour, zeros muted."""
    counts = {key: 0 for key in ('success', 'partial', 'skipped', 'error')}
    for row in results:
        if row.get('status') in counts:
            counts[row['status']] += 1
    colors = COLORS[appearance]
    parts = []
    for key, title in (('success', 'başarılı'), ('partial', 'kısmi'), ('skipped', 'atlanan'), ('error', 'hatalı')):
        if key == 'partial' and not counts[key]:
            continue
        color = colors[STATUS_TOKENS[key]] if counts[key] else colors['muted']
        parts.append(f'<span style="color:{color}"><b>{counts[key]}</b> {title}</span>')
    return f'<span style="color:{colors["muted"]}"> · </span>'.join(parts)


def source_section(title, *trailing):
    """Source-column heading with a little air above, no card frame."""
    header = section_header(title, *trailing)
    header.setContentsMargins(0, SPACING['xs'], 0, 0)
    return header


def export_parts(*args, **kwargs):
    """Keep the callable service boundary without loading DXF on the PDF page."""
    from modules.dxf_dwg.exporter import export_parts as run
    return run(*args, **kwargs)


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
        # Flat source column, top to bottom: Kaynak → Çıktı → Seçenekler →
        # source inventory. Hairline rules separate the groups; no cards.
        panel = QWidget(); panel.setObjectName('transferSource')
        body = QVBoxLayout(panel); body.setContentsMargins(0, 0, SPACING['xs'], 0); body.setSpacing(SPACING['m'])
        self.form = ValueForm(self.settings, mode + '_')
        self.source = self.form.path('source', 'Kaynak klasör')
        self.output_form = ValueForm(self.settings, mode + '_')
        self.output = self.output_form.path('output', 'Çıktı klasörü')
        if not pdf:
            self.output_form.combo('format', 'Çıktı türü', ('DXF', 'DWG'), 'DXF')
        self.options_form = ValueForm(self.settings, mode + '_')
        self.options_form.check('recursive', 'Alt klasörleri tara', True)
        self.options_form.check('overwrite', 'Üzerine yaz', False).setToolTip('Mevcut çıktıların üzerine yaz')
        if not pdf:
            self.options_form.check('bend_lines', 'Büküm çizgilerini ekle', False)
            self.options_form.check('group_by_thickness', 'Kalınlığa göre klasörle', True)
        # Keep the original complete value interface used by the service boundary.
        for subform in (self.output_form, self.options_form):
            self.form.fields.update(subform.fields)
            subform.changed.connect(self.form.changed)
        self.open_output_button = button('Çıktıyı aç', lambda: open_folder(self.output.text()) if self.output.text() else None, flat=True)
        self.open_output_button.setToolTip('Çıktı klasörünü dosya gezgininde aç')
        body.addWidget(source_section('Kaynak'))
        body.addWidget(self.form)
        body.addWidget(separator())
        body.addWidget(source_section('Çıktı', self.open_output_button))
        body.addWidget(self.output_form)
        self.form.stack_fields(); self.output_form.stack_fields()
        body.addWidget(separator())
        self.options = Disclosure('Aktarım seçenekleri', self.options_form, expanded=True)
        self.options.layout().setSpacing(SPACING['xs'])
        self.options_form.form.setSpacing(SPACING['xs'])
        body.addWidget(self.options)
        body.addWidget(separator())
        self.controls.extend((self.form, self.output_form, self.options_form))
        self.results = self.create_results()
        self.results.cleared.connect(lambda:self.set_status('Dosya listesi ve işlem günlüğü temizlendi.'))
        self.status_delegate = StatusDelegate(lambda: self.context.appearance, self.results.table)
        self.results.table.setItemDelegateForColumn(1, self.status_delegate)
        self.results.table.setColumnWidth(1, 140)  # 'Kısmen tamamlandı' fits unelided
        self.outcome = label('', wrap=False); self.outcome.setTextFormat(Qt.RichText)
        self.outcome.setAccessibleName('Aktarım sonucu sayaçları')
        self._dock_outcome()
        for signal in (self.results.model.modelReset, self.results.model.rowsInserted,
                       self.results.model.dataChanged, self.results.cleared):
            signal.connect(self.refresh_outcome)
        self.source_files = SourceFiles(self.results)
        body.addWidget(self.source_files,1)
        self.splitter = TransferWorkspace(self,panel,self.results)
        self.source_scroll = self.splitter.source_scroll
        self.layout.addWidget(self.splitter, 1)
        self.finish_layout()

    def create_results(self):
        return ResultsPanel(empty_hint='Kaynak klasörü seçin, ardından “Klasörü tara” veya aktarım komutunu kullanın.')

    def _dock_outcome(self):
        """Put the coloured outcome counter on the results counter row."""
        layout = self.results.layout
        position = layout.indexOf(self.results.counter)
        layout.removeWidget(self.results.counter)
        self.results.counter.setWordWrap(False)
        # Side by side; stacked when the results pane is narrow.
        self.counter_row = AdaptiveRow(self.results.counter, self.outcome, spacing=SPACING['l'], stretch=0)
        layout.insertWidget(position, self.counter_row)
        self.refresh_outcome()

    def refresh_outcome(self, *args):
        self.outcome.setText(outcome_text(self.results.results, self.context.appearance))
        self.outcome.setVisible(bool(self.results.results))

    def theme_changed(self):
        self.refresh_outcome()
        self.results.table.viewport().update()

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
        self.prepare_export_results()
        mode = self.mode
        extra = self.export_arguments()

        def operation(sink, stop):
            target = Path(values['output'])
            if target.exists() and not target.is_dir():
                raise ValueError('Çıktı konumu bir klasör olmalı.')
            args = (values['source'], values['output'], values['recursive'], values['overwrite'], sink, stop)
            if mode == 'pdf':
                export_drawings(*args)
            else:
                export_parts(*args, formats=(values['format'].lower(),), bend_lines=values['bend_lines'],
                             group_by_thickness=values['group_by_thickness'], **extra)

        self.jobs.start(self, operation)
        self.set_status('Aktarım hazırlanıyor…')

    def export_arguments(self):
        return {}

    def prepare_export_results(self):
        self.results.reset()

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
                self.refresh_outcome()
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
