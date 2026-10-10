"""Avoid repeating expensive CustomTkinter redraws for unchanged properties."""


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
