import json
import numpy as np
import pytest
from qmap.workflows.qasp_runner import build_qasp_workflow, project_sampled_subspace
from qmap.workflows.runner import MockAdapter, execute_workflow


def test_projection_known_subspace_and_eigenpair():
    state = {'counts_by_task': {'q0': {'00': 6, '01': 4}, 'q1': {'00': 5, '01': 5}}}
    result = project_sampled_subspace(state, qubits=2, shots=10, krylov_dimension=2)
    assert result['retained_basis_size'] == 2
    assert result['total_samples'] == 20
    assert result['retained_basis_bitstrings'] == ['00', '01']
    expected = np.array([[-1., -.7], [-.7, 1.]])
    assert np.allclose(result['projected_hamiltonian'], expected)
    assert result['ground_energy'] == pytest.approx(np.linalg.eigvalsh(expected)[0])


@pytest.mark.parametrize('policy,expected_submissions', [('fifo', 4), ('batch', 1)])
def test_qasp_mock_round_trip(tmp_path, policy, expected_submissions):
    wf = build_qasp_workflow(qubits=4, shots=100, krylov_dimension=4, adapter='mock')
    row = execute_workflow(wf, MockAdapter(latency_ms=0, per_circuit_ms=0), policy, tmp_path)
    assert row['quantum_submissions'] == expected_submissions
    result = row['classical_results']['project']
    assert result['total_samples'] == 400
    assert result['retained_basis_size'] == 1  # deterministic zero-only mock
    trace = [json.loads(line) for line in open(row['trace'])]
    assert sum(e['event'] == 'task_completed' and e['data'].get('kind') == 'quantum' for e in trace) == 4
    assert any(e['event'] == 'classical_result_computed' for e in trace)
    manifest = tmp_path / f"{row['run_id']}.manifest.json"
    assert json.loads(manifest.read_text())['reference']['qelf_pattern'] == 'QASP'


def test_rejects_incomplete_histogram():
    with pytest.raises(ValueError, match='received'):
        project_sampled_subspace({'counts_by_task': {'q0': {'00': 9}, 'q1': {'00': 10}}},
                                 qubits=2, shots=10, krylov_dimension=2)
