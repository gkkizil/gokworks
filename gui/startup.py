"""Prepare native page surfaces once before interactive navigation starts."""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from gui.icons import make_logo
from gui.theme import BG, TEXT, MUTED, UI_FONT


def prepare_pages(app):
    """Build and lay out pages on the Tk thread under a startup cover.

    Event pumping happens between complete pages, never inside constructors.
    Once the cover is removed, menu clicks only raise already prepared pages.
    """
    if app._preload_id is not None:
        app.after_cancel(app._preload_id)
        app._preload_id = None
    app._preparing_navigation = True
    background = app._apply_appearance_mode(BG)
    cover = tk.Frame(app, background=background, takefocus=True)
    app._startup_cover = cover
    cover.place(x=0, y=0, relwidth=1, relheight=1)
    center = tk.Frame(cover, background=background)
    center.place(relx=.5, rely=.5, anchor='center')
    ctk.CTkLabel(center, text='', image=make_logo(224), width=224, height=80,
                 fg_color=background).pack(pady=(0, 12))
    tk.Label(center, text='GOKWORKS', font=(UI_FONT, 14, 'bold'),
             background=background, foreground=app._apply_appearance_mode(TEXT)).pack(pady=(0, 16))
    label = tk.Label(center, text='Çalışma alanları hazırlanıyor…', font=(UI_FONT, 12),
                     background=background, foreground=app._apply_appearance_mode(MUTED))
    label.pack(pady=(0, 14))
    progress = ttk.Progressbar(center, mode='determinate', maximum=len(app._MODES), length=320)
    progress.pack()
    app.deiconify()
    cover.lift()
    cover.focus_set()
    try:
        app.update()
        for index, mode in enumerate(app._MODES, 1):
            if app._closed:
                return
            app._switch_mode(mode)
            # Finish the follow-up viewport fit now, while the cover is up.
            # Otherwise the next page cancels its pending resize timer.
            app._resize_pdf_area(immediate=True)
            app.update_idletasks()
            app.workspace._navigation_layout = app._navigation_layout_key()
            label.configure(text=f"Çalışma alanları hazırlanıyor · {index} / {len(app._MODES)}")
            progress.configure(value=index)
            # Process mapping, final layout, and the window close button while
            # no partly constructed page can receive input.
            app.update()
            if app._closed:
                return
        app._switch_mode('pdf')
        app.update_idletasks()
    finally:
        app._preparing_navigation = False
        app._startup_cover = None
        if not app._closed:
            cover.destroy()
            app.workspace.tkraise()
            app.workspace.focus_set()
