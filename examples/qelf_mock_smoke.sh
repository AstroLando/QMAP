#!/usr/bin/env bash
set -euo pipefail
# Run from QMAP repository root, in your preferred Python environment.
PYTHONPATH=src python -m qmap.workflows.runner \
  --adapter mock --pattern all --policy both --repeats 3 \
  --output results/qelf_workflows/mock_smoke
