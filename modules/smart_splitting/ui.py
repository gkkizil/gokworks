"""Native workbench; all source parsing, splitting, nesting and export run as jobs."""
from copy import deepcopy
import math
from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QCheckBox)
from shapely.geometry import box, mapping

from gui_qt.components import BasePage, ValueForm, button, configure_view, fit_columns, label, scroll
from modules.nesting.materials import new_project
from modules.nesting.models import integer, number
from .analysis import analyze, load_parts, validate_source
from .canvas import SplitCanvas
from .models import SplitSettings


class SmartSplittingPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Akıllı Parça Bölme','Konturu koruyarak bölün, adayları aynı Nesting ayarlarıyla karşılaştırın.')
        self.sources=[]; self.source=None; self.solution=None; self.optimization=None
        self.import_path=None; self.import_options=None; self.import_stale=False
        self.action('DXF seç',self.import_dialog)
        self.reload_button=self.action('Yeniden Oku',self.reload_source)
        self.stop_button=self.action('Durdur',self.jobs.cancel,locked=False)
        self.action('Sıfırla',self.clear)
        self.form=ValueForm(self.settings,'smart_splitting/')
        f=self.form
        f.text('count','Segment sayısı',6); f.text('quantity','Orijinal parça adedi',1)
        f.combo('mode','Bölme yöntemi',('Eşit açısal','Kontur duyarlı','Fire optimizasyonu'))
        f.text('start_angle','Başlangıç açısı · °',0)
        f.combo('center_mode','Bölme merkezi',('Sınır kutusu merkezi','Alan ağırlık merkezi','Özel merkez'))
        f.text('center_x','Özel merkez X · mm',0); f.text('center_y','Özel merkez Y · mm',0)
        f.text('sheet_width','Levha eni · mm',1500); f.text('sheet_height','Levha boyu · mm',3000)
        f.text('thickness','Sac kalınlığı · mm',2)
        materials=[m.id for m in new_project().materials]; f.combo('material','Malzeme',materials)
        f.text('margin','Levha kenar payı · mm',10); f.text('gap','Parça aralığı · mm',3)
        f.text('kerf','Kesim kerf · mm',.2); f.check('rotation','Rotasyona izin ver',True)
        f.text('angles','İzin verilen açılar · ; ile','0;90;180;270')
        f.combo('profile','Arama profili',('Hızlı','Dengeli','Detaylı'))
        f.text('min_width','Minimum segment genişliği · mm',1)
        f.text('min_web','Minimum et ön kontrolü · mm',0)
        f.text('hole_clearance','Kritik delik/slot yaklaşması · mm',0)
        f.combo('joining','Birleştirme yöntemi',('Kaynak','Cıvata','Diğer'))
        f.text('weld_gap','Kaynak boşluğu · mm',0); f.text('allowance','Birleştirme kenarı işleme payı · mm',0)
        f.text('forbidden','Yasaklı kutular · x,y,en,boy;…','')
        f.combo('unit','DXF birimi tanımsızsa',('Seçilmedi','mm','cm','inch'))
        f.text('tolerance','DXF eğri sapması · mm',.05)
        f.fields['tolerance'].setToolTip('Okunmuş DXF’de değişiklikten sonra Yeniden Oku gerekir. Nesting’den alınan geometri mevcut hassasiyetini korur.')
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        ll.addWidget(button('Nesting’den seçili parçayı al',self.from_nesting))
        self.source_picker=QComboBox(); self.source_picker.setAccessibleName('Kaynak DXF parçası')
        self.source_picker.currentIndexChanged.connect(self.select_source); ll.addWidget(self.source_picker)
        self.info=label('DXF seçin veya Nesting’den bir parça alın.','muted'); ll.addWidget(self.info)
        ll.addWidget(f)
        ll.addWidget(label('Koordinatlar, içe alınan parçanın sol altına göre mm’dir. Yasaklı kutularda ondalık nokta kullanın.','muted'))
        left_scroll=scroll(left); left_scroll.setMinimumWidth(260)
        self.canvas=SplitCanvas()
        self.original=QCheckBox('Orijinal konturu göster'); self.original.toggled.connect(self.redraw)
        toolbar=QHBoxLayout(); toolbar.addWidget(self.original); toolbar.addStretch(); toolbar.addWidget(button('Sığdır',self.canvas.fit))
        self.summary=label('Henüz bölme sonucu yok.','section')
        self.warning=label('Geometrik ön kontroldür; dayanım veya kaynak onayı değildir.','muted')
        self.segments_table=self.make_table(('Segment','Adet','Net alan · mm²','İmalat alanı · mm²','En × boy · mm','Genişlik · mm','Birleşim · mm','Komşular'))
        self.candidate_table=self.make_table(('Aday','Durum','Levha','Brüt alan · m²','Fire · %','Birleşim · mm','Süre · s'))
        tabs=QTabWidget(); tabs.addTab(self.segments_table,'Segmentler'); tabs.addTab(self.candidate_table,'Aday karşılaştırması')
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(0,0,0,0)
        rl.addLayout(toolbar); rl.addWidget(self.canvas,3); rl.addWidget(self.summary); rl.addWidget(tabs,2); rl.addWidget(self.warning)
        self.workspace=QSplitter(); self.workspace.addWidget(left_scroll); self.workspace.addWidget(right)
        self.workspace.setChildrenCollapsible(False); self.workspace.setSizes([340,760]); self.layout.addWidget(self.workspace,1)
        actions=QHBoxLayout()
        self.split_button=button('Parçayı Böl',self.run_split,primary=True)
        self.optimize_button=button('Fireyi Optimize Et',lambda:self.run_split(optimize=True))
        self.transfer_button=button('Nesting’e Aktar',self.transfer)
        self.export_button=button('DXF Dışa Aktar',self.export_dialog)
        for widget in (self.split_button,self.optimize_button,self.transfer_button,self.export_button): actions.addWidget(widget); self.controls.append(widget)
        self.layout.addLayout(actions); self.controls.extend((left,self.original))
        self.form.changed.connect(self.invalidate); self.update_actions()
        self.set_status('DXF seçin → Bölme ayarlarını girin → Parçayı Böl veya Fireyi Optimize Et.')

    def make_table(self,headers):
        table=configure_view(QTableWidget(0,len(headers))); table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers); table.setSortingEnabled(False)
        fit_columns(table,elastic=0,minimum=120); table.setMinimumHeight(90)
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
        forbidden=[]
        for row in f.value('forbidden').split(';'):
            if not row.strip(): continue
            try: x,y,w,h=map(float,row.split(','))
            except (ValueError,TypeError): raise ValueError('Yasaklı bölge: x,y,en,boy biçimini kullanın.') from None
            if not all(math.isfinite(v) for v in (x,y,w,h)) or min(w,h)<=0: raise ValueError('Yasaklı bölge ölçüleri pozitif olmalı.')
            forbidden.append(mapping(box(x,y,x+w,y+h)))
        custom=f.value('center_mode')=='Özel merkez'
        value=SplitSettings(**numeric,count=integer(f.value('count'),'Segment sayısı',minimum=2,maximum=64),
            quantity=integer(f.value('quantity'),'Parça adedi'),start_angle=signed('start_angle'),
            center=(signed('center_x'),signed('center_y')) if custom else None,
            center_mode='centroid' if f.value('center_mode')=='Alan ağırlık merkezi' else 'bounds',
            angles=tuple(float(a.strip().replace(',','.')) for a in f.value('angles').split(';') if a.strip()),
            rotation=f.value('rotation'),profile=f.value('profile'),material=f.value('material'),joining=f.value('joining'),forbidden=tuple(forbidden))
        value.validate()
        if value.material not in {m.id for m in new_project().materials}:
            raise ValueError('Özel kaynak malzemesi bu ekranın kataloğunda yok; kullanacağınız katalog malzemesini açıkça seçin.')
        return value

    def invalidate(self,*args):
        self.solution=None; self.optimization=None
        self.segments_table.setRowCount(0); self.candidate_table.setRowCount(0)
        self.summary.setText('Ayarlar değişti; yeniden bölün veya optimize edin.')
        custom=self.form.value('center_mode')=='Özel merkez'
        for key in ('center_x','center_y'): self.form.fields[key].setEnabled(custom)
        self.import_stale=False
        if self.import_path is not None:
            try:
                current=(self.form.value('unit'),float(str(self.form.value('tolerance')).replace(',','.')))
                self.import_stale=current!=self.import_options
            except (ValueError,TypeError): self.import_stale=True
            if self.import_stale:
                self.set_status('DXF birimi / eğri toleransı değişti. Yeni geometri için Yeniden Oku düğmesini kullanın.',True)
        self.update_actions(); self.redraw()

    def update_actions(self):
        ready=not self.busy and self.source is not None and not self.import_stale
        self.split_button.setEnabled(ready)
        self.optimize_button.setEnabled(ready)
        self.reload_button.setEnabled(not self.busy and self.import_path is not None)
        self.transfer_button.setEnabled(not self.busy and self.solution is not None)
        self.export_button.setEnabled(not self.busy and self.solution is not None)

    def set_busy(self,busy):
        super().set_busy(busy); self.update_actions()

    def import_dialog(self):
        if not self.can_start(): return
        path,_=QFileDialog.getOpenFileName(self,'Bölünecek DXF seç','','DXF (*.dxf)')
        if path: self.load_file(path)

    def load_file(self,path):
        if not self.can_start(): return
        try:
            unit=self.form.value('unit'); tolerance=number(self.form.value('tolerance'),'Eğri toleransı',positive=True)
            if tolerance>1: raise ValueError('Eğri toleransı en fazla 1 mm olabilir.')
        except ValueError as error: return self.set_status(error,True)
        def operation(sink,stop):
            parts=load_parts(path,unit=None if unit=='Seçilmedi' else unit,tolerance=tolerance,stop=stop)
            sink.put(('split_sources',(parts,str(path),(unit,tolerance))))
        self.jobs.start(self,operation); self.set_status('DXF konturları okunuyor…')

    def reload_source(self):
        if self.import_path is not None: self.load_file(self.import_path)

    def set_sources(self,parts,*,import_path=None,import_options=None):
        selected=self.source.code if self.source is not None and import_path is not None and import_path==self.import_path else None
        self.import_path=import_path; self.import_options=import_options
        self.sources=deepcopy(parts); self.source_picker.blockSignals(True); self.source_picker.clear()
        for key in ('unit','tolerance'): self.form.fields[key].setEnabled(import_path is not None)
        self.source_picker.addItems([p.code for p in self.sources]); self.source_picker.blockSignals(False)
        index=next((i for i,p in enumerate(self.sources) if p.code==selected),0)
        self.source_picker.setCurrentIndex(index); self.select_source(index)

    def select_source(self,index):
        self.source=self.sources[index] if 0<=index<len(self.sources) else None
        self.invalidate()
        if self.source is not None:
            a=analyze(self.source); b=a['bounds']
            self.info.setText(f"{self.source.code} · {a['kind']}\n{b[2]-b[0]:.2f} × {b[3]-b[1]:.2f} mm · {a['holes']} iç kontur\nNet alan {a['area']:.2f} mm²")

    def from_nesting(self):
        if not self.can_start(): return
        page=self.context.pages['nesting']; ids=page.selected_part_ids()
        if len(ids)!=1: return self.set_status('Nesting’de tek parça seçin; sonra bu düğmeyi kullanın.',True)
        part=deepcopy(page.project.part(next(iter(ids))))
        try: validate_source(part)
        except ValueError as error: return self.set_status(error,True)
        self.set_sources([part]); self.form.set_value('quantity',part.quantity); self.form.set_value('thickness',part.thickness)
        material=self.form.fields['material']
        if material.findText(part.material)<0: material.addItem(part.material)
        self.form.set_value('material',part.material)
        if part.material not in {m.id for m in new_project().materials}:
            self.set_status('Kaynak özel malzeme: '+part.material+'. Bölmeden önce kullanacağınız katalog malzemesini açıkça seçin.',True)
        else: self.set_status('Seçili Nesting parçası kopyalandı; mevcut Nesting listesi korundu.')

    def run_split(self,*,optimize=False):
        if not self.can_start() or self.source is None: return
        if self.import_stale:
            return self.set_status('DXF birimi / eğri toleransı değişti; önce Yeniden Oku ile geometriyi güncelleyin.',True)
        try: settings=self.settings_value()
        except (ValueError,TypeError) as error: return self.set_status(error,True)
        source=deepcopy(self.source); optimize=optimize or self.form.value('mode')=='Fire optimizasyonu'
        mode='smart' if self.form.value('mode')=='Kontur duyarlı' else 'equal'
        self.invalidate()
        def operation(sink,stop):
            if optimize:
                from .optimizer import optimize as search
                result=search(source,settings,stop=stop,progress=lambda i,n,text:sink.put(('split_progress',(i,n,text))))
                sink.put(('split_optimized',result))
            else:
                from .splitter import split
                sink.put(('split_solution',split(source,settings,mode=mode,stop=stop)))
        self.jobs.start(self,operation); self.set_status('Geometri ve bölme adayları hesaplanıyor…')

    def show_solution(self,solution):
        self.solution=solution
        rows=[]
        for s in solution.segments:
            x0,y0,x1,y1=s.blank.bounds
            rows.append((f'{s.original_name}_SEG_{s.number:03d}',solution.settings.quantity,f'{s.nominal.area:.2f}',f'{s.blank.area:.2f}',
                         f'{x1-x0:.2f} × {y1-y0:.2f}',f'{s.minimum_width:.2f}',f'{s.seam_length:.2f}',', '.join(map(str,s.neighbors))))
        self.fill(self.segments_table,rows)
        total=sum(s.blank.area for s in solution.segments)*solution.settings.quantity
        self.summary.setText(f'{len(rows)} segment × {solution.settings.quantity} adet · Net imalat {total/1e6:.3f} m² · Birleşim/orijinal {solution.seam_length:.2f} mm · Alan farkı {solution.area_delta:.6g} mm²')
        self.warning.setText(' '.join(solution.warnings)); self.warning.setToolTip(self.warning.text())
        self.redraw(); self.update_actions(); self.set_status('Segmentler oluşturuldu; nominal alan ve kontur doğrulandı.')

    def fill(self,table,rows):
        table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row): table.setItem(i,j,QTableWidgetItem(str(value)))

    def redraw(self,*args):
        self.canvas.show_geometry(self.source,self.solution,self.original.isChecked())

    def theme_changed(self):
        if hasattr(self,'canvas'): self.canvas.theme=self.context.appearance; self.redraw()

    def transfer(self):
        if not self.can_start() or self.solution is None: return
        try:
            from .adapter import transfer_to_nesting
            transfer_to_nesting(self.context.pages['nesting'],self.solution)
        except ValueError as error: return self.set_status(error,True)
        self.context.navigate('nesting')

    def export_dialog(self):
        if not self.can_start() or self.solution is None: return
        path,_=QFileDialog.getSaveFileName(self,'Yeni DXF çıktı klasörü adı',self.source.code+'_SEGMENTLER','Tüm dosyalar (*)')
        if path: self.export_to(path)

    def export_to(self,path):
        if not self.can_start() or self.solution is None: return
        solution=deepcopy(self.solution)
        def operation(sink,stop):
            from .dxf_export import export_segments
            export_segments(solution,path,stop=stop); sink.put(('split_exported',str(Path(path))))
        self.jobs.start(self,operation)

    def handle_events(self,events):
        for kind,value in events:
            if kind=='split_sources':
                parts,path,options=value
                self.set_sources(parts,import_path=path,import_options=options)
                self.set_status(f'{len(parts)} kaynak parça okundu.')
            elif kind=='split_solution': self.show_solution(value)
            elif kind=='split_optimized':
                self.optimization=value; self.show_solution(value.solution)
                self.fill(self.candidate_table,[(r.label,r.status,r.sheets if r.sheets is not None else '—',
                    f'{r.gross_area/1e6:.4f}' if r.gross_area is not None else '—',
                    f'{r.waste_percent:.3f}' if r.waste_percent is not None else '—',
                    f'{r.seam_length:.2f}' if r.seam_length is not None else '—',f'{r.elapsed:.2f}') for r in value.candidates])
                from .optimizer import metrics
                sheets,gross,waste,_=metrics(value.project,value.nesting)
                self.summary.setText(self.summary.text()+f'\nBulunan en iyi çözüm: {value.best_label} · {sheets} levha · {gross/1e6:.3f} m² · %{waste:.2f} fire · {value.elapsed:.2f} s')
                self.set_status('Arama durduruldu; doğrulanmış bulunan en iyi çözüm korundu.' if value.stopped else 'Aday karşılaştırması tamamlandı; bulunan en iyi çözüm gösteriliyor.')
            elif kind=='split_progress': self.progressChanged.emit(value[0],value[1]); self.set_status(value[2])
            elif kind=='split_exported': self.set_status('Ayrı ve birleşik DXF dosyaları doğrulanarak dışa aktarıldı: '+value)
            elif kind=='job_error': self.set_status(value['error'],True)

    def clear(self):
        if not self.can_start(): return
        self.sources=[]; self.source=None; self.source_picker.clear(); self.invalidate()
        self.import_path=None; self.import_options=None; self.import_stale=False
        for key in ('unit','tolerance'): self.form.fields[key].setEnabled(True)
        self.update_actions()
        self.info.setText('DXF seçin veya Nesting’den bir parça alın.'); self.set_status('Bölme ekranı sıfırlandı.')
