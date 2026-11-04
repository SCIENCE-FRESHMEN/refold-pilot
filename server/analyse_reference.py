"""Export an anonymised frozen pool and independently evaluate reference outcomes."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import re
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("REFOLD_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(ROOT / "source/bin"))
from evaluate_refold_selection import evaluate
from select_refold_candidates import POLICIES, build_manifest, public_record, read_scores, select


def read_table(path):
    if not path.is_file():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_reports(output, summary, comparisons):
    lines = ["Single-GPU reference study and frozen-pool evaluation", "",
             f"Unique candidates: {summary['valid_unique_reference_candidates']}; proxy positives: {summary['proxy_positive_count']}; missing outcomes: {summary['missing_reference_outputs']}.",
             "Proxy: ipSAE >= 0.6 and target-aligned binder RMSD_all <= 2 angstrom. No experimental binding validation.", "",
             "policy\tbudget\tselected_count_range\tproxy_positive_count_range\trecorded_selected_refold_seconds_range"]
    for policy in ("hash", "score", "diverse"):
        for budget in (2, 4, 8):
            subset = [row for row in comparisons if row["policy"] == policy and row["budget"] == budget]
            selected = [row["selected_count"] for row in subset]
            positives = [row["selected_positive_count"] for row in subset]
            seconds = [row["selected_recorded_refold_seconds"] for row in subset]
            cost = f"{min(seconds):.3f}–{max(seconds):.3f}" if all(x is not None for x in seconds) else "missing"
            lines.append(f"{policy}\t{budget}\t{min(selected)}–{max(selected)}\t{min(positives)}–{max(positives)}\t{cost}")
    lines += ["", "All policies use the same frozen pool; labels enter independent evaluation only.",
              "Repeated score/diverse seeds are not independent samples; small pools do not establish general quality improvement.",
              "Durations are selected-task records from the full reference run; budget policies were not independently run and end-to-end speedup was not measured."]
    (output / "experiment-summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pools = []
    unique, targets = set(), set()
    for path in (ROOT / "export").glob("*/summary.json"):
        record = json.loads(path.read_text())
        if record["missing_reference_outputs"]:
            continue
        pools.append(record)
        data = json.loads((path.parent / "candidate_manifest.json").read_text())
        unique.update(item["stable_id"] for item in data["candidates"])
        targets.update(item["target_id"] for item in data["candidates"])
    text = ("Protein binder candidate selection and reproducible evaluation\n\n"
            f"Completed {len(pools)} reference pools covering {len(targets)} target sequences and {len(unique)} unique structural candidates.\n"
            "Reference workflow: RFdiffusion -> ProteinMPNN -> AF2IG -> Boltz, with at most one model GPU at a time. Selection uses per-target budgets, checksum replay, and complete outcomes.\n"
            "Computational proxy validation only; experimental binding, end-to-end speedup, and general quality improvement are unverified.\n")
    destination = ROOT / "export/study-summary.txt"
    temporary = destination.with_suffix(".temporary")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(destination)


def bundle_exports():
    export = ROOT / "export"
    allowed = {"candidate_manifest.json", "comparison.json", "outcomes.tsv", "pre-refold.tsv", "protocol.json",
               "quality-metrics.json", "resource-summary.json", "summary.json", "experiment-summary.txt",
               "order-invariance.json", "replay-audit.json"}
    files = []
    for path in sorted(export.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(export).parts
        if parts == ("study-summary.txt",) or (len(parts) == 2 and parts[1] in allowed) or (
                len(parts) == 3 and parts[1] == "structures" and
                re.fullmatch(r"candidate_[0-9a-f]{16}\.pdb", parts[2])):
            files.append(path)
    private_user = os.environ.get("USER", "")
    for path in files:
        value = path.read_text(encoding="utf-8")
        if ".private" in path.name or re.search(
                r"[A-Za-z]:[\\/]|/(?:home|mnt|scratch\d*|fs\d+)/|[\w.+-]+@[\w.-]+\.[A-Za-z]+|\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", value):
            raise ValueError("An export contains identifying text")
        if private_user and private_user in value:
            raise ValueError("An export contains a login identifier")
    pending = ROOT / "runtime/experiment-results.pending.tar.gz"
    pending.parent.mkdir(parents=True, exist_ok=True)
    with pending.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in files:
                    raw = path.read_bytes()
                    info = tarfile.TarInfo("experiments/" + path.relative_to(export).as_posix())
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    archive.addfile(info, io.BytesIO(raw))
    pending.replace(ROOT / "runtime/experiment-results.tar.gz")


def analyse(run, expected):
    run = run.resolve()
    if not run.is_relative_to(ROOT / "runs"):
        raise ValueError("Reference run must be inside the experiment workspace")
    output = ROOT / "export" / run.name
    if output.exists():
        raise ValueError("Use a fresh export directory")
    results = run / "results"
    source_manifest = json.loads((results / "refold_selection/selection/candidate_manifest.json").read_text())
    protocol = json.loads((ROOT / "scripts/protocol.json").read_text())
    candidates = source_manifest["candidates"]
    if not candidates:
        raise ValueError("The reference pool is empty")
    rmsd = {}
    for row in read_table(results / "boltz_refold/rmsd/rmsd_target_aligned_binder.tsv"):
        key = Path(row["structure1"]).stem
        if key in rmsd:
            raise ValueError("Duplicate target-aligned RMSD result")
        rmsd[key] = row
    trace_files = sorted((run / "attempts").glob("trace-*.private.tsv")) + [run / "trace.private.tsv"]
    trace_records = {}
    for trace_file in trace_files:
        for row in read_table(trace_file):
            key = (row.get("native_id"), row.get("hash"), row["name"])
            trace_records[key] = row
    traces = list(trace_records.values())
    quarantined_files = sorted((run / 'attempts').glob('quarantined-*.private.tsv'))
    quarantined_stages = {}
    for path in quarantined_files:
        for row in read_table(path):
            stage = row['name'].split(' (')[0].split(':')[-1]
            stats = quarantined_stages.setdefault(stage, {'recorded_tasks': 0, 'cached_tasks': 0,
                                                          'known_task_script_seconds': 0.0})
            stats['recorded_tasks'] += 1
            if row['status'] == 'CACHED':
                stats['cached_tasks'] += 1
                continue
            duration = finite(row.get('realtime'))
            if duration is not None:
                stats['known_task_script_seconds'] += duration / 1000
    durations = defaultdict(dict)
    stage_stats = {}
    hardware = set()
    for row in traces:
        stage = row["name"].split(" (")[0].split(":")[-1]
        elapsed = finite(row.get("realtime"))
        elapsed = elapsed / 1000 if elapsed is not None else None
        rss = finite(row.get("peak_rss"))
        stats = stage_stats.setdefault(stage, {"completed_tasks": 0, "cached_tasks": 0, "failed_tasks": 0,
                                               "known_task_script_seconds": 0.0, "missing_durations": 0,
                                               "peak_host_rss_bytes": None})
        stats["cached_tasks" if row["status"] == "CACHED" else
              "completed_tasks" if row["status"] == "COMPLETED" else "failed_tasks"] += 1
        if elapsed is None:
            stats["missing_durations"] += 1
        else:
            stats["known_task_script_seconds"] += elapsed
        if rss is not None:
            stats["peak_host_rss_bytes"] = max(stats["peak_host_rss_bytes"] or 0, rss)
        match = re.search(r"(BOLTZ_COMPARE_COMPLEX|BOLTZ_COMPARE_BINDER_MONOMER) \(([^)]+)\)$", row["name"])
        if match and row["status"] in ("COMPLETED", "CACHED"):
            durations[match.group(2)][match.group(1)] = elapsed
        if stage == "RFDIFFUSION" and row.get("workdir"):
            work = Path(row["workdir"]).resolve()
            if work.is_relative_to(ROOT) and (work / ".command.out").is_file():
                text = (work / ".command.out").read_text(errors="replace")
                hardware.update(re.findall(r"NVIDIA\s+(L40S|A40|A100\S*|H100\S*)", text))

    labels, metrics = {}, []
    original_paths = []
    for item in candidates:
        name, stable = Path(item["candidate"]).stem, item["stable_id"]
        source = results / "rfd/af2_initial_guess/pdbs" / item["candidate"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["file_sha256"]:
            raise ValueError("Reference structure changed after pool freeze")
        original_paths.append((item, source))
        confidence = results / "boltz_refold/predict/complex" / f"boltz_results_{name}" / "predictions" / name / f"confidence_{name}_model_0.json"
        data = json.loads(confidence.read_text()) if confidence.is_file() else {}
        ipsae = finite(data.get("ipsae_min"))
        row = rmsd.get(name, {})
        value = finite(row.get(protocol["rmsd_field"]))
        roles = (row.get("superimposed_chains_fixed"), row.get("superimposed_chains_mobile"),
                 row.get("scored_chains_fixed"), row.get("scored_chains_mobile"))
        if row and roles != ("B", "B", "A", "A"):
            raise ValueError("RMSD roles differ from the registered target/binder mapping")
        reason = "missing_reference_output" if ipsae is None or value is None else "computed"
        passed = int(ipsae is not None and value is not None and ipsae >= protocol["ipsae_minimum"] and
                     value <= protocol["target_aligned_binder_rmsd_maximum_angstrom"])
        task_times = durations.get(name, {})
        seconds = sum(task_times.values()) if len(task_times) == 2 and all(
            value is not None for value in task_times.values()) else None
        labels[stable] = {"quality_pass": passed, "refold_seconds": seconds}
        metrics.append({"stable_id": stable, "ipsae_min": ipsae,
                        "target_aligned_binder_rmsd_all": value, "quality_pass": passed, "reason": reason})

    output.mkdir(parents=True)
    structures = output / "structures"
    structures.mkdir()
    score_rows = ["description\tplddt_binder\tpae_interaction"]
    for item, source in original_paths:
        name = "candidate_" + item["stable_id"][:16]
        atoms = [line for line in source.read_text().splitlines() if line.startswith(("ATOM  ", "HETATM", "TER   "))]
        (structures / f"{name}.pdb").write_text("\n".join(atoms) + "\nEND\n")
        plddt = "" if item["plddt_binder"] is None else item["plddt_binder"]
        pae = "" if item["pae_interaction"] is None else item["pae_interaction"]
        score_rows.append(f"{name}\t{plddt}\t{pae}")
    score_path = output / "pre-refold.tsv"
    score_path.write_text("\n".join(score_rows) + "\n")
    exported = build_manifest(list(structures.glob("*.pdb")), read_scores([score_path]), ["A"], ["B"])
    if {item["stable_id"] for item in exported["candidates"]} != set(labels):
        raise ValueError("De-identification changed structural candidate identities")
    manifest = {**exported, "candidates": [public_record(item) for item in exported["candidates"]]}
    write_json(output / "candidate_manifest.json", manifest)
    order_rows = []
    check_budget = min(4, len(candidates))
    for policy in POLICIES:
        reference, reference_audit = select(manifest, policy, check_budget, 0)
        expected_ids = [item["stable_id"] for item in reference]
        if policy == "hash":
            replayed, _ = select(manifest, policy, check_budget, 0, replay=reference_audit)
            assert [item["stable_id"] for item in replayed] == expected_ids
            write_json(output / "replay-audit.json", reference_audit)
        elapsed = 0.0
        for permutation in range(16):
            shuffled = manifest["candidates"].copy()
            random.Random(permutation).shuffle(shuffled)
            started = time.perf_counter()
            chosen, _ = select({**manifest, "candidates": shuffled}, policy, check_budget, 0)
            elapsed += time.perf_counter() - started
            assert [item["stable_id"] for item in chosen] == expected_ids
        order_rows.append({"policy": policy, "budget": check_budget, "permutations": 16, "consistent": 16,
                           "mean_loaded_manifest_selection_seconds": elapsed / 16})
    write_json(output / "order-invariance.json", {"data_kind": "real_reference_pool", "trials": 48,
               "consistent_trials": 48, "checksum_replay": "passed", "results": order_rows})
    with (output / "outcomes.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["stable_id", "quality_pass", "refold_seconds"])
        for key, row in labels.items():
            writer.writerow([key, row["quality_pass"], row["refold_seconds"]])
    comparisons = evaluate(manifest, labels, protocol["budgets"], protocol["selection_seeds"],
                           protocol["similarity_threshold"])
    write_json(output / "comparison.json", {"label_kind": "computational_proxy", "results": comparisons,
               "cost_scope": protocol["cost_scope"], "independent_gpu_runs_per_strategy": False})
    write_json(output / "quality-metrics.json", metrics)
    write_json(output / "protocol.json", protocol)
    write_json(output / "resource-summary.json", {"stages": stage_stats, "actual_gpu_models_seen": sorted(hardware),
               "quarantined_non_reference_attempts": len(quarantined_files),
               "quarantined_non_reference_stages": quarantined_stages,
               "quarantined_attempt_scope": "Non-reference regeneration caused by path-alias cache misses; retained as overhead, excluded from the frozen candidate pool",
               "gpu_model_observation_scope": "RFdiffusion stdout only; other stages may use different compatible GPUs",
               "gpu_model_coverage_complete": False,
               "compatible_gpu_classes": ["A100-80G", "A40", "L40S"],
               "gpu_peak_memory_measured": False, "raw_trace_exported": False,
               "elapsed_definition": "Task-script wall time from raw Nextflow realtime in milliseconds; not GPU kernel time",
               "includes_model_setup_cost": False,
               "comparison_costs_are_subsets_of_reference_trace": True,
               "end_to_end_speedup_measured": False})
    summary = {"status": "reference_complete" if all(row["reason"] == "computed" for row in metrics) else "reference_incomplete",
               "requested_designs": expected,
               "valid_unique_reference_candidates": len(candidates),
               "source_manifest_input_count": source_manifest["input_count"],
               "proxy_positive_count": sum(row["quality_pass"] for row in labels.values()),
               "missing_reference_outputs": sum(row["reason"] != "computed" for row in metrics),
               "label_kind": "computational_proxy", "experimental_binding_validation": False,
               "selection_seed_repeats_are_not_independent_targets": True,
               "selector_source_sha256": hashlib.sha256((ROOT / "source/bin/select_refold_candidates.py").read_bytes()).hexdigest(),
               "protocol_sha256": hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()}
    write_json(output / "summary.json", summary)
    write_reports(output, summary, comparisons)
    bundle_exports()
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--expected-designs", type=int, required=True)
    args = parser.parse_args()
    analyse(args.run, args.expected_designs)
