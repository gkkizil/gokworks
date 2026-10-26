"""Three linked native Qt panes: folded mesh / native flat output / properties."""

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainterPath, QPen, QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QComboBox, QCheckBox, QPushButton, QGraphicsView, QGraphicsScene, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QScrollArea, QFrame)

from .viewer import MeshView, VIEWS


class FlatView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#ffffff'))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setAccessibleName('Seçili parçanın DXF açınımı')

    def show_flat(self, flat):
        self.scene().clear()
        if flat is not None:
            paths = {}
            for stroke in flat.strokes:
                path = paths.setdefault((stroke.color, stroke.bend), QPainterPath())
                path.moveTo(stroke.points[0][0], -stroke.points[0][1])
                for x, y in stroke.points[1:]: path.lineTo(x, -y)
            for (color, bend), path in paths.items():
                pen = QPen(QColor(color)); pen.setCosmetic(True)
                if bend: pen.setStyle(Qt.DashLine)
                self.scene().addPath(path, pen)
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-2, -2, 2, 2))
        self.fit()

    def fit(self):
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event); self.fit()

    def wheelEvent(self, event):
        factor = 1.15 ** (event.angleDelta().y()/120)
        if .001 < self.transform().m11()*factor < 10000:
            self.scale(factor, factor)
        event.accept()


class PreviewPanel(QWidget):
    refreshRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(240)
        outer = QVBoxLayout(self); outer.setContentsMargins(4, 0, 0, 0)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(); content.setMinimumHeight(460)
        self.scroll.setWidget(content); outer.addWidget(self.scroll)
        body = QVBoxLayout(content); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(4)
        self.source_label = QLabel('Önizleme · listeden bir sac parçası seçin')
        self.source_label.setWordWrap(True); body.addWidget(self.source_label)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        upper = QWidget(); layout = QVBoxLayout(upper); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        upper.setMinimumHeight(185)
        row = QHBoxLayout()
        self.views = QComboBox(); self.views.addItems(VIEWS); self.views.setAccessibleName('3D standart görünüş')
        self.fit_button = QPushButton('Sığdır'); self.refresh_button = QPushButton('Yenile')
        self.refresh_button.setToolTip('SolidWorks kaynak, konfigürasyon ve geometri güncelliğini yeniden kontrol et')
        row.addWidget(self.views, 1); row.addWidget(self.fit_button); row.addWidget(self.refresh_button)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.perspective = QCheckBox('Perspektif'); self.edges = QCheckBox('Kenarlar'); self.edges.setChecked(True)
        row.addWidget(self.perspective); row.addWidget(self.edges); row.addStretch()
        layout.addLayout(row)
        self.mesh_view = MeshView(); layout.addWidget(self.mesh_view, 1)
        self.message = QLabel('Gerçek SolidWorks geometrisi · görsel inceleme içindir')
        self.message.setWordWrap(True); layout.addWidget(self.message)
        self.splitter.addWidget(upper)
        middle = QWidget(); layout = QVBoxLayout(middle); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        middle.setMinimumHeight(125)
        row = QHBoxLayout(); self.flat_label = QLabel('Açınım · henüz okunmadı'); self.flat_label.setWordWrap(True)
        self.flat_fit = QPushButton('Sığdır'); row.addWidget(self.flat_label, 1); row.addWidget(self.flat_fit)
        layout.addLayout(row); self.flat_view = FlatView(); layout.addWidget(self.flat_view)
        self.splitter.addWidget(middle)
        self.info = QTableWidget(0, 2)
        self.info.setHorizontalHeaderLabels(('Parça bilgisi', 'Değer'))
        self.info.verticalHeader().hide()
        self.info.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.info.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.info.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info.setMinimumHeight(85); self.info.setAccessibleName('Seçili sac parçasının teknik bilgileri')
        self.splitter.addWidget(self.info)
        self.splitter.setSizes([270, 190, 160]); body.addWidget(self.splitter, 1)
        self.views.currentTextChanged.connect(self.mesh_view.view)
        self.fit_button.clicked.connect(self.mesh_view.fit)
        self.flat_fit.clicked.connect(self.flat_view.fit)
        self.refresh_button.clicked.connect(self.refreshRequested)
        self.perspective.toggled.connect(self.camera_changed)
        self.edges.toggled.connect(self.camera_changed)

    def camera_changed(self):
        projection_changed = self.mesh_view.camera.perspective != self.perspective.isChecked()
        self.mesh_view.camera.perspective = self.perspective.isChecked()
        self.mesh_view.camera.edges = self.edges.isChecked()
        if projection_changed: self.mesh_view.fit()
        else: self.mesh_view.changed()

    def clear(self, message='Listeden bir sac parçası seçin.'):
        self.mesh_view.set_mesh(None); self.flat_view.show_flat(None)
        self.info.setRowCount(0); self.source_label.setText('Önizleme')
        self.message.setText(message); self.message.setToolTip(message)
        self.flat_label.setText('Açınım · henüz okunmadı')

    def show_payload(self, payload):
        from pathlib import Path
        self.source_label.setText(f'{Path(payload.source).name} · {payload.configuration}')
        self.source_label.setToolTip(payload.source)
        self.mesh_view.set_mesh(payload.mesh)
        self.flat_view.show_flat(payload.flat)
        self.flat_label.setText(payload.flat.description if payload.flat else 'Açınım · okunamadı')
        self.info.setRowCount(len(payload.info))
        for row, (name, value) in enumerate(payload.info):
            self.info.setItem(row, 0, QTableWidgetItem(str(name)))
            item = QTableWidgetItem(str(value)); item.setToolTip(str(value))
            self.info.setItem(row, 1, item)
        self.info.resizeRowsToContents()
        text = '\n'.join(payload.warnings) if payload.warnings else f'{payload.mesh.triangles:,} üçgen · görsel inceleme · imalat ölçümü değildir'
        self.message.setText(text); self.message.setToolTip(text)
