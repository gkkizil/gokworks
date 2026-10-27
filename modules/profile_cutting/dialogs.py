"""Small native dialogs for mapping, manual demands and explicit source review."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QMessageBox, QWidget
from gui_qt.components import ValueForm, Disclosure, label, scroll
from .models import Demand, ScanRow, quantity, number
from .properties import DEFAULT_MAPPING, validate_mapping, section_thickness


class MappingDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.setWindowTitle('SolidWorks alan adları')
        self.resize(530, 600)
        body = QVBoxLayout(self)
        body.addWidget(label('Kesim boyu, malzeme ve diğer bilgilerin SolidWorks’teki alan adları. Birden çok adı noktalı virgülle ayırın.', 'muted'))
        self.form = ValueForm(page.settings, 'profile_mapping_editor_')
        titles = dict(profile='Profil / kesit',length='Kesim boyu',material='Malzeme',count='Adet',
            angle1='Uç açısı 1',angle2='Uç açısı 2',total_length='Toplam boy',thickness='Et kalınlığı',
            standard='Profil standardı',stock_code='Stok kodu')
        for key, names in page.mapping.items():
            self.form.text(key, titles[key], '; '.join(names))
            self.form.set_value(key, '; '.join(names))
        body.addWidget(scroll(self.form), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.defaults)
        body.addWidget(buttons)
        self.mapping = None

    def defaults(self):
        for key, names in DEFAULT_MAPPING.items(): self.form.set_value(key, '; '.join(names))

    def check(self):
        try:
            self.mapping = validate_mapping({key: [v.strip() for v in self.form.value(key).split(';') if v.strip()]
                                             for key in DEFAULT_MAPPING})
            self.accept()
        except ValueError as error: QMessageBox.warning(self, 'Eşleştirme', str(error))


class RowDialog(QDialog):
    def __init__(self, page, row=None):
        super().__init__(page)
        self.original = row
        self.review_mode = isinstance(row, ScanRow)
        self.value = None
        self.setWindowTitle('SolidWorks satırını kontrol et' if self.review_mode else 'Parçayı düzenle' if row else 'Kesilecek parça ekle')
        self.resize(520, 560 if self.review_mode else 320)
        body = QVBoxLayout(self)
        content = QWidget(); fields = QVBoxLayout(content); fields.setContentsMargins(0,0,0,0)
        self.form = ValueForm(page.settings, 'profile_row_editor_')
        if self.review_mode:
            fields.addWidget(label(f'{row.source} [{row.configuration}]\nKesim grubu: {row.folder}', 'muted'))
            notes = row.issues+row.errors()
            fields.addWidget(label('\n'.join(notes[:6]) + ('\nDiğer sorunlar: Okuma ayrıntıları bölümünde.' if len(notes)>6 else '') or 'Kaynak veriler hazır.', 'muted'))
        else:
            fields.addWidget(label('Kesilecek parçanın ölçüsünü girin. Ham çubuk boyunu ana ekranda belirleyeceksiniz.', 'muted'))
        for key, title, default in (
            ('profile','Profil kesiti · mm',''), ('material','Malzeme kalitesi',''),
            ('length','Parça boyu · mm',''), ('count','Kesilecek adet','1')):
            value = str(getattr(row, key)) if row is not None else default
            self.form.text(key, title, value); self.form.set_value(key, value)
        for key, text in dict(profile='Örn. 40×40×2 veya Ø42,4×2', material='Örn. S235JR', length='Örn. 1200').items():
            self.form.fields[key].setPlaceholderText(text)
        fields.addWidget(self.form)
        self.extra = ValueForm(page.settings, 'profile_row_editor_')
        for key, title, default in (('thickness','Et kalınlığı · mm',''),('standard','Profil standardı',''),
                                   ('stock_code','Stok kodu',''),('allowance','İlave boy · mm / parça','0')):
            value = str(getattr(row,key)) if row is not None else default
            self.extra.text(key,title,value); self.extra.set_value(key,value)
        self.extra.form.addRow(label('İlave boy, gönye / son işlem için parçaya eklenir. Testere payı ayrıca hesaplanır. Kesitte açıkça yazılan et kalınlığı boş bırakılırsa okunur.', 'muted'))
        if not self.review_mode:
            self.extra.text('note','Not',''); self.extra.set_value('note',row.note if row else '')
        self.form.fields.update(self.extra.fields)
        try: has_allowance = bool(row and number(row.allowance))
        except ValueError: has_allowance = True
        self.advanced = Disclosure('Diğer bilgiler · isteğe bağlı',self.extra, expanded=has_allowance)
        fields.addWidget(self.advanced)
        if self.review_mode:
            fields.addWidget(label('Kaynak açıları doğrudan testere ayarı değildir. Açılı kesimde uzun uç ölçüsünü, yönü ve gerekli ilave boyu üretim resminden kontrol edin.', 'muted'))
            review = ValueForm(page.settings, 'profile_row_editor_')
            review.text('note', 'Kontrol notu', ''); review.set_value('note', row.review_note)
            review.check('confirmed', 'Doğrusal profil, miktar ve gerekli ham stok boyunu doğruladım.', False, persist=False)
            self.form.fields.update(review.fields); fields.addWidget(review)
        fields.addStretch(); body.addWidget(scroll(content), 1)
        self.error_label = label('', 'error'); self.error_label.hide(); body.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Kontrolü onayla' if self.review_mode else 'Değişiklikleri uygula' if row else 'Listeye ekle')
        buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        buttons.accepted.connect(self.check); buttons.rejected.connect(self.reject)
        body.addWidget(buttons)

    def check(self):
        try:
            values = {key: self.form.value(key) for key in
                      ('profile','material','length','count','thickness','standard','stock_code','allowance')}
            if not values['profile'].strip() or not values['material'].strip():
                raise ValueError('Profil kesitini ve malzeme kalitesini girin.')
            values['length'] = str(number(values['length'], 'Parça boyu', positive=True))
            values['allowance'] = str(number(values['allowance'], 'Ek ham boy'))
            values['count'] = quantity(values['count'])
            inferred = section_thickness(values['profile'])
            if not values['thickness']:
                if inferred is not None: values['thickness'] = str(inferred)
            if values['thickness']:
                actual = number(values['thickness'], 'Et kalınlığı', positive=True)
                if inferred is not None and actual != inferred:
                    self.advanced.set_expanded(True)
                    raise ValueError('Et kalınlığı profil kesitiyle uyuşmuyor. Kesitteki değeri girin veya otomatik okumak için boş bırakın.')
            if not values['profile'].strip() or not values['material'].strip():
                raise ValueError('Profil kesiti ve malzeme kalitesi girin.')
            note = self.form.value('note').strip()
            if self.review_mode:
                if not self.form.value('confirmed') or not note:
                    raise ValueError('Doğrulama kutusunu işaretleyin ve neyi kontrol ettiğinizi not edin.')
                self.value = replace(self.original, **values, reviewed=True, review_note=note)
            elif self.original is not None:
                self.value = replace(self.original, **values, note=note)
                self.value.validate()
            else:
                self.value = Demand(uuid4().hex, **values, note=note)
            self.accept()
        except ValueError as error:
            self.error_label.setText(str(error)); self.error_label.show()
