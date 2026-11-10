"""One operator sheet per step, actual checked geometry and explicit scope."""
from pathlib import Path
import threading
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageSize, QPainter, QPdfWriter
from modules.dxf_dwg.preview.viewer import Camera, raster
from modules.tolerance_stack.storage import atomic_write
from modules.cad_converter.models import checkpoint
from .service import PHASES, STATUS


def export_pdf(plan, result, path, *, overwrite=False, stop=None):
    if result.revision != plan.revision:
        raise ValueError('Plan değişti. PDF’den önce hareket kontrolünü yeniden çalıştırın.')
    def write(temporary):
        pdf = QPdfWriter(str(temporary)); pdf.setResolution(120)
        pdf.setPageSize(QPageSize(QPageSize.A4)); pdf.setTitle('GOKWORKS · Büküm Föyü')
        pdf.setCreator('GOKWORKS · Abkant Simülasyonu')
        painter = QPainter(pdf)
        if not painter.isActive():
            raise OSError('PDF yazıcısı açılamadı.')
        try:
            width, height = pdf.width(), pdf.height()
            scale = width/950
            painter.scale(scale, scale)
            for i, (step, status) in enumerate(zip(plan.steps, result.steps)):
                checkpoint(stop)
                if i:
                    pdf.newPage()
                p = plan.part
                bend = next(b for b in p.bends if b.id == step.bend)
                punch, die = plan.tool(step.punch), plan.tool(step.die)
                channel = next((c for c in die.channels if c.id == step.channel), None)
                y = 12
                def text(value, size=10, colour='#20252b', space=34):
                    nonlocal y
                    painter.setPen(QColor(colour)); painter.setFont(QFont('DejaVu Sans', size))
                    actual = painter.fontMetrics().boundingRect(0, 0, 925, 10000, Qt.TextWordWrap, value).height()+5
                    space = max(space, actual)
                    if y+space > height/scale-10:
                        pdf.newPage(); y = 15
                    rect = QRectF(12, y, 925, space)
                    painter.drawText(rect, Qt.TextWordWrap | Qt.AlignTop, value)
                    y += space
                text('GOKWORKS · ABKANT BÜKÜM FÖYÜ', 17, space=42)
                text(('DEMO · ÖZGÜN ÖRNEK GEOMETRİ · ' if p.demo else '')+f'{p.name} / {p.configuration}', 11, space=48)
                text(f'Malzeme: {p.material}    Sac: {p.thickness:g} mm    Kaynak: {p.source}', space=52)
                text(f'Adım {i+1} / {len(plan.steps)} · {bend.id}', 13, space=44)
                text(f'İç açı: {bend.inside_angle:g}°  |  Dönüş: {bend.turn:g}°  |  Yön: {bend.direction*(-1 if step.reverse else 1):+d}  |  İç R: {bend.radius:g} mm', space=34)
                text(f'Eksen: {bend.start} → {bend.end} mm · Etkin boy: {bend.length:.2f} mm', space=40)
                text(f'Üst bıçak: {punch.maker} / {punch.code} · Uç R: {punch.tip_radius if punch.tip_radius is not None else "bilinmiyor"} mm', space=38)
                text(f'Alt kalıp: {die.maker} / {die.code} · Kanal: {step.channel} · V: {channel.opening if channel else "bilinmiyor"} mm · Çalışma referansı: {channel.center if channel else "bilinmiyor"}', space=44)
                for tool, chosen in ((punch, step.punch_segments), (die, step.die_segments)):
                    segments = tool.segments if chosen is None else chosen
                    desc = '; '.join(f'x={s.start:g}, L={s.length:g}' for s in segments) or 'atanmamış'
                    load = f'{tool.line_load:g} {tool.line_load_unit} (üretici beyanı)' if tool.line_load is not None else 'bilinmiyor'
                    text(f'{tool.code} segmentleri (mm): {desc} · Hat yükü: {load}', space=40)
                text(f'Tutuş: {"ana flanş sabit" if step.fixed_side == "parent" else "karşı taraf sabit"} · Yön: {step.orientation}° · Sıra değişimindeki konumlandırma fiziksel olarak kontrol edilmedi.', space=44)
                frames = [f for f in result.frames if f.step == i]
                frame = status.first_hit or next((f for f in reversed(frames) if f.phase == 'bend'), None)
                if frame:
                    image = raster(frame.mesh, 850, 350, Camera().state(), threading.Event(), (250, 250, 250))
                    painter.drawImage(QRectF(50, y, 850, 350), image); y += 354
                    text(f'Görsel: {PHASES[frame.phase]} · yaklaşık {frame.angle:.2f}° dönüş · {len(frame.hits)} çarpışma çifti', 9, space=32)
                text(STATUS[status.status], 12, '#b42318' if status.status == 'collision' else '#795200' if status.status == 'unknown' else '#195b42', space=38)
                if status.first_hit:
                    f = status.first_hit
                    text(f'İlk çarpışma: {PHASES[f.phase]} / {f.angle:.2f}° · '+', '.join(' ↔ '.join(h.pair)+f' @ {tuple(round(v, 2) for v in h.location)} mm' for h in f.hits), 9, space=60)
                text(f'{status.samples} katı poz kontrolü · Çiftler: '+', '.join(status.pairs), 9, space=34)
                text('Kontrol notları: '+' '.join(status.notes), 8, space=96)
                text('Kapsam dışı: '+'; '.join(result.excluded), 8, space=65)
                text(f'Ölçü kaynağı: {bend.provenance}. Proses iç R tahmini: bilinmiyor. Takım kesiti: {punch.source} / {die.source}.', 8, space=55)
                text('Geometrik hava bükümü incelemesidir. Gerçek tezgâh kurulumu, takım bağlantısı ve operatör doğrulaması ayrıca yapılır. CNC strok veya üretim uygunluğu onayı içermez.', 8, space=65)
        finally:
            painter.end()
    return atomic_write(Path(path), write, overwrite=overwrite, stop=stop)
