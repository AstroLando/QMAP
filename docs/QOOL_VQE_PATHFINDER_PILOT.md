# QOOL/VQE Pathfinder Pilot — v0.3b.1

This is an additive update to `src/qmap/workflows/qool_vqe.py`. No changes to working v0.3a QTES runner or original QMAP modules are required.

## Evaluation-budget fix

SciPy's installed COBYLA implementation requires `maxfun >= number_of_variational_parameters + 2`. The current QHEAT ansatz has `qubits * layers` parameters (four qubits, two layers = eight parameters). The runner now rejects a budget below ten **before constructing the backend**, so a `--max-evals 5` request cannot silently become ten hardware submissions. The default is now ten.

## Step 1 — Aer validation

From repository root, with the existing Conda environment activated:

```sh
PYTHONPATH=src python -m qmap.workflows.qool_vqe \
  --adapter aer --qubits 4 --layers 2 --shots 100 \
  --max-evals 10 --output results/qelf_workflows/qool_aer_v03b1
```

Expected: ten sequential objective evaluations, each with two measurement-basis circuits batched into a single job; ten jobs and twenty circuit evaluations (2,000 shots total). Energies can fluctuate due to shot noise. Ten evaluations are not a convergence test.

## Step 2 — Pathfinder pilot (submits hardware jobs)

Activate `qmap_iqm` and source the existing shell-compatible `tokens.env` as for prior Pathfinder tests. Do not commit credentials.

```sh
PYTHONPATH=src python -m qmap.workflows.qool_vqe \
  --adapter iqm-onprem --qubits 4 --layers 2 --shots 100 \
  --max-evals 10 --output results/qelf_workflows/qool_pathfinder_pilot
```

Before running, check allocation, access, and active backend availability. This requests **ten jobs**, two circuits per job, 100 shots per circuit, for **2,000 shots total** if all succeed. The existing IQM adapter's transpilation path is used. The run may fail if unsupported gates or batch limits are encountered; retain the traceback and partial JSONL trace in that case. Do not modify the working QMAP Pathfinder initialization.

## Artifacts and scientific meaning

Outputs include a JSONL event trace with phase-level events and semantic optimizer-iteration markers, `.manifest.json` reference classification, `.energy.json` history, and `qool_summary.csv`. Job result waiting is **not** interchangeable with server queue time or QPU service time. The objective evaluations are sequential because the classical optimizer depends on preceding results; within one objective, Z/ZZ and X measurement bases are batched into one job. This is a functional and telemetry pilot, not evidence of VQE convergence or a controlled scheduling-policy comparison.
