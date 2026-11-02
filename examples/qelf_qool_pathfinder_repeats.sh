#!/usr/bin/env bash
set -euo pipefail
# Run from the QMAP repository root after activating qmap_iqm and loading tokens.env.
# Three sequential ten-evaluation experiments = 30 backend jobs, 60 circuits, 6000 shots.
# Each run writes independent trace, energy history, and manifest files.
for repeat in 1 2 3; do
  echo "QOOL Pathfinder replicate ${repeat}/3"
  PYTHONPATH=src python -m qmap.workflows.qool_vqe \
    --adapter iqm-onprem --qubits 4 --layers 2 --shots 100 \
    --max-evals 10 --output results/qelf_workflows/qool_pathfinder_repeats
 done
