"""Give native Windows GUI checks a real desktop large enough for wide layouts.

GitHub's Hyper-V desktop can start at 1024x768. Windows then clamps a requested
1440x900 top-level window to about 1028x749, so a wide-layout test actually
examines a compact window. Change only this ephemeral runner's current display
mode; do not persist a setting in the registry or alter the shipped application.
"""

import ctypes
import json
from pathlib import Path
import sys


def select_mode(modes, minimum=(1920, 1080)):
    candidates = [mode for mode in modes
                  if mode[0] >= minimum[0] and mode[1] >= minimum[1] and mode[2] >= 24]
    # Prefer a reasonably sized wide desktop, retaining room for high-DPI checks.
    bounded = [mode for mode in candidates if mode[0] <= 4096 and mode[1] <= 3072]
    return max(bounded or candidates, key=lambda mode: (mode[0]*mode[1],mode[2],mode[3]), default=None)


def main():
    if sys.platform != 'win32':
        raise SystemExit('This display setup is only for the native Windows CI runner.')
    from ctypes import wintypes as wt

    class Point(ctypes.Structure):
        _fields_ = [('x',wt.LONG),('y',wt.LONG)]

    class Display(ctypes.Structure):
        _fields_ = [('position',Point),('orientation',wt.DWORD),('fixed_output',wt.DWORD)]

    class Printer(ctypes.Structure):
        _fields_ = [(name,ctypes.c_short) for name in
                    ('orientation','paper_size','paper_length','paper_width',
                     'scale','copies','default_source','print_quality')]

    class ModeUnion(ctypes.Union):
        _fields_ = [('display',Display),('printer',Printer)]

    class Mode(ctypes.Structure):
        _fields_ = [('device',wt.WCHAR*32),('spec_version',wt.WORD),
            ('driver_version',wt.WORD),('size',wt.WORD),('driver_extra',wt.WORD),
            ('fields',wt.DWORD),('details',ModeUnion),
            *[(name,ctypes.c_short) for name in ('color','duplex','y_resolution','tt_option','collate')],
            ('form',wt.WCHAR*32),('log_pixels',wt.WORD),
            *[(name,wt.DWORD) for name in ('bits','width','height','flags','frequency',
               'icm_method','icm_intent','media_type','dither_type','reserved1','reserved2',
               'panning_width','panning_height')]]

    assert ctypes.sizeof(Mode) == 220, ctypes.sizeof(Mode)
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    enum = user32.EnumDisplaySettingsW
    enum.argtypes = [wt.LPCWSTR,wt.DWORD,ctypes.POINTER(Mode)]
    enum.restype = wt.BOOL
    change = user32.ChangeDisplaySettingsExW
    change.argtypes = [wt.LPCWSTR,ctypes.POINTER(Mode),wt.HWND,wt.DWORD,ctypes.c_void_p]
    change.restype = wt.LONG

    def current():
        mode=Mode();mode.size=ctypes.sizeof(Mode)
        if not enum(None,0xffffffff,ctypes.byref(mode)):
            raise RuntimeError('Cannot read the Windows runner display mode.')
        return mode

    before=current()
    available=[]
    modes=[]
    index=0
    while True:
        mode=Mode();mode.size=ctypes.sizeof(Mode)
        if not enum(None,index,ctypes.byref(mode)):
            break
        available.append((mode.width,mode.height,mode.bits,mode.frequency))
        modes.append(mode)
        index+=1
    selected=select_mode(available)
    if selected is not None:
        requested=modes[available.index(selected)]
    else:
        # Some virtual adapters accept a larger mode without enumerating it.
        requested=current();requested.width=1920;requested.height=1080
        requested.fields=0x00080000|0x00100000  # DM_PELSWIDTH | DM_PELSHEIGHT
    result=change(None,ctypes.byref(requested),None,0,None)
    after=current()
    report=dict(before=[before.width,before.height],requested=[requested.width,requested.height],
                actual=[after.width,after.height],change_result=int(result),
                available=sorted(set(available)))
    Path('windows-display.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)
    if result != 0 or after.width < 1920 or after.height < 1080:
        raise RuntimeError('Windows desktop is too small for native wide-layout checks.')


if __name__ == '__main__':
    main()
