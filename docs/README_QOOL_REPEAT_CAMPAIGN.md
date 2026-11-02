# QOOL/VQE Pathfinder follow-up: v0.3b.2

## Changes

`src/qmap/workflows/qool_vqe.py` now reports `best_observed_energy`, `best_observed_evaluation_index`, `last_evaluated_energy` and `last_evaluation_index` in `workflow_completed` and summary CSV. Existing `final_energy` (SciPy result.fun) is retained for compatibility and must not be confused with last evaluated energy. These finite-shot minima are **not** evidence of convergence or an accurate ground-state energy.

If the destination `qool_summary.csv` has the old header, new rows go to `qool_summary_v03b2.csv` to avoid corrupting the prior CSV. No changes to the QTES runner, adapters, backend authentication, scientific ansatz, or measurement scheme.

## Validation

Run in the working `qmap_iqm` environment:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_qool_energy_summary.py' -v
```

Then a single Aer run, if desired:

```bash
PYTHONPATH=src python -m qmap.workflows.qool_vqe --adapter aer --qubits 4 --layers 2 --shots 100 --max-evals 10 --output results/qelf_workflows/qool_aer_v03b2
```

## Pathfinder follow-up

After loading credentials and checking the available allocation, run `bash examples/qelf_qool_pathfinder_repeats.sh` from the repository root. This requests **3 full optimizer runs**, **30 jobs**, **60 circuit evaluations**, and **6000 requested shots** total; no retries assumed. To start smaller, run one invocation manually with the same arguments. Keep the previous one-run Pathfinder pilot as a separate dataset. Never interpret its makespan as directly comparable to the QTES runs without workload normalization.

Measure the per-job transpilation, submission, result waiting, and optimizer energy histories. Inter-run variability, not only the mean, is important. The separate reference manifests preserve the QOOL/fragmented label for later blinded QWAT studies.

## Before IQM collaboration discussion

Ask which Pathfinder lifecycle timestamps distinguish arrival, acceptance, queued, execution-start, execution-end, and ready-to-fetch; how `job.result()` polling and batched circuit execution are implemented; whether persistent sessions or reservations are supported; and whether job/service accounting metadata are accessible with the existing API. Do not attribute the result-waiting interval to queue alone.
