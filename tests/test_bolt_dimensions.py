"""Distinguish ISO hexagon heads from old DIN sizes in the diagram."""

import unittest

from bolt.dimensions import dimensions
from bolt.rules import THREADS


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
