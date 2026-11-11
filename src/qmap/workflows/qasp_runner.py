"""QASP sampled-subspace projection diagnostic using existing QHEAT Krylov circuits.

Distinct from exact Krylov overlap / projected-H matrix calculations: computational-
basis samples select a subspace of bitstrings, and a *known model Hamiltonian* is
projected onto it. No inaccessible wavefunction overlaps are inferred from counts.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

from .runner import Task, Workflow, execute_workflow, setup_adapter


def project_sampled_subspace(state: dict[str, Any], *, qubits: int, shots: int,
                             krylov_dimension: int, j_coupling: float = 1.0,
                             h_field: float = 0.7,
                             max_basis: int = 16) -> dict[str, Any]:
    """Construct S=I and H_B in the observed computational basis; solve H_B c=E c.

    The selected basis is ranked by pooled counts (ties broken by bitstring),
    and the matrix is built from the specified nearest-neighbour TFIM, not
    reconstructed through off-diagonal quantum measurements. Units are those
    of the chosen model Hamiltonian.
    """
    import numpy as np
    from scipy.linalg import eigh
    grouped = state['counts_by_task']
    if len(grouped) != krylov_dimension:
        raise ValueError(f'Expected {krylov_dimension} circuit histograms, got {len(grouped)}')
    pooled: dict[str, int] = {}
    individual: dict[str, int] = {}
    for task_id, counts in sorted(grouped.items()):
        total = 0
        for raw, value in counts.items():
            bits = str(raw).replace(' ', '')
            if len(bits) != qubits or any(c not in '01' for c in bits):
                raise ValueError(f'Invalid {qubits}-qubit measured bitstring: {raw!r}')
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f'Invalid count for {task_id}: {value!r}')
            pooled[bits] = pooled.get(bits, 0) + value
            total += value
        if total != shots:
            raise ValueError(f'{task_id}: received {total} shots, expected {shots}')
        individual[task_id] = total
    selected = sorted((b for b, count in pooled.items() if count > 0),
                      key=lambda b: (-pooled[b], b))[:max_basis]
    if not selected:
        raise ValueError('No nonzero measured outcomes')
    # X_i connects basis states differing at precisely one qubit; ZZ is diagonal.
    dim = len(selected)
    index = {bits: i for i, bits in enumerate(selected)}
    hmat = np.zeros((dim, dim), dtype=float)
    for i, bits in enumerate(selected):
        hmat[i, i] = -j_coupling * sum(
            (1 if bits[q] == bits[q + 1] else -1) for q in range(qubits - 1))
        for q in range(qubits):
            flipped = bits[:q] + ('1' if bits[q] == '0' else '0') + bits[q + 1:]
            j = index.get(flipped)
            if j is not None:
                hmat[i, j] = -h_field
    eigenvalues, eigenvectors = eigh(hmat, check_finite=True)
    if not np.allclose(hmat, hmat.T):
        raise ValueError('Projected Hamiltonian is not symmetric')
    result = {
        'method': 'sampled_computational_basis_subspace_projection',
        'scope': 'SKQD_inspired_diagnostic_not_exact_Krylov_projection',
        'hamiltonian': {'type': 'open_chain_transverse_field_ising',
                        'j_coupling': j_coupling, 'h_field': h_field},
        'num_qubits': qubits, 'krylov_circuit_count': krylov_dimension,
        'shots_per_circuit': shots, 'total_samples': sum(pooled.values()),
        'observed_basis_size': len([x for x in pooled.values() if x > 0]),
        'retained_basis_size': dim, 'basis_selection': 'pooled_counts_descending_then_lexicographic',
        'retained_basis_bitstrings': selected,
        'retained_basis_counts': {key: pooled[key] for key in selected},
        'overlap_matrix': 'identity_in_orthonormal_computational_basis',
        'projected_hamiltonian': hmat.tolist(),
        'eigenvalues': eigenvalues.tolist(),
        'ground_energy': float(eigenvalues[0]),
        'ground_coefficients': eigenvectors[:, 0].tolist(),
        'input_counts_per_task': individual,
        'reference_limitation': ('Bitstring samples select a computational subspace. '
                                 'They do not determine <phi_i|phi_j> or <phi_i|H|phi_j> '
                                 'for Krylov states. Hamiltonian coefficients are known inputs.'),
    }
    return result


def build_qasp_workflow(*, qubits: int, shots: int, krylov_dimension: int,
                        adapter: str, trotter_steps: int = 2,
                        evolution_step: float = 0.2, max_basis: int = 16,
                        j_coupling: float = 1.0, h_field: float = 0.7,
                        root: Path | None = None) -> Workflow:
    if qubits < 2 or shots < 1 or krylov_dimension < 2 or trotter_steps < 1:
        raise ValueError('Requires qubits>=2, shots>=1, krylov_dimension>=2, trotter_steps>=1')
    if max_basis < 1 or max_basis > 2 ** qubits or evolution_step <= 0:
        raise ValueError('Requires 1<=max_basis<=2**qubits and evolution_step>0')
    if adapter == 'mock':
        circuits = [type('MockCircuit', (), {'num_qubits': qubits})() for _ in range(krylov_dimension)]
    else:
        root = root or Path(__file__).resolve().parents[3]
        src = root / 'QHEAT' / 'qasp_skqd.py'
        spec = importlib.util.spec_from_file_location('qheat_qasp_skqd', src)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Cannot load QASP kernel: {src}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        problem = module.QASPSKQD(num_qubits=qubits, krylov_dimension=krylov_dimension,
                                 trotter_steps=trotter_steps, evolution_step=evolution_step,
                                 j_coupling=j_coupling, h_field=h_field, shots=shots)
        circuits = problem.build_circuits()
        if any(qc.parameters or qc.num_clbits != qubits for qc in circuits):
            raise ValueError('QASP requires fully bound circuits with measurement')
    tasks = [Task(f'q{k}', 'quantum', (), circuit,
                  semantic_attributes={'circuit_index': k, 'krylov_index': k,
                                       'evolution_time': k * evolution_step,
                                       'shots_requested': shots, 'dependency_ids': []})
             for k, circuit in enumerate(circuits)]
    deps = tuple(t.task_id for t in tasks)
    tasks.append(Task('project', 'classical', deps,
                      semantic_attributes={'dependency_ids': list(deps),
                                           'reduction_role': 'sampled_subspace_projection',
                                           'input_type': 'krylov_bitstring_histograms_plus_model_hamiltonian',
                                           'output_type': 'reduced_eigenproblem'},
                      classical_action=lambda state: project_sampled_subspace(
                          state, qubits=qubits, shots=shots,
                          krylov_dimension=krylov_dimension, max_basis=max_basis,
                          j_coupling=j_coupling, h_field=h_field)))
    return Workflow('qasp_sampled_subspace_projection', 'QASP', 'batched', tasks, shots,
                    semantic_attributes={'kernel_type': 'qheat_krylov_trotter_ising',
                                         'num_qubits': qubits, 'krylov_dimension': krylov_dimension,
                                         'trotter_steps': trotter_steps, 'evolution_step': evolution_step,
                                         'j_coupling': j_coupling, 'h_field': h_field,
                                         'max_retained_basis_states': max_basis,
                                         'shots_per_circuit': shots,
                                         'quantum_to_classical_barriers': 1,
                                         'classical_projection': 'sampled_computational_basis',
                                         'is_exact_krylov_projection': False,
                                         'semantic_schema': 'qasp_sampled_projection_v0.1'})


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter', choices=['mock', 'aer', 'iqm-onprem'], default='mock')
    p.add_argument('--policy', choices=['fifo', 'batch', 'both'], default='both')
    p.add_argument('--qubits', type=int, default=4)
    p.add_argument('--shots', type=int, default=256)
    p.add_argument('--krylov-dimension', type=int, default=4)
    p.add_argument('--trotter-steps', type=int, default=2)
    p.add_argument('--evolution-step', type=float, default=0.2)
    p.add_argument('--max-basis', type=int, default=16)
    p.add_argument('--j-coupling', type=float, default=1.0)
    p.add_argument('--h-field', type=float, default=0.7)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--output', type=Path, default=Path('results/qelf_qasp'))
    p.add_argument('--iqm-url', default='https://qccsw.ccs.ornl.gov/default')
    p.add_argument('--mock-latency-ms', type=float, default=20.0)
    p.add_argument('--mock-per-circuit-ms', type=float, default=5.0)
    p.add_argument('--no-semantic-hooks', action='store_true')
    args = p.parse_args(argv)
    if args.repeats < 1 or args.mock_latency_ms < 0 or args.mock_per_circuit_ms < 0:
        p.error('repeats>=1, mock durations>=0 required')
    try:
        wf = build_qasp_workflow(qubits=args.qubits, shots=args.shots,
                                 krylov_dimension=args.krylov_dimension,
                                 adapter=args.adapter, trotter_steps=args.trotter_steps,
                                 evolution_step=args.evolution_step, max_basis=args.max_basis,
                                 j_coupling=args.j_coupling, h_field=args.h_field)
    except ValueError as e:
        p.error(str(e))
    adapter = setup_adapter(args)
    args.output.mkdir(parents=True, exist_ok=True)
    policies = ['fifo', 'batch'] if args.policy == 'both' else [args.policy]
    rows = []
    for rep in range(args.repeats):
        for pol in policies[rep % len(policies):] + policies[:rep % len(policies)]:
            row = execute_workflow(wf, adapter, pol, args.output,
                                   semantic_hooks=not args.no_semantic_hooks)
            projection = row.pop('classical_results')['project']
            path = args.output / f"{row['run_id']}.projection.json"
            path.write_text(json.dumps({'run_id': row['run_id'], 'projection': projection}, indent=2) + '\n')
            row.update({'repeat': rep, 'qubits': args.qubits,
                        'krylov_dimension': args.krylov_dimension,
                        'total_samples': projection['total_samples'],
                        'retained_basis_size': projection['retained_basis_size'],
                        'ground_energy': projection['ground_energy'],
                        'projection_path': str(path)})
            rows.append(row)
            print(f"QASP {pol:5}: {row['makespan_ms']:.2f} ms, "
                  f"{row['quantum_submissions']} submissions, "
                  f"{row['total_samples']} samples, "
                  f"subspace={row['retained_basis_size']}, "
                  f"E0={row['ground_energy']:.6f} | {row['trace']}")
    out = args.output / 'qasp_summary.csv'
    with out.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'QASP summary: {out}')


if __name__ == '__main__':
    main()
