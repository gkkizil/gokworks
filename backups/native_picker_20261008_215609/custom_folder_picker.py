"""Klasörlerin içindeki dosyaları da gösteren karanlık klasör seçici."""

from dataclasses import dataclass
import os
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

BG, PANEL, INPUT = "#101316", "#191E23", "#11161B"
TEXT, MUTED, ACCENT, RED = "#EDF2F5", "#95A3AE", "#4AD7B3", "#F1848F"


@dataclass(frozen=True)
class FolderEntry:
    path: Path
    is_directory: bool
    size: int | None


def list_directory(folder):
    entries = []
    with os.scandir(folder) as iterator:
        for entry in iterator:
            try:
                is_directory = entry.is_dir()
                size = None if is_directory else entry.stat().st_size
                entries.append(FolderEntry(Path(entry.path), is_directory, size))
            except OSError:
                entries.append(FolderEntry(Path(entry.path), False, None))
    return sorted(entries, key=lambda entry: (not entry.is_directory, entry.path.name.casefold()))


def initial_directory(value):
    if value:
        try:
            path = Path(os.path.expandvars(value)).expanduser()
            if path.is_file():
                return path.parent.resolve()
            for candidate in (path, *path.parents):
                if candidate.is_dir():
                    return candidate.resolve()
        except (OSError, ValueError):
            pass
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


def readable_size(size):
    if size is None:
        return "—"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class DirectoryPicker(ctk.CTkToplevel):
    def __init__(self, parent, title, initial_dir="", relevant_suffix=".slddrw"):
        super().__init__(parent)
        self.title(title)
        self.geometry("800x560")
        self.minsize(660, 440)
        self.configure(fg_color=BG)
        self.transient(parent)
        self.result = None
        self.current_directory = initial_directory(initial_dir)
        self.selected_directory = self.current_directory
        self.relevant_suffix = relevant_suffix.casefold()
        self.address = tk.StringVar(self, value=str(self.current_directory))
        self.items = {}
        self.events = queue.Queue()
        self.generation = 0
        self.closed = False
        self.poll_id = None
        self._build(title)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda event: self._cancel())
        self.bind("<Alt-Up>", lambda event: self._navigate(self.current_directory.parent))
        self.after(0, lambda: self._navigate(self.current_directory))
        self.poll_id = self.after(60, self._poll)

    def _button(self, parent, text, command, primary=False, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=7,
                             fg_color=ACCENT if primary else "#253039",
                             hover_color="#70E7C7" if primary else "#34434F",
                             text_color="#10231D" if primary else TEXT,
                             font=("Segoe UI", 12), **kwargs)

    def _build(self, title):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 21, "bold"), text_color=TEXT).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 3))
        ctk.CTkLabel(self, text="Dosyalar görünür. Seçim, dosyanın bulunduğu klasördür.",
                     font=("Segoe UI", 12), text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))
        navigation = ctk.CTkFrame(self, fg_color="transparent")
        navigation.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        navigation.grid_columnconfigure(1, weight=1)
        self._button(navigation, "Üst", lambda: self._navigate(self.current_directory.parent), width=50).grid(
            row=0, column=0, padx=(0, 8))
        entry = ctk.CTkEntry(navigation, textvariable=self.address, height=36, fg_color=INPUT, border_color="#2D353D")
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda event: self._navigate(self.address.get()))
        self._button(navigation, "Aç", lambda: self._navigate(self.address.get()), width=50).grid(
            row=0, column=2, padx=(8, 0))

        middle = ctk.CTkFrame(self, fg_color="transparent")
        middle.grid(row=3, column=0, sticky="nsew", padx=20)
        middle.grid_columnconfigure(1, weight=1)
        middle.grid_rowconfigure(0, weight=1)
        shortcuts = ctk.CTkFrame(middle, fg_color=PANEL, width=128)
        shortcuts.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        for row, (name, path) in enumerate((("Masaüstü", Path.home() / "Desktop"),
                                            ("Belgeler", Path.home() / "Documents"), ("Kullanıcı", Path.home()),
                                            ("Disk kökü", Path(self.current_directory.anchor)))):
            self._button(shortcuts, name, lambda p=path: self._navigate(p), width=112).grid(
                row=row, column=0, padx=8, pady=(12 if row == 0 else 6, 0))
        table_frame = ctk.CTkFrame(middle, fg_color=INPUT)
        table_frame.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Folder.Treeview", background=INPUT, fieldbackground=INPUT, foreground=TEXT,
                         rowheight=29, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Folder.Treeview.Heading", background="#253039", foreground=MUTED,
                         relief="flat", padding=(7, 8), font=("Segoe UI", 10, "bold"))
        style.map("Folder.Treeview", background=[("selected", "#284B40")], foreground=[("selected", "white")])
        style.map("Folder.Treeview.Heading", background=[("active", "#30434D")])
        self.table = ttk.Treeview(table_frame, columns=("name", "type", "size"), show="headings",
                                  selectmode="browse", style="Folder.Treeview")
        for column, caption, width in (("name", "AD", 290), ("type", "TÜR", 95), ("size", "BOYUT", 80)):
            self.table.heading(column, text=caption)
            self.table.column(column, width=width, minwidth=60, stretch=column == "name")
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ctk.CTkScrollbar(table_frame, command=self.table.yview, fg_color=INPUT)
        scroll.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        horizontal = ctk.CTkScrollbar(table_frame, orientation="horizontal", command=self.table.xview, fg_color=INPUT)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(xscrollcommand=horizontal.set)
        self.table.tag_configure("directory", foreground=TEXT)
        self.table.tag_configure("relevant", foreground=ACCENT)
        self.table.tag_configure("file", foreground=MUTED)
        self.table.bind("<<TreeviewSelect>>", self._selection_changed)
        self.table.bind("<Double-1>", self._double_click)
        self.table.bind("<Return>", self._enter_selection)
        self.status = ctk.CTkLabel(self, text="Klasör okunuyor…", text_color=MUTED, font=("Segoe UI", 11), anchor="w")
        self.status.grid(row=4, column=0, sticky="ew", padx=20, pady=(9, 4))
        self.chosen = ctk.CTkLabel(self, text=str(self.selected_directory), text_color=TEXT,
                                  font=("Segoe UI", 11), anchor="w", wraplength=740, justify="left")
        self.chosen.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 8))
        self.bind("<Configure>", lambda event: self.chosen.configure(wraplength=max(400, self.winfo_width() - 40))
                  if event.widget is self else None)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 18))
        footer.grid_columnconfigure(1, weight=1)
        self._button(footer, "Yeni klasör", self._new_folder, width=108).grid(row=0, column=0)
        self._button(footer, "İptal", self._cancel, width=80).grid(row=0, column=2, padx=(8, 8))
        self.select_button = self._button(footer, "Klasörü seç", self._accept, primary=True, width=135)
        self.select_button.grid(row=0, column=3)

    def _navigate(self, value):
        try:
            path = Path(os.path.expandvars(str(value))).expanduser()
            if path.is_file():
                path = path.parent
            if not path.is_dir():
                raise ValueError("Klasör bulunamadı.")
            path = path.resolve()
        except (OSError, ValueError) as error:
            self.status.configure(text=str(error), text_color=RED)
            return
        self.generation += 1
        generation = self.generation
        self.current_directory = self.selected_directory = path
        self.address.set(str(path))
        self.chosen.configure(text=str(path))
        self.table.delete(*self.table.get_children())
        self.items.clear()
        self.status.configure(text="Klasör okunuyor…", text_color=MUTED)
        self.select_button.configure(state="disabled")
        def load():
            try:
                self.events.put((generation, list_directory(path), None))
            except OSError as error:
                self.events.put((generation, [], str(error)))
        threading.Thread(target=load, daemon=True).start()

    def _show_entries(self, entries):
        self.table.delete(*self.table.get_children())
        self.items.clear()
        for index, entry in enumerate(entries):
            row_id = f"entry_{index}"
            self.items[row_id] = entry
            relevant = entry.path.suffix.casefold() == self.relevant_suffix
            kind = "Klasör" if entry.is_directory else entry.path.suffix.lstrip(".").upper() or "Dosya"
            tag = "directory" if entry.is_directory else "relevant" if relevant else "file"
            self.table.insert("", "end", iid=row_id,
                               values=(entry.path.name, kind, "—" if entry.is_directory else readable_size(entry.size)),
                               tags=(tag,))
        directories = sum(entry.is_directory for entry in entries)
        relevant = sum(not entry.is_directory and entry.path.suffix.casefold() == self.relevant_suffix for entry in entries)
        self.status.configure(text=f"{directories} klasör · {len(entries) - directories} dosya · {relevant} {self.relevant_suffix.upper()}", text_color=MUTED)
        self.select_button.configure(state="normal")

    def _poll(self):
        try:
            while True:
                generation, entries, error = self.events.get_nowait()
                if generation != self.generation:
                    continue
                if error:
                    self.status.configure(text=error, text_color=RED)
                    self.select_button.configure(state="disabled")
                else:
                    self._show_entries(entries)
        except queue.Empty:
            pass
        if not self.closed:
            self.poll_id = self.after(60, self._poll)

    def _selection_changed(self, event=None):
        selected = self.table.selection()
        entry = self.items.get(selected[0]) if selected else None
        self.selected_directory = entry.path if entry is not None and entry.is_directory else self.current_directory
        self.chosen.configure(text=str(self.selected_directory))

    def _double_click(self, event):
        entry = self.items.get(self.table.identify_row(event.y))
        if entry is not None and entry.is_directory:
            self._navigate(entry.path)

    def _enter_selection(self, event=None):
        selected = self.table.selection()
        entry = self.items.get(selected[0]) if selected else None
        if entry is not None and entry.is_directory:
            self._navigate(entry.path)
        else:
            self._accept()
        return "break"

    def _new_folder(self):
        dialog = ctk.CTkInputDialog(title="Yeni klasör", text="Klasör adı:")
        name = dialog.get_input()
        self.grab_set()
        if name is None:
            return
        name = name.strip()
        if not name or name in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith((" ", ".")):
            self.status.configure(text="Geçerli bir klasör adı yaz.", text_color=RED)
            return
        try:
            path = self.current_directory / name
            path.mkdir()
            self._navigate(path)
        except OSError as error:
            self.status.configure(text=f"Klasör oluşturulamadı: {error}", text_color=RED)

    def _accept(self):
        if self.selected_directory.is_dir():
            self.result = str(self.selected_directory)
            self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        self.closed = True
        if self.poll_id is not None:
            self.after_cancel(self.poll_id)
        self.grab_release()
        self.destroy()


def choose_directory(parent, title, initial_dir="", relevant_suffix=".slddrw"):
    picker = DirectoryPicker(parent, title, initial_dir, relevant_suffix)
    picker.wait_visibility()
    picker.grab_set()
    picker.focus_set()
    parent.wait_window(picker)
    return picker.result
