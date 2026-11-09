"""Native workbench; all source parsing, splitting, nesting and export run as jobs.

Layout: left, the three things the user decides in order (1 source part, 2 how to split,
3 sheet and Nesting settings; constraints and joining are optional disclosures). Right,
the drawing with the split centre and forbidden zones, result tiles and the segment /
candidate tables. Bottom: Split → Optimize, then DXF export or transfer to Nesting.
"""
from copy import deepcopy
import math
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QCheckBox)
from shapely.geometry import box, mapping

from gui_qt.components import BasePage, Disclosure, ValueForm, button, configure_view, fit_columns, label, scroll
from gui_qt.theme import COLORS
from modules.nesting.materials import new_project
from modules.nesting.models import integer, number
from .analysis import analyze, load_parts, validate_source
from .canvas import SplitCanvas
from .models import SplitSettings

PREFIX = 'smart_splitting/'
METHODS = ('Eşit açısal', 'Kontur duyarlı')
PROFILE_HELP = {'Hızlı': 'en fazla 3 aday · aday başına 2 s', 'Dengeli': 'en fazla 7 aday · aday başına 3 s',
                'Detaylı': 'en fazla 13 aday · aday başına 5 s'}


def area_text(mm2):
    return f'{mm2/1e6:.4f} m²'.replace('.', ',') if abs(mm2) >= 1e5 else f'{mm2:.1f} mm²'.replace('.', ',')


def length_text(mm):
    return f'{mm/1000:.3f} m'.replace('.', ',') if mm >= 1e4 else f'{mm:.1f} mm'.replace('.', ',')


class SectionedForm(QObject):
    """Several ValueForms (one per section) behaving as one form: value, set_value, fields, changed."""
    changed = Signal(str)

    def __init__(self, settings):
        super().__init__(); self.settings = settings; self.forms = []; self.fields = {}

    def section(self):
        form = ValueForm(self.settings, PREFIX); form.changed.connect(self.changed); self.forms.append(form)
        return form

    def owner(self, key):
        return next(f for f in self.forms if key in f.fields)

    def collect(self):
        self.fields = {k: w for f in self.forms for k, w in f.fields.items()}

    def value(self, key):
        return self.owner(key).value(key)

    def values(self):
        return {k: self.value(k) for k in self.fields}

    def set_value(self, key, value):
        self.owner(key).set_value(key, value)

    def show_field(self, key, visible):
        self.owner(key).show_field(key, visible)


class Tile(QFrame):
    """One result value with its unit and a short meaning."""

    def __init__(self, title, note=''):
        super().__init__(); self.setProperty('card', True)
        box_ = QVBoxLayout(self); box_.setContentsMargins(10, 6, 10, 6); box_.setSpacing(0)
        self.title = label(title, 'muted', wrap=False); self.value = label('—', 'result', wrap=False)
        self.note = label(note, 'muted')
        for widget in (self.title, self.value, self.note): box_.addWidget(widget)

    def set(self, value, note=None, role=None):
        self.value.setText(value)
        if note is not None: self.note.setText(note)
        self.value.setProperty('role', role or 'result'); self.value.style().unpolish(self.value); self.value.style().polish(self.value)


class TileRow(QWidget):
    """Six tiles in one row when there is room, otherwise two rows of three."""

    def __init__(self, tiles):
        super().__init__(); self.tiles = list(tiles); self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0); self.grid.setSpacing(6); self.columns = 0; self.reflow(6)

    def reflow(self, columns):
        if columns == self.columns: return
        self.columns = columns
        for tile in self.tiles: self.grid.removeWidget(tile)
        for i, tile in enumerate(self.tiles): self.grid.addWidget(tile, i // columns, i % columns)
        for col in range(6): self.grid.setColumnStretch(col, 1 if col < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event); self.reflow(6 if self.width() >= 720 else 3)


def step_title(number_, text):
    return label(f'{number_}  {text}', 'section')


class SmartSplittingPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Akıllı Parça Bölme','Büyük bir parçayı levhaya sığacak segmentlere bölün; konturu ve delikleri koruyun, fireyi Nesting ile karşılaştırın.')
        self.sources=[]; self.meta=[]; self.source=None; self.solution=None; self.optimization=None
        self.solutions={}; self.part_errors={}; self.current=-1
        self.dxf_button=self.action('DXF/DWG ekle…',self.import_dialog)
        self.stop_button=self.action('Durdur',self.jobs.cancel,locked=False)
        self.action('Sıfırla',self.clear)
        self.form=SectionedForm(self.settings)

        # ---------------------------------------------------------------- left: decisions in order
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,8,0); ll.setSpacing(10)
        ll.addWidget(step_title(1,'Bölünecek parçalar'))
        sources=QHBoxLayout(); sources.setSpacing(6)
        self.open_button=button('DXF/DWG ekle…',self.import_dialog,primary=True)
        self.open_button.setToolTip('Bir veya birden çok DXF/DWG seçin. Adet ve kalınlık dosya adından okunur (ör. “Flanş - 3 mm - 5 adet.dwg”). '
                                    'DWG, uygulamadaki dönüştürücüyle okunur; ek program gerekmez.')
        self.nesting_button=button('Nesting’den al',self.from_nesting)
        self.nesting_button.setToolTip('Nesting’de seçili tek parçayı geometri, adet ve kalınlığıyla kopyalar; Nesting listesi değişmez.')
        sources.addWidget(self.open_button); sources.addWidget(self.nesting_button); sources.addStretch(1); ll.addLayout(sources)
        self.source_table=QTableWidget(0,4); self.source_table.setHorizontalHeaderLabels(('Parça','Adet','mm','Durum'))
        for col,tip in ((1,'Adet: dosya adından okunur; çift tıklayıp düzeltin.'),(2,'Sac kalınlığı · mm: dosya adından okunur; çift tıklayıp düzeltin.')):
            self.source_table.horizontalHeaderItem(col).setToolTip(tip)
        configure_view(self.source_table); self.source_table.setSortingEnabled(False)
        self.source_table.setAccessibleName('Bölünecek parçalar; adet ve kalınlık düzenlenebilir')
        self.source_table.setToolTip('Satırı seçin: çizim ve sonuçlar o parçayı gösterir. Adet ve kalınlığa çift tıklayıp düzeltebilirsiniz.')
        fit_columns(self.source_table,elastic=0,minimum=36,defaults={0:110,1:44,2:40,3:62})
        self.source_table.itemSelectionChanged.connect(lambda:self.select_source(self.selected_row()))
        self.source_table.itemChanged.connect(self.part_edited)
        self.source_table.setMinimumHeight(70); self.source_table.setMaximumHeight(190); self.source_table.hide()
        ll.addWidget(self.source_table)
        self.info=label('Henüz parça yok. Bir DXF açın veya Nesting’den bir parça alın.','muted'); self.info.setTextFormat(Qt.PlainText)
        ll.addWidget(self.info)
        reading=self.form.section()
        reading.combo('unit','Birimsiz DXF’in birimi',('Seçilmedi','mm','cm','inch'))
        reading.text('tolerance','Eğri sapması · mm',.05)
        ll.addWidget(Disclosure('DXF okuma',reading))

        ll.addWidget(step_title(2,'Nasıl bölünsün?'))
        split=self.form.section()
        split.text('count','Segment sayısı',6); split.text('quantity','Adet (dosya adında yoksa)',1)
        split.combo('mode','Bölme yöntemi',METHODS)
        split.text('start_angle','İlk kesim açısı · °',0)
        split.combo('center_mode','Bölme merkezi',('Sınır kutusu merkezi','Alan ağırlık merkezi','Özel merkez'))
        split.text('center_x','Özel merkez X · mm',0); split.text('center_y','Özel merkez Y · mm',0)
        ll.addWidget(split)
        self.method_help=label('','muted'); ll.addWidget(self.method_help)
        limits=self.form.section()
        limits.text('min_width','En dar segment genişliği · mm',1)
        limits.text('min_web','En ince et ön kontrolü · mm',0)
        limits.text('hole_clearance','Delik/slota en yakın kesim · mm',0)
        limits.text('forbidden','Yasaklı kutular','')
        holder=QWidget(); hl=QVBoxLayout(holder); hl.setContentsMargins(0,0,0,0); hl.addWidget(limits)
        hl.addWidget(label('Yasaklı kutular: x,y,en,boy; birden fazlası için ; ile ayırın (ör. 100,50,40,40). Koordinatlar parçanın sol alt köşesine göre mm’dir. Kutular çizimde kırmızı taralı görünür.','muted'))
        ll.addWidget(Disclosure('Kısıtlar',holder))

        ll.addWidget(step_title(3,'Levha ve Nesting'))
        sheet=self.form.section()
        sheet.text('sheet_width','Levha eni · mm',1500); sheet.text('sheet_height','Levha boyu · mm',3000)
        sheet.text('thickness','Kalınlık (dosya adında yoksa) · mm',2)
        sheet.combo('material','Malzeme',[m.id for m in new_project().materials])
        sheet.combo('profile','Fire araması',('Hızlı','Dengeli','Detaylı'))
        ll.addWidget(sheet)
        self.profile_help=label('','muted'); ll.addWidget(self.profile_help)
        nest=self.form.section()
        nest.text('margin','Levha kenar payı · mm',10); nest.text('gap','Parça aralığı · mm',3)
        nest.text('kerf','Kesim boşluğu (kerf) · mm',.2); nest.check('rotation','Döndürmeye izin ver',True)
        nest.text('angles','İzin verilen açılar · ; ile','0;90;180;270')
        ll.addWidget(Disclosure('Yerleşim ayarları',nest))
        joining=self.form.section()
        joining.combo('joining','Birleştirme yöntemi',('Kaynak','Cıvata','Diğer'))
        joining.text('weld_gap','Kaynak boşluğu · mm',0); joining.text('allowance','İşleme payı · mm',0)
        jholder=QWidget(); jl=QVBoxLayout(jholder); jl.setContentsMargins(0,0,0,0); jl.addWidget(joining)
        jl.addWidget(label('Yöntem bilgi amaçlıdır; kaynak ağzı veya bağlantı dayanımı hesaplanmaz. Kaynak boşluğu ile işleme payı aynı anda kullanılamaz.','muted'))
        ll.addWidget(Disclosure('Birleştirme',jholder))
        ll.addStretch(1)
        self.form.collect()
        left_scroll=self.left_scroll=scroll(left); left_scroll.setMinimumWidth(330)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # the form follows the column width

        # ---------------------------------------------------------------- right: drawing and results
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(8,0,0,0); rl.setSpacing(6)
        toolbar=QHBoxLayout(); toolbar.setSpacing(10)
        self.original=QCheckBox('Orijinal konturu göster'); self.original.toggled.connect(self.redraw)
        toolbar.addWidget(self.original)
        self.legend=label('Kesikli mavi: birleştirme çizgisi · sarı artı: bölme merkezi · kırmızı tarama: yasaklı bölge','muted',wrap=False)
        toolbar.addWidget(self.legend,1)
        self.canvas=SplitCanvas(); toolbar.addWidget(button('Sığdır',self.canvas.fit))
        rl.addLayout(toolbar); rl.addWidget(self.canvas,3)
        self.tiles={'segments':Tile('Segment','kesim parçası'),'area':Tile('Net imalat alanı','adetler dahil'),
                    'seam':Tile('Birleştirme','parça başına'),'check':Tile('Kontrol','alan ve kontur'),
                    'sheets':Tile('Levha','optimize edince'),'waste':Tile('Fire','optimize edince')}
        self.tile_row=TileRow(self.tiles.values()); rl.addWidget(self.tile_row)
        self.summary=label('Henüz bölme sonucu yok.','muted'); self.summary.setTextFormat(Qt.PlainText); rl.addWidget(self.summary)
        self.segments_table=self.make_table(('Segment','Adet','Net alan','İmalat alanı','En × boy · mm','Genişlik · mm','Birleşim · mm','Komşular'),{0:190})
        self.candidate_table=self.make_table(('Aday','Durum','Levha','Brüt alan · m²','Fire · %','Birleşim · mm','Süre · s'),{0:170,1:200})
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.segments_table,'Segmentler'); self.tabs.addTab(self.candidate_table,'Aday karşılaştırması')
        rl.addWidget(self.tabs,2)
        self.warning=label('Geometrik ön kontroldür; dayanım veya kaynak onayı değildir.','muted'); rl.addWidget(self.warning)
        self.workspace=QSplitter(); self.workspace.addWidget(left_scroll); self.workspace.addWidget(right)
        self.workspace.setChildrenCollapsible(False); self.workspace.setStretchFactor(1,1); self.workspace.setSizes([400,760])
        self.layout.addWidget(self.workspace,1)

        # ---------------------------------------------------------------- bottom: the flow
        actions=QHBoxLayout(); actions.setSpacing(8)
        self.split_button=button('Parçayı Böl',self.run_split,primary=True)
        self.all_button=button('Tümünü Böl',self.run_all)
        self.all_button.setToolTip('Listedeki bütün parçaları aynı bölme ayarlarıyla tek seferde böler.')
        self.optimize_button=button('Fireyi Optimize Et',lambda:self.run_split(optimize=True))
        self.optimize_button.setToolTip('Farklı bölmeleri gerçek Nesting yerleşiminde karşılaştırır; segment sayısı değişmez.')
        self.next_hint=label('','muted',wrap=False)
        self.export_button=button('DXF Dışa Aktar…',self.export_dialog)
        self.export_button.setToolTip('Her segment için ayrı DXF, birleşik DXF ve BOLME_RAPORU.json; yazılanlar yeniden okunup doğrulanır.')
        self.transfer_button=button('Nesting’e Aktar →',self.transfer)
        self.transfer_button.setToolTip('Segmentleri bağımsız parça türleri olarak Nesting’e ekler; diğer parçalar korunur.')
        for widget in (self.split_button,self.all_button,self.optimize_button): actions.addWidget(widget)
        actions.addSpacing(12); actions.addWidget(self.next_hint); actions.addStretch(1)
        for widget in (self.export_button,self.transfer_button): actions.addWidget(widget)
        for widget in (self.split_button,self.all_button,self.optimize_button,self.transfer_button,self.export_button): self.controls.append(widget)
        self.layout.addLayout(actions); self.controls.extend((left,self.original))
        self.form.changed.connect(self.invalidate); self.invalidate()
        self.set_status('1 DXF’leri ekleyin → 2 Bölme ayarlarını girin → Parçayı Böl / Tümünü Böl → 3 DXF’e veya Nesting’e aktarın.')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # Narrow windows: labels above their fields, so numbers are never cut off in the left column.
        compact=self.width()<1100
        from PySide6.QtWidgets import QFormLayout
        for form in self.form.forms:
            policy=QFormLayout.WrapAllRows if compact else QFormLayout.WrapLongRows
            if form.form.rowWrapPolicy()!=policy: form.form.setRowWrapPolicy(policy)
        self.left_scroll.setMinimumWidth(270 if compact else 330)
        self.next_hint.setVisible(not compact)   # the buttons themselves say what comes next

    def make_table(self,headers,defaults=None):
        table=configure_view(QTableWidget(0,len(headers))); table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers); table.setSortingEnabled(False)
        fit_columns(table,elastic=0,minimum=90,defaults=defaults or {}); table.setMinimumHeight(90)
        return table

    def settings_value(self):
        f=self.form
        def signed(key):
            try: value=float(str(f.value(key)).replace(',','.'))
            except (ValueError,TypeError): raise ValueError(key+': sonlu sayı gerekli.') from None
            if not math.isfinite(value): raise ValueError(key+': sonlu sayı gerekli.')
            return value
        numeric={k:number(f.value(k),k,positive=k in ('sheet_width','sheet_height','thickness','min_width'))
                 for k in ('sheet_width','sheet_height','thickness','min_width','min_web','hole_clearance','margin','gap','kerf','weld_gap','allowance')}
        custom=f.value('center_mode')=='Özel merkez'
        value=SplitSettings(**numeric,count=integer(f.value('count'),'Segment sayısı',minimum=2,maximum=64),
            quantity=integer(f.value('quantity'),'Parça adedi'),start_angle=signed('start_angle'),
            center=(signed('center_x'),signed('center_y')) if custom else None,
            center_mode='centroid' if f.value('center_mode')=='Alan ağırlık merkezi' else 'bounds',
            angles=tuple(float(a.strip().replace(',','.')) for a in f.value('angles').split(';') if a.strip()),
            rotation=f.value('rotation'),profile=f.value('profile'),material=f.value('material'),joining=f.value('joining'),
            forbidden=tuple(mapping(p) for p in self.forbidden_boxes()))
        value.validate(); return value

    def part_settings(self, index, base=None):
        """Shared split settings with the part's own quantity and thickness (file name or table edit)."""
        from dataclasses import replace
        base=base or self.settings_value(); meta=self.meta[index]
        value=replace(base,quantity=meta.get('quantity') or base.quantity,thickness=meta.get('thickness') or base.thickness)
        value.validate(); return value

    def forbidden_boxes(self, strict=True):
        boxes=[]
        for row in self.form.value('forbidden').split(';'):
            if not row.strip(): continue
            try:
                x,y,w,h=map(float,row.split(','))
                if not all(math.isfinite(v) for v in (x,y,w,h)) or min(w,h)<=0: raise ValueError
            except (ValueError,TypeError):
                if strict: raise ValueError('Yasaklı bölge: x,y,en,boy biçiminde pozitif ölçüler girin (ör. 100,50,40,40).') from None
                continue
            boxes.append(box(x,y,x+w,y+h))
        return boxes

    def preview_center(self):
        """Where the split centre is for the drawing (display only; the splitter decides for real)."""
        if self.solution is not None: return tuple(self.solution.center)
        if self.source is None: return None
        mode=self.form.value('center_mode')
        if mode=='Özel merkez':
            try: return (float(self.form.value('center_x').replace(',','.')),float(self.form.value('center_y').replace(',','.')))
            except ValueError: return None
        if mode=='Alan ağırlık merkezi':
            point=self.source.polygon.centroid; return (point.x,point.y)
        x0,y0,x1,y1=self.source.polygon.bounds; return ((x0+x1)/2,(y0+y1)/2)

    def invalidate(self,*args):
        self.solution=None; self.optimization=None
        if self.sender() is not self.source_table: self.solutions={}; self.part_errors={}
        self.refresh_sources()
        self.segments_table.setRowCount(0); self.candidate_table.setRowCount(0)
        self.summary.setText('Ayarlar değişti; yeniden bölün veya optimize edin.' if self.source is not None else 'Henüz bölme sonucu yok.')
        custom=self.form.value('center_mode')=='Özel merkez'
        for key in ('center_x','center_y'):
            self.form.fields[key].setEnabled(custom)
            self.form.fields[key].setToolTip('' if custom else 'Yalnız “Bölme merkezi: Özel merkez” seçilince kullanılır.')
        self.method_help.setText('Eşit dilimler; deliklere bakmaz.' if self.form.value('mode')=='Eşit açısal'
                                 else 'Kesim açılarını delik ve yasaklı bölgelerden kaçacak şekilde ±%33 kaydırır.')
        self.profile_help.setText('Fireyi Optimize Et: '+PROFILE_HELP.get(self.form.value('profile'),''))
        notes={'segments':'kesim parçası','area':'adetler dahil','seam':'parça başına','check':'alan ve kontur','sheets':'optimize edince','waste':'optimize edince'}
        for key,note in notes.items(): self.tiles[key].set('—',note)
        self.warning.setText('Geometrik ön kontroldür; dayanım veya kaynak onayı değildir.'); self.warning.setProperty('role','muted')
        self.warning.style().unpolish(self.warning); self.warning.style().polish(self.warning)
        self.update_actions(); self.redraw()

    def update_actions(self):
        has_source=self.source is not None; has_solution=self.solution is not None
        self.split_button.setEnabled(not self.busy and has_source)
        self.optimize_button.setEnabled(not self.busy and has_source)
        self.all_button.setVisible(len(self.sources)>1); self.all_button.setEnabled(not self.busy and len(self.sources)>1)
        self.all_button.setText(f'Tümünü Böl ({len(self.sources)})')
        done=len(self.solutions); many=done>1
        self.transfer_button.setText(f'Nesting’e Aktar ({done}) →' if many else 'Nesting’e Aktar →')
        self.export_button.setText(f'DXF Dışa Aktar ({done})…' if many else 'DXF Dışa Aktar…')
        self.transfer_button.setToolTip(f'{done} bölünmüş parçanın segmentleri Nesting’e eklenir; diğer parçalar korunur.' if many else
                                        'Segmentleri bağımsız parça türleri olarak Nesting’e ekler; diğer parçalar korunur.')
        has_solution=has_solution or bool(self.solutions)
        self.transfer_button.setEnabled(not self.busy and has_solution)
        self.export_button.setEnabled(not self.busy and has_solution)
        self.transfer_button.setProperty('primary',has_solution); self.transfer_button.style().unpolish(self.transfer_button); self.transfer_button.style().polish(self.transfer_button)
        self.split_button.setProperty('primary',not has_solution); self.split_button.style().unpolish(self.split_button); self.split_button.style().polish(self.split_button)
        self.open_button.setProperty('primary',not has_source); self.open_button.style().unpolish(self.open_button); self.open_button.style().polish(self.open_button)
        self.next_hint.setText('Hesaplanıyor…' if self.busy else 'Sonraki: parça seçin' if not has_source
                               else 'Sonraki: Parçayı Böl veya Fireyi Optimize Et' if not has_solution
                               else 'Sonraki: DXF’e veya Nesting’e aktarın')
        reason='' if has_solution else 'Önce parçayı bölün.'
        for widget in (self.transfer_button,self.export_button):
            if not widget.isEnabled() and not self.busy: widget.setStatusTip(reason)

    def set_busy(self,busy):
        super().set_busy(busy); self.update_actions()

    def import_dialog(self):
        if not self.can_start(): return
        paths,_=QFileDialog.getOpenFileNames(self,'Bölünecek DXF/DWG dosyalarını seç (birden çok seçilebilir)','',
                                             'DXF/DWG (*.dxf *.DXF *.dwg *.DWG);;DXF (*.dxf *.DXF);;DWG (*.dwg *.DWG)')
        if paths: self.load_files(paths)

    def load_file(self,path):
        self.load_files([path],replace=True)

    def load_files(self,paths,*,replace=False):
        """Read every DXF in one job; a bad file is reported and the others still load."""
        if not self.can_start(): return
        try:
            unit=self.form.value('unit'); tolerance=number(self.form.value('tolerance'),'Eğri toleransı',positive=True)
            if tolerance>1: raise ValueError('Eğri toleransı en fazla 1 mm olabilir.')
        except ValueError as error: return self.set_status(error,True)
        paths=[str(p) for p in paths]
        def operation(sink,stop):
            from modules.nesting.filename_parser import parse_filename
            parts,metas,errors=[],[],[]
            for i,path in enumerate(paths):
                sink.put(('split_progress',(i,len(paths),f'Okunuyor: {Path(path).name}')))
                try:
                    found=load_parts(path,unit=None if unit=='Seçilmedi' else unit,tolerance=tolerance,stop=stop)
                except (ValueError,OSError,TimeoutError) as error:
                    errors.append(f'{Path(path).name}: {error}'); continue
                info=parse_filename(path); stem=Path(path).stem
                for part in found:
                    # “Flanş - 3 mm - 5 adet” → part “Flanş”; segment names stay short (Flanş_SEG_001).
                    if info.code and info.code!=stem and part.code.startswith(stem): part.code=info.code+part.code[len(stem):]
                    parts.append(part); metas.append(dict(file=Path(path).name,quantity=info.quantity,thickness=info.thickness))
            sink.put(('split_sources',(parts,metas,errors,replace)))
        self.jobs.start(self,operation); self.set_status(f'{len(paths)} dosya okunuyor…'+(' DWG’ler önce DXF’e çevrilir.' if any(p.lower().endswith('.dwg') for p in paths) else ''))

    def set_sources(self,parts,metas=None,*,replace=True):
        metas=metas or [dict(file='',quantity=None,thickness=None) for _ in parts]
        if replace: self.sources,self.meta=[],[]
        known={(p.source_sha256,p.code) for p in self.sources}
        for part,meta in zip(deepcopy(parts),metas):
            if (part.source_sha256,part.code) in known and part.source_sha256: continue
            self.sources.append(part); self.meta.append(dict(meta)); known.add((part.source_sha256,part.code))
        self.solutions={}; self.part_errors={}
        self.refresh_sources(); self.select_source(0 if replace or self.current<0 else self.current)

    def refresh_sources(self):
        table=self.source_table; table.blockSignals(True); table.setRowCount(len(self.sources))
        for i,(part,meta) in enumerate(zip(self.sources,self.meta)):
            status=('✓ '+str(len(self.solutions[i].segments))) if i in self.solutions else '✕ hata' if i in self.part_errors else 'bekliyor'
            detail=(f'{len(self.solutions[i].segments)} segment, doğrulandı' if i in self.solutions else
                    'Bölünemedi: '+self.part_errors[i] if i in self.part_errors else 'Henüz bölünmedi')
            cells=(part.code,str(meta.get('quantity') or '—'),f"{meta['thickness']:g}" if meta.get('thickness') else '—',status)
            for j,text in enumerate(cells):
                item=QTableWidgetItem(text)
                if j in (1,2): item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                else: item.setFlags(item.flags()&~Qt.ItemIsEditable)
                item.setToolTip({0:meta.get('file') or part.code,1:'Boşsa “Adet (dosya adında yoksa)” kullanılır.',
                                 2:'Boşsa “Kalınlık (dosya adında yoksa)” kullanılır.',3:detail}[j])
                if j==3 and i in self.part_errors: item.setForeground(QColor(COLORS[self.context.appearance]['danger']))
                if j==3 and i in self.solutions: item.setForeground(QColor(COLORS[self.context.appearance]['success']))
                table.setItem(i,j,item)
        table.blockSignals(False); table.setVisible(bool(self.sources))

    def selected_row(self):
        rows=self.source_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def part_edited(self,item):
        """Adet/kalınlık edited in the list: only that part's result becomes stale."""
        row,col=item.row(),item.column(); text=item.text().strip().replace(',','.')
        key='quantity' if col==1 else 'thickness'
        try:
            value=None if text in ('','—') else (int(text) if key=='quantity' else float(text))
            if value is not None and (value<=0 or (key=='thickness' and not math.isfinite(value))): raise ValueError
        except ValueError:
            self.set_status(('Adet pozitif tam sayı' if key=='quantity' else 'Kalınlık pozitif sayı')+' olmalı.',True)
            self.refresh_sources(); return
        self.meta[row][key]=value; self.solutions.pop(row,None); self.part_errors.pop(row,None)
        if row==self.current: self.solution=None; self.optimization=None
        self.refresh_sources(); self.update_actions(); self.redraw()

    def select_source(self,index):
        if index<0 and self.sources: return
        self.current=index
        self.source=self.sources[index] if 0<=index<len(self.sources) else None
        if self.source is not None and self.selected_row()!=index:
            self.source_table.blockSignals(True); self.source_table.selectRow(index); self.source_table.blockSignals(False)
        if self.source is not None:
            a=analyze(self.source); b=a['bounds']
            self.info.setText(f"{self.source.code}\n{a['kind']} · {b[2]-b[0]:.1f} × {b[3]-b[1]:.1f} mm · {a['holes']} iç kontur\nNet alan {area_text(a['area'])}")
            self.info.setProperty('role',None); self.info.style().unpolish(self.info); self.info.style().polish(self.info)
        solved=self.solutions.get(index)
        self.solution=None; self.optimization=None
        self.segments_table.setRowCount(0); self.candidate_table.setRowCount(0)
        if solved is not None: self.show_solution(solved,announce=False)
        else:
            for key in ('segments','area','seam','check','sheets','waste'): self.tiles[key].set('—')
            self.summary.setText(('Bölünemedi: '+self.part_errors[index]) if index in self.part_errors else
                                 'Bu parça henüz bölünmedi.' if self.source is not None else 'Henüz bölme sonucu yok.')
            self.update_actions(); self.redraw()

    def from_nesting(self):
        if not self.can_start(): return
        page=self.context.pages['nesting']; ids=page.selected_part_ids()
        if len(ids)!=1: return self.set_status('Nesting’de tek parça seçin; sonra “Nesting’den al” düğmesini kullanın.',True)
        part=deepcopy(page.project.part(next(iter(ids))))
        try: validate_source(part)
        except ValueError as error: return self.set_status(error,True)
        self.set_sources([part],[dict(file='Nesting',quantity=None,thickness=None)]); self.form.set_value('quantity',part.quantity); self.form.set_value('thickness',part.thickness)
        if part.material in {m.id for m in new_project().materials}: self.form.set_value('material',part.material)
        self.set_status('Seçili Nesting parçası kopyalandı; Nesting listesi değişmedi.')

    def run_split(self,*,optimize=False):
        if not self.can_start() or self.source is None: return
        try: settings=self.part_settings(self.current)
        except (ValueError,TypeError) as error: return self.set_status(error,True)
        source=deepcopy(self.source)
        mode='smart' if self.form.value('mode')=='Kontur duyarlı' else 'equal'
        self.solution=None; self.optimization=None; self.solutions.pop(self.current,None); self.part_errors.pop(self.current,None)
        self.segments_table.setRowCount(0); self.candidate_table.setRowCount(0); self.refresh_sources()
        def operation(sink,stop):
            if optimize:
                from .optimizer import optimize as search
                result=search(source,settings,stop=stop,progress=lambda i,n,text:sink.put(('split_progress',(i,n,text))))
                sink.put(('split_optimized',result))
            else:
                from .splitter import split
                sink.put(('split_solution',split(source,settings,mode=mode,stop=stop)))
        self.jobs.start(self,operation)
        self.set_status('Bölme adayları gerçek Nesting yerleşiminde karşılaştırılıyor…' if optimize else 'Parça bölünüyor ve doğrulanıyor…')

    def run_all(self):
        """Split every listed part with the same settings; each failure is kept beside its part."""
        if not self.can_start() or not self.sources: return
        try:
            base=self.settings_value(); jobs=[(i,deepcopy(p),self.part_settings(i,base)) for i,p in enumerate(self.sources)]
        except (ValueError,TypeError) as error: return self.set_status(error,True)
        mode='smart' if self.form.value('mode')=='Kontur duyarlı' else 'equal'
        self.solutions={}; self.part_errors={}; self.solution=None; self.optimization=None; self.refresh_sources()
        def operation(sink,stop):
            from .splitter import split
            done,failed={},{}
            for n,(i,part,settings) in enumerate(jobs):
                sink.put(('split_progress',(n,len(jobs),f'Bölünüyor {n+1}/{len(jobs)}: {part.code}')))
                try: done[i]=split(part,settings,mode=mode,stop=stop)
                except InterruptedError: raise
                except (ValueError,ArithmeticError) as error: failed[i]=str(error)
            sink.put(('split_batch',(done,failed)))
        self.jobs.start(self,operation); self.set_status(f'{len(jobs)} parça aynı ayarlarla bölünüyor…')

    def show_solution(self,solution,announce=True):
        self.solution=solution; quantity=solution.settings.quantity
        if 0<=self.current<len(self.sources): self.solutions[self.current]=solution; self.part_errors.pop(self.current,None)
        rows=[]
        for s in solution.segments:
            x0,y0,x1,y1=s.blank.bounds
            rows.append((f'{s.original_name}_SEG_{s.number:03d}',quantity,area_text(s.nominal.area),area_text(s.blank.area),
                         f'{x1-x0:.1f} × {y1-y0:.1f}',f'{s.minimum_width:.1f}',f'{s.seam_length:.1f}',', '.join(map(str,s.neighbors))))
        self.fill(self.segments_table,rows)
        total=sum(s.blank.area for s in solution.segments)*quantity
        largest=max(max(s.blank.bounds[2]-s.blank.bounds[0],s.blank.bounds[3]-s.blank.bounds[1]) for s in solution.segments)
        self.tiles['segments'].set(f'{len(rows)} × {quantity}',f'{len(rows)*quantity} kesim parçası')
        self.tiles['area'].set(area_text(total),'adetler dahil')
        self.tiles['seam'].set(length_text(solution.seam_length),'parça başına')
        self.tiles['check'].set('✓ Doğru','alan ve kontur',role='success')
        self.tiles['check'].setToolTip('Segment sayısı, alan korunumu, orijinalle birleşim ve segment çakışmaları bağımsız kontrol edildi.')
        self.summary.setText(f'En büyük segment {largest:.0f} mm · levha {solution.settings.sheet_width:g} × {solution.settings.sheet_height:g} mm.'
                             + (' Segmentler levhaya sığmayabilir; Fireyi Optimize Et ile kontrol edin.'
                                if largest>max(solution.settings.sheet_width,solution.settings.sheet_height) else ''))
        opens=[w for w in solution.warnings if 'delik' in w.lower() or 'slot' in w.lower()]
        self.warning.setText(('Dikkat: '+' '.join(opens)+' — ' if opens else '')
                             +'Geometrik ön kontroldür; dayanım veya kaynak onayı değildir.')
        self.warning.setToolTip('\n'.join(solution.warnings))
        self.warning.setProperty('role','warning' if opens else 'muted'); self.warning.style().unpolish(self.warning); self.warning.style().polish(self.warning)
        self.refresh_sources(); self.redraw(); self.update_actions()
        if announce: self.set_status('Segmentler oluşturuldu; nominal alan ve kontur doğrulandı.')

    def fill(self,table,rows,highlight=None):
        table.setRowCount(len(rows))
        accent=QColor(COLORS[self.context.appearance]['selected'])
        for i,row in enumerate(rows):
            for j,value in enumerate(row):
                item=QTableWidgetItem(str(value))
                if j and isinstance(value,(int,float)) or (j and str(value)[:1].isdigit()): item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                if highlight is not None and i==highlight: item.setBackground(accent)
                if j==0: item.setToolTip(str(value))
                table.setItem(i,j,item)

    def redraw(self,*args):
        self.canvas.show_geometry(self.source,self.solution,self.original.isChecked(),
                                  center=self.preview_center(),forbidden=self.forbidden_boxes(strict=False))

    def theme_changed(self):
        if hasattr(self,'canvas'): self.canvas.theme=self.context.appearance; self.redraw()

    def ready_solutions(self):
        found=dict(self.solutions)
        if self.solution is not None and 0<=self.current: found[self.current]=self.solution
        return [found[i] for i in sorted(found)]

    def transfer(self):
        solutions=self.ready_solutions()
        if not self.can_start() or not solutions: return
        from .adapter import transfer_to_nesting
        nesting=self.context.pages['nesting']; snapshot=deepcopy(nesting.project)
        try:
            for solution in solutions: transfer_to_nesting(nesting,solution)
        except ValueError as error:
            nesting.project=snapshot; nesting.refresh()   # all or nothing
            return self.set_status(error,True)
        if len(solutions)>1:
            nesting.set_status(f'{len(solutions)} parçanın segmentleri Nesting’e aktarıldı.')
        self.context.navigate('nesting')

    def export_dialog(self):
        solutions=self.ready_solutions()
        if not self.can_start() or not solutions: return
        name=self.source.code+'_SEGMENTLER' if len(solutions)==1 else 'BOLUNMUS_PARCALAR'
        path,_=QFileDialog.getSaveFileName(self,'Yeni DXF çıktı klasörü adı',name,'Tüm dosyalar (*)')
        if path: self.export_to(path)

    def export_to(self,path):
        """One part: its own folder. Several: one sub-folder per part inside a new folder."""
        solutions=deepcopy(self.ready_solutions())
        if not self.can_start() or not solutions: return
        def operation(sink,stop):
            import re
            from .dxf_export import export_segments
            if len(solutions)==1:
                export_segments(solutions[0],path,stop=stop)
            else:
                root=Path(path)
                if root.exists(): raise FileExistsError('DXF için henüz bulunmayan yeni bir klasör seçin.')
                used=set()
                for n,solution in enumerate(solutions):
                    sink.put(('split_progress',(n,len(solutions),f'DXF yazılıyor: {solution.source.code}')))
                    stem=re.sub(r'[^\w.\-]+','_',solution.source.code,flags=re.UNICODE).strip('.')[:80] or 'PARCA'
                    folder=stem; k=2
                    while folder.lower() in used: folder=f'{stem}_{k}'; k+=1
                    used.add(folder.lower()); export_segments(solution,root/folder,stop=stop)
            sink.put(('split_exported',str(Path(path))))
        self.jobs.start(self,operation); self.set_status('DXF dosyaları yazılıyor ve doğrulanıyor…')

    def handle_events(self,events):
        for kind,value in events:
            if kind=='split_sources':
                parts,metas,errors,replace=value if isinstance(value,tuple) else (value,None,[],True)
                if parts: self.set_sources(parts,metas,replace=replace)
                message=f'{len(parts)} parça eklendi; toplam {len(self.sources)}.'+(' Hepsini aynı ayarlarla bölmek için “Tümünü Böl”.' if len(self.sources)>1 else '')
                if errors: message+=f' Okunamayan {len(errors)} dosya: '+'; '.join(errors)
                self.set_status(message,bool(errors) and not parts)
            elif kind=='split_batch':
                done,failed=value; self.solutions,self.part_errors=dict(done),dict(failed)
                index=self.current if self.current in done else (min(done) if done else self.current)
                self.select_source(index)
                self.set_status(f'{len(done)} parça bölündü'+(f', {len(failed)} parça bölünemedi (listede gerekçesiyle).' if failed else '; hepsi doğrulandı.'),
                                bool(failed) and not done)
            elif kind=='split_solution': self.show_solution(value)
            elif kind=='split_optimized':
                self.optimization=value; self.show_solution(value.solution)
                best=next((i for i,r in enumerate(value.candidates) if r.label==value.best_label),None)
                self.fill(self.candidate_table,[(r.label+(' ★ en iyi' if r.label==value.best_label else ''),r.status,
                    r.sheets if r.sheets is not None else '—',
                    f'{r.gross_area/1e6:.4f}' if r.gross_area is not None else '—',
                    f'{r.waste_percent:.2f}' if r.waste_percent is not None else '—',
                    f'{r.seam_length:.1f}' if r.seam_length is not None else '—',f'{r.elapsed:.2f}') for r in value.candidates],highlight=best)
                from .optimizer import metrics
                sheets,gross,waste,_=metrics(value.project,value.nesting)
                self.tiles['sheets'].set(str(sheets),f'brüt {gross/1e6:.2f} m²'.replace('.',','))
                self.tiles['waste'].set(f'%{waste:.1f}'.replace('.',','),'en iyi aday'); self.tiles['waste'].setToolTip(value.best_label)
                self.summary.setText(f'Bulunan en iyi çözüm: {value.best_label} · {len(value.candidates)} aday {value.elapsed:.1f} s içinde denendi. '
                                     'Global en iyi iddiası yoktur.')
                self.tabs.setCurrentWidget(self.candidate_table)
                self.set_status('Arama durduruldu; doğrulanmış bulunan en iyi çözüm korundu.' if value.stopped else 'Aday karşılaştırması tamamlandı; bulunan en iyi çözüm gösteriliyor.')
            elif kind=='split_progress': self.progressChanged.emit(value[0],value[1]); self.set_status(value[2])
            elif kind=='split_exported': self.set_status('Ayrı ve birleşik DXF dosyaları doğrulanarak dışa aktarıldı: '+value)
            elif kind=='job_error': self.set_status(value['error'],True)

    def clear(self):
        if not self.can_start(): return
        self.sources=[]; self.meta=[]; self.source=None; self.current=-1; self.invalidate()
        self.info.setText('Henüz parça yok. Bir DXF açın veya Nesting’den bir parça alın.'); self.set_status('Bölme ekranı sıfırlandı.')
