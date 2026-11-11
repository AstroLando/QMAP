"""Measured QSMC sampling/aggregation dataflow using QMAP's existing runner.

No claims of provider queue or QPU execution duration are inferred from client waits.
Run with ``python -m qmap.workflows.qsmc_runner --help``.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .runner import Task, Workflow, execute_workflow, setup_adapter


def aggregate_counts(state: dict[str, Any]) -> dict[str, Any]:
    """Compute observed empirical distribution from per-circuit shot histograms.

    Qiskit bitstrings can include register-space separators; strip them before
    computing parity and mean Z. This is descriptive sampling, not a claim of
    a quantum speedup or a fully fledged Monte Carlo estimator.
    """
    grouped = state['counts_by_task']
    if not grouped:
        raise ValueError('No sampled counts available')
    totals: dict[str, int] = {}
    per_circuit: dict[str, dict[str, Any]] = {}
    width: int | None = None
    for task_id, counts in sorted(grouped.items()):
        count = 0
        for raw, value in counts.items():
            bits = str(raw).replace(' ', '')
            if not bits or any(c not in '01' for c in bits):
                raise ValueError(f'Unsupported bitstring: {raw!r}')
            if width is None:
                width = len(bits)
            if len(bits) != width or int(value) < 0 or int(value) != value:
                raise ValueError('Inconsistent bitstring widths or invalid counts')
            totals[bits] = totals.get(bits, 0) + int(value)
            count += int(value)
        if count == 0:
            raise ValueError('Empty circuit histogram')
        per_circuit[task_id] = {'shots_received': count, 'distinct_bitstrings': len(counts)}
    n = sum(totals.values())
    probability = {k: v / n for k, v in sorted(totals.items())}
    # Parity observable Z_0 * ... * Z_(n-1), with sampling standard error.
    parity = sum(((-1) ** bits.count('1')) * count for bits, count in totals.items()) / n
    parity_se = ((max(0.0, 1.0 - parity * parity) / n) ** 0.5)
    mean_z = [sum((1 if bits[-1 - i] == '0' else -1) * c for bits, c in totals.items()) / n
              for i in range(width or 0)]
    return {'total_samples': n, 'circuit_count': len(grouped), 'num_qubits': width,
            'probabilities': probability, 'counts': dict(sorted(totals.items())),
            'per_circuit': per_circuit, 'parity_mean': parity,
            'parity_standard_error': parity_se, 'mean_z_per_qubit': mean_z,
            'aggregation_method': 'pooled_empirical_distribution',
            'estimator_scope': 'descriptive_sampling_diagnostic'}


def build_qsmc_workflow(*, qubits: int, shots: int, evaluations: int, adapter: str,
                        root: Path | None = None) -> Workflow:
    """A circuit ensemble followed by one real classical aggregation barrier.

    Each circuit has a different deterministic rotation-vector offset, so that
    the ensemble is not a repetition of a single circuit with a decorative DAG.
    """
    if qubits < 2 or shots < 1 or evaluations < 1:
        raise ValueError('Require qubits>=2, shots>=1, evaluations>=1')
    if adapter == 'mock':
        circuits = [type('MockCircuit', (), {'num_qubits': qubits})() for _ in range(evaluations)]
    else:
        import importlib.util
        root = root or Path(__file__).resolve().parents[3]
        src = root / 'QHEAT' / 'qsmc_sampling.py'
        spec = importlib.util.spec_from_file_location('qheat_qsmc_sampling', src)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Cannot load {src}')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import numpy as np
        circuits = []
        for i in range(evaluations):
            # Bounded deterministic perturbation, no change to the original kernel.
            params = np.clip(np.linspace(0.2, 1.0, qubits * 2) +
                             (i - (evaluations - 1) / 2) * 0.04, 0.0, 3.14159)
            problem = mod.QSMCSampling(num_qubits=qubits, layers=2, shots=shots,
                                       parameters=params)
            qc = problem.build_circuit()
            if qc.parameters or qc.num_clbits != qubits:
                raise ValueError('QSMC requires fully bound circuits with measurement')
            circuits.append(qc)
    tasks = [Task(f'q{i}', 'quantum', (), circuit,
                  semantic_attributes={'circuit_index': i, 'ensemble_member_id': f'sample_{i}',
                                       'dependency_ids': [], 'shots_requested': shots,
                                       'parameter_offset_rad': round((i - (evaluations - 1) / 2) * 0.04, 6)})
             for i, circuit in enumerate(circuits)]
    deps = tuple(t.task_id for t in tasks)
    tasks.append(Task('reduce', 'classical', deps, semantic_attributes={
        'dependency_ids': list(deps), 'reduction_role': 'empirical_distribution',
        'input_type': 'bitstring_histograms', 'output_type': 'sampling_statistics'},
        classical_action=aggregate_counts))
    return Workflow('qsmc_sampling_aggregation', 'QSMC', 'batched', tasks, shots,
                    semantic_attributes={'kernel_type': 'qheat_correlated_sampling',
                                         'execution_granularity': 'parameterized_circuit_ensemble',
                                         'ensemble_size': evaluations, 'shots_per_circuit': shots,
                                         'num_qubits': qubits, 'circuit_layers': 2,
                                         'classical_aggregation': 'pooled_histograms',
                                         'parameter_sweep': 'deterministic_bounded_offsets',
                                         'quantum_to_classical_barriers': 1,
                                         'semantic_schema': 'qsmc_sampling_v0.1'})


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter', choices=['mock', 'aer', 'iqm-onprem'], default='mock')
    p.add_argument('--policy', choices=['fifo', 'batch', 'both'], default='both')
    p.add_argument('--qubits', type=int, default=4)
    p.add_argument('--shots', type=int, default=100)
    p.add_argument('--evaluations', type=int, default=4)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--output', type=Path, default=Path('results/qelf_qsmc'))
    p.add_argument('--iqm-url', default='https://qccsw.ccs.ornl.gov/default')
    p.add_argument('--mock-latency-ms', type=float, default=20)
    p.add_argument('--mock-per-circuit-ms', type=float, default=5)
    p.add_argument('--no-semantic-hooks', action='store_true')
    args = p.parse_args(argv)
    if args.qubits < 2 or min(args.shots, args.evaluations, args.repeats) < 1:
        p.error('qubits>=2, shots/evaluations/repeats>=1 required')
    if args.mock_latency_ms < 0 or args.mock_per_circuit_ms < 0:
        p.error('mock latency values must be nonnegative')
    adapter = setup_adapter(args)
    args.output.mkdir(parents=True, exist_ok=True)
    policies = ['fifo', 'batch'] if args.policy == 'both' else [args.policy]
    rows: list[dict[str, Any]] = []
    for rep in range(args.repeats):
        for policy in (policies[rep % len(policies):] + policies[:rep % len(policies)]):
            wf = build_qsmc_workflow(qubits=args.qubits, shots=args.shots,
                                     evaluations=args.evaluations, adapter=args.adapter)
            result = execute_workflow(wf, adapter, policy, args.output,
                                      semantic_hooks=not args.no_semantic_hooks)
            # Aggregate results live in the trace as well as in a sidecar.
            aggregation = result.pop('classical_results')['reduce']
            summary = args.output / f"{result['run_id']}.aggregation.json"
            summary.write_text(json.dumps({'run_id': result['run_id'], 'sampling': aggregation}, indent=2) + '\n')
            result.update({'repeat': rep, 'qubits': args.qubits, 'kernel': 'qsmc',
                           'aggregation_path': str(summary),
                           'total_samples': aggregation['total_samples'],
                           'parity_mean': aggregation['parity_mean']})
            rows.append(result)
            print(f"QSMC {policy:5s}: {result['makespan_ms']:.2f} ms, "
                  f"{result['quantum_submissions']} submissions, "
                  f"{result['total_samples']} samples | {result['trace']}")
    out = args.output / 'qsmc_summary.csv'
    with out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'QSMC summary: {out}')


if __name__ == '__main__':
    main()
