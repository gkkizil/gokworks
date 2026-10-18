"""Manual thickness rows remain independent from calculation helper inputs."""
import json
from unittest.mock import patch

from support.gui import GuiTestCase
from k_factor.rules import AssignmentTable
from k_factor.window import AUTOMATIC_TAB


class AssignmentWindowTests(GuiTestCase):
    def manual_rows(self):
        self.app._switch_mode('k_factor')
        self.app.k_state['manual_k'].set('0,274')
        self.app.k_state['manual_r'].set('2')
        self.app._add_assignment_row({'thickness': '3', 'k': '0.31', 'r': '4'})
        return self.app.k_widgets['assignment_rows']

    def test_preview_and_worker_capture_complete_table(self):
        self.manual_rows()
        result = self.app._preview_k_calculation()
        self.assertEqual(result.k_factor, .274)
        text = self.app.k_widgets['manual_summary'].cget('text')
        self.assertIn('2 mm sac', text)
        self.assertIn('3 mm sac', text)
        with patch('k_factor.window.threading.Thread') as thread:
            self.app._run_k_worker(preview=True)
        table = thread.call_args.kwargs['args'][0]
        self.assertIsInstance(table, AssignmentTable)
        self.assertEqual([r.thickness_mm for r in table.rows], [2, 3])
        self.assertEqual([r.radius_mm for r in table.rows], [2, 4])
        self.app._set_busy(False)

    def test_rows_persist_remove_and_duplicate_blocks_assignment(self):
        rows = self.manual_rows()
        self.assertEqual(json.loads(self.app.k_state['manual_rows'].get())[0]['k'], '0.31')
        self.app._on_close()
        self.open_app()
        self.app._switch_mode('k_factor')
        rows = self.app.k_widgets['assignment_rows']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['k'].get(), '0,274')
        self.assertEqual(rows[1]['k'].get(), '0.31')
        rows[1]['thickness'].set('2,0')
        with self.assertRaises(ValueError):
            self.app._manual_k_recipe()
        removed_controls = list(rows[1]['controls'])
        self.app._remove_assignment_row(rows[1])
        self.assertEqual(self.app.k_state['manual_rows'].get(), '[]')
        self.assertTrue(all(control not in self.app.controls for control in removed_controls))
        self.assertEqual(len(self.app._manual_k_recipe()[1].rows), 1)

    def test_helper_values_do_not_fill_manual_rows_or_apply(self):
        self.app._switch_mode('k_factor')
        self.app._select_k_assignment(AUTOMATIC_TAB)
        self.app.k_state['thickness'].set('7')
        self.app.k_state['punch'].set('5')
        self.app.k_state['radius'].set('6')
        self.assertEqual(self.app.k_state['manual_k'].get(), '')
        self.assertEqual(self.app.k_state['manual_r'].get(), '')
        with patch('k_factor.window.threading.Thread') as thread:
            self.app._run_k_worker(preview=False)
        thread.assert_not_called()
        self.assertFalse(self.app.busy)

    def test_queued_apply_keeps_row_snapshot(self):
        rows = self.manual_rows()
        self.app.busy = True
        self.app.k_widgets['operation_preview'] = True
        self.app._start_k_apply()
        table, save = self.app.k_widgets['pending_apply']
        rows[1]['k'].set('.8')
        self.assertEqual(table.rows[1].k_factor, .31)
        self.assertFalse(save)
        self.app.busy = False
