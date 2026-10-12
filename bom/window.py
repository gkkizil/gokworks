"""BOM preview and Excel export, with workers separated from Tk rendering."""

from pathlib import PureWindowsPath
from itertools import chain
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import customtkinter as ctk

from bom.exporter import Cancelled, export_excel, scan_worker
from gui.icons import set_window_icon
from gui.rendering import hide_grid
from gui.text import BOM_TITLE, BOM_TREE_TAB
from gui.theme import (PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT, ACCENT_BG,
                       SECONDARY, HOVER, GREEN, RED, AMBER, UI_FONT)


class BomTabs(ctk.CTkTabview):
    _button_height = 36
    _outer_spacing = 4

    def set(self, name):
        super().set(name)
        if self._command:
            self._command()


class BomView:
    def _create_bom_state(self, saved):
        self.bom_state = {'include_excluded': tk.BooleanVar(self, value=saved.get('bom_include_excluded', False) is True)}
        self.bom_query = tk.StringVar(self)
        self.bom_query.trace_add('write', lambda *_: self._filter_bom() if self.mode == 'bom' else None)
        self.bom_result = None
        self.bom_widgets = {}

    def _build_bom_workspace(self):
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self.workspace, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(18, 14))
        header.grid_columnconfigure(0, weight=1)
        self.bom_widgets['eyebrow'] = self._label(header, 'MONTAJ YÖNETİMİ', 10, MUTED, True)
        self.bom_widgets['eyebrow'].grid(row=0, column=0, sticky='w')
        self._label(header, BOM_TITLE, 25, bold=True).grid(row=1, column=0, sticky='w', pady=(5, 4))
        self.bom_widgets['subtitle'] = self._label(header, 'Parça listesi ve alt montaj hiyerarşisi.', 12, MUTED,
                    width=1, wraplength=300, justify='left', anchor='w')
        self.bom_widgets['subtitle'].grid(row=2, column=0, sticky='ew')
        actions = ctk.CTkFrame(header, fg_color='transparent')
        actions.grid(row=1, column=1, rowspan=2, sticky='e', padx=(12, 0))
        for key, label, command, width, primary, icon in (
                ('scan', 'Montajı tara', self._scan_bom, 128, False, 'search'),
                ('export', 'Excel’e aktar', self._save_bom, 144, True, 'download'),
                ('stop', 'Durdur', self._stop_bom, 78, False, None)):
            button = self._button(actions, label, command, width=width, primary=primary, icon=icon)
            button.configure(height=42)
            button.pack(side='left', padx=(0, 6))
            self.bom_widgets[key] = button
        self.bom_widgets['export'].configure(state='disabled')
        self.bom_widgets['stop'].configure(state='disabled')

        source = ctk.CTkFrame(self.workspace, fg_color=INPUT, corner_radius=12,
                              border_width=1, border_color=BORDER)
        source.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 12))
        source.grid_columnconfigure(1, weight=1)
        badge = ctk.CTkLabel(source, text='', image=self._icon('layers', ACCENT, 24),
                            width=44, height=44, fg_color=ACCENT_BG, corner_radius=10)
        badge.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=12)
        self.bom_widgets['assembly'] = self._label(source, 'Montaj seçilmedi', 14, bold=True,
                                                   anchor='w', width=1, wraplength=460)
        self.bom_widgets['assembly'].grid(row=0, column=1, sticky='ew', pady=(12, 2))
        self.bom_widgets['configuration'] = self._label(source,
            'SolidWorks’te ana montajı etkinleştirin.', 11, MUTED, anchor='w', width=1, wraplength=460)
        self.bom_widgets['configuration'].grid(row=1, column=1, sticky='ew', pady=(0, 12))
        options = ctk.CTkFrame(source, fg_color='transparent')
        options.grid(row=0, column=2, rowspan=2, sticky='e', padx=16, pady=12)
        self.bom_widgets['excluded'] = ctk.CTkCheckBox(options, text='BOM dışındakileri ekle',
            variable=self.bom_state['include_excluded'], text_color=TEXT, fg_color=ACCENT,
            font=(UI_FONT, 12), checkbox_width=18, checkbox_height=18, border_color=BORDER)
        self.bom_widgets['excluded'].pack(anchor='e')
        self._label(options, 'Sonraki taramada uygulanır', 10, MUTED).pack(anchor='e', pady=(4, 0))

        metrics = ctk.CTkFrame(self.workspace, fg_color='transparent')
        metrics.grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 14))
        for column, (key, label, icon) in enumerate((('unique', 'Farklı parça', 'file'),
                    ('quantity', 'Toplam adet', 'layers'), ('assemblies', 'Alt montaj adedi', 'folder'))):
            metrics.grid_columnconfigure(column, weight=1, uniform='bom_metrics')
            card = ctk.CTkFrame(metrics, fg_color=INPUT, border_width=1, border_color=BORDER, corner_radius=10)
            card.grid(row=0, column=column, sticky='ew', padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
            card.grid_columnconfigure(0, weight=1)
            caption = self._label(card, label, 11, MUTED)
            caption.grid(row=0, column=0, sticky='w', padx=14, pady=(8, 0))
            value = self._label(card, '0', 22, ACCENT if key == 'quantity' else TEXT, True)
            value.grid(row=1, column=0, sticky='w', padx=14, pady=(0, 8))
            symbol = ctk.CTkLabel(card, text='', image=self._icon(icon, MUTED, 22))
            symbol.grid(row=0, column=1, rowspan=2, padx=14)
            self.bom_widgets['metric_'+key] = value
            self.bom_widgets['metric_caption_'+key] = caption
            self.bom_widgets['metric_icon_'+key] = symbol

        content = ctk.CTkFrame(self.workspace, fg_color='transparent')
        content.grid(row=3, column=0, sticky='nsew', padx=24)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.bom_widgets['content'] = content
        card = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        card.grid(row=0, column=0, sticky='nsew')
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        titlebar = ctk.CTkFrame(card, fg_color='transparent')
        titlebar.grid(row=0, column=0, sticky='ew', padx=16, pady=(14, 4))
        titlebar.grid_columnconfigure(0, weight=1)
        self._label(titlebar, 'Montaj içeriği', 15, bold=True).grid(row=0, column=0, sticky='w')
        self.bom_widgets['counts'] = self._label(titlebar, 'Henüz tarama yapılmadı', 11, MUTED)
        self.bom_widgets['counts'].grid(row=0, column=1, sticky='e')
        detailbar = ctk.CTkFrame(card, fg_color='transparent')
        detailbar.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 8))
        detailbar.grid_columnconfigure(0, weight=1)
        self.bom_widgets['selection_summary'] = self._label(detailbar,
            'Excel dosyasına tüm montaj aktarılır.', 10, MUTED, anchor='w', width=1)
        self.bom_widgets['selection_summary'].grid(row=0, column=0, sticky='ew', padx=(0, 8))
        details = self._button(detailbar, 'Ayrıntılar', self._show_bom_details, width=90, state='disabled')
        details.configure(height=30)
        details.grid(row=0, column=1, sticky='e')
        self.bom_widgets['details'] = details
        tabs = BomTabs(card, fg_color=PANEL, text_color=TEXT, anchor='w',
                       command=self._bom_tab_changed,
                       segmented_button_fg_color=INPUT, segmented_button_unselected_color=INPUT,
                       segmented_button_unselected_hover_color=SECONDARY,
                       segmented_button_selected_color=ACCENT_BG,
                       segmented_button_selected_hover_color=HOVER)
        tabs.grid(row=1, column=0, sticky='nsew', padx=12, pady=(0, 4))
        tabs._segmented_button.configure(font=(UI_FONT, 13, 'bold'), corner_radius=8,
                                         width=300, dynamic_resizing=False)
        self.bom_widgets['tabs'] = tabs
        for label, key in (('Parça listesi', 'parts'), (BOM_TREE_TAB, 'tree')):
            tab = tabs.add(label)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)
            toolbar = ctk.CTkFrame(tab, fg_color='transparent')
            toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(8, 10))
            toolbar.grid_columnconfigure(0, weight=1)
            if key == 'parts':
                search_box = ctk.CTkFrame(toolbar, fg_color=INPUT, border_width=1, border_color=BORDER, corner_radius=8)
                search_box.grid(row=0, column=0, sticky='ew', padx=(0, 8))
                search_box.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(search_box, text='', image=self._icon('search', MUTED, 18), width=30).grid(row=0, column=0, padx=(6, 0))
                entry = ctk.CTkEntry(search_box, textvariable=self.bom_query,
                                    fg_color=INPUT, text_color=TEXT, border_width=0, height=36, font=(UI_FONT, 12))
                entry.grid(row=0, column=1, sticky='ew')
                hint = self._label(search_box, 'Parça adı, konfigürasyon veya yol ara', 11, MUTED, anchor='w', width=1)
                hint.grid(row=0, column=1, sticky='ew', padx=5)
                hint.bind('<Button-1>', lambda event: self.bom_widgets['search'].focus_set())
                entry.bind('<FocusIn>', lambda event: self._update_bom_search_hint(), add='+')
                entry.bind('<FocusOut>', lambda event: self._update_bom_search_hint(), add='+')
                self.bom_widgets['search_hint'] = hint
                clear = self._button(search_box, '×', lambda: self.bom_query.set(''), width=30)
                clear.configure(height=28, fg_color=INPUT)
                clear.grid(row=0, column=2, padx=4)
                self.bom_widgets['search'] = entry
                self.bom_widgets['clear_search'] = clear
                self._label(toolbar, 'Ada göre sıralı', 11, MUTED).grid(row=0, column=1, sticky='e')
                table = ttk.Treeview(tab, columns=('name', 'qty', 'config', 'path'),
                                     displaycolumns=('name', 'qty', 'config'), show='headings', style='Bom.Treeview')
                columns = [('name', 'Parça adı ↑', 260), ('qty', 'Adet', 75), ('config', 'Konfigürasyon', 180), ('path', 'Dosya yolu', 300)]
            else:
                self._label(toolbar, 'Montaj hiyerarşisi', 11, MUTED).grid(row=0, column=0, sticky='w')
                for column, (key_button, text, expanded) in enumerate((('expand', 'Tümünü aç', True), ('collapse', 'Tümünü kapat', False)), 1):
                    button = self._button(toolbar, text, lambda opened=expanded: self._toggle_bom_tree(opened), width=105)
                    button.configure(height=32)
                    button.grid(row=0, column=column, sticky='e', padx=(6, 0))
                    self.bom_widgets[key_button] = button
                table = ttk.Treeview(tab, columns=('kind', 'config', 'path'),
                    displaycolumns=('kind', 'config'), show='tree headings', style='Bom.Treeview')
                table.heading('#0', text='Montaj / parça', anchor='w')
                table.column('#0', width=330, minwidth=200)
                columns = [('kind', 'Tür', 90), ('config', 'Konfigürasyon', 180), ('path', 'Dosya yolu', 300)]
            for column, title, width in columns:
                table.heading(column, text=title, anchor='center' if column == 'qty' else 'w')
                table.column(column, width=width, minwidth=60, stretch=column not in ('qty', 'kind'),
                             anchor='center' if column == 'qty' else 'w')
            table.configure(selectmode='browse')
            table.grid(row=1, column=0, sticky='nsew')
            vertical = ctk.CTkScrollbar(tab, command=table.yview, width=10, fg_color=PANEL, button_color=BORDER)
            vertical.grid(row=1, column=1, sticky='ns')
            horizontal = ctk.CTkScrollbar(tab, orientation='horizontal', command=table.xview, height=10,
                                         fg_color=PANEL, button_color=BORDER)
            horizontal.grid(row=2, column=0, sticky='ew')
            table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            table.bind('<<TreeviewSelect>>', lambda event, view=key: self._select_bom_row(view))
            table.bind('<Return>', lambda event, view=key: self._show_bom_details(view))
            self.bom_widgets[key] = table
            empty = ctk.CTkFrame(table, fg_color=PANEL, corner_radius=0)
            empty.place(relx=.5, rely=.5, anchor='center')
            empty_icon = ctk.CTkLabel(empty, text='', image=self._icon('layers' if key == 'tree' else 'file', ACCENT, 32),
                                    fg_color=ACCENT_BG, width=64, height=64, corner_radius=16)
            empty_icon.pack(pady=(0, 12))
            heading = self._label(empty, 'Montajınız burada görünecek', 16, bold=True)
            heading.pack()
            hint = self._label(empty, 'Montajı tarayın; parçalar ve adetler otomatik listelensin.', 11, MUTED,
                               wraplength=310, justify='center')
            hint.pack(pady=(5, 0))
            self.bom_widgets[key+'_empty'] = empty
            self.bom_widgets[key+'_empty_icon'] = empty_icon
            self.bom_widgets[key+'_empty_heading'] = heading
            self.bom_widgets[key+'_empty_hint'] = hint

        inspector = ctk.CTkFrame(content, width=220, fg_color=INPUT, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        inspector.grid(row=0, column=1, sticky='ns', padx=(12, 0))
        inspector.grid_propagate(False)
        inspector.grid_columnconfigure(0, weight=1)
        self._label(inspector, 'SATIR AYRINTISI', 10, MUTED, True).grid(row=0, column=0, sticky='w', padx=16, pady=(18, 14))
        self.bom_widgets['detail_name'] = self._label(inspector, 'Bir satır seçin', 16, bold=True,
                                                     anchor='w', justify='left', wraplength=185)
        self.bom_widgets['detail_name'].grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 6))
        self.bom_widgets['detail_info'] = self._label(inspector, 'Parça veya alt montaj bilgileri burada görünür.', 11, MUTED,
                                                     anchor='w', justify='left', wraplength=185)
        self.bom_widgets['detail_info'].grid(row=2, column=0, sticky='ew', padx=16)
        ctk.CTkFrame(inspector, height=1, fg_color=BORDER).grid(row=3, column=0, sticky='ew', padx=16, pady=18)
        self._label(inspector, 'DOSYA YOLU', 10, MUTED, True).grid(row=4, column=0, sticky='w', padx=16)
        self.bom_widgets['detail_path'] = self._label(inspector, 'Seçim yapılmadı', 11, MUTED,
                                                    anchor='w', justify='left', wraplength=185)
        self.bom_widgets['detail_path'].grid(row=5, column=0, sticky='ew', padx=16, pady=(6, 12))
        copy = self._button(inspector, 'Yolu kopyala', self._copy_bom_path, icon='copy', width=170, state='disabled')
        copy.grid(row=6, column=0, sticky='ew', padx=16)
        self.bom_widgets['copy_path'] = copy
        self.bom_widgets['inspector'] = inspector
        footer = ctk.CTkFrame(self.workspace, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='ew', padx=24, pady=(10, 6))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = self._label(footer, 'Hazır · Ana montajı tarayarak başlayın.', 11, MUTED,
                                        anchor='w', wraplength=700, justify='left')
        self.status_label.grid(row=0, column=0, sticky='ew')
        self.progress = ctk.CTkProgressBar(self.workspace, height=3, progress_color=ACCENT, fg_color=BORDER)
        self.progress.grid(row=5, column=0, sticky='ew', padx=24, pady=(0, 12))
        self.progress.set(0)
        self._configure_table_style()
        self._bom_busy(False)
        for key in ('parts', 'tree'):
            self._bom_empty_state(key)
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._resize_bom_workspace()

    def _style_bom_tables(self, widgets=None):
        widgets = self.bom_widgets if widgets is None else widgets
        scale = widgets['content']._get_widget_scaling()
        color = lambda value: value[1 if ctk.get_appearance_mode() == 'Dark' else 0]
        style = ttk.Style(self)
        style.configure('Bom.Treeview', background=color(PANEL), fieldbackground=color(PANEL),
                        foreground=color(TEXT), borderwidth=0, bordercolor=color(PANEL),
                        lightcolor=color(PANEL), darkcolor=color(PANEL), rowheight=round(38*scale),
                        font=(UI_FONT, -round(12*scale)))
        style.configure('Bom.Treeview.Heading', background=color(INPUT), foreground=color(MUTED),
                        relief='flat', padding=(round(10*scale), round(10*scale)),
                        font=(UI_FONT, -round(11*scale), 'bold'))
        style.map('Bom.Treeview.Heading', background=[('active', color(SECONDARY))])
        style.map('Bom.Treeview', background=[('selected', color(ACCENT_BG))],
                  foreground=[('selected', color(TEXT))])
        for key in ('parts', 'tree'):
            table = widgets[key]
            table.tag_configure('stripe', background=color(INPUT))
            table.tag_configure('assembly', foreground=color(ACCENT), background=color(ACCENT_BG),
                                font=(UI_FONT, -round(12*scale), 'bold'))

    def _resize_bom_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.workspace.winfo_width() < 100:
            return
        widgets = self.bom_widgets
        scale = self.workspace._get_widget_scaling()
        width = self.workspace.winfo_width()/scale
        compact = self.workspace.winfo_height()/scale < 740
        if widgets.get('compact') != compact:
            widgets['compact'] = compact
            for key, row in (('eyebrow', 0), ('subtitle', 2)):
                if compact:
                    hide_grid(widgets[key])
                else:
                    widgets[key].grid(row=row, column=0, sticky='ew' if row == 2 else 'w')
            for key in ('unique', 'quantity', 'assemblies'):
                caption, value, icon = (widgets[prefix+key] for prefix in
                                        ('metric_caption_', 'metric_', 'metric_icon_'))
                caption.grid(row=0, column=0, sticky='w', padx=14, pady=10 if compact else (8, 0))
                value.grid(row=0 if compact else 1, column=1 if compact else 0,
                           sticky='e' if compact else 'w', padx=(0, 14) if compact else 14,
                           pady=8 if compact else (0, 8))
                if compact:
                    hide_grid(icon)
                else:
                    icon.grid(row=0, column=1, rowspan=2, padx=14)
        if getattr(self, '_table_style_key', None) != (ctk.get_appearance_mode(), scale):
            self._configure_table_style()
        show_inspector = width >= 950
        if widgets.get('show_inspector') != show_inspector:
            if show_inspector:
                widgets['inspector'].grid(row=0, column=1, sticky='ns', padx=(12, 0))
            else:
                hide_grid(widgets['inspector'])
            widgets['show_inspector'] = show_inspector
        wrap = max(180, width-370)
        for key in ('assembly', 'configuration'):
            if widgets[key].cget('wraplength') != wrap:
                widgets[key].configure(wraplength=wrap)
        self.status_label.configure(wraplength=max(240, width-48))
        # Keep the useful columns in view; paths belong in the detail panel.
        table_width = max(340, width-98-(232 if show_inspector else 0))
        for key, name_column, fixed_column in (('parts', 'name', 'qty'), ('tree', '#0', 'kind')):
            table = widgets[key]
            fixed = 70 if key == 'parts' else 85
            config = min(175, table_width*.30)
            table.column(name_column, width=round((table_width-fixed-config)*scale), minwidth=round(140*scale))
            table.column(fixed_column, width=round(fixed*scale), minwidth=round(60*scale), stretch=False)
            table.column('config', width=round(config*scale), minwidth=round(100*scale))
            icon = widgets[key+'_empty_icon']
            if table.winfo_height()/scale < 210:
                icon.pack_forget()
            elif not icon.winfo_manager():
                icon.pack(before=widgets[key+'_empty_heading'], pady=(0, 12))
            widgets[key+'_empty_hint'].configure(wraplength=min(310, table_width-28))

    def _update_bom_search_hint(self):
        if 'search_hint' not in self.bom_widgets:
            return
        if self.bom_query.get() or self.focus_get() == self.bom_widgets['search']._entry:
            hide_grid(self.bom_widgets['search_hint'])
        else:
            self.bom_widgets['search_hint'].grid(row=0, column=1, sticky='ew', padx=5)

    def _update_bom_metrics(self):
        result = self.bom_result
        values = (len(result.parts), result.total_parts,
                  sum(node.kind == 'Montaj' for node in result.tree)) if result is not None else (0, 0, 0)
        for key, value in zip(('unique', 'quantity', 'assemblies'), values):
            self.bom_widgets['metric_'+key].configure(text=f'{value:,}'.replace(',', '.'))

    def _update_bom_counts(self):
        if self.bom_result is None:
            return
        if self.bom_widgets['tabs'].get() == BOM_TREE_TAB:
            text = f'{len(self.bom_result.tree)} bileşen'
        else:
            text = f'{len(self.bom_widgets["parts"].get_children())} / {len(self.bom_result.parts)} parça'
        self.bom_widgets['counts'].configure(text=text)

    def _bom_tab_changed(self):
        self._update_bom_counts()
        view = 'parts' if self.bom_widgets['tabs'].get() == 'Parça listesi' else 'tree'
        self._reset_bom_details()
        self._select_bom_row(view)

    def _bom_empty_state(self, key, *, filtered=False):
        widgets = self.bom_widgets
        table = widgets[key]
        if table.get_children():
            widgets[key+'_empty'].place_forget()
            return
        has_result = self.bom_result is not None
        heading = 'Eşleşen parça yok' if filtered else 'Montajda parça bulunamadı' if has_result else 'Montajınız burada görünecek'
        hint = ('Aramayı değiştirin veya × düğmesiyle temizleyin.' if filtered else
                'Bastırılmış ve BOM dışı bileşenleri kontrol edin.' if has_result else
                'SolidWorks’te bir montaj açıp Montajı tara’ya basın.')
        widgets[key+'_empty_heading'].configure(text=heading)
        widgets[key+'_empty_hint'].configure(text=hint)
        widgets[key+'_empty'].place(relx=.5, rely=.55, anchor='center')

    def _reset_bom_details(self):
        widgets = self.bom_widgets
        widgets.pop('selection', None)
        widgets['detail_name'].configure(text='Bir satır seçin')
        widgets['detail_info'].configure(text='Parça veya alt montaj bilgileri burada görünür.')
        widgets['detail_path'].configure(text='Seçim yapılmadı')
        widgets['selection_summary'].configure(text='Excel dosyasına tüm montaj aktarılır.')
        for key in ('copy_path', 'details'):
            widgets[key].configure(state='disabled')

    def _select_bom_row(self, view):
        # Selection events from a hidden tab must not replace the visible details.
        active = 'parts' if self.bom_widgets['tabs'].get() == 'Parça listesi' else 'tree'
        if view != active:
            return
        result = self.bom_result
        if result is None or 'render' in self.bom_widgets:
            return
        rows = self.bom_widgets[view].selection()
        if not rows:
            return self._reset_bom_details()
        if view == 'parts':
            part = result.parts[int(rows[0].removeprefix('part_'))]
            name, path = part.name, part.path
            info = f'Parça · {part.quantity} adet\nKonfigürasyon: {part.configuration}'
        else:
            node = self.bom_widgets['nodes'][rows[0]]
            name, path = node.name, node.path
            info = f'{node.kind}\nKonfigürasyon: {node.configuration}\nBileşen: {node.instance}'
        self.bom_widgets['selection'] = name, info, path
        self.bom_widgets['detail_name'].configure(text=name)
        self.bom_widgets['detail_info'].configure(text=info)
        self.bom_widgets['detail_path'].configure(text=path or 'Dosya yolu bulunamadı')
        self.bom_widgets['selection_summary'].configure(text=f'{name} · Excel’e tüm montaj aktarılır.')
        self.bom_widgets['details'].configure(state='normal' if not self.busy else 'disabled')
        self.bom_widgets['copy_path'].configure(state='normal' if path and not self.busy else 'disabled')

    def _copy_bom_path(self, path=None):
        if path is None:
            selection = self.bom_widgets.get('selection')
            path = selection[2] if selection else ''
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            if self.mode == 'bom' and not self.busy:
                self.status_label.configure(text='Dosya yolu kopyalandı.', text_color=MUTED)

    def _show_bom_details(self, view=None):
        if self.busy:
            return 'break'
        if view is not None:
            self._select_bom_row(view)
        selection = self.bom_widgets.get('selection')
        if selection is None:
            return 'break'
        name, info, path = selection
        self._close_detail()
        window = ctk.CTkToplevel(self)
        set_window_icon(window)
        self.detail_window = window
        window.title('GOKWORKS · BOM satır ayrıntıları')
        window.geometry('620x400')
        window.minsize(500, 320)
        window.configure(fg_color=PANEL)
        window.transient(self)
        window.protocol('WM_DELETE_WINDOW', self._close_detail)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        self._label(window, name, 20, bold=True, wraplength=550, justify='left').grid(
            row=0, column=0, sticky='w', padx=24, pady=(20, 12))
        content = ctk.CTkTextbox(window, fg_color=INPUT, text_color=TEXT, wrap='word', font=(UI_FONT, 13))
        content.grid(row=1, column=0, sticky='nsew', padx=24)
        content.insert('1.0', f'{info}\n\nDosya yolu\n{path or "Dosya yolu bulunamadı"}')
        content.configure(state='disabled')
        actions = ctk.CTkFrame(window, fg_color='transparent')
        actions.grid(row=2, column=0, sticky='ew', padx=24, pady=18)
        # Keep the dialog tied to its own row even if the table selection changes.
        window.copy_path_button = self._button(actions, 'Yolu kopyala', lambda: self._copy_bom_path(path),
                                               icon='copy', width=150, state='normal' if path else 'disabled')
        window.copy_path_button.pack(side='left')
        self._button(actions, 'Kapat', self._close_detail, width=90).pack(side='right')
        window.bind('<Escape>', lambda event: self._close_detail())
        return 'break'

    def _toggle_bom_tree(self, opened):
        if self.busy or self.bom_result is None:
            return
        self.bom_widgets['tree_toggle'] = iter(node.number for node in self.bom_result.tree if node.kind == 'Montaj')
        self.bom_widgets['tree_open'] = opened

    def _toggle_bom_tree_batch(self):
        deadline = time.perf_counter()+.006
        for identifier in self.bom_widgets['tree_toggle']:
            self.bom_widgets['tree'].item(identifier, open=self.bom_widgets['tree_open'])
            if time.perf_counter() >= deadline:
                return
        self.bom_widgets.pop('tree_toggle')

    def _bom_busy(self, value):
        self.busy = value
        for button in self.nav_buttons.values():
            button.configure(state='disabled' if value else 'normal')
        self.bom_widgets['scan'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['excluded'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['search'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['clear_search'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['export'].configure(state='normal' if not value and self.bom_result is not None else 'disabled')
        self.bom_widgets['stop'].configure(state='normal' if value else 'disabled')
        for key in ('expand', 'collapse'):
            self.bom_widgets[key].configure(state='normal' if not value and self.bom_result is not None else 'disabled')
        selection = self.bom_widgets.get('selection')
        self.bom_widgets['details'].configure(state='normal' if selection and not value else 'disabled')
        self.bom_widgets['copy_path'].configure(state='normal' if selection and selection[2] and not value else 'disabled')
        if value:
            self.progress.configure(mode='indeterminate')
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode='determinate')
            self.progress.set(0)

    def _scan_bom(self):
        if self.busy:
            return
        self._clear_bom()
        self.bom_query.set('')
        self.stop_event.clear()
        self._bom_busy(True)
        self.status_label.configure(text='Aktif montaj taranıyor…', text_color=MUTED)
        self.bom_widgets['assembly'].configure(text='Aktif montaj taranıyor…')
        self.bom_widgets['configuration'].configure(text='Montaj ve parça bilgileri okunuyor.')
        include = self.bom_state['include_excluded'].get()
        threading.Thread(target=scan_worker, args=(self.events, self.stop_event),
                         kwargs={'include_excluded': include}, daemon=False).start()

    def _stop_bom(self):
        self.stop_event.set()
        self.bom_widgets['stop'].configure(state='disabled')
        self.status_label.configure(text='İşlem durduruluyor…', text_color=AMBER)

    def _clear_bom(self):
        self.bom_result = None
        self.bom_widgets.pop('render', None)
        self.bom_widgets.pop('tree_toggle', None)
        for key in ('parts', 'tree'):
            table = self.bom_widgets[key]
            # Search may have detached part rows; cached IDs include all of them.
            rows = self.bom_widgets.get('part_ids', ()) if key == 'parts' else table.get_children()
            if rows:
                table.delete(*rows)
        self.bom_widgets['part_ids'] = []
        self.bom_widgets['nodes'] = {}
        self.bom_widgets['counts'].configure(text='Henüz tarama yapılmadı')
        self.bom_widgets['assembly'].configure(text='Montaj seçilmedi')
        self.bom_widgets['configuration'].configure(text='SolidWorks’te ana montajı etkinleştirin.')
        self._update_bom_metrics()
        self._reset_bom_details()
        for key in ('parts', 'tree'):
            self._bom_empty_state(key)

    def _start_bom_render(self, result):
        self._clear_bom()
        self.bom_result = result
        self.bom_widgets['assembly'].configure(text=PureWindowsPath(result.assembly).name)
        self.bom_widgets['configuration'].configure(text=f'Konfigürasyon: {result.configuration}')
        self.bom_widgets['nodes'] = {node.number: node for node in result.tree}
        self._update_bom_metrics()
        for key in ('parts', 'tree'):
            self.bom_widgets[key+'_empty'].place_forget()
        self.bom_widgets['render'] = chain((('part', i, part) for i, part in enumerate(result.parts)),
                                         (('tree', i, node) for i, node in enumerate(result.tree)))
        self.status_label.configure(text='Ürün ağacı hazırlanıyor…', text_color=MUTED)

    def _render_bom_batch(self):
        if self.stop_event.is_set():
            self._clear_bom()
            return self._end_bom(dict(state='cancelled'))
        deadline = time.perf_counter()+.006
        iterator = self.bom_widgets['render']
        for kind, index, value in iterator:
            if kind == 'part':
                iid = f'part_{index}'
                self.bom_widgets['parts'].insert('', 'end', iid=iid,
                    values=(value.name, value.quantity, value.configuration, value.path),
                    tags=('stripe',) if index % 2 else ())
                self.bom_widgets['part_ids'].append(iid)
            else:
                self.bom_widgets['tree'].insert(value.parent, 'end', iid=value.number,
                    text=value.name, values=(value.kind, value.configuration, value.path), open=True,
                    tags=('assembly',) if value.kind == 'Montaj' else ('stripe',) if index % 2 else ())
            if time.perf_counter() >= deadline:
                return
        self.bom_widgets.pop('render')
        self._filter_bom()
        self._bom_empty_state('tree')
        self._end_bom(dict(state='completed'))

    def _filter_bom(self):
        self._update_bom_search_hint()
        result = self.bom_result
        if result is None or 'render' in self.bom_widgets:
            return
        query = self.bom_query.get().casefold().replace('\u0307', '')
        ids = [iid for iid, part in zip(self.bom_widgets['part_ids'], result.parts)
               if query in f'{part.name} {part.configuration} {part.path}'.casefold().replace('\u0307', '')]
        selected = self.bom_widgets['parts'].selection()
        self.bom_widgets['parts'].set_children('', *ids)
        self._update_bom_counts()
        self._bom_empty_state('parts', filtered=bool(query))
        if selected and selected[0] not in ids:
            self.bom_widgets['parts'].selection_remove(*selected)
            self._reset_bom_details()

    def _save_bom(self):
        if self.busy or self.bom_result is None:
            return
        result = self.bom_result
        path = filedialog.asksaveasfilename(parent=self, title='Ürün ağacını Excel dosyasına kaydet',
            initialfile=f'{PureWindowsPath(result.assembly).stem}_BOM.xlsx', defaultextension='.xlsx',
            filetypes=[('Excel çalışma kitabı', '*.xlsx')])
        if not path:
            return
        self.stop_event.clear()
        self._bom_busy(True)
        self.status_label.configure(text='Excel dosyası hazırlanıyor…', text_color=MUTED)
        def write():
            try:
                export_excel(result, path, self.stop_event)
                outcome = dict(state='exported', path=path)
            except Cancelled:
                outcome = dict(state='cancelled')
            except Exception as error:
                outcome = dict(state='error', error=f'Excel kaydedilemedi: {error}')
            self.events.put(('bom_done', outcome))
        threading.Thread(target=write, daemon=False).start()

    def _end_bom(self, outcome):
        self._bom_busy(False)
        state = outcome['state']
        if state == 'error':
            text, color = outcome['error'], RED
        elif state == 'cancelled':
            text, color = 'Durduruldu · Yeni bir Excel dosyası oluşturulmadı.', AMBER
        elif state == 'exported':
            text, color = f'Excel kaydedildi: {outcome["path"]}', GREEN
        else:
            result = self.bom_result
            text, color = (f'Tarama tamamlandı · {result.total_parts} parça adedi · '
                           f'Atlanan bileşen: {result.suppressed} bastırılmış, {result.excluded} BOM dışı.'), GREEN
        if self.bom_result is None and state in ('error', 'cancelled'):
            self.bom_widgets['assembly'].configure(text='Tarama tamamlanamadı' if state == 'error' else 'Tarama durduruldu')
            self.bom_widgets['configuration'].configure(text='Montajı tara düğmesiyle yeniden deneyin.')
        self.status_label.configure(text=text, text_color=color)
        if self.close_pending:
            self._destroy_app()

    def _process_bom_events(self):
        try:
            if 'render' in self.bom_widgets:
                self._render_bom_batch()
            else:
                if 'tree_toggle' in self.bom_widgets:
                    self._toggle_bom_tree_batch()
                for _ in range(100):
                    event, value = self.events.get_nowait()
                    if event == 'bom_phase':
                        self.status_label.configure(text=value, text_color=MUTED)
                    elif event == 'bom_done':
                        if value.get('result') is not None and not self.stop_event.is_set():
                            self._start_bom_render(value['result'])
                        else:
                            if value.get('result') is not None:
                                value = dict(state='cancelled')
                            self._end_bom(value)
                        break
        except queue.Empty:
            pass
        finally:
            if not self._closed:
                active = 'render' in self.bom_widgets or 'tree_toggle' in self.bom_widgets
                self._poll_id = self.after(8 if active else 80, self._process_events)
