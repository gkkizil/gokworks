"""Integrated DXF nesting workspace; every heavy operation uses the existing job runner."""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter, QTabWidget,
    QTableView, QComboBox, QLineEdit, QFileDialog, QDialog)

from ..components import BasePage, card, label, button, scroll, configure_view, show_details, ValueForm
from ..models import TableModel, Column, FilterProxy
from .nesting_widgets import Editor, Values, NestingCanvas
from nesting.materials import new_project, SIZES
from nesting.models import Material, Sheet, Options, Operations, uid, number, integer
from nesting.geometry import polygons
from nesting.accounting import mass, calculate

IMPORT_LABELS = {'pending':'Sırada', 'running':'Okunuyor', 'success':'Hazır', 'error':'Okunamadı', 'cancelled':'Durduruldu'}


def fmt(v):
    if v is None: return '—'
    return f'{v:,.3f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class NestingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Nesting · Sac maliyeti',
                         'DXF parçalarını yükleyin, sac stokunu tanımlayın ve gerçek konturlarla yerleştirin.')
        self.project = new_project(); self.result = None; self.loading = False
        self.imports = []; self.sheet_totals = []
        self.price_candidate = None
        self.price_timer = QTimer(self); self.price_timer.setSingleShot(True); self.price_timer.setInterval(220)
        self.price_timer.timeout.connect(self.reprice)
        self.jobs.finished.connect(lambda:self.price_timer.start() if self.price_candidate is not None else None)
        self.pending_progress = None
        self.progress_timer = QTimer(self); self.progress_timer.setSingleShot(True); self.progress_timer.setInterval(80)
        self.progress_timer.timeout.connect(self.flush_progress)
        self.action('Proje aç', self.open_project)
        self.action('Kaydet', self.save_project)
        name_row = QHBoxLayout(); name_row.addWidget(label('Proje adı', 'muted'))
        self.name = QLineEdit(self.project.name); self.name.textEdited.connect(self.name_changed)
        name_row.addWidget(self.name,1); self.controls.append(self.name)
        self.engine_label = label('GOKWORKS NFP · Gerçek kontur', 'muted'); name_row.addWidget(self.engine_label)
        self.layout.addLayout(name_row)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(True)
        left, left_layout = card('1 · Parçalar')
        left.setMinimumWidth(230); self.parts_panel = left; self.compact = False
        self.import_button = button('DXF dosyalarını yükle', self.import_dialog, primary=True); left_layout.addWidget(self.import_button)
        self.search = QLineEdit(); self.search.setPlaceholderText('Parça ara…'); self.search.setClearButtonEnabled(True); left_layout.addWidget(self.search)
        self.part_model = TableModel([Column('Dosya / parça','code'),Column('Durum','status',lambda s:IMPORT_LABELS.get(s,s)),
                                     Column('Adet','quantity'),Column('Kalınlık','thickness',fmt),Column('Net kg','weight',fmt),Column('Açıklama','detail')])
        self.part_proxy = FilterProxy(self); self.part_proxy.setSourceModel(self.part_model)
        self.part_table = configure_view(QTableView()); self.part_table.setModel(self.part_proxy)
        for i, width in enumerate((180,95,55,80,90,360)): self.part_table.setColumnWidth(i,width)
        self.part_table.doubleClicked.connect(self.edit_part); self.search.textChanged.connect(self.part_proxy.set_query)
        left_layout.addWidget(self.part_table,1)
        buttons = QHBoxLayout(); buttons.addWidget(button('Düzenle', self.edit_part)); buttons.addWidget(button('Kaldır', self.remove_part)); left_layout.addLayout(buttons)
        self.import_info = label('Henüz DXF seçilmedi.', 'muted'); left_layout.addWidget(self.import_info)
        self.import_report_button = button('Yükleme ayrıntıları', self.show_import_report); left_layout.addWidget(self.import_report_button)
        self.part_info = label('Çift tıklayarak adet, malzeme ve kalınlığı düzenleyin.', 'muted'); left_layout.addWidget(self.part_info)
        self.splitter.addWidget(left); self.controls.append(left)
        self.tabs = QTabWidget()
        preview = QWidget(); layout = QVBoxLayout(preview); layout.setContentsMargins(0,8,0,0)
        toolbar = QHBoxLayout(); self.sheet_picker = QComboBox(); self.sheet_picker.setMinimumContentsLength(10)
        self.sheet_picker.currentIndexChanged.connect(self.render_sheet); toolbar.addWidget(self.sheet_picker,1)
        self.previous_sheet = button('‹', lambda:self.change_sheet(-1)); self.previous_sheet.setToolTip('Önceki plaka')
        self.next_sheet = button('›', lambda:self.change_sheet(1)); self.next_sheet.setToolTip('Sonraki plaka')
        toolbar.addWidget(self.previous_sheet); toolbar.addWidget(self.next_sheet)
        self.canvas = NestingCanvas()
        self.previous_sheet.setEnabled(False); self.next_sheet.setEnabled(False)
        toolbar.addWidget(button('Sığdır', self.canvas.fit)); toolbar.addWidget(button('+', lambda:self.canvas.scale(1.25,1.25)))
        toolbar.addWidget(button('−', lambda:self.canvas.scale(.8,.8))); layout.addLayout(toolbar)
        self.current_note = label('2 · Saclar ve malzemeler sekmesinden ölçüleri ve fiyatları belirleyin.', 'muted'); layout.addWidget(self.current_note)
        layout.addWidget(self.canvas,1)
        self.summary = label('Henüz yerleşim yok.', 'subtitle'); layout.addWidget(self.summary)
        self.cost_summary = label('', 'result'); layout.addWidget(self.cost_summary)
        self.preview_scroll = scroll(preview); self.tabs.addTab(self.preview_scroll, 'Yerleşim')
        self.stock_widget = self.build_stock(); self.tabs.addTab(self.stock_widget, 'Saclar ve malzemeler')
        self.parameters = self.build_parameters(); self.tabs.addTab(scroll(self.parameters), 'Yerleşim ve maliyet ayarları')
        self.controls.extend([self.stock_widget, self.parameters])
        self.splitter.addWidget(self.tabs); self.splitter.setStretchFactor(1,1); self.splitter.setSizes([300,800])
        self.layout.addWidget(self.splitter,1)
        footer = QGridLayout()
        self.nest_button = button('Yerleştir', self.start_nest, primary=True); footer.addWidget(self.nest_button,0,0)
        self.nest_button.setToolTip('Gerçek konturlarla otomatik yerleşimi başlat')
        self.verify_button = button('Doğrula', self.verify); footer.addWidget(self.verify_button,0,1)
        self.detail_button = button('Hesap ayrıntıları', self.show_calculations); footer.addWidget(self.detail_button,0,2)
        self.stop_button = button('Durdur',self.jobs.cancel); self.stop_button.setEnabled(False); footer.addWidget(self.stop_button,0,3)
        self.dxf_button = button('DXF dışa aktar', self.export_dxf); footer.addWidget(self.dxf_button,1,0)
        self.excel_button = button('Excel raporu', lambda:self.export_report('excel')); footer.addWidget(self.excel_button,1,1)
        self.pdf_button = button('PDF raporu', lambda:self.export_report('pdf')); footer.addWidget(self.pdf_button,1,2)
        self.new_button = button('Yeni proje',self.new_project); footer.addWidget(self.new_button,1,3); self.controls.append(self.new_button)
        self.result_controls = [self.verify_button,self.detail_button,self.dxf_button,self.excel_button,self.pdf_button]
        self.controls.append(self.nest_button); self.controls.extend(self.result_controls)
        self.layout.addLayout(footer); self.finish_layout(); self.refresh()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'tabs'): return
        compact = self.width() < 850
        if compact == self.compact: return
        self.compact = compact
        if compact:
            self.parts_panel.setParent(None); self.tabs.insertTab(0,self.parts_panel,'Parçalar')
        else:
            self.tabs.removeTab(self.tabs.indexOf(self.parts_panel)); self.splitter.insertWidget(0,self.parts_panel)
            self.parts_panel.show()
            self.splitter.setSizes([300,800])

    def selected(self, table):
        return table.currentIndex().data(Qt.UserRole) if table.currentIndex().isValid() else None

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
        self.result = None; self.sheet_totals = []; self.canvas.render(self.project,None,None); self.sheet_picker.clear()
        self.summary.setText('Yerleşim bekleniyor.'); self.cost_summary.setText('')
        self.update_buttons()
        if had_result: self.set_status('Parça, sac veya ayarlar değişti. Güncel sonuç için yeniden otomatik yerleşim yapın.')

    def name_changed(self, value):
        self.cost_changed(); self.project.name = value

    def cost_changed(self):
        if self.loading: return
        if self.result is not None:
            self.price_candidate = (self.project.placement_fingerprint(),deepcopy(self.result))
        self.invalidate(preserve_price_candidate=True)
        self.price_timer.start()

    def reprice(self):
        if self.price_candidate is None or self.busy or self.jobs.busy: return
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
        for control in self.result_controls: control.setEnabled(not self.busy and self.result is not None)

    def set_busy(self, busy):
        super().set_busy(busy); self.update_buttons()
        if not busy:
            self.progress_timer.stop(); self.pending_progress = None

    def flush_progress(self):
        value,self.pending_progress = self.pending_progress,None
        if value is not None and self.jobs.owner is self:
            self.progressChanged.emit(value[0],value[1]); self.set_status(value[2])

    def new_project(self):
        self.project = new_project(); self.result = None; self.imports = []; self.sync_forms(); self.refresh(); self.invalidate()
        self.set_status('Yeni proje hazır. Kaynak DXF dosyaları değiştirilmez.')

    def build_stock(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(label('2 · Kullanılabilir saclar', 'section'))
        self.sheet_model = TableModel([Column('Sac','name'),Column('En mm','width',fmt),Column('Boy mm','height',fmt),
                                      Column('t mm','thickness',fmt),Column('Malzeme','material'),Column('Stok','stock'),Column('Fiyat','price')])
        self.sheet_table = configure_view(QTableView()); self.sheet_table.setModel(self.sheet_model)
        self.sheet_table.doubleClicked.connect(self.edit_sheet); layout.addWidget(self.sheet_table,1)
        row = QHBoxLayout()
        for text, callback in [('Sac ekle',lambda:self.edit_sheet(new=True)),('Düzenle',self.edit_sheet),('Kaldır',self.remove_sheet)]: row.addWidget(button(text,callback))
        layout.addLayout(row)
        layout.addWidget(label('Stok adedi kadar plaka otomatik kullanılır: 1. plaka doldurulur, kalan parçalar 2., 3. plakaya geçer. '
                               'Farklı kalınlık ve malzemeler için ayrı sac tanımlayın.', 'muted'))
        layout.addWidget(label('Malzeme kütüphanesi · yaklaşık yoğunluklar, projeye özel düzenlenebilir', 'section'))
        self.material_model = TableModel([Column('Malzeme','name'),Column('Yoğunluk kg/m³','density',fmt),Column('Kaynak','source')])
        self.material_table = configure_view(QTableView()); self.material_table.setModel(self.material_model)
        self.material_table.doubleClicked.connect(self.edit_material); layout.addWidget(self.material_table,1)
        row = QHBoxLayout(); row.addWidget(button('Özel malzeme ekle',lambda:self.edit_material(new=True)))
        row.addWidget(button('Malzemeyi düzenle',self.edit_material)); layout.addLayout(row)
        return widget

    def build_parameters(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.form = f = ValueForm(Values(), '')
        f.text('gap','Bitmiş parçalar arası mesafe · mm',3); f.text('margin','Sac kenar payı · mm',10)
        f.text('kerf','Kesim kerf · mm',.2); f.check('rotation','Döndürmeye izin ver',True)
        f.text('angles','İzinli açılar · ; ile ayırın','0;90;180;270')
        f.text('angle_step','Serbest açı adımı · ° (boşsa yukarıdaki liste)','')
        f.check('grain_locked','Hadde yönünü koru · yalnız 0° / 180°',False)
        f.text('seconds','En fazla arama süresi · saniye',15); f.combo('quality','Optimizasyon kalitesi',('Hızlı','Dengeli','Yüksek'),'Dengeli')
        f.text('seed','Tekrarlanabilir arama seed',42)
        layout.addWidget(label('3 · Yerleşim ayarları','section')); layout.addWidget(f)
        layout.addWidget(label('Aynalama ve delik içine yerleşim kapalı. En iyi bulunan geçerli sonuç gösterilir; matematiksel optimum garantisi yok. '
                               'Kerf, CAM kesim yolu telafisi olarak uygulanmaz. Çarpışma aralığı max(parça mesafesi, kerf) ve eğri hata paylarıdır.', 'muted'))
        self.cost_form = c = ValueForm(Values(), '')
        for key, title in [('cut_price_m','Kesim · TL/m'),('piercing_price','Piercing · TL/kontur'),('setup','Tezgâh hazırlık · TL'),
                           ('fixed','Sabit gider · TL'),('profit_percent','Kâr · %'),('vat_percent','KDV · %')]: c.text(key,title,0)
        layout.addWidget(label('İsteğe bağlı operasyon giderleri','section')); layout.addWidget(c)
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
        o = Options(**{k:number(f.value(k),k) for k in ('gap','margin','kerf','seconds')},
                    rotation=f.value('rotation'), angles=angles, grain_locked=f.value('grain_locked'),
                    quality=f.value('quality'),seed=integer(f.value('seed'),'Seed',minimum=0,maximum=2**32-1))
        operations = Operations(**{key:number(self.cost_form.value(key),key) for key in asdict(self.project.operations)})
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
        finally: self.loading = False

    def refresh(self):
        rows = []
        for p in self.project.parts:
            g = p.polygon; m = self.project.material(p.material)
            rows.append(dict(id=p.id,code=p.code,quantity=p.quantity,thickness=p.thickness,weight=mass(g.area,p.thickness,m.density),
                             status='success',source=p.source,detail='Kesim konturu hazır.',kind='part'))
        rows.extend(dict(id=e['id'],code=Path(e['source']).name,quantity=None,thickness=e['options'].get('thickness',2),weight=None,
                         status=e['status'],source=e['source'],detail=e['detail'],kind='import')
                    for e in self.imports if e['status'] != 'success')
        self.part_model.replace(rows)
        self.sheet_model.replace([dict(asdict(s),price=f'{s.price_sheet:g} TL/levha' if s.pricing == 'sheet' else f'{s.price_kg:g} TL/kg') for s in self.project.sheets])
        self.material_model.replace([asdict(m) for m in self.project.materials]); self.update_buttons()
        counts = {status:sum(e['status'] == status for e in self.imports) for status in IMPORT_LABELS}
        if self.imports:
            self.import_info.setText(f"{len(self.imports)} dosya seçildi · {counts['success']} hazır · {counts['error']} sorunlu"
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
        row = self.selected(self.sheet_table)
        if row:
            self.project.sheets = [s for s in self.project.sheets if s.id != row['id']]; self.invalidate(); self.refresh()

    def edit_part(self, *args):
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
            f.form.addRow(label(f'Net alan {fmt(item.area)} mm² · X {fmt(bounds[2]-bounds[0])} × Y {fmt(bounds[3]-bounds[1])} mm\n'
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
        row = self.selected(self.part_table)
        if row:
            if row.get('kind') == 'import':
                self.imports = [e for e in self.imports if e['id'] != row['id']]
            else:
                self.project.parts = [p for p in self.project.parts if p.id != row['id']]
            self.invalidate(); self.refresh()

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
        self.search.clear(); self.invalidate()
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
            from nesting.batch_import import import_batch
            import_batch(entries,options,sink,stop)
        self.jobs.start(self,operation); self.set_status(f'{len(files)} DXF dosyası sıraya eklendi; konturlar okunuyor…')

    def start_nest(self):
        if not self.can_start(): return
        problems = [e for e in self.imports if e['status'] != 'success']
        if problems:
            return self.set_status(f'{len(problems)} dosya henüz hazır değil. Listede Okunamadı/Durduruldu yazan dosyaya çift tıklayıp yeniden okuyun veya Kaldır ile çıkarın.',True)
        try: self.read_parameters(); self.project.validate()
        except ValueError as error: return self.set_status(error,True)
        missing = sorted({(part.material,part.thickness) for part in self.project.parts
                          if not any(s.material == part.material and abs(s.thickness-part.thickness) <= 1e-7 and s.stock > 0 for s in self.project.sheets)})
        if missing:
            self.tabs.setCurrentWidget(self.stock_widget)
            return self.set_status('Sac tanımı / stok eksik: '+', '.join(f'{self.project.material(material).name} · {thickness:g} mm' for material,thickness in missing)
                                   + '. Sac ekle ile uygun kalınlıkta sac tanımlayın veya stok adedini artırın.',True)
        self.invalidate(); snapshot = deepcopy(self.project)
        def operation(sink,stop):
            from nesting.engine import nest
            result = nest(snapshot,stop=stop,progress=lambda percent,text:sink.put(('nest_progress',(percent,100,text))))
            totals = calculate(snapshot,result,complete=False)
            sink.put(('nest_result',(result,totals)))
        self.jobs.start(self,operation); self.tabs.setCurrentWidget(self.preview_scroll); self.set_status('Kontur yerleşimi aranıyor…')

    def show_result(self,result,totals=None):
        self.result = result
        if result is None: return self.invalidate()
        totals = totals or calculate(self.project,result,complete=False)
        self.sheet_totals = totals['sheets']
        self.sheet_picker.clear()
        for index,s in enumerate(totals['sheets'],1):
            self.sheet_picker.addItem(f"{index}. plaka · {s['name']} · {s['material']} · {s['thickness']:g} mm",(s['id'],s['number']))
        self.summary.setText(f"{totals['part_count']} parça · {totals['sheet_count']} levha · Verim %{fmt(totals['efficiency'])}\n"
                             f"Brüt {fmt(totals['gross_weight'])} kg · Net {fmt(totals['net_weight'])} kg · Fire {fmt(totals['waste_weight'])} kg")
        self.cost_summary.setText(f"{fmt(totals['material_cost'])} TL · Sac malzemesi")
        self.engine_label.setText(result.engine+' '+result.engine_version)
        self.current_note.setText('Nominal konturlar · Tekerlek: zoom · Sürükle: kaydır · Optimum garantisi yok')
        self.render_sheet(); self.update_buttons()
        if result.unplaced:
            codes = sorted({self.project.part(key).code for key in result.unplaced})
            self.set_status(f'{len(result.unplaced)} parça yerleşmedi: '+', '.join(codes)+'. Sac ölçüsü/stokunu ve süreyi kontrol edin. Üretim çıktısı kapalı.',True)
        else: self.set_status(f'Yerleşim doğrulandı · {totals["part_count"]} parça · {totals["sheet_count"]} levha · {result.elapsed:.1f} sn')

    def render_sheet(self):
        self.canvas.render(self.project,self.result,self.sheet_picker.currentData())
        index = self.sheet_picker.currentIndex(); count = self.sheet_picker.count()
        self.previous_sheet.setEnabled(index > 0); self.next_sheet.setEnabled(0 <= index < count-1)
        if self.result is not None and 0 <= index < len(self.sheet_totals):
            s = self.sheet_totals[index]
            quantity = sum((p.sheet_id,p.sheet_number) == (s['id'],s['number']) for p in self.result.placements)
            self.current_note.setText(f"{index+1}/{count} plaka · {quantity} parça · Verim %{fmt(s['efficiency'])} · Tekerlek: zoom · Sürükle: kaydır")

    def change_sheet(self, direction):
        index = self.sheet_picker.currentIndex()+direction
        if 0 <= index < self.sheet_picker.count(): self.sheet_picker.setCurrentIndex(index)

    def theme_changed(self):
        self.canvas.theme = self.context.appearance; self.render_sheet()

    def verify(self):
        if not self.can_start() or self.result is None: return
        project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from nesting.validation import validate_result
            validate_result(project,result,stop=stop); sink.put(('nest_message','Yerleşim doğrulandı: adetler, malzeme/kalınlık, stok, kenar payı ve kontur aralıkları uygun.'))
        self.jobs.start(self,operation)

    def show_calculations(self):
        if self.result is None: return
        try:
            from nesting.report import summary_rows
            totals = calculate(self.project,self.result,complete=False)
            text = '\n'.join(f'{k}: {v}' for k,v in summary_rows(self.project,self.result,totals))
            show_details(self,'Nesting · Hesap ve maliyet ayrıntıları',text)
        except ValueError as error: self.set_status(error,True)

    def export_report(self,kind):
        if not self.can_start() or self.result is None: return
        suffix = '.xlsx' if kind == 'excel' else '.pdf'
        path,_ = QFileDialog.getSaveFileName(self,'Nesting raporu','Nesting'+suffix,'Rapor (*'+suffix+')')
        if not path: return
        project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from nesting.report import export_excel,export_pdf
            (export_excel if kind == 'excel' else export_pdf)(project,result,path,overwrite=True,stop=stop)
            sink.put(('nest_message','Rapor kaydedildi: '+str(path)))
        self.jobs.start(self,operation)

    def export_dxf(self):
        if not self.can_start() or self.result is None: return
        folder = QFileDialog.getExistingDirectory(self,'DXF çıktısının kaydedileceği ana klasör')
        if not folder: return
        target = Path(folder)/('GOKWORKS-Nesting-'+uid()[:8]); project,result = deepcopy(self.project),deepcopy(self.result)
        def operation(sink,stop):
            from nesting.dxf_export import export_dxf
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
            from nesting.storage import save_project
            save_project(project,path,result,overwrite=True,stop=stop,imports=imports); sink.put(('nest_message','Proje, geometrileri ve DXF yükleme listesiyle kaydedildi.'))
        self.jobs.start(self,operation)

    def open_project(self):
        if not self.can_start(): return
        path,_ = QFileDialog.getOpenFileName(self,'Nesting projesi aç','','Nesting (*.goknest.json)')
        if not path: return
        def operation(sink,stop):
            from nesting.storage import load_project
            sink.put(('nest_project',load_project(path,with_imports=True)))
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
                self.project,result,self.imports = value; self.sync_forms(); self.refresh(); self.show_result(result)
                if result is None: self.set_status('Proje açıldı. Otomatik yerleşim yapabilirsiniz.')
            elif kind == 'nest_message': self.set_status(value)
            elif kind == 'job_error':
                self.progress_timer.stop(); self.pending_progress = None
                for entry in self.imports:
                    if entry['status'] in ('pending','running'):
                        entry.update(status='error',detail='Dosya okunamadı: '+value['error']); imports_changed = True
                self.set_status(value['error'],True)
        if imports_changed: self.refresh()
