"""QMAP QELF workflow runner v0.1.

Controlled, measured DAG experiments using either a deterministic *mock* backend
or a Qiskit backend.run() adapter. Mock timings are NOT hardware measurements.
The runner supports logical execution dependencies, and uses one physical job
for each ready batch when --policy batch is selected and the adapter allows it.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): serialize(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [serialize(x) for x in v]
    return str(v)


@dataclass
class Task:
    task_id: str
    kind: str  # "quantum" or "classical"
    deps: tuple[str, ...] = ()
    circuit: Any = None
    duration_ms: float = 0.0


@dataclass
class Workflow:
    name: str
    pattern: str
    locality: str
    tasks: list[Task]
    shots: int

    def validate(self) -> None:
        ids = {t.task_id for t in self.tasks}
        if len(ids) != len(self.tasks):
            raise ValueError('Duplicate task IDs')
        if not self.tasks:
            raise ValueError('Workflow must contain tasks')
        if self.shots < 1:
            raise ValueError('shots must be positive')
        for task in self.tasks:
            if task.kind not in ('quantum', 'classical'):
                raise ValueError(f'Unsupported task kind: {task.kind}')
            if task.kind == 'quantum' and task.circuit is None:
                raise ValueError(f'Missing quantum circuit: {task.task_id}')
            if set(task.deps) - ids or task.task_id in task.deps:
                raise ValueError(f'Invalid dependencies for {task.task_id}')
        done: set[str] = set()
        while len(done) < len(ids):
            ready = {t.task_id for t in self.tasks if t.task_id not in done and set(t.deps) <= done}
            if not ready:
                raise ValueError('Dependency cycle detected')
            done |= ready


class Trace:
    def __init__(self, path: Path, run_id: str, workflow: Workflow, policy: str, backend: str, mode: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.handle = path.open('w', encoding='utf-8')
        self.run_id = run_id
        self.workflow = workflow
        self.policy = policy
        self.backend = backend
        self.mode = mode
        self.t0 = time.perf_counter_ns()

    def emit(self, event: str, *, task_id: str | None = None, job_id: str | None = None, **details: Any) -> None:
        record = {
            'schema_version': 'qmap-qelf-events-0.1',
            'run_id': self.run_id, 'workflow': self.workflow.name,
            'pattern': self.workflow.pattern, 'locality': self.workflow.locality,
            'policy': self.policy, 'backend': self.backend, 'execution_mode': self.mode,
            'event': event, 'task_id': task_id, 'job_id': job_id,
            'utc_time': utc_now(), 'monotonic_offset_ns': time.perf_counter_ns() - self.t0,
            'data': serialize(details),
        }
        self.handle.write(json.dumps(record) + '\n')
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


@dataclass
class Submission:
    job_id: str
    counts: list[dict[str, int]]
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    phase_durations_ms: dict[str, float] = field(default_factory=dict)


class Adapter(Protocol):
    name: str
    mode: str
    def execute(self, circuits: list[Any], shots: int) -> Submission: ...


class MockAdapter:
    """Deterministic counts with optional sleeps for end-to-end functional testing.

    Not a quantum circuit simulator and not an empirical timing model.
    """
    name = 'mock'
    mode = 'synthetic'

    def __init__(self, latency_ms: float = 20.0, per_circuit_ms: float = 5.0):
        self.latency_ms = latency_ms
        self.per_circuit_ms = per_circuit_ms

    def execute(self, circuits: list[Any], shots: int) -> Submission:
        time.sleep((self.latency_ms + len(circuits) * self.per_circuit_ms) / 1000)
        return Submission(str(uuid.uuid4()), [{'0' * getattr(c, 'num_qubits', 4): shots} for c in circuits],
                          {'mock_latency_ms': self.latency_ms, 'mock_per_circuit_ms': self.per_circuit_ms})


class QiskitBackendAdapter:
    """Generic backend.run adapter; actual support for multi-circuit jobs is backend dependent."""
    mode = 'hardware_or_provider_simulator'

    def __init__(self, backend: Any, name: str):
        self.backend, self.name = backend, name

    def execute(self, circuits: list[Any], shots: int,
                event_callback: Callable[..., None] | None = None) -> Submission:
        """Execute a job and record client-side phases without assuming IQM queue fields.

        Event callback receives (event, **data), and is invoked synchronously.
        Failure events preserve the phase being attempted.
        """
        phases: dict[str, float] = {}
        def emit(event: str, **data: Any) -> None:
            if event_callback is not None:
                event_callback(event, **data)
        def time_phase(phase: str, operation: Callable[[], Any], **fields: Any) -> Any:
            emit(phase + '_started', **fields)
            t0 = time.perf_counter_ns()
            try:
                value = operation()
            except Exception as exc:
                emit(phase + '_failed', elapsed_ms=(time.perf_counter_ns()-t0)/1e6,
                     error_type=type(exc).__name__, message=str(exc), **fields)
                raise
            elapsed = (time.perf_counter_ns()-t0)/1e6
            phases[phase + '_ms'] = elapsed
            emit(phase + '_completed', elapsed_ms=elapsed, **fields)
            return value

        # Do not silently transform or compile on non-IQM backends.
        if self.name == 'iqm_onprem':
            from qiskit import transpile
            circuits = time_phase('transpilation', lambda: transpile(
                circuits, backend=self.backend, optimization_level=1,
                seed_transpiler=42), circuit_count=len(circuits))

        job = time_phase('job_submission', lambda: self.backend.run(
            circuits if len(circuits) > 1 else circuits[0], shots=shots),
            circuit_count=len(circuits), shots=shots)
        job_id = str(job.job_id()) if callable(getattr(job, 'job_id', None)) else str(getattr(job, 'job_id', 'unknown'))
        emit('job_accepted_by_client', job_id=job_id,
             interpretation='backend.run returned; provider queue acceptance NOT confirmed')
        result = time_phase('result_wait', job.result, job_id=job_id)

        def extract_counts() -> list[dict[str, int]]:
            counts = []
            for i in range(len(circuits)):
                try:
                    counts.append(serialize(result.get_counts(i if len(circuits) > 1 else None)))
                except (TypeError, KeyError):
                    counts.append(serialize(result.get_counts()))
            return counts
        counts = time_phase('result_decoding', extract_counts, job_id=job_id)

        meta: dict[str, Any] = {}
        # Preserve only documented/public-looking surfaces; never serialize full job
        # objects, backend configuration, client state, or credentials.
        for key, obj in (('result_metadata', result), ('result_date', result),
                         ('result_time_taken', result)):
            attr = {'result_metadata':'metadata', 'result_date':'date',
                    'result_time_taken':'time_taken'}[key]
            try:
                value = getattr(obj, attr, None)
                if value is not None:
                    meta[key] = serialize(value)
            except Exception as ex:
                meta[key + '_error'] = type(ex).__name__
        for key in ('status', 'time_per_step', 'timestamps'):
            try:
                value = getattr(job, key, None)
                if value is not None:
                    meta['job_' + key] = serialize(value() if callable(value) else value)
            except Exception as ex:
                meta['job_' + key + '_error'] = type(ex).__name__
        # Provider metadata is unnormalized. Never infer queue or execution
        # duration from the client-side result-wait interval.
        emit('provider_metadata_collected', job_id=job_id,
             raw_provider_metadata=meta, metadata_provenance='job_and_result_objects')
        return Submission(job_id, counts, meta, phases)


def load_qheat_circuit(name: str, n: int, shots: int, root: Path) -> Any:
    """Reuse QHEAT's existing circuit constructors by filesystem path."""
    mapping = {'qtes': ('qtes_trotter_ising.py', 'QTESTrotterIsing', 'build_circuit'),
               'qsmc': ('qsmc_sampling.py', 'QSMCSampling', 'build_sampling_circuit')}
    filename, classname, method = mapping[name]
    path = root / 'QHEAT' / filename
    spec = importlib.util.spec_from_file_location(f'qheat_{name}', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    instance = getattr(module, classname)(num_qubits=n, shots=shots)
    circuit = getattr(instance, method)()
    if getattr(circuit, 'parameters', None):
        # QSMC circuits contain free parameters; bind deterministic QHEAT defaults.
        if name == 'qsmc':
            circuit = circuit.assign_parameters(dict(zip(instance.theta, instance.parameters)))
        else:
            raise ValueError('Unbound circuit parameters')
    return circuit


def make_workflow(pattern: str, circuit: Any, shots: int, evaluations: int,
                  classical_ms: float) -> Workflow:
    """Same circuit/evaluations/shots; change only scheduling dependencies.

    'fragmented': quantum -> classical -> quantum -> ...
    'batched': independent quantum tasks -> one classical reduction
    'contiguous': one quantum job with one circuit (different total physical work).
    Contiguous is separate and MUST NOT be treated as work-matched to others.
    """
    if evaluations < 1 or classical_ms < 0:
        raise ValueError('Invalid evaluations/classical_ms')
    tasks: list[Task] = []
    if pattern == 'fragmented':
        prev: tuple[str, ...] = ()
        for i in range(evaluations):
            q, c = f'q{i}', f'c{i}'
            tasks.append(Task(q, 'quantum', prev, circuit))
            tasks.append(Task(c, 'classical', (q,), duration_ms=classical_ms))
            prev = (c,)
        return Workflow('controlled_fragmented', 'QOOL-like', 'fragmented', tasks, shots)
    if pattern == 'batched':
        for i in range(evaluations):
            tasks.append(Task(f'q{i}', 'quantum', (), circuit))
        tasks.append(Task('reduce', 'classical', tuple(f'q{i}' for i in range(evaluations)),
                          duration_ms=classical_ms * evaluations))
        return Workflow('controlled_batched', 'QSMC/QASP-like', 'batched', tasks, shots)
    if pattern == 'contiguous':
        return Workflow('qtes_single', 'QTES', 'contiguous', [Task('q0', 'quantum', (), circuit)], shots)
    raise ValueError(f'Unknown pattern {pattern}')


def execute_workflow(workflow: Workflow, adapter: Adapter, policy: str, output: Path) -> dict[str, Any]:
    workflow.validate()
    if policy not in ('fifo', 'batch'):
        raise ValueError(f'Unknown policy {policy}')
    run_id = str(uuid.uuid4())
    trace_path = output / f'{run_id}.jsonl'
    trace = Trace(trace_path, run_id, workflow, policy, adapter.name, adapter.mode)
    done: set[str] = set()
    quantum_submissions = 0
    measured_task_ms: dict[str, float] = {}
    t_start = time.perf_counter_ns()
    try:
        trace.emit('workflow_started', shots=workflow.shots, tasks=len(workflow.tasks))
        while len(done) < len(workflow.tasks):
            ready = [t for t in workflow.tasks if t.task_id not in done and set(t.deps) <= done]
            if not ready:
                raise ValueError('Workflow stalled: dependency cycle')
            # Classical operations are serialized in this v0.1 runner.
            classical = next((t for t in ready if t.kind == 'classical'), None)
            if classical is not None:
                trace.emit('task_ready', task_id=classical.task_id)
                trace.emit('task_started', task_id=classical.task_id, kind='classical')
                a = time.perf_counter_ns()
                time.sleep(classical.duration_ms / 1000)
                measured_task_ms[classical.task_id] = (time.perf_counter_ns() - a) / 1e6
                trace.emit('task_completed', task_id=classical.task_id, kind='classical',
                           elapsed_ms=measured_task_ms[classical.task_id])
                done.add(classical.task_id)
                continue
            quantum = [t for t in ready if t.kind == 'quantum']
            selected = quantum if policy == 'batch' else quantum[:1]
            for t in selected:
                trace.emit('task_ready', task_id=t.task_id)
            trace.emit('submission_started', task_ids=[t.task_id for t in selected],
                       circuit_count=len(selected), shots=workflow.shots)
            a = time.perf_counter_ns()
            try:
                if isinstance(adapter, QiskitBackendAdapter):
                    submission = adapter.execute(
                        [t.circuit for t in selected], workflow.shots,
                        event_callback=lambda event, **fields: trace.emit(
                            event, task_ids=[t.task_id for t in selected], **fields))
                else:
                    submission = adapter.execute([t.circuit for t in selected], workflow.shots)
            except Exception as exc:
                trace.emit('submission_failed', task_ids=[t.task_id for t in selected],
                           error_type=type(exc).__name__, message=str(exc))
                raise
            elapsed = (time.perf_counter_ns() - a) / 1e6
            quantum_submissions += 1
            trace.emit('submission_completed', job_id=submission.job_id,
                       task_ids=[t.task_id for t in selected], elapsed_client_ms=elapsed,
                       provider_metadata=submission.provider_metadata,
                       phase_durations_ms=submission.phase_durations_ms,
                       duration_semantics='client_observed_adapter_call_including_transpilation_and_metadata',
                       provider_queue_ms=None, provider_execution_ms=None)
            for i, t in enumerate(selected):
                # Shared elapsed time is *not* divisible into per-circuit QPU times.
                trace.emit('task_completed', task_id=t.task_id, job_id=submission.job_id,
                           kind='quantum', counts=submission.counts[i] if i < len(submission.counts) else None)
                done.add(t.task_id)
        makespan_ms = (time.perf_counter_ns() - t_start) / 1e6
        trace.emit('workflow_completed', makespan_ms=makespan_ms,
                   quantum_submissions=quantum_submissions,
                   physical_circuit_executions=sum(t.kind == 'quantum' for t in workflow.tasks),
                   classical_time_ms=sum(measured_task_ms.values()))
    finally:
        trace.close()
    return {'run_id': run_id, 'trace': str(trace_path), 'workflow': workflow.name,
            'pattern': workflow.pattern, 'locality': workflow.locality,
            'policy': policy, 'backend': adapter.name, 'execution_mode': adapter.mode,
            'makespan_ms': round(makespan_ms, 4), 'quantum_submissions': quantum_submissions,
            'quantum_circuits': sum(t.kind == 'quantum' for t in workflow.tasks),
            'shots_per_circuit': workflow.shots,
            'classical_time_ms': round(sum(measured_task_ms.values()), 4)}


def setup_adapter(args: argparse.Namespace) -> Adapter:
    if args.adapter == 'mock':
        return MockAdapter(args.mock_latency_ms, args.mock_per_circuit_ms)
    if args.adapter == 'aer':
        from qiskit_aer import AerSimulator
        return QiskitBackendAdapter(AerSimulator(), 'aer_simulator')
    if args.adapter == 'iqm-onprem':
        from iqm.qiskit_iqm import IQMProvider
        token = os.environ.get('IQM_ONPREM_TOKEN')
        if not token:
            raise RuntimeError('IQM_ONPREM_TOKEN must be set for on-prem runs')
        old = os.environ.pop('IQM_TOKEN', None)
        try:
            provider = IQMProvider(args.iqm_url, token=token)
            backend = provider.get_backend()
        finally:
            if old is not None:
                os.environ['IQM_TOKEN'] = old
        return QiskitBackendAdapter(backend, 'iqm_onprem')
    raise ValueError(args.adapter)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', choices=['mock', 'aer', 'iqm-onprem'], default='mock')
    parser.add_argument('--policy', choices=['fifo', 'batch', 'both'], default='both')
    parser.add_argument('--pattern', choices=['fragmented', 'batched', 'contiguous', 'all'], default='all')
    parser.add_argument('--kernel', choices=['qtes', 'qsmc'], default='qtes')
    parser.add_argument('--qubits', type=int, default=4)
    parser.add_argument('--shots', type=int, default=1024)
    parser.add_argument('--evaluations', type=int, default=4)
    parser.add_argument('--classical-ms', type=float, default=5.0)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--mock-latency-ms', type=float, default=20.0)
    parser.add_argument('--mock-per-circuit-ms', type=float, default=5.0)
    parser.add_argument('--iqm-url', default='https://qccsw.ccs.ornl.gov/default')
    parser.add_argument('--output', type=Path, default=Path('results/qelf_workflows'))
    args = parser.parse_args(argv)
    if args.qubits < 2 or args.shots < 1 or args.evaluations < 1 or args.repeats < 1:
        parser.error('qubits>=2, shots>=1, evaluations>=1, repeats>=1 required')
    if args.classical_ms < 0 or args.mock_latency_ms < 0 or args.mock_per_circuit_ms < 0:
        parser.error('durations must be nonnegative')
    # mock adapter can operate without Qiskit; real adapters require QHEAT circuits.
    root = Path(__file__).resolve().parents[3]
    if args.adapter == 'mock':
        circuit = type('MockCircuit', (), {'num_qubits': args.qubits})()
    else:
        circuit = load_qheat_circuit(args.kernel, args.qubits, args.shots, root)
    adapter = setup_adapter(args)
    args.output.mkdir(parents=True, exist_ok=True)
    patterns = ('fragmented', 'batched', 'contiguous') if args.pattern == 'all' else (args.pattern,)
    policies = ('fifo', 'batch') if args.policy == 'both' else (args.policy,)
    rows = []
    for rep in range(args.repeats):
        # Rotate pattern/policy order to mitigate simple temporal order confounding.
        combos = [(p, pol) for p in patterns for pol in policies]
        combos = combos[rep % len(combos):] + combos[:rep % len(combos)]
        for pattern, policy in combos:
            workflow = make_workflow(pattern, circuit, args.shots, args.evaluations, args.classical_ms)
            row = execute_workflow(workflow, adapter, policy, args.output)
            row.update({'repeat': rep, 'kernel': args.kernel, 'qubits': args.qubits})
            rows.append(row)
            print(f"{pattern:12} {policy:5} {row['makespan_ms']:9.2f} ms "
                  f"{row['quantum_submissions']:2} submissions | {row['trace']}")
    csv_path = args.output / 'summary.csv'
    write_headers = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open('a', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        if write_headers:
            writer.writeheader()
        writer.writerows(rows)
    for p in patterns:
        for pol in policies:
            values = [x['makespan_ms'] for x in rows if x['locality'] == p and x['policy'] == pol]
            if values:
                print(f'Median {p:12} {pol:5}: {statistics.median(values):.2f} ms')
    print(f'Summary: {csv_path}')


if __name__ == '__main__':
    main()
