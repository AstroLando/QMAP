import importlib.util
from pathlib import Path
import unittest

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reconstruct',BASE/'src/qmap/workflows/reconstruct_dag.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReconstructionTests(unittest.TestCase):
    def test_qtes_batch_dag(self):
        g=module.infer_graph(module.load_events(BASE/'examples/qtes_pathfinder_sample.jsonl'))
        self.assertEqual(len(g['dispatches']),1)
        self.assertEqual(len(g['dispatches'][0]['task_ids']),4)
        self.assertEqual(sum(x['id']=='reduce' for x in g['nodes']),1)
        self.assertEqual(len([x for x in g['edges'] if x['type']=='depends_on']),4)
        self.assertIsNone(g['dispatches'][0]['provider_queue_ms'])
    def test_qool_feedback_chain(self):
        g=module.infer_graph(module.load_events(BASE/'examples/qool_pathfinder_sample.jsonl'))
        self.assertEqual(len(g['dispatches']),10)
        self.assertEqual(len([x for x in g['edges'] if x['type']=='depends_on']),9)
        self.assertEqual(g['nodes'][0]['metadata']['measured_energy'],1.0960000000000003)
        self.assertTrue(all(x['phases_ms'].get('result_wait_ms') for x in g['dispatches']))

if __name__=='__main__':unittest.main()
