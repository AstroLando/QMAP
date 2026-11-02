# QELF semantic instrumentation v0.3a — Change log

Based on the current QMAP archive uploaded October 28, 2026.

Modified:
- `QMAP/src/qmap/workflows/runner.py`: optional semantic events, per-task
  metadata, QTES kernel annotations, reference manifest and CLI switch.

Added:
- `QMAP/src/qmap/workflows/telemetry.py`: event/span API.
- `QMAP/src/qmap/workflows/export_inference_trace.py`: remove known reference
  pattern/locality/workflow labels from exported traces.
- `QMAP/tests/test_semantic_telemetry.py`: semantic event and export tests.
- `QMAP/SEMANTIC_INSTRUMENTATION_README.md`: commands, caveats and next steps.

Unchanged:
- QMAP core files (`problemRunner.py`, `ProblemBase.py`, provider adapters).
- QHEAT scientific kernels, including `qtes_trotter_ising.py`.
- Existing `WORKFLOW_RUNNER_README.md` (the new supplement documents v0.3a).

Tests: six local unit tests passed using a dependency-isolated package import;
actual Qiskit/IQM hardware integration not run in this environment.
