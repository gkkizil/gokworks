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
from gui.text import BOM_TITLE
from gui.theme import PANEL, INPUT, BORDER, TEXT, MUTED, ACCENT, GREEN, RED, AMBER, UI_FONT


class BomView:
    def _create_bom_state(self, saved):
        self.bom_state = {'include_excluded': tk.BooleanVar(self, value=saved.get('bom_include_excluded', False) is True)}
        self.bom_query = tk.StringVar(self)
        self.bom_query.trace_add('write', lambda *_: self._filter_bom() if self.mode == 'bom' else None)
        self.bom_result = None
        self.bom_widgets = {}

    def _build_bom_workspace(self):
        self.workspace = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
        self.workspace.grid(row=0, column=1, sticky='nsew', padx=(0, 20), pady=20)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self.workspace, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 12))
        header.grid_columnconfigure(0, weight=1)
        self._label(header, 'GOKWORKS  /  MONTAJ LİSTESİ', 10, MUTED, True).grid(row=0, column=0, sticky='w')
        self._label(header, BOM_TITLE, 24, bold=True).grid(row=1, column=0, sticky='w', pady=(4, 6))
        self._label(header, 'Aktif montajdaki parçalar, adetler ve alt montaj ilişkileri.', 12, MUTED,
                    wraplength=440, justify='left').grid(row=2, column=0, sticky='w')
        actions = ctk.CTkFrame(self.workspace, fg_color='transparent')
        actions.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 12))
        for key, label, command, width, primary in (
                ('scan', 'Montajı tara', self._scan_bom, 150, False),
                ('export', 'Excel’e aktar', self._save_bom, 150, True),
                ('stop', 'Durdur', self._stop_bom, 90, False)):
            button = self._button(actions, label, command, width=width, primary=primary,
                                  icon='download' if key == 'export' else None)
            button.pack(side='left', padx=(0, 8))
            self.bom_widgets[key] = button
        self.bom_widgets['export'].configure(state='disabled')
        self.bom_widgets['stop'].configure(state='disabled')
        stats = self._label(actions, '0 kalem · 0 toplam adet', 12, MUTED)
        stats.pack(side='right')
        self.bom_widgets['counts'] = stats
        options = ctk.CTkFrame(self.workspace, fg_color=INPUT, corner_radius=10)
        options.grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 12))
        options.grid_columnconfigure(0, weight=1)
        self.bom_widgets['assembly'] = self._label(options, 'SolidWorks’te ana montajı etkinleştirin.', 12,
                                                 anchor='w', wraplength=650, justify='left')
        self.bom_widgets['assembly'].grid(row=0, column=0, sticky='ew', padx=14, pady=(10, 6))
        self.bom_widgets['excluded'] = ctk.CTkCheckBox(options, text='BOM dışında bırakılanları da ekle',
            variable=self.bom_state['include_excluded'], text_color=TEXT, fg_color=ACCENT,
            font=(UI_FONT, 12), checkbox_width=18, checkbox_height=18)
        self.bom_widgets['excluded'].grid(row=1, column=0, sticky='w', padx=14, pady=(0, 8))
        self._label(options, 'Parçalar adlarına göre sıralanır: Parça 2, Parça 10. Bastırılmış bileşenler alınmaz; gizli parçalar sayılır.',
                    11, MUTED, wraplength=700, justify='left').grid(row=2, column=0, sticky='w', padx=14, pady=(0, 10))
        tabs = ctk.CTkTabview(self.workspace, fg_color=PANEL, text_color=TEXT,
                            segmented_button_selected_color=('#E7F4EE', '#173A33'))
        tabs.grid(row=3, column=0, sticky='nsew', padx=18)
        self.bom_widgets['tabs'] = tabs
        for label, key in (('Parça listesi', 'parts'), ('Ürün ağacı', 'tree')):
            tab = tabs.add(label)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)
            if key == 'parts':
                entry = ctk.CTkEntry(tab, textvariable=self.bom_query, placeholder_text='Parça adı veya konfigürasyon ara',
                                    fg_color=INPUT, text_color=TEXT, border_color=BORDER, height=34)
                entry.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
                self.bom_widgets['search'] = entry
                table = ttk.Treeview(tab, columns=('name', 'qty', 'config', 'path'), show='headings', style='Gok.Treeview')
                columns = [('name', 'PARÇA ADI', 260), ('qty', 'ADET', 65), ('config', 'KONFİGÜRASYON', 160), ('path', 'DOSYA YOLU', 360)]
            else:
                self._label(tab, 'Alt montajı genişletip içindeki parçaları görebilirsiniz.', 11, MUTED).grid(
                    row=0, column=0, sticky='w', pady=(0, 8))
                table = ttk.Treeview(tab, columns=('kind', 'config', 'path'), show='tree headings', style='Gok.Treeview')
                table.heading('#0', text='MONTAJ / PARÇA')
                table.column('#0', width=330, minwidth=140)
                columns = [('kind', 'TÜR', 90), ('config', 'KONFİGÜRASYON', 160), ('path', 'DOSYA YOLU', 360)]
            for column, title, width in columns:
                table.heading(column, text=title)
                table.column(column, width=width, minwidth=60, stretch=column != 'qty')
            table.grid(row=1, column=0, sticky='nsew')
            vertical = ctk.CTkScrollbar(tab, command=table.yview)
            vertical.grid(row=1, column=1, sticky='ns')
            horizontal = ctk.CTkScrollbar(tab, orientation='horizontal', command=table.xview)
            horizontal.grid(row=2, column=0, sticky='ew')
            table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            self.bom_widgets[key] = table
        self.status_label = self._label(self.workspace, 'Hazır · Montajı tara ile listeyi oluşturun.', 12, MUTED,
                                        anchor='w', wraplength=700, justify='left')
        self.status_label.grid(row=4, column=0, sticky='ew', padx=24, pady=(10, 6))
        self.progress = ctk.CTkProgressBar(self.workspace, height=4, progress_color=ACCENT, fg_color=BORDER)
        self.progress.grid(row=5, column=0, sticky='ew', padx=24, pady=(0, 14))
        self.progress.set(0)
        self._configure_table_style()
        self.workspace.bind('<Configure>', self._resize_pdf_area)

    def _bom_busy(self, value):
        self.busy = value
        for button in self.nav_buttons.values():
            button.configure(state='disabled' if value else 'normal')
        self.bom_widgets['scan'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['excluded'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['search'].configure(state='disabled' if value else 'normal')
        self.bom_widgets['export'].configure(state='normal' if not value and self.bom_result is not None else 'disabled')
        self.bom_widgets['stop'].configure(state='normal' if value else 'disabled')
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
        for key in ('parts', 'tree'):
            table = self.bom_widgets[key]
            # Search may have detached part rows; cached IDs include all of them.
            rows = self.bom_widgets.get('part_ids', ()) if key == 'parts' else table.get_children()
            if rows:
                table.delete(*rows)
        self.bom_widgets['part_ids'] = []
        self.bom_widgets['counts'].configure(text='0 kalem · 0 toplam adet')

    def _start_bom_render(self, result):
        self._clear_bom()
        self.bom_result = result
        self.bom_widgets['assembly'].configure(text=f'{PureWindowsPath(result.assembly).name} · Konfigürasyon: {result.configuration}')
        self.bom_widgets['counts'].configure(text=f'{len(result.parts)} kalem · {result.total_parts} toplam adet')
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
                    values=(value.name, value.quantity, value.configuration, value.path))
                self.bom_widgets['part_ids'].append(iid)
            else:
                self.bom_widgets['tree'].insert(value.parent, 'end', iid=value.number,
                    text=f'{value.name} · {value.instance}', values=(value.kind, value.configuration, value.path), open=True)
            if time.perf_counter() >= deadline:
                return
        self.bom_widgets.pop('render')
        self._filter_bom()
        self._end_bom(dict(state='completed'))

    def _filter_bom(self):
        result = self.bom_result
        if result is None or 'render' in self.bom_widgets:
            return
        query = self.bom_query.get().casefold().replace('\u0307', '')
        ids = [iid for iid, part in zip(self.bom_widgets['part_ids'], result.parts)
               if query in f'{part.name} {part.configuration} {part.path}'.casefold().replace('\u0307', '')]
        self.bom_widgets['parts'].set_children('', *ids)

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
                           f'Atlanan dal: {result.suppressed} bastırılmış, {result.excluded} BOM dışı.'), GREEN
        self.status_label.configure(text=text, text_color=color)
        if self.close_pending:
            self._destroy_app()

    def _process_bom_events(self):
        try:
            if 'render' in self.bom_widgets:
                self._render_bom_batch()
            else:
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
                self._poll_id = self.after(8 if 'render' in self.bom_widgets else 80, self._process_events)
