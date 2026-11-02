"""Export QELF execution events without reference-pattern labels.

Usage: python -m qmap.workflows.export_inference_trace INPUT.jsonl OUTPUT.jsonl
The original trace and separate reference manifest are preserved.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REFERENCE_KEYS = frozenset({'pattern', 'locality', 'qelf_pattern', 'locality_class', 'reference_classification'})


def strip_reference_labels(obj):
    if isinstance(obj, dict):
        return {k: strip_reference_labels(v) for k, v in obj.items() if k not in REFERENCE_KEYS}
    if isinstance(obj, list):
        return [strip_reference_labels(v) for v in obj]
    return obj


def export_trace(src: Path, dest: Path):
    if src.resolve() == dest.resolve():
        raise ValueError('Refusing to overwrite source trace')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open(encoding='utf-8') as inp, dest.open('w', encoding='utf-8') as out:
        for line in inp:
            if line.strip():
                record = json.loads(line)
                # names can be predictive labels: remove workflow_name as well.
                record.pop('workflow', None)
                data = strip_reference_labels(record)
                if isinstance(data.get('data'), dict):
                    data['data'].pop('workflow_name', None)
                out.write(json.dumps(data) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export_trace(args.input, args.output)


if __name__ == '__main__':
    main()
