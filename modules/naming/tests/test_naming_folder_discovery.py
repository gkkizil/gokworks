"""Folder selection finds assembly candidates without a SolidWorks session."""

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from modules.naming.exporter import Cancelled
from modules.naming.source import discover_assemblies


class NamingFolderDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def make_file(self, relative):
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_root_assemblies_take_priority_and_use_natural_case_insensitive_order(self):
        ten = self.make_file('Montaj10.SLDASM')
        two = self.make_file('montaj2.sldasm')
        self.make_file('Alt/Ana.sldasm')
        self.make_file('~$Montaj1.sldasm')
        self.make_file('~Montaj3.sldasm')
        self.make_file('Parca.sldprt')
        self.assertEqual(discover_assemblies(self.folder), (two, ten))

    def test_nested_candidates_use_relative_path_natural_order_and_skip_symlinks(self):
        first = self.make_file('Grup2/Montaj2.sldasm')
        second = self.make_file('Grup2/Montaj10.SLDASM')
        third = self.make_file('Grup10/Ana.sldasm')
        self.make_file('Grup1/~$Gecici.sldasm')
        with TemporaryDirectory() as external:
            (Path(external) / 'Dis-montaj.sldasm').touch()
            (self.folder / 'Grup0').symlink_to(external, target_is_directory=True)
            (self.folder / 'Grup2' / 'Dongu').symlink_to(self.folder,
                                                        target_is_directory=True)
            self.assertEqual(discover_assemblies(self.folder), (first, second, third))

    def test_empty_invalid_or_missing_folder_has_clear_result(self):
        self.make_file('Alt/Parca.sldprt')
        self.assertEqual(discover_assemblies(self.folder), ())
        for invalid in ('', None, self.folder / 'yok', self.folder / 'Alt/Parca.sldprt'):
            with self.subTest(folder=invalid), self.assertRaisesRegex(ValueError, 'klasör'):
                discover_assemblies(invalid)

    def test_cancellation_before_and_during_scan_uses_existing_cancelled_exception(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Cancelled):
            discover_assemblies(self.folder, stop)
        stop.clear()
        self.make_file('Alt/Ana.sldasm')
        real_scandir = __import__('os').scandir

        def cancel_on_child(path):
            if Path(path) != self.folder:
                stop.set()
            return real_scandir(path)

        with patch('modules.naming.source.os.scandir', side_effect=cancel_on_child):
            with self.assertRaises(Cancelled):
                discover_assemblies(self.folder, stop)

    def test_unreadable_subfolder_is_reported_instead_of_returning_partial_results(self):
        self.make_file('Alt/Ana.sldasm')
        real_scandir = __import__('os').scandir

        def deny_child(path):
            if Path(path) != self.folder:
                raise PermissionError(13, 'Permission denied', str(path))
            return real_scandir(path)

        with patch('modules.naming.source.os.scandir', side_effect=deny_child):
            with self.assertRaisesRegex(OSError, 'Montaj klasörü okunamadı.*Alt'):
                discover_assemblies(self.folder)


if __name__ == '__main__':
    unittest.main()
