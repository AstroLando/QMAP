#!/usr/bin/env bash
set -euo pipefail
# Run from the QMAP repo root after `conda activate qmap_iqm`.
# Load tokens.env first: set -a; source tokens.env; set +a
# CAUTION: This script submits real jobs to Pathfinder. Check allocations and permissions.
if [[ -z "${IQM_ONPREM_TOKEN:-}" ]]; then
  echo 'IQM_ONPREM_TOKEN is not set. Source tokens.env (do not print the token).' >&2
  exit 1
fi
# One hardware connectivity/ISA test:
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter iqm-onprem --kernel qtes --qubits 4 --shots 100 \
  --pattern contiguous --policy fifo --repeats 1 \
  --output results/qelf_workflows/pathfinder_single
# Deliberately do NOT automatically submit larger pilot jobs. Run the two
# separately documented commands in WORKFLOW_RUNNER_README.md after review.
