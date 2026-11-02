import json
import tempfile
import unittest
from pathlib import Path
from qmap.workflows.telemetry import SemanticTelemetry
from qmap.workflows.export_inference_trace import export_trace
from qmap.workflows.runner import MockAdapter, execute_workflow, make_workflow


class DummyCircuit:
    num_qubits = 4


class SemanticTests(unittest.TestCase):
    def test_spans_and_parent(self):
        events = []
        recorder = SemanticTelemetry(emit=lambda name, **attrs: events.append((name, attrs)))
        with recorder.span('outer') as parent:
            with recorder.span('inner'):
                recorder.event('update', iteration_index=1)
        self.assertEqual(events[1][1]['parent_span_id'], parent)
        self.assertEqual(events[2][1]['attributes']['iteration_index'], 1)

    def test_manifest_and_inference_export(self):
        with tempfile.TemporaryDirectory() as path:
            out = Path(path)
            wf = make_workflow('batched', DummyCircuit(), 10, 3, 0)
            wf.semantic_attributes['kernel_type'] = 'trotter_ising_1d'
            result = execute_workflow(wf, MockAdapter(0,0), 'batch', out)
            manifest = json.loads((out / (result['run_id']+'.manifest.json')).read_text())
            self.assertEqual(manifest['reference']['qelf_pattern'], 'QSMC/QASP-like')
            traces = [json.loads(x) for x in Path(result['trace']).read_text().splitlines()]
            self.assertTrue(any(x['event'] == 'semantic_span_started' for x in traces))
            self.assertTrue(any(x['event'] == 'semantic_event' for x in traces))
            self.assertEqual(sum(x['event']=='task_completed' for x in traces), 4)
            filtered = out/'inference.jsonl'
            export_trace(Path(result['trace']), filtered)
            data = filtered.read_text()
            self.assertNotIn('QSMC/QASP-like', data)
            self.assertNotIn('"pattern"', data)
            self.assertNotIn('"workflow"', data)
            self.assertIn('circuit_index', data)

    def test_disable_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            wf = make_workflow('contiguous', DummyCircuit(), 10, 1, 0)
            row = execute_workflow(wf, MockAdapter(0,0), 'fifo', Path(tmp), semantic_hooks=False)
            lines = Path(row['trace']).read_text()
            self.assertNotIn('semantic_event', lines)
            self.assertIn('workflow_completed', lines)


if __name__ == '__main__':
    unittest.main()
