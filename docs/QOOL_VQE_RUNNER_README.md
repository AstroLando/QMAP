# QELF QOOL/VQE integration (v0.3b pilot)

This additive module uses the existing `QHEAT/vqe_pauli_expectation.py` ansatz and Hamiltonian with **real finite-shot measurement counts**. It does not change the validated QTES runner or its adapters. It introduces an optimizer-feedback workflow: *COBYLA parameter proposal → quantum Z/ZZ and X basis measurements → classical energy estimate → next COBYLA evaluation*. Each objective evaluation has two commuting measurement groups, dispatched as a single Qiskit backend job if supported. Objective evaluations are sequential and cannot be batched ahead of optimizer feedback.

## Installation

Copy `src/qmap/workflows/qool_vqe.py` and `tests/test_qool_vqe.py` into the matching paths in your existing repository. Retain your **working v0.3a runner.py and telemetry.py**. Requires Qiskit, SciPy, NumPy and qiskit-aer for Aer, plus your original IQM SDK for Pathfinder.

## First: unit checks

```bash
conda activate qmap_iqm
cd /Users/r51/QMAP
PYTHONPATH=src python -m unittest discover -s tests -p 'test_qool_vqe.py' -v
```

## Next: Aer functional validation (no Pathfinder jobs)

```bash
PYTHONPATH=src python -m qmap.workflows.qool_vqe \
  --adapter aer --qubits 4 --layers 2 --shots 256 \
  --max-evals 5 --output results/qelf_workflows/qool_aer
```

Inspect the objective energy trajectory, the `qool_summary.csv`, and the `*.jsonl` trace. Expected: five sequential COBYLA objective evaluations with two basis circuits per evaluation, five Qiskit jobs and ten basis circuits total. Five evaluations **do not imply VQE convergence**.

## Pathfinder pilot (only after Aer works)

```bash
set -a; source tokens.env; set +a
PYTHONPATH=src python -m qmap.workflows.qool_vqe \
  --adapter iqm-onprem --qubits 4 --layers 2 --shots 100 \
  --max-evals 5 --output results/qelf_workflows/qool_pathfinder
```

**Important:** Verify backend limits and support for two circuits in one job before submission. This requests five jobs, each containing two measurement circuits with 100 shots per circuit (1,000 total shots). In a readout-limited regime the energy is a noisy estimate; COBYLA may report failure at small max-evals because budget was exhausted, not because jobs failed.

## Output and methodology

- Existing QMAP v0.3a JSONL trace events including per-adapter compilation, submission, result waiting, metadata, semantic spans, loop indices, parameter IDs, and previous-evaluation dependency.
- Separate `.manifest.json` with reference label QOOL/fragmented; export blinded inference traces with the existing `export_inference_trace` module.
- `*.energy.json` containing per-evaluation energies and optimizer parameter vectors. **These are scientific inputs and could be sensitive for future applications; only publish appropriately sanitized datasets.**
- Dedicated `qool_summary.csv` rather than appending incompatible columns to QTES `summary.csv`.

**Scope:** This implementation integrates actual measurement-based VQE objectives, but is not yet a broad policy experiment. It groups commuting Pauli measurements inside an iteration; it does not violate iteration dependencies. The system-level timing includes repeated compilation of ansatz circuits (parameters change each evaluation). Compare compiler costs separately when eventually studying scheduler benefits. The original Hamiltonian is generic (not molecule-specific). There is no ideal-reference or noise-model accuracy guarantee, and no claim of convergence at five evaluations.

No Pathfinder hardware execution has been performed on this newly written module in the development environment.
