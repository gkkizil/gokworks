"""Run before PyInstaller's Qt hooks and before any Qt module is imported."""
from solidworks.runtime import configure_libraries

configure_libraries()
