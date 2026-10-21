"""Kullanıcının kalınlık tablosunu tahmin yapmadan eşleştirme sözleşmesi."""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

from modules.k_factor.rules import (
    AssignmentTable, ManualAssignment, ManualCalculation, ThicknessMismatch,
    calculate,
)


class ThicknessAssignmentTests(unittest.TestCase):
    def test_multiple_thicknesses_preserve_entered_values_without_calculation(self):
        table = AssignmentTable((
            ManualAssignment('3,0', '0,413456789', '4,56789'),
            ManualAssignment('2', '0,274', '2'),
            ManualAssignment('25', '1', '80'),
            ManualAssignment('1', '0', '0,5'),
        ))
        with patch('modules.k_factor.rules.recommended_k', side_effect=AssertionError('No estimated K')):
            for thickness, k, radius in ((2, .274, 2), (3, .413456789, 4.56789),
                                          (25, 1, 80), (1, 0, .5)):
                with self.subTest(thickness=thickness):
                    result = calculate(thickness, table)
                    self.assertIsInstance(result, ManualCalculation)
                    self.assertEqual((result.thickness_mm, result.k_factor, result.radius_mm),
                                     (thickness, k, radius))
                    self.assertIsNone(result.ba_mm)

    def test_only_conversion_roundoff_matches_and_unlisted_thicknesses_skip(self):
        table = AssignmentTable((ManualAssignment(2, .274, 2), ManualAssignment(2000, .3, 3)))
        self.assertEqual(calculate(2 + 1e-10, table).k_factor, .274)
        self.assertEqual(calculate(2000 + 1e-8, table).k_factor, .3)
        for actual in (1.99, 2 + 2e-6, 3, 2000.001):
            with self.subTest(actual=actual), self.assertRaises(ThicknessMismatch):
                calculate(actual, table)

    def test_duplicate_and_ambiguous_intervals_are_rejected_before_matching(self):
        for second in ('2,000', 2 + .5e-6, 2 + 1.5e-6):
            table = AssignmentTable((ManualAssignment(2, .274, 2), ManualAssignment(second, .4, 4)))
            with self.subTest(second=second), self.assertRaisesRegex(ValueError, 'tek K/R satırı'):
                # Even an unrelated thickness must not hide invalid input as a skip.
                calculate(5, table)
        separate = AssignmentTable((ManualAssignment(2, .274, 2),
                                    ManualAssignment(2 + 3e-6, .4, 4)))
        self.assertEqual(calculate(2, separate).k_factor, .274)
        self.assertEqual(calculate(2 + 3e-6, separate).k_factor, .4)

    def test_missing_and_invalid_rows_cannot_start_assignment(self):
        for rows in ((), ('invalid',), (ManualAssignment(0, .2, 1),),
                     (ManualAssignment(2, 'nan', 2),), (ManualAssignment(2, 1.01, 2),),
                     (ManualAssignment(2, -.1, 2),), (ManualAssignment(2, .2, 0),),
                     (ManualAssignment(True, .2, 1),), (ManualAssignment(2, .2, 'inf'),)):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                AssignmentTable(rows).validate()

    def test_table_is_immutable_and_single_assignment_api_remains_valid(self):
        source = [ManualAssignment('2,0', '0,274', '2,5')]
        table = AssignmentTable(source)
        source.clear()
        self.assertIsInstance(table.rows, tuple)
        self.assertEqual(len(table.rows), 1)
        self.assertTrue(table.all_bends)
        with self.assertRaises(FrozenInstanceError):
            table.rows = ()
        self.assertEqual(calculate(2, table), calculate(2, table.rows[0]))


if __name__ == '__main__':
    unittest.main()
