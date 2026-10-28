# QMAP / QHEAT — QELF Workflow Runner

**Status: v0.2 timing instrumentation; validated on Qiskit Aer and ORNL Pathfinder (IQM) in October 2026.**

This is a controlled workflow-dispatch and telemetry harness, designed to study how hybrid DAG structure and job granularity affect client-observed system costs. It complements the existing QMAP QC-only benchmarks and QHEAT scientific kernel examples; it does not replace either. The `runner.py` in `src/qmap/workflows/` is the execution code. This document records the **tested** invocations and experimental interpretation.

## Repository layout

```text
QMAP/
├── QHEAT/                         # existing scientific kernel examples
├── WORKFLOW_RUNNER_README.md      # this document
├── examples/
│   ├── qelf_mock_smoke.sh
│   ├── qelf_aer_smoke.sh
│   └── qelf_pathfinder_pilot.sh
├── src/qmap/
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── runner.py             # v0.2 timing-instrumented runner
│   └── ...                       # existing QMAP code unchanged
└── results/qelf_workflows/        # generated; not source code
```

## Environment and credentials

Use the existing QMAP IQM Conda environment; Pathfinder has been exercised in `qmap_iqm` (Python 3.11). The local/Aer paths require their own installed Qiskit dependencies.

```bash
conda activate qmap_iqm
cd /Users/r51/QMAP
```

To enable Pathfinder access, in the shell where jobs will run:

```bash
set -a
source tokens.env
set +a
echo "${IQM_ONPREM_TOKEN:+Pathfinder token loaded}"
```

Keep `tokens.env` out of Git (`.gitignore`); do not commit tokens, generated provider credentials, or full raw provider secrets. The runner expects `IQM_ONPREM_TOKEN` in the environment. If `IQM_TOKEN` is set for another service, the runner temporarily removes and restores it when creating the IQM provider. The default Pathfinder URL is in the runner, but the IQM SDK may warn that the URL form is deprecated; verify the updated endpoint through ORNL/IQM documentation rather than guessing.

## Verified command sequence

All commands below run from the repo root. `--output` isolates generated traces and summary CSVs.

### 1. Smoke-test the DAG runner without hardware

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter mock --pattern all --policy both --repeats 3 \
  --output results/qelf_workflows/mock_smoke
```

Mock counts and times are artificial; **never interpret these as QPU performance**.

### 2. Aer QTES: one circuit

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter aer --kernel qtes --qubits 4 --shots 100 \
  --pattern contiguous --policy fifo --repeats 1 \
  --output results/qelf_workflows/aer_single
```

### 3. Aer QTES: four evaluations, both dispatch policies

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter aer --kernel qtes --qubits 4 --shots 100 \
  --pattern batched --policy both --evaluations 4 --repeats 3 \
  --output results/qelf_workflows/aer_dispatch
```

### 4. Pathfinder QTES: one hardware job

Run only with authorization/allocation, loaded credentials and a suitable hardware configuration:

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter iqm-onprem --kernel qtes --qubits 4 --shots 100 \
  --pattern contiguous --policy fifo --repeats 1 \
  --output results/qelf_workflows/pathfinder_single
```

The v0.2 runner transpiles IQM circuits with `transpile(..., backend=self.backend, optimization_level=1, seed_transpiler=42)` because the untranspiled QTES circuit contains instructions (e.g. `h`) not accepted by Pathfinder's native ISA.

### 5. Pathfinder FIFO-versus-batch dispatch pilot

**FIFO: four independent circuit evaluations, submitted as four jobs per repetition:**

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter iqm-onprem --kernel qtes --qubits 4 --shots 100 \
  --pattern batched --policy fifo --evaluations 4 --repeats 3 \
  --output results/qelf_workflows/fifo
```

**Batch: the same four independent circuit evaluations, one job per repetition:**

```bash
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter iqm-onprem --kernel qtes --qubits 4 --shots 100 \
  --pattern batched --policy batch --evaluations 4 --repeats 3 \
  --output results/qelf_workflows/batch
```

**Why `--pattern batched` in both cases?** The DAG and scientific circuit workload are held fixed; `--policy` changes the submission granularity. `--pattern fragmented` is a separate dependency-structure experiment, not the same controlled comparison. `--pattern contiguous` uses a single quantum evaluation and is not equal-work matched to four-evaluation workflows.

The batch path requires multi-circuit jobs on the provider; that behavior was verified in the initial Pathfinder pilot, not guaranteed on other backends.

## Pilot observations (Oct 2026; 3 repetitions per policy)

| Metric | FIFO | Batch |
| --- | ---: | ---: |
| QTES circuits per workflow | 4 | 4 |
| Shots per circuit | 100 | 100 |
| Jobs per workflow | 4 | 1 |
| Mean client-observed makespan | 8.646 s | 2.965 s |
| Mean accumulated submission phase | 2.226 s | 0.543 s |
| Mean accumulated result-wait phase | 6.252 s | 2.269 s |
| Mean accumulated transpilation phase | 0.141 s | 0.129 s |

The observed mean makespan reduction is **approximately 65.7%** (2.92×). This is a small **non-interleaved pilot**, not a statistically controlled estimate of pattern-aware scheduling improvement. Phase intervals are client-side timings; `result_wait` can contain provider queue time, QPU execution, network and polling. These cannot yet be separated with the current provider metadata. QTES uses a first-order Trotterized 1-D transverse-field Ising kernel; in this pilot the four QTES circuits are *independent instances*, forming a batched higher-level DAG.

## Trace format

Each run generates a `<run_id>.jsonl` with events and a `summary.csv` row in its selected output directory. The JSONL includes run/workflow/policy/backend IDs, UTC timestamps, monotonic offsets, task IDs, job IDs, and event `data`. The v0.2 adapter adds:

- `transpilation_started` / `transpilation_completed` (IQM path)
- `job_submission_started` / `job_submission_completed`
- `job_accepted_by_client` (client-side return **not** server-queue acceptance)
- `result_wait_started` / `result_wait_completed`
- `result_decoding_started` / `result_decoding_completed`
- `provider_metadata_collected` and phase error events where applicable

The legacy `submission_completed` event and CSV fields remain for compatibility. Provider queue and execution durations remain `null` unless verified provider lifecycle timestamps become available; do not substitute the local blocking duration for either. **Provider metadata may contain sensitive infrastructure details; review traces before publishing.**

## What this version does *not* do

1. It is not a production QPASS scheduler: policies are synchronous FIFO or grouping currently ready circuits into one job. It does not reserve resources, issue concurrent jobs, or perform critical-path prioritization.
2. The controlled DAGs do not implement adaptive VQE feedback or hardware-measured SKQD overlaps; the classical tasks are timed artificial workloads (`sleep`). Separate QHEAT examples demonstrate the scientific structures.
3. Circuit construction occurs before the measured workflow interval; compilation occurs inside the IQM adapter and is timed separately. For stronger policy isolation, a later version should pretranspile or cache circuits.
4. Provider queue time and QPU execution time are not resolved. `result_wait` is **client-observed** blocking duration, not QPU service time.
5. Comparisons need warm-up management, interleaved randomized trials, repeat counts, and provider-side timing validation before inferential claims or cross-vendor ranking.

## Next controlled experiment

For a follow-up pilot, use `--pattern batched --policy both --evaluations 4 --repeats 10` in a **new output directory**, rather than mixing with these first three-repetition runs. The runner rotates the order across repetitions; it does not fully randomize policy order. Use the same backend, shots, circuit and environmental settings. Record allocation, calibration and server status outside the trace when possible.

## Reproducibility notes

Record your actual package versions (`python --version`, `pip freeze` or `conda env export --from-history`), circuit parameters, backend target/calibration, git commit SHA, date/time, and allocation. Avoid committing raw result files or credentials by default; publish scrubbed traces/aggregates when approved. The original QMAP `problemRunner.py` and `src/qmap/__init__.py` do not need to be replaced for this workflow documentation update.
