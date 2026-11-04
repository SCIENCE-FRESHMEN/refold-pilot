#!/usr/bin/env python3
"""One-command end-to-end demo: select candidates, then evaluate the selection.

Runs the two standalone CLI tools on the bundled synthetic fixtures and writes
everything to ./example-output/ (selection/ plus evaluation.json).

Usage (from the repository root, Python 3.10+, standard library only):

    python3 run_example.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_ROOT / "example-output"

POLICY = "score"
BUDGET = 2
SEED = 0


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    selection_dir = OUTPUT_DIR / "selection"
    evaluation_path = OUTPUT_DIR / "evaluation.json"
    python = sys.executable or "python3"

    run(
        [
            python,
            str(REPO_ROOT / "bin" / "select_refold_candidates.py"),
            "--pdb-dir",
            str(REPO_ROOT / "fixtures" / "structures"),
            "--scores-file",
            str(REPO_ROOT / "fixtures" / "scores.tsv"),
            "--binder-chains",
            "A",
            "--target-chains",
            "B",
            "--policy",
            POLICY,
            "--budget",
            str(BUDGET),
            "--seed",
            str(SEED),
            "--output-dir",
            str(selection_dir),
        ]
    )

    run(
        [
            python,
            str(REPO_ROOT / "bin" / "evaluate_refold_selection.py"),
            "--manifest",
            str(selection_dir / "candidate_manifest.json"),
            "--outcomes",
            str(REPO_ROOT / "fixtures" / "synthetic-outcomes.tsv"),
            "--label-kind",
            "synthetic",
            "--budgets",
            "1",
            "2",
            "4",
            "--seeds",
            "0",
            "7",
            "42",
            "--output",
            str(evaluation_path),
        ]
    )

    print(f"\nDone. Outputs in {OUTPUT_DIR}/:")
    print(f"  {selection_dir}/candidate_manifest.json")
    print(f"  {selection_dir}/selected_candidates.tsv")
    print(f"  {selection_dir}/selection_audit.json")
    print(f"  {evaluation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
