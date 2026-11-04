"""Run a synthetic invariance experiment against the implemented selector."""

import argparse
import importlib.util
import json
import random
import time
from pathlib import Path


def run(module_path: Path, output: Path) -> dict:
    spec = importlib.util.spec_from_file_location("implemented_selection", module_path)
    selector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector)
    rows = []
    started = time.perf_counter()
    for size in (8, 32, 128):
        pool = [{"stable_id": selector.digest(["candidate", n]), "target_id": "target",
                 "candidate": f"candidate_{n}.pdb", "file_sha256": selector.digest(["file", n]),
                 "binder_sequence": "AAAAAAAA", "plddt_binder": 90.0,
                 "pae_interaction": float(n)} for n in range(size)]
        for budget in (2, 4, 8):
            for seed in (0, 7, 42):
                for policy in selector.POLICIES:
                    reference = None
                    consistent = 0
                    for permutation in range(100):
                        shuffled = pool.copy()
                        random.Random(permutation).shuffle(shuffled)
                        manifest = {"candidates": shuffled, "rejected": [], "input_count": size}
                        selected, _ = selector.select(manifest, policy, budget, seed)
                        ids = [item["stable_id"] for item in selected]
                        reference = ids if reference is None else reference
                        consistent += ids == reference
                        assert len(ids) == min(budget, size)
                    rows.append({"pool_size": size, "budget": budget, "seed": seed,
                                 "policy": policy, "permutations": 100,
                                 "consistent_permutations": consistent})
    result = {"data_kind": "synthetic; no inference or biological labels",
              "groups": len(rows), "selection_runs": sum(x["permutations"] for x in rows),
              "consistent_runs": sum(x["consistent_permutations"] for x in rows),
              "elapsed_seconds": round(time.perf_counter() - started, 3), "results": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "results"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selector", type=Path, default=Path(__file__).parent.parent /
                        "nf-binder-design/bin/select_refold_candidates.py")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "evidence/invariance.json")
    args = parser.parse_args()
    print(json.dumps(run(args.selector, args.output), indent=2))
