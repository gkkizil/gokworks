"""Small native dialogs for mapping, manual demands and explicit source review."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QMessageBox
from gui_qt.components import ValueForm, label, scroll
from .models import Demand, quantity, number
from .properties import DEFAULT_MAPPING, validate_mapping


class MappingDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.setWindowTitle('Weldments · Property eşleştirmesi')
        self.resize(530, 600)
        body = QVBoxLayout(self)
        body.addWidget(label('Property adlarını noktalı virgülle ayırın. Ham ifadeler çözümlenmiş değer yerine kullanılmaz.', 'muted'))
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
        self.value = None
        self.setWindowTitle('Profil · Kaynak inceleme' if row else 'Manuel profil ekle')
        self.resize(540, 660)
        body = QVBoxLayout(self)
        self.form = ValueForm(page.settings, 'profile_row_editor_')
        if row:
            body.addWidget(label(f'{row.source} [{row.configuration}]\nCut List: {row.folder}', 'muted'))
            notes = row.issues+row.errors()
            body.addWidget(label('\n'.join(notes[:6]) + ('\nDiğer sorunlar: Tarama ayrıntıları bölümünde.' if len(notes)>6 else '') or 'Kaynak veriler hazır.', 'muted'))
        for key, title, default in (
            ('profile','Profil kesiti','40×40×2'), ('material','Malzeme kalitesi','S235JR'),
            ('length','Kesim boyu · mm','1000'), ('count','Adet','1'),
            ('thickness','Et kalınlığı · mm',''), ('standard','Profil standardı',''),
            ('stock_code','Stok kodu',''), ('allowance','Ek ham boy · mm / parça','0')):
            value = str(getattr(row, key)) if row is not None else default
            self.form.text(key, title, value); self.form.set_value(key, value)
        self.form.text('note', 'Doğrulama notu' if row else 'Not', '')
        self.form.set_value('note', row.review_note if row else '')
        if row:
            body.addWidget(label('SOLIDWORKS Angle1/Angle2, doğrudan testere ayarı değildir. Gönye için uzun uç ölçüsünü, yönü, ilave ham boyu ve testere açısını üretim resminden doğrulayın.', 'muted'))
            self.form.check('confirmed', 'Doğrusal profil, miktar ve gerekli ham stok boyunu doğruladım.', False, persist=False)
        body.addWidget(scroll(self.form), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.check); buttons.rejected.connect(self.reject)
        body.addWidget(buttons)

    def check(self):
        try:
            values = {key: self.form.value(key) for key in
                      ('profile','material','length','count','thickness','standard','stock_code','allowance')}
            values['length'] = str(number(values['length'], 'Boy', positive=True))
            values['allowance'] = str(number(values['allowance'], 'Ek ham boy'))
            values['count'] = quantity(values['count'])
            if values['thickness']: number(values['thickness'], 'Et kalınlığı', positive=True)
            if not values['profile'].strip() or not values['material'].strip():
                raise ValueError('Profil kesiti ve malzeme kalitesi girin.')
            note = self.form.value('note').strip()
            if self.original is not None:
                if not self.form.value('confirmed') or not note:
                    raise ValueError('Doğrulama kutusunu işaretleyin ve neyi kontrol ettiğinizi not edin.')
                self.value = replace(self.original, **values, reviewed=True, review_note=note)
            else:
                self.value = Demand(uuid4().hex, **values, note=note)
            self.accept()
        except ValueError as error: QMessageBox.warning(self, 'Profil bilgileri', str(error))
