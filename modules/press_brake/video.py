"""Animation export: the checked frames, rendered off-screen, encoded with Qt Multimedia (no extra dependency).

Frames are drawn in the worker with the same software rasterizer as the PDF; encoding
runs on the GUI thread through QMediaRecorder (H.264 where the platform offers it,
otherwise MPEG-4 Part 2) and is written to a temporary file that replaces the target
only when the recording finished.
"""
import os
from pathlib import Path
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from modules.cad_converter.models import checkpoint
from modules.dxf_dwg.preview.viewer import raster
from .service import PHASES, STATUS
from .viewer import AXIS, HIT, LEGEND, projector

WIDTH, HEIGHT = 1280, 720
BACKGROUND = ((246, 247, 249), (222, 226, 232))
FOOTER = 'GOKWORKS · Abkant geometrik hareket kontrolü · üretim onayı değildir'


def caption(plan, frame):
    text = f'Adım {frame.step+1}/{len(plan.steps)} · {plan.steps[frame.step].bend} · {PHASES[frame.phase]} · dönüş {frame.angle:.1f}°'
    return text.replace('.', ',')+(' · ✕ ÇARPIŞMA' if frame.hits else '')


def render_frame(plan, result, frame, state, stop, width=WIDTH, height=HEIGHT):
    image = raster(frame.mesh, width, height, state, stop, BACKGROUND)
    if image is None:   # only when stopped
        checkpoint(stop); raise RuntimeError('Video karesi çizilemedi.')
    image = image.convertToFormat(QImage.Format_ARGB32)
    painter = QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
    project = projector(frame.mesh, state, width, height)
    a, b = project(frame.axis[0]), project(frame.axis[1])
    painter.setPen(QPen(QColor(AXIS), 3, Qt.DashLine)); painter.drawLine(a, b)
    for hit in frame.hits:
        p = project(hit.location); painter.setPen(QPen(QColor(HIT), 3)); painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(p, 13, 13); painter.drawLine(p+QPointF(-19, 0), p+QPointF(19, 0)); painter.drawLine(p+QPointF(0, -19), p+QPointF(0, 19))
    font = QFont('DejaVu Sans'); font.setPixelSize(22); font.setBold(True); painter.setFont(font)
    text = caption(plan, frame); box = QRectF(20, 18, painter.fontMetrics().horizontalAdvance(text)+36, 44)
    accent = QColor(HIT) if frame.hits else QColor('#56C08D') if result.steps[frame.step].status == 'clear' else QColor(AXIS)
    painter.setPen(QPen(accent, 2)); painter.setBrush(QColor(255, 255, 255, 225)); painter.drawRoundedRect(box, 7, 7)
    painter.setPen(QColor('#1F2328')); painter.drawText(box.adjusted(18, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
    font.setPixelSize(15); font.setBold(False); painter.setFont(font); metrics = painter.fontMetrics()
    x = 20
    for name, colour in LEGEND:
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(colour)); painter.drawRoundedRect(QRectF(x, height-66, 14, 14), 3, 3)
        painter.setPen(QColor('#1F2328')); painter.drawText(QPointF(x+20, height-54), name); x += metrics.horizontalAdvance(name)+44
    painter.setPen(QColor('#4B525C'))   # own line under the legend: never overlaps it
    footer = metrics.elidedText(STATUS[result.status]+' · '+FOOTER, Qt.ElideRight, width-40)
    painter.drawText(QRectF(20, height-36, width-40, 24), Qt.AlignLeft | Qt.AlignVCenter, footer)
    painter.end()
    return image


def render_frames(plan, result, state, stop, progress=None):
    """PNG bytes per checked frame, in playback order (lossless; decoded again for encoding)."""
    frames = []
    for i, frame in enumerate(result.frames):
        checkpoint(stop)
        image = render_frame(plan, result, frame, state, stop)
        data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.WriteOnly); image.save(buffer, 'PNG'); buffer.close()
        frames.append(bytes(data))
        if progress:
            progress(i+1, len(result.frames))
    if not frames:
        raise ValueError('Kaydedilecek kare yok; önce hareketi kontrol edin.')
    return frames


def video_codec():
    from PySide6.QtMultimedia import QMediaFormat
    supported = QMediaFormat(QMediaFormat.MPEG4).supportedVideoCodecs(QMediaFormat.Encode)
    for codec in (QMediaFormat.VideoCodec.H264, QMediaFormat.VideoCodec.MPEG4):
        if codec in supported:
            return codec
    return None


class VideoWriter(QObject):
    """Feeds PNG frames to QMediaRecorder on the GUI thread; emits finished(path) or failed(message)."""
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, frames, path, fps, parent=None):
        super().__init__(parent)
        from PySide6.QtMultimedia import QMediaCaptureSession, QMediaFormat, QMediaRecorder, QVideoFrameInput
        self.frames, self.fps, self.index, self.done = frames, max(1, int(fps)), 0, False
        self.path = Path(path); self.temporary = self.path.with_name(f'.{self.path.stem}.{os.getpid()}.kayit.mp4')
        codec = video_codec()
        if codec is None:
            raise ValueError('Bu sistemde MP4 video kodlayıcısı bulunamadı.')
        self.input = QVideoFrameInput(); self.session = QMediaCaptureSession(); self.session.setVideoFrameInput(self.input)
        self.recorder = QMediaRecorder(); self.session.setRecorder(self.recorder)
        media = QMediaFormat(QMediaFormat.MPEG4); media.setVideoCodec(codec); self.recorder.setMediaFormat(media)
        self.recorder.setVideoResolution(WIDTH, HEIGHT); self.recorder.setVideoFrameRate(self.fps)
        self.recorder.setQuality(QMediaRecorder.VeryHighQuality)
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self.temporary)))
        self.input.readyToSendVideoFrame.connect(self.send)
        self.recorder.recorderStateChanged.connect(self.state_changed)
        self.recorder.errorOccurred.connect(lambda error, message: self.fail(message or 'Video kaydı başarısız.'))
        self.timeout = QTimer(self); self.timeout.setSingleShot(True); self.timeout.timeout.connect(lambda: self.fail('Video kodlayıcısı yanıt vermedi.'))

    def start(self):
        self.timeout.start(30000+len(self.frames)*500); self.recorder.record()

    def state_changed(self, state):
        from PySide6.QtMultimedia import QMediaRecorder
        if state == QMediaRecorder.RecordingState:
            QTimer.singleShot(200, self.send)          # the encoder accepts frames shortly after it starts
        elif state == QMediaRecorder.StoppedState and self.index >= len(self.frames) and not self.done:
            self.done = True; self.timeout.stop()
            try:
                if not self.temporary.exists() or self.temporary.stat().st_size == 0:
                    raise OSError('Video dosyası oluşmadı.')
                os.replace(self.temporary, self.path)
            except OSError as error:
                self.fail(str(error)); return
            self.finished.emit(str(self.path))

    def send(self):
        from PySide6.QtMultimedia import QVideoFrame
        while not self.done and self.index < len(self.frames):
            image = QImage.fromData(self.frames[self.index], 'PNG').convertToFormat(QImage.Format_ARGB32)
            frame = QVideoFrame(image)
            frame.setStartTime(self.index*1_000_000//self.fps); frame.setEndTime((self.index+1)*1_000_000//self.fps)
            if not self.input.sendVideoFrame(frame):
                return                                    # queue full: readyToSendVideoFrame calls again
            self.index += 1
        if not self.done and self.index >= len(self.frames):
            self.recorder.stop()

    def fail(self, message):
        if self.done:
            return
        self.done = True; self.timeout.stop(); self.recorder.stop()
        try:
            self.temporary.unlink(missing_ok=True)
        except OSError:
            pass
        self.failed.emit(message)
