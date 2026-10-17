"""Avoid repeating expensive CustomTkinter redraws for unchanged properties."""


def limit_root_configure_events(window):
    """Keep CTk's root-size listener out of every descendant's resize event.

    Tk adds the toplevel bindtag to all children. CTk's root Configure handler
    consequently runs for thousands of child changes, querying the same root
    size each time. Filter in Tcl before Tk marshals an event into Python.
    Later application bindings and widget-specific Configure handlers remain
    untouched; real toplevel resize events still reach CTk's original handler.
    """
    script = window.bind('<Configure>')
    if script:
        window.tk.call('bind', window._w, '<Configure>',
                       f'if {{"%W" == "{window._w}"}} {{\n{script}\n}}')


def configure_changed(widget, **options):
    changed = {key: value for key, value in options.items() if widget.cget(key) != value}
    if changed:
        widget.configure(**changed)


def hide_grid(widget):
    # CTk 6 replays this call on DPI changes even after Tk's grid_remove().
    # Scrollable frames delegate geometry to their outer CTkFrame.
    # Retain Tk's grid geometry, but prevent hidden widgets from being remapped.
    widget.grid_remove()
    owner = getattr(widget, '_parent_frame', widget)
    owner._last_geometry_manager_call = None
