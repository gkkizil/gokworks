"""Naming preview and worker controls for reference-preserving packages."""

from pathlib import Path, PureWindowsPath
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, simpledialog, ttk

import customtkinter as ctk

from gui.rendering import configure_changed, hide_grid
from gui.theme import PANEL, INPUT, BORDER, TEXT, MUTED, RED, AMBER, SUCCESS, UI_FONT
from naming.exporter import NameCollision, Rules, plan_names, worker
from naming.hierarchy import document_rows


class NamingView:
    def _create_naming_state(self, saved):
        defaults = dict(parent='', package='Yeni-paket', mode='Ön / son ek', prefix='', suffix='',
                        find='', replacement='', start='1', digits='3',
                        source_mode='Aktif montaj', source_folder='', source_file='')
        self.naming_state = {key: tk.StringVar(self, value=str(saved.get('naming_'+key, value)))
                             for key, value in defaults.items()}
        if self.naming_state['mode'].get() not in ('Ön / son ek', 'Numaralı'):
            self.naming_state['mode'].set('Ön / son ek')
        if self.naming_state['source_mode'].get() not in ('Aktif montaj', 'Dosyadan'):
            self.naming_state['source_mode'].set('Aktif montaj')
        self.naming_snapshot = None
        self.naming_plan = ()
        self.naming_overrides = {}
        self.naming_widgets = {}
        for key, value in self.naming_state.items():
            if key.startswith('source_'):
                value.trace_add('write', lambda *_, key=key: self._naming_source_changed(key)
                                if self.mode == 'naming' else None)
            else:
                value.trace_add('write', lambda *_: self._schedule_naming_preview() if self.mode == 'naming' else None)

    def _build_naming_workspace(self):
        self.workspace = self._workspace_shell()
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        _, actions, labels = self._page_header('İsimlendirme aracı',
            'Montaj ve teknik resim bağlantılarını koruyarak yeni bir paket oluşturun.',
            'AKTARIM / İSİMLENDİRME', 'copy')
        widgets = self.naming_widgets
        widgets.update(labels)
        widgets['scan'] = self._button(actions, 'Dosyaları oku', self._scan_naming, width=132, icon='search')
        widgets['scan'].pack(side='left', padx=(0, 6))
        widgets['stop'] = self._button(actions, 'Durdur', self._stop_naming, width=78, state='disabled')
        widgets['stop'].pack(side='left')
        source = ctk.CTkFrame(self.workspace, fg_color=PANEL, border_width=1,
                            border_color=BORDER, corner_radius=16)
        source.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 8))
        source.grid_columnconfigure((0, 1), weight=1, uniform='naming_source')
        widgets['source'] = self._label(source, 'Kaynak: '+self.naming_state['source_mode'].get(),
                                        12, MUTED, anchor='w', width=1, wraplength=600)
        widgets['source'].grid(row=0, column=0, sticky='ew', padx=(14, 4), pady=(8, 4))
        widgets['active_source'] = self._button(source, 'Aktif montajı kullan', self._use_active_naming_assembly,
                                                width=158, icon='layers')
        widgets['active_source'].configure(height=30)
        widgets['active_source'].grid(row=0, column=1, sticky='e', padx=(4, 14), pady=(8, 4))
        for column, key, title, button_key, button_text, command in (
            (0, 'source_folder', 'Kaynak klasör', 'source_browse', 'Klasör seç', self._pick_naming_source_folder),
            (1, 'source_file', 'Kaynak montaj / dosya', 'source_pick', 'Dosya seç', self._pick_naming_source_file),
        ):
            holder = ctk.CTkFrame(source, fg_color='transparent')
            holder.grid(row=1, column=column, sticky='ew', padx=(14 if column == 0 else 4, 14 if column == 1 else 4), pady=(0, 10))
            holder.grid_columnconfigure(0, weight=1)
            self._label(holder, title, 11, MUTED).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))
            widgets[key] = ctk.CTkEntry(holder, textvariable=self.naming_state[key], height=32,
                                        width=1, font=(UI_FONT, 12))
            widgets[key].grid(row=1, column=0, sticky='ew', padx=(0, 5))
            widgets[button_key] = self._button(holder, button_text, command, width=86,
                                               icon='folder' if column == 0 else 'file')
            widgets[button_key].configure(height=32)
            widgets[button_key].grid(row=1, column=1)
        form = ctk.CTkScrollableFrame(self.workspace, fg_color=PANEL, border_width=1,
                                      border_color=BORDER, corner_radius=16, height=245)
        widgets['form'] = form
        # CTk's scrollbar otherwise requests a 200 px minimum viewport.
        form._scrollbar.configure(height=0)
        form.grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 12))
        for col in range(4):
            form.grid_columnconfigure(col, weight=1, uniform='naming_form')
        output = ctk.CTkFrame(form, fg_color='transparent')
        output.grid(row=1, column=0, columnspan=3, sticky='ew', padx=(14, 8), pady=(0, 8))
        output.grid_columnconfigure(0, weight=1)
        self._label(output, 'Çıktı konumu', 11, MUTED).grid(row=0, column=0, sticky='w')
        widgets['parent'] = ctk.CTkEntry(output, textvariable=self.naming_state['parent'], height=36,
                                        width=1, font=(UI_FONT, 12))
        widgets['parent'].grid(row=1, column=0, sticky='ew', padx=(0, 6))
        widgets['browse'] = self._button(output, 'Klasör seç', self._pick_naming_folder, width=100, icon='folder')
        widgets['browse'].grid(row=1, column=1)
        def field(key, label, row, col):
            holder = ctk.CTkFrame(form, fg_color='transparent')
            holder.grid(row=row, column=col, sticky='ew', padx=(14 if col == 0 else 4, 14 if col == 3 else 4), pady=(0, 8))
            holder.grid_columnconfigure(0, weight=1)
            self._label(holder, label, 11, MUTED).grid(row=0, column=0, sticky='w')
            control = (ctk.CTkOptionMenu(holder, variable=self.naming_state[key], values=['Ön / son ek', 'Numaralı'],
                                         height=36, width=1, dynamic_resizing=False, font=(UI_FONT, 12)) if key == 'mode' else
                       ctk.CTkEntry(holder, textvariable=self.naming_state[key], height=36, width=1, font=(UI_FONT, 12)))
            control.grid(row=1, column=0, sticky='ew')
            widgets[key] = control
        field('package', 'Yeni paket klasörü', 1, 3)
        for key, label, col in (('mode', 'İsimlendirme', 0), ('prefix', 'Ön ek', 1), ('suffix', 'Son ek', 2)):
            field(key, label, 2, col)
        numbers = ctk.CTkFrame(form, fg_color='transparent')
        numbers.grid(row=2, column=3, sticky='ew', padx=(4, 14), pady=(0, 8))
        for col, key, label in ((0, 'start', 'Başlangıç'), (1, 'digits', 'Basamak')):
            numbers.grid_columnconfigure(col, weight=1)
            self._label(numbers, label, 11, MUTED).grid(row=0, column=col, sticky='w')
            control = ctk.CTkEntry(numbers, textvariable=self.naming_state[key], width=50, height=36, font=(UI_FONT, 12))
            control.grid(row=1, column=col, sticky='ew', padx=(0, 4) if col == 0 else (4, 0))
            widgets[key] = control
        field('find', 'Bul', 3, 0)
        field('replacement', 'Yerine yaz', 3, 1)
        widgets['hint'] = self._label(form, 'Teknik resimler, bastırılmış parçalar ve Toolbox dahil edilir.\nYeni paket ayrı klasöre kaydedilir.',
                                      11, MUTED, wraplength=310, width=1, justify='left', anchor='w')
        widgets['hint'].grid(row=3, column=2, columnspan=2, sticky='ew', padx=(8, 14), pady=(0, 10))

        card = ctk.CTkFrame(self.workspace, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=16)
        card.grid(row=3, column=0, sticky='nsew', padx=24)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(card, fg_color='transparent')
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', padx=14, pady=10)
        toolbar.grid_columnconfigure(0, weight=1)
        widgets['summary'] = self._label(toolbar, 'Dosyaları okuyun; eski ve yeni adları burada karşılaştırın.', 11, MUTED,
                                          anchor='w', width=1, wraplength=420)
        widgets['summary'].grid(row=0, column=0, sticky='ew')
        widgets['edit'] = self._button(toolbar, 'Seçili adı düzenle', self._edit_naming_row, width=140, state='disabled')
        widgets['edit'].grid(row=0, column=1, padx=(6, 0))
        widgets['reset'] = self._button(toolbar, 'Elle girilenleri sıfırla', self._reset_naming_overrides, width=150)
        widgets['reset'].grid(row=0, column=2, padx=(6, 0))
        table = ttk.Treeview(card, columns=('new', 'kind'), show='tree headings', selectmode='browse', style='Gok.Treeview')
        for key, title, width in (('#0', 'Montaj / mevcut dosya adı', 330), ('new', 'Yeni dosya adı', 300), ('kind', 'Tür', 150)):
            table.heading(key, text=title, anchor='w')
            table.column(key, width=width, minwidth=100, stretch=key != 'kind')
        table.grid(row=1, column=0, sticky='nsew', padx=(12, 0))
        bar = ctk.CTkScrollbar(card, command=table.yview, width=10, fg_color=PANEL, button_color=BORDER)
        bar.grid(row=1, column=1, sticky='ns', padx=(0, 10))
        hbar = ctk.CTkScrollbar(card, orientation='horizontal', command=table.xview, height=10, fg_color=PANEL, button_color=BORDER)
        hbar.grid(row=2, column=0, sticky='ew', padx=12, pady=(0, 8))
        table.configure(yscrollcommand=bar.set, xscrollcommand=hbar.set)
        table.bind('<Double-1>', self._double_click_naming_row)
        table.bind('<Return>', lambda event: self._edit_naming_row())
        table.bind('<<TreeviewSelect>>', lambda event: self._naming_buttons())
        widgets['table'] = table
        footer = ctk.CTkFrame(self.workspace, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='ew', padx=24, pady=(10, 6))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = self._label(footer, 'Hazır · Dosyaları oku ile başlayın.', 11, MUTED,
                                        anchor='w', width=1, wraplength=460, justify='left')
        self.status_label.grid(row=0, column=0, sticky='ew', padx=(0, 12))
        widgets['status'] = self.status_label
        widgets['save'] = self._button(footer, 'Paketi oluştur', self._save_naming, primary=True, icon='copy', width=158, state='disabled')
        widgets['save'].grid(row=0, column=1)
        self.progress = ctk.CTkProgressBar(self.workspace, height=3)
        self.progress.grid(row=5, column=0, sticky='ew', padx=24, pady=(0, 12))
        self.progress.set(0)
        self._configure_table_style()
        self.workspace.bind('<Configure>', self._resize_pdf_area)
        self._resize_naming_workspace()

    def _resize_naming_workspace(self):
        self._layout_fit_id = None
        if self._closed or self.workspace.winfo_width() < 100:
            return
        widgets = self.naming_widgets
        scale = self.workspace._get_widget_scaling()
        width = self.workspace.winfo_width()/scale
        compact = self.workspace.winfo_height()/scale < 740
        if widgets.get('compact') != compact:
            widgets['form'].configure(height=80 if compact else 200)
            for key in ('edit', 'reset'):
                widgets[key].configure(height=30 if compact else 38)
            widgets['save'].configure(height=32 if compact else 38)
            for key, row in (('eyebrow', 0), ('subtitle', 2)):
                if compact:
                    hide_grid(widgets[key])
                else:
                    widgets[key].grid(row=row, column=1, sticky='ew' if row == 2 else 'w')
            widgets['compact'] = compact
        for widget, wrap in ((widgets['source'], max(150, (width-76)/2)), (widgets['status'], max(240, width-235)),
                             (widgets['summary'], max(150, width-390)), (widgets['hint'], max(180, (width-76)/2))):
            configure_changed(widget, wraplength=wrap)
        style_key = ctk.get_appearance_mode(), scale
        if getattr(self, '_table_style_key', None) != style_key:
            self._configure_table_style()

    def _pick_naming_folder(self):
        selected = filedialog.askdirectory(parent=self, title='Yeni paketin oluşturulacağı üst klasör')
        if selected:
            self.naming_state['parent'].set(selected)

    def _clear_naming_preview(self):
        widgets = self.naming_widgets
        for key in ('preview_id', 'render_id'):
            timer = widgets.pop(key, None)
            if timer is not None:
                self.after_cancel(timer)
        widgets.pop('render', None)
        widgets.pop('drawn_plan', None)
        self.naming_snapshot = None
        self.naming_plan = ()
        self.naming_overrides.clear()
        widgets['valid'] = False
        if 'table' in widgets:
            widgets['table'].delete(*widgets['table'].get_children())
            widgets['summary'].configure(text='Kaynağı seçip Dosyaları oku ile montaj ağacını yükleyin.')
            self._naming_buttons()

    def _naming_source_changed(self, key):
        widgets = self.naming_widgets
        if widgets.get('changing_source'):
            return
        if key != 'source_mode':
            widgets['changing_source'] = True
            self.naming_state['source_mode'].set('Dosyadan')
            if key == 'source_folder':
                self.naming_state['source_file'].set('')
            widgets['changing_source'] = False
        self._clear_naming_preview()
        if 'source' in widgets:
            widgets['source'].configure(text='Kaynak: '+self.naming_state['source_mode'].get())
        if 'status' in widgets:
            widgets['status'].configure(text='Kaynak değişti · Ana montajı/dosyayı seçip Dosyaları oku kullanın.', text_color=MUTED)

    def _pick_naming_source_folder(self):
        if self.busy:
            return
        selected = filedialog.askdirectory(parent=self, title='İsimlendirilecek projenin kaynak klasörü',
                                           initialdir=self.naming_state['source_folder'].get() or None)
        if selected:
            self.naming_state['source_folder'].set(selected)
            # Let the native file picker choose the root explicitly; every
            # assembly in this folder may belong to a different project.
            self._pick_naming_source_file()

    def _pick_naming_source_file(self):
        if self.busy:
            return
        selected = filedialog.askopenfilename(parent=self, title='Kaynak ana montajı veya SolidWorks dosyasını seçin',
            initialdir=self.naming_state['source_folder'].get() or None,
            filetypes=[('SolidWorks dosyaları', '*.sldasm *.SLDASM *.sldprt *.SLDPRT *.slddrw *.SLDDRW'),
                       ('Montaj', '*.sldasm *.SLDASM'), ('Parça', '*.sldprt *.SLDPRT'),
                       ('Teknik resim', '*.slddrw *.SLDDRW')])
        if selected:
            self.naming_state['source_folder'].set(str(Path(selected).parent))
            self.naming_state['source_file'].set(selected)

    def _use_active_naming_assembly(self):
        if self.busy:
            return
        widgets = self.naming_widgets
        widgets['changing_source'] = True
        self.naming_state['source_mode'].set('Aktif montaj')
        self.naming_state['source_folder'].set('')
        self.naming_state['source_file'].set('')
        widgets['changing_source'] = False
        self._scan_naming()

    def _schedule_naming_preview(self):
        widgets = self.naming_widgets
        previous = widgets.pop('preview_id', None)
        if previous is not None:
            self.after_cancel(previous)
        widgets['valid'] = False
        self._naming_buttons()
        widgets['preview_id'] = self.after(150, self._update_naming_preview)

    def _update_naming_preview(self):
        widgets = self.naming_widgets
        pending = widgets.pop('preview_id', None)
        if pending is not None:
            self.after_cancel(pending)
        if self.naming_snapshot is None or self.busy:
            return
        try:
            from naming.exporter import valid_stem
            values = {key: value.get() for key, value in self.naming_state.items()}
            valid_stem(values['package'])
            numbered = values['mode'] == 'Numaralı'
            rules = Rules(values['prefix'], values['suffix'], values['find'], values['replacement'], numbered,
                          int(values['start']) if numbered else 1, int(values['digits']) if numbered else 3)
            destination = Path(values['parent'])/values['package']
            self.naming_plan = plan_names(self.naming_snapshot, destination, rules, self.naming_overrides)
            widgets['valid'] = bool(values['parent'] and Path(values['parent']).is_dir() and not destination.exists())
            draws = sum(doc.kind == 'Teknik resim' for doc in self.naming_snapshot.documents)
            widgets['summary'].configure(text=f'{len(self.naming_plan)} farklı dosya · {draws} teknik resim · Montajları oklarla açıp kapatın.')
            widgets['status'].configure(text='İsimleri kontrol edin, ardından yeni paketi oluşturun.' if widgets['valid'] else
                                          'Çıktı konumunu ve kullanılmamış bir paket klasörü adı seçin.', text_color=MUTED)
        except NameCollision as error:
            self.naming_plan = plan_names(self.naming_snapshot, destination, rules, self.naming_overrides, allow_collisions=True)
            widgets['valid'] = False
            widgets['status'].configure(text=str(error), text_color=RED)
            widgets['summary'].configure(text='Çakışan adları düzenleyin; aktarım şu anda engellendi.')
        except (ValueError, OSError) as error:
            self.naming_plan = ()
            widgets['valid'] = False
            widgets['status'].configure(text=str(error), text_color=RED)
        if widgets.get('drawn_plan') == self.naming_plan:
            self._naming_buttons()
            return
        widgets['drawn_plan'] = self.naming_plan
        previous = widgets.pop('render_id', None)
        if previous is not None:
            self.after_cancel(previous)
        table = widgets['table']
        if widgets.get('hierarchy_snapshot') is not self.naming_snapshot:
            widgets['hierarchy_snapshot'] = self.naming_snapshot
            widgets['hierarchy_rows'] = document_rows(self.naming_snapshot)
        rows = widgets['hierarchy_rows'] if self.naming_plan else ()
        widgets['row_indices'] = {row.iid: row.index for row in rows}
        # Updating names in place preserves collapsed branches, selection and scroll.
        widgets['render'] = iter(rows)
        if not rows:
            table.delete(*table.get_children())
        self._paint_naming_rows()
        self._naming_buttons()

    def _paint_naming_rows(self):
        if self._closed:
            return
        widgets = self.naming_widgets
        widgets.pop('render_id', None)
        deadline = time.perf_counter()+.006
        for row in widgets['render']:
            entry = self.naming_plan[row.index]
            kind = self.naming_snapshot.documents[row.index].kind
            if row.shared:
                kind += ' · Ortak dosya'
            elif row.reference:
                kind += ' · Referans'
            table = widgets['table']
            content = dict(text=PureWindowsPath(entry.source).name,
                           values=(PureWindowsPath(entry.destination).name, kind))
            if table.exists(row.iid):
                table.item(row.iid, **content)
            else:
                table.insert(row.parent, 'end', iid=row.iid, open=True, **content)
            if time.perf_counter() >= deadline:
                widgets['render_id'] = self.after(8, self._paint_naming_rows)
                return
        widgets.pop('render')
        self._naming_buttons()

    def _double_click_naming_row(self, event):
        table = self.naming_widgets['table']
        if 'indicator' in table.identify_element(event.x, event.y):
            return
        row = table.identify_row(event.y)
        if row:
            table.selection_set(row)
            self._edit_naming_row()
        return 'break'

    def _edit_naming_row(self):
        if self.busy or not self.naming_plan or 'render' in self.naming_widgets:
            return
        rows = self.naming_widgets['table'].selection()
        if not rows:
            return
        index = self.naming_widgets['row_indices'][rows[0]]
        entry = self.naming_plan[index]
        doc = self.naming_snapshot.documents[index]
        if doc.kind == 'Ek dosya':
            return
        name = simpledialog.askstring('Dosya adını düzenle',
            f'{entry.source}\nYeni adı uzantısız yazın:',
            initialvalue=PureWindowsPath(entry.destination).stem, parent=self)
        if name is not None:
            from naming.exporter import valid_stem
            try:
                valid_stem(name)
            except ValueError as error:
                self.naming_widgets['status'].configure(text=str(error), text_color=RED)
                return
            self.naming_overrides[entry.source] = name
            self._update_naming_preview()

    def _reset_naming_overrides(self):
        if not self.busy:
            self.naming_overrides.clear()
            self._update_naming_preview()

    def _naming_buttons(self):
        widgets = self.naming_widgets
        if 'save' not in widgets:
            return
        ready = not self.busy and bool(self.naming_plan) and widgets.get('valid') and 'render' not in widgets
        widgets['save'].configure(state='normal' if ready else 'disabled')
        rows = widgets['table'].selection()
        can_edit = (not self.busy and bool(self.naming_plan) and bool(rows) and
                    rows[0] in widgets.get('row_indices', {}) and
                    self.naming_snapshot.documents[widgets['row_indices'][rows[0]]].kind != 'Ek dosya')
        widgets['edit'].configure(state='normal' if can_edit else 'disabled')

    def _naming_busy(self, value):
        self.busy = value
        for button in self.nav_buttons.values():
            button.configure(state='disabled' if value else 'normal')
        for key in ('scan', 'browse', 'reset', 'active_source', 'source_browse', 'source_pick', *self.naming_state):
            if key in self.naming_widgets:
                self.naming_widgets[key].configure(state='disabled' if value else 'normal')
        self.naming_widgets['stop'].configure(state='normal' if value else 'disabled')
        self._naming_buttons()
        if value:
            self.progress.configure(mode='indeterminate')
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode='determinate')
            self.progress.set(0)

    def _scan_naming(self):
        if self.busy:
            return
        self._clear_naming_preview()
        explicit = self.naming_state['source_mode'].get() == 'Dosyadan'
        source_path = self.naming_state['source_file'].get().strip() if explicit else None
        if explicit and not source_path:
            self.naming_widgets['status'].configure(text='Kaynak klasördeki ana montajı veya dosyayı seçin.', text_color=RED)
            return
        self.naming_widgets['source'].configure(text='SolidWorks dosyaları ve teknik resimler okunuyor…')
        self._save_preferences()
        self.stop_event.clear()
        self._naming_busy(True)
        threading.Thread(target=worker, args=(self.events, self.stop_event),
                         kwargs=dict(source_path=source_path, require_assembly=not explicit), daemon=False).start()

    def _save_naming(self):
        if self.busy:
            return
        self._update_naming_preview()
        if not self.naming_widgets.get('valid') or not self.naming_plan or 'render' in self.naming_widgets:
            return
        self._save_preferences()
        self.stop_event.clear()
        self._naming_busy(True)
        destination = str(Path(self.naming_state['parent'].get())/self.naming_state['package'].get())
        threading.Thread(target=worker, args=(self.events, self.stop_event),
                         kwargs=dict(operation='save', snapshot=self.naming_snapshot, entries=self.naming_plan,
                                     destination=destination), daemon=False).start()

    def _stop_naming(self):
        self.stop_event.set()
        self.naming_widgets['stop'].configure(state='disabled')
        self.naming_widgets['status'].configure(text='SolidWorks işlemi tamamlanınca durdurulacak…', text_color=AMBER)

    def _process_naming_events(self):
        try:
            for _ in range(100):
                event, value = self.events.get_nowait()
                if event == 'naming_phase':
                    self.naming_widgets['status'].configure(text=value, text_color=MUTED)
                elif event == 'naming_done':
                    self._naming_busy(False)
                    if value['state'] == 'scanned' and not self.stop_event.is_set():
                        self.naming_snapshot = value['snapshot']
                        self.naming_widgets['source'].configure(text=f'{self.naming_state["source_mode"].get()}: {PureWindowsPath(self.naming_snapshot.root).name}')
                        self.naming_widgets['changing_source'] = True
                        root = self.naming_snapshot.root
                        self.naming_state['source_folder'].set(str(Path(root).parent) if Path(root).is_absolute()
                                                              else str(PureWindowsPath(root).parent))
                        self.naming_state['source_file'].set(self.naming_snapshot.root)
                        self.naming_widgets['changing_source'] = False
                        self._update_naming_preview()
                    elif value['state'] == 'saved':
                        self.naming_widgets['valid'] = False
                        self.naming_widgets['status'].configure(text=f'Paket oluşturuldu; dosya bağlantıları doğrulandı.\n{value["report"]["root"]}', text_color=SUCCESS)
                    else:
                        self.naming_widgets['status'].configure(text=value.get('error', 'Durduruldu · Tamamlanmamış paket kullanılmaz.'),
                                                               text_color=RED if value['state'] == 'error' else AMBER)
                    self._naming_buttons()
                    if self.close_pending:
                        self._destroy_app()
                    break
        except queue.Empty:
            pass
        finally:
            if not self._closed:
                self._poll_id = self.after(80, self._process_events)
