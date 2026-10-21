"""Distinguish ISO hexagon heads from old DIN sizes in the diagram."""

import unittest

from modules.bolt.dimensions import dimensions
from modules.bolt.rules import THREADS


class BoltDimensionsTests(unittest.TestCase):
    def test_reference_head_sizes_and_approximate_tapping_hole(self):
        for metric, height, flats in (('M8', 5.3, 13), ('M10', 6.4, 16),
                                      ('M12', 7.5, 18), ('M22', 14, 34)):
            with self.subTest(metric=metric):
                value = dimensions(metric)
                self.assertEqual(value.head_height, height)
                self.assertEqual(value.across_flats, flats)
        self.assertEqual(dimensions('M8').tapping_hole, 6.75)

    def test_every_supported_metric_has_head_geometry(self):
        for metric in THREADS:
            with self.subTest(metric=metric):
                value = dimensions(metric)
                self.assertGreater(value.across_flats, value.diameter)
                self.assertGreater(value.head_height, 0)
                self.assertGreater(value.tapping_hole, 0)

    def test_fine_pitch_changes_approximate_tapping_hole(self):
        coarse = dimensions('M10')
        fine = dimensions('M10', 'İnce diş', '.75')
        self.assertEqual(fine.pitch, .75)
        self.assertEqual(fine.tapping_hole, 9.25)
        self.assertEqual(coarse.tapping_hole, 8.5)
        self.assertEqual(fine.diameter, coarse.diameter)
        self.assertEqual(fine.across_flats, coarse.across_flats)
