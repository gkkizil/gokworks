"""Native geometry checks for usable work areas independent of form scrolling."""

import unittest
from collections import Counter
import time
from unittest.mock import patch


from shared.window_geometry import window_sizes


class WindowBoundsTests(unittest.TestCase):
    def test_default_and_minimum_sizes_fit_available_screen_at_display_dpi(self):
        for width, height, scale in ((1920, 1040, 1), (1366, 728, 1.25), (1920, 1040, 1.5), (2560, 1400, 2)):
            with self.subTest(width=width, height=height, scale=scale):
                initial, minimum = window_sizes(width, height, scale)
                self.assertLessEqual(minimum[0], initial[0])
                self.assertLessEqual(minimum[1], initial[1])
                self.assertLessEqual((initial[0]+24)*scale, width)
                self.assertLessEqual((initial[1]+48)*scale, height)
        self.assertEqual(window_sizes(1920, 1040, 1), ((1240, 860), (1000, 690)))




if __name__ == '__main__':
    unittest.main()
