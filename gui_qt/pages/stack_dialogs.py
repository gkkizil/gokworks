"""Native Qt editors for local analysis data, never CAD parameter editing."""

from dataclasses import replace
from PySide6.QtWidgets import QDialog,QVBoxLayout,QDialogButtonBox,QMessageBox
from ..components import ValueForm,label
from tolerance_stack.models import manual_dimension,iso_dimension,Term,UNITS,length,number

KINDS={'Doğrusal':'linear','Yatay (görünüm)':'horizontal','Düşey (görünüm)':'vertical','Ordinat':'ordinate','Çap':'diameter','Radyüs':'radius'}
DIST={'Analiz ayarını kullan':'inherit','Normal':'normal','Uniform':'uniform','Üçgensel':'triangular'}


class MemorySettings:
    def __init__(self,values=None): self.values=values or {}
    def get(self,key,default=None): return self.values.get(key,default)
    def set(self,key,value): self.values[key]=value


class Editor(QDialog):
    def __init__(self,parent,title):
        super().__init__(parent);self.setWindowTitle(title);self.setMinimumWidth(440)
        self.body=QVBoxLayout(self);self.form=ValueForm(MemorySettings(),'')
        self.body.addWidget(self.form)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.submit);self.buttons.rejected.connect(self.reject)
        self.body.addWidget(self.buttons)
        self.value=None

    def submit(self):
        try: self.value=self.read_value()
        except ValueError as error: QMessageBox.warning(self,'Değerleri kontrol edin',str(error));return
        self.accept()


class DimensionDialog(Editor):
    def __init__(self,parent,dimension=None):
        super().__init__(parent,'Analiz ölçüsü · CAD ölçüsü değiştirilmez')
        self.original=dimension;f=self.form
        f.text('name','Ölçü adı',dimension.name if dimension else '')
        f.combo('kind','Tür',KINDS,next((title for title,key in KINDS.items() if dimension and key==dimension.kind),'Doğrusal'))
        f.combo('unit','Giriş birimi',UNITS,'mm')
        f.combo('mode','Tolerans girişi',('Alt / üst sapma','Simetrik ±','Alt / üst ölçü limiti'))
        f.text('nominal','Nominal',dimension.nominal if dimension and dimension.nominal is not None else '')
        f.text('lower','Alt sapma / alt ölçü',dimension.lower if dimension and dimension.lower is not None else '')
        f.text('upper','Üst sapma / üst ölçü / ±',dimension.upper if dimension and dimension.upper is not None else '')
        f.text('note','Açıklama / genel tolerans kaynağı',dimension.note if dimension else '')
        self.body.insertWidget(0,label('Bilinmeyen toleranslara varsayılan değer atanmaz. '
            'Burada yapılan değişiklik yalnız analize uygulanır; üretim ölçüsünü değiştirmez.','muted'))

    def read_value(self):
        f=self.form;nominal=length(f.value('nominal'),f.value('unit'))
        upper=length(f.value('upper'),f.value('unit'))
        if f.value('mode')=='Simetrik ±':
            if upper<0: raise ValueError('Simetrik ± değeri negatif olamaz.')
            lower=-upper
        else:
            lower=length(f.value('lower'),f.value('unit'))
            if f.value('mode')=='Alt / üst ölçü limiti': lower-=nominal;upper-=nominal
        if not f.value('name').strip() or lower>upper: raise ValueError('Ad boş veya alt sapma üst sapmadan büyük.')
        dimension=manual_dimension(f.value('name'),nominal,lower,upper,kind=KINDS[f.value('kind')],note=f.value('note'))
        if self.original:
            if self.original.kind in ('angle','gdt','basic','reference','arc','chamfer'):
                raise ValueError('Bu ölçü türü için doğrulanmış 1D model yok; türü değiştirerek zincire alınamaz.')
            dimension=replace(self.original,name=dimension.name,nominal=nominal,lower=lower,upper=upper,
                kind=dimension.kind,note=f.value('note'),display_unit='mm',provenance='manual_override' if self.original.source else 'manual')
        return dimension


class TermDialog(Editor):
    def __init__(self,parent,term,dimension):
        super().__init__(parent,'Zincir ilişkisi · '+dimension.name);self.original=term;f=self.form
        f.combo('direction','Yön',('+','−'),'+' if term.direction>0 else '−')
        for key,title in (('start','Başlangıç noktası'),('end','Bitiş noktası'),('datum','Ortak fonksiyonel datum')):
            f.text(key,title,getattr(term,key))
        f.combo('axis','Eksen',('X','Y','Z'),term.axis)
        f.text('factor','Doğrusal ilişki katsayısı',term.factor)
        f.text('relation','Fonksiyonel ilişki / projeksiyon açıklaması',term.relation)
        f.combo('distribution','Dağılım',DIST,next(title for title,key in DIST.items() if key==term.distribution))
        for key,title in (('mean','Normal merkez · mm (boş = bant ortası)'),('sigma','Normal σ · mm (boş = banttan)'),('mode','Üçgensel tepe · mm (boş = bant ortası)')):
            f.text(key,title,'' if getattr(term,key) is None else getattr(term,key))
        self.body.insertWidget(0,label('Çap/radyüs için ilişki zorunludur. Örnek: çapsal boşluk D−d için 1; '
            'radyal boşluk (D−d)/2 için 0,5. Açılar ve GD&T bu şekilde dönüştürülemez.','muted'))

    def read_value(self):
        f=self.form
        return replace(self.original,direction=1 if f.value('direction')=='+' else -1,start=f.value('start'),end=f.value('end'),
            axis=f.value('axis'),datum=f.value('datum'),factor=number(f.value('factor')),relation=f.value('relation'),
            distribution=DIST[f.value('distribution')],**{key:number(f.value(key)) if f.value(key).strip() else None for key in ('mean','sigma','mode')})


class IsoPairDialog(Editor):
    def __init__(self,parent):
        super().__init__(parent,'ISO 286 geçmesini zincire aktar')
        from iso_fits.rules import classes
        f=self.form;f.text('diameter','Ortak nominal çap · mm','50')
        f.combo('hole','Delik sınıfı',classes('hole'),'H7');f.combo('shaft','Mil sınıfı',classes('shaft'),'h6')
        f.combo('relation','Fonksiyonel ilişki',('Çapsal boşluk D−d','Radyal boşluk (D−d)/2'))
        self.body.insertWidget(0,label('GOKWORKS’ün doğrulanmış ISO 286 limitleri kullanılır. '
            'Delik (+) ve mil (−) iki ayrı terim olarak eklenir; zinciri ayrıca doğrulamanız gerekir.','muted'))

    def read_value(self):
        f=self.form;n=f.value('diameter')
        return (iso_dimension('Delik '+f.value('hole'),n,f.value('hole'),'hole'),
                iso_dimension('Mil '+f.value('shaft'),n,f.value('shaft'),'shaft'),
                number('.5' if f.value('relation').startswith('Radyal') else '1'),f.value('relation'))
