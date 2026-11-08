"""Doğrulanmış hesap anlık görüntüsünden atomik PDF/Excel/JSON raporları."""
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from tempfile import mkstemp
from ..core.service import calculate_project
from ..presentation import result_rows

PHASE_LABELS = {'extend':'İtme','retract':'Çekme','regenerate':'Rejeneratif itme',
                'hold':'Basınçta bekleme','idle':'Boşta'}
SEVERITY_LABELS = {'info':'Bilgi','warning':'Uyarı','critical':'Kritik'}
PHASE_HEADERS = ('Faz adı','Silindir kimliği','Hareket','Süre · s','Gerekli debi · m³/s',
    'Silindir dönüş debisi · m³/s','Gerekli besleme basıncı · Pa','Pompa basıncı · Pa',
    'Pompa debisi · m³/s','Mil gücü · W','Faydalı güç · W','Isı yükü · W','Hız · m/s',
    'Karşılanıyor','Kullanılabilir pompa debisi · m³/s','Silindir basıncı · Pa',
    'Hat kaybı · Pa','Başlangıç konumu · m','Bitiş konumu · m')


def checked_result(project, result):
    """Girdi değiştiyse eski raporun yayımlanmasını önler."""
    if calculate_project(project) != result:
        raise ValueError('Sonuç güncel girdilerle eşleşmiyor; yeniden hesaplayın.')


def _cancel(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('Rapor işlemi iptal edildi.')


def _atomic(path, writer, stop=None):
    target = Path(path)
    fd, name = mkstemp(prefix='.gokworks-hyd-', suffix=target.suffix, dir=target.parent)
    os.close(fd); temporary = Path(name)
    try:
        _cancel(stop); writer(temporary); _cancel(stop)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def export_json(project, result, path, stop=None):
    checked_result(project, result)
    data = dict(schema='gokworks.hydraulic_unit.result', version=1, units='SI',
                generated_at=datetime.now(timezone.utc).isoformat(), project=asdict(project), result=asdict(result))
    def write(p):
        p.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
        json.loads(p.read_text(encoding='utf-8'))
    return _atomic(path, write, stop)


def export_excel(project, result, path, stop=None):
    checked_result(project, result)
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, Alignment
    def write(p):
        book = Workbook(); summary = book.active; summary.title = 'Özet'
        summary.append(('Proje', project.name)); summary.append(('Tarih UTC', datetime.now(timezone.utc).isoformat()))
        summary.append(('Sonuç', 'Kritik kontrol yok' if result.feasible else 'Kritik kontroller var; tasarım onaylanmadı'))
        summary.append(('Alan','Değer','Birim','Yöntem'))
        for row in result_rows(project, result):
            _cancel(stop); summary.append(row)
        phases = book.create_sheet('Fazlar SI'); phases.append(PHASE_HEADERS)
        for phase in result.cycle['phases']:
            _cancel(stop)
            values = asdict(phase)
            values['kind'] = PHASE_LABELS[phase.kind]
            values['feasible'] = 'Evet' if phase.feasible else 'Hayır'
            phases.append(tuple(values.values()))
        inputs = book.create_sheet('Girdiler SI'); inputs.append(('Alan', 'Değer'))
        def flatten(value, prefix=''):
            _cancel(stop)
            if isinstance(value, dict):
                for k, v in value.items(): flatten(v, prefix + '.' + k)
            elif isinstance(value, (tuple, list)):
                for i, v in enumerate(value): flatten(v, prefix + f'[{i}]')
            else: inputs.append((prefix, value))
        flatten(asdict(project))
        notes = book.create_sheet('Uyarılar'); notes.append(('Seviye','Kod','Alan','Açıklama'))
        for issue in result.issues: notes.append((SEVERITY_LABELS[issue.severity],issue.code,issue.field,issue.message))
        for note in result.assumptions: notes.append(('Bilgi','VARSAYIM','',note))
        for sheet in book:
            _cancel(stop)
            sheet.freeze_panes = 'A2'
            for cell in sheet[1]: cell.font = Font(bold=True)
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = min(65, max(16, max(len(str(c.value or '')) for c in col) + 2))
                for cell in col:
                    if isinstance(cell.value, str): cell.data_type = 's'
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
        book.save(p); book.close()
        check = load_workbook(p, read_only=True)
        try:
            if check['Fazlar SI'].max_row != len(project.phases) + 1:
                raise RuntimeError('Excel faz satırları doğrulanamadı.')
        finally: check.close()
    return _atomic(path, write, stop)


def report_html(project, result):
    checked_result(project, result)
    def table(headers, rows):
        content = '<tr>' + ''.join('<th>' + escape(str(h)) + '</th>' for h in headers) + '</tr>'
        for row in rows:
            content += '<tr>' + ''.join('<td>' + escape('Değerlendirilmedi' if v is None else f'{v:.6g}' if isinstance(v,float) else str(v)) + '</td>' for v in row) + '</tr>'
        return '<table width="100%" border="1" cellspacing="0" cellpadding="4">' + content + '</table>'
    html = '<h1>GOKWORKS · Hidrolik Ünite</h1><h2>' + escape(project.name) + '</h2>'
    html += '<p>' + datetime.now(timezone.utc).isoformat() + ' · Girdi kayıtları SI birimindedir.</p>'
    html += '<p><b>' + ('Kritik kontrol yok; üretici/imalat onayı değildir.' if result.feasible else 'Kritik kontroller var. Sağlanamayan fazların ısı/güç sonuçları erişilmiş performans değildir.') + '</b></p>'
    html += table(('Sonuç','Değer','Birim','Yöntem'), result_rows(project, result))
    html += '<h2>Fazlar — SI</h2>' + table(('Ad','Hareket','Süre s','Debi m³/s','Basınç Pa','Mil W','Kayıp W','Karşılanıyor'),
        [(r.name,PHASE_LABELS[r.kind],r.duration,r.flow,r.pressure,r.shaft_power,r.heat_power,
          'Evet' if r.feasible else 'Hayır') for r in result.cycle['phases']])
    html += '<h2>Uyarılar ve varsayımlar</h2>' + ''.join('<p>' + escape(SEVERITY_LABELS[i.severity] + ': ' + i.message) + '</p>' for i in result.issues)
    html += ''.join('<p>' + escape(s) + '</p>' for s in result.assumptions)
    html += '<h2>Girdi kaydı — SI</h2><pre>' + escape(json.dumps(asdict(project), ensure_ascii=False, indent=2)) + '</pre>'
    return html


def _pdf_steps(project, result, path, images=None, stop=None):
    """Her sayfada kontrolü çağırana bırakan atomik PDF üreticisi."""
    from PySide6.QtGui import QPdfWriter, QTextDocument, QPainter, QPageSize, QFont, QPalette, QColor, QAbstractTextDocumentLayout
    from PySide6.QtCore import QRectF, QMarginsF, QUrl, QThread, QSizeF
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError('PDF işlemi etkin QGuiApplication ana iş parçacığında çalışmalı.')
    _cancel(stop)
    content = report_html(project, result)
    if images is None:
        from .plots import cycle_images
        images = cycle_images(project,result)
    target = Path(path)
    fd, name = mkstemp(prefix='.gokworks-hyd-', suffix='.pdf', dir=target.parent)
    os.close(fd); temporary = Path(name)
    writer = None; painter = None
    try:
        writer = QPdfWriter(str(temporary)); writer.setPageSize(QPageSize(QPageSize.A4)); writer.setResolution(96)
        writer.setPageMargins(QMarginsF(12,12,12,12)); writer.setTitle(project.name)
        doc = QTextDocument(); doc.setDefaultFont(QFont('DejaVu Sans', 9))
        doc.setDefaultStyleSheet('body, td, th, p {color:#111111} table {font-size:9pt;} pre {font-size:8pt;}')
        html = content
        if images:
            html += '<h2 style="page-break-before:always">Çevrim grafikleri</h2>'
        for i, img in enumerate(images):
            doc.addResource(QTextDocument.ImageResource, QUrl(f'chart://{i}'), img)
            height = round(620 * img.height() / img.width())
            title = ('Gerekli basınç','Gerekli debi','Pompa mil gücü')[i] if i < 3 else f'Grafik {i+1}'
            html += f'<p><b>{title}</b><br><img src="chart://{i}" width="620" height="{height}"></p>'
        doc.setHtml(html); doc.setPageSize(QSizeF(writer.width(),writer.height()))
        offsets = range(0, max(1,doc.pageCount()) * writer.height(), writer.height())
        painter = QPainter(writer)
        for page, offset in enumerate(offsets, 1):
            _cancel(stop)
            if offset and not writer.newPage(): raise RuntimeError('PDF sayfası oluşturulamadı.')
            painter.save(); painter.setClipRect(QRectF(0,0,writer.width(),writer.height())); painter.translate(0,-offset)
            ctx = QAbstractTextDocumentLayout.PaintContext(); ctx.clip = QRectF(0,offset,writer.width(),writer.height())
            for role in (QPalette.Text,QPalette.WindowText): ctx.palette.setColor(role,QColor('#111111'))
            doc.documentLayout().draw(painter,ctx); painter.restore()
            yield page, len(offsets)
        painter.end(); painter = None
        writer = None
        data = temporary.read_bytes()
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
            raise RuntimeError('PDF dosyası doğrulanamadı.')
        _cancel(stop); os.replace(temporary,target)
    finally:
        if painter is not None: painter.end()
        writer = None
        temporary.unlink(missing_ok=True)


def export_pdf(project, result, path, images=None, stop=None):
    """CLI/senkron kullanım; GUI için create_pdf_job tercih edilir."""
    for _ in _pdf_steps(project,result,path,images,stop):
        pass
    return Path(path)


def create_pdf_job(project, result, path, images=None, *, parent=None):
    """Ana iş parçacığında sayfa başına QTimer ile ilerleyen, iptal edilebilir iş.

    Dönen QObject: start(), cancel(); progress(int,int), finished(str), failed(str).
    UI widget'ı oluşturmaz; Claude mevcut iş akışına bu işi bağlayabilir.
    """
    import threading
    from PySide6.QtCore import QObject, QTimer, Signal

    class PdfJob(QObject):
        progress = Signal(int,int)
        finished = Signal(str)
        failed = Signal(str)

        def __init__(self):
            super().__init__(parent)
            self.stop = threading.Event(); self.started = False; self.completed = False
            self.steps = _pdf_steps(project,result,path,images,self.stop)
            self.timer = QTimer(self); self.timer.setInterval(0)
            self.timer.timeout.connect(self.advance)
            steps = self.steps
            self.destroyed.connect(lambda: steps.close())

        def start(self):
            if self.started or self.completed: raise RuntimeError('PDF işi yalnız bir kez başlatılabilir.')
            self.started = True; self.timer.start()

        def cancel(self):
            if self.completed: return
            self.completed = True
            self.stop.set()
            self.timer.stop()
            self.steps.close()
            self.failed.emit('PDF işlemi iptal edildi; hedef dosya korunur.')

        def advance(self):
            try:
                current,total = next(self.steps)
                self.progress.emit(current,total)
            except StopIteration:
                self.completed = True; self.timer.stop(); self.finished.emit(str(path))
            except Exception as exc:
                self.completed = True; self.timer.stop(); self.steps.close(); self.failed.emit(str(exc))

    return PdfJob()
