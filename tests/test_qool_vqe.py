"""Pure unit tests; full Aer/Pathfinder requires user Qiskit environment."""
import unittest
from qmap.workflows.qool_vqe import term_expectation, estimate_pauli_energy


class FakeOp:
    def to_list(self):
        return [('ZI', 0.5), ('ZZ', 0.25), ('IX', 0.1)]


class QOOLTests(unittest.TestCase):
    def test_parity(self):
        self.assertEqual(term_expectation({'00': 10}, 'ZZ'), 1.0)
        self.assertEqual(term_expectation({'01': 10}, 'IZ'), -1.0)
        self.assertEqual(term_expectation({'00': 5, '01': 5}, 'IZ'), 0.0)

    def test_energy(self):
        # All-0 Z basis => +1 ZI, +1 ZZ; all-0 X basis => +1 IX.
        self.assertAlmostEqual(estimate_pauli_energy({'00': 100}, {'00': 100}, FakeOp()), 0.85)

    def test_empty(self):
        with self.assertRaises(ValueError):
            term_expectation({}, 'ZI')


if __name__ == '__main__':
    unittest.main()
