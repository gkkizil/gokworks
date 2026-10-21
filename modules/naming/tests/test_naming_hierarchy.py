"""Reference graph edge cases in the naming tree."""

import unittest

from modules.naming.exporter import Document, Snapshot
from modules.naming.hierarchy import document_rows


class NamingHierarchyTests(unittest.TestCase):
    def test_cycles_shared_branches_and_unrelated_files_remain_finite(self):
        snapshot = Snapshot('C:/Ana.sldasm', (
            Document('C:/Ana.sldasm', ('C:/Alt.sldasm', 'C:/Vida.sldprt'), ()),
            Document('C:/Alt.sldasm', ('c:/ANA.SLDASM', 'C:/Vida.sldprt', 'C:/Vida.sldprt'), ()),
            Document('C:/Vida.sldprt', (), ()),
            Document('C:/Ek.txt', (), ()),
        ))
        rows = document_rows(snapshot)
        self.assertEqual({row.index for row in rows}, {0, 1, 2, 3})
        self.assertEqual(len(rows), 6)
        by_id = {row.iid: row for row in rows}
        self.assertEqual(by_id['1'].parent, '0')
        self.assertEqual(by_id['2'].parent, '1')
        self.assertEqual(by_id['3'].parent, '')
        for row in rows:
            if row.shared:
                self.assertFalse(any(other.parent == row.iid for other in rows))

    def test_drawing_root_and_deep_models_do_not_recurse(self):
        count = 1200
        paths = [f'C:/M{i}.sldasm' for i in range(count)]
        docs = [Document(path, (paths[i+1],) if i+1 < count else (), ())
                for i, path in enumerate(paths)]
        drawing = Document('C:/Ana.slddrw', (paths[0],), ())
        rows = document_rows(Snapshot(drawing.path, (*docs, drawing)))
        self.assertEqual(len(rows), count+1)
        self.assertEqual(rows[0].index, count)
        self.assertEqual(rows[1].parent, str(count))
        self.assertEqual(rows[-1].parent, str(count-2))
