"""Inventory tracked Python, eager local imports and security-sensitive call sites.

Read-only analysis: no application imports, COM session or CAD file changes.
Run: python packaging/audit_project.py --output docs/audit/inventory.json
Findings are review locations, never proof that a call is exploitable/dead code.
"""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WATCH = {'eval', 'exec', 'loads', 'load', 'Popen', 'run', 'system', 'unlink', 'rmtree', 'replace', 'rename'}


def inventory(root=ROOT):
    paths = subprocess.run(['git', 'ls-files', '-z', '--', '*.py'], cwd=root,
                           capture_output=True, check=True).stdout.decode().split('\0')
    # Include newly added, untracked source without traversing environments.
    extra = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '-z', '--', '*.py'],
                           cwd=root, capture_output=True, check=True).stdout.decode().split('\0')
    paths = sorted(set(paths + extra) - {''})
    modules = {p: p.removesuffix('.py').replace('/', '.').removesuffix('.__init__') for p in paths}
    names = set(modules.values()); graph = defaultdict(set)
    files, hazards, duplicates = [], [], defaultdict(list)

    def local(name):
        while name:
            if name in names: return name
            name = name.rpartition('.')[0]
        return ''

    for relative in paths:
        path = root/relative; source = path.read_text(encoding='utf-8-sig')
        record = dict(path=relative, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), lines=len(source.splitlines()))
        try:
            tree = ast.parse(source, filename=relative)
            compile(tree, relative, 'exec')
        except (SyntaxError, ValueError) as error:
            record['syntax_error'] = str(error); files.append(record); continue
        module = modules[relative]
        package = module if path.name == '__init__.py' else module.rpartition('.')[0]
        record['functions'] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
        record['classes'] = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.rsplit('.', 1)[-1] in WATCH:
                    hazards.append(dict(path=relative, line=node.lineno, call=name))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Exact bodies, ignoring location/name/docstring. Only sizeable
                # duplicates are useful review candidates; no automatic removal.
                body = node.body[1:] if ast.get_docstring(node) else node.body
                if len(body) >= 5:
                    key = hashlib.sha256(ast.dump(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()
                    duplicates[key].append(f'{relative}:{node.lineno} {node.name}')

        def eager(nodes):
            # Function/class-local and TYPE_CHECKING imports are lazy edges.
            for node in nodes:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if name := local(alias.name): graph[module].add(name)
                elif isinstance(node, ast.ImportFrom):
                    parts = package.split('.') if package else []
                    base = '.'.join(parts[:len(parts)-node.level+1]) if node.level else ''
                    target = '.'.join(p for p in (base, node.module) if p)
                    for alias in node.names:
                        if name := local(target + '.' + alias.name): graph[module].add(name)
                elif isinstance(node, ast.Try):
                    eager(node.body); eager(node.orelse); eager(node.finalbody)
                    for handler in node.handlers: eager(handler.body)
                elif isinstance(node, ast.If) and ast.unparse(node.test) not in ('TYPE_CHECKING', 'typing.TYPE_CHECKING'):
                    eager(node.body); eager(node.orelse)
        eager(tree.body); graph[module].discard(module)
        record['eager_local_imports'] = sorted(graph[module]); files.append(record)

    # Tarjan strongly connected components, which cover cycles without
    # enumerating exponentially many possible paths through the same component.
    order, low, stack, on_stack, cycles = {}, {}, [], set(), []
    def visit(node):
        order[node] = low[node] = len(order); stack.append(node); on_stack.add(node)
        for child in sorted(graph[node]):
            if child not in order: visit(child); low[node] = min(low[node], low[child])
            elif child in on_stack: low[node] = min(low[node], order[child])
        if order[node] == low[node]:
            component = []
            while True:
                child = stack.pop(); on_stack.remove(child); component.append(child)
                if child == node: break
            if len(component) > 1: cycles.append(sorted(component))
    for module in sorted(names):
        if module not in order: visit(module)
    return dict(files=files, python_files=len(files), lines=sum(f['lines'] for f in files),
                syntax_errors=[f for f in files if 'syntax_error' in f],
                by_directory=dict(sorted(Counter(p.split('/')[0] for p in paths).items())),
                eager_import_cycles=cycles, identical_large_bodies=[v for v in duplicates.values() if len(v)>1],
                sensitive_calls=hazards)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"{result['python_files']} Python files, {result['lines']} lines, "
          f"{len(result['syntax_errors'])} syntax errors, {len(result['eager_import_cycles'])} import components.")
    return bool(result['syntax_errors'])


if __name__ == '__main__':
    raise SystemExit(main())
