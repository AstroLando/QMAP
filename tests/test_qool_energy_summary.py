"""Run within the installed qmap_iqm environment: PYTHONPATH=src python -m unittest discover -s tests."""
import unittest
from qmap.workflows.qool_vqe import energy_history_summary


class EnergyHistorySummaryTest(unittest.TestCase):
    def test_best_and_last_are_distinct(self):
        rows = [
            {'index': 0, 'energy': 1.285},
            {'index': 1, 'energy': 0.843},
            {'index': 2, 'energy': 1.324},
        ]
        result = energy_history_summary(rows)
        self.assertEqual(result['best_observed_energy'], 0.843)
        self.assertEqual(result['best_observed_evaluation_index'], 1)
        self.assertEqual(result['last_evaluated_energy'], 1.324)
        self.assertEqual(result['last_evaluation_index'], 2)

    def test_empty_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No objective evaluations'):
            energy_history_summary([])


if __name__ == '__main__':
    unittest.main()
