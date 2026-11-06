"""Unicode vector PDF, using the existing Qt dependency only when requested."""
from html import escape
from .geometry import curve_points,guide_label_points

_cli_application=None


def write_pdf(parts,path,result,options,cancel_token=None):
    from .shapes.common import check_cancel
    global _cli_application
    from PySide6.QtCore import QRectF,QMarginsF,QPointF,Qt
    from PySide6.QtGui import (QGuiApplication,QPdfWriter,QPageSize,QPageLayout,QPainter,QFont,
                              QColor,QPen,QPainterPath,QTextDocument)
    if QGuiApplication.instance() is None:
        from threading import current_thread,main_thread
        if current_thread() is not main_thread():raise ValueError('GUI uygulaması olmadan PDF ana iş parçacığında oluşturulmalı.')
        _cli_application=QGuiApplication([])
    writer=QPdfWriter(str(path));writer.setResolution(96)
    writer.setPageSize(QPageSize(QPageSize.A3 if options.page_size=='A3' else QPageSize.A4))
    writer.setPageMargins(QMarginsF(12,12,12,12),QPageLayout.Millimeter)
    writer.setTitle(options.project_name or 'Sac Açınımı');writer.setCreator('GOKWORKS Unfolding '+result.engine_version)
    painter=QPainter(writer)
    if not painter.isActive():raise OSError('PDF çizicisi başlatılamadı.')
    painter.setRenderHint(QPainter.Antialiasing,True);painter.setFont(QFont('Arial',9))
    def view(curves,rect,draw,nominal=()):
        points=[p for curve in (*curves,*nominal) for p in curve_points(curve,.5)]
        if not points:return
        x0=min(p[0] for p in points);x1=max(p[0] for p in points);y0=min(p[1] for p in points);y1=max(p[1] for p in points)
        scale=min((rect.width()-15)/max(x1-x0,1e-9),(rect.height()-15)/max(y1-y0,1e-9))
        def point(p):return QPointF(rect.left()+7+(p[0]-x0)*scale,rect.bottom()-7-(p[1]-y0)*scale)
        draw.setPen(QPen(QColor('#17212b'),.7))
        for index,curve in enumerate((*curves,*nominal)):
            draw.setPen(QPen(QColor('#a65b00'),.7,Qt.DashLine) if index>=len(curves) else QPen(QColor('#17212b'),.7))
            pts=curve_points(curve,.1);path2=QPainterPath(point(pts[0]))
            for p in pts[1:]:path2.lineTo(point(p))
            draw.drawPath(path2)
        return scale,point
    try:
        for index,part in enumerate(parts):
            check_cancel(cancel_token)
            if index and not writer.newPage():raise OSError('PDF sayfası oluşturulamadı.')
            w,h=writer.width(),writer.height();n=result.normalized_inputs;m=part.metrics
            painter.fillRect(QRectF(0,0,w,h),QColor('#ffffff'))
            from .registry import definition
            schema=definition(n['shape_id']).schema(n['variant_id']);names={f.id:f.label for f in schema.fields}
            params='; '.join(f'{names.get(key,key)} = {value:g}' for key,value in n['reference_parameters_mm'].items())
            rows=[('Proje / kod / revizyon',f'{options.project_name} / {options.project_code} / {options.project_revision}'),
                  ('Parça / adet',f'{part.code} / {part.quantity*options.quantity_multiplier}'),
                  ('Hesap / sonuç kimliği',f'{result.calculation_method} / r{result.revision} / {result.input_hash[:16]}'),
                  (f'Giriş ölçüleri (mm/°; {n["source_dimension_reference"]})',params),('Kalınlık / malzeme',f'{n["thickness"]:g} mm / {n["material"]["name"] or "belirtilmedi"}'),
                  ('Alan net / paylı / dikdörtgen (mm²)',f'{m.net_area_mm2:.6f} / {m.cutting_area_mm2:.6f} / {m.rectangle_area_mm2:.6f}'),
                  ('Kesim uzunluğu / kütle',f'{m.cutting_length_mm:.6f} mm / '+(f'{m.mass_kg:.6f} kg' if m.mass_kg is not None else 'hesaplanamadı')),
                  ('Kullanıcı fiyatıyla maliyet',f'{m.material_cost:.6f} {n["material"]["currency"]}' if m.material_cost is not None else 'Fiyat veya hesap girdisi eksik; değerlendirilmedi.'),
                  ('Uyarılar','; '.join(x.message for x in result.warnings if x.part_id in (None,part.id))),
                  ('Yardımcı çizgiler','Numaralı gerçek boylar kesim çizgisi veya uygulanabilir abkant planı değildir.')]
            document=QTextDocument();document.setDefaultFont(QFont('Arial',9))
            document.setDefaultStyleSheet('body {color:#000000;font-family:Arial,sans-serif;font-size:8pt;} h1{font-size:15pt;} td{padding:2px;}')
            # Black text set inline: the app's dark-theme palette must never reach the printed page.
            document.setHtml('<div style="color:#000000"><h1 style="color:#000000">GOKWORKS · Sac Açınımı</h1>'
                '<table style="color:#000000">'+''.join(
                f'<tr><td style="color:#000000"><b>{escape(a)}</b></td><td style="color:#000000">{escape(b)}</td></tr>'
                for a,b in rows)+'</table></div>')
            document.setTextWidth(w);header_height=document.size().height()
            if header_height>h*.52:raise ValueError('PDF başlık/veri metni sayfa alanını aşıyor; daha kısa açıklama kullanın.')
            from PySide6.QtGui import QAbstractTextDocumentLayout,QPalette
            context=QAbstractTextDocumentLayout.PaintContext();context.palette.setColor(QPalette.Text,QColor('#000000'))
            context.clip=QRectF(0,0,w,header_height)
            painter.save();painter.setClipRect(context.clip);document.documentLayout().draw(painter,context);painter.restore()
            top=header_height+18;mini_h=min(120.,(h-top)*.22)
            for i,drawing in enumerate(part.drawing_views):
                painter.drawText(QRectF(i*w/2,top,w/2,18),drawing.label)
                view(drawing.geometry,QRectF(i*w/2,top+20,w/2-10,mini_h),painter)
            top+=mini_h+40
            painter.drawText(QRectF(0,top,w,18),'Açınım · kesim konturu ve ana boyutlar (mm)')
            box=QRectF(0,top+22,w,h-top-105)
            curves=part.geometry_2d.outer+tuple(c for hole in part.geometry_2d.holes for c in hole)
            nominal=part.nominal_geometry_2d
            nominal_curves=nominal.outer+tuple(c for hole in nominal.holes for c in hole) if nominal and options.development=='comparison' else ()
            scale,point=view(curves,box,painter,nominal_curves)
            painter.save();painter.setFont(QFont('Arial',6))
            for color,lines,folds in (('#476f9e',part.construction_lines,False),('#3c8060',part.seams,False),('#a7adb4',part.bending_lines,True)):
                painter.setPen(QPen(QColor(color),.25 if folds else .6,Qt.SolidLine if folds else Qt.DashLine))
                for line,anchor in zip(lines,guide_label_points(lines)):
                    painter.drawLine(point(line.start),point(line.end))
                    # Number the independent G samples. Hundreds of physical
                    # facet IDs at one fan apex would obscure the whole sheet.
                    if line.id and not folds:painter.drawText(point(anchor),line.id)
            painter.restore()
            painter.setPen(QColor('#000000'))
            bounds=m.bounds_mm
            painter.drawText(QRectF(0,h-78,w,20),f'Ana boyutlar: {bounds[2]-bounds[0]:.6f} × {bounds[3]-bounds[1]:.6f} mm')
            painter.drawText(QRectF(0,h-56,w,20),f'Ölçek: sayfaya sığdırıldı; 1:1 değildir (çizim ölçek çarpanı {scale*25.4/96:.6f}).')
            painter.drawText(QRectF(0,h-34,w,20),f'GOKWORKS {result.engine_version} · {options.page_size} · {index+1}/{len(parts)} · orta yüzey / imalat süreci onayı yok')
            lengths=part.true_lengths
            for first in range(0,len(lengths),38):
                check_cancel(cancel_token)
                if not writer.newPage():raise OSError('Gerçek boy listesi PDF sayfası oluşturulamadı.')
                painter.fillRect(QRectF(0,0,w,h),QColor('#ffffff'))
                painter.setPen(QColor('#000000'));painter.setFont(QFont('Arial',10))
                painter.drawText(QRectF(0,0,w,30),f'{part.code} · Gerçek uzunluk listesi · mm')
                painter.drawText(QRectF(0,34,w,30),'G: ana doğru/yardımcı çizgi; abkant programı değildir.')
                for row,record in enumerate(lengths[first:first+38]):
                    painter.drawText(QRectF(0,75+row*21,w,21),f'{record.id}: {record.length_mm:.6f} mm')
            if result.forming_report:
                from .forming.reporting import report_lines
                import math
                summary=QTextDocument();summary.setDefaultFont(QFont('Arial',9))
                summary.setHtml('<div style="color:#000000"><h2>Şekillendirme hesabı · '+escape(part.code)+'</h2>'
                                '<p>Çıktı seçimi: '+escape(options.development)+'</p>'
                                +''.join('<p style="margin:3px 0">'+escape(line)+'</p>' for line in report_lines(result.forming_report,part.id))+'</div>')
                summary.setTextWidth(w);page_height=h-30
                for page in range(max(1,math.ceil(summary.size().height()/page_height))):
                    check_cancel(cancel_token)
                    if not writer.newPage():raise OSError('Şekillendirme raporu sayfası oluşturulamadı.')
                    painter.fillRect(QRectF(0,0,w,h),QColor('#ffffff'))
                    painter.save();painter.setClipRect(QRectF(0,0,w,page_height));painter.translate(0,-page*page_height)
                    ctx=QAbstractTextDocumentLayout.PaintContext();ctx.palette.setColor(QPalette.Text,QColor('#000000'))
                    ctx.clip=QRectF(0,page*page_height,w,page_height);summary.documentLayout().draw(painter,ctx);painter.restore()
    finally:painter.end()
    del painter;del writer
    content=path.read_bytes()
    if not content.startswith(b'%PDF-') or b'%%EOF' not in content[-1024:]:raise ValueError('PDF dosya bütünlüğü denetlenemedi.')
    from PySide6.QtPdf import QPdfDocument
    document=QPdfDocument()
    try:
        if document.load(str(path))!=QPdfDocument.Error.None_:raise ValueError('PDF tekrar açılamadı.')
        text=''.join(document.getAllText(i).text() for i in range(document.pageCount()))
        if document.pageCount()<len(parts) or any(part.code not in text for part in parts):raise ValueError('PDF istenen parça içeriği eksik.')
        if options.project_code and options.project_code not in text:raise ValueError('PDF proje kodu metni doğrulanamadı.')
        if 'sığdırıldı' not in text or '1:1 değildir' not in text:raise ValueError('PDF ölçek bilgisi doğrulanamadı.')
        if result.forming_report and 'Şekillendirme hesabı' not in text:raise ValueError('PDF şekillendirme raporu metni eksik.')
    finally:document.close()
