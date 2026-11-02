"""No backend should be initialized for an invalid COBYLA budget."""
import subprocess
import sys
import unittest


class CobylaBudgetGuardTest(unittest.TestCase):
    def test_reject_before_backend_initialization(self):
        command = [sys.executable, '-m', 'qmap.workflows.qool_vqe',
                   '--adapter', 'iqm-onprem', '--qubits', '4', '--layers', '2',
                   '--max-evals', '5']
        p = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('requires --max-evals >= 10', p.stderr)
        self.assertNotIn('IQM_ONPREM_TOKEN', p.stderr)


if __name__ == '__main__':
    unittest.main()
