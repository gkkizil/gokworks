"""Integrated DXF nesting workspace; every heavy operation uses the existing job runner."""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, QItemSelectionModel
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout, QTabBar, QSplitter,
    QTableView, QLineEdit, QFileDialog, QDialog, QMenu, QHeaderView,
    QAbstractItemView, QDialogButtonBox, QCheckBox, QApplication)

from gui_qt.components import BasePage, card, label, button, scroll, configure_view, show_details, ValueForm
from gui_qt.models import TableModel, Column, FilterProxy
from gui_qt.theme import COLORS
from modules.nesting.ui_widgets import Editor, Values, NestingCanvas, NestingTableModel
from modules.nesting.materials import new_project, SIZES
from modules.nesting.models import Material, Sheet, Options, Operations, uid, number, integer
from modules.nesting.geometry import polygons
from modules.nesting.accounting import mass, calculate

IMPORT_LABELS = {'pending':'Sırada', 'running':'Okunuyor', 'success':'Hazır', 'error':'Okunamadı', 'cancelled':'Durduruldu'}


def fmt(v, digits=3):
    if v is None: return '—'
    return f'{v:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class NestingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Nesting · Sac maliyeti',
                         'Parçaları ekleyin, sacı tanımlayın ve plakaları sırayla doldurun.')
        self.project = new_project(); self.result = None; self.loading = False
        self.imports = []; self.sheet_totals = []; self.totals = None; self.preferred_sheet = None
        self.price_candidate = None
        self.price_timer = QTimer(self); self.price_timer.setSingleShot(True); self.price_timer.setInterval(220)
        self.price_timer.timeout.connect(self.reprice)
        self.jobs.finished.connect(lambda:self.price_timer.start() if self.price_candidate is not None else None)
        self.pending_progress = None
        self.progress_timer = QTimer(self); self.progress_timer.setSingleShot(True); self.progress_timer.setInterval(80)
        self.progress_timer.timeout.connect(self.flush_progress)
        project_menu = QMenu(self)
        project_menu.addAction('Proje aç…', self.open_project)
        project_menu.addAction('Kaydet…', self.save_project)
        project_menu.addSeparator()
        self.new_button = project_menu.addAction('Yeni proje', self.new_project)
        self.action('Proje',None).setMenu(project_menu)
        # A compact project header; the working surface has no wizard tabs.
        heading = self.layout.itemAt(0).layout(); captions = heading.itemAt(0).layout()
        captions.itemAt(0).widget().setText('Nesting')
        captions.itemAt(0).widget().setStyleSheet('font-size: 21px; font-weight: 650;')
        captions.itemAt(1).widget().hide(); heading.setStretch(0,0)
        self.name = QLineEdit(self.project.name); self.name.textEdited.connect(self.name_changed)
        self.name.setMinimumWidth(0); self.name.setAccessibleName('Nesting proje adı')
        self.name.setToolTip('Proje adı'); heading.insertWidget(1,self.name,1); self.controls.append(self.name)
        commands = QHBoxLayout(); commands.setSpacing(8)
        self.parts_toggle = button('Parçalar'); self.parts_toggle.setCheckable(True); self.parts_toggle.setChecked(True)
        self.parts_toggle.setToolTip('Parça listesini gizle / göster. Panel kenarını sürükleyerek genişliğini ayarlayın.')
        self.parts_toggle.toggled.connect(self.toggle_parts); commands.addWidget(self.parts_toggle)
        self.settings_button = button('Sac ve ayarlar',self.show_settings); commands.addWidget(self.settings_button)
        self.controls.append(self.settings_button)
        commands.addStretch()
        self.stop_button = button('Durdur',self.jobs.cancel); self.stop_button.hide(); commands.addWidget(self.stop_button)
        self.nest_button = button('Yerleştir',self.start_nest,primary=True); commands.addWidget(self.nest_button)
        self.nest_button.setToolTip('Birinci plakadan başlayarak, stok adedi kadar plakayı sırayla doldur')
        self.controls.append(self.nest_button); self.layout.addLayout(commands)
        self.workspace = QSplitter(Qt.Horizontal); self.workspace.setChildrenCollapsible(False)
        self.workspace.setHandleWidth(8); self.workspace.setAccessibleName('Parçalar ve sac yerleşimi')
        self.layout.addWidget(self.workspace,1)
        left, left_layout = card()
        self.parts_panel = left; left.setMinimumWidth(216)
        left_layout.setContentsMargins(10,10,10,10); left_layout.setSpacing(8)
        title_row = QHBoxLayout(); title_row.addWidget(label('Parçalar','section')); title_row.addStretch()
        self.import_button = button('DXF ekle', self.import_dialog, primary=True); title_row.addWidget(self.import_button)
        left_layout.addLayout(title_row); self.controls.append(self.import_button)
        part_tools = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Parça veya dosya ara…'); self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Parçalarda ara')
        part_tools.addWidget(self.search,1); left_layout.addLayout(part_tools)
        self.part_model = NestingTableModel([Column('Parça','display_code'),Column('Adet','quantity'),
            Column('t · mm','thickness',lambda v:fmt(v,2)),Column('Malzeme','material'),
            Column('Durum','status',lambda s:IMPORT_LABELS.get(s,s))])
        self.part_proxy = FilterProxy(self); self.part_proxy.setSourceModel(self.part_model)
        self.part_table = configure_view(QTableView()); self.part_table.setModel(self.part_proxy)
        self.part_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.part_table.horizontalHeader().setMinimumSectionSize(32)
        self.part_table.horizontalHeader().setStretchLastSection(False)
        self.part_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for i, width in enumerate((140,42,60,115,105)): self.part_table.setColumnWidth(i,width)
        # The compact list keeps its numeric columns visible. Full material,
        # import status and source remain in the row tooltip and properties.
        self.part_table.hideColumn(3); self.part_table.hideColumn(4)
        self.part_table.verticalHeader().setDefaultSectionSize(32)
        self.part_table.setToolTip('Çift tık: adet, malzeme ve kalınlık. Ctrl / Shift: çoklu seçim. Satır üzerinde bekleyin: kaynak ve yükleme durumu.')
        self.part_table.doubleClicked.connect(self.edit_part); self.search.textChanged.connect(self.part_proxy.set_query)
        self.part_table.selectionModel().selectionChanged.connect(self.part_selection_changed)
        left_layout.addWidget(self.part_table,1)
        buttons = QHBoxLayout()
        self.edit_part_button = button('Düzenle', self.edit_part); buttons.addWidget(self.edit_part_button)
        self.remove_part_button = button('Kaldır', self.remove_part); buttons.addWidget(self.remove_part_button)
        buttons.addStretch()
        self.import_report_button = button('…', self.show_import_report); buttons.addWidget(self.import_report_button)
        self.import_report_button.setAccessibleName('DXF yükleme ayrıntıları'); self.import_report_button.setToolTip('DXF yükleme ayrıntıları')
        left_layout.addLayout(buttons)
        self.import_info = label('Henüz DXF seçilmedi.', 'muted'); left_layout.addWidget(self.import_info)
        self.workspace.addWidget(left)
        self.controls.extend([self.edit_part_button,self.remove_part_button])
        self.settings_dialog = QDialog(self); self.settings_dialog.setWindowTitle('Nesting · Sac ve ayarlar')
        self.settings_dialog.setWindowModality(Qt.WindowModal)
        settings_layout = QVBoxLayout(self.settings_dialog)
        settings_layout.addWidget(label('Sac stokunu ve yerleşim koşullarını buradan düzenleyin. Değişiklikler projeye hemen uygulanır.','muted'))
        self.settings_error = label('','error'); self.settings_error.hide(); settings_layout.addWidget(self.settings_error)
        self.stock_widget = self.build_stock(); settings_layout.addWidget(self.stock_widget,1)
        self.settings_dialog.installEventFilter(self)
        close = QDialogButtonBox(QDialogButtonBox.Close); close.button(QDialogButtonBox.Close).setText('Kapat')
        close.rejected.connect(self.settings_dialog.reject); settings_layout.addWidget(close)
        preview, layout = card(); preview.setMinimumWidth(220)
        layout.setContentsMargins(10,10,10,10); layout.setSpacing(8)
        toolbar = QBoxLayout(QBoxLayout.LeftToRight); self.plate_toolbar = toolbar
        self.sheet_tabs = QTabBar()
        self.sheet_tabs.setObjectName('nestingPlates')
        self.sheet_tabs.setDocumentMode(True); self.sheet_tabs.setDrawBase(False)
        self.sheet_tabs.setExpanding(False); self.sheet_tabs.setUsesScrollButtons(True)
        self.sheet_tabs.setElideMode(Qt.ElideNone); self.sheet_tabs.setMinimumWidth(0)
        self.sheet_tabs.setAccessibleName('Plakalar')
        self.sheet_tabs.setToolTip('Plaka sekmesine tıklayın veya sol / sağ ok tuşlarıyla geçin.')
        self.sheet_tabs.currentChanged.connect(self.render_sheet); toolbar.addWidget(self.sheet_tabs,1)
        self.canvas = NestingCanvas()
        self.canvas.partActivated.connect(self.select_canvas_part)
        tools = QWidget(); tool_layout = QHBoxLayout(tools)
        tool_layout.setContentsMargins(0,0,0,0); tool_layout.setSpacing(8)
        self.fit_button = button('Sığdır', self.canvas.fit); tool_layout.addWidget(self.fit_button)
        self.labels_toggle = QCheckBox('Adlar'); self.labels_toggle.setChecked(True)
        self.labels_toggle.setAccessibleName('Yerleşimde parça adlarını göster')
        self.labels_toggle.toggled.connect(self.canvas.set_labels_visible)
        self.labels_toggle.setToolTip('Uzun veya çok sayıdaki parça adlarını gizleyebilirsiniz. Ayrıntılar parça üzerinde bekleyince görünür.')
        tool_layout.addWidget(self.labels_toggle)
        toolbar.addWidget(tools,0,Qt.AlignRight); layout.addLayout(toolbar)
        self.current_note = label('DXF ekleyin, sacı tanımlayın ve Yerleştir düğmesine basın.', 'muted')
        self.current_note.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Parçaya tıkla: listede seç')
        layout.addWidget(self.current_note); layout.addWidget(self.canvas,1)
        self.summary = label('Henüz yerleşim yok.', 'subtitle'); layout.addWidget(self.summary)
        self.cost_summary = label('', 'section'); layout.addWidget(self.cost_summary)
        # The viewport itself resizes: an outer scroll area clips the sheet and
        # puts the summary below the fold, even when fitInView succeeds.
        self.preview_scroll = preview; preview.installEventFilter(self)
        self.workspace.addWidget(preview)
        self.workspace.setStretchFactor(0,0); self.workspace.setStretchFactor(1,1)
        self.workspace.setSizes([330,750]); self.parts_width = 330
        self.workspace.splitterMoved.connect(lambda *_:self.update_result_text())
        self.controls.extend([self.stock_widget, self.parameters])
        footer = QHBoxLayout(); footer.setSpacing(8)
        detail_menu = QMenu(self)
        self.detail_button = detail_menu.addAction('Hesap ve maliyet ayrıntıları',self.show_calculations)
        self.verify_button = detail_menu.addAction('Yerleşimi yeniden doğrula',self.verify)
        self.details_button = button('Ayrıntılar'); self.details_button.setMenu(detail_menu); footer.addWidget(self.details_button)
        export_menu = QMenu(self)
        self.dxf_button = export_menu.addAction('Plakaları DXF olarak kaydet…',self.export_dxf)
        self.excel_button = export_menu.addAction('Excel raporu…',lambda:self.export_report('excel'))
        self.pdf_button = export_menu.addAction('PDF raporu…',lambda:self.export_report('pdf'))
        self.export_button = button('Dışa aktar'); self.export_button.setMenu(export_menu); footer.addWidget(self.export_button)
        footer.addStretch()
        layout.addLayout(footer)
        self.result_controls = [self.verify_button,self.detail_button,self.dxf_button,self.excel_button,self.pdf_button]
        self.controls.extend(self.result_controls)
        self.finish_layout(); self.refresh()
        # Local density only: other GOKWORKS modules retain their current style.
        self.setStyleSheet('QPushButton { padding: 5px 10px; } QLineEdit { padding: 5px 7px; } '
                           'QHeaderView::section { padding: 7px 4px; }')
        self.layout.setContentsMargins(16,12,16,10); self.layout.setSpacing(8)
        self.style_sheet_tabs()
        self.set_status('DXF ekleyin · Sac ve ayarlardan stok tanımlayın · Yerleştir')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'workspace') and self.parts_panel.isVisible():
            # Keep a useful drawing area at the application's minimum width.
            maximum = max(216,int(self.workspace.width()*.42))
            sizes = self.workspace.sizes()
            if sizes[0] > maximum: self.workspace.setSizes([maximum,max(220,self.workspace.width()-maximum-8)])
        if hasattr(self,'cost_summary'): QTimer.singleShot(0,self.update_result_text)

    def eventFilter(self, watched, event):
        if watched is getattr(self,'settings_dialog',None) and event.type() == QEvent.Resize:
            self.stock_layout.setDirection(QBoxLayout.LeftToRight if watched.width() >= 1040 else QBoxLayout.TopToBottom)
        elif watched is getattr(self,'preview_scroll',None) and event.type() == QEvent.Resize:
            # Native Windows fonts can make one plate label wider than the
            # space left beside the tools. Give tabs the full preview width
            # on small windows; Qt can then scroll the selected plate into view.
            self.plate_toolbar.setDirection(QBoxLayout.LeftToRight if watched.width() >= 490 else QBoxLayout.TopToBottom)
        return super().eventFilter(watched,event)

    def show_settings(self, *, error=''):
        if not self.can_start(): return
        self.settings_error.setText(str(error)); self.settings_error.setVisible(bool(error))
        if not self.settings_dialog.isVisible():
            bounds = self.screen().availableGeometry()
            self.settings_dialog.resize(min(1100,bounds.width()-40),min(740,bounds.height()-60))
        self.settings_dialog.open()
        if error: self.stock_widget.verticalScrollBar().setValue(0)

    def toggle_parts(self, visible):
        if not hasattr(self,'workspace'): return
        if not visible: self.parts_width = self.workspace.sizes()[0]
        self.parts_panel.setVisible(visible)
        if visible:
            width = min(self.parts_width,max(216,int(self.workspace.width()*.42)))
            self.workspace.setSizes([width,max(220,self.workspace.width()-width-8)])
        self.parts_toggle.setText('Parçalar' if visible else 'Parçaları göster')

    def part_selection_changed(self):
        self.update_part_actions()
        if hasattr(self,'canvas'):
            self.canvas.set_selected_parts({index.data(Qt.UserRole)['id'] for index in self.part_table.selectionModel().selectedRows()
                                            if index.data(Qt.UserRole).get('kind') == 'part'})

    def select_canvas_part(self, part_id):
        if not part_id: return self.part_table.clearSelection()
        self.parts_toggle.setChecked(True)
        # A click on the drawing should still find a row hidden by the search.
        row = next((i for i in range(self.part_proxy.rowCount()) if self.part_proxy.index(i,0).data(Qt.UserRole)['id'] == part_id),None)
        if row is None:
            self.search.clear()
            row = next((i for i in range(self.part_proxy.rowCount()) if self.part_proxy.index(i,0).data(Qt.UserRole)['id'] == part_id),None)
        if row is not None:
            index = self.part_proxy.index(row,0)
            self.part_table.selectionModel().setCurrentIndex(index,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
            self.part_table.scrollTo(index)

    def update_part_actions(self):
        if not hasattr(self,'edit_part_button'): return
        count = len(self.part_table.selectionModel().selectedRows())
        self.edit_part_button.setEnabled(not self.busy and count == 1)
        self.remove_part_button.setEnabled(not self.busy and count > 0)
        self.remove_part_button.setText(f'Kaldır ({count})' if count > 1 else 'Kaldır')

    def selected(self, table):
        return table.currentIndex().data(Qt.UserRole) if table.currentIndex().isValid() else None

    def selected_sheet_key(self):
        return self.sheet_tabs.tabData(self.sheet_tabs.currentIndex()) if self.sheet_tabs.currentIndex() >= 0 else None

    def clear_sheet_tabs(self):
        self.sheet_tabs.blockSignals(True)
        while self.sheet_tabs.count(): self.sheet_tabs.removeTab(self.sheet_tabs.count()-1)
        self.sheet_tabs.blockSignals(False)

    def material_field(self,form,current):
        choices = {f'{m.name} · {m.density:g} kg/m³':m.id for m in self.project.materials}
        box = form.combo('material','Malzeme',choices,next((name for name,key in choices.items() if key == current),next(iter(choices))))
        form.material_ids = choices
        return box

    @staticmethod
    def material_value(form):
        return form.material_ids[form.value('material')]

    def invalidate(self, *, preserve_price_candidate=False):
        if self.loading: return
        if not preserve_price_candidate:
            self.price_candidate = None; self.price_timer.stop()
        had_result = self.result is not None
        self.result = None; self.sheet_totals = []; self.totals = None
        self.clear_sheet_tabs()
        self.render_sheet()
        self.summary.setText('Yerleşim bekleniyor.'); self.summary.setToolTip(''); self.cost_summary.setText('')
        self.cost_summary.setToolTip(''); self.cost_summary.setAccessibleDescription('')
        self.current_note.setText('Parça ve sac bilgilerini tamamlayıp Yerleştir düğmesine basın.')
        self.update_buttons()
        if had_result: self.set_status('Parça, sac veya ayarlar değişti. Güncel sonuç için yeniden otomatik yerleşim yapın.')

    def name_changed(self, value):
        self.cost_changed(); self.project.name = value

    def cost_changed(self):
        if self.loading: return
        if self.result is not None:
            self.preferred_sheet = self.selected_sheet_key()
            self.price_candidate = (self.project.placement_fingerprint(),deepcopy(self.result))
        self.invalidate(preserve_price_candidate=True)
        self.price_timer.start()

    def reprice(self):
        if self.price_candidate is None or self.busy or self.jobs.busy: return
        # An editor runs its own event loop. Wait for its draft to be accepted
        # or discarded before taking a price snapshot of the live project.
        modal = QApplication.activeModalWidget()
        if modal is not None and modal is not self.settings_dialog:
            self.price_timer.start(); return
        signature,candidate = self.price_candidate
        try:
            self.read_parameters()
            if signature != self.project.placement_fingerprint(): return self.invalidate()
            snapshot = deepcopy(self.project); candidate = deepcopy(candidate); candidate.digest = snapshot.fingerprint()
            from datetime import datetime,timezone
            candidate.timestamp = datetime.now(timezone.utc).isoformat()
            self.project.validate()
        except ValueError as error: return self.set_status(error,True)
        self.price_candidate = None
        def operation(sink,stop):
            totals = calculate(snapshot,candidate,complete=False,stop=stop)
            sink.put(('nest_result',(candidate,totals)))
        self.jobs.start(self,operation)

    def update_buttons(self):
        if not hasattr(self,'result_controls'): return
        ready = not self.busy and self.result is not None
        complete = ready and not self.result.unplaced
        for control in (self.detail_button,self.details_button): control.setEnabled(ready)
        for control in (self.verify_button,self.export_button,self.dxf_button,self.excel_button,self.pdf_button):
            control.setEnabled(complete)
        self.export_button.setToolTip('Tüm parçalar yerleştiğinde DXF, Excel veya PDF kaydedebilirsiniz.'
                                     if not complete else 'DXF, Excel veya PDF kaydet')
        self.nest_button.setEnabled(not self.busy and bool(self.project.parts))
        self.stop_button.setVisible(self.busy)
        self.sheet_tabs.setEnabled(bool(self.sheet_totals))
        self.import_report_button.setVisible(bool(self.imports))
        self.update_part_actions()

    def set_busy(self, busy):
        super().set_busy(busy); self.update_buttons()
        if not busy:
            self.progress_timer.stop(); self.pending_progress = None

    def flush_progress(self):
        value,self.pending_progress = self.pending_progress,None
        if value is not None and self.jobs.owner is self:
            self.progressChanged.emit(value[0],value[1]); self.set_status(value[2])

    def new_project(self):
        if not self.can_start(): return
        self.project = new_project(); self.result = None; self.imports = []; self.sync_forms(); self.refresh(); self.invalidate()
        self.search.clear(); self.parts_toggle.setChecked(True)
        self.settings_dialog.reject()
        self.set_status('Yeni proje hazır. Kaynak DXF dosyaları değiştirilmez.')

    def build_stock(self):
        widget = QWidget(); self.stock_layout = QBoxLayout(QBoxLayout.LeftToRight,widget)
        self.stock_layout.setContentsMargins(0,8,0,0)
        panel, layout = card('Kullanılabilir saclar')
        self.sheet_model = NestingTableModel([Column('Sac / malzeme','title'),Column('Ölçü · mm','size'),
                                      Column('t · mm','thickness',lambda v:fmt(v,2)),Column('Stok','stock'),Column('Fiyat','price')])
        self.sheet_table = configure_view(QTableView()); self.sheet_table.setModel(self.sheet_model)
        self.sheet_table.setMinimumHeight(170); self.sheet_table.setMaximumHeight(260)
        self.sheet_table.horizontalHeader().setMinimumSectionSize(45)
        self.sheet_table.horizontalHeader().setStretchLastSection(False)
        self.sheet_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for index,width in enumerate((140,125,75,60,110)): self.sheet_table.setColumnWidth(index,width)
        self.sheet_table.doubleClicked.connect(self.edit_sheet); layout.addWidget(self.sheet_table,1)
        row = QHBoxLayout()
        for text, callback in [('Sac ekle',lambda:self.edit_sheet(new=True)),('Düzenle',self.edit_sheet),('Kaldır',self.remove_sheet)]: row.addWidget(button(text,callback))
        layout.addLayout(row)
        layout.addWidget(label('İlk plaka dolunca sıradakine geçilir. En fazla stok adedi kadar plaka kullanılır.', 'muted'))
        self.stock_hint = label('', 'muted'); layout.addWidget(self.stock_hint)
        layout.addWidget(button('Malzeme kütüphanesi…',self.show_materials)); layout.addStretch()
        self.stock_layout.addWidget(panel,3)
        self.parameters = self.build_parameters(); self.stock_layout.addWidget(self.parameters,2)
        return scroll(widget)

    def show_materials(self):
        if not self.can_start(): return
        dialog = QDialog(self); dialog.setWindowTitle('Malzeme kütüphanesi'); dialog.resize(720,500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('Yoğunluklar yaklaşık başlangıç değerleridir; düzenlemeler bu projeye kaydedilir.', 'muted'))
        self.material_model = TableModel([Column('Malzeme','name'),Column('Yoğunluk kg/m³','density',fmt),Column('Kaynak','source')])
        self.material_table = configure_view(QTableView()); self.material_table.setModel(self.material_model)
        self.material_model.replace([asdict(m) for m in self.project.materials])
        self.material_table.doubleClicked.connect(self.edit_material); layout.addWidget(self.material_table,1)
        row = QHBoxLayout(); row.addWidget(button('Özel malzeme ekle',lambda:self.edit_material(new=True)))
        row.addWidget(button('Malzemeyi düzenle',self.edit_material)); layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText('Kapat'); close.rejected.connect(dialog.reject); layout.addWidget(close)
        try: dialog.exec()
        finally:
            self.material_table = self.material_model = None
            dialog.deleteLater()

    def build_parameters(self):
        widget, layout = card('Yerleşim ayarları')
        self.form = f = ValueForm(Values(), '')
        f.text('gap','Parça aralığı · mm',3); f.text('margin','Kenar payı · mm',10)
        f.check('rotation','Parçalar döndürülebilsin',True)
        quality = f.combo('quality','Yerleşim kalitesi',('Hızlı','Dengeli','Yüksek'),'Dengeli')
        quality.setToolTip('Hızlı daha az, Yüksek daha fazla yerleşim denemesi yapar. Hesaplama süresi sınırı her durumda geçerlidir.')
        quality.setAccessibleName('Yerleşim kalitesi')
        self.advanced_button = button('Gelişmiş ayarları göster')
        self.advanced_button.setCheckable(True)
        f.form.addRow(self.advanced_button)
        f.text('kerf','Kesim genişliği (kerf) · mm',.2)
        f.text('angles','İzinli açılar · ; ile ayırın','0;90;180;270')
        f.text('angle_step','Serbest açı adımı · ° (boşsa yukarıdaki liste)','')
        f.check('grain_locked','Hadde yönünü koru · yalnız 0° / 180°',False)
        seconds = f.text('seconds','Yerleşim hesaplama süresi · sn',15)
        seconds.setToolTip('İzin verilen en uzun hesaplama süresi. Daha erken bitebilir; süre dolunca bulunan en iyi geçerli yerleşim gösterilir.')
        seconds.setAccessibleName('Yerleşim hesaplama süresi, saniye')
        seed = f.text('seed','Deneme sırası kodu',42)
        seed.setAccessibleName('Deneme sırası kodu')
        self.seed_hint = label('Varsayılan 42; değiştirmeniz gerekmez. Bu kod, farklı yerleşimlerin hangi sırayla deneneceğini belirler.', 'muted')
        seed.setToolTip(self.seed_hint.text()); f.form.addRow(self.seed_hint)
        self.advanced_note = label('Aynalama ve delik içine yerleşim kapalıdır. Kerf telafisi CAM tarafında yapılır. '
                                   'Yerleşim aralığı, parça aralığı ile kerf değerinin büyüğü ve kontur hata paylarıdır.', 'muted')
        f.form.addRow(self.advanced_note)
        def advanced(visible):
            for key in ('kerf','angles','angle_step','grain_locked','seconds','seed'): f.show_field(key,visible)
            self.seed_hint.setVisible(visible)
            self.advanced_note.setVisible(visible)
            self.advanced_button.setText('Gelişmiş ayarları gizle' if visible else 'Gelişmiş ayarları göster')
        self.advanced_button.toggled.connect(advanced); advanced(False)
        layout.addWidget(f)
        self.cost_form = c = ValueForm(Values(), '')
        for key, title in [('cut_price_m','Kesim · TL/m'),('piercing_price','Piercing · TL/kontur'),('setup','Tezgâh hazırlık · TL'),
                           ('fixed','Sabit gider · TL'),('profit_percent','Kâr · %'),('vat_percent','KDV · %')]: c.text(key,title,0)
        self.cost_toggle = button('Kesim ve ek maliyetler')
        self.cost_toggle.setCheckable(True); self.cost_toggle.toggled.connect(c.setVisible)
        layout.addWidget(self.cost_toggle); layout.addWidget(c); c.hide()
        layout.addWidget(label('Sac birim fiyatını, sac satırına çift tıklayarak girebilirsiniz.', 'muted'))
        f.changed.connect(lambda:self.parameters_changed()); c.changed.connect(lambda:self.cost_changed())
        layout.addStretch(); return widget

    def read_parameters(self):
        f = self.form
        step = f.value('angle_step').strip()
        if step:
            step = number(step,'Açı adımı',positive=True)
            if step < 1 or step > 360: raise ValueError('Açı adımı 1–360° arasında olmalı.')
            angles = [i*step for i in range(int(359.999999/step)+1)]
        else:
            try: angles = [float(v.strip().replace(',','.')) for v in f.value('angles').split(';') if v.strip()]
            except ValueError: raise ValueError('Dönüş açılarını 0;90;180;270 biçiminde girin.') from None
        titles = dict(gap='Parça aralığı',margin='Kenar payı',kerf='Kesim genişliği',seconds='Yerleşim hesaplama süresi')
        o = Options(**{k:number(f.value(k),titles[k]) for k in titles},
                    rotation=f.value('rotation'), angles=angles, grain_locked=f.value('grain_locked'),
                    quality=f.value('quality'),seed=integer(f.value('seed'),'Deneme sırası kodu',minimum=0,maximum=2**32-1))
        operations = Operations(**{key:number(self.cost_form.value(key),self.cost_form.form.labelForField(self.cost_form.fields[key]).text())
                                   for key in asdict(self.project.operations)})
        self.project.options = o; self.project.operations = operations

    def parameters_changed(self):
        if not self.loading: self.invalidate()

    def sync_forms(self):
        self.loading = True
        try:
            self.name.setText(self.project.name)
            for k,v in asdict(self.project.options).items():
                self.form.set_value(k,';'.join(map(str,v)) if k == 'angles' else v)
            self.form.set_value('angle_step','')
            for k,v in asdict(self.project.operations).items(): self.cost_form.set_value(k,v)
            self.cost_toggle.setChecked(any(asdict(self.project.operations).values()))
        finally: self.loading = False

    def refresh(self):
        rows = []
        for p in self.project.parts:
            g = p.polygon; m = self.project.material(p.material)
            rows.append(dict(id=p.id,code=p.code,display_code=p.code,quantity=p.quantity,thickness=p.thickness,weight=mass(g.area,p.thickness,m.density),
                             material=m.name,status='success',source=p.source,detail='Kesim konturu hazır.',kind='part'))
        rows.extend(dict(id=e['id'],code=Path(e['source']).name,display_code=Path(e['source']).name+' · '+IMPORT_LABELS[e['status']],
                         quantity=None,thickness=e['options'].get('thickness',2),weight=None,
                         material=next((m.name for m in self.project.materials if m.id == e['options'].get('material','S235JR')),'—'),
                         status=e['status'],source=e['source'],detail=e['detail'],kind='import')
                    for e in self.imports if e['status'] != 'success')
        self.part_model.replace(rows)
        self.sheet_model.replace([dict(asdict(s),title=f'{s.name} · {self.project.material(s.material).name}',
            size=f'{s.width:g} × {s.height:g}',
            price=(f'{fmt(s.price_sheet,2)} TL/levha' if s.pricing == 'sheet' else f'{fmt(s.price_kg,2)} TL/kg')) for s in self.project.sheets])
        if getattr(self,'material_model',None) is not None: self.material_model.replace([asdict(m) for m in self.project.materials])
        missing = self.missing_stock()
        self.stock_hint.setText(('Eksik sac: '+', '.join(f'{self.project.material(m).name} · {t:g} mm' for m,t in missing)+'. Sac ekle ile tanımlayın.')
                               if missing else 'Parçalar yalnız aynı malzeme ve kalınlıktaki saclara yerleştirilir.')
        self.update_buttons()
        counts = {status:sum(e['status'] == status for e in self.imports) for status in IMPORT_LABELS}
        if self.imports:
            self.import_info.setText(f"{len(self.imports)} dosya · {counts['success']} hazır · {counts['error']} sorunlu"
                                     + (f" · {counts['pending']+counts['running']} bekliyor" if counts['pending']+counts['running'] else '')
                                     + (f" · {counts['cancelled']} durduruldu" if counts['cancelled'] else ''))
        else: self.import_info.setText(f'{len(self.project.parts)} parça hazır.' if self.project.parts else 'Henüz DXF seçilmedi.')

    def show_import_report(self):
        lines = [self.import_info.text(), 'Okunamayan dosyaya çift tıklayıp birim/katman ayarlarını düzenleyerek yeniden deneyebilirsiniz.']
        for e in self.imports:
            lines.append(f"\n{Path(e['source']).name} · {IMPORT_LABELS[e['status']]}\n{e['detail']}")
        show_details(self,'DXF yükleme ayrıntıları','\n'.join(lines))

    def edit_material(self, *args, new=False):
        row = self.selected(self.material_table)
        if not new and not row: return self.set_status('Düzenlemek için bir malzeme seçin.')
        item = Material(uid(),'Özel malzeme',7850) if new else self.project.material(row['id'])
        def build(f):
            f.text('name','Malzeme adı',item.name); f.text('density','Yoğunluk · kg/m³',item.density); f.text('source','Kaynak / not',item.source)
        def parse(f):
            name = f.value('name').strip()
            if not name: raise ValueError('Malzeme adı boş olamaz.')
            return replace(item,name=name,density=number(f.value('density'),'Yoğunluk',positive=True),source=f.value('source'))
        dialog = Editor(self,'Malzeme tanımı',build,parse)
        try:
            if dialog.exec() == QDialog.Accepted:
                self.cost_changed()
                if new: self.project.materials.append(dialog.value)
                else: self.project.materials[self.project.materials.index(item)] = dialog.value
                self.refresh()
        finally: dialog.deleteLater()

    def edit_sheet(self, *args, new=False):
        if not self.can_start(): return
        row = self.selected(self.sheet_table)
        if not new and not row: return self.set_status('Düzenlemek için bir sac seçin.')
        item = Sheet(uid(),'Yeni sac') if new else self.project.sheet(row['id'])
        def build(f):
            preset = f.combo('preset','Ölçü şablonu',['Özel',*[f'{w} × {h}' for w,h in SIZES]],'Özel')
            f.text('name','Sac adı',item.name); f.text('width','En · mm',item.width); f.text('height','Boy · mm',item.height)
            f.text('thickness','Kalınlık · mm',item.thickness); self.material_field(f,item.material)
            f.text('stock','Stok adedi',item.stock); f.combo('pricing','Fiyat modeli',('TL/kg','TL/levha'),'TL/kg' if item.pricing == 'kg' else 'TL/levha')
            f.text('price_kg','TL/kg',item.price_kg); f.text('price_sheet','TL/levha',item.price_sheet)
            def change():
                if preset.currentIndex():
                    w,h = SIZES[preset.currentIndex()-1]; f.set_value('width',w); f.set_value('height',h)
            preset.currentIndexChanged.connect(change)
        def parse(f):
            return replace(item,name=f.value('name').strip() or 'Sac',width=number(f.value('width'),'En',positive=True),
                           height=number(f.value('height'),'Boy',positive=True),thickness=number(f.value('thickness'),'Kalınlık',positive=True),
                           material=self.material_value(f),stock=integer(f.value('stock'),'Stok',minimum=0),
                           pricing='kg' if f.value('pricing') == 'TL/kg' else 'sheet',
                           price_kg=number(f.value('price_kg'),'TL/kg'),price_sheet=number(f.value('price_sheet'),'TL/levha'))
        dialog = Editor(self,'Sac ve fiyat tanımı',build,parse)
        try:
            if dialog.exec() == QDialog.Accepted:
                self.cost_changed()
                if new: self.project.sheets.append(dialog.value)
                else: self.project.sheets[self.project.sheets.index(item)] = dialog.value
                self.refresh()
        finally: dialog.deleteLater()

    def remove_sheet(self):
        if not self.can_start(): return
        row = self.selected(self.sheet_table)
        if row:
            self.project.sheets = [s for s in self.project.sheets if s.id != row['id']]; self.invalidate(); self.refresh()

    def edit_part(self, *args):
        if not self.can_start(): return
        if len(self.part_table.selectionModel().selectedRows()) > 1:
            return self.set_status('Özelliklerini düzenlemek için tek parça seçin.')
        row = self.selected(self.part_table)
        if not row: return self.set_status('Düzenlemek için bir parça seçin.')
        if row.get('kind') == 'import':
            entry = next(e for e in self.imports if e['id'] == row['id'])
            return self.configure_import([entry['source']], defaults=entry['options'], retry_id=entry['id'], detail=entry['detail'])
        item = self.project.part(row['id']); bounds = item.polygon.bounds
        def build(f):
            f.text('code','Parça kodu',item.code); f.text('description','Açıklama',item.description)
            f.text('quantity','Adet',item.quantity); self.material_field(f,item.material)
            f.text('thickness','Kalınlık · mm',item.thickness); f.check('grain_locked','Bu parçada hadde yönünü koru',item.grain_locked)
            f.form.addRow(label(f'Net ağırlık {fmt(mass(item.area,item.thickness,self.project.material(item.material).density))} kg/adet\n'
                                f'Net alan {fmt(item.area)} mm² · X {fmt(bounds[2]-bounds[0])} × Y {fmt(bounds[3]-bounds[1])} mm\n'
                                f'Dış çevre {fmt(sum(p.exterior.length for p in polygons(item.polygon)))} mm\n'
                                f'Delik çevresi {fmt(sum(r.length for p in polygons(item.polygon) for r in p.interiors))} mm\n'
                                f'Kaynak: {Path(item.source).name}\n'+ '\n'.join(item.notes), 'muted'))
        def parse(f):
            code = f.value('code').strip()
            if not code: raise ValueError('Parça kodu boş olamaz.')
            return replace(item,code=code,description=f.value('description'),quantity=integer(f.value('quantity'),'Adet'),
                           material=self.material_value(f),thickness=number(f.value('thickness'),'Kalınlık',positive=True),grain_locked=f.value('grain_locked'))
        dialog = Editor(self,'Parça özellikleri',build,parse)
        try:
            if dialog.exec() == QDialog.Accepted:
                self.project.parts[self.project.parts.index(item)] = dialog.value; self.invalidate(); self.refresh()
        finally: dialog.deleteLater()

    def remove_part(self):
        if not self.can_start(): return
        rows = [index.data(Qt.UserRole) for index in self.part_table.selectionModel().selectedRows()]
        if not rows: return
        part_ids = {row['id'] for row in rows if row.get('kind') == 'part'}
        import_ids = {row['id'] for row in rows if row.get('kind') == 'import'}
        self.project.parts = [p for p in self.project.parts if p.id not in part_ids]
        self.imports = [e for e in self.imports if e['id'] not in import_ids]
        self.invalidate(); self.refresh()
        self.set_status(f'{len(rows)} satır listeden kaldırıldı.')

    def import_dialog(self):
        if not self.can_start(): return
        files,_ = QFileDialog.getOpenFileNames(self,'DXF dosyalarını yükle','','DXF (*.dxf *.DXF)')
        if not files: return
        self.configure_import(files)

    def configure_import(self, files, *, defaults=None, retry_id=None, detail=''):
        if not self.can_start(): return
        defaults = defaults or {}
        def build(f):
            f.form.addRow(label(f'{len(files)} DXF dosyası seçildi. Hepsi yükleme listesine eklenecek.', 'section'))
            if detail: f.form.addRow(label(detail,'error'))
            self.material_field(f,defaults.get('material',self.project.materials[0].id))
            f.text('thickness','Sac kalınlığı · mm',defaults.get('thickness',2)); f.text('quantity','Her parça için adet',defaults.get('quantity',1))
            f.combo('unit',"DXF'de birim yazmıyorsa",('Birim seçilmedi','mm','cm','inch'),defaults.get('unit') or 'Birim seçilmedi')
            f.text('tolerance','Eğri kiriş toleransı · mm',defaults.get('tolerance',.02)); f.text('join_tolerance','Uç birleştirme toleransı · mm',defaults.get('join_tolerance',.001))
            f.text('excluded_layers','Dışlanacak katmanlar · ; ile ayırın',';'.join(defaults.get('excluded_layers',[])))
            f.check('grouped','Her dosyadaki bağımsız konturları tek grup olarak tut',defaults.get('grouped',False))
            f.form.addRow(label('Ölçülendirme, yazı, tarama ve kapalı/dondurulmuş katmanlar kesime alınmaz. '
                                'Açık veya hatalı kontur sessizce onarılmaz. Kaynak DXF değiştirilmez.', 'muted'))
        def parse(f):
            return dict(material=self.material_value(f),thickness=number(f.value('thickness'),'Kalınlık',positive=True),
                        quantity=integer(f.value('quantity'),'Adet'),unit=None if f.value('unit') == 'Birim seçilmedi' else f.value('unit'),
                        tolerance=number(f.value('tolerance'),'Eğri toleransı',positive=True),
                        join_tolerance=number(f.value('join_tolerance'),'Uç toleransı',positive=True),
                        excluded_layers=[s.strip() for s in f.value('excluded_layers').split(';') if s.strip()],grouped=f.value('grouped'))
        dialog = Editor(self,'DXF içe aktarma seçenekleri',build,parse)
        try:
            if dialog.exec() == QDialog.Accepted: self.import_files(files,retry_id=retry_id,**dialog.value)
        finally: dialog.deleteLater()

    def import_files(self, files, *, retry_id=None, **options):
        if not self.can_start(): return
        files = list(files)
        if not files: return
        self.search.clear(); self.invalidate(); self.parts_toggle.setChecked(True)
        entries = []
        for path in files:
            if retry_id:
                entry = next(e for e in self.imports if e['id'] == retry_id)
                entry.update(source=str(path),status='pending',detail='Yeniden okuma sırasında.',options=deepcopy(options))
            else:
                entry = dict(id=uid(),source=str(path),status='pending',detail='Okuma sırasında.',options=deepcopy(options))
                self.imports.append(entry)
            entries.append(deepcopy(entry))
        self.refresh()
        def operation(sink,stop):
            from modules.nesting.batch_import import import_batch
            import_batch(entries,options,sink,stop)
        self.jobs.start(self,operation); self.set_status(f'{len(files)} DXF dosyası sıraya eklendi; konturlar okunuyor…')

    def missing_stock(self):
        return sorted({(part.material,part.thickness) for part in self.project.parts
                       if not any(s.material == part.material and abs(s.thickness-part.thickness) <= 1e-7 and s.stock > 0
                                  for s in self.project.sheets)})

    def start_nest(self):
        if not self.can_start(): return
        problems = [e for e in self.imports if e['status'] != 'success']
        if problems:
            self.parts_toggle.setChecked(True)
            return self.set_status(f'{len(problems)} dosya henüz hazır değil. Listede Okunamadı/Durduruldu yazan dosyaya çift tıklayıp yeniden okuyun veya Kaldır ile çıkarın.',True)
        try: self.read_parameters(); self.project.validate()
        except ValueError as error:
            self.set_status(error,True); return self.show_settings(error=str(error))
        missing = self.missing_stock()
        if missing:
            error = 'Sac tanımı / stok eksik: '+', '.join(f'{self.project.material(material).name} · {thickness:g} mm' for material,thickness in missing)
            error += '. Sac ekle ile uygun kalınlıkta sac tanımlayın veya stok adedini artırın.'
            self.set_status(error,True); return self.show_settings(error=error)
        self.invalidate(); self.preferred_sheet = None; snapshot = deepcopy(self.project)
        def operation(sink,stop):
            from modules.nesting.engine import nest
            result = nest(snapshot,stop=stop,progress=lambda percent,text:sink.put(('nest_progress',(percent,100,text))))
            totals = calculate(snapshot,result,complete=False)
            sink.put(('nest_result',(result,totals)))
        self.jobs.start(self,operation); self.set_status('Parçalar plakalara yerleştiriliyor…')

    def show_result(self,result,totals=None):
        self.result = result
        if result is None: return self.invalidate()
        totals = totals or calculate(self.project,result,complete=False)
        self.totals = totals
        self.sheet_totals = totals['sheets']
        self.clear_sheet_tabs(); self.sheet_tabs.blockSignals(True)
        for index,s in enumerate(totals['sheets'],1):
            tab = self.sheet_tabs.addTab(f'{index}. plaka')
            self.sheet_tabs.setTabData(tab,(s['id'],s['number']))
            self.sheet_tabs.setTabToolTip(tab,f"{s['name']} · {s['width']:g} × {s['height']:g} mm · {s['material']} · t={s['thickness']:g} mm")
        selected = next((i for i in range(self.sheet_tabs.count()) if self.sheet_tabs.tabData(i) == self.preferred_sheet),-1)
        if selected >= 0: self.sheet_tabs.setCurrentIndex(selected)
        self.sheet_tabs.blockSignals(False); self.preferred_sheet = None
        self.update_result_text()
        self.render_sheet(); self.update_buttons()
        if result.unplaced:
            codes = sorted({self.project.part(key).code for key in result.unplaced})
            reason = ('İşlem durduruldu; yeniden yerleşim başlatabilirsiniz.' if result.stopped else
                      'Hesaplama süresi doldu; süreyi artırıp yeniden deneyin.' if result.timed_out else
                      'Sac ölçüsü/stoku, dönüş açıları ve yerleşim paylarını kontrol edin.')
            self.set_status(f'{len(result.unplaced)} parça yerleşmedi: '+', '.join(codes)+'. '+reason+' Üretim çıktısı kapalı.',True)
        else: self.set_status(f'Yerleşim doğrulandı · {totals["part_count"]} parça · {totals["sheet_count"]} levha · {result.elapsed:.1f} sn')

    def update_result_text(self):
        if self.result is None or self.totals is None: return
        totals = self.totals; compact = self.preview_scroll.width() < 490
        full = (f"{totals['part_count']} parça · {totals['sheet_count']} levha · Verim %{fmt(totals['efficiency'],1)}"
                             + (f" · {len(self.result.unplaced)} parça yerleşmedi" if self.result.unplaced else '') + '\n'
                             f"Brüt {fmt(totals['gross_weight'])} kg · Net {fmt(totals['net_weight'])} kg · Fire {fmt(totals['waste_weight'])} kg")
        self.summary.setToolTip(full)
        self.summary.setText((f"{totals['part_count']} parça · {totals['sheet_count']} levha · %{fmt(totals['efficiency'],1)}"
                             + (f"\n{len(self.result.unplaced)} parça yerleşmedi" if self.result.unplaced else '')
                             + f"\nNet {fmt(totals['net_weight'])} kg") if compact else full)
        unpriced = any(s['price'] == 0 for s in totals['sheets'])
        prefix = 'Kısmi hesap' if self.result.unplaced else 'Toplam'
        self.cost_summary.setText(f"{prefix} {fmt(totals['total'],2)} TL"
                                  + (f" · Malzeme {fmt(totals['material_cost'],2)} TL" if not compact else '')
                                  + (' · Sac fiyatı eksik' if unpriced else ''))
        breakdown = f"{prefix} {fmt(totals['total'],2)} TL\nMalzeme {fmt(totals['material_cost'],2)} TL"
        if unpriced: breakdown += '\nSac fiyatı eksik'
        self.cost_summary.setAccessibleDescription(breakdown)
        self.cost_summary.setToolTip(breakdown+'\n\nGirilen sac, kesim, hazırlık, sabit gider, kâr ve KDV toplamı. '
                                     'Sıfır bırakılan fiyat ve giderler hesaba eklenmez.')

    def render_sheet(self):
        self.canvas.render(self.project,self.result,self.selected_sheet_key())
        self.part_selection_changed()
        index = self.sheet_tabs.currentIndex(); count = self.sheet_tabs.count()
        if self.result is not None and 0 <= index < len(self.sheet_totals):
            s = self.sheet_totals[index]
            quantity = sum((p.sheet_id,p.sheet_number) == (s['id'],s['number']) for p in self.result.placements)
            self.current_note.setText(f"{index+1}/{count} plaka · {s['width']:g} × {s['height']:g} mm · {s['material']} · t={s['thickness']:g} mm · {quantity} parça · Verim %{fmt(s['efficiency'],1)}")

    def theme_changed(self):
        self.style_sheet_tabs()
        self.canvas.theme = self.context.appearance; self.render_sheet()

    def style_sheet_tabs(self):
        c=COLORS[self.context.appearance]
        self.sheet_tabs.setStyleSheet(f'''
            QTabBar#nestingPlates::tab {{ background: {c['input']}; color: {c['muted']};
                border: 1px solid {c['border']}; border-top-left-radius: 5px; border-top-right-radius: 5px;
                margin-right: 3px; padding: 5px 12px; }}
            QTabBar#nestingPlates::tab:selected {{ background: {c['selected']}; color: {c['accent']};
                border-bottom: 2px solid {c['accent']}; }}
            QTabBar#nestingPlates::tab:hover {{ color: {c['text']}; }}
        ''')

    def verify(self):
        if not self.can_start() or self.result is None: return
        project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from modules.nesting.validation import validate_result
            validate_result(project,result,stop=stop); sink.put(('nest_message','Yerleşim doğrulandı: adetler, malzeme/kalınlık, stok, kenar payı ve kontur aralıkları uygun.'))
        self.jobs.start(self,operation)

    def show_calculations(self):
        if self.result is None or self.totals is None: return
        try:
            from modules.nesting.report import summary_rows
            text = '\n'.join(f'{k}: {v}' for k,v in summary_rows(self.project,self.result,self.totals))
            show_details(self,'Nesting · Hesap ve maliyet ayrıntıları',text)
        except ValueError as error: self.set_status(error,True)

    def can_export(self):
        if not self.can_start() or self.result is None: return False
        if self.result.unplaced:
            self.set_status('Çıktı almak için tüm parçalar yerleşmeli. Sac stokunu/ölçüsünü veya yerleşim hesaplama süresini artırın.',True)
            return False
        return True

    def export_report(self,kind):
        if not self.can_export(): return
        suffix = '.xlsx' if kind == 'excel' else '.pdf'
        path,_ = QFileDialog.getSaveFileName(self,'Nesting raporu','Nesting'+suffix,'Rapor (*'+suffix+')')
        if not path: return
        project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from modules.nesting.report import export_excel,export_pdf
            (export_excel if kind == 'excel' else export_pdf)(project,result,path,overwrite=True,stop=stop)
            sink.put(('nest_message','Rapor kaydedildi: '+str(path)))
        self.jobs.start(self,operation)

    def export_dxf(self):
        if not self.can_export(): return
        folder = QFileDialog.getExistingDirectory(self,'DXF çıktısının kaydedileceği ana klasör')
        if not folder: return
        target = Path(folder)/('GOKWORKS-Nesting-'+uid()[:8]); project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from modules.nesting.dxf_export import export_dxf
            paths = export_dxf(project,result,target,stop=stop)
            sink.put(('nest_message',f'{len(paths)} levha DXF olarak kaydedildi: {target}'))
        self.jobs.start(self,operation)

    def save_project(self):
        if not self.can_start(): return
        try: self.read_parameters(); self.project.validate(require_work=False)
        except ValueError as error: return self.set_status(error,True)
        path,_ = QFileDialog.getSaveFileName(self,'Nesting projesini kaydet','Nesting.goknest.json','Nesting (*.goknest.json)')
        if not path: return
        project,result,imports = deepcopy(self.project),deepcopy(self.result),deepcopy(self.imports)
        def operation(sink,stop):
            from modules.nesting.storage import save_project
            save_project(project,path,result,overwrite=True,stop=stop,imports=imports); sink.put(('nest_message','Proje, geometrileri ve DXF yükleme listesiyle kaydedildi.'))
        self.jobs.start(self,operation)

    def open_project(self):
        if not self.can_start(): return
        path,_ = QFileDialog.getOpenFileName(self,'Nesting projesi aç','','Nesting (*.goknest.json)')
        if not path: return
        def operation(sink,stop):
            from modules.nesting.storage import load_project
            project,result,imports = load_project(path,with_imports=True)
            totals = calculate(project,result,complete=False,stop=stop) if result is not None else None
            sink.put(('nest_project',(project,result,imports,totals)))
        self.jobs.start(self,operation)

    def handle_events(self,events):
        imports_changed = False
        for kind,value in events:
            if kind == 'nest_progress':
                self.pending_progress = value
                if not self.progress_timer.isActive(): self.progress_timer.start()
            elif kind == 'nest_file':
                entry = next((e for e in self.imports if e['id'] == value['id']),None)
                if entry is not None:
                    entry.update(status=value['status'],detail=value['detail'])
                    if value['parts']: self.project.parts.extend(value['parts'])
                    imports_changed = True
            elif kind == 'nest_import_done':
                self.progress_timer.stop(); self.pending_progress = None
                self.refresh()
                self.set_status(f"Yükleme tamamlandı · {value['selected']} dosya · {value['ready']} hazır · {value['parts']} parça · "
                                f"{value['errors']} okunamadı · {value['cancelled']} durduruldu. "
                                + ('Sorunlu dosyalar listede; ayrıntı için çift tıklayın.' if value['errors'] or value['cancelled'] else 'Yerleştir ile plakaları sırayla doldurun.'),
                                bool(value['errors'] or value['cancelled']))
            elif kind == 'nest_result':
                self.progress_timer.stop(); self.pending_progress = None; self.show_result(*value)
            elif kind == 'nest_project':
                self.price_candidate = None; self.price_timer.stop()
                self.project,result,self.imports,totals = value
                self.search.clear(); self.sync_forms(); self.refresh(); self.show_result(result,totals)
                self.parts_toggle.setChecked(True)
                if result is None: self.set_status('Proje açıldı. Otomatik yerleşim yapabilirsiniz.')
            elif kind == 'nest_message': self.set_status(value)
            elif kind == 'job_error':
                self.progress_timer.stop(); self.pending_progress = None
                for entry in self.imports:
                    if entry['status'] in ('pending','running'):
                        entry.update(status='error',detail='Dosya okunamadı: '+value['error']); imports_changed = True
                self.set_status(value['error'],True)
        if imports_changed: self.refresh()
