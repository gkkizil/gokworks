"""Açık SolidWorks oturumuna bağlanma yardımcıları."""


def connect_to_solidworks(*, raw=False):
    """Çalışan SolidWorks oturumuna bağlan."""
    try:
        if raw:
            import pythoncom
        else:
            import win32com.client
    except ImportError as error:
        raise RuntimeError(
            "SolidWorks bağlantısı için pywin32 paketi gerekli. "
            "PyCharm terminalinde .venv\\Scripts\\python.exe -m pip install pywin32 komutunu çalıştırın."
        ) from error

    try:
        if raw:
            # Avoid win32com's automatic MakePy/type-info wrapping for callers
            # that invoke the published dual interfaces explicitly.
            # GetActiveObject resolves a ProgID itself (PyWinObject_AsIID).
            # CLSIDFromProgID is a Windows API, not a pythoncom export.
            active = pythoncom.GetActiveObject("SldWorks.Application")
            return active.QueryInterface(pythoncom.IID_IDispatch)
        return win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as error:
        raise RuntimeError(
            "SolidWorks açık değil veya oturuma bağlanılamadı. SolidWorks'ü açıp tekrar deneyin.\n" + str(error)
        ) from error
