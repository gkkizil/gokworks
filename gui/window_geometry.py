"""Initial window bounds in logical pixels, including the Windows work area."""

import os


def window_sizes(width, height, scale):
    # Leave room for the window frame/title bar even at 125–200% display DPI.
    available_width = max(1, int(width/scale)-24)
    available_height = max(1, int(height/scale)-48)
    return ((min(1240, available_width), min(860, available_height)),
            (min(1000, available_width), min(690, available_height)))


def configure_window_geometry(window):
    width, height = window.winfo_screenwidth(), window.winfo_screenheight()
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

        user = ctypes.windll.user32
        nearest = user.MonitorFromWindow
        nearest.argtypes, nearest.restype = [wintypes.HWND, wintypes.DWORD], wintypes.HANDLE
        get_info = user.GetMonitorInfoW
        get_info.argtypes, get_info.restype = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)], wintypes.BOOL
        info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
        if get_info(nearest(window.winfo_id(), 2), ctypes.byref(info)):
            width = info.rcWork.right-info.rcWork.left
            height = info.rcWork.bottom-info.rcWork.top
    initial, minimum = window_sizes(width, height, window._get_window_scaling())
    window.geometry(f'{initial[0]}x{initial[1]}')
    window.minsize(*minimum)
