#!/usr/bin/env bash
set -euo pipefail
# Run from QMAP repository root with Qiskit Aer installed.
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter aer --kernel qtes --qubits 4 --shots 100 \
  --pattern contiguous --policy fifo --repeats 1 \
  --output results/qelf_workflows/aer_single
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter aer --kernel qtes --qubits 4 --shots 100 \
  --pattern batched --policy both --evaluations 4 --repeats 3 \
  --output results/qelf_workflows/aer_dispatch
