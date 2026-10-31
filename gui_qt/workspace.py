"""Native CAD-style navigation and contextual workbench chrome."""

from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtWidgets import (QFrame, QWidget, QVBoxLayout, QHBoxLayout,
    QToolButton, QLineEdit, QComboBox, QSizePolicy)

from .components import button, label, scroll
from .icons import BrandLogo
from .models import search_text


WORKSPACES = (
    ('Aktarım', ('pdf', 'dxf_dwg', 'cad_converter')),
    ('Montaj', ('bom', 'naming')),
    ('Üretim', ('nesting', 'profile_cutting', 'k_factor', 'shaft_generator')),
    ('Hesaplar', ('iso_fits', 'geometric_tolerances', 'tolerance_stack', 'bolt', 'bolt_torque', 'weight')),
    ('Makine Elemanları', ('gear_calculator',)),
)


class NavigationGroup(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName('navigationGroup')
        body = QVBoxLayout(self); body.setContentsMargins(0,0,0,0); body.setSpacing(1)
        self.toggle = QToolButton(); self.toggle.setText(title.replace('i','İ').upper())
        self.toggle.setProperty('navigationGroup', True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True); self.toggle.setChecked(True)
        self.toggle.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.toggle.setAccessibleName(title+' araçlarını göster veya gizle')
        self.content = QWidget(); self.items = QVBoxLayout(self.content)
        self.items.setContentsMargins(0,0,0,3); self.items.setSpacing(1)
        body.addWidget(self.toggle); body.addWidget(self.content)
        self.toggle.toggled.connect(self.expand); self.expand(True)

    def expand(self, expanded):
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)


class ModuleBrowser(QFrame):
    def __init__(self, modules, settings, navigate, toggle_sidebar, show_settings, show_about, set_theme, *, show_contact=None):
        super().__init__()
        self.settings = settings; self.collapsed = False
        self.setObjectName('sidebar'); self.setFixedWidth(232)
        body = QVBoxLayout(self); body.setContentsMargins(8,6,8,8); body.setSpacing(6)
        brand = QHBoxLayout(); brand.setSpacing(6)
        self.logo = BrandLogo(); self.logo.setMinimumWidth(80); self.logo.setFixedSize(104,30)
        brand.addWidget(self.logo); brand.addStretch()
        self.menu_toggle = QToolButton(); self.menu_toggle.setText('‹'); self.menu_toggle.setFixedSize(28,28)
        self.menu_toggle.clicked.connect(toggle_sidebar); brand.addWidget(self.menu_toggle); body.addLayout(brand)
        self.caption = label('ÇALIŞMA ALANLARI','muted'); self.caption.setProperty('eyebrow',True)
        body.addWidget(self.caption)
        self.search = QLineEdit(); self.search.setPlaceholderText('Araç bul…  Ctrl+K'); self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        self.search.setAccessibleName('GOKWORKS araçlarında ara')
        self.search.setToolTip('Ctrl+K: ara · Enter: ilk aracı aç · Esc: aramayı temizle')
        body.addWidget(self.search)
        menu = QWidget(); groups_layout = QVBoxLayout(menu)
        groups_layout.setContentsMargins(0,0,0,0); groups_layout.setSpacing(4)
        self.groups = {}; self.buttons = {}; self.group_for_mode = {}
        titles = {key:title for key,title,_ in modules}
        preferences = settings.get('navigation_groups',{})
        if not isinstance(preferences,dict): preferences = {}
        for title, keys in WORKSPACES:
            group = NavigationGroup(title); self.groups[title] = group
            group.toggle.setText(group.toggle.text()+'  ·  '+str(len(keys)))
            for key in keys:
                nav = button(titles[key],lambda checked=False,key=key:navigate(key))
                nav.setProperty('nav',True); nav.setCheckable(True); nav.setIconSize(QSize(18,18))
                nav.setAccessibleName(titles[key]); nav.setToolTip(titles[key])
                group.items.addWidget(nav); self.buttons[key] = nav; self.group_for_mode[key] = title
            group.toggle.setChecked(preferences.get(title,True) is not False)
            group.toggle.toggled.connect(lambda checked,title=title:self.remember_group(title,checked))
            groups_layout.addWidget(group)
        self.search_feedback = label('', 'muted')
        self.search_feedback.setTextFormat(Qt.PlainText)
        self.search_feedback.setAlignment(Qt.AlignCenter)
        self.search_feedback.setContentsMargins(8, 18, 8, 8)
        self.search_feedback.hide()
        groups_layout.addWidget(self.search_feedback)
        self.reset_search = button('Aramayı temizle', self.search.clear)
        self.reset_search.hide(); groups_layout.addWidget(self.reset_search)
        groups_layout.addStretch()
        self.menu_scroll = scroll(menu); self.menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.addWidget(self.menu_scroll,1)
        self.footer = QWidget(); footer = QVBoxLayout(self.footer)
        footer.setContentsMargins(0,0,0,0); footer.setSpacing(4)
        row=QHBoxLayout();row.setSpacing(4)
        self.settings_button = button('Ayarlar',show_settings); self.about_button = button('Hakkında',show_about)
        row.addWidget(self.settings_button);row.addWidget(self.about_button);footer.addLayout(row)
        self.contact_button=button('İletişim',show_contact)
        self.contact_button.setToolTip('E-posta ve LinkedIn iletişim bilgileri')
        footer.addWidget(self.contact_button);body.addWidget(self.footer)
        self.theme_picker = QComboBox()
        self.theme_picker.addItem('Koyu tema','dark'); self.theme_picker.addItem('Açık tema','light')
        self.theme_picker.setCurrentIndex(0 if settings.get('appearance','dark')=='dark' else 1)
        self.theme_picker.setAccessibleName('Arayüz teması')
        self.theme_picker.currentIndexChanged.connect(lambda:set_theme(self.theme_picker.currentData()))
        body.addWidget(self.theme_picker)
        self.search.textChanged.connect(self.filter)

    def remember_group(self,title,expanded):
        if self.collapsed or self.search.text(): return
        values = dict(self.settings.get('navigation_groups',{})) if isinstance(self.settings.get('navigation_groups',{}),dict) else {}
        values[title] = expanded; self.settings.set('navigation_groups',values)

    def activate(self, mode):
        if not self.collapsed:
            group = self.groups[self.group_for_mode[mode]]
            group.toggle.setChecked(True)
        for key,control in self.buttons.items(): control.setChecked(key==mode)
        self.menu_scroll.ensureWidgetVisible(self.buttons[mode], 0, 12)

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.search.clear()
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
                matches = [b for b in self.buttons.values() if b.isVisible()]
                if matches:
                    if event.key() == Qt.Key_Down:
                        matches[0].setFocus()
                    else:
                        matches[0].click()
                        matches[0].setFocus()
                return True
        return super().eventFilter(watched, event)

    def filter(self, value):
        needle = search_text(value.strip())
        for title, keys in WORKSPACES:
            visible = False
            for key in keys:
                match = not needle or needle in search_text(title+' '+self.buttons[key].accessibleName())
                self.buttons[key].setVisible(match); visible |= match
            group = self.groups[title]; group.setVisible(visible)
            if needle or self.collapsed: group.content.setVisible(True)
            else: group.content.setVisible(group.toggle.isChecked())
        empty = bool(needle) and not any(not b.isHidden() for b in self.buttons.values())
        self.search_feedback.setText('Araç bulunamadı.\nFarklı bir ad veya çalışma alanı deneyin.')
        self.search_feedback.setVisible(empty)
        self.reset_search.setVisible(empty)
        if not needle:
            selected = next((b for b in self.buttons.values() if b.isChecked()), None)
            if selected is not None: self.menu_scroll.ensureWidgetVisible(selected, 0, 12)

    def set_collapsed(self, collapsed):
        self.collapsed = collapsed; self.setFixedWidth(64 if collapsed else 232)
        for widget in (self.logo,self.caption,self.search,self.footer,self.theme_picker): widget.setVisible(not collapsed)
        for group in self.groups.values():
            group.toggle.setVisible(not collapsed)
        for control in self.buttons.values():
            control.setText('' if collapsed else control.accessibleName())
            control.setStyleSheet('text-align:center; padding:5px 0;' if collapsed else '')
        self.menu_toggle.setText('›' if collapsed else '‹')
        self.menu_toggle.setToolTip('Menüyü genişlet · Ctrl+B' if collapsed else 'Menüyü daralt · Ctrl+B')
        self.menu_toggle.setAccessibleName(self.menu_toggle.toolTip())
        self.filter('' if collapsed else self.search.text())
