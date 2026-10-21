"""Native Qt editors for local analysis data, never CAD parameter editing."""

from dataclasses import replace
from PySide6.QtWidgets import QDialog,QVBoxLayout,QDialogButtonBox,QMessageBox,QWidget,QApplication
from gui_qt.components import ValueForm,label,scroll
from modules.tolerance_stack.ui_widgets import Disclosure,short_name,compact
from modules.tolerance_stack.models import manual_dimension,iso_dimension,Term,UNITS,length,number

KINDS={'Doğrusal':'linear','Yatay (görünüm)':'horizontal','Düşey (görünüm)':'vertical','Ordinat':'ordinate','Çap':'diameter','Radyüs':'radius'}
KIND_TITLES={**{key:title for title,key in KINDS.items()},'reference':'Referans ölçü','basic':'Temel (BASIC)',
             'angle':'Açısal','arc':'Yay uzunluğu','chamfer':'Pah','gdt':'GD&T','unknown':'Türü bilinmiyor'}
DIST={'Analiz ayarını kullan':'inherit','Normal':'normal','Uniform':'uniform','Üçgensel':'triangular'}


class MemorySettings:
    def __init__(self,values=None): self.values=values or {}
    def get(self,key,default=None): return self.values.get(key,default)
    def set(self,key,value): self.values[key]=value


class Editor(QDialog):
    def __init__(self,parent,title):
        super().__init__(parent);self.setWindowTitle(title);self.setMinimumWidth(440)
        self.body=QVBoxLayout(self);self.content=QWidget();self.content_body=QVBoxLayout(self.content)
        self.content_body.setContentsMargins(4,4,4,4)
        self.form=ValueForm(MemorySettings(),'');self.content_body.addWidget(self.form)
        self.body.addWidget(scroll(self.content),1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText('Uygula')
        self.buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        self.buttons.accepted.connect(self.submit);self.buttons.rejected.connect(self.reject)
        self.body.addWidget(self.buttons)
        self.value=None
        screen=QApplication.primaryScreen()
        self.resize(570,min(640,screen.availableGeometry().height()-90) if screen else 640)

    def submit(self):
        try: self.value=self.read_value()
        except ValueError as error: QMessageBox.warning(self,'Değerleri kontrol edin',str(error));return
        self.accept()


class DimensionDialog(Editor):
    def __init__(self,parent,dimension=None):
        super().__init__(parent,'Ölçüyü analize hazırla')
        self.original=dimension;f=self.form
        f.text('name','Ölçü adı',dimension.name if dimension else '')
        native_kind=(dimension.geometry_kind if dimension.kind=='reference' else dimension.kind) if dimension else ''
        f.combo('kind','Tür',KINDS,next((title for title,key in KINDS.items() if key==native_kind),'Doğrusal'))
        f.combo('unit','Giriş birimi',UNITS,'mm')
        f.combo('mode','Tolerans girişi',('Alt / üst sapma','Simetrik ±','Alt / üst ölçü limiti'))
        f.text('nominal','Ölçü değeri',dimension.nominal if dimension and dimension.nominal is not None else '')
        f.text('lower','Alt sapma / alt ölçü',dimension.lower if dimension and dimension.lower is not None else '')
        f.text('upper','Üst sapma / üst ölçü / ±',dimension.upper if dimension and dimension.upper is not None else '')
        notes=ValueForm(MemorySettings(),'')
        notes.text('note','Açıklama / toleransın kaynağı',dimension.note if dimension else '')
        f.fields.update(notes.fields)
        self.content_body.addWidget(Disclosure('Açıklama ve kaynak notları',notes))
        if dimension and dimension.kind=='reference':
            f.fields['kind'].setEnabled(False)
            f.check('reference_confirmed','Ölçü değerini ve toleransını kontrol ettim.',False)
            self.content_body.insertWidget(0,label('Bu bir referans ölçü. Çizimde veya üretim şartlarında belirtilen '
                'değerini ve toleransını kontrol edin; sonra aşağıdaki kutuyu işaretleyin.','muted'))
        self.content_body.insertWidget(0,label('Gerçek ölçü ve tolerans değerlerini girin. Bilinmeyen toleranslar tahmin edilmez. '
            'Buradaki değişiklikler yalnız analize aittir; SolidWorks ölçüsü değiştirilmez.','muted'))
        f.fields['mode'].currentTextChanged.connect(self.mode_changed);self.mode_changed(f.value('mode'))
        f.fields['upper'].setPlaceholderText('Örnek: 0,1')
        f.fields['lower'].setPlaceholderText('Örnek: -0,1')
        self.content_body.addStretch()

    def mode_changed(self,mode):
        f=self.form;f.show_field('lower',mode!='Simetrik ±')
        for key,title in (('nominal','Ölçü değeri'),('lower','En küçük gerçek ölçü' if mode=='Alt / üst ölçü limiti' else 'Alt sapma (ör. −0,1)'),
                          ('upper','± Tolerans' if mode=='Simetrik ±' else 'En büyük gerçek ölçü' if mode=='Alt / üst ölçü limiti' else 'Üst sapma (ör. +0,1)')):
            f.form.labelForField(f.fields[key]).setText(title)

    def read_value(self):
        f=self.form;nominal=length(f.value('nominal'),f.value('unit'))
        upper=length(f.value('upper'),f.value('unit'))
        if f.value('mode')=='Simetrik ±':
            if upper<0: raise ValueError('Simetrik ± değeri negatif olamaz.')
            lower=-upper
        else:
            lower=length(f.value('lower'),f.value('unit'))
            if f.value('mode')=='Alt / üst ölçü limiti': lower-=nominal;upper-=nominal
        if not f.value('name').strip():raise ValueError('Ölçüye bir ad verin. Örneğin: Gövde boyu.')
        if lower>upper:raise ValueError('Alt değer üst değerden büyük olamaz. Sapmaları veya ölçü limitlerini kontrol edin.')
        dimension=manual_dimension(f.value('name'),nominal,lower,upper,kind=KINDS[f.value('kind')],note=f.value('note'))
        if self.original:
            if self.original.kind=='reference':
                if self.original.geometry_kind not in KINDS.values():
                    raise ValueError('Referans ölçünün geometrik türü 1D uzunluk olarak doğrulanamadı; teknik resmi yeniden tarayın.')
                if not f.value('reference_confirmed'):
                    raise ValueError('Referans ölçünün değerini ve toleransını doğrulayın: alttaki kontrol kutusunu işaretleyin.')
                if dimension.kind!=self.original.geometry_kind:
                    raise ValueError('Referans ölçünün kaynak geometrik türü değiştirilemez.')
            elif self.original.kind in ('angle','gdt','basic','arc','chamfer'):
                raise ValueError('Bu ölçü türü için doğrulanmış 1D model yok; türü değiştirerek zincire alınamaz.')
            dimension=replace(self.original,name=dimension.name,nominal=nominal,lower=lower,upper=upper,
                kind=dimension.kind,note=f.value('note'),display_unit='mm',provenance='manual_override' if self.original.source else 'manual')
            if self.original.kind=='reference':
                dimension=replace(dimension,tolerance_type='Manuel · '+f.value('mode'),
                    note=dimension.note+'\nReferans ölçünün nominali ve toleransları kullanıcı tarafından analiz için doğrulandı.')
        return dimension


class TermDialog(Editor):
    def __init__(self,parent,term,dimension):
        super().__init__(parent,'Ölçü ayarları · '+short_name(dimension));self.original=term;self.dimension=dimension;f=self.form
        self.content_body.insertWidget(0,label(f'{short_name(dimension)} · {compact(dimension.nominal)} mm','section'))
        self.content_body.insertWidget(1,label('+ ölçüyü sonuca ekler, − sonuçtan çıkarır. Sıradan bir uzunluk için katsayı 1 olarak kalır.','muted'))
        f.combo('direction','İşlem (+ toplar / − çıkarır)',('+','−'),'+' if term.direction>0 else '−')
        self.use_options={'Doğrudan kullan (×1)':(number(1),''),'Özel katsayı / dönüşüm':(None,None)}
        if dimension.kind=='diameter':
            self.use_options={'Kullanımı seçin…':(None,None),'Çapı doğrudan kullan (×1)':(number(1),'Çap mesafesi doğrudan kullanılıyor.'),
                'Çaptan yarıçap mesafesi (×0,5)':(number('.5'),'Çapın yarısı, yarıçap mesafesi olarak kullanılıyor.'),'Özel katsayı / dönüşüm':(None,None)}
        elif dimension.kind=='radius':
            self.use_options={'Kullanımı seçin…':(None,None),'Radyüsü doğrudan kullan (×1)':(number(1),'Radyüs mesafesi doğrudan kullanılıyor.'),
                'Radyüsten çap mesafesi (×2)':(number(2),'Radyüsün iki katı, çap mesafesi olarak kullanılıyor.'),'Özel katsayı / dönüşüm':(None,None)}
        selected=('Özel katsayı / dönüşüm' if term.factor!=1 or dimension.kind in ('diameter','radius') and term.relation else next(iter(self.use_options)))
        f.combo('use','Ölçü nasıl kullanılacak?',self.use_options,selected)
        f.check('alignment_confirmed','Ortak doğrultuyu ve referansı kontrol ettim.',term.alignment_confirmed)
        frame=ValueForm(MemorySettings(),'')
        for key,title in (('start','Başlangıç noktası'),('end','Bitiş noktası'),('datum','Ortak referans (datum)')):
            frame.text(key,title,getattr(term,key))
        frame.combo('axis','Ölçüm doğrultusu',('X','Y','Z'),term.axis)
        frame.text('factor','Ölçü katsayısı',term.factor)
        frame.text('relation','Dönüşüm açıklaması',term.relation)
        self.frame_section=Disclosure('Gelişmiş · Bağlantı ve dönüşüm',frame);self.content_body.addWidget(self.frame_section)
        project=getattr(parent,'project',None)
        if project and (term.axis!=project.axis or term.datum!=project.datum):
            self.frame_section.toggle.setChecked(True)
            self.content_body.insertWidget(2,label(f'Zincirin ortak doğrultusu / referansı: {project.axis} / {project.datum}. '
                f'Bu ölçüde {term.axis} / {term.datum} seçilmiş. Aşağıdaki doğrultu ve referans alanlarını gerçek çizime göre eşleştirin.','muted'))
        statistics=ValueForm(MemorySettings(),'')
        statistics.combo('distribution','Dağılım',DIST,next(title for title,key in DIST.items() if key==term.distribution))
        for key,title in (('mean','Normal merkez · mm (boş = bant ortası)'),('sigma','Normal σ · mm (boş = banttan)'),('mode','Üçgensel tepe · mm (boş = bant ortası)')):
            statistics.text(key,title,'' if getattr(term,key) is None else getattr(term,key))
        self.content_body.addWidget(Disclosure('Gelişmiş · Bu ölçünün istatistik ayarları',statistics))
        f.fields.update(frame.fields);f.fields.update(statistics.fields)
        def update_use(value):
            frame.show_field('factor',value=='Özel katsayı / dönüşüm')
            frame.show_field('relation',value=='Özel katsayı / dönüşüm')
            if value=='Özel katsayı / dönüşüm':self.frame_section.toggle.setChecked(True)
        f.fields['use'].currentTextChanged.connect(update_use);update_use(selected)
        frame.changed.connect(lambda key:f.set_value('alignment_confirmed',False) if key in ('axis','datum') else None)
        self.content_body.addStretch()
        self.resize(570,440)

    def read_value(self):
        f=self.form
        use=f.value('use')
        if use=='Kullanımı seçin…':raise ValueError('Çap veya radyüsün hesapta hangi mesafeyi temsil ettiğini seçin.')
        custom=use=='Özel katsayı / dönüşüm'
        factor=number(f.value('factor'),'Ölçü katsayısı') if custom else self.use_options[use][0]
        relation=f.value('relation').strip() if custom or self.dimension.kind not in ('diameter','radius') else self.use_options[use][1]
        if not custom and self.dimension.kind not in ('diameter','radius') and self.original.factor!=1:relation=''
        if not 0<factor<=1000:raise ValueError('Katsayı sıfırdan büyük, en fazla 1.000 olmalı. Normal kullanım için 1 seçin.')
        if custom and not relation:raise ValueError('Özel dönüşümün neyi temsil ettiğini Dönüşüm açıklaması alanına yazın.')
        return replace(self.original,direction=1 if f.value('direction')=='+' else -1,start=f.value('start'),end=f.value('end'),
            axis=f.value('axis'),datum=f.value('datum'),factor=factor,relation=relation,alignment_confirmed=f.value('alignment_confirmed'),
            distribution=DIST[f.value('distribution')],**{key:number(f.value(key)) if f.value(key).strip() else None for key in ('mean','sigma','mode')})


class IsoPairDialog(Editor):
    def __init__(self,parent):
        super().__init__(parent,'ISO 286 geçmesini zincire aktar')
        from modules.iso_fits.rules import classes
        f=self.form;f.text('diameter','Ortak nominal çap · mm','50')
        f.combo('hole','Delik sınıfı',classes('hole'),'H7');f.combo('shaft','Mil sınıfı',classes('shaft'),'h6')
        f.combo('relation','Fonksiyonel ilişki',('Çapsal boşluk D−d','Radyal boşluk (D−d)/2'))
        self.content_body.insertWidget(0,label('GOKWORKS’ün doğrulanmış ISO 286 limitleri kullanılır. '
            'Delik (+) ve mil (−) iki ayrı terim olarak eklenir; zinciri ayrıca doğrulamanız gerekir.','muted'))
        self.content_body.addStretch()
        self.resize(570,360)

    def read_value(self):
        f=self.form;n=f.value('diameter')
        return (iso_dimension('Delik '+f.value('hole'),n,f.value('hole'),'hole'),
                iso_dimension('Mil '+f.value('shaft'),n,f.value('shaft'),'shaft'),
                number('.5' if f.value('relation').startswith('Radyal') else '1'),f.value('relation'))
