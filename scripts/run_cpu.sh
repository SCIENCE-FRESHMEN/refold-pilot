#!/bin/bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "${bundle_dir}"
python3 tests/bin/test_refold_selection.py
python3 tests/bin/test_refold_evaluation.py
mkdir -p results
python3 scripts/benchmark_selection.py --selector bin/select_refold_candidates.py --output results/invariance.json
python3 bin/select_refold_candidates.py --pdb-dir fixtures/structures --scores-file fixtures/scores.tsv \
    --binder-chains A --target-chains B --policy hash --budget 2 --seed 0 --output-dir results/selection
python3 bin/evaluate_refold_selection.py --manifest results/selection/candidate_manifest.json \
    --outcomes fixtures/synthetic-outcomes.tsv --label-kind synthetic --budgets 2 4 8 --seeds 0 7 42 \
    --output results/synthetic-evaluation.json
