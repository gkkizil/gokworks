"""PDF için statik çevrim grafikleri; UI widget'ı veya QtCharts bağımlılığı yok."""


def cycle_images(project, result):
    """Ana Qt iş parçacığında üç beyaz zeminli basamak grafik görüntüsü üretir."""
    from PySide6.QtGui import QImage, QPainter, QColor, QPen, QFont
    from PySide6.QtCore import QPointF, QRectF
    from ..core.units import convert
    pressure_unit = 'psi' if project.display_units == 'us' else 'bar'
    flow_unit = 'gpm' if project.display_units == 'us' else 'L/min'
    images = []
    definitions = [('pressure','Gerekli basınç','Pa',pressure_unit),
                   ('flow','Gerekli debi','m3/s',flow_unit),('shaft_power','Pompa mil gücü','W','kW')]
    for key, title, source, unit in definitions:
        image = QImage(960,300,QImage.Format_RGB32); image.fill(QColor('white'))
        painter = QPainter(image)
        try:
            painter.setFont(QFont('DejaVu Sans',10)); painter.setPen(QColor('#111111'))
            painter.drawText(QRectF(75,5,850,28),f'{title} · {unit} — nominal faz hesabı')
            values = [convert(getattr(r,key),source,unit) for r in result.cycle['phases']]
            maximum = max(1.,max(values)) * 1.1; duration = result.cycle['duration']
            for i in range(5):
                y = 250-i*50
                painter.setPen(QColor('#dddddd')); painter.drawLine(75,y,930,y)
                painter.setPen(QColor('#111111')); painter.drawText(QRectF(0,y-9,70,22),f'{maximum*i/4:.4g}')
            painter.drawLine(75,50,75,250); painter.drawLine(75,250,930,250)
            painter.drawText(QRectF(75,265,850,25),f'0 s                                                Çevrim süresi: {duration:.6g} s')
            painter.setPen(QPen(QColor('#1767C6'),2)); time = 0.; previous = None
            for phase,value in zip(result.cycle['phases'],values):
                start = 75+855*time/duration; time += phase.duration; end = 75+855*time/duration
                y = 250-200*value/maximum
                if previous is not None: painter.drawLine(QPointF(start,previous),QPointF(start,y))
                painter.drawLine(QPointF(start,y),QPointF(end,y)); previous = y
        finally: painter.end()
        images.append(image)
    return tuple(images)
