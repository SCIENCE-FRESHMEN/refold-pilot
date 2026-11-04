#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Evaluate selectors on one frozen pool with separate, complete outcome labels."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from pathlib import Path

from select_refold_candidates import POLICIES, select, sequence_similarity


def read_labels(path: Path, expected: set[str]) -> dict:
    labels = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            key = row.get("stable_id", "")
            if key not in expected or key in labels:
                raise ValueError("Unknown or duplicate outcome identifier")
            if row.get("quality_pass") not in ("0", "1"):
                raise ValueError("Every outcome needs quality_pass 0 or 1; retain failed runs as 0")
            seconds = None
            if row.get("refold_seconds", ""):
                seconds = float(row["refold_seconds"])
                if not math.isfinite(seconds) or seconds < 0:
                    raise ValueError("Invalid refolding duration")
            labels[key] = {"quality_pass": int(row["quality_pass"]), "refold_seconds": seconds}
    if labels.keys() != expected:
        raise ValueError("Outcomes must cover the full unique pool; do not drop failed candidates")
    return labels


def evaluate(manifest: dict, labels: dict, budgets: list[int], seeds: list[int],
             similarity: float = 0.8) -> list[dict]:
    pool = manifest["candidates"]
    ids = [item["stable_id"] for item in pool]
    if len(ids) != len(set(ids)) or set(ids) != labels.keys():
        raise ValueError("Manifest identifiers must be unique and match the complete outcomes")
    groups = {}
    for item in pool:
        groups.setdefault(item["target_id"], []).append(item)
    rows = []
    for budget in budgets:
        for seed in seeds:
            for policy in POLICIES:
                selected, _ = select(manifest, policy, budget, seed, similarity)
                for target, full in sorted(groups.items()):
                    chosen = [item for item in selected if item["target_id"] == target]
                    positives = sum(labels[item["stable_id"]]["quality_pass"] for item in full)
                    hits = sum(labels[item["stable_id"]]["quality_pass"] for item in chosen)
                    durations = [labels[item["stable_id"]]["refold_seconds"] for item in chosen]
                    pairs = [sequence_similarity(a["binder_sequence"], b["binder_sequence"])
                             for n, a in enumerate(chosen) for b in chosen[n + 1:]]
                    rows.append({
                        "target_id": target, "policy": policy, "seed": seed, "budget": budget,
                        "pool_count": len(full), "selected_count": len(chosen),
                        "budget_shortfall": max(0, min(budget, len(full)) - len(chosen)),
                        "reference_positive_count": positives, "selected_positive_count": hits,
                        "selected_precision": hits / len(chosen) if chosen else None,
                        "reference_recall": hits / positives if positives else None,
                        "any_positive": bool(hits),
                        "unique_binder_sequences": len({x["binder_sequence"] for x in chosen}),
                        "mean_pairwise_edit_similarity": sum(pairs) / len(pairs) if pairs else None,
                        "candidate_refold_fraction": len(chosen) / len(full),
                        "selected_recorded_refold_seconds": sum(durations)
                        if all(value is not None for value in durations) else None,
                        "selected_ids": [item["stable_id"] for item in chosen],
                    })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--label-kind", choices=("synthetic", "computational_proxy", "experimental"),
                        required=True)
    parser.add_argument("--budgets", type=int, nargs="+", default=[2, 4, 8])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 7, 42])
    parser.add_argument("--similarity-threshold", type=float, default=0.8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Use a fresh output file")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        labels = read_labels(args.outcomes, {item["stable_id"] for item in manifest["candidates"]})
        result = {"label_kind": args.label_kind,
                  "scope": "Frozen-pool selection; excludes upstream generation and reference acquisition costs",
                  "results": evaluate(manifest, labels, args.budgets, args.seeds, args.similarity_threshold)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, KeyError, OSError) as exc:
        logging.error("%s", exc if not isinstance(exc, OSError) else "Input or output file unavailable")
        raise SystemExit(2) from exc
    logging.info("Wrote %d target-policy comparisons", len(result["results"]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
