# QMAP Workflow Runner v0.3a — Semantic instrumentation

This update is intended as an **additive change** to the working v0.2 runner.
It retains the existing IQM authentication, transpilation, job timing events,
policy selection, and CSV column layout. No changes to the existing QMAP
`problemRunner.py` or scientific QHEAT kernel implementations are required.

## What was added

- `src/qmap/workflows/telemetry.py` — optional `SemanticTelemetry.event()` and
  `SemanticTelemetry.span()` APIs with nested span identifiers.
- `Task.semantic_attributes` and `Workflow.semantic_attributes` in the runner.
- Events for DAG/dependency structure, logical circuit index, dispatch grouping,
  batch membership and provider job association.
- QTES annotations: `kernel_type=trotter_ising_1d`, `trotter_step_count=3`,
  `evolution_time=1.0`, coupling and field parameters, and the fact that
  Trotter steps occur **inside** one quantum circuit, not across QPU calls.
- `<run_id>.manifest.json` — separate reference classification and experiment
  configuration, designed for validating QWAT classification against ground truth.
- `export_inference_trace.py` — export a copy of a trace with reference pattern,
  locality and workflow labels removed. The original trace format remains
  compatible with v0.2 analyses and still contains the original labels.
- `--no-semantic-hooks` — disables optional semantic events/spans for overhead tests;
  the reference manifest is still written.

## Terminology and scientific limitations

A `qtes` circuit's internal Trotter steps are **not** separately timed or
submitted to the backend. The runner's `batched` pattern is an independently
schedulable ensemble of QTES circuit evaluations, not a single contiguous
multi-step QPU call. The `fragmented` pattern is a controlled QOOL-like DAG
with a synthetic classical delay, **not** a scientific VQE feedback loop.

QWAT's blind validation should use exported inference traces, **not** raw
JSONL files or their reference manifests. The exporter removes known reference
labels and workflow names; independent leakage auditing is still recommended
before publishing any pattern-classification accuracy result. Structural
metadata such as kernel identity may itself correlate with class, so evaluate
telemetry-only and semantic-assisted modes separately.

## Commands (from repository root in the working Conda environment)

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter mock --kernel qtes --pattern batched --policy both \
  --evaluations 4 --repeats 1 --output results/qelf_workflows/v03_mock
```

After verifying the mock results, run the previously working QTES single-circuit
Pathfinder command (credentials should be loaded from your local `tokens.env`):

```bash
conda activate qmap_iqm
set -a; source tokens.env; set +a
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter iqm-onprem --kernel qtes --qubits 4 --shots 100 \
  --pattern contiguous --policy fifo --repeats 1 \
  --output results/qelf_workflows/v03_pathfinder_smoke
```

Export an inference-facing copy of a JSONL trace:

```bash
PYTHONPATH=src python -m qmap.workflows.export_inference_trace \
  results/qelf_workflows/v03_mock/<run_id>.jsonl \
  results/qelf_workflows/v03_mock/<run_id>.inference.jsonl
```

The companion `<run_id>.manifest.json` contains expected QELF classification,
which should be withheld from inference. To compare hook overhead under otherwise
identical inputs, run a matched mock/Aer pair with and without `--no-semantic-hooks`.

## Known remaining work

1. The existing legacy trace continues to emit pattern/locality top-level fields
   to preserve v0.2 compatibility; use the filtered exporter for inference tests.
2. Semantic spans presently cover dispatch groups; they are not yet full
   application-level optimizer loops or live Trotter-step telemetry.
3. IQM queue versus execution intervals remain unavailable unless verified
   provider-side timestamps can be retrieved and normalized.
4. QOOL/VQE measurement feedback and QASP physical-overlap estimation still need
   separate scientific integration and validation.
5. New v0.3a code was checked with local mocks; live Pathfinder validation
   is required before treating any new trace as a hardware-validated result.
