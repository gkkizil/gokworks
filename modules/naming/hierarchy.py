"""Display saved file relationships without changing the Pack and Go order."""

from dataclasses import dataclass
from pathlib import PureWindowsPath

from modules.bom.exporter import name_key
from modules.naming.exporter import path_key


@dataclass(frozen=True)
class Row:
    iid: str
    parent: str
    index: int
    shared: bool = False
    reference: bool = False


def document_rows(snapshot):
    """Show shared files under each parent, expanding their contents once.

    These are file relationships, not component quantities/configurations.
    Iterative traversal also handles deep or cyclic reference graphs safely.
    """
    docs = snapshot.documents
    indices = {path_key(doc.path): index for index, doc in enumerate(docs)}

    def order(index):
        doc = docs[index]
        return (doc.kind != 'Montaj', doc.kind == 'Teknik resim',
                name_key(PureWindowsPath(doc.path).name), path_key(doc.path))

    children = [[] for _ in docs]
    for index, doc in enumerate(docs):
        refs = {indices[path_key(ref)] for ref in doc.dependencies if path_key(ref) in indices}
        if doc.kind in ('Montaj', 'Parça'):
            children[index].extend(ref for ref in refs if docs[ref].kind in ('Montaj', 'Parça'))
        elif doc.kind == 'Teknik resim' and index != indices.get(path_key(snapshot.root)):
            models = [ref for ref in refs if docs[ref].kind in ('Montaj', 'Parça')]
            if models:
                stem = path_key(str(PureWindowsPath(doc.path).with_suffix('')))
                owner = min(models, key=lambda ref: (
                    path_key(str(PureWindowsPath(docs[ref].path).with_suffix(''))) != stem, order(ref)))
                children[owner].append(index)
    for values in children:
        values.sort(key=order)

    root = indices.get(path_key(snapshot.root))
    starts = sorted(range(len(docs)), key=order)
    if root is not None:
        starts.remove(root)
        starts.insert(0, root)
    seen, rows = set(), []
    for start in starts:
        if start in seen:
            continue
        stack = [(start, '', False)]
        while stack:
            index, parent, reference = stack.pop()
            shared = index in seen
            iid = f'{index}:{len(rows)}' if shared else str(index)
            rows.append(Row(iid, parent, index, shared, reference))
            if shared:
                continue
            seen.add(index)
            # An active drawing is the entry point to its referenced models.
            descendants = children[index]
            if index == root and docs[index].kind == 'Teknik resim':
                descendants = sorted({indices[path_key(ref)] for ref in docs[index].dependencies
                                      if path_key(ref) in indices}, key=order)
            for child in reversed(descendants):
                stack.append((child, iid, docs[index].kind == 'Parça' and docs[child].kind != 'Teknik resim'))
    return tuple(rows)
