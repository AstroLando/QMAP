"""QHEAT QOOL/VQE hardware-feedback runner, additive to QMAP v0.3a.

Two commuting measurement groups (Z/ZZ and X) per classical optimizer
objective evaluation. The measurement bases can be submitted together in
one backend job, but successive optimizer evaluations remain dependent.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from .runner import Trace, Workflow, QiskitBackendAdapter, setup_adapter, serialize
from .telemetry import SemanticTelemetry


def term_expectation(counts: dict[str, int], pauli: str) -> float:
    """Z-basis parity expectation for a Qiskit Pauli label (leftmost=highest qubit)."""
    total = sum(int(v) for v in counts.values())
    if total <= 0:
        raise ValueError('No measurements found')
    acc = 0
    for bits, n in counts.items():
        bits = bits.replace(' ', '')
        if len(bits) != len(pauli):
            raise ValueError(f'Bad bitstring {bits!r} for {pauli!r}')
        parity = sum(bits[i] == '1' for i, p in enumerate(pauli) if p != 'I') % 2
        acc += int(n) * (-1 if parity else 1)
    return acc / total


def estimate_pauli_energy(counts_z: dict[str, int], counts_x: dict[str, int], operator: Any) -> float:
    """Finite-shot expectation for the original QHEAT Z, ZZ and X Hamiltonian.

    All diagonal Z/ZZ terms share the computational-basis measurement;
    all single-X terms share the global X basis. Mixed-axis terms are rejected.
    """
    energy = 0.0
    for label, coeff in operator.to_list():
        if abs(complex(coeff).imag) > 1e-12:
            raise ValueError('Non-Hermitian Pauli coefficient unsupported')
        chars = set(label) - {'I'}
        if not chars or chars <= {'Z'}:
            counts = counts_z
        elif chars <= {'X'}:
            counts = counts_x
        else:
            raise ValueError(f'Mixed/unsupported measurement term {label}')
        energy += float(complex(coeff).real) * term_expectation(counts, label)
    return energy


def load_problem(root: Path, qubits: int, layers: int, shots: int):
    path = root / 'QHEAT' / 'vqe_pauli_expectation.py'
    spec = importlib.util.spec_from_file_location('qheat_vqe_pauli_expectation', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load QHEAT problem {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VQEPauliExpectation(num_qubits=qubits, layers=layers, shots=shots)


def basis_circuits(problem: Any, parameters: np.ndarray):
    problem.parameters = np.asarray(parameters, dtype=float)
    ansatz = problem.build_circuit()
    z = ansatz.copy()
    z.measure_all()
    x = ansatz.copy()
    for i in range(problem.num_qubits):
        x.h(i)
    x.measure_all()
    return [z, x]


def energy_history_summary(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """Report both minimum observed energy and last sampled energy.

    The minimum is a noisy finite-shot observation, not a validated ground
    state or a convergence estimate.
    """
    if not evaluations:
        raise ValueError('No objective evaluations')
    best = min(evaluations, key=lambda item: float(item['energy']))
    last = evaluations[-1]
    return {
        'best_observed_energy': float(best['energy']),
        'best_observed_evaluation_index': int(best['index']),
        'last_evaluated_energy': float(last['energy']),
        'last_evaluation_index': int(last['index']),
    }


def run_vqe(args, adapter: Any, *, root: Path) -> dict[str, Any]:
    problem = load_problem(root, args.qubits, args.layers, args.shots)
    min_evals = len(problem.parameters) + 2
    if args.max_evals < min_evals:
        raise ValueError(
            f'COBYLA max-evals must be >= {min_evals} for {len(problem.parameters)} parameters; '
            f'received {args.max_evals}. No jobs were submitted.'
        )
    if args.shots < 1:
        raise ValueError('Shots must be >=1')
    root_output = Path(args.output)
    root_output.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    workflow = Workflow('qool_vqe_feedback', 'QOOL', 'fragmented', [], args.shots)
    trace_path = root_output / f'{run_id}.jsonl'
    trace = Trace(trace_path, run_id, workflow, 'feedback_grouped_bases', adapter.name, adapter.mode)
    hooks = SemanticTelemetry(emit=trace.emit if not args.no_semantic_hooks else None)
    reference = {
        'manifest_schema': 'qmap-qelf-reference-0.1', 'run_id': run_id,
        'reference': {'qelf_pattern': 'QOOL', 'locality': 'fragmented',
                      'workflow_name': workflow.name},
        'experiment': {'backend': adapter.name, 'shots_per_basis': args.shots,
                       'max_objective_evaluations': args.max_evals,
                       'minimum_cobyla_evaluations': min_evals,
                       'variational_parameter_count': len(problem.parameters),
                       'measurement_bases_per_evaluation': 2,
                       'ansatz_layers': args.layers, 'qubits': args.qubits},
        'known_application_structure': {'algorithm': 'COBYLA', 'kernel_type': 'vqe_pauli_expectation',
                                        'dependent_objective_evaluations': True}
    }
    (root_output / f'{run_id}.manifest.json').write_text(json.dumps(reference, indent=2) + '\n')
    t0 = time.perf_counter_ns()
    evaluations: list[dict[str, Any]] = []
    submissions = 0
    try:
        trace.emit('workflow_started', algorithm='VQE', optimizer='COBYLA',
                   max_evals=args.max_evals, qubits=args.qubits, shots=args.shots)
        hooks.event('workflow_structure', kernel_type='vqe_pauli_expectation',
                    optimization_algorithm='COBYLA', ansatz_layers=args.layers,
                    pauli_term_count=len(problem.get_observables()),
                    measurement_groups=['Z_ZZ', 'X'], feedback_dependency=True)
        hamiltonian = problem.get_observables()

        def objective(theta: np.ndarray) -> float:
            nonlocal submissions
            iteration = len(evaluations)
            dependency = f'objective_{iteration-1}' if iteration > 0 else None
            task = f'objective_{iteration}'
            trace.emit('task_ready', task_id=task, kind='quantum_classical_objective',
                       dependency_ids=[dependency] if dependency else [])
            hooks.event('optimizer_objective_ready', iteration_index=iteration,
                        objective_evaluation_id=task, dependency_ids=[dependency] if dependency else [],
                        parameter_set_id=f'params_{iteration}', parameter_count=len(theta))
            with hooks.span('optimizer_objective', iteration_index=iteration,
                            objective_evaluation_id=task, dependency_ids=[dependency] if dependency else []):
                trace.emit('task_started', task_id=task, kind='quantum_classical_objective')
                circuits = basis_circuits(problem, theta)
                batch_id = str(uuid.uuid4())
                hooks.event('measurement_group_dispatch', batch_id=batch_id,
                            iteration_index=iteration, basis_ids=['Z_ZZ', 'X'],
                            independent_within_objective=True, shots_per_basis=args.shots)
                trace.emit('submission_started', task_ids=[task], circuit_count=2, shots=args.shots,
                           batch_id=batch_id)
                a = time.perf_counter_ns()
                try:
                    if isinstance(adapter, QiskitBackendAdapter):
                        submission = adapter.execute(circuits, args.shots, event_callback=trace.emit)
                    else:
                        submission = adapter.execute(circuits, args.shots)
                except Exception as ex:
                    trace.emit('submission_failed', task_ids=[task], batch_id=batch_id,
                               error_type=type(ex).__name__, message=str(ex))
                    raise
                submissions += 1
                trace.emit('submission_completed', job_id=submission.job_id, task_ids=[task],
                           batch_id=batch_id, elapsed_client_ms=(time.perf_counter_ns()-a)/1e6,
                           phase_durations_ms=getattr(submission, 'phase_durations_ms', {}),
                           provider_metadata=submission.provider_metadata,
                           provider_queue_ms=None, provider_execution_ms=None)
                if len(submission.counts) != 2:
                    raise ValueError('Expected two measurement-basis count dictionaries')
                energy = estimate_pauli_energy(submission.counts[0], submission.counts[1], hamiltonian)
                trace.emit('task_completed', task_id=task, job_id=submission.job_id,
                           measured_energy=energy, iteration_index=iteration,
                           counts_by_basis={'Z_ZZ': submission.counts[0], 'X': submission.counts[1]})
                hooks.event('objective_result_consumed', iteration_index=iteration,
                            objective_evaluation_id=task, measured_energy=energy,
                            parameter_set_id=f'params_{iteration}', job_id=submission.job_id)
                evaluations.append({'index': iteration, 'energy': energy, 'job_id': submission.job_id,
                                    'parameters': [float(v) for v in theta]})
                print(f'QOOL objective {iteration:02d}  energy={energy:.6f}  job={submission.job_id}')
                return energy

        result = minimize(objective, np.asarray(problem.parameters, dtype=float),
                          method='COBYLA', options={'maxiter': args.max_evals, 'rhobeg': args.rhobeg})
        makespan = (time.perf_counter_ns() - t0)/1e6
        energy_summary = energy_history_summary(evaluations)
        trace.emit('workflow_completed', makespan_ms=makespan,
                   quantum_submissions=submissions, physical_circuit_executions=2*submissions,
                   objective_evaluations=len(evaluations), final_reported_energy=float(result.fun),
                   **energy_summary,
                   optimizer_success=bool(result.success), optimizer_message=str(result.message))
    finally:
        trace.close()
    row = {'run_id': run_id, 'trace': str(trace_path), 'workflow': workflow.name,
           'pattern': 'QOOL', 'locality': 'fragmented', 'policy': 'feedback_grouped_bases',
           'backend': adapter.name, 'execution_mode': adapter.mode,
           'makespan_ms': round(makespan, 4), 'quantum_submissions': submissions,
           'quantum_circuits': 2*submissions, 'shots_per_circuit': args.shots,
           'objective_evaluations': len(evaluations),
           'final_energy': float(result.fun), 'optimizer_success': bool(result.success),
           'manifest': str(root_output / f'{run_id}.manifest.json'),
           **energy_summary}
    # Dedicated summary schema, not the existing QTES summary.csv.
    summary_path = root_output / 'qool_summary.csv'
    if summary_path.exists() and summary_path.stat().st_size:
        with summary_path.open(newline='', encoding='utf-8') as fp:
            existing_fields = next(csv.reader(fp), [])
        if existing_fields != list(row):
            # Never append new columns to a CSV with an older header.
            summary_path = root_output / 'qool_summary_v03b2.csv'
    if summary_path.exists() and summary_path.stat().st_size:
        with summary_path.open(newline='', encoding='utf-8') as fp:
            fields = next(csv.reader(fp), [])
        if fields != list(row):
            raise ValueError(f'Existing summary schema differs: {summary_path}')
    headers = not summary_path.exists() or summary_path.stat().st_size == 0
    with summary_path.open('a', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(row))
        if headers:
            writer.writeheader()
        writer.writerow(row)
    (root_output / f'{run_id}.energy.json').write_text(json.dumps(evaluations, indent=2) + '\n')
    return row


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', choices=['aer', 'iqm-onprem'], default='aer')
    parser.add_argument('--qubits', type=int, default=4)
    parser.add_argument('--layers', type=int, default=2)
    parser.add_argument('--shots', type=int, default=256)
    parser.add_argument('--max-evals', type=int, default=10)
    parser.add_argument('--rhobeg', type=float, default=0.2)
    parser.add_argument('--iqm-url', default='https://qccsw.ccs.ornl.gov/default')
    parser.add_argument('--no-semantic-hooks', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('results/qelf_workflows/qool_vqe'))
    args = parser.parse_args(argv)
    if args.qubits < 2 or args.layers < 1 or args.shots < 1 or args.rhobeg <= 0 or args.max_evals < 2:
        parser.error('Require qubits>=2, layers>=1, shots>=1, max-evals>=2, rhobeg>0')
    # Reject invalid budgets before contacting an IQM backend.
    min_evals = args.qubits * args.layers + 2
    if args.max_evals < min_evals:
        parser.error(f'COBYLA requires --max-evals >= {min_evals} for '
                     f'{args.qubits * args.layers} variational parameters; '
                     'no hardware jobs submitted')
    from .runner import setup_adapter
    adapter = setup_adapter(args)
    root = Path(__file__).resolve().parents[3]
    row = run_vqe(args, adapter, root=root)
    print(f"Completed: {row['objective_evaluations']} evaluations; "
          f"{row['quantum_submissions']} jobs; {row['quantum_circuits']} circuits; "
          f"{row['makespan_ms']} ms")
    print(f"Trace: {row['trace']}")


if __name__ == '__main__':
    main()
