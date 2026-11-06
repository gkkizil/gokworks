"""Optional shop inputs; calculation and profile validation stay in core.unfolding."""
import json

from PySide6.QtCore import Signal,QSignalBlocker
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QCheckBox,QComboBox,QLineEdit,QPlainTextEdit,QFileDialog,QHBoxLayout

from gui_qt.components import Disclosure,label,button
from core.unfolding.forming.mechanics import normalize_options,GRADES
from core.unfolding.models import to_data

PROCESSES=(('air_bending','Hava bükümü'),('bottoming','Kalıba oturtma'),('coining','Ezerek büküm'),
           ('roll_bending','Silindirle kıvırma'),('segmented_assembly','Segmentli imalat / birleştirme'))
METHODS=(('k_factor','Açık K-Faktör'),('material_k','Malzeme kaynaklı K'),('ba_table','BA tablosu'),
         ('bd_table','BD tablosu'),('calibrated','Ölçülen numuneden K kalibrasyonu'))


class FormingPanel(QWidget):
    changed=Signal()

    def __init__(self,parent=None):
        super().__init__(parent);self.edits={};self.boxes={};self._base={}
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        self.enabled=QCheckBox('Şekillendirme / abkant telafisini hesapla');outer.addWidget(self.enabled)
        self.body=QWidget();form=QFormLayout(self.body);form.setContentsMargins(0,0,0,0)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        def choice(key,title,values):
            box=QComboBox();box.setAccessibleName(title)
            for value,caption in values:box.addItem(caption,value)
            box.currentIndexChanged.connect(self._changed);self.boxes[key]=box;form.addRow(title,box)
        choice('process','Üretim yöntemi',PROCESSES);choice('method','Açınım telafisi',METHODS)
        self.grade=QComboBox();self.grade.setEditable(True);self.grade.addItem('')
        self.grade.addItems(GRADES);self.grade.setAccessibleName('Mekanik malzeme kalitesi')
        self.grade.currentTextChanged.connect(self._changed);form.addRow('Mekanik kalite',self.grade)
        material_host=QWidget();material_form=QFormLayout(material_host);material_form.setContentsMargins(0,0,0,0)
        tool_host=QWidget();tool_form=QFormLayout(tool_host);tool_form.setContentsMargins(0,0,0,0)
        material_form.setRowWrapPolicy(QFormLayout.WrapLongRows);tool_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        def edit(key,title):
            widget=QLineEdit();widget.setAccessibleName(title);widget.setPlaceholderText('Girilmedi')
            widget.textChanged.connect(self._changed);self.edits[key]=widget
            target=material_form if key.startswith('material.') else tool_form if key.startswith('tool.') else form
            target.addRow(title,widget)
        for key,title in (('k_factor','K-Faktör'),('material.standard','Malzeme standardı'),('material.source','Mekanik veri kaynağı'),
                          ('material.young_modulus_mpa','Elastisite E · MPa'),('material.poisson_ratio','Poisson ν'),
                          ('material.yield_strength_mpa','Akma dayanımı · MPa'),('material.tensile_strength_mpa','Çekme dayanımı · MPa'),
                          ('material.hardening_modulus_mpa','Pekleşme modülü · MPa'),('tool.id','Takım kimliği'),('tool.source','Takım verisi kaynağı'),
                          ('tool.punch_radius_mm','Üst kalıp yarıçapı · mm'),('tool.die_opening_mm','Alt kalıp V açıklığı · mm'),
                          ('tool.die_angle_deg','Alt kalıp açık açısı · °')):edit(key,title)
        form.addRow(Disclosure('Mekanik malzeme verileri',material_host))
        form.addRow(Disclosure('Takım geometrisi ve kaynağı',tool_host))
        choice('grain_direction','Hadde yönü',(('unspecified','Belirtilmedi'),('along','Büküm hattı haddeye paralel'),('across','Büküm hattı haddeye dik')))
        choice('springback','Yaylanma hesabı',(('none','Hesaplama'),('analytic','Elastik-plastik analitik tahmin'),('calibrated','Üretim ölçümleriyle kalibrasyon')))
        self.extra=QPlainTextEdit();self.extra.setAccessibleName('BA/BD ve kalibrasyon verileri JSON')
        self.extra.setMaximumHeight(160);self.extra.setPlainText('{}');self.extra.textChanged.connect(self._changed)
        extra_host=QWidget();extra_box=QVBoxLayout(extra_host);extra_box.setContentsMargins(0,0,0,0)
        extra_box.addWidget(label('Tablo, ölçüm, tolerans ve minimum takım limitleri JSON profilinden yüklenebilir. Tüm *_mm alanları daima mm’dir.','muted'))
        extra_box.addWidget(self.extra);form.addRow(Disclosure('Tablo / kalibrasyon / tolerans verileri',extra_host))
        files=QHBoxLayout();files.addWidget(button('Üretim profili aç…',self.open_profile));files.addWidget(button('Profili kaydet…',self.save_profile))
        form.addRow(files)
        form.addRow(label('Malzeme seçimi mekanik özellik atamaz. Analitik yaylanma için E, akma ve pekleşme modülü açıkça girilir; ideal plastik varsayımı için pekleşme 0’dır.','muted'))
        self.error=label('','muted');outer.addWidget(self.body);outer.addWidget(self.error)
        self.body.setEnabled(False)
        self.enabled.toggled.connect(self.body.setEnabled);self.enabled.toggled.connect(self._changed)

    def _changed(self,*args):
        self.changed.emit()

    def options(self):
        if not self.enabled.isChecked():return {}
        try:
            content=self.extra.toPlainText()
            if len(content.encode('utf-8'))>4*1024*1024:raise ValueError('Üretim verisi JSON 4 MiB sınırını aşıyor.')
            def pairs(values):
                data={}
                for key,value in values:
                    if key in data:raise ValueError('JSON tekrarlanan alan içeriyor: '+key)
                    data[key]=value
                return data
            extra=json.loads(content,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Sonlu JSON gerekli.')))
            if not isinstance(extra,dict):raise ValueError('Ek üretim verisi JSON nesnesi olmalı.')
            if set(extra)&{'version','k_factor',*self.boxes}:raise ValueError('Yöntem, K ve proses için ilgili form alanlarını kullanın.')
            for group in ('material','tool'):
                nested=extra.get(group,{})
                if not isinstance(nested,dict):raise ValueError(group+': JSON nesnesi gerekli.')
                if any(group+'.'+key in self.edits or group=='material' and key=='grade' for key in nested):
                    raise ValueError('Görünür malzeme/takım girdileri için ilgili form alanlarını kullanın.')
            o=dict(self._base);o.update(extra)
            for key,box in self.boxes.items():o[key]=box.currentData()
            m=dict(o.get('material') or {});m['grade']=self.grade.currentText().strip();o['material']=m
            o['tool']=dict(o.get('tool') or {})
            for key,edit in self.edits.items():
                content=edit.text().strip()
                value=content if key in ('material.standard','material.source','tool.id','tool.source') else float(content.replace(',','.')) if content else None
                if '.' in key:
                    group,name=key.split('.');o[group][name]=value if value is not None else '' if key.endswith(('source','standard','id')) else None
                else:o[key]=value
            result=to_data(normalize_options(o));self.error.setText('');return result
        except (ValueError,TypeError) as exc:
            self.error.setText('Üretim verisi: '+str(exc));raise ValueError(str(exc)) from exc

    def set_options(self,options):
        normalized=to_data(normalize_options(options))
        with QSignalBlocker(self):
            self._base=normalized
            self.enabled.setChecked(bool(normalized));self.body.setEnabled(bool(normalized))
            for key,box in self.boxes.items():
                box.setCurrentIndex(max(0,box.findData(normalized.get(key))))
            self.grade.setCurrentText(normalized.get('material',{}).get('grade',''))
            for key,edit in self.edits.items():
                if '.' in key:group,name=key.split('.');value=normalized.get(group,{}).get(name)
                else:value=normalized.get(key)
                edit.setText('' if value is None else str(value))
            extra={k:v for k,v in normalized.items() if k not in ('version','material','tool','k_factor',*self.boxes)}
            # Preserve optional tool/material fields not represented by direct edits.
            for group in ('material','tool'):
                hidden={k:v for k,v in normalized.get(group,{}).items() if group+'.'+k not in self.edits and not (group=='material' and k=='grade')}
                if hidden:extra[group]=hidden
            self.extra.setPlainText(json.dumps(extra,ensure_ascii=False,indent=2));self.error.setText('')

    def open_profile(self):
        path,_=QFileDialog.getOpenFileName(self,'Üretim profilini aç','','JSON (*.json)')
        if not path:return
        try:
            from core.unfolding.forming.storage import load_profile
            self.set_options(load_profile(path));self.changed.emit()
        except (ValueError,OSError) as exc:self.error.setText(str(exc))

    def save_profile(self):
        try:options=self.options()
        except ValueError:return
        path,_=QFileDialog.getSaveFileName(self,'Üretim profilini kaydet','uretim-profili.json','JSON (*.json)')
        if not path:return
        try:
            from core.unfolding.forming.storage import save_profile
            save_profile(options,path,overwrite=True);self.error.setText('Profil kaydedildi.')
        except (ValueError,OSError) as exc:self.error.setText(str(exc))
