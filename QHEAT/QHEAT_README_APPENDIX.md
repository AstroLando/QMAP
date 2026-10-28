# QHEAT README addendum: status of hardware-backed workflow tests (October 2026)

Append this to `QHEAT/README_QHEAT_4_Patterns.md` if desired; it is provided separately to avoid replacing the existing scientific examples documentation.

## QELF/QMAP workflow runner status

The `src/qmap/workflows/runner.py` v0.2 harness can construct QTES and QSMC circuits from QHEAT and run **controlled** fragmented/batched/contiguous DAG experiments using mock, Qiskit Aer or an IQM on-prem backend. QTES four-qubit circuit execution and four-circuit FIFO/batch dispatch have been demonstrated on ORNL's Pathfinder IQM path. The latter is a scheduling/granularity test: four independent QTES evaluations are grouped into a batch-oriented higher-level workflow.

The other scientific QHEAT examples have **not** all been validated as end-to-end Pathfinder applications. VQE/QOOL's full adaptive hardware optimization loop and QASP/SKQD's measurement-based reduced-subspace solve remain separate implementation tasks. See `WORKFLOW_RUNNER_README.md` at the repository root for actual commands, outputs and limitations.
