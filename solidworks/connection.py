"""Açık SolidWorks oturumuna bağlanma yardımcıları."""


def connect_to_solidworks():
    """Çalışan SolidWorks oturumuna bağlan."""
    try:
        import win32com.client
    except ImportError as error:
        raise RuntimeError(
            "SolidWorks bağlantısı için pywin32 paketi gerekli. "
            "PyCharm terminalinde .venv\\Scripts\\python.exe -m pip install pywin32 komutunu çalıştırın."
        ) from error

    try:
        return win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as error:
        raise RuntimeError(
            "SolidWorks açık değil veya oturuma bağlanılamadı. SolidWorks'ü açıp tekrar deneyin.\n" + str(error)
        ) from error
