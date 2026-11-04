import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "bin"
sys.path.insert(0, str(BIN))
import select_refold_candidates as selection
from interface_scores import read_interface_metrics


def structure(path: Path, variant: int = 0, target: str = "ALA", residue: str = "GLY") -> Path:
    lines = []
    for serial, (chain, name, x) in enumerate([("A", residue, variant + 1.0), ("B", target, 0.0)], 1):
        lines.append(f"ATOM  {serial:5d}  CA  {name} {chain}{1:4d}    "
                     f"{x:8.3f}{0:8.3f}{0:8.3f}  1.00 90.00           C\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines))
    return path


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = [structure(self.root / f"candidate_{n}.pdb", n) for n in range(8)]
        self.scores = {p.stem: {"plddt_binder": 90.0, "pae_interaction": float(n)}
                       for n, p in enumerate(self.paths)}

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, paths=None, scores=None):
        return selection.build_manifest(self.paths if paths is None else paths,
                                        self.scores if scores is None else scores, ["A"], ["B"])

    def test_real_filtered_af2_score_schema(self):
        scores = self.root / "af2ig_filtered_scores.tsv"
        scores.write_text("design_id\tpdb_path\tplddt_binder\tpae_interaction\taf2ig_pass_filter\n"
                          "candidate_0\tcandidate_0.pdb\t68.519\t25.093\tTrue\n")
        parsed = selection.read_scores([scores])
        self.assertEqual(parsed, {"candidate_0": {"plddt_binder": 68.519, "pae_interaction": 25.093}})
        candidate = next(row for row in self.manifest(scores=parsed)["candidates"]
                         if row["candidate"] == "candidate_0.pdb")
        self.assertEqual(candidate["plddt_binder"], 68.519)
        scores.write_text("pdb_path\tplddt_binder\tpae_interaction\n"
                          "candidate_0.pdb\t94.135\t26.426\n")
        self.assertEqual(selection.read_scores([scores])["candidate_0"]["pae_interaction"], 26.426)

    def test_conflicting_score_identifier_columns_fail(self):
        scores = self.root / "scores.tsv"
        scores.write_text("design_id\tpdb_path\tplddt_binder\n"
                          "candidate_0\tcandidate_1.pdb\t90\n")
        with self.assertRaisesRegex(ValueError, "conflicting candidate identifiers"):
            selection.read_scores([scores])

    def test_cli_explicit_score_file_and_missing_directory(self):
        scores = self.root / "scores.tsv"
        scores.write_text("description\tplddt_binder\tpae_interaction\n" + "".join(
            f"{path.stem}\t90\t{n}\n" for n, path in enumerate(self.paths)))
        command = [sys.executable, str(BIN / "select_refold_candidates.py"), "--pdb-dir", str(self.root),
                   "--scores-file", str(scores), "--binder-chains", "A", "--target-chains", "B",
                   "--policy", "score", "--budget", "2", "--output-dir", str(self.root / "output")]
        result = subprocess.run(command, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = json.loads((self.root / "output/selection_audit.json").read_text())
        self.assertEqual(selected["selected_count"], 2)
        command[command.index("--pdb-dir") + 1] = str(self.root / "missing")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_order_invariance_for_all_policies(self):
        for policy in selection.POLICIES:
            expected = None
            for seed in range(100):
                paths = self.paths.copy()
                random.Random(seed).shuffle(paths)
                chosen, audit = selection.select(self.manifest(paths), policy, 3, 0)
                got = [x["stable_id"] for x in chosen]
                expected = got if expected is None else expected
                self.assertEqual(got, expected)
                self.assertEqual(audit["selected_count"], 3)

    def test_score_uses_pre_refold_metrics_only(self):
        manifest = self.manifest()
        chosen, _ = selection.select(manifest, "score", 2)
        for item in manifest["candidates"]:
            item["oracle_binding"] = random.random()
            item["future_boltz_score"] = random.random()
        again, _ = selection.select(manifest, "score", 2)
        self.assertEqual([x["stable_id"] for x in chosen], [x["stable_id"] for x in again])
        self.assertEqual([x["pae_interaction"] for x in chosen], [0.0, 1.0])

    def test_zero_budget_and_zero_seed(self):
        self.assertEqual(selection.select(self.manifest(), "hash", 0, 0)[0], [])
        self.assertEqual(len(selection.select(self.manifest(), "hash", 99, 0)[0]), 8)

    def test_budget_is_per_target(self):
        other = structure(self.root / "other.pdb", 10, target="VAL")
        chosen, _ = selection.select(self.manifest(self.paths + [other]), "hash", 2)
        self.assertEqual(len(chosen), 3)
        self.assertEqual(len({x["target_id"] for x in chosen}), 2)

    def test_missing_scores_are_not_zero(self):
        manifest = self.manifest(scores={})
        chosen, audit = selection.select(manifest, "score", 2)
        self.assertEqual(chosen, [])
        self.assertEqual(len(audit["decisions"]), 8)
        self.assertTrue(all(x["reason"] == "missing_or_nonfinite_score" for x in audit["decisions"]))
        self.assertEqual(len(selection.select(manifest, "hash", 2)[0]), 2)

    def test_nonfinite_score_input(self):
        table = self.root / "scores.tsv"
        table.write_text("description\tplddt_binder\tpae_interaction\ncandidate_0\tNaN\tinf\n")
        scores = selection.read_scores([table])
        self.assertIsNone(scores["candidate_0"]["plddt_binder"])
        self.assertIsNone(scores["candidate_0"]["pae_interaction"])

    def test_duplicate_structure_has_a_reason(self):
        duplicate = self.root / "copy.pdb"
        shutil.copyfile(self.paths[0], duplicate)
        manifest = self.manifest(self.paths + [duplicate],
                                 {**self.scores, "copy": self.scores["candidate_0"]})
        self.assertEqual(len(manifest["candidates"]), 8)
        self.assertEqual(manifest["rejected"][0]["reason"], "duplicate_structure")

    def test_conflicting_duplicate_scores_fail(self):
        duplicate = self.root / "copy.pdb"
        shutil.copyfile(self.paths[0], duplicate)
        with self.assertRaises(ValueError):
            self.manifest(self.paths + [duplicate],
                          {**self.scores, "copy": {"plddt_binder": 10, "pae_interaction": 99}})

    def test_basename_collision_fails_before_copy(self):
        other = structure(self.root / "subdir" / self.paths[0].name, 99)
        with self.assertRaises(ValueError):
            self.manifest(self.paths + [other])

    def test_filename_is_not_stable_identity(self):
        renamed = self.root / "renamed.pdb"
        shutil.copyfile(self.paths[0], renamed)
        first = selection.read_structure(self.paths[0], ["A"], ["B"])
        second = selection.read_structure(renamed, ["A"], ["B"])
        self.assertEqual(first["stable_id"], second["stable_id"])

    def test_invalid_structure_is_audited(self):
        invalid = self.root / "invalid.pdb"
        invalid.write_text("not a structure\n")
        manifest = self.manifest([invalid])
        self.assertEqual(manifest["rejected"][0]["reason"], "invalid_structure")
        self.assertEqual(selection.select(manifest, "hash", 2)[0], [])

    def test_replay_checks_content_and_budget(self):
        manifest = self.manifest()
        selected, audit = selection.select(manifest, "hash", 3, 0)
        replayed, _ = selection.select(manifest, "score", 3, replay=audit)
        self.assertEqual([x["stable_id"] for x in selected], [x["stable_id"] for x in replayed])
        with self.assertRaises(ValueError):
            selection.select(manifest, "hash", 2, replay=audit)
        audit["pool_checksums"][selected[0]["stable_id"]] = "modified"
        with self.assertRaises(ValueError):
            selection.select(manifest, "hash", 3, replay=audit)

    def test_diversity_budget_fill_is_labelled(self):
        chosen, audit = selection.select(self.manifest(), "diverse", 3)
        self.assertEqual(len(chosen), 3)
        reasons = [x["reason"] for x in audit["decisions"] if x.get("selected")]
        self.assertEqual(reasons.count("budget_fill"), 2)

    def test_empty_output_and_overwrite_guard(self):
        manifest = self.manifest([], {})
        chosen, audit = selection.select(manifest, "hash", 2)
        out = self.root / "output"
        selection.write_outputs(manifest, chosen, audit, out)
        self.assertEqual(json.loads((out / "selection_audit.json").read_text())["selected_count"], 0)
        self.assertEqual(len((out / "selected_candidates.tsv").read_text().splitlines()), 1)
        with self.assertRaises(ValueError):
            selection.write_outputs(manifest, chosen, audit, out)

    def test_edit_similarity(self):
        self.assertEqual(selection.sequence_similarity("AAA", "AAA"), 1.0)
        self.assertAlmostEqual(selection.sequence_similarity("AAA", "AAG"), 2 / 3)
        self.assertEqual(selection.sequence_similarity("", "AAA"), 0.0)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "interface.tsv"
        self.header = "Chn1 Chn2 Type ipSAE pDockQ LIS\n"
        self.rows = ["A B min 0.95 0.9 0.9\n", "A C min 0.2 0.1 0.3\n",
                     "B C min 0.3 0.2 0.4\n"]

    def tearDown(self):
        self.temp.cleanup()

    def test_ambiguous_rows_fail_without_roles(self):
        self.path.write_text(self.header + "".join(self.rows))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            read_interface_metrics(self.path)

    def test_role_aware_result_is_order_invariant(self):
        for seed in range(20):
            rows = self.rows.copy()
            random.Random(seed).shuffle(rows)
            self.path.write_text(self.header + "".join(rows))
            result = read_interface_metrics(self.path, ["C"], ["A", "B"], False)
            self.assertEqual(result["ipSAE"], 0.2)
            self.assertEqual(result["interface_aggregation"], "pairwise_min_not_union")
            self.assertEqual(result["interface_pairs"], "A:C,B:C")

    def test_two_chain_compatibility(self):
        self.path.write_text(self.header + self.rows[0])
        self.assertEqual(read_interface_metrics(self.path)["ipSAE"], 0.95)

    def test_missing_interface_distinguishes_monomer(self):
        self.path.write_text(self.header)
        self.assertEqual(read_interface_metrics(self.path), {})
        with self.assertRaises(ValueError):
            read_interface_metrics(self.path, ["C"], ["A", "B"], False)

    def test_duplicate_pair_is_rejected(self):
        self.path.write_text(self.header + self.rows[0] * 2)
        with self.assertRaises(ValueError):
            read_interface_metrics(self.path, ["B"], ["A"])

    def test_overlapping_roles_are_rejected(self):
        self.path.write_text(self.header + self.rows[0])
        with self.assertRaises(ValueError):
            read_interface_metrics(self.path, ["A"], ["A"])

    def test_required_metric_cannot_be_silently_missing(self):
        self.path.write_text(self.header + "A B min nan 0.2 0.3\n")
        with self.assertRaises(ValueError):
            read_interface_metrics(self.path, ["B"], ["A"], False)


if __name__ == "__main__":
    unittest.main()
