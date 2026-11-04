#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Select a reproducible, per-target refolding budget using pre-refold data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import shutil
from pathlib import Path

RESIDUES = dict(zip(
    "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split(),
    "ARNDCQEGHILKMFPSTWYV",
))
POLICIES = ("hash", "score", "diverse")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finite(value: object) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def read_structure(path: Path, binder_chains: list[str], target_chains: list[str]) -> dict:
    if not binder_chains or not target_chains or set(binder_chains) & set(target_chains):
        raise ValueError("Binder and target chains must be explicit and disjoint")
    chains: dict[str, dict] = {}
    atoms = []
    for line in path.read_text().splitlines():
        if not line.startswith("ATOM  ") or len(line) < 54 or line[16] not in (" ", "A"):
            continue
        chain = line[21]
        if chain not in binder_chains + target_chains:
            continue
        residue = (line[22:26].strip(), line[26].strip())
        chains.setdefault(chain, {})[residue] = RESIDUES.get(line[17:20].strip(), "X")
        coordinates = tuple(float(line[start:start + 8]) for start in (30, 38, 46))
        if not all(math.isfinite(x) for x in coordinates):
            raise ValueError("Non-finite coordinates")
        atoms.append((chain, *residue, line[12:16].strip(), *coordinates))
    if any(not chains.get(c) for c in binder_chains + target_chains):
        raise ValueError("Missing requested chain")
    sequences = {c: "".join(chains[c].values()) for c in sorted(chains)}
    identity = {"chains": sequences, "binder_chains": sorted(binder_chains),
                "target_chains": sorted(target_chains), "atoms": sorted(atoms)}
    return {
        "stable_id": digest(identity),
        "target_id": digest({c: sequences[c] for c in sorted(target_chains)}),
        "binder_sequence": "/".join(sequences[c] for c in binder_chains),
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def read_scores(paths: list[Path]) -> dict[str, dict]:
    result = {}
    for path in sorted(paths):
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                identifiers = {Path(row[field]).stem for field in ("description", "id", "design_id", "pdb_path")
                               if row.get(field) and row[field].strip()}
                if not identifiers:
                    raise ValueError("Score record has no candidate identifier")
                if len(identifiers) != 1:
                    raise ValueError("Score record has conflicting candidate identifiers")
                key = identifiers.pop()
                values = {"plddt_binder": finite(row.get("plddt_binder")),
                          "pae_interaction": finite(row.get("pae_interaction"))}
                if key in result and result[key] != values:
                    raise ValueError("Conflicting score records for a candidate")
                result[key] = values
    return result


def build_manifest(paths: list[Path], scores: dict, binder: list[str], target: list[str]) -> dict:
    candidates = []
    rejected = []
    seen = {}
    names = {}
    for path in sorted(paths, key=lambda p: (p.name, str(p))):
        try:
            item = read_structure(path, binder, target)
        except (ValueError, OSError) as exc:
            rejected.append({"candidate": path.name, "reason": "invalid_structure",
                             "detail": str(exc) if isinstance(exc, ValueError) else "unreadable_input"})
            continue
        if path.name in names and names[path.name] != item["stable_id"]:
            raise ValueError("Different structures share an output basename")
        names[path.name] = item["stable_id"]
        item.update(scores.get(path.stem, {"plddt_binder": None, "pae_interaction": None}))
        item.update({"candidate": path.name, "_path": path})
        if item["stable_id"] in seen:
            previous = seen[item["stable_id"]]
            if any(item[k] != previous[k] for k in ("plddt_binder", "pae_interaction")):
                raise ValueError("Identical structures have conflicting scores")
            rejected.append({"candidate": path.name, "stable_id": item["stable_id"],
                             "reason": "duplicate_structure"})
        else:
            seen[item["stable_id"]] = item
            candidates.append(item)
    candidates.sort(key=lambda x: (x["target_id"], x["stable_id"]))
    return {"candidates": candidates, "rejected": rejected, "input_count": len(paths)}


def sequence_similarity(left: str, right: str) -> float:
    """Normalised edit similarity, not an evolutionary or homology estimate."""
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return 1.0 - previous[-1] / max(len(left), len(right))


def select(manifest: dict, policy: str, budget: int | None, seed: int = 0,
           similarity: float = 0.8, replay: dict | None = None) -> tuple[list[dict], dict]:
    if policy not in POLICIES or (budget is not None and budget < 0):
        raise ValueError("Invalid selection policy or budget")
    if not 0 <= similarity <= 1:
        raise ValueError("Similarity threshold must be between zero and one")
    decisions = list(manifest["rejected"])
    pool = manifest["candidates"]
    if replay is not None:
        expected = {x["stable_id"]: x["file_sha256"] for x in pool}
        if replay.get("pool_checksums") != expected:
            raise ValueError("Replay pool differs from the recorded pool")
        ids = replay.get("selected_ids", [])
        if len(ids) != len(set(ids)) or not set(ids) <= set(expected):
            raise ValueError("Invalid replay candidate identifiers")
        selected = [next(x for x in pool if x["stable_id"] == key) for key in ids]
        counts = {}
        for item in selected:
            key = item["target_id"]
            counts[key] = counts.get(key, 0) + 1
        if budget is not None and any(n > budget for n in counts.values()):
            raise ValueError("Replay exceeds the per-target budget")
        reasons = {x["stable_id"]: "replayed" for x in selected}
    else:
        groups: dict[str, list] = {}
        for item in pool:
            if policy != "hash" and any(item.get(k) is None for k in ("pae_interaction", "plddt_binder")):
                decisions.append({"candidate": item["candidate"], "stable_id": item["stable_id"],
                                  "reason": "missing_or_nonfinite_score"})
                continue
            groups.setdefault(item["target_id"], []).append(item)
        selected = []
        reasons = {}
        for key in sorted(groups):
            group = groups[key]
            if policy == "hash":
                ordered = sorted(group, key=lambda x: digest([seed, x["stable_id"]]))
            else:
                ordered = sorted(group, key=lambda x: (x["pae_interaction"],
                                                       -x["plddt_binder"], x["stable_id"]))
            count = len(ordered) if budget is None else min(budget, len(ordered))
            chosen = []
            if policy == "diverse":
                for item in ordered:
                    if len(chosen) == count:
                        break
                    if all(sequence_similarity(item["binder_sequence"], other["binder_sequence"]) < similarity
                           for other in chosen):
                        chosen.append(item)
                        reasons[item["stable_id"]] = "quality_and_diversity"
            for item in ordered:
                if len(chosen) == count:
                    break
                if item not in chosen:
                    chosen.append(item)
                    reasons[item["stable_id"]] = "budget_fill" if policy == "diverse" else policy
            selected.extend(chosen)
    selected_ids = {x["stable_id"] for x in selected}
    rejected_ids = {x.get("stable_id") for x in decisions if x["reason"] == "missing_or_nonfinite_score"}
    for item in pool:
        if item["stable_id"] not in rejected_ids:
            decisions.append({"candidate": item["candidate"], "stable_id": item["stable_id"],
                              "target_id": item["target_id"],
                              "reason": reasons[item["stable_id"]] if item["stable_id"] in selected_ids else "outside_budget",
                              "selected": item["stable_id"] in selected_ids})
    audit = {
        "schema_version": 1, "policy": "replay" if replay is not None else policy,
        "seed": seed, "per_target_budget": budget, "similarity_threshold": similarity,
        "input_count": manifest["input_count"], "unique_count": len(pool),
        "selected_count": len(selected), "selected_ids": [x["stable_id"] for x in selected],
        "pool_checksums": {x["stable_id"]: x["file_sha256"] for x in pool},
        "decisions": decisions,
    }
    return selected, audit


def public_record(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def write_outputs(manifest: dict, selected: list[dict], audit: dict, output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty; use a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    selected_dir = output / "selected"
    selected_dir.mkdir()
    for item in selected:
        shutil.copyfile(item["_path"], selected_dir / item["candidate"])
    clean = {**manifest, "candidates": [public_record(x) for x in manifest["candidates"]]}
    (output / "candidate_manifest.json").write_text(
        json.dumps(clean, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "selection_audit.json").write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "selected_candidates.tsv").open("w", newline="") as handle:
        columns = ["candidate", "stable_id", "target_id", "file_sha256", "binder_sequence",
                   "plddt_binder", "pae_interaction"]
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(public_record(x) for x in selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb-dir", type=Path, required=True)
    score_input = parser.add_mutually_exclusive_group()
    score_input.add_argument("--scores-dir", type=Path)
    score_input.add_argument("--scores-file", type=Path, help="Use one explicit frozen-pool score table")
    parser.add_argument("--binder-chains", nargs="+", required=True)
    parser.add_argument("--target-chains", nargs="+", required=True)
    parser.add_argument("--policy", choices=POLICIES, default="hash")
    parser.add_argument("--budget", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--similarity-threshold", type=float, default=0.8)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not args.pdb_dir.is_dir() or (args.scores_dir and not args.scores_dir.is_dir()):
            raise ValueError("Input directory is missing")
        paths = list(args.pdb_dir.rglob("*.pdb"))
        score_paths = ([args.scores_file] if args.scores_file else
                       list(args.scores_dir.rglob("*.tsv")) if args.scores_dir else [])
        scores = read_scores(score_paths)
        manifest = build_manifest(paths, scores, args.binder_chains, args.target_chains)
        replay = json.loads(args.replay.read_text()) if args.replay else None
        selected, audit = select(manifest, args.policy, args.budget, args.seed,
                                 args.similarity_threshold, replay)
        write_outputs(manifest, selected, audit, args.output_dir)
    except (ValueError, OSError, KeyError) as exc:
        logging.error("%s", exc if not isinstance(exc, OSError) else "Input or output file unavailable")
        raise SystemExit(2) from exc
    logging.info("Selected %d of %d unique candidates", len(selected), len(manifest["candidates"]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
