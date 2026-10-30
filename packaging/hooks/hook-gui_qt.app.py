"""Keep every lazily imported workbench in both onefile and onedir builds.

Read the declarative catalog without importing Qt or constructing the GUI in
PyInstaller's analysis process. Existing per-library hooks still apply.
"""
import ast
from pathlib import Path

source = Path(__file__).resolve().parents[2] / 'gui_qt' / 'app.py'
module = ast.parse(source.read_text(encoding='utf-8'))
catalog = next(ast.literal_eval(node.value) for node in module.body
               if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'PAGE_TYPES' for target in node.targets))
hiddenimports = [module_name for module_name, _ in catalog.values()]
