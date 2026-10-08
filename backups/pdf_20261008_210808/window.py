"""GOKWORKS için sade, karanlık PDF aktarım arayüzü."""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from pdf.exporter import export_drawings


BG = "#101216"
PANEL = "#181B22"
PANEL_LIGHT = "#20242D"
BORDER = "#2A2F3A"
TEXT = "#F3F4F6"
MUTED = "#9AA3B2"
BLUE = "#3B82F6"
GREEN = "#35C98A"
AMBER = "#E8AD55"
RED = "#E56B75"


class GokworksPdfApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("GOKWORKS | PDF Aktarımı")
        self.geometry("1000x740")
        self.minsize(840, 660)
        self.configure(fg_color=BG)

        self.events = queue.Queue()
        self.source_folder = tk.StringVar(master=self)
        self.output_folder = tk.StringVar(master=self)
        self.include_subfolders = tk.BooleanVar(master=self, value=True)
        self.overwrite_existing = tk.BooleanVar(master=self, value=False)
        self.stat_values = {}

        self._build_window()
        self.after(100, self._process_events)

    def _build_window(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(24, 12))
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkFrame(header, width=44, height=44, corner_radius=13, fg_color=BLUE)
        logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="G", font=ctk.CTkFont(size=23, weight="bold"), text_color="white").place(
            relx=0.5, rely=0.47, anchor="center"
        )

        ctk.CTkLabel(
            header,
            text="GOKWORKS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=MUTED,
        ).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(
            header,
            text="SolidWorks otomasyonu",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).grid(row=1, column=1, sticky="nw")

        self.tabs = ctk.CTkTabview(
            self,
            fg_color=BG,
            segmented_button_fg_color=PANEL,
            segmented_button_selected_color=BLUE,
            segmented_button_selected_hover_color="#2F70D4",
            segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color=PANEL_LIGHT,
            text_color=TEXT,
            corner_radius=14,
            border_width=0,
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.tabs.add("PDF Aktarımı")
        self._build_pdf_tab(self.tabs.tab("PDF Aktarımı"))

    def _build_pdf_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            tab,
            text="PDF Aktarımı",
            font=ctk.CTkFont(size=25, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(
            tab,
            text="Teknik resim klasörünü seç, PDF’leri istediğin konuma aktar.",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 18))

        folder_card = ctk.CTkFrame(tab, fg_color=PANEL, corner_radius=15)
        folder_card.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        folder_card.grid_columnconfigure(0, weight=1)
        self._folder_row(folder_card, 0, "KAYNAK KLASÖR", self.source_folder, self._choose_source)
        self._folder_row(folder_card, 1, "PDF KAYIT KLASÖRÜ", self.output_folder, self._choose_output)

        options_card = ctk.CTkFrame(tab, fg_color=PANEL, corner_radius=15)
        options_card.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        options_card.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkCheckBox(
            options_card,
            text="Alt klasörleri de tara",
            variable=self.include_subfolders,
            font=ctk.CTkFont(size=13),
            text_color=TEXT,
            fg_color=BLUE,
            hover_color="#2F70D4",
            border_color=BORDER,
            corner_radius=5,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=15)
        ctk.CTkCheckBox(
            options_card,
            text="Mevcut PDF’lerin üzerine yaz",
            variable=self.overwrite_existing,
            font=ctk.CTkFont(size=13),
            text_color=TEXT,
            fg_color=BLUE,
            hover_color="#2F70D4",
            border_color=BORDER,
            corner_radius=5,
        ).grid(row=0, column=1, sticky="w", padx=18, pady=15)

        action_row = ctk.CTkFrame(tab, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(2, 14))
        action_row.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            action_row,
            text="SolidWorks açık olmalı · Hazır",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        )
        self.status_label.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.progress = ctk.CTkProgressBar(
            action_row,
            height=7,
            corner_radius=5,
            fg_color=PANEL_LIGHT,
            progress_color=BLUE,
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=(0, 14))
        self.progress.set(0)
        self.start_button = ctk.CTkButton(
            action_row,
            text="PDF’LERİ AKTAR",
            command=self._start_export,
            height=44,
            width=190,
            corner_radius=11,
            fg_color=BLUE,
            hover_color="#2F70D4",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.start_button.grid(row=0, column=1, rowspan=2, sticky="e")

        stats = ctk.CTkFrame(tab, fg_color="transparent")
        stats.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 12))
        for column in range(4):
            stats.grid_columnconfigure(column, weight=1, uniform="stats")
        self._stat_card(stats, 0, "BULUNAN", "0", MUTED)
        self._stat_card(stats, 1, "BAŞARILI", "0", GREEN)
        self._stat_card(stats, 2, "ATLANAN", "0", AMBER)
        self._stat_card(stats, 3, "HATALI", "0", RED)

        log_card = ctk.CTkFrame(tab, fg_color=PANEL, corner_radius=15)
        log_card.grid(row=6, column=0, sticky="nsew", padx=18, pady=(0, 14))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            log_card,
            text="İŞLEM KAYITLARI",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=MUTED,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(13, 6))
        self.log_box = ctk.CTkTextbox(
            log_card,
            height=120,
            corner_radius=10,
            fg_color="#111318",
            text_color="#D7DCE5",
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def _folder_row(self, parent, row, label, variable, command):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(14 if row == 0 else 8, 8))
        row_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row_frame,
            text=label,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=MUTED,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        entry = ctk.CTkEntry(
            row_frame,
            textvariable=variable,
            height=38,
            corner_radius=9,
            border_color=BORDER,
            fg_color="#111318",
            text_color=TEXT,
            placeholder_text="Bir klasör seç...",
            placeholder_text_color="#697386",
            font=ctk.CTkFont(size=12),
        )
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 9))
        ctk.CTkButton(
            row_frame,
            text="Gözat",
            command=command,
            width=86,
            height=38,
            corner_radius=9,
            fg_color=PANEL_LIGHT,
            hover_color="#2B303B",
            text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=1, sticky="e")

    def _stat_card(self, parent, column, label, initial_value, color):
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 5 if column < 3 else 0))
        ctk.CTkLabel(
            card,
            text=label,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=MUTED,
        ).pack(anchor="w", padx=13, pady=(10, 1))
        value_label = ctk.CTkLabel(
            card,
            text=initial_value,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=color,
        )
        value_label.pack(anchor="w", padx=13, pady=(0, 9))
        self.stat_values[label] = value_label

    def _choose_source(self):
        folder = filedialog.askdirectory(title=".SLDDRW dosyalarının bulunduğu klasörü seç")
        if folder:
            self.source_folder.set(folder)

    def _choose_output(self):
        folder = filedialog.askdirectory(title="PDF dosyalarının kaydedileceği klasörü seç")
        if folder:
            self.output_folder.set(folder)

    def _append_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _start_export(self):
        source = self.source_folder.get().strip()
        output = self.output_folder.get().strip()

        if not source or not os.path.isdir(source):
            messagebox.showerror("Kaynak klasör gerekli", "Lütfen geçerli bir kaynak klasör seç.", parent=self)
            return
        if not output or not os.path.isdir(output):
            messagebox.showerror("Kayıt klasörü gerekli", "Lütfen geçerli bir PDF kayıt klasörü seç.", parent=self)
            return

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.progress.set(0)
        self.status_label.configure(text="SolidWorks bağlantısı kuruluyor...", text_color=MUTED)
        self.start_button.configure(state="disabled", text="AKTARILIYOR...")
        for label in ("BULUNAN", "BAŞARILI", "ATLANAN", "HATALI"):
            self.stat_values[label].configure(text="0")

        worker = threading.Thread(
            target=export_drawings,
            args=(source, output, self.include_subfolders.get(), self.overwrite_existing.get(), self.events),
            daemon=True,
        )
        worker.start()

    def _process_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()

                if event == "log":
                    self._append_log(value)
                elif event == "total":
                    self.stat_values["BULUNAN"].configure(text=str(value))
                elif event == "progress":
                    current, total = value
                    self.progress.set(current / total if total else 0)
                    self.status_label.configure(text=f"İşleniyor · {current} / {total}")
                elif event == "done":
                    succeeded, skipped, failed = value
                    self.stat_values["BAŞARILI"].configure(text=str(succeeded))
                    self.stat_values["ATLANAN"].configure(text=str(skipped))
                    self.stat_values["HATALI"].configure(text=str(failed))
                    self.status_label.configure(
                        text=f"Tamamlandı · {succeeded} başarılı, {skipped} atlanan, {failed} hatalı",
                        text_color=GREEN if failed == 0 else AMBER,
                    )
                    self.start_button.configure(state="normal", text="PDF’LERİ AKTAR")
        except queue.Empty:
            pass

        self.after(100, self._process_events)


def main():
    app = GokworksPdfApp()
    app.mainloop()
