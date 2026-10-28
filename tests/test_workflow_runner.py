import json
import tempfile
import unittest
from pathlib import Path
from qmap.workflows.runner import MockAdapter, Task, Workflow, execute_workflow, make_workflow


class DummyCircuit:
    num_qubits = 4


class RunnerTests(unittest.TestCase):
    def test_workflow_dependency_and_batching(self):
        q = DummyCircuit()
        with tempfile.TemporaryDirectory() as tmp:
            for pattern in ('fragmented', 'batched'):
                wf = make_workflow(pattern, q, 100, 4, 0)
                for policy in ('fifo', 'batch'):
                    result = execute_workflow(wf, MockAdapter(0, 0), policy, Path(tmp))
                    expected = 1 if pattern == 'batched' and policy == 'batch' else 4
                    self.assertEqual(result['quantum_submissions'], expected)
                    self.assertEqual(result['quantum_circuits'], 4)
                    events = [json.loads(x) for x in Path(result['trace']).read_text().splitlines()]
                    self.assertEqual(events[-1]['event'], 'workflow_completed')
                    self.assertTrue(all('monotonic_offset_ns' in x for x in events))

    def test_reject_cycles(self):
        with self.assertRaises(ValueError):
            Workflow('bad', 'x', 'batched', [Task('a', 'classical', ('b',)),
                                          Task('b', 'classical', ('a',))], 100).validate()

    def test_quantum_failure_trace(self):
        class Broken(MockAdapter):
            def execute(self, circuits, shots):
                raise RuntimeError('expected failure')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'expected failure'):
                execute_workflow(make_workflow('contiguous', DummyCircuit(), 10, 1, 0),
                                 Broken(), 'fifo', Path(tmp))
            trace = list(Path(tmp).glob('*.jsonl'))[0].read_text()
            self.assertIn('submission_failed', trace)


if __name__ == '__main__':
    unittest.main()
